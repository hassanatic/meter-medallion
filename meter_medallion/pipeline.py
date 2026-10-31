"""Load source files into bronze, then build every SQL model in dependency order and check its assertions.

Models live in models/<layer>/<name>.sql. Leading comment lines declare metadata, Dataform-style:

    -- depends: silver_readings, silver_apartments
    -- materialized: view            (default: table)
    -- assert: unique(meter_id, reading_at)
    -- assert: not_null(meter_id, reading_at)
    -- assert: row_condition(litres >= 0)
    -- assert: no_personal_data
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
SOURCES = ("bronze_buildings", "bronze_apartments", "bronze_readings")
_META = re.compile(r"^--\s*(depends|materialized|assert):\s*(.+?)\s*$")
_ASSERT = re.compile(r"^(\w+)(?:\((.*)\))?$")
PERSONAL_COLUMN = re.compile(r"name|email|phone|resident|address|contact|ssn|birth", re.IGNORECASE)


class PipelineError(Exception):
    pass


class AssertionFailed(PipelineError):
    pass


@dataclass
class Model:
    name: str
    layer: str
    sql: str
    depends: list[str] = field(default_factory=list)
    asserts: list[str] = field(default_factory=list)
    view: bool = False


@dataclass
class RunResult:
    connection: sqlite3.Connection
    built: list[str]
    row_counts: dict[str, int]
    assertions_checked: int


def load_models(directory: Path = MODELS_DIR) -> dict[str, Model]:
    models = {}
    for path in sorted(directory.glob("*/*.sql")):
        text = path.read_text()
        model = Model(name=path.stem, layer=path.parent.name, sql=text)
        for line in text.splitlines():
            if not line.startswith("--"):
                break
            match = _META.match(line)
            if not match:
                continue
            key, value = match.groups()
            if key == "depends":
                model.depends += [d.strip() for d in value.split(",") if d.strip()]
            elif key == "materialized":
                model.view = value.strip().lower() == "view"
            else:
                model.asserts.append(value)
        if model.name in models:
            raise PipelineError(f"duplicate model name {model.name}")
        models[model.name] = model
    return models


def build_order(models: dict[str, Model], sources=SOURCES) -> list[Model]:
    """Topological order; unknown dependencies and cycles are errors, not surprises at run time."""
    for model in models.values():
        for dep in model.depends:
            if dep not in models and dep not in sources:
                raise PipelineError(f"{model.name} depends on unknown table {dep}")

    ordered, done, visiting = [], set(sources), set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in done:
            return
        if name in visiting:
            raise PipelineError("dependency cycle: " + " -> ".join(path + (name,)))
        visiting.add(name)
        for dep in models[name].depends:
            visit(dep, path + (name,))
        visiting.discard(name)
        done.add(name)
        ordered.append(models[name])

    for name in sorted(models):
        visit(name, ())
    return ordered


def load_bronze(conn: sqlite3.Connection, data_dir: Path, load_id: str) -> None:
    """Bronze keeps source rows as they arrived (text), plus where and when they came from."""
    loaded_at = datetime.now(timezone.utc).isoformat()

    def create(table: str, columns: list[str]) -> None:
        cols = ", ".join(f"{c} TEXT" for c in columns)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols}, _load_id TEXT, _loaded_at TEXT, _source TEXT, _row INTEGER)")

    def insert(table: str, columns: list[str], rows, source: str) -> None:
        create(table, columns)
        marks = ", ".join("?" for _ in range(len(columns) + 4))
        conn.executemany(
            f"INSERT INTO {table} VALUES ({marks})",
            [[*(None if row.get(c) is None else str(row.get(c)) for c in columns), load_id, loaded_at, source, i]
             for i, row in enumerate(rows, start=1)],
        )

    for table, filename in (("bronze_buildings", "buildings.csv"), ("bronze_apartments", "apartments.csv")):
        with open(data_dir / filename, newline="") as f:
            reader = csv.DictReader(f)
            insert(table, list(reader.fieldnames or []), list(reader), filename)

    with open(data_dir / "readings.jsonl") as f:
        readings = [json.loads(line) for line in f if line.strip()]
    insert("bronze_readings", ["meter_id", "apartment_id", "ts", "cumulative_litres"], readings, "readings.jsonl")


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]


def check(conn: sqlite3.Connection, table: str, assertion: str) -> list[str]:
    """Return failure messages for one assertion (empty list when it holds)."""
    match = _ASSERT.match(assertion.strip())
    if not match:
        raise PipelineError(f"{table}: cannot parse assertion {assertion!r}")
    kind, arg = match.group(1), (match.group(2) or "").strip()

    if kind == "unique":
        keys = arg
        rows = conn.execute(
            f"SELECT {keys}, COUNT(*) FROM {table} GROUP BY {keys} HAVING COUNT(*) > 1 LIMIT 3").fetchall()
        return [f"{table}: duplicate ({keys}) = {row[:-1]} x{row[-1]}" for row in rows]
    if kind == "not_null":
        cols = [c.strip() for c in arg.split(",")]
        where = " OR ".join(f"{c} IS NULL" for c in cols)
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        return [f"{table}: {n} rows with NULL in ({arg})"] if n else []
    if kind == "row_condition":
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE NOT ({arg})").fetchone()[0]
        return [f"{table}: {n} rows break {arg}"] if n else []
    if kind == "no_personal_data":
        failures = [f"{table}: column {c} looks like personal data" for c in _columns(conn, table) if PERSONAL_COLUMN.search(c)]
        for column in _columns(conn, table):
            n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE CAST({column} AS TEXT) LIKE '%@%'").fetchone()[0]
            if n:
                failures.append(f"{table}: {n} values in {column} look like email addresses")
        return failures
    raise PipelineError(f"{table}: unknown assertion {kind}")


def build(conn: sqlite3.Connection, models: dict[str, Model]) -> tuple[list[str], int]:
    built, checked = [], 0
    for model in build_order(models):
        kind = "VIEW" if model.view else "TABLE"
        conn.execute(f"DROP {kind} IF EXISTS {model.name}")
        conn.execute(f"CREATE {kind} {model.name} AS {model.sql}")
        failures = []
        for assertion in model.asserts:
            failures += check(conn, model.name, assertion)
            checked += 1
        if failures:
            raise AssertionFailed("; ".join(failures))
        built.append(model.name)
    return built, checked


def run(data_dir: Path, db_path: str | Path = ":memory:", models_dir: Path = MODELS_DIR,
        load_id: str | None = None) -> RunResult:
    conn = sqlite3.connect(str(db_path))
    load_bronze(conn, Path(data_dir), load_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    built, checked = build(conn, load_models(models_dir))
    conn.commit()
    counts = {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in (*SOURCES, *built)}
    return RunResult(conn, built, counts, checked)

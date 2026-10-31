import sqlite3

import pytest

from meter_medallion.pipeline import AssertionFailed, PipelineError, build, build_order, check, load_models, run
from meter_medallion.sample import generate


def write(models_dir, layer, name, sql):
    path = models_dir / layer / f"{name}.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql)


def test_models_are_built_after_their_dependencies():
    order = [m.name for m in build_order(load_models())]
    for model in load_models().values():
        for dep in model.depends:
            if dep in order:
                assert order.index(dep) < order.index(model.name)


def test_a_dependency_cycle_is_an_error(tmp_path):
    write(tmp_path, "silver", "a", "-- depends: b\nSELECT 1 AS x")
    write(tmp_path, "silver", "b", "-- depends: a\nSELECT 1 AS x")
    with pytest.raises(PipelineError, match="cycle"):
        build_order(load_models(tmp_path))


def test_an_unknown_dependency_is_an_error(tmp_path):
    write(tmp_path, "silver", "a", "-- depends: nowhere\nSELECT 1 AS x")
    with pytest.raises(PipelineError, match="unknown table nowhere"):
        build_order(load_models(tmp_path))


def test_a_failing_assertion_stops_the_run_and_names_the_model(tmp_path):
    data = tmp_path / "data"
    generate(data)
    models = tmp_path / "models"
    write(models, "gold", "bad_totals",
          "-- depends: bronze_readings\n-- assert: unique(meter_id)\nSELECT meter_id FROM bronze_readings")
    with pytest.raises(AssertionFailed, match="bad_totals: duplicate"):
        run(data, models_dir=models)


def test_assertion_kinds():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER, v INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?, ?)", [(1, 5), (1, None), (2, -1)])
    assert check(conn, "t", "unique(id)")
    assert check(conn, "t", "not_null(v)")
    assert check(conn, "t", "row_condition(v >= 0)")
    assert check(conn, "t", "unique(id, v)") == []
    with pytest.raises(PipelineError, match="unknown assertion"):
        check(conn, "t", "sorted(id)")


def test_views_are_supported(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bronze_buildings (x INTEGER)")
    write(tmp_path, "serve", "v", "-- depends: bronze_buildings\n-- materialized: view\nSELECT x FROM bronze_buildings")
    built, _ = build(conn, load_models(tmp_path))
    assert built == ["v"]
    assert conn.execute("SELECT type FROM sqlite_master WHERE name = 'v'").fetchone()[0] == "view"

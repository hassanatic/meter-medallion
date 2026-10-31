"""Deterministic synthetic source data, shaped like what real source systems send.

- buildings.csv and apartments.csv: a CRM-style export, including personal data (contact and resident
  names, emails) that must never reach the AI-facing dataset.
- readings.jsonl: hourly cumulative meter readings from a meter API, with the usual problems: re-sent
  duplicates, rows out of order, a meter that resets to zero, and a few malformed rows.

Apartment A-0103 has a constant leak (water flows every night); nobody else does.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAYS = 10
LEAKING = "A-0103"
RESETTING = "A-0202"


def generate(out: Path, seed: int = 42) -> dict[str, int]:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    buildings = [
        ("B-01", "Rantakatu 4", "Kokkola", "Maija Virtanen", "maija.virtanen@example.com"),
        ("B-02", "Puistotie 12", "Pori", "Jussi Laine", "jussi.laine@example.com"),
        ("B-03", "Asemakatu 7", "Kokkola", "Anna Koski", "anna.koski@example.com"),
    ]
    with open(out / "buildings.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["building_id", "address", "city", "contact_name", "contact_email"])
        w.writerows(buildings)

    apartments = []
    for b, (building_id, *_rest) in enumerate(buildings, start=1):
        for n in range(1, 5):
            apartments.append((f"A-0{b}0{n}", building_id, f"Resident {b}{n}"))
    with open(out / "apartments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["apartment_id", "building_id", "resident_name"])
        w.writerows(apartments)

    rows = []
    for apartment_id, _building, _name in apartments:
        meter_id = "M-" + apartment_id[2:]
        total = rng.randint(100_000, 900_000)
        for h in range(DAYS * 24):
            ts = START + timedelta(hours=h)
            if 7 <= ts.hour <= 22:
                total += rng.choice([0, 0, 5, 12, 30, 45])
            elif ts.hour == 23 and rng.random() < 0.2:
                total += 3  # an occasional late tap, not a leak
            if apartment_id == LEAKING:
                total += 2
            if apartment_id == RESETTING and h == 5 * 24:
                total = 0  # meter replaced: the counter starts again
            rows.append({"meter_id": meter_id, "apartment_id": apartment_id,
                         "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "cumulative_litres": total})

    resent = rng.sample(rows, 25)
    bad = [
        {"meter_id": "M-0101", "apartment_id": "A-0101", "ts": "not-a-time", "cumulative_litres": 10},
        {"meter_id": "M-0101", "apartment_id": "A-0101", "ts": "2026-10-03T04:00:00Z", "cumulative_litres": None},
        {"meter_id": "M-9999", "apartment_id": "A-9999", "ts": "2026-10-03T04:00:00Z", "cumulative_litres": 50},
    ]
    all_rows = rows + resent + bad
    rng.shuffle(all_rows)
    with open(out / "readings.jsonl", "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")

    return {"buildings": len(buildings), "apartments": len(apartments), "readings": len(all_rows),
            "duplicates": len(resent), "malformed": len(bad)}

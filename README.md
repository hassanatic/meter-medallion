# meter-medallion

A small bronze / silver / gold SQL pipeline for water-meter data. Source files land in **bronze** as
they arrived, **silver** types, validates and de-duplicates them, **gold** turns them into reusable
datasets, and a **serve** layer holds what dashboards and AI tools read. Every model is a plain SQL
file with Dataform-style metadata, and the run fails if any model breaks its assertions.

It runs on SQLite so it needs nothing but Python; the models are ordinary SQL with window functions and
would port to a cloud warehouse with small dialect changes.

```bash
pip install -e ".[test]"
python -m meter_medallion sample --out data/sample      # synthetic source files
python -m meter_medallion run --data data/sample --db build/warehouse.db
pytest -q
```

```
silver_readings                     2880
silver_rejected_readings               3
gold_leak_alerts                       1
...
12 models built, 19 assertions passed
```

## Layers

| layer | model | what it does |
|---|---|---|
| bronze | `bronze_buildings`, `bronze_apartments`, `bronze_readings` | rows exactly as received, as text, with load id, load time, source file and row number |
| silver | `silver_readings_typed` | types every reading and records why it is unusable (bad timestamp, missing value, unknown apartment) |
| silver | `silver_rejected_readings` | the quarantine: bad rows kept with their reason so they can be fixed at source |
| silver | `silver_readings` | one reading per meter and time; a re-sent reading is a duplicate and the latest load wins |
| silver | `silver_consumption` | litres per interval from the running totals; a drop in the total is a meter reset, never negative use |
| gold | `gold_daily_consumption`, `gold_building_daily` | daily use per apartment and per building |
| gold | `gold_night_flow`, `gold_leak_alerts` | nights where water ran in every hour from 01:00 to 05:00; three such nights raise a leak alert |
| serve | `report_building_kpis` | one row per building for dashboards: totals, litres per day, open leak alerts |
| serve | `ai_building_consumption` | the dataset AI tools may query: aggregated, with no names, emails, residents or addresses |

## Model metadata

```sql
-- depends: silver_readings
-- assert: unique(meter_id, interval_start)
-- assert: row_condition(litres >= 0)
SELECT ...
```

- `depends` orders the build; an unknown table or a cycle is an error before anything runs.
- `materialized: view` builds a view instead of a table.
- Assertions: `unique(cols)`, `not_null(cols)`, `row_condition(expr)` and `no_personal_data`, which fails
  if a column name looks personal (name, email, phone, resident, address, contact) or a value looks like
  an email address.

## The sample data

`sample.py` writes deterministic synthetic files shaped like real sources: a CRM export with contact and
resident names (the personal data the AI dataset must not contain) and hourly meter readings with
re-sent duplicates, rows out of order, a meter that resets to zero and three malformed rows. One
apartment has a constant leak. The tests check that the pipeline finds exactly that apartment, drops the
duplicates, quarantines the bad rows with the right reasons, and keeps personal data out of the AI view.

## Not in scope

Incremental loads, a scheduler, a real warehouse, and real customer data.

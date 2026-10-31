-- One clean reading per meter and time. A re-sent reading is a duplicate; the latest load wins.
-- depends: silver_readings_typed
-- assert: unique(meter_id, reading_at)
-- assert: not_null(meter_id, apartment_id, reading_at, cumulative_litres)
SELECT meter_id, apartment_id, reading_at, cumulative_litres
FROM (
    SELECT
        meter_id,
        apartment_id,
        datetime(ts) AS reading_at,
        cumulative_litres,
        ROW_NUMBER() OVER (
            PARTITION BY meter_id, datetime(ts)
            ORDER BY _load_id DESC, _row DESC
        ) AS rn
    FROM silver_readings_typed
    WHERE reject_reason IS NULL
)
WHERE rn = 1

-- Every bronze reading, typed, with the reason it is unusable (NULL when it is fine).
-- depends: bronze_readings, silver_apartments
SELECT
    r.meter_id,
    r.apartment_id,
    r.ts,
    CAST(r.cumulative_litres AS INTEGER) AS cumulative_litres,
    r._load_id,
    r._row,
    CASE
        WHEN datetime(r.ts) IS NULL THEN 'unparseable timestamp'
        WHEN r.cumulative_litres IS NULL OR r.cumulative_litres = '' THEN 'missing reading'
        WHEN a.apartment_id IS NULL THEN 'unknown apartment'
        WHEN CAST(r.cumulative_litres AS INTEGER) < 0 THEN 'negative reading'
    END AS reject_reason
FROM bronze_readings r
LEFT JOIN silver_apartments a ON a.apartment_id = r.apartment_id

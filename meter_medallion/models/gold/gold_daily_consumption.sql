-- depends: silver_consumption
-- assert: unique(apartment_id, day)
-- assert: row_condition(litres >= 0)
SELECT
    apartment_id,
    date(interval_start) AS day,
    SUM(litres) AS litres,
    SUM(meter_reset) AS meter_resets,
    COUNT(*) AS intervals
FROM silver_consumption
GROUP BY apartment_id, date(interval_start)

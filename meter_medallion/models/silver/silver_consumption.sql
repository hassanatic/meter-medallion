-- Litres used between consecutive readings of a meter. Meters report a running total, so use is the
-- difference; when the total drops the meter was reset or replaced, and the new total is the use.
-- depends: silver_readings
-- assert: unique(meter_id, interval_start)
-- assert: row_condition(litres >= 0)
SELECT
    meter_id,
    apartment_id,
    prev_at AS interval_start,
    reading_at AS interval_end,
    CASE
        WHEN cumulative_litres >= prev_litres THEN cumulative_litres - prev_litres
        ELSE cumulative_litres
    END AS litres,
    CASE WHEN cumulative_litres < prev_litres THEN 1 ELSE 0 END AS meter_reset
FROM (
    SELECT
        *,
        LAG(cumulative_litres) OVER w AS prev_litres,
        LAG(reading_at) OVER w AS prev_at
    FROM silver_readings
    WINDOW w AS (PARTITION BY meter_id ORDER BY reading_at)
)
WHERE prev_litres IS NOT NULL

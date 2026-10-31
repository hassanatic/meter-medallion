-- Nights on which water flowed in every hour between 01:00 and 05:00: nobody runs a tap all night,
-- so this is the classic sign of a leaking toilet or pipe.
-- depends: silver_consumption
-- assert: unique(apartment_id, night)
SELECT apartment_id, date(interval_start) AS night, COUNT(*) AS hours_with_flow
FROM silver_consumption
WHERE CAST(strftime('%H', interval_start) AS INTEGER) BETWEEN 1 AND 4
  AND litres > 0
GROUP BY apartment_id, date(interval_start)
HAVING COUNT(*) = 4

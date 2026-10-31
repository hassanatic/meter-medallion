-- depends: gold_daily_consumption, silver_apartments
-- assert: unique(building_id, day)
SELECT
    a.building_id,
    d.day,
    SUM(d.litres) AS litres,
    COUNT(DISTINCT d.apartment_id) AS apartments_reporting
FROM gold_daily_consumption d
JOIN silver_apartments a USING (apartment_id)
GROUP BY a.building_id, d.day

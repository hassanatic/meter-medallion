-- Serve layer for dashboards: one row per building.
-- depends: gold_building_daily, gold_leak_alerts, silver_buildings
-- assert: unique(building_id)
-- assert: not_null(building_id, city)
SELECT
    b.building_id,
    b.address,
    b.city,
    COALESCE(SUM(g.litres), 0) AS litres_total,
    ROUND(1.0 * SUM(g.litres) / NULLIF(COUNT(DISTINCT g.day), 0), 1) AS litres_per_day,
    (SELECT COUNT(*) FROM gold_leak_alerts l WHERE l.building_id = b.building_id) AS open_leak_alerts
FROM silver_buildings b
LEFT JOIN gold_building_daily g USING (building_id)
GROUP BY b.building_id, b.address, b.city

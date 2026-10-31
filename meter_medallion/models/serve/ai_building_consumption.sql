-- The dataset AI tools may query: aggregated per building and day, with no names, emails, residents
-- or street addresses. The no_personal_data assertion fails the run if any of that leaks in.
-- depends: gold_building_daily, silver_buildings, gold_leak_alerts
-- materialized: view
-- assert: no_personal_data
-- assert: unique(building_id, day)
SELECT
    g.building_id,
    b.city,
    g.day,
    g.litres,
    g.apartments_reporting,
    (SELECT COUNT(*) FROM gold_leak_alerts l WHERE l.building_id = g.building_id) AS leak_alerts
FROM gold_building_daily g
JOIN silver_buildings b USING (building_id)

-- depends: gold_night_flow, silver_apartments
-- assert: unique(apartment_id)
-- assert: row_condition(nights_with_continuous_flow >= 3)
SELECT
    n.apartment_id,
    a.building_id,
    COUNT(*) AS nights_with_continuous_flow,
    MIN(n.night) AS first_night,
    MAX(n.night) AS last_night
FROM gold_night_flow n
JOIN silver_apartments a USING (apartment_id)
GROUP BY n.apartment_id, a.building_id
HAVING COUNT(*) >= 3

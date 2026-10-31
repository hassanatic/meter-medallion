-- depends: bronze_apartments, silver_buildings
-- assert: unique(apartment_id)
-- assert: not_null(apartment_id, building_id)
SELECT DISTINCT a.apartment_id, a.building_id, a.resident_name
FROM bronze_apartments a
JOIN silver_buildings b USING (building_id)

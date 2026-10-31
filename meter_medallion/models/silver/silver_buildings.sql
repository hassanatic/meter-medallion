-- depends: bronze_buildings
-- assert: unique(building_id)
-- assert: not_null(building_id, city)
SELECT DISTINCT building_id, address, city, contact_name, contact_email
FROM bronze_buildings

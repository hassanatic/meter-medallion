-- Quarantine: rows that never reach the clean layers, kept with the reason so they can be fixed at source.
-- depends: silver_readings_typed
-- assert: not_null(reject_reason)
SELECT meter_id, apartment_id, ts, cumulative_litres, reject_reason
FROM silver_readings_typed
WHERE reject_reason IS NOT NULL

-- Initial domain schema is defined by SQLAlchemy metadata; startup uses create_all.
-- flow_studies(name UNIQUE,direction); dose_levels(study_id,label UNIQUE,flow)
-- pressure_readings(study_id,specimen_ref UNIQUE,level_id,pressure,measurement_note)
-- monotone_runs(config JSON,result JSON,status), validation_notes(result_snapshot JSON,status)
-- users(email UNIQUE), audit_logs. No production migration runner is claimed.

-- 002: recorded production batch per independent filter.
-- Nullable by design: historical readings without a batch stay unlabeled and are
-- never assigned one. Startup applies the same idempotent ALTER for existing databases.
ALTER TABLE pressure_readings ADD COLUMN IF NOT EXISTS production_batch VARCHAR(80);

-- Schema 2 adds oscillator/lifecycle/information fields inside versioned state JSON.
-- Old event payloads are never rewritten; readers supply schema-1 defaults.
IF NOT EXISTS(SELECT 1 FROM SCHEMA_MIGRATIONS WHERE version=2)
INSERT INTO SCHEMA_MIGRATIONS(version) VALUES(2);
GO
CREATE OR ALTER VIEW POINT_OSCILLATORS AS
SELECT * FROM POINT_EVENTS WHERE kind IN ('oscillator_configuration','mapping_configuration','mapping_status');
GO
CREATE OR ALTER VIEW POINT_TELEMETRY AS
SELECT * FROM POINT_EVENTS WHERE kind='telemetry';
GO

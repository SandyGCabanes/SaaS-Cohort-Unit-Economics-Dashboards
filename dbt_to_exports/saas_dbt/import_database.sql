-- Import all from parquet · SQL
-- Bulk-reloads every table from a folder created by export_all_to_parquet.sql.
-- Run this against a fresh or empty database, not the one that produced
-- the export, unless the existing tables should be dropped first.
 
IMPORT DATABASE 'export_directory';
-- Writes every mart table to a Parquet file inside the project.
-- Run it from the project folder, after dbt build, so the relative
-- folder parquet_exports resolves to the folder inside the project.
-- The folder parquet_exports/reporting
-- must already exist. It ships with the project.
-- The same export is available as one dbt command:
--     dbt run-operation export_marts_to_parquet
-- Example with the DuckDB command line:
--     duckdb saas_reporting.duckdb < export_marts_to_parquet.sql

COPY main_marts.unit_economics_grid TO 'parquet_exports/unit_economics_grid.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

-- Reporting-engine marts
COPY main_reporting_marts.cohort_metrics_long TO 'parquet_exports/reporting/cohort_metrics_long.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.monthly_metrics_long TO 'parquet_exports/reporting/monthly_metrics_long.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.nrr_long TO 'parquet_exports/reporting/nrr_long.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.mrr_movements_long TO 'parquet_exports/reporting/mrr_movements_long.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.arr_movements_long TO 'parquet_exports/reporting/arr_movements_long.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.kpi_summary TO 'parquet_exports/reporting/kpi_summary.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.arr_by_month TO 'parquet_exports/reporting/arr_by_month.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

-- Added in v5a: inputs for build_dashboard_from_marts.py
COPY main_reporting_marts.cac_per_customer_by_channel TO 'parquet_exports/reporting/cac_per_customer_by_channel.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY main_reporting_marts.unit_economics_by_cohort TO 'parquet_exports/reporting/unit_economics_by_cohort.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);

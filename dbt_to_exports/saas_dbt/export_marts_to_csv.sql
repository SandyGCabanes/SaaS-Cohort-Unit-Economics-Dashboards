-- Writes every mart table to a CSV file inside the project.
-- Run it from the project folder, after dbt build, so the relative
-- folder csv_exports resolves to the folder inside the project.
-- The folder csv_exports/reporting
-- must already exist. It ships with the project.
-- CSV files are plain text. They open in Excel, Tableau or any text editor
-- with no password.
-- Example with the DuckDB command line:
--     duckdb saas_reporting.duckdb < export_marts_to_csv.sql

COPY main_marts.unit_economics_grid TO 'csv_exports/unit_economics_grid.csv' (FORMAT CSV, HEADER);

-- Reporting-engine marts
COPY main_reporting_marts.cohort_metrics_long TO 'csv_exports/reporting/cohort_metrics_long.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.monthly_metrics_long TO 'csv_exports/reporting/monthly_metrics_long.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.nrr_long TO 'csv_exports/reporting/nrr_long.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.mrr_movements_long TO 'csv_exports/reporting/mrr_movements_long.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.arr_movements_long TO 'csv_exports/reporting/arr_movements_long.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.kpi_summary TO 'csv_exports/reporting/kpi_summary.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.arr_by_month TO 'csv_exports/reporting/arr_by_month.csv' (FORMAT CSV, HEADER);

-- Added in v5a: inputs for build_dashboard_from_marts.py
COPY main_reporting_marts.cac_per_customer_by_channel TO 'csv_exports/reporting/cac_per_customer_by_channel.csv' (FORMAT CSV, HEADER);
COPY main_reporting_marts.unit_economics_by_cohort TO 'csv_exports/reporting/unit_economics_by_cohort.csv' (FORMAT CSV, HEADER);

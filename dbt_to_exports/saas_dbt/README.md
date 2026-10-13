# SaaS Reporting Analytics dbt Project

## Problem
The Analyst created a Python notebook that analyzes SaaS subscription data. 
This was a precursor before building the actual dashboard.
The notebook reads two CSV files: a revenue export and a cost export. 
These two are previous staging outputs from dbt_from_raw model, and stored
in an accessible folder.  The notebook calculates standard SaaS metrics 
such as MRR, churn, retention, and customer lifetime value.

The notebook requires reshaping csv files in order to build html plotly dashboards 
or use BI tools like Tableau, or even excel pivot tables.

## Solution
This project rebuilds the notebook's re-shaping logic as a dbt project. Now this dbt 
can turn raw database tables into clean, tested, documented tables using
SQL. Two CSV files feed the project: `customer_month_panel.csv` and
`cost_per_customer.csv`. dbt reads them from the landing zone folder and
names them `fct_revenue` and `fct_cost`. The project produces a full set of SaaS
metrics tables in a single database file `saas_reporting.duckdb`. It also
exports CSVs for pickup by reporting BI tools, or even excel.

This dbt project produces one set of output tables, in long form. One row holds
one value, and a `metric_name` column says which metric it is. The Python
reporting engine, HTML dashboards, Tableau and Excel can all read the same
tables, with minimal reshaping.

## Benefits
- One database `saas_reporting.duckdb` file holds every metric. No more scattered CSVs.
- Every table has automated tests. Bad data gets caught early.
- Refreshing data does not require rebuilding anything. One command
  refreshes every table.
- One consumer-ready layer exists. No manual reshaping is needed for
  Tableau, Excel, HTML dashboards or a Python reporting engine.
- The notebook remains available as an independent check on the pipeline's
  output.

## How It Works

### Project structure
The project has three layers of models. Each layer builds on the one
before it.

1. Staging. This layer reads the two source tables, `fct_revenue` and
   `fct_cost`. It only renames and casts columns. It adds no business
   logic.
2. Intermediate. This layer builds shared building blocks. Examples
   include a customer-by-month grid, a retention base table, and the large
   customer-by-month movement tables. These models are not meant to be
   queried directly by any dashboard or report.
3. Marts. This is the final layer. Every table a dashboard or report
   should query lives here. The `reporting` folder holds the long-form
   tables. One shared table, `unit_economics_grid`, sits at the top of the
   layer, outside that folder, because it is an aggregate data check.

### Why use DuckDB instead of SQLite
DuckDB runs window functions and large cross-joins faster than SQLite.
Several models in this project depend on both.

DuckDB also has a built-in command called PIVOT. SQLite has
no equivalent command, and building the same grid there would require dbt
to generate a fixed list of columns in advance. That approach breaks the
moment a new column should appear.

If the source system writes to SQLite instead of DuckDB, DuckDB can still
read that SQLite file directly. It can then write all output tables to a
separate DuckDB file. This project does not implement that setup, but it is
straightforward to add later.

### How to refresh data

1. Place the newest `customer_month_panel.csv` and `cost_per_customer.csv`
   in the landing zone folder. This folder simulates the cloud storage
   bucket. Each new file fully replaces the old one. 
2. The staging layer reads the two CSV files directly. Every downstream
   table is then rebuilt in the correct order.
3. The Parquet files and the CSV files are written automatically at the end of a
   full `dbt build`. They go to the `parquet_exports` and `csv_exports` folders in the
   project. If any step fails, or the build covers only some models, both exports
   are skipped and the log says why. 
4. To write one set on its own, run `dbt run-operation export_marts_to_parquet` 
   or `dbt run-operation export_marts_to_csv`.
   The root files `export_marts_to_parquet.sql` and `export_marts_to_csv.sql` do the
   same job from the DuckDB command line, outside dbt.

### Input files and 24-month CLV
The panel file should have these columns:

| File | Columns |
|---|---|
| `customer_month_panel.csv` | `customer_id, channel, plan_tier, cohort_year, cohort_month, calendar_month, lifetime_month, is_active, mrr, customer_clv_24m, customer_cac, unit_clv_cac_ratio_24m, is_mature_24m` |
| `cost_per_customer.csv` | `cohort_year, cohort_month, channel, plan_tier, new_customers, segment_mix_share_percentage, cac_per_customer_dollars, total_acquisition_cost_dollars` |

`customer_clv_24m` is the customer's MRR added up over lifetime months 0 to
23. It repeats on every row of that customer. The uncapped older columns
`customer_clv` and `unit_clv_to_cac_ratio` are gone.

`is_mature_24m` is true when a cohort has been observed for the full 24
months. When the data ends in 2028-12, the last mature cohort is 2027-01.
Unit economics count mature customers only. Each customer counts once.
This way every customer in the average has had the same 24 months to earn
revenue.

Where the 24-month limit shows up:

| Table | What it holds now |
|---|---|
| `unit_economics_grid` | `clv_24m`, `average_cac` and `clv_to_cac_ratio` per channel and plan tier, mature customers only. `mature_customers` shows how many customers each row uses. |
| `cohort_metrics_long` | The `cumulative_ltv` and `ltv_cac_ratio` rows stop at period 23. The last period is the 24-month figure. |
| `reindexed_panel_audit_mrr` and `_arr` | Intermediate tables in the database only. They carry `customer_clv_24m`, `unit_clv_cac_ratio_24m` and `is_mature_24m` on every row. |

Two notes:

- The limit for the month-by-month tables is the dbt variable
  `clv_horizon_months` in `dbt_project.yml`. It is set to 24. The 24-month
  figures inside the panel file are consistent.
- A cohort that has no rows in `cost_per_customer.csv` drops out of
  the `ltv_cac_ratio` rows in `cohort_metrics_long`, because its CAC is
  unknown.

### Materialization
Four large tables in this project are stored as real tables, not views.
They are `customer_level_movements_mrr`, `customer_level_movements_arr`,
`reindexed_panel_audit_mrr` and `reindexed_panel_audit_arr`. They live in
`models/intermediate/`. Each one has a row for every customer in every
month. On the full data, a CSV export of each one ran from about 520 MB to
680 MB, so they stay in the database and are not exported to CSV or
Parquet. Building them requires a cross-join and a window function. That
calculation is expensive. 

Three reporting tables read from them (`mrr_movements_long`, 
`arr_movements_long` and `monthly_metrics_long`).
Storing them as views could incur repeated compute cost.

Every other model in the intermediate layer stays a view. 

## Appendix

### Mart, shape, and what it feeds
The reporting-engine tables all follow a consistent shape. This lets one
chart component work for many different metrics, just by pointing it at a
different `metric_name` value.

| Mart | Shape | Feeds |
|---|---|---|
| `cohort_metrics_long` | `segment_type, segment_value, cohort_month, period, metric_name, metric_value` | Retention heatmap and cohort line charts. Filter by `metric_name`: `retention_rate`, `mrr_total`, `avg_mrr`, `cumulative_ltv`, `ltv_cac_ratio`, `mrr_retention_rate`, `active_customers`. `cumulative_ltv` and `ltv_cac_ratio` stop at period 23 (24-month CLV). |
| `monthly_metrics_long` | `segment_type, segment_value, calendar_month, metric_name, metric_value` | Monthly trend line and bar charts. |
| `nrr_long` | `segment_type, segment_value, calendar_month, nrr_percentage` | Net revenue retention trend, blended or segmented. |
| `mrr_movements_long` and `arr_movements_long` | `calendar_month, movement_type, delta_value` | Stacked-bar or waterfall movement charts. |
| `arr_by_month` | `calendar_month, total_mrr, arr_value` | Annual run-rate line chart. `arr_value` is `total_mrr` times 12. |
| `kpi_summary` | `segment_type, segment_value, metric_name, period, current_value, previous_value, pct_change` | KPI cards. `pct_change` is already calculated. |
| `unit_economics_grid` | `channel, plan_tier, mature_customers, clv_24m, average_cac, clv_to_cac_ratio` | Already in a usable shape. Used as-is. 24-month CLV over mature cohorts only. |
| `cac_per_customer_by_channel` (v5a) | `cohort_month, channel, cohort_cac` | CAC-by-channel chart. Total spend divided by total new customers, all plan tiers together. Also gives blended CAC per cohort when weighted by cohort size. |
| `unit_economics_by_cohort` (v5a) | `cohort_month, channel, plan_tier, mature_customers, ltv_24m, average_cac` | The unit economics grid with `cohort_month` kept. Lets a dashboard rebuild the grid for any window of cohorts. Weight each row by `mature_customers`. Mature cohorts only. |


**Test only**
- `dbt test --select path:models/marts/reporting` runs just the tests for the reporting marts. There are 9 reporting marts, and 8 of them have tests. `arr_by_month` has none yet.

**Build and test together**
- `dbt build --select path:models/marts/reporting` runs the models then tests them right after, in dependency order. This is usually the better choice, since a failed test on one model stops it from feeding a broken result downstream in the same run.

### In - progress ---- html dashboard builder to be updated
### Files for an HTML dashboard builder (v5a)
`build_dashboard_from_marts.py` reads only the files in
`csv_exports/reporting`. After a full `dbt build`, that folder holds 9 CSV
files. The script needs these 5 to draw the dashboard:
`monthly_metrics_long`, `nrr_long`, `mrr_movements_long`,
`cohort_metrics_long` and `cac_per_customer_by_channel`.

Two more are optional. `unit_economics_by_cohort` fills the channel by plan
tier table in the Unit Economics card for each timeframe. `arr_movements_long`
and `kpi_summary` are used only to cross-check the others.

`arr_by_month` and `unit_economics_grid` are exported too, but the script
does not read them. It works out ARR as total MRR times 12.

### Deviations from the notebook
Some tables differ from what the notebook (`saas_validation_v9_2`) produced.
These differences are intentional.

- Retention by channel and by plan tier. In the notebook, a loop builds one
  retention grid per channel or per plan tier. But the loop overwrites its
  own result each time. Only the last channel's grid was ever saved to the
  notebook's CSV. This project fixes that. Every channel and every plan
  tier is included in `cohort_metrics_long`, as the `segment_type` and
  `segment_value` columns.
- `unit_economics_grid`. CLV and CAC are built differently from the
  notebook's CLV:CAC section.
  - The notebook builds CLV one month of life at a time. For each month of
    life, it uses every cohort that has reached that month. A young cohort
    counts only for the months it has lived. Its CAC is total spend divided
    by all customers acquired, young cohorts included.
  - This project follows `saas_kpi_engine.py`. It keeps mature customers
    only, meaning cohorts observed for the full 24 months. It averages each
    customer's 24-month CLV. CAC is the average CAC of those same
    customers. Each customer counts once.
  - Both methods are valid. On the full files, the ratios agree within
    0.4% for every channel and plan tier. The notebook rounds to 2
    decimals, which explains most of the difference. This project keeps
    full precision. Formatting belongs in the BI tool or report.
  - The notebook's CLV:CAC by channel alone can be rebuilt from this table.
    Weight each row by `mature_customers`. The oldest-cohort-only version
    has no table here.
- LTV table of the oldest cohort. The notebook builds this table over the
  cohort's whole observed history. This project has no table for it. The
  same figures come from `cohort_metrics_long` for the oldest cohort. The
  first 24 months use the same arithmetic. Later months are not produced,
  because `cumulative_ltv` stops at lifetime month 23.
- Notebook-only sections. These have no dbt counterpart: the data integrity checks, the price parity check, and the
  analysis of what stopping a channel would cost, including months to earn
  back CAC. CAC over time by channel was in this list until v5a. It now
  comes from `cac_per_customer_by_channel`.

### Setup
1. Use the `profiles.yml` that ships in the project folder. Or copy it to
   `~/.dbt/profiles.yml`. Or set the `DBT_PROFILES_DIR` environment
   variable to point at it. Whichever you pick, set the `path` value to the location of `saas_reporting.duckdb`.
   This database holds the source tables and every model built from them, up to
   the marts. The first dbt layer keeps its own database, saas_analytics.db, so
   the two files do not get mixed up. DuckDB names a database after its file, so
   the name in `models/staging/sources.yml` (`database:`) has to match this file name.
2. Install dbt and the DuckDB adapter: `pip install dbt-core dbt-duckdb`.
3. Run `dbt build`.

Version v5 was tested end to end, against 100-customer sample files that
match the 24-month schema of both CSV files. All 33 models built and all 37
automated tests passed. Version v5a adds 2 models and 10 tests, so a full
build should now show 35 models and 47 tests. The v5a additions have not
been run in dbt yet. Their SQL was checked outside dbt on small made-up
tables, and their output columns were checked against
`build_dashboard_from_marts.py`. Run `dbt build` once on the sample files,
then on the full files, before relying on the numbers.

### Change history
See the `docs/` folder for a record of what changed at each step, and how
to reverse each change if needed. Files are named
`edits_v1_to_v2.txt`, `edits_v2_to_v3.txt`, and so on.
`edits_clv_24m.txt` covers the move to 24-month CLV.
`edits_v4_to_v5.txt` covers the removal of the Tableau folder.
`edits_v5_to_v5a.txt` covers the two new reporting marts, the new test, and
the export lines for both.

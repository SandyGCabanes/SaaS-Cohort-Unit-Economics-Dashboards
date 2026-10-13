# SaaS Dashboard Built from the dbt Exports

## What this does

`build_dashboard_from_dbt_exports.py` turns the CSV files exported by the dbt
reporting model into a set of standalone HTML dashboards. It reads only those
export files. 

Each HTML page is one two-year timeframe containing two tabs:

- **Revenue tab.** 7 cards covering MRR, ARR, MRR movements, ARPU, revenue churn,
  net revenue retention and a revenue retention heatmap.
- **Customers tab.** 7 cards covering active customers, customer churn, CAC by
  channel, two kinds of retention heatmaps, unit economics and LTV:CAC payback.

Each page is a single file with the Plotly library embedded, so it opens offline in
any browser. Next to the pages, the script saves the numbers behind every card as one
Excel workbook and as CSV files.

The dbt model already did the heavy work. This script only cuts the tables at the
last real month, reshapes them, and draws them. Section "How the numbers are built"
lists the few calculations it adds.

## Requirements

- Python 3 with `pandas`, `numpy`, `plotly` and `openpyxl`.
- Written and run with Python 3.12, pandas 3, plotly 7 and openpyxl 3.1.
- The dbt export CSV files listed below. 

```
pip install pandas numpy plotly openpyxl
```

## Source files

The script looks for each file in the folder given by `--exports-dir`, then in that
folder's `reporting/` subfolder. All seven files are required. If one is missing, or
a required column is missing, the script stops and says which.

| File | One row is | Columns the script reads | Feeds |
|---|---|---|---|
| `monthly_metrics_long.csv` | one metric for one calendar month | `segment_type, segment_value, calendar_month, metric_name, metric_value` | Total MRR, ARPU, revenue churn, active customers, customer churn |
| `arr_by_month.csv` | one calendar month | `calendar_month, total_mrr, arr_value` | ARR |
| `mrr_movements_long.csv` | one movement type for one calendar month | `calendar_month, movement_type, delta_value` | MRR Movements |
| `nrr_long.csv` | one calendar month for one segment | `segment_type, segment_value, calendar_month, nrr_percentage` | Net Revenue Retention |
| `cohort_metrics_long.csv` | one metric for one cohort, segment and month of life | `segment_type, segment_value, cohort_month, period, metric_name, metric_value` | All heatmaps, LTV:CAC Payback, blended CAC |
| `cac_per_customer_by_channel.csv` | one cohort and channel | `cohort_month, channel, cohort_cac` | CAC by Channel, blended CAC |
| `unit_economics_by_cohort.csv` | one cohort, channel and plan tier | `cohort_month, channel, plan_tier, mature_customers, ltv_24m, average_cac` | Unit Economics |

**Metrics used from the long tables** (all with `segment_type = all` unless noted):

| Table | `metric_name` values the script uses |
|---|---|
| `monthly_metrics_long` | `total_mrr`, `arpu`, `active_customers`, `new_customers`, `churned_customers`, `logo_churn_rate_pct`, `revenue_churn_rate_pct` |
| `cohort_metrics_long` | `retention_rate` (all, by channel, by plan tier), `mrr_retention_rate`, `ltv_cac_ratio`, and `active_customers` for each channel at period 0 |

The cohort file must also contain `cumulative_ltv` rows. The script does not chart
them. It checks for them to catch a partial or sampled file.

**Files in the export folder that are not read:**

| File | Why it is not needed |
|---|---|
| `arr_movements_long.csv` | It is the MRR movements multiplied by 12. |
| `kpi_summary.csv` | It is the monthly metrics plus last month's value. The script builds its own change badges. |
| `unit_economics_grid.csv` | It is `unit_economics_by_cohort.csv` summed over all cohorts. The by-cohort file can be summed for any timeframe. |

## How to run

### From terminal
```
python build_dashboard_from_dbt_exports.py --exports-dir csv_exports
```

| Option | Meaning | Default |
|---|---|---|
| `--exports-dir` | Folder with the export CSV files | `csv_exports` |
| `--output-dir` | Folder for the HTML pages | `docs` |
| `--data-dir` | Folder for the workbook and CSV files | `dashboard_data` |
| `--as-of YYYY-MM` | The last month that has happened. Later months are dropped. `none` keeps every month | `2025-12` (the constant `AS_OF_MONTH`) |
| `--only SLUG ...` | Build only these timeframes, for example `--only all 2024-2025` | The list in `TIMEFRAMES_TO_BUILD` |
| `--plotly external` | Write `plotly.min.js` once and link to it, so each page is much smaller | `inline` |

### From VSCode
- Set `TIMEFRAMES_TO_BUILD` (see Timeframes below)
- Set `AS_OF_MONTH` near the top of the script. 
- Set `TIMEFRAMES_TO_BUILD = None` to build every timeframe.

### Timeframes

Each timeframe is one HTML page and will appear with a button. 
`TIMEFRAME_OPTIONS` in the script lists them, and you can add to the time periods there.

| Row of buttons | Timeframes (slug) |
|---|---|
| Full period | `all` (written as `index.html`) |
| 2 years | `2022-2023`, `2023-2024`, `2024-2025`, `2025-2026`, `2026-2027` |
| 3 years | `2022-2024`, `2023-2025`, `2024-2026`, `2025-2027`, `2026-2028` |

The other pages are named `saas_dashboard_<slug>.html`. The Timeframe buttons in the
top right corner link the pages to each other by file name, so keep all the pages in
one folder. Only the timeframes built in a run get a button. A timeframe that starts
after the as-of month has no data and is skipped with a message.

### The as-of month caps the most recent month in the build

The exports can contain months that have been pre-simulated or planned but have not happened.
The as-of month marks the last real month. Before any chart is built, the script:

- drops monthly rows after the as-of month,
- keeps a cohort cell only when its cohort month plus its month of life is on or
  before the as-of month, so heatmaps stop at the as-of month,
- keeps CAC rows for cohorts that signed up by the as-of month,
- keeps unit economics rows only for cohorts with a full 24 months of history by the
  as-of month. A cohort is mature when the as-of month is at least 23 months after
  its signup month, so it has lived through lifetime months 0 to 23.

### Updating when new data arrives

1. Run the dbt build in dbt_to_exports models directory if there are new landing_zone files, 
so the export files are refreshed.
2. Set `--as-of` (or `AS_OF_MONTH`) to the latest real month.
3. Run the script again. Every page and data file is rewritten.

Pages from an earlier run that are not rebuilt are left alone. The script lists them
so you can delete or rebuild them.

## How the numbers are built

Every number on a page comes from the export tables. The script adds only these
steps.

| Step | Rule |
|---|---|
| Sorting | The long tables are not stored in date order. They are sorted once on load. |
| Slicing by timeframe | The tables are built on the full history first, then cut. Month-based charts keep the calendar months in the window. Cohort-based charts keep the cohorts that signed up in the window and show their whole life, even past the window end. This way every month-over-month change uses the real previous month. |
| Net MRR growth | New Business + Expansion + Contraction + Churn for the month. Contraction and Churn are negative. |
| MRR movement as a share | Each movement divided by the previous month's total MRR. It shows in the hover text. |
| Customer churn table | Customers at the start of a month are last month's active customers. |
| Blended CAC per cohort | Total acquisition spend divided by total new customers. Each channel's CAC is weighted by that channel's signups, which are the active customers at month 0 for the channel. |
| Unit economics | Every row from `unit_economics_by_cohort` is weighted by `mature_customers`, so each customer counts once. The ratio is 24-month LTV divided by average CAC. The blended figure uses all rows together. |
| Unit economics per timeframe | Recomputed from only the mature cohorts that signed up in the window. |
| Payback month | The first month of life, within months 0 to 23, where `ltv_cac_ratio` reaches 1 or more. A cohort that has not reached 1 shows "Not yet". |
| Payback ratio | `ltv_cac_ratio` at the last month of life the cohort has lived through, up to month 23. A star marks cohorts under 24 months old, since their ratio is to date. |
| Ratio tiers | 3x or more is Healthy. From 1x up to 3x is Below floor. Under 1x is Underwater. |
| Change badges | The percent change from the previous month (or cohort). For churn and CAC, a rise shows in pink because it is bad. For the rest, a rise shows in navy. |

## Charts

Segment colors are the same everywhere. Channels: Ads navy, Organic gold, Referral
gray. Plan tiers: Basic gray, Pro gold, Enterprise navy. The page has 14 cards and 17
Plotly figures. Two cards hold buttons that switch between views.

### Revenue tab

| Card | Chart | Built from | Big number and badge |
|---|---|---|---|
| Total MRR | Line | `monthly_metrics_long`, `total_mrr` | Latest month, from the previous month, percent change |
| ARR (Run-Rate) | Line with fill | `arr_by_month`, `arr_value` | Latest month, from the previous month, percent change |
| MRR Movements | Stacked bars for New Business, Expansion, Contraction and Churn, with a Net MRR Growth line | `mrr_movements_long` | Latest net change, percent change against the previous net change |
| ARPU | Line | `monthly_metrics_long`, `arpu` | Latest month, from the previous month, percent change |
| Revenue Churn Rate | Line, pink | `monthly_metrics_long`, `revenue_churn_rate_pct` | Latest rate, from the previous month. A rise is bad |
| Net Revenue Retention | Three views. All (one line), By Channel (three lines), By Plan Tier (three lines). Dashed line at 100% | `nrr_long` | Latest overall NRR. The badge shows the value, navy at 100% or more |
| Revenue Retention Heatmap (blended) | Heatmap of cohort by month of life | `cohort_metrics_long`, `mrr_retention_rate` | None. Values above 100% mean upsell outweighs churn |

### Customers tab

| Card | Chart | Built from | Big number and badge |
|---|---|---|---|
| Active Customers | Three lines: Active, New, Churned | `monthly_metrics_long`, three customer counts | Latest active customers, from the previous month, percent change |
| Customer Churn Rate | Line, pink | `monthly_metrics_long`, `logo_churn_rate_pct` | Latest rate, from the previous month. A rise is bad |
| CAC by Channel | One line per channel | `cac_per_customer_by_channel` | Blended CAC of the latest cohort, per new customer, all channels. A rise is bad |
| Cohort Retention Heatmap (blended) | Heatmap of cohort by month of life, 0 to 100% | `cohort_metrics_long`, `retention_rate` | None |
| Retention Heatmap by Segment | Two views, each with three heatmaps side by side. By Channel and By Plan Tier | `cohort_metrics_long`, `retention_rate` by segment | None |
| Unit Economics | Table, one row per channel and plan tier: 24-month LTV, average CAC, ratio, a Read label, plus a legend and a note | `unit_economics_by_cohort`, for the cohorts in the timeframe | Blended 24-month LTV:CAC. The badge compares it with the 3x floor |
| LTV:CAC Payback | Table, one row per cohort: starting CAC, payback month, 24-month ratio, plus a note | `cohort_metrics_long`, `ltv_cac_ratio`, and blended CAC | Number of cohorts that have paid back, for example 21/24 |

**Table notes.** The Unit Economics note names how many customers and which cohorts
are behind the numbers. The Payback note says whether "Not yet" cohorts are simply the
newest ones. If a timeframe has no mature cohort, the Unit Economics card shows "n/a".

## Outputs

### HTML pages

One page per timeframe in `--output-dir`. Each has a left sidebar with a link to
every card, the two tabs, the Timeframe buttons, and icon links to the author's
profiles. Edit `PROFILE_LINKS`, `PALETTE` and `CSS_TEMPLATE` in the script to change
the links and the look.

### Data files

Written to `--data-dir`. They hold the exact values the pages show.

| Output | Contents |
|---|---|
| `saas_dashboard_data.xlsx` | One workbook with 33 sheets. A `contents` sheet comes first and lists every other sheet and the card it feeds. Then 12 summary sheets. Then 20 data sheets stacked across timeframes, each with a `timeframe` column in front |
| `<timeframe>/<sheet>.csv` | The same 20 data sheets as CSV files, one folder per timeframe |
| `summary/<sheet>.csv` | The 12 summary sheets as CSV files |

The 20 data sheets are `headline_cards`, `total_mrr`, `arr`, `mrr_movements`, `arpu`,
`revenue_churn`, `nrr_all`, `nrr_by_channel`, `nrr_by_plan_tier`,
`revenue_retention_heatmap`, `customer_counts`, `customer_churn`, `cac_by_channel`,
`cac_blended`, `cohort_retention_heatmap`, `retention_by_channel`,
`retention_by_plan_tier`, `unit_economics_table`, `unit_economics_blended` and
`ltv_cac_payback`. The `headline_cards` sheet holds each card's big number, small text
and change badge.

The 12 summary sheets use the full history, so they do not change with the timeframes
built. They hold headline figures for fixed months, such as December of each year.
The months and cohorts are set by the `SUMMARY_*` constants in the script.

## Example result

Run on the full exports with the as-of month 2025-12, the 2024-2025 page shows:

| Card | Value |
|---|---|
| Total MRR | $2,638,614, up 6.7% from $2,474,087 |
| ARR | $31,663,365 |
| ARPU | $161 |
| Net Revenue Retention | 100.5% |
| Active Customers | 16,392, up 6.2% |
| Customer Churn Rate | 1.7%, from 1.6% |
| CAC by Channel | $488 per new customer |
| Unit Economics | 6.70x blended, from 332 customers in the 2024-01 cohort, the only mature cohort in that window |
| LTV:CAC Payback | 21/24 cohorts paid back. The three newest cohorts are "Not yet" |

## Limits and checks

- The cohort file must be the full file. The script stops if its metrics are missing.
- Channel and plan tier names in the colors and in the summary sheets are Ads,
  Organic, Referral and Basic, Pro, Enterprise. 
- Unit economics depend on the by-cohort file. Its rows cover only cohorts that were
  mature when dbt built it. A cohort that matured after that is missing until the
  exports are refreshed.
- The script was checked on pages for All, 2022-2023, 2023-2024, 2024-2025,
  2022-2024, 2023-2025, 2024-2026 and 2025-2026, and with `--as-of none`.
  Chart data and page text were checked. 

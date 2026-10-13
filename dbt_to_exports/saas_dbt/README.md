# Where each dashboard table comes from (dbt_to_exports v5a)

**There are six lineage diagrams for each exported csv or parquet file from dbt_to_exports models.  Final tables are the blue boxes in the lineage diagrams, exported as csv file in the pill boxes.**


[Net revenue retention (`nrr_long`)](#net-revenue-retention-nrr-long)

[Cohort retention (`cohort_metrics_long`, part 1 of 2)](#2-cohort-retention-cohort_metrics_long-part-1-of-2)

[Cohort LTV and LTV:CAC (`cohort_metrics_long`, part 2 of 2)](#3-cohort-ltv-and-ltvcac-cohort_metrics_long-part-2-of-2)

[Unit economics and CAC (three tables)](#4-unit-economics-and-cac-three-tables)

[MRR and ARR movements (`mrr_movements_long`, `arr_movements_long`)](#5-mrr-and-arr-movements-mrr_movements_long-arr_movements_long)

[Monthly metrics and KPI cards (`monthly_metrics_long`, `arr_by_month`, `kpi_summary`)](#6-monthly-metrics-and-kpi-cards-monthly_metrics_long-arr_by_month-kpi_summary)

**Legends in this lineage diagram**. 
- Grey disc: a file.
- Dark grey box: table or view
- Purple: one of the four wide customer-by-month tables, stored once as real tables.
- Green: new in v5a vs. v5 dbt_to_exports model
- Blue: the table explained in the section
- Grey pill at the bottom: the csv file exported
- The words on an arrow are the metrics, kpis or segments for that branch.

**Two terms**
- `stg_` models are staging. They are a clean copy of a source file and with rename and cast columns as transformations.
- `int_` models are intermediate building blocks. Dashboards do not read them.

---

## 1. Net revenue retention (`nrr_long`)

Three versions of the same calculation (all customers, by channel, by plan tier) are appended or concatenated into one table.

```mermaid
graph TD
    panel[("customer_month_panel.csv")]
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    int_nrr_base["NRR, all customers<br/>int_nrr_base"]
    int_nrr_by_channel["NRR by channel<br/>int_nrr_by_channel"]
    int_nrr_by_plan_tier["NRR by plan tier<br/>int_nrr_by_plan_tier"]
    nrr_long["Net revenue retention by month<br/>nrr_long"]
    csv(["csv_exports/reporting/<br/>nrr_long.csv"])

    panel --> stg_revenue
    stg_revenue --> int_nrr_base
    stg_revenue --> int_nrr_by_channel
    stg_revenue --> int_nrr_by_plan_tier
    int_nrr_base -->|"all"| nrr_long
    int_nrr_by_channel -->|"channel"| nrr_long
    int_nrr_by_plan_tier -->|"plan_tier"| nrr_long
    nrr_long --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class panel,csv file
    class nrr_long target
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

---

## 2. Cohort retention (`cohort_metrics_long`, part 1 of 2)

Customer retention and MRR retention, by cohort and months since signup. Part 2 covers the LTV rows of the same table.

```mermaid
graph TD
    panel[("customer_month_panel.csv")]
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    int_retention_base["Customers still active,<br> by cohort and month<br/>int_retention_base"]
    int_retention_percentage["Retention % by cohort<br> and month<br/>int_retention_percentage"]
    int_mrr_retention_percentage["MRR retention % by cohort<br> and month<br/>int_mrr_retention_percentage"]
    cohort_metrics_long["Cohort table (long form)<br/>cohort_metrics_long"]
    csv(["csv_exports/reporting/<br/>cohort_metrics_long.csv"])

    panel --> stg_revenue
    stg_revenue --> int_retention_base
    int_retention_base --> int_retention_percentage
    stg_revenue --> int_mrr_retention_percentage
    int_retention_base -->|"active_customers"| cohort_metrics_long
    int_retention_percentage -->|"retention_rate"| cohort_metrics_long
    int_mrr_retention_percentage -->|"mrr_retention_rate"| cohort_metrics_long
    stg_revenue -->|"mrr_total"| cohort_metrics_long
    cohort_metrics_long --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class panel,csv file
    class cohort_metrics_long target
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

---

## 3. Cohort LTV and LTV:CAC (`cohort_metrics_long`, part 2 of 2)

The same table as diagram 2. LTV stops at month 23, so the last value is the 24-month figure. A cohort with no cost rows has no CAC and drops out of the ratio.

```mermaid
graph TD
    panel[("customer_month_panel.csv")]
    cost[("cost_per_customer.csv")]
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    stg_cost["Clean copy of the <br>cost file<br/>stg_cost"]
    int_avg_mrr["Average MRR per customer,<br> by cohort and month<br/>int_avg_mrr"]
    int_cumulative_ltv["Running total of average MRR,<br> months 0 to 23<br/>int_cumulative_ltv"]
    int_cohort_cac_summary["CAC per customer,<br> by cohort<br/>int_cohort_cac_summary"]
    int_ltv_cac_ratio["LTV divided by CAC<br/>int_ltv_cac_ratio"]
    cohort_metrics_long["Cohort table (long form)<br/>cohort_metrics_long"]
    csv(["csv_exports/reporting/<br/>cohort_metrics_long.csv"])

    panel --> stg_revenue
    cost --> stg_cost
    stg_revenue --> int_avg_mrr
    int_avg_mrr --> int_cumulative_ltv
    stg_cost --> int_cohort_cac_summary
    int_cumulative_ltv --> int_ltv_cac_ratio
    int_cohort_cac_summary --> int_ltv_cac_ratio
    int_avg_mrr -->|"avg_mrr"| cohort_metrics_long
    int_cumulative_ltv -->|"cumulative_ltv"| cohort_metrics_long
    int_ltv_cac_ratio -->|"ltv_cac_ratio"| cohort_metrics_long
    cohort_metrics_long --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class panel,cost,csv file
    class cohort_metrics_long target
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

---

## 4. Unit economics and CAC (three tables)

`unit_economics_grid` has one row per channel and plan tier. `unit_economics_by_cohort` is the same grid with the cohort month kept. `cac_per_customer_by_channel` is CAC per cohort and channel.

```mermaid
graph TD
    panel[("customer_month_panel.csv")]
    cost[("cost_per_customer.csv")]
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    stg_cost["Clean copy of the cost file<br/>stg_cost"]
    int_customer_clv_24m["One row per customer, with 24-month CLV<br/>int_customer_clv_24m"]
    int_unit_economics["Average CLV and CAC,<br> by channel and plan tier<br/>int_unit_economics"]
    unit_economics_grid["unit_economics_grid"]
    unit_economics_by_cohort["unit_economics_by_cohort"]
    cac_per_customer_by_channel["cac_per_customer_by_channel"]
    csv(["csv_exports/reporting<br/>unit_economics_grid.csv<br/<br>unit_economics_by_cohort.csv<br>cac_per_customer_by_channel.csv"])

    panel --> stg_revenue
    cost --> stg_cost
    stg_revenue --> int_customer_clv_24m
    int_customer_clv_24m --> int_unit_economics
    int_unit_economics --> unit_economics_grid
    int_customer_clv_24m --> unit_economics_by_cohort
    stg_cost --> cac_per_customer_by_channel
    unit_economics_grid --> csv
    unit_economics_by_cohort --> csv
    cac_per_customer_by_channel --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    classDef newv5a fill:#7F9388,stroke:#1e8449,stroke-width:2px,color:#000000
    class panel,cost,csv file
    class unit_economics_grid target
    class unit_economics_by_cohort,cac_per_customer_by_channel newv5a
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

---

## 5. MRR and ARR movements (`mrr_movements_long`, `arr_movements_long`)

The four purple tables are the wide customer-by-month tables. Each customer gets a row for every calendar month, with zero MRR for missing months. The movements tables then label each month as New Business, Expansion, Contraction, Churn or No Change.

The "every customer x every month" box is built from two small models, `int_customer_attributes` and `int_calendar_months`. Both read `stg_revenue`.

```mermaid
graph TD
    panel[("customer_month_panel.csv")]
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    int_customer_clv_24m["One row per customer, with 24-month CLV<br/>int_customer_clv_24m"]
    int_customer_calendar_spine["Every customer x every month<br/>int_customer_calendar_spine"]
    reindexed_panel_audit_mrr["Full grid (wide),<br> zero MRR for missing months<br/>reindexed_panel_audit_mrr"]
    reindexed_panel_audit_arr["Same grid but ARR (MRR x 12)<br/>reindexed_panel_audit_arr"]
    customer_level_movements_mrr["Last month's<br> and a movement label<br/>customer_level_movements_mrr"]
    customer_level_movements_arr["Adds last month's  ARR<br/>customer_level_movements_arr"]
    mrr_movements_long["MRR movements by month<br/>mrr_movements_long"]
    arr_movements_long["ARR movements by month<br/>arr_movements_long"]
    csv(["csv_exports/reporting/<br/>mrr_movements_long.csv<br/>arr_movements_long.csv"])

    panel --> stg_revenue
    stg_revenue --> int_customer_clv_24m
    stg_revenue -->|"via two small models"| int_customer_calendar_spine
    int_customer_calendar_spine --> reindexed_panel_audit_mrr
    stg_revenue -->|"actual MRR"| reindexed_panel_audit_mrr
    int_customer_clv_24m -->|"CLV and CAC columns"| reindexed_panel_audit_mrr
    reindexed_panel_audit_mrr --> reindexed_panel_audit_arr
    reindexed_panel_audit_mrr --> customer_level_movements_mrr
    reindexed_panel_audit_arr --> customer_level_movements_arr
    customer_level_movements_mrr --> mrr_movements_long
    customer_level_movements_arr --> arr_movements_long
    mrr_movements_long --> csv
    arr_movements_long --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef stored fill:#6C3483,stroke:#4a235a,stroke-width:2px,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class panel,csv file
    class reindexed_panel_audit_mrr,reindexed_panel_audit_arr,customer_level_movements_mrr,customer_level_movements_arr stored
    class mrr_movements_long,arr_movements_long target
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

---

## 6. Monthly metrics and KPI cards (`monthly_metrics_long`, `arr_by_month`, `kpi_summary`)

One table of monthly metrics feeds the other two. The purple box is the movements table from diagram 5.

```mermaid
graph TD
    stg_revenue["Clean copy of the panel<br/>stg_revenue"]
    customer_level_movements_mrr["Movements table (see diagram 5)<br/>customer_level_movements_mrr"]
    arpu_by_month["Revenue per customer<br/>arpu_by_month"]
    churn_rate_by_month["Share of customers lost<br/>churn_rate_by_month"]
    customer_counts_by_month["Active, new and churned customers<br/>customer_counts_by_month"]
    revenue_churn_rate_by_month["Share of MRR lost<br/>revenue_churn_rate_by_month"]
    monthly_metrics_long["Monthly metrics (long form)<br/>monthly_metrics_long"]
    arr_by_month["ARR by month<br/>arr_by_month"]
    kpi_summary["KPI cards: current vs previous month<br/>kpi_summary"]
    csv(["csv_exports/reporting/<br/>monthly_metrics_long.csv<br/>arr_by_month.csv<br/>kpi_summary.csv"])

    stg_revenue --> arpu_by_month
    stg_revenue --> churn_rate_by_month
    stg_revenue --> revenue_churn_rate_by_month
    customer_level_movements_mrr --> customer_counts_by_month
    customer_level_movements_mrr --> revenue_churn_rate_by_month
    stg_revenue -->|"total_mrr"| monthly_metrics_long
    arpu_by_month -->|"arpu"| monthly_metrics_long
    churn_rate_by_month -->|"logo_churn_rate_pct"| monthly_metrics_long
    customer_counts_by_month -->|"active, new and churned customers"| monthly_metrics_long
    revenue_churn_rate_by_month -->|"revenue_churn_rate_pct"| monthly_metrics_long
    monthly_metrics_long --> arr_by_month
    monthly_metrics_long --> kpi_summary
    monthly_metrics_long --> csv
    arr_by_month --> csv
    kpi_summary --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef stored fill:#6C3483,stroke:#4a235a,stroke-width:2px,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class csv file
    class customer_level_movements_mrr stored
    class monthly_metrics_long,arr_by_month,kpi_summary target
```
[Back to top](#where-each-dashboard-table-comes-from-dbt_to_exports-v5a)

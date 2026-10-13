# Lineage of the dashboard charts

This document shows where each chart on the dashboard comes from. The dashboard is built only from the CSV files exported by the dbt reporting model. Each diagram covers one chart or one small group of charts, so none of them is a big web.

There are **12 diagrams**, plus a table of every card.

**Legend**
- Grey disc: an export file read by the dashboard.
- Dark grey box: a step the dashboard script does.
- Blue box: a chart card on the page.
- The words on an arrow are the metric, segment or column that moves along that branch.

**Contents**

[1. Big picture](#1-big-picture)

[2. Which exports feed which tab](#2-which-exports-feed-which-tab)

[3. Revenue tab: MRR and ARR](#3-revenue-tab-mrr-and-arr)

[4. Revenue tab: MRR movements](#4-revenue-tab-mrr-movements)

[5. Revenue tab: ARPU and revenue churn](#5-revenue-tab-arpu-and-revenue-churn)

[6. Revenue tab: net revenue retention](#6-revenue-tab-net-revenue-retention)

[7. Revenue tab: revenue retention heatmap](#7-revenue-tab-revenue-retention-heatmap)

[8. Customers tab: active customers and churn](#8-customers-tab-active-customers-and-churn)

[9. Customers tab: CAC by channel](#9-customers-tab-cac-by-channel)

[10. Customers tab: retention heatmaps](#10-customers-tab-retention-heatmaps)

[11. Customers tab: unit economics and payback](#11-customers-tab-unit-economics-and-payback)

[12. Outputs: pages and data files](#12-outputs-pages-and-data-files)

[Table of every card](#table-of-every-card)

---

## 1. Big picture

Every page goes through the same steps. The as-of month removes months that have not happened yet. The timeframe step keeps the months and cohorts in one window, such as 2024-2025.

```mermaid
graph TD
    exports[("7 export files<br/>csv_exports")]
    load["Load<br/>check files, columns and metrics"]
    cut["Cut at the as-of month<br/>later months dropped"]
    kpi["Build one table per chart<br/>on the full history"]
    slice["Slice by timeframe<br/>months and cohorts in the window"]
    pages["One HTML page<br/>per timeframe"]
    data["Data files<br/>workbook and CSV files"]

    exports --> load
    load --> cut
    cut --> kpi
    kpi --> slice
    slice --> pages
    slice --> data

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class exports file
    class load,cut,kpi,slice step
    class pages,data target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 2. Which exports feed which tab

Five files feed the Revenue tab. Four feed the Customers tab. The monthly metrics file and the cohort file feed both.

```mermaid
graph LR
    monthly[("monthly_metrics_long.csv")]
    arr[("arr_by_month.csv")]
    movements[("mrr_movements_long.csv")]
    nrr[("nrr_long.csv")]
    cohort[("cohort_metrics_long.csv")]
    cac[("cac_per_customer_by_channel.csv")]
    unit[("unit_economics_by_cohort.csv")]
    revenue["Revenue tab<br/>7 cards"]
    customers["Customers tab<br/>7 cards"]

    
    arr --> revenue
    nrr --> revenue
    movements --> revenue
    monthly --> revenue
    cohort --> revenue
    monthly --> customers
    cohort --> customers
    cac --> customers
    unit --> customers

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class monthly,arr,movements,nrr,cohort,cac,unit file
    class revenue,customers target
```

Three more files sit in the export folder and are not read. `arr_movements_long.csv` is the MRR movements times 12. `kpi_summary.csv` is the monthly metrics plus last month's value. `unit_economics_grid.csv` is the by-cohort unit economics added up over all cohorts.

[Back to top](#lineage-of-the-dashboard-charts)

---

## 3. Revenue tab: MRR and ARR

Two cards. Each one shows a line over calendar months, the latest value, the previous value, and the percent change.

```mermaid
graph TD
    monthly[("monthly_metrics_long.csv")]
    arr[("arr_by_month.csv")]
    pick_mrr["Keep total_mrr<br/>one row per month"]
    pick_arr["Keep arr_value<br/>one row per month"]
    card_mrr["Total MRR<br/>line"]
    card_arr["ARR (Run-Rate)<br/>line with fill"]

    monthly -->|"total_mrr"| pick_mrr
    pick_mrr --> card_mrr
    arr -->|"arr_value"| pick_arr
    pick_arr --> card_arr

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class monthly,arr file
    class pick_mrr,pick_arr step
    class card_mrr,card_arr target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 4. Revenue tab: MRR movements

One card. Two files meet here. The movements give the bars and the net line. The monthly total MRR gives the previous month's MRR, so the hover text can show each movement as a share of it.

```mermaid
graph TD
    movements[("mrr_movements_long.csv")]
    monthly[("monthly_metrics_long.csv")]
    spread["One column per movement<br/>New Business, Expansion,<br/>Contraction, Churn"]
    net["Net MRR growth<br/>the four columns added"]
    prior["Previous month's<br/>total MRR"]
    share["Each movement divided by<br/>previous month's MRR"]
    card["MRR Movements<br/>stacked bars and net line"]

    movements -->|"delta_value"| spread
    spread --> net
    monthly -->|"total_mrr"| prior
    spread --> share
    prior --> share
    spread -->|"bars"| card
    net -->|"line and big number"| card
    share -->|"hover text"| card

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class movements,monthly file
    class spread,net,prior,share step
    class card target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 5. Revenue tab: ARPU and revenue churn

Two cards from the same file. Both are lines over calendar months. For revenue churn, a rise is bad, so the badge turns pink when it goes up.

```mermaid
graph TD
    monthly[("monthly_metrics_long.csv")]
    pick_arpu["Keep arpu<br/>one row per month"]
    pick_churn["Keep revenue_churn_rate_pct<br/>one row per month"]
    card_arpu["ARPU<br/>line"]
    card_churn["Revenue Churn Rate<br/>pink line"]

    monthly -->|"arpu"| pick_arpu
    pick_arpu --> card_arpu
    monthly -->|"revenue_churn_rate_pct"| pick_churn
    pick_churn --> card_churn

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class monthly file
    class pick_arpu,pick_churn step
    class card_arpu,card_churn target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 6. Revenue tab: net revenue retention

One card with three views. The buttons on the card switch between them. All three views read the same file and differ only in the segment.

```mermaid
graph TD
    nrr[("nrr_long.csv")]
    view_all["View 1: All<br/>one line"]
    view_channel["View 2: By Channel<br/>three lines"]
    view_plan["View 3: By Plan Tier<br/>three lines"]
    card["Net Revenue Retention<br/>dashed line at 100 percent"]

    nrr -->|"segment_type = all"| view_all
    nrr -->|"segment_type = channel"| view_channel
    nrr -->|"segment_type = plan_tier"| view_plan
    view_all --> card
    view_channel --> card
    view_plan --> card

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class nrr file
    class view_all,view_channel,view_plan step
    class card target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 7. Revenue tab: revenue retention heatmap

One card. The cohort file holds one row per cohort and month of life. The script turns those rows into a grid, with cohorts down the side and months of life across the top. Values above 100 percent mean upsell is larger than churn.

```mermaid
graph TD
    cohort[("cohort_metrics_long.csv")]
    keep["Keep mrr_retention_rate<br/>segment all"]
    cutcells["Keep a cell only if<br/>cohort month plus month of life<br/>is on or before the as-of month"]
    grid["Grid<br/>cohort by month of life"]
    window["Keep cohorts that signed up<br/>in the timeframe"]
    card["Revenue Retention Heatmap<br/>blended"]

    cohort -->|"mrr_retention_rate"| keep
    keep --> cutcells
    cutcells --> grid
    grid --> window
    window --> card

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class cohort file
    class keep,cutcells,grid,window step
    class card target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 8. Customers tab: active customers and churn

Two cards from the same file. Customer churn is a pink line, and a higher churn is bad.

```mermaid
graph TD
    monthly[("monthly_metrics_long.csv")]
    counts["Keep three customer counts<br/>one row per month"]
    pick_churn["Keep logo_churn_rate_pct<br/>one row per month"]
    card_active["Active Customers<br/>three lines: Active, New, Churned"]
    card_churn["Customer Churn Rate<br/>pink line"]

    monthly -->|"active_customers<br/>new_customers<br/>churned_customers"| counts
    counts --> card_active
    monthly -->|"logo_churn_rate_pct"| pick_churn
    pick_churn --> card_churn

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class monthly file
    class counts,pick_churn step
    class card_active,card_churn target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 9. Customers tab: CAC by channel

One card. The lines come straight from the CAC file. The big number is a blended CAC for the latest cohort. It weights each channel's CAC by that channel's signups. The same blended CAC is the starting CAC in the payback table (diagram 11).

```mermaid
graph TD
    cac[("cac_per_customer_by_channel.csv")]
    cohort[("cohort_metrics_long.csv")]
    lines["One line per channel<br/>CAC by cohort"]
    signups["Signups per cohort and channel<br/>active customers at month 0"]
    blend["Blended CAC per cohort<br/>total spend divided by total signups"]
    card["CAC by Channel<br/>three lines and big number"]
    payback["To the payback table<br/>starting CAC (diagram 11)"]

    cac -->|"cohort_cac"| lines
    cohort -->|"active_customers, segment channel, period 0"| signups
    cac -->|"cohort_cac"| blend
    signups --> blend
    lines --> card
    blend -->|"big number and badge"| card
    blend --> payback

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class cac,cohort file
    class lines,signups,blend,payback step
    class card target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 10. Customers tab: retention heatmaps

Two cards from one metric. The blended card uses the all-customers rows. The segment card has two views, one for channels and one for plan tiers, each with three heatmaps side by side. Every heatmap goes through the same cut at the as-of month and the same timeframe filter, so each branch ends with one grid.

```mermaid
graph TD
    cohort[("cohort_metrics_long.csv")]
    keep["Keep retention_rate<br/>cut at the as-of month<br/>keep cohorts in the timeframe"]
    grid_all["One grid<br/>all customers"]
    grid_segments["One grid per segment<br/>3 channels and 3 plan tiers"]
    card_blended["Cohort Retention Heatmap<br/>blended"]
    card_segment["Retention Heatmap by Segment<br/>By Channel and By Plan Tier"]

    cohort -->|"retention_rate"| keep
    keep -->|"segment all"| grid_all
    keep -->|"segment channel<br/>segment plan_tier"| grid_segments
    grid_all --> card_blended
    grid_segments --> card_segment

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class cohort file
    class keep,grid_all,grid_segments step
    class card_blended,card_segment target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 11. Customers tab: unit economics and payback

Two tables. The unit economics table starts from the by-cohort file. Only mature cohorts are kept. A cohort is mature when it has lived through 24 months by the as-of month. Rows are weighted by their mature customers, so each customer counts once. The payback table finds the month each cohort earns back its CAC.

```mermaid
graph TD
    unit[("unit_economics_by_cohort.csv")]
    cohort[("cohort_metrics_long.csv")]
    mature["Keep cohorts with<br/>24 months by the as-of month"]
    window["Keep cohorts that signed up<br/>in the timeframe"]
    roll["Weight rows by mature_customers<br/>sum by channel and plan tier"]
    ratio["LTV divided by CAC<br/>per row and blended"]
    card_unit["Unit Economics<br/>table and blended ratio"]
    keep_ratio["Keep ltv_cac_ratio<br/>by cohort and month of life"]
    find["Find first month the ratio<br/>reaches 1 within months 0 to 23"]
    blended_cac["Blended CAC per cohort<br/>from diagram 9"]
    card_payback["LTV:CAC Payback<br/>table, one row per cohort"]

    unit -->|"ltv_24m, average_cac,<br/>mature_customers"| mature
    mature --> window
    window --> roll
    roll --> ratio
    ratio --> card_unit
    cohort -->|"ltv_cac_ratio, segment all"| keep_ratio
    keep_ratio --> find
    find -->|"payback month"| card_payback
    keep_ratio -->|"latest ratio"| card_payback
    blended_cac -->|"starting CAC"| card_payback

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class unit,cohort file
    class mature,window,roll,ratio,keep_ratio,find,blended_cac step
    class card_unit,card_payback target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## 12. Outputs: pages and data files

The same tables feed the pages and the data files, so the numbers in the files match what each page shows.

```mermaid
graph TD
    kpi["Chart tables<br/>one per card"]
    slice["Slice by timeframe<br/>All, 2-year and 3-year windows"]
    html["One HTML page per timeframe<br/>index.html and saas_dashboard_slug.html"]
    sheets["20 data sheets<br/>per timeframe"]
    summary["12 summary sheets<br/>full history"]
    workbook["saas_dashboard_data.xlsx<br/>33 sheets"]
    csv(["CSV files<br/>one folder per timeframe<br/>and one summary folder"])

    kpi --> slice
    slice --> html
    slice --> sheets
    kpi --> summary
    sheets --> workbook
    summary --> workbook
    sheets --> csv
    summary --> csv

    classDef file fill:#777777,stroke:#888888,color:#000000
    classDef step fill:#4d4d4d,stroke:#222222,color:#ffffff
    classDef target fill:#1F4E79,stroke:#2471a3,stroke-width:2px,color:#ffffff
    class csv file
    class kpi,slice step
    class html,sheets,summary,workbook target
```
[Back to top](#lineage-of-the-dashboard-charts)

---

## Table of every card

| Tab | Card | Chart | Export files read | Diagram |
|---|---|---|---|---|
| Revenue | Total MRR | Line | `monthly_metrics_long` | 3 |
| Revenue | ARR (Run-Rate) | Line with fill | `arr_by_month` | 3 |
| Revenue | MRR Movements | Stacked bars and net line | `mrr_movements_long`, `monthly_metrics_long` | 4 |
| Revenue | ARPU | Line | `monthly_metrics_long` | 5 |
| Revenue | Revenue Churn Rate | Line | `monthly_metrics_long` | 5 |
| Revenue | Net Revenue Retention | Three line views | `nrr_long` | 6 |
| Revenue | Revenue Retention Heatmap (blended) | Heatmap | `cohort_metrics_long` | 7 |
| Customers | Active Customers | Three lines | `monthly_metrics_long` | 8 |
| Customers | Customer Churn Rate | Line | `monthly_metrics_long` | 8 |
| Customers | CAC by Channel | Three lines | `cac_per_customer_by_channel`, `cohort_metrics_long` | 9 |
| Customers | Cohort Retention Heatmap (blended) | Heatmap | `cohort_metrics_long` | 10 |
| Customers | Retention Heatmap by Segment | Two views of three heatmaps | `cohort_metrics_long` | 10 |
| Customers | Unit Economics | Table | `unit_economics_by_cohort` | 11 |
| Customers | LTV:CAC Payback | Table | `cohort_metrics_long`, `cac_per_customer_by_channel` | 11 |

[Back to top](#lineage-of-the-dashboard-charts)

"""
build_dashboard_from_dbt_exports.py

Reads the dbt export tables (csv_exports/), reshapes them, and writes one standalone
HTML file per timeframe: the same two-tab Plotly dashboard (Revenue, Customer) that
build_dashboard.py writes from the two raw generator CSVs. plotly.js is embedded
inline, so each output file works offline with no CDN dependency.

This file stands alone. It does not import saas_kpi_engine or build_dashboard.
Section 0 below replaces saas_kpi_engine.py. Everything after it is the drawing
code copied from build_dashboard.py. The only edits are in
filter_kpis_to_window(), build_dashboard_html() and main().

Edit points
-----------
- PALETTE: the four brand colors, plus text/background colors.
- CSS_TEMPLATE: every visual rule for the page, cards, tabs, and toggles.
- Each make_*_figure() function: one chart type, reused by every card that
  needs it.
- build_revenue_tab() / build_customer_tab(): which KPI feeds which card,
  in what order. This is the wireframe, in code.

Input files (in --exports-dir, or its reporting/ subfolder)
-----------------------------------------------------------
cohort_metrics_long.csv, monthly_metrics_long.csv, nrr_long.csv,
mrr_movements_long.csv, arr_by_month.csv, cac_per_customer_by_channel.csv,
unit_economics_by_cohort.csv. See section 0 for the columns each one needs.
The cohort file must be the FULL file. A random sample cannot draw the heatmaps.

Timeframe files
---------------
One HTML file is written per timeframe (see TIMEFRAME_OPTIONS). The "All" file
is index.html, so GitHub Pages serves it as the home page. The others are named
saas_dashboard_<timeframe>.html, for example saas_dashboard_2022-2023.html.
The Timeframe buttons in the top right corner link between these files by file
name only (no leading slash, no full address). Keep every file in the same
folder, normally docs/, and the links work on GitHub Pages and from a local copy.

Data files (one workbook, plus CSV files)
-----------------------------------------
For every timeframe built, the data behind every chart and table on that page is
saved. A card's big number, small text and change badge are saved too, as
headline_cards. These are the exact values the page shows, cut to that timeframe.

- dashboard_data/saas_dashboard_data.xlsx  one workbook for all timeframes built.
  The first sheet, contents, lists every sheet and the card it feeds. Every other
  sheet has a timeframe column in front, so one filter picks a timeframe.
- dashboard_data/<timeframe>/<sheet>.csv   the same tables as CSV, one folder per
  timeframe, for loading into dbt, DuckDB or Tableau.

Run
---
    python build_dashboard_from_dbt_exports.py --exports-dir csv_exports

Optional:
    --output-dir docs         folder for all the HTML files (default: docs)
    --data-dir dashboard_data folder for the KPI tables as CSV files (default: dashboard_data)
    --as-of 2025-12           the last month that has happened (default: AS_OF_MONTH below).
                              Later rows in the exports are dropped before any KPI is built.
                              Use --as-of none to keep every month in the files.
    --only all 2022-2023      build just these timeframes (default: all of them).
                              The Timeframe buttons then list only these windows.
                              Running from VS Code without arguments? Set
                              TIMEFRAMES_TO_BUILD near the top of the file instead.
    --plotly external         write plotly.min.js once and link to it, so each
                              HTML file is far smaller (default: inline)
"""

import argparse
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# 0. Data layer -- load the dbt export tables and reshape them into the KPI dict
# ---------------------------------------------------------------------------
# This replaces saas_kpi_engine.py. dbt already did the heavy work, so this section
# only loads the files, cuts them at the as-of month, and reshapes them into the
# same table shapes the drawing code below expects. Nothing in this section draws.
#
# Files read (looked up in --exports-dir, then in --exports-dir/reporting):
#   cohort_metrics_long.csv        segment_type, segment_value, cohort_month, period, metric_name, metric_value
#   monthly_metrics_long.csv       segment_type, segment_value, calendar_month, metric_name, metric_value
#   nrr_long.csv                   segment_type, segment_value, calendar_month, nrr_percentage
#   mrr_movements_long.csv         calendar_month, movement_type, delta_value
#   arr_by_month.csv               calendar_month, total_mrr, arr_value
#   cac_per_customer_by_channel.csv  cohort_month, channel, cohort_cac
#   unit_economics_by_cohort.csv   cohort_month, channel, plan_tier, mature_customers, ltv_24m, average_cac
# Files NOT read: arr_movements_long.csv (MRR movements x 12), kpi_summary.csv (monthly
# metrics plus last month's value), unit_economics_grid.csv (the by-cohort file summed up).

# LTV is measured over the first 24 lifetime months (period 0 to 23).
CLV_HORIZON_MONTHS = 24

EXPORT_FILE_NAMES = {
    "cohort": "cohort_metrics_long.csv",
    "monthly": "monthly_metrics_long.csv",
    "nrr": "nrr_long.csv",
    "mrr_movements": "mrr_movements_long.csv",
    "arr": "arr_by_month.csv",
    "cac": "cac_per_customer_by_channel.csv",
    "unit_by_cohort": "unit_economics_by_cohort.csv",
}

REQUIRED_EXPORT_COLUMNS = {
    "cohort": {"segment_type", "segment_value", "cohort_month", "period", "metric_name", "metric_value"},
    "monthly": {"segment_type", "segment_value", "calendar_month", "metric_name", "metric_value"},
    "nrr": {"segment_type", "segment_value", "calendar_month", "nrr_percentage"},
    "mrr_movements": {"calendar_month", "movement_type", "delta_value"},
    "arr": {"calendar_month", "total_mrr", "arr_value"},
    "cac": {"cohort_month", "channel", "cohort_cac"},
    "unit_by_cohort": {"cohort_month", "channel", "plan_tier", "mature_customers", "ltv_24m", "average_cac"},
}

# Metrics the cohort table must hold, so a thin or sampled file fails with a clear message.
REQUIRED_COHORT_METRICS = {
    "active_customers", "retention_rate", "mrr_retention_rate", "cumulative_ltv", "ltv_cac_ratio",
}


def _month_number(month_string):
    """'2023-05' -> a running month count, so two months can be subtracted."""
    year, month = str(month_string).split("-")[:2]
    return int(year) * 12 + int(month)


def _month_numbers(series):
    """_month_number for a whole column, computed once per distinct month."""
    lookup = {m: _month_number(m) for m in series.unique()}
    return series.map(lookup)


def _find_export_file(export_dir, file_name):
    for folder in (export_dir, os.path.join(export_dir, "reporting")):
        path = os.path.join(folder, file_name)
        if os.path.exists(path):
            return path
    return None


def load_exports(export_dir):
    """Read the dbt export files. Fails loudly if a file, a column or a metric is missing."""
    exports = {}
    for key, file_name in EXPORT_FILE_NAMES.items():
        path = _find_export_file(export_dir, file_name)
        if path is None:
            hint = ""
            if key == "cohort" and _find_export_file(export_dir, "cohort_metrics_long_random_sample.csv"):
                hint = (" Only cohort_metrics_long_random_sample.csv was found. A random sample cannot draw the "
                        "heatmaps or the payback table. Put the full cohort_metrics_long.csv in the folder.")
            raise FileNotFoundError(f"Missing export file {file_name} in {export_dir} (or its reporting subfolder).{hint}")
        frame = pd.read_csv(path)
        missing = REQUIRED_EXPORT_COLUMNS[key] - set(frame.columns)
        if missing:
            raise ValueError(f"{file_name} is missing columns: {sorted(missing)}")
        exports[key] = frame

    missing_metrics = REQUIRED_COHORT_METRICS - set(exports["cohort"]["metric_name"].unique())
    if missing_metrics:
        raise ValueError(f"cohort_metrics_long.csv has no rows for metrics {sorted(missing_metrics)}. Is it a sample?")

    # The long tables are not stored in date order. Sort once.
    exports["monthly"] = exports["monthly"].sort_values(["metric_name", "calendar_month"]).reset_index(drop=True)
    exports["nrr"] = exports["nrr"].sort_values(["segment_type", "segment_value", "calendar_month"]).reset_index(drop=True)
    exports["mrr_movements"] = exports["mrr_movements"].sort_values(["calendar_month", "movement_type"]).reset_index(drop=True)
    exports["arr"] = exports["arr"].sort_values("calendar_month").reset_index(drop=True)
    exports["last_month"] = exports["monthly"]["calendar_month"].max()
    return exports


def cut_to_as_of_month(exports, as_of_month):
    """
    Drop every month after as_of_month. Months later than that have not happened yet.

    - Month tables keep calendar_month <= as_of_month.
    - The cohort table keeps a cell when cohort_month + period <= as_of_month.
    - The CAC table keeps cohorts that signed up by as_of_month.
    - The unit economics table keeps cohorts that have a full 24 months by as_of_month.
      Their 24-month LTV does not change with the cut, since it is a fixed 24 months.
    """
    limit = _month_number(as_of_month)
    out = dict(exports)
    for key in ("monthly", "nrr", "mrr_movements", "arr"):
        frame = exports[key]
        out[key] = frame[_month_numbers(frame["calendar_month"]) <= limit].reset_index(drop=True)

    cohort = exports["cohort"]
    out["cohort"] = cohort[(_month_numbers(cohort["cohort_month"]) + cohort["period"]) <= limit].reset_index(drop=True)

    cac = exports["cac"]
    out["cac"] = cac[_month_numbers(cac["cohort_month"]) <= limit].reset_index(drop=True)

    unit = exports["unit_by_cohort"]
    out["unit_by_cohort"] = unit[(limit - _month_numbers(unit["cohort_month"])) >= CLV_HORIZON_MONTHS - 1].reset_index(drop=True)

    out["last_month"] = out["monthly"]["calendar_month"].max()
    return out


def _cohort_grid(cohort_df, metric_name, segment_type="all", segment_value="all"):
    """Pivot one metric of one segment into a cohort_month x lifetime_month grid."""
    rows = cohort_df[
        (cohort_df["segment_type"] == segment_type)
        & (cohort_df["segment_value"] == segment_value)
        & (cohort_df["metric_name"] == metric_name)
    ]
    grid = rows.pivot(index="cohort_month", columns="period", values="metric_value").sort_index()
    grid.columns.name = "lifetime_month"
    return grid


def _segment_values(cohort_df, segment_type):
    return sorted(cohort_df.loc[cohort_df["segment_type"] == segment_type, "segment_value"].unique())


def compute_mrr_movements(mrr_movements_df):
    """Monthly grid: New Business / Expansion / Contraction / Churn dollars, plus Net MRR Growth."""
    categories = ["New Business", "Expansion", "Contraction", "Churn"]
    monthly = (
        mrr_movements_df.groupby(["calendar_month", "movement_type"])["delta_value"]
        .sum().unstack(fill_value=0)
    )
    for category in categories:
        if category not in monthly.columns:
            monthly[category] = 0.0
    monthly = monthly[categories].reset_index().sort_values("calendar_month").reset_index(drop=True)
    monthly.columns.name = None
    monthly["Net MRR Growth"] = monthly[categories].sum(axis=1)
    return monthly


def compute_revenue_churn_rate(wide_df, mrr_movements):
    """
    |Churned MRR this month| / total MRR the prior month, as a percentage.
    The percentage is dbt's own revenue_churn_rate_pct. The two dollar columns are
    rebuilt so the table has the columns the data export expects.
    """
    total_mrr = wide_df["total_mrr"]
    churned = (-mrr_movements.set_index("calendar_month")["Churn"]).reindex(total_mrr.index, fill_value=0)
    return pd.DataFrame({
        "calendar_month": total_mrr.index,
        "starting_mrr": total_mrr.shift(1).values,
        "churned_mrr": churned.values,
        "revenue_churn_rate_pct": wide_df["revenue_churn_rate_pct"].values,
    })


def compute_logo_churn_rate(wide_df):
    """Monthly logo churn. customers_at_start is last month's active count."""
    table = pd.DataFrame({
        "calendar_month": wide_df.index,
        "customers_at_start": wide_df["active_customers"].shift(1).values,
        "customers_churned": wide_df["churned_customers"].values,
        "churn_rate_percentage": wide_df["logo_churn_rate_pct"].values,
    }).iloc[1:].reset_index(drop=True)
    table[["customers_at_start", "customers_churned"]] = table[["customers_at_start", "customers_churned"]].astype(int)
    return table


def compute_nrr_by_segment(nrr_df, segment_type):
    """Long-form NRR: one row per (calendar_month, segment value)."""
    rows = nrr_df[nrr_df["segment_type"] == segment_type]
    return (
        rows.rename(columns={"segment_value": segment_type})[["calendar_month", segment_type, "nrr_percentage"]]
        .sort_values([segment_type, "calendar_month"]).reset_index(drop=True)
    )


def compute_blended_cac_by_cohort(cac_df, cohort_df):
    """
    Series indexed by cohort_month: total acquisition spend / total new customers across
    every channel and plan tier. The CAC table holds one customer-weighted CAC per cohort x
    channel, so each is weighted here by that channel's signups (active customers at month 0).
    """
    signups = cohort_df[
        (cohort_df["segment_type"] == "channel")
        & (cohort_df["metric_name"] == "active_customers")
        & (cohort_df["period"] == 0)
    ].rename(columns={"segment_value": "channel", "metric_value": "new_customers"})[["cohort_month", "channel", "new_customers"]]
    merged = cac_df.merge(signups, on=["cohort_month", "channel"], how="inner")
    merged["spend"] = merged["cohort_cac"] * merged["new_customers"]
    totals = merged.groupby("cohort_month")[["spend", "new_customers"]].sum()
    return (totals["spend"] / totals["new_customers"]).rename("blended_cac_dollars").sort_index()


def compute_unit_economics(unit_by_cohort_df):
    """
    24-month LTV, CAC and LTV:CAC ratio by channel x plan tier, from the by-cohort rows given.

    Only mature cohorts are in the table, so every customer has had the same 24 months.
    Each row is weighted by its mature customers, so every customer counts once and a
    segment's averages are customer-weighted. ltv_to_cac_ratio is ltv_24m / average_cac.
    """
    columns = ["channel", "plan_tier", "mature_customers", "ltv_24m", "average_cac", "ltv_to_cac_ratio"]
    if unit_by_cohort_df.empty:
        return pd.DataFrame(columns=columns)
    weighted = unit_by_cohort_df.assign(
        total_ltv=unit_by_cohort_df["ltv_24m"] * unit_by_cohort_df["mature_customers"],
        total_cac=unit_by_cohort_df["average_cac"] * unit_by_cohort_df["mature_customers"],
    )
    totals = weighted.groupby(["channel", "plan_tier"])[["mature_customers", "total_ltv", "total_cac"]].sum()
    table = pd.DataFrame({
        "mature_customers": totals["mature_customers"].astype(int),
        "ltv_24m": totals["total_ltv"] / totals["mature_customers"],
        "average_cac": totals["total_cac"] / totals["mature_customers"],
    }).reset_index()
    table["ltv_to_cac_ratio"] = table["ltv_24m"] / table["average_cac"]
    return table.sort_values(["channel", "plan_tier"]).reset_index(drop=True)[columns]


def compute_blended_unit_economics(unit_by_cohort_df):
    """
    One 24-month LTV:CAC for all mature customers together. Every customer counts once,
    so big segments weigh more than small ones. Returns a dict. cohort_count, first_cohort
    and last_cohort say which cohorts it covers.
    """
    if unit_by_cohort_df.empty:
        return {"mature_customers": 0, "ltv_24m": np.nan, "average_cac": np.nan, "ltv_to_cac_ratio": np.nan,
                "cohort_count": 0, "first_cohort": None, "last_cohort": None}
    customers = unit_by_cohort_df["mature_customers"].sum()
    ltv = (unit_by_cohort_df["ltv_24m"] * unit_by_cohort_df["mature_customers"]).sum() / customers
    cac = (unit_by_cohort_df["average_cac"] * unit_by_cohort_df["mature_customers"]).sum() / customers
    cohorts = sorted(unit_by_cohort_df["cohort_month"].unique())
    return {
        "mature_customers": int(customers),
        "ltv_24m": ltv,
        "average_cac": cac,
        "ltv_to_cac_ratio": ltv / cac,
        "cohort_count": len(cohorts),
        "first_cohort": cohorts[0],
        "last_cohort": cohorts[-1],
    }


def compute_ltv_cac_payback(cohort_df, blended_cac, last_month):
    """
    For each cohort, the earliest lifetime_month where cumulative average revenue per
    customer crosses the cohort's CAC (ratio >= 1), looking only inside the first 24
    lifetime months. The ratio grid is dbt's own ltv_cac_ratio.

    latest_ratio is the ratio at the last month inside that 24-month window that the
    cohort has actually lived through. For mature cohorts that is the full 24-month
    LTV:CAC. For younger cohorts it is a to-date figure, flagged by is_mature_24m = False.
    """
    ratio_grid = _cohort_grid(cohort_df, "ltv_cac_ratio")
    cohort_cac = blended_cac.reindex(ratio_grid.index)
    last_number = _month_number(last_month)

    rows = []
    for cohort in ratio_grid.index:
        row = ratio_grid.loc[cohort].dropna()
        crossed = row[row >= 1]
        rows.append({
            "cohort_month": cohort,
            "starting_cac": cohort_cac.get(cohort, np.nan),
            "payback_lifetime_month": int(crossed.index.min()) if len(crossed) else pd.NA,
            "latest_observed_month": int(row.index.max()) if len(row) else pd.NA,
            "latest_ratio": row.iloc[-1] if len(row) else np.nan,
            "is_mature_24m": bool(last_number - _month_number(cohort) >= CLV_HORIZON_MONTHS - 1),
        })
    table = pd.DataFrame(rows).sort_values("cohort_month").reset_index(drop=True)
    table["payback_lifetime_month"] = table["payback_lifetime_month"].astype("Int64")
    table["latest_observed_month"] = table["latest_observed_month"].astype("Int64")
    return table


def build_all_kpis(exports):
    """
    Reshape the (already cut) exports into a flat dict of DataFrames / Series, keyed by
    name. The drawing code below reads from this dict only. Same keys the old
    saas_kpi_engine.build_all_kpis() returned, plus unit_economics_by_cohort, which
    filter_kpis_to_window() uses to recompute unit economics for each timeframe.
    """
    cohort_df = exports["cohort"]
    wide = exports["monthly"].pivot(index="calendar_month", columns="metric_name", values="metric_value").sort_index()
    wide.index.name = "calendar_month"

    total_mrr = wide["total_mrr"].rename("mrr")
    arr = exports["arr"].set_index("calendar_month")["arr_value"].sort_index().rename("arr_run_rate")
    mrr_movements = compute_mrr_movements(exports["mrr_movements"])

    arpu = pd.DataFrame({
        "calendar_month": wide.index,
        "total_mrr": wide["total_mrr"].values,
        "active_customers": wide["active_customers"].astype(int).values,
        "arpu": wide["arpu"].values,
    })
    customer_counts = pd.DataFrame({
        "calendar_month": wide.index,
        "active_customers": wide["active_customers"].astype(int).values,
        "new_customers": wide["new_customers"].astype(int).values,
        "churned_customers": wide["churned_customers"].astype(int).values,
    })
    nrr_overall = (
        exports["nrr"][exports["nrr"]["segment_type"] == "all"]
        .set_index("calendar_month")["nrr_percentage"].sort_index().rename("nrr_percentage")
    )

    cac_by_channel = (
        exports["cac"].rename(columns={"cohort_cac": "cac_per_customer_dollars"})
        .sort_values(["channel", "cohort_month"]).reset_index(drop=True)
    )
    blended_cac = compute_blended_cac_by_cohort(exports["cac"], cohort_df)
    unit_by_cohort = exports["unit_by_cohort"]

    return {
        # Revenue tab
        "total_mrr_by_month": total_mrr,
        "arr_by_month": arr,
        "mrr_movements": mrr_movements,
        "arpu_by_month": arpu,
        "revenue_churn_rate": compute_revenue_churn_rate(wide, mrr_movements),
        "nrr_overall": nrr_overall,
        "nrr_by_channel": compute_nrr_by_segment(exports["nrr"], "channel"),
        "nrr_by_plan_tier": compute_nrr_by_segment(exports["nrr"], "plan_tier"),
        "mrr_retention_grid": _cohort_grid(cohort_df, "mrr_retention_rate"),

        # Customer tab
        "customer_counts_by_month": customer_counts,
        "logo_churn_rate": compute_logo_churn_rate(wide),
        "cac_by_channel": cac_by_channel,
        "blended_cac_by_cohort": blended_cac,
        "cohort_retention_grid": _cohort_grid(cohort_df, "retention_rate"),
        "retention_grid_by_channel": {
            name: _cohort_grid(cohort_df, "retention_rate", "channel", name)
            for name in _segment_values(cohort_df, "channel")
        },
        "retention_grid_by_plan_tier": {
            name: _cohort_grid(cohort_df, "retention_rate", "plan_tier", name)
            for name in _segment_values(cohort_df, "plan_tier")
        },
        "unit_economics": compute_unit_economics(unit_by_cohort),
        "blended_unit_economics": compute_blended_unit_economics(unit_by_cohort),
        "ltv_cac_payback": compute_ltv_cac_payback(cohort_df, blended_cac, exports["last_month"]),
        "unit_economics_by_cohort": unit_by_cohort,
    }


def _slugify(title):
    """'ARR (Run-Rate)' -> 'card-arr-run-rate'. Used so the sidebar can link
    straight to a card's id without hand-maintaining a separate list."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"card-{slug}"


# ---------------------------------------------------------------------------
# 1. Palette and CSS -- edit these to restyle the whole dashboard
# ---------------------------------------------------------------------------

PALETTE = {
    "navy": "#1b365d",
    "gold": "#d4af37",
    "gray": "#8a8d8f",
    "pink": "#ff6b8b",
    "bg": "#f5f6f8",
    "card_bg": "#ffffff",
    "text_dark": "#242833",
    "text_muted": "#767b87",
    "border": "#e7e8ec",
}

# Movement-type colors, reused by the MRR Movements chart and anywhere else
# that breaks revenue down the same way.
MOVEMENT_COLORS = {
    "New Business": PALETTE["navy"],
    "Expansion": PALETTE["gold"],
    "Contraction": PALETTE["gray"],
    "Churn": PALETTE["pink"],
}

# Segment colors, reused by every channel / plan-tier multi-line and table.
CHANNEL_COLORS = {"Ads": PALETTE["navy"], "Organic": PALETTE["gold"], "Referral": PALETTE["gray"]}
PLAN_TIER_COLORS = {"Basic": PALETTE["gray"], "Pro": PALETTE["gold"], "Enterprise": PALETTE["navy"]}

# Heatmap gradient built from the same four colors instead of a default
# red-yellow-green scale: pink (low) -> gray (mid) -> navy (high).
HEATMAP_SCALE = [[0.0, PALETTE["pink"]], [0.5, PALETTE["gray"]], [1.0, PALETTE["navy"]]]

FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif"

# Profile links shown as small icons at the bottom of the left panel.
# Each entry is (name, url, icon viewBox, icon path). Edit the urls here.
# Both icons are single-color shapes that take their color from the CSS.
PROFILE_LINKS = [
    ("LinkedIn", "https://www.linkedin.com/in/sandygcabanes", "0 0 24 24",
     # rounded square with the letters "in" cut out of it
     "M5 2h14a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3z"
     "M7.5 6a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"
     "M6.2 10h2.6v7.5H6.2z"
     "M11 10h2.5v1.1c.5-.8 1.4-1.3 2.6-1.3 2.2 0 3 1.4 3 3.5v4.2h-2.6v-3.7c0-1-.3-1.7-1.3-1.7"
     "s-1.6.7-1.6 1.7v3.7H11z"),
    ("GitHub", "https://github.com/SandyGCabanes", "0 0 16 16",
     "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"
     "-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82"
     ".72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15"
     "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82"
     ".44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2"
     " 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"),
]
CHART_CONFIG = {"displayModeBar": False, "responsive": True}

CSS_TEMPLATE = """
:root {{
  --navy: {navy}; --gold: {gold}; --gray: {gray}; --pink: {pink};
  --bg: {bg}; --card-bg: {card_bg}; --text-dark: {text_dark};
  --text-muted: {text_muted}; --border: {border};
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text-dark);
  font-family: {font_family};
}}
h1 {{ font-size: 22px; margin: 0 0 4px; color: var(--navy); }}
.subtitle {{ color: var(--text-muted); font-size: 13px; margin: 0 0 20px; }}

.app-shell {{ display: flex; align-items: flex-start; min-height: 100vh; }}
/* Left panel spacing. To fit more on screen, lower the padding values below.
   .nav-list scrolls on its own if the window is still too short, so the
   profile icons at the bottom never get pushed off screen. */
.sidebar {{
  width: 220px; flex-shrink: 0; background: var(--navy); color: #fff;
  padding: 16px 0; position: sticky; top: 0; height: 100vh; overflow-y: auto;
  display: flex; flex-direction: column;
}}
.sidebar-title {{
  font-weight: 700; font-size: 16px; line-height: 1.3;
  padding: 0 20px 16px; letter-spacing: 0.2px;
}}
.nav-list {{ display: flex; flex-direction: column; flex: 0 1 auto; min-height: 0; overflow-y: auto; }}
.nav-group {{ margin-bottom: 2px; }}
.nav-item {{
  background: transparent; border: none; border-left: 3px solid transparent;
  color: rgba(255, 255, 255, 0.75); text-align: left; width: 100%;
  padding: 8px 20px; font-size: 14px; font-weight: 600; cursor: pointer;
  font-family: {font_family};
}}
.nav-item:hover {{ background: rgba(255, 255, 255, 0.06); color: #fff; }}
.nav-item.active {{
  background: rgba(255, 255, 255, 0.1); color: #fff;
  border-left-color: var(--gold);
}}
.nav-sublist {{ display: flex; flex-direction: column; padding: 0 0 4px; }}
.nav-sublink {{
  display: block; color: rgba(255, 255, 255, 0.55); text-decoration: none;
  font-size: 12px; font-weight: 500; padding: 3px 20px 3px 34px; line-height: 1.25;
}}
.nav-sublink:hover {{ color: #fff; background: rgba(255, 255, 255, 0.06); }}
.main-content {{ flex: 1; min-width: 0; padding: 24px 32px 64px; }}

.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}

.grid {{
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;
}}
.card {{
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
  padding: 18px 20px; box-shadow: 0 1px 2px rgba(20, 20, 30, 0.04);
  min-width: 0; scroll-margin-top: 20px;
}}
.table-legend {{
  margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
  font-size: 11px; color: var(--text-muted);
}}
.card--full {{ grid-column: 1 / -1; }}

.card-header {{ display: flex; justify-content: space-between; align-items: center; }}
.card-title {{ font-weight: 700; font-size: 13px; color: var(--navy); letter-spacing: 0.2px; }}
.delta {{ font-size: 13px; font-weight: 700; padding: 2px 8px; border-radius: 12px; }}
.delta.positive {{ color: var(--navy); background: rgba(27, 54, 93, 0.08); }}
.delta.negative {{ color: var(--pink); background: rgba(255, 107, 139, 0.12); }}

.card-value {{ font-size: 26px; font-weight: 700; color: var(--text-dark); margin: 6px 0 4px; }}
.card-value-sub {{ font-size: 13px; font-weight: 400; color: var(--text-muted); margin-left: 8px; }}

.card-body {{ margin-top: 6px; }}

.seg-control {{ display: flex; gap: 6px; margin: 10px 0 4px; }}
.seg-btn {{
  border: 1px solid var(--border); background: var(--bg); color: var(--text-muted);
  padding: 5px 12px; border-radius: 14px; font-size: 12px; font-weight: 600; cursor: pointer;
}}
.seg-btn.active {{ background: var(--navy); border-color: var(--navy); color: #fff; }}
.seg-panel {{ display: none; }}
.seg-panel.active {{ display: block; }}
.dashboard-container {{
    max-width: 1400px;
    margin: 0;
    padding: 0;
}}

.page-header {{
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 24px; flex-wrap: wrap; margin-bottom: 4px;
}}
.page-header .subtitle {{ margin-bottom: 16px; }}

.timeframe-control {{
  display: flex; flex-direction: column; gap: 6px; align-items: flex-end;
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 12px;
}}
.timeframe-title {{ font-size: 12px; font-weight: 700; color: var(--navy); }}
.timeframe-row {{ display: flex; align-items: center; gap: 6px; }}
.timeframe-group {{ font-size: 11px; color: var(--text-muted); width: 62px; text-align: right; }}
.timeframe-btn {{
  border: 1px solid var(--border); background: var(--bg); color: var(--text-muted);
  padding: 4px 10px; border-radius: 14px; font-size: 12px; font-weight: 600;
  text-decoration: none; white-space: nowrap;
}}
.timeframe-btn:hover {{ border-color: var(--navy); color: var(--navy); }}
.timeframe-btn:focus-visible {{ outline: 2px solid var(--gold); outline-offset: 2px; }}
.timeframe-btn.active {{ background: var(--navy); border-color: var(--navy); color: #fff; }}

.sidebar-links {{
  margin-top: auto; padding: 12px 20px 0; display: flex; gap: 14px; flex-shrink: 0;
}}
.sidebar-link {{
  display: inline-flex; padding: 4px; border-radius: 6px;
  color: rgba(255, 255, 255, 0.7); text-decoration: none;
}}
.sidebar-link:hover {{ color: var(--gold); }}
.sidebar-link:focus-visible {{ outline: 2px solid var(--gold); outline-offset: 2px; }}

.sidebar-timeframe {{
  margin: 0 20px 14px; padding: 10px 12px; border-radius: 8px;
  background: rgba(255, 255, 255, 0.08); border-left: 3px solid var(--gold);
}}
.sidebar-timeframe-label {{ font-size: 11px; color: rgba(255, 255, 255, 0.6); }}
.sidebar-timeframe-value {{ font-size: 18px; font-weight: 700; color: var(--gold); margin: 2px 0; }}
.sidebar-timeframe-note {{ font-size: 11px; color: rgba(255, 255, 255, 0.6); line-height: 1.3; }}
"""


# ---------------------------------------------------------------------------
# 1b. Timeframes -- one HTML file per window, linked by the top-right buttons
# ---------------------------------------------------------------------------

# (slug, button label, first year, last year, row label in the control)
# slug      -> goes into the file name, e.g. saas_dashboard_2022-2023.html.
#              "all" is special: its file is index.html.
# years     -> both ends are included. None, None means no filter.
# row label -> which row of the control the button sits in.
# Edit this list to add, drop, or rename windows. Nothing else needs to change.
TIMEFRAME_OPTIONS = [
    ("all",       "All",     None, None, "Full period"),
    ("2022-2023", "2022\u201323", 2022, 2023, "2 years"),
    ("2023-2024", "2023\u201324", 2023, 2024, "2 years"),
    ("2024-2025", "2024\u201325", 2024, 2025, "2 years"),
    ("2025-2026", "2025\u201326", 2025, 2026, "2 years"),
    ("2026-2027", "2026\u201327", 2026, 2027, "2 years"),
    ("2022-2024", "2022\u201324", 2022, 2024, "3 years"),
    ("2023-2025", "2023\u201325", 2023, 2025, "3 years"),
    ("2024-2026", "2024\u201326", 2024, 2026, "3 years"),
    ("2025-2027", "2025\u201327", 2025, 2027, "3 years"),
    ("2026-2028", "2026\u201328", 2026, 2028, "3 years"),
]


# Default index.html file is for all years.  
# Change the filenames later if a different timeframe will be the home page.
HOME_FILENAME = "index.html"          # the "All" timeframe. GitHub Pages serves this as the home page.
WINDOW_FILE_PREFIX = "saas_dashboard"  # the other timeframes: saas_dashboard_<slug>.html


# The Timeframe buttons on each page list only 
# the windows built, so there are no dead links.

# The --only option on the command line overrides this setting.
# Example Command: --only 2024-2025 2023-2025.
# python build_dashboard.py --panel saas_dataset_v9_2_....csv --cost cost_per_customer_v9_2_....csv --only 2024-2025 2023-2025

# VSCode
# Example: TIMEFRAMES_TO_BUILD = None  # means all of them
# Example: TIMEFRAMES_TO_BUILD = ["2022-2023","2023-2024", "2024-2025"]
# Edit by picking from the TIMEFRAME_OPTIONS list above. 
TIMEFRAMES_TO_BUILD = ["2022-2023","2023-2024", "2024-2025"]

# The scenario ends here. The generator simulates months after this, but they have not
# happened yet, so they are dropped before any KPI is computed. Heatmaps then stop at
# this month. The command line option --as-of overrides this. Use None to keep every month.
AS_OF_MONTH = "2025-12"


def timeframe_filename(slug):
    """'all' -> 'index.html'. '2022-2023' -> 'saas_dashboard_2022-2023.html'.
    A bare file name, so it works as a relative link from any page in the same folder."""
    if slug == "all":
        return HOME_FILENAME
    return f"{WINDOW_FILE_PREFIX}_{slug}.html"


def timeframe_display(option):
    """Text shown in the sidebar: '2023\u20132025', or 'All years'."""
    _slug, _label, start_year, end_year, _row = option
    if start_year is None:
        return "All years"
    return f"{start_year}\u2013{end_year}"


def _in_window(values, start_year, end_year):
    """True/False per item. values are 'YYYY-MM' strings; only the year is compared."""
    years = pd.Series(values).astype(str).str[:4].astype(int).to_numpy()
    return (years >= start_year) & (years <= end_year)


def filter_kpis_to_window(kpis, start_year, end_year):
    """
    Cut the KPI dict down to one timeframe.

    The KPIs are always computed on the full history first, then sliced here.
    That keeps month-over-month numbers honest. If we cut the raw data first,
    every customer would look brand new in the first month of the window.

    - Month-based tables (MRR, churn, NRR, customer counts) keep the months in the window.
    - Cohort-based tables (heatmaps, CAC, payback) keep the cohorts that signed up in the window.
      They still show each cohort's full life after signup, even past the window end.
    - Unit economics is recomputed from the by-cohort rows of mature cohorts that signed up in the window.
      Each customer's 24-month LTV can reach past the window end. The cohort is what is
      filtered, not the revenue months.
    """
    if start_year is None:
        return kpis

    def by_index(obj):
        return obj[_in_window(obj.index, start_year, end_year)]

    def by_column(df, column):
        return df[_in_window(df[column], start_year, end_year)].reset_index(drop=True)

    def grid(g):
        # Drop lifetime months that none of the kept cohorts have reached.
        return g[_in_window(g.index, start_year, end_year)].dropna(axis=1, how="all")

    out = dict(kpis)
    for key in ("total_mrr_by_month", "arr_by_month", "nrr_overall"):
        out[key] = by_index(kpis[key])
    for key in ("mrr_movements", "arpu_by_month", "revenue_churn_rate", "customer_counts_by_month",
                "logo_churn_rate", "nrr_by_channel", "nrr_by_plan_tier"):
        out[key] = by_column(kpis[key], "calendar_month")
    for key in ("cac_by_channel", "ltv_cac_payback"):
        out[key] = by_column(kpis[key], "cohort_month")
    out["blended_cac_by_cohort"] = by_index(kpis["blended_cac_by_cohort"])
    for key in ("mrr_retention_grid", "cohort_retention_grid"):
        out[key] = grid(kpis[key])
    for key in ("retention_grid_by_channel", "retention_grid_by_plan_tier"):
        out[key] = {name: grid(g) for name, g in kpis[key].items()}

    unit_by_cohort = kpis["unit_economics_by_cohort"]
    unit_in_window = unit_by_cohort[_in_window(unit_by_cohort["cohort_month"], start_year, end_year)]
    out["unit_economics"] = compute_unit_economics(unit_in_window)
    out["blended_unit_economics"] = compute_blended_unit_economics(unit_in_window)
    return out


def build_timeframe_control_html(current_slug, built_slugs=None):
    """
    The button panel for the top right corner. Each button is a plain relative link
    (file name only) to the sibling HTML file for that timeframe, so it works from
    a GitHub Pages folder as well as from a local copy. There is no script to manage.
    keepTab() adds the open tab (Revenue or Customers) to the link, so the next
    file opens on the same tab.

    built_slugs is the list of timeframes being built in this run. Only those get
    a button, so no button points to a file that does not exist. None means all.
    """
    rows = {}
    for slug, label, _start, _end, row_label in TIMEFRAME_OPTIONS:
        if built_slugs is not None and slug not in built_slugs:
            continue
        href = timeframe_filename(slug)
        active = " active" if slug == current_slug else ""
        current = ' aria-current="page"' if slug == current_slug else ""
        rows.setdefault(row_label, []).append(
            f'<a class="timeframe-btn{active}" href="{href}"{current} onclick="keepTab(this)">{label}</a>'
        )
    row_html = "".join(
        f'<div class="timeframe-row"><span class="timeframe-group">{row_label}</span>{"".join(buttons)}</div>'
        for row_label, buttons in rows.items()
    )
    return f'<div class="timeframe-control"><span class="timeframe-title">Timeframe</span>{row_html}</div>'


def build_sidebar_links_html():
    """Icon links (LinkedIn, GitHub) pinned to the bottom of the left panel. Open in a new tab."""
    links = "".join(
        f'<a class="sidebar-link" href="{url}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="{name}" title="{name}">'
        f'<svg viewBox="{viewbox}" width="22" height="22" fill="currentColor" aria-hidden="true" focusable="false">'
        f'<path fill-rule="evenodd" d="{path}"/></svg></a>'
        for name, url, viewbox, path in PROFILE_LINKS
    )
    return f'<div class="sidebar-links">{links}</div>'


def build_sidebar_timeframe_html(option):
    """Small block under the sidebar title that says which timeframe this file shows."""
    slug = option[0]
    note = ("Every month and every signup cohort." if slug == "all"
            else "Months and signup cohorts in this range.")
    return (
        '<div class="sidebar-timeframe">'
        '<div class="sidebar-timeframe-label">Timeframe</div>'
        f'<div class="sidebar-timeframe-value">{timeframe_display(option)}</div>'
        f'<div class="sidebar-timeframe-note">{note}</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# 2. Small formatting / delta helpers
# ---------------------------------------------------------------------------

def format_dollars(value):
    return "-${:,.0f}".format(abs(value)) if value < 0 else "${:,.0f}".format(value)


def format_percent(value, decimals=1):
    return f"{value:.{decimals}f}%"


def compute_delta(series):
    """series: index sorted ascending. Returns (latest, previous, pct_change), any of which may be None."""
    values = series.dropna()
    if len(values) == 0:
        return None, None, None
    latest = values.iloc[-1]
    previous = values.iloc[-2] if len(values) > 1 else None
    pct_change = None
    if previous not in (None, 0):
        pct_change = (latest - previous) / abs(previous) * 100
    return latest, previous, pct_change


def delta_badge_html(pct_change, good_direction="up"):
    """good_direction='up' means a rise is good (navy). 'down' means a rise is bad (pink), e.g. churn rates."""
    if pct_change is None:
        return ""
    direction = "up" if pct_change >= 0 else "down"
    is_good = direction == good_direction
    arrow = "▲" if direction == "up" else "▼"
    css_class = "positive" if is_good else "negative"
    return f'<span class="delta {css_class}">{arrow} {abs(pct_change):.1f}%</span>'


def threshold_badge_html(value, threshold=100, unit="%"):
    """For metrics with a fixed pass/fail line (NRR vs. 100%) rather than a period-over-period compare."""
    is_good = value >= threshold
    arrow = "▲" if is_good else "▼"
    css_class = "positive" if is_good else "negative"
    return f'<span class="delta {css_class}">{arrow} {value:.1f}{unit}</span>'


# ---------------------------------------------------------------------------
# 3. Chart factories -- one function per chart type, reused across cards
# ---------------------------------------------------------------------------

def _base_layout(height=260, y_title="", x_title="", y_tickprefix=""):
    return dict(
        height=height,
        margin=dict(l=55, r=20, t=10, b=40),
        font=dict(family=FONT_FAMILY, color=PALETTE["text_dark"], size=11),
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=x_title, type="category", showgrid=False, tickangle=-45),
        yaxis=dict(title=y_title, tickprefix=y_tickprefix, showgrid=True, gridcolor="#f0f1f4", zeroline=False),
        hovermode="x unified",
        showlegend=False,
    )


def make_line_figure(x, y, color=None, y_title="", y_tickprefix="$", fill=False):
    color = color or PALETTE["navy"]
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers",
        line=dict(color=color, width=2.5), marker=dict(size=5, color=color),
        fill="tozeroy" if fill else None,
        fillcolor="rgba(27, 54, 93, 0.08)" if fill else None,
        hovertemplate=f"%{{x}}<br>{y_tickprefix}%{{y:,.1f}}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(y_title=y_title, y_tickprefix=y_tickprefix))
    return fig


def make_multiline_figure(df, x_col, y_col, group_col, color_map, y_title="", y_tickprefix="$"):
    fig = go.Figure()
    for group_value in sorted(df[group_col].unique()):
        group_df = df[df[group_col] == group_value].sort_values(x_col)
        color = color_map.get(group_value, PALETTE["gray"])
        fig.add_trace(go.Scatter(
            x=group_df[x_col], y=group_df[y_col], mode="lines+markers", name=str(group_value),
            line=dict(color=color, width=2.2), marker=dict(size=4, color=color),
            hovertemplate=f"{group_value}<br>%{{x}}<br>{y_tickprefix}%{{y:,.1f}}<extra></extra>",
        ))
    layout = _base_layout(y_title=y_title, y_tickprefix=y_tickprefix)
    layout["showlegend"] = True
    layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
    layout["margin"] = dict(l=55, r=20, t=30, b=40)
    fig.update_layout(**layout)
    return fig


def make_movements_figure(df, x_col, bar_cols, line_col, color_map, y_title="MRR change ($)"):
    """Stacked bars for each movement, plus a net line. The hover shows the dollars and
    the same movement as a share of the previous month's MRR. That share is read from
    the column named by movement_pct_column(), added in add_movement_percentages()."""
    fig = go.Figure()
    for col in bar_cols:
        fig.add_trace(go.Bar(
            x=df[x_col], y=df[col], name=col, marker_color=color_map[col],
            customdata=df[movement_pct_column(col)],
            hovertemplate=f"{col}<br>%{{x}}<br>$%{{y:,.0f}} (%{{customdata:+.2f}}% of prior MRR)<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[line_col], mode="lines+markers", name=line_col,
        line=dict(color=PALETTE["text_dark"], width=2.5), marker=dict(size=6),
        customdata=df[movement_pct_column(line_col)],
        hovertemplate=f"{line_col}<br>%{{x}}<br>$%{{y:,.0f}} (%{{customdata:+.2f}}% of prior MRR)<extra></extra>",
    ))
    layout = _base_layout(y_title=y_title, y_tickprefix="$", height=320)
    layout["barmode"] = "relative"
    layout["showlegend"] = True
    layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
    layout["margin"] = dict(l=60, r=20, t=30, b=40)
    layout["yaxis"]["zeroline"] = True
    layout["yaxis"]["zerolinecolor"] = "#c7c9d1"
    fig.update_layout(**layout)
    return fig


MOVEMENT_COLUMNS = ["New Business", "Expansion", "Contraction", "Churn", "Net MRR Growth"]


def movement_pct_column(column):
    """'Churn' -> 'Churn % of prior MRR'. One name, used by the chart and the export."""
    return f"{column} % of prior MRR"


def add_movement_percentages(kpis):
    """Add each movement as a % of the previous month's MRR to kpis['mrr_movements'].

    Run once on the full history, before any timeframe is cut. That way the first month
    of a window still divides by the real previous month. A month with no previous month
    on record (the very first one) is left blank.
    """
    mrr = kpis["total_mrr_by_month"]
    movements = kpis["mrr_movements"].copy()
    previous_months = movements["calendar_month"].map(lambda m: str(pd.Period(m, "M") - 1))
    movements["Prior Month MRR"] = previous_months.map(mrr.to_dict()).astype(float)
    for column in MOVEMENT_COLUMNS:
        movements[movement_pct_column(column)] = movements[column] / movements["Prior Month MRR"] * 100
    kpis = dict(kpis)
    kpis["mrr_movements"] = movements
    return kpis


def make_heatmap_figure(grid_df, zmin=0, zmax=100, value_suffix="%"):
    fig = go.Figure(go.Heatmap(
        z=grid_df.values,
        x=[str(c) for c in grid_df.columns],
        y=[str(r) for r in grid_df.index],
        colorscale=HEATMAP_SCALE, zmin=zmin, zmax=zmax,
        colorbar=dict(title=value_suffix, thickness=12, len=0.9),
        hovertemplate=f"Cohort %{{y}}<br>Month %{{x}}<br>%{{z:.1f}}{value_suffix}<extra></extra>",
    ))
    fig.update_layout(
        height=max(320, 22 * len(grid_df) + 90),
        margin=dict(l=80, r=20, t=10, b=45),
        font=dict(family=FONT_FAMILY, color=PALETTE["text_dark"], size=11),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Lifetime month", type="category"),
        yaxis=dict(title="Cohort month", type="category", autorange="reversed"),
    )
    return fig


def make_small_multiple_heatmap_figure(grid_dict, zmin=0, zmax=100, value_suffix="%"):
    names = list(grid_dict.keys())
    fig = make_subplots(rows=1, cols=len(names), subplot_titles=names, horizontal_spacing=0.03)
    tallest = max(len(g) for g in grid_dict.values())
    for position, name in enumerate(names, start=1):
        grid = grid_dict[name]
        fig.add_trace(
            go.Heatmap(
                z=grid.values, x=[str(c) for c in grid.columns], y=[str(r) for r in grid.index],
                colorscale=HEATMAP_SCALE, zmin=zmin, zmax=zmax, showscale=(position == len(names)),
                colorbar=dict(title=value_suffix, thickness=12, len=0.9),
                hovertemplate=f"{name}<br>Cohort %{{y}}<br>Month %{{x}}<br>%{{z:.1f}}{value_suffix}<extra></extra>",
            ),
            row=1, col=position,
        )
        fig.update_yaxes(autorange="reversed", type="category", row=1, col=position)
        fig.update_xaxes(type="category", title="Lifetime month", row=1, col=position)
    fig.update_layout(
        height=max(320, 22 * tallest + 110),
        margin=dict(l=70, r=20, t=40, b=45),
        font=dict(family=FONT_FAMILY, color=PALETTE["text_dark"], size=11),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _auto_column_widths(columns):
    """Plotly Table doesn't wrap-aware-autofit columns -- equal widths mean any column
    with longer text (like a status label) wraps to 2 lines, which both breaks vertical
    alignment against single-line columns and overflows the table's fixed height. Sizing
    columns from actual content length avoids the wrap in the first place."""
    widths = []
    for c in columns:
        header_len = len(c["label"])
        max_val_len = max((len(str(v)) for v in c["values"]), default=0)
        widths.append(max(header_len, max_val_len) + 3)
    return widths


def make_table_figure(columns, row_fill_colors, height=None, column_width=None):
    """
    Polished go.Table, following plotly_table_polished.txt:
    row line_color is set to match row fill_color (erases gridlines), and
    numeric columns get their own font-color array for at-a-glance status.

    columns: list of dicts, each {"label": str, "values": list, "align": "left"|"right",
             "font_color": str or list (defaults to text_dark),
             "fill_color": list (optional, per-row background tint for this column only --
             falls back to row_fill_colors, i.e. the normal alternating stripe, when absent)}
    row_fill_colors: list, one fill color per row (also used as the line color)
    column_width: optional list of relative widths, one per column. Auto-sized from
    content length when omitted -- pass this only to override that default.
    """
    n_rows = len(row_fill_colors)
    header_values = [f"<b>{c['label']}</b>" for c in columns]
    cell_values = [c["values"] for c in columns]
    align = [c.get("align", "left") for c in columns]
    font_colors = [
        c.get("font_color", PALETTE["text_dark"]) if isinstance(c.get("font_color"), list)
        else [c.get("font_color", PALETTE["text_dark"])] * n_rows
        for c in columns
    ]
    fill_per_column = [c.get("fill_color", row_fill_colors) for c in columns]
    line_per_column = [c.get("fill_color", row_fill_colors) for c in columns]
    widths = column_width or _auto_column_widths(columns)

    fig = go.Figure(go.Table(
        columnwidth=widths,
        header=dict(
            values=header_values, fill_color=PALETTE["navy"], line_color=PALETTE["navy"],
            font=dict(color="#ffffff", size=12, family=FONT_FAMILY), align=align, height=32,
        ),
        cells=dict(
            values=cell_values, fill_color=fill_per_column, line_color=line_per_column,
            font=dict(color=font_colors, size=12, family=FONT_FAMILY), align=align, height=30,
        ),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=4, b=4),
        height=height or (32 + 30 * n_rows + 20),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY),
    )
    return fig


# Shared 3-tier read on an LTV:CAC ratio -- reused by the Unit Economics table
# and the Payback table so both use the same thresholds and the same colors.
# cell_label stays short so it never wraps inside a narrow table column;
# legend_label carries the full context and only ever sits in the wide caption row.
RATIO_TIERS = {
    "healthy":     {"cell_label": "Healthy",     "legend_label": "Healthy (3x+)",
                     "font": PALETTE["navy"], "fill": "#eef1f6"},
    "below_floor": {"cell_label": "Below floor", "legend_label": "Below the 3x floor",
                     "font": "#8a6d1a",       "fill": "#fdf3d9"},
    "underwater":  {"cell_label": "Underwater",  "legend_label": "Underwater (under 1x)",
                     "font": PALETTE["pink"], "fill": "#ffe3e9"},
}


def ratio_tier(ratio):
    if ratio < 1:
        return RATIO_TIERS["underwater"]
    if ratio < 3:
        return RATIO_TIERS["below_floor"]
    return RATIO_TIERS["healthy"]


def build_table_legend(*tier_keys):
    """Small caption row under a table, reusing the same colors as the cells above it
    so the color-to-meaning mapping doesn't have to be guessed."""
    chips = []
    for key in tier_keys:
        tier = RATIO_TIERS[key]
        chips.append(
            f'<span style="color:{tier["font"]}; font-weight:600;">&#9679;</span> {tier["legend_label"]}'
        )
    return f'<div class="table-legend">{"&nbsp;&nbsp;&nbsp;".join(chips)}</div>'


# ---------------------------------------------------------------------------
# 4. Card assembly -- wraps a figure (or several) in the callout card shell
# ---------------------------------------------------------------------------

_card_counter = {"n": 0}
_card_log = []  # every card headline built for the current page, saved by the data export


def _log_card(title, value_text, value_sub, badge_html):
    """Remember a card's headline text so the data export holds exactly what the page shows."""
    if value_text is None:
        return
    _card_log.append({
        "card": title,
        "headline": re.sub(r"<[^>]+>", "", str(value_text)).strip(),
        "subtext": re.sub(r"<[^>]+>", "", str(value_sub or "")).strip(),
        "badge": re.sub(r"<[^>]+>", "", str(badge_html or "")).replace("&nbsp;", " ").strip(),
    })


def _next_id(prefix):
    _card_counter["n"] += 1
    return f"{prefix}-{_card_counter['n']}"


def _embed(fig, div_id):
    return pyo.plot(fig, include_plotlyjs=False, output_type="div", config=CHART_CONFIG,
                     filename=div_id, auto_open=False)


def build_card(title, fig, value_text=None, value_sub=None, badge_html="", full_width=False, footnote=""):
    div_id = _next_id("chart")
    chart_html = _embed(fig, div_id)
    _log_card(title, value_text, value_sub, badge_html)
    value_line = ""
    if value_text is not None:
        sub = f'<span class="card-value-sub">{value_sub}</span>' if value_sub else ""
        value_line = f'<div class="card-value">{value_text}{sub}</div>'
    extra_class = "card--full" if full_width else ""
    return f"""
<div class="card {extra_class}" id="{_slugify(title)}">
  <div class="card-header">
    <span class="card-title">{title}</span>
    {badge_html}
  </div>
  {value_line}
  <div class="card-body">{chart_html}</div>
  {footnote}
</div>"""


def build_toggle_card(title, options, value_text=None, value_sub=None, badge_html=""):
    """options: list of (label, figure) pairs. Renders as a full-width card with a button row."""
    card_id = _next_id("toggle")
    buttons, panels = [], []
    for i, (label, fig) in enumerate(options):
        div_id = _next_id("chart")
        chart_html = _embed(fig, div_id)
        active = "active" if i == 0 else ""
        buttons.append(f'<button class="seg-btn {active}" onclick="showSegment(\'{card_id}\', {i})">{label}</button>')
        panels.append(f'<div class="seg-panel {active}">{chart_html}</div>')

    _log_card(title, value_text, value_sub, badge_html)
    value_line = ""
    if value_text is not None:
        sub = f'<span class="card-value-sub">{value_sub}</span>' if value_sub else ""
        value_line = f'<div class="card-value">{value_text}{sub}</div>'

    return f"""
<div class="card card--full" id="{_slugify(title)}">
  <div class="card-header">
    <span class="card-title">{title}</span>
    {badge_html}
  </div>
  {value_line}
  <div class="seg-control" data-card="{card_id}">{''.join(buttons)}</div>
  <div class="card-body">{''.join(panels)}</div>
</div>"""


# ---------------------------------------------------------------------------
# 5. Tabs -- which KPI feeds which card, in what order (the wireframe)
# ---------------------------------------------------------------------------

def extract_nav_items(card_html_list):
    """Pull (title, anchor_id) out of each rendered card, in order, so the
    sidebar sub-nav always matches whatever build_revenue_tab / build_customer_tab
    actually produced -- no separate list to keep in sync by hand."""
    items = []
    for card_html in card_html_list:
        id_match = re.search(r'id="(card-[^"]+)"', card_html)
        title_match = re.search(r'<span class="card-title">([^<]+)</span>', card_html)
        if id_match and title_match:
            items.append((title_match.group(1), id_match.group(1)))
    return items


def build_revenue_tab(kpis):
    cards = []

    latest, previous, pct = compute_delta(kpis["total_mrr_by_month"])
    fig = make_line_figure(kpis["total_mrr_by_month"].index, kpis["total_mrr_by_month"].values)
    cards.append(build_card("Total MRR", fig, format_dollars(latest),
                             f"from {format_dollars(previous)}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="up")))

    latest, previous, pct = compute_delta(kpis["arr_by_month"])
    fig = make_line_figure(kpis["arr_by_month"].index, kpis["arr_by_month"].values, fill=True)
    cards.append(build_card("ARR (Run-Rate)", fig, format_dollars(latest),
                             f"from {format_dollars(previous)}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="up")))

    movements = kpis["mrr_movements"]
    net_series = movements.set_index("calendar_month")["Net MRR Growth"]
    latest, previous, pct = compute_delta(net_series)
    fig = make_movements_figure(movements, "calendar_month",
                                 ["New Business", "Expansion", "Contraction", "Churn"],
                                 "Net MRR Growth", MOVEMENT_COLORS)
    cards.append(build_card("MRR Movements", fig, format_dollars(latest), "net change this month",
                             delta_badge_html(pct, good_direction="up"), full_width=True))

    arpu_series = kpis["arpu_by_month"].set_index("calendar_month")["arpu"]
    latest, previous, pct = compute_delta(arpu_series)
    fig = make_line_figure(arpu_series.index, arpu_series.values)
    cards.append(build_card("ARPU", fig, format_dollars(latest),
                             f"from {format_dollars(previous)}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="up")))

    churn_series = kpis["revenue_churn_rate"].set_index("calendar_month")["revenue_churn_rate_pct"]
    latest, previous, pct = compute_delta(churn_series)
    fig = make_line_figure(churn_series.index, churn_series.values, color=PALETTE["pink"], y_tickprefix="")
    cards.append(build_card("Revenue Churn Rate", fig, format_percent(latest),
                             f"from {format_percent(previous)}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="down")))

    nrr_overall = kpis["nrr_overall"]
    latest_nrr = nrr_overall.dropna().iloc[-1]
    fig_all = make_line_figure(nrr_overall.index, nrr_overall.values, y_tickprefix="")
    fig_channel = make_multiline_figure(kpis["nrr_by_channel"], "calendar_month", "nrr_percentage",
                                         "channel", CHANNEL_COLORS, y_tickprefix="")
    fig_plan = make_multiline_figure(kpis["nrr_by_plan_tier"], "calendar_month", "nrr_percentage",
                                      "plan_tier", PLAN_TIER_COLORS, y_tickprefix="")
    for f in (fig_all, fig_channel, fig_plan):
        f.add_hline(y=100, line_dash="dash", line_color=PALETTE["text_muted"], line_width=1)
    cards.append(build_toggle_card(
        "Net Revenue Retention",
        [("All", fig_all), ("By Channel", fig_channel), ("By Plan Tier", fig_plan)],
        format_percent(latest_nrr), "existing customers only",
        threshold_badge_html(latest_nrr, threshold=100),
    ))

    fig = make_heatmap_figure(kpis["mrr_retention_grid"], zmin=0,
                               zmax=max(120, kpis["mrr_retention_grid"].max().max()))
    cards.append(build_card("Revenue Retention Heatmap (blended)", fig, full_width=True))

    return cards


def build_customer_tab(kpis):
    cards = []


    counts = kpis["customer_counts_by_month"]
    active_series = counts.set_index("calendar_month")["active_customers"]
    latest, previous, pct = compute_delta(active_series)
    long_counts = counts.melt(id_vars="calendar_month",
                               value_vars=["active_customers", "new_customers", "churned_customers"],
                               var_name="series", value_name="count")
    series_labels = {"active_customers": "Active", "new_customers": "New", "churned_customers": "Churned"}
    long_counts["series"] = long_counts["series"].map(series_labels)
    series_colors = {"Active": PALETTE["navy"], "New": PALETTE["gold"], "Churned": PALETTE["pink"]}
    fig = make_multiline_figure(long_counts, "calendar_month", "count", "series", series_colors, y_tickprefix="")
    cards.append(build_card("Active Customers", fig, f"{latest:,.0f}",
                             f"from {previous:,.0f}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="up"), full_width=True))

    logo_churn = kpis["logo_churn_rate"].set_index("calendar_month")["churn_rate_percentage"]
    latest, previous, pct = compute_delta(logo_churn)
    fig = make_line_figure(logo_churn.index, logo_churn.values, color=PALETTE["pink"], y_tickprefix="")
    cards.append(build_card("Customer Churn Rate", fig, format_percent(latest),
                             f"from {format_percent(previous)}" if previous is not None else None,
                             delta_badge_html(pct, good_direction="down")))

    cac = kpis["cac_by_channel"]
    blended_cac = kpis["blended_cac_by_cohort"]  # total spend / total new customers, same as the payback table
    latest, previous, pct = compute_delta(blended_cac)
    fig = make_multiline_figure(cac, "cohort_month", "cac_per_customer_dollars", "channel", CHANNEL_COLORS)
    cards.append(build_card("CAC by Channel", fig, format_dollars(latest), "per new customer, all channels",
                             delta_badge_html(pct, good_direction="down")))

    fig = make_heatmap_figure(kpis["cohort_retention_grid"])
    cards.append(build_card("Cohort Retention Heatmap (blended)", fig, full_width=True))

    fig_channel = make_small_multiple_heatmap_figure(kpis["retention_grid_by_channel"])
    fig_plan = make_small_multiple_heatmap_figure(kpis["retention_grid_by_plan_tier"])
    cards.append(build_toggle_card(
        "Retention Heatmap by Segment",
        [("By Channel", fig_channel), ("By Plan Tier", fig_plan)],
    ))

    unit_econ = kpis["unit_economics"].copy()
    unit_econ = unit_econ.sort_values(["channel", "plan_tier"])
    row_fill = ["#ffffff" if i % 2 == 0 else "#f4f4f6" for i in range(len(unit_econ))]
    tiers = [ratio_tier(r) for r in unit_econ["ltv_to_cac_ratio"]]
    columns = [
        {"label": "Channel", "values": unit_econ["channel"].tolist(), "align": "left"},
        {"label": "Plan Tier", "values": unit_econ["plan_tier"].tolist(), "align": "left"},
        {"label": "24-Month LTV", "values": [format_dollars(v) for v in unit_econ["ltv_24m"]], "align": "right"},
        {"label": "Average CAC", "values": [format_dollars(v) for v in unit_econ["average_cac"]], "align": "right"},
        {"label": "LTV:CAC Ratio", "values": [f"{v:.2f}x" for v in unit_econ["ltv_to_cac_ratio"]],
         "align": "right", "font_color": [t["font"] for t in tiers], "fill_color": [t["fill"] for t in tiers]},
        {"label": "Read", "values": [t["cell_label"] for t in tiers],
         "align": "left", "font_color": [t["font"] for t in tiers], "fill_color": [t["fill"] for t in tiers]},
    ]
    # One ratio for all mature customers together. Each customer counts once, so big
    # segments weigh more than small ones. Summing the rows above would not do that.
    blended = kpis["blended_unit_economics"]
    blended_ratio = blended["ltv_to_cac_ratio"]
    has_ratio = pd.notna(blended_ratio)
    if blended["cohort_count"] == 1:
        cohort_text = f'{blended["mature_customers"]:,} customers who signed up in the {blended["first_cohort"]} cohort'
    elif blended["cohort_count"]:
        cohort_text = (f'{blended["mature_customers"]:,} customers who signed up in the '
                       f'{blended["cohort_count"]} cohorts from {blended["first_cohort"]} to {blended["last_cohort"]}')
    else:
        cohort_text = "no customers yet, since no cohort in this window has a full 24 months of history"
    unit_note = (f'<div class="table-legend">24-month LTV for {cohort_text}. These are the cohorts with '
                 f'a full 24 months of history. Each customer counts once. '
                 f'A cohort\'s 24 months can run past the end of the selected timeframe.</div>')
    fig = make_table_figure(columns, row_fill)
    cards.append(build_card(
        "Unit Economics", fig, f"{blended_ratio:.2f}x" if has_ratio else "n/a", "blended 24-month LTV:CAC",
        threshold_badge_html(blended_ratio, threshold=3, unit="x") if has_ratio else "",
        footnote=build_table_legend("healthy", "below_floor", "underwater") + unit_note,
    ))

    payback = kpis["ltv_cac_payback"].copy()
    payback_labels = [
        f"Month {int(m)}" if pd.notna(m) else "Not yet"
        for m in payback["payback_lifetime_month"]
    ]
    payback_month_colors = [PALETTE["pink"] if lbl == "Not yet" else PALETTE["navy"] for lbl in payback_labels]
    # A star marks cohorts that have not reached 24 months yet. Their ratio is to date.
    ratio_labels = [
        "n/a" if pd.isna(ratio) else f"{ratio:.2f}x" + ("" if mature else "*")
        for ratio, mature in zip(payback["latest_ratio"], payback["is_mature_24m"])
    ]
    has_young_cohorts = not payback["is_mature_24m"].all()
    
    row_fill = ["#ffffff" if i % 2 == 0 else "#f4f4f6" for i in range(len(payback))]
    columns = [
        {"label": "Cohort", "values": payback["cohort_month"].tolist(), "align": "left"},
        {"label": "Starting CAC", "values": [format_dollars(v) for v in payback["starting_cac"]], "align": "right"},
        {"label": "Payback Month", "values": payback_labels, "align": "right", "font_color": payback_month_colors},
        {"label": "24-Mo LTV:CAC", "values": ratio_labels, "align": "right"},
    ]
    paid_back_count = sum(1 for lbl in payback_labels if lbl != "Not yet")
    not_yet_flags = [lbl == "Not yet" for lbl in payback_labels]
    n_not_yet = sum(not_yet_flags)
    # cohorts are listed oldest-to-newest; if every "Not yet" cohort is one of the
    # most recent ones, that's an age effect, not a stalled cohort -- say so.
    trailing_not_yet = not_yet_flags == ([False] * (len(not_yet_flags) - n_not_yet) + [True] * n_not_yet)
    if n_not_yet == 0:
        payback_note = "Every cohort on record has recovered its acquisition cost."
    elif trailing_not_yet:
        payback_note = (f"The {n_not_yet} cohort(s) marked \"Not yet\" are the most recent ones -- "
                         f"they simply haven't had enough months to break even, not a stalled cohort.")
    else:
        payback_note = (f"{n_not_yet} cohort(s) marked \"Not yet\" are not all recent -- "
                         f"worth checking whether any of these have stalled rather than just started.")
    if has_young_cohorts:
        payback_note += " * Cohort is under 24 months old, so its ratio is to date."
    fig = make_table_figure(columns, row_fill)
    cards.append(build_card(
        "LTV:CAC Payback", fig, f"{paid_back_count}/{len(payback)}", "cohorts paid back",
        footnote=f'<div class="table-legend">{payback_note}</div>',
    ))

    return cards


# ---------------------------------------------------------------------------
# 6. Final HTML assembly
# ---------------------------------------------------------------------------

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SaaS Dashboard | {timeframe_title}</title>
<style>{css}</style>
</head>
<body>
{plotly_script}

<div class="app-shell">
  <aside class="sidebar">
    <div class="sidebar-title">SaaS Executive Dashboard</div>
    {sidebar_timeframe}
    <nav class="nav-list">
      <div class="nav-group">
        <button class="nav-item active" id="navbtn-revenue" onclick="showTab('revenue')">Revenue</button>
        <div class="nav-sublist">{revenue_nav}</div>
      </div>
      <div class="nav-group">
        <button class="nav-item" id="navbtn-customer" onclick="showTab('customer')">Customers</button>
        <div class="nav-sublist">{customer_nav}</div>
      </div>
    </nav>
    {sidebar_links}
  </aside>

  <main class="main-content">
    <div class="dashboard-container">
      <div class="page-header">
        <div>
          <h1>SaaS Control Center</h1>
          <p class="subtitle">Revenue and customer KPIs, generated from the business simulation dataset.</p>
        </div>
        {timeframe_control}
      </div>

      <div class="tab-panel active" id="tab-revenue"><div class="grid">{revenue_cards}</div></div>
      <div class="tab-panel" id="tab-customer"><div class="grid">{customer_cards}</div></div>
    </div>
  </main>
</div>

<script>
function resizeAllIn(container) {{
  if (!container) return;
  var plots = container.querySelectorAll('.plotly-graph-div');
  plots.forEach(function(p) {{ try {{ Plotly.Plots.resize(p); }} catch (e) {{}} }});
}}
function showTab(name) {{
  document.querySelectorAll('.tab-panel').forEach(function(el) {{ el.classList.remove('active'); }});
  document.querySelectorAll('.nav-item').forEach(function(el) {{ el.classList.remove('active'); }});
  var panel = document.getElementById('tab-' + name);
  panel.classList.add('active');
  document.getElementById('navbtn-' + name).classList.add('active');
  resizeAllIn(panel);
}}
function goToChart(event, tabName, anchorId) {{
  event.preventDefault();
  showTab(tabName);
  // Wait two frames so the tab is visible and Plotly has resized before we scroll,
  // otherwise the target's position is measured against the old (hidden) layout.
  requestAnimationFrame(function() {{
    requestAnimationFrame(function() {{
      var el = document.getElementById(anchorId);
      if (el) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
    }});
  }});
}}
function showSegment(cardId, index) {{
  var control = document.querySelector('[data-card="' + cardId + '"]');
  var body = control.parentElement.querySelector('.card-body');
  var panels = body.querySelectorAll('.seg-panel');
  panels.forEach(function(p, i) {{ p.classList.toggle('active', i === index); }});
  control.querySelectorAll('.seg-btn').forEach(function(b, i) {{ b.classList.toggle('active', i === index); }});
  resizeAllIn(body);
}}
function keepTab(link) {{
  // Carry the open tab into the next timeframe file, e.g. saas_dashboard_2023-2025.html#customer
  var open = document.querySelector('.tab-panel.active');
  if (open) link.hash = '#' + open.id.replace('tab-', '');
}}
document.addEventListener('DOMContentLoaded', function() {{
  var wanted = location.hash.replace('#', '');
  var tab = (wanted === 'customer') ? 'customer' : 'revenue';
  if (tab === 'customer') showTab('customer');
  resizeAllIn(document.getElementById('tab-' + tab));
}});
</script>
</body>
</html>
"""


def _render_sublinks(tab_name, nav_items):
    links = [
        f'<a href="#{anchor_id}" class="nav-sublink" '
        f'onclick="goToChart(event, \'{tab_name}\', \'{anchor_id}\')">{title}</a>'
        for title, anchor_id in nav_items
    ]
    return "".join(links)


def _plotly_script_tag(plotly_mode):
    """inline = plotly.js pasted into every file (works offline, about 4.5 MB each).
    external = one shared plotly.min.js next to the HTML files (each HTML file stays small)."""
    if plotly_mode == "external":
        return '<script src="plotly.min.js"></script>'
    return f"<script>{pyo.get_plotlyjs()}</script>"


def build_dashboard_html(kpis, option, plotly_mode="inline", built_slugs=None, export_sink=None):
    """One finished HTML page for one timeframe option from TIMEFRAME_OPTIONS.
    kpis must come from build_all_kpis() on the full exports, not a pre-cut copy.
    export_sink: an empty dict. If given, it is filled with the timeframe's cut KPIs
    and card headlines, which the data export saves."""
    slug, _label, start_year, end_year, _row = option
    _card_counter["n"] = 0  # same card ids in every file, no matter the build order

    window_kpis = filter_kpis_to_window(kpis, start_year, end_year)
    _card_log.clear()
    revenue_card_list = build_revenue_tab(window_kpis)
    revenue_headline_count = len(_card_log)
    customer_card_list = build_customer_tab(window_kpis)
    if export_sink is not None:
        export_sink["window_kpis"] = window_kpis
        export_sink["cards"] = [
            {"tab": "Revenue" if i < revenue_headline_count else "Customers", **card}
            for i, card in enumerate(_card_log)
        ]
    revenue_cards = "".join(revenue_card_list)
    customer_cards = "".join(customer_card_list)
    revenue_nav = _render_sublinks("revenue", extract_nav_items(revenue_card_list))
    customer_nav = _render_sublinks("customer", extract_nav_items(customer_card_list))
    css = CSS_TEMPLATE.format(font_family=FONT_FAMILY, **PALETTE)
    return PAGE_TEMPLATE.format(
        css=css, revenue_cards=revenue_cards, customer_cards=customer_cards,
        revenue_nav=revenue_nav, customer_nav=customer_nav,
        plotly_script=_plotly_script_tag(plotly_mode),
        timeframe_title=timeframe_display(option),
        timeframe_control=build_timeframe_control_html(slug, built_slugs),
        sidebar_timeframe=build_sidebar_timeframe_html(option),
        sidebar_links=build_sidebar_links_html(),
    )


# ---------------------------------------------------------------------------
# 7. Data export -- every chart and table on the pages, as CSV files and one workbook
# ---------------------------------------------------------------------------

WORKBOOK_NAME = "saas_dashboard_data.xlsx"

# (kpi key, sheet name, tab, card or chart it feeds, what the rows are)
# Sheet names stay under 31 characters, the Excel limit.
EXPORT_SHEETS = [
    ("headline_cards", "headline_cards", "Both", "Every card",
     "The big number, the small text and the change badge printed on each card."),
    ("total_mrr_by_month", "total_mrr", "Revenue", "Total MRR", "Total MRR by calendar month."),
    ("arr_by_month", "arr", "Revenue", "ARR (Run-Rate)", "ARR run-rate by calendar month."),
    ("mrr_movements", "mrr_movements", "Revenue", "MRR Movements",
     "New business, expansion, contraction, churn and net MRR change by calendar month, in dollars and as a % of the previous month's MRR."),
    ("arpu_by_month", "arpu", "Revenue", "ARPU", "MRR, active customers and ARPU by calendar month."),
    ("revenue_churn_rate", "revenue_churn", "Revenue", "Revenue Churn Rate", "Revenue churn by calendar month."),
    ("nrr_overall", "nrr_all", "Revenue", "Net Revenue Retention, All", "NRR by calendar month."),
    ("nrr_by_channel", "nrr_by_channel", "Revenue", "Net Revenue Retention, By Channel", "NRR by month and channel."),
    ("nrr_by_plan_tier", "nrr_by_plan_tier", "Revenue", "Net Revenue Retention, By Plan Tier", "NRR by month and plan tier."),
    ("mrr_retention_grid", "revenue_retention_heatmap", "Revenue", "Revenue Retention Heatmap (blended)",
     "Percent of month-0 MRR kept. One row per cohort, one column per lifetime month."),
    ("customer_counts_by_month", "customer_counts", "Customers", "Active Customers",
     "Active, new and churned customers by calendar month."),
    ("logo_churn_rate", "customer_churn", "Customers", "Customer Churn Rate", "Customer (logo) churn by calendar month."),
    ("cac_by_channel", "cac_by_channel", "Customers", "CAC by Channel (chart lines)", "CAC per new customer by cohort and channel."),
    ("blended_cac_by_cohort", "cac_blended", "Customers", "CAC by Channel (big number)",
     "CAC per new customer by cohort, all channels (total spend / total new customers)."),
    ("cohort_retention_grid", "cohort_retention_heatmap", "Customers", "Cohort Retention Heatmap (blended)",
     "Percent of customers still active. One row per cohort, one column per lifetime month."),
    ("retention_grid_by_channel", "retention_by_channel", "Customers", "Retention Heatmap by Segment, By Channel",
     "Same grid as above, one block per channel."),
    ("retention_grid_by_plan_tier", "retention_by_plan_tier", "Customers", "Retention Heatmap by Segment, By Plan Tier",
     "Same grid as above, one block per plan tier."),
    ("unit_economics", "unit_economics_table", "Customers", "Unit Economics (table)",
     "24-month LTV, average CAC and LTV:CAC by channel and plan tier, plus the Read label."),
    ("blended_unit_economics", "unit_economics_blended", "Customers", "Unit Economics (big number)",
     "One blended LTV:CAC for all mature customers together."),
    ("ltv_cac_payback", "ltv_cac_payback", "Customers", "LTV:CAC Payback (table)",
     "Starting CAC, payback month and 24-month LTV:CAC by cohort, plus the labels shown."),
]
_SEGMENT_COLUMN = {"retention_grid_by_channel": "channel", "retention_grid_by_plan_tier": "plan_tier"}


def _grid_frame(grid, segment_column=None, segment_value=None):
    frame = grid.reset_index()
    frame.columns = [str(column) for column in frame.columns]
    if segment_column:
        frame.insert(0, segment_column, segment_value)
    return frame


def _kpi_to_frame(key, value):
    """Turn one KPI (series, table, grid, dict of grids or dict of numbers) into a flat table."""
    if isinstance(value, pd.Series):
        return value.rename(value.name or key).reset_index()
    if isinstance(value, dict) and value and all(isinstance(v, pd.DataFrame) for v in value.values()):
        segment_column = _SEGMENT_COLUMN[key]
        return pd.concat([_grid_frame(grid, segment_column, name) for name, grid in value.items()],
                         ignore_index=True)
    if isinstance(value, dict):
        return pd.DataFrame([value])
    if value.index.name is not None:  # the heatmap grids
        return _grid_frame(value)
    return value.reset_index(drop=True)


def tidy_window_frames(window_kpis, cards):
    """The data behind one page as {sheet name: table}. Same values the page shows."""
    frames = {"headline_cards": pd.DataFrame(cards, columns=["tab", "card", "headline", "subtext", "badge"])}
    for key, sheet, *_ in EXPORT_SHEETS:
        if key == "headline_cards":
            continue
        frames[sheet] = _kpi_to_frame(key, window_kpis[key])

    # Add the labels the tables print, so nothing on the page is missing from the data.
    unit_table = frames["unit_economics_table"]
    unit_table["read"] = [
        "n/a" if pd.isna(r) else ratio_tier(r)["cell_label"] for r in unit_table["ltv_to_cac_ratio"]
    ]
    payback_table = frames["ltv_cac_payback"]
    payback_table["payback_label"] = [
        f"Month {int(m)}" if pd.notna(m) else "Not yet" for m in payback_table["payback_lifetime_month"]
    ]
    payback_table["ratio_shown"] = [
        "n/a" if pd.isna(r) else f"{r:.2f}x" + ("" if mature else "*")
        for r, mature in zip(payback_table["latest_ratio"], payback_table["is_mature_24m"])
    ]
    return {name: frame.round(4) for name, frame in frames.items()}


# ---------------------------------------------------------------------------
# 8. Summary report tables -- every table and figure in vc_funding_readiness_summary_.md
# ---------------------------------------------------------------------------
# These sheets use the full history (every month and every cohort), so they do not
# depend on which timeframes were built. Values are written as text, formatted
# exactly as the summary prints them, so each cell can be checked by eye.
# Edit the months and cohorts below if the summary moves to another period.

SUMMARY_MONTHS = ("2024-12", "2025-12")
SUMMARY_MOVEMENT_MONTHS = ("2023-12", "2024-12", "2025-12")
SUMMARY_MOM_MONTHS = ("2023-06", "2023-12", "2024-06", "2024-12", "2025-06", "2025-12")
SUMMARY_RETENTION_COHORTS = ("2023-01", "2024-01", "2025-01")
SUMMARY_RETENTION_MONTHS = (1, 12, 24)
SUMMARY_PAYBACK_RANGES = (("2023-01", "2025-12"), ("2024-01", "2025-12"))
SUMMARY_SIGNUP_FLAT_FROM = "2026-01"
SUMMARY_NRR_BAR = 110.0  # the Series A bar quoted in the summary

# (sheet name, summary section, summary table)
SUMMARY_SHEETS = [
    ("summary_exec", "Executive Summary", "Signal table (Dec 2024 vs Dec 2025)"),
    ("summary_growth", "1. Growth & Scale", "Total MRR, ARR, ARPU, Active customers"),
    ("summary_mom_growth", "1. Growth & Scale", "MoM MRR growth by period"),
    ("summary_mrr_movement", "1. Growth & Scale", "MRR movement for each December"),
    ("summary_mrr_movement_pct", "1. Growth & Scale", "The movement rows as a share of the previous month's MRR (cited in the text)"),
    ("summary_retention_churn", "2. Retention & Churn", "NRR, revenue churn, logo churn"),
    ("summary_nrr_segment", "2. Retention & Churn", "NRR by segment"),
    ("summary_cohort_retention", "2. Retention & Churn", "Cohort retention at month 1, 12 and 24"),
    ("summary_unit_econ_dec", "3. Unit Economics & Efficiency", "December cohort: CAC, LTV:CAC, payback"),
    ("summary_segment_ltv_cac", "3. Unit Economics & Efficiency", "LTV:CAC by segment (full history)"),
    ("summary_prose_numbers", "Throughout", "Every other figure quoted in the text, with how it is calculated"),
    ("summary_source_map", "Where the numbers come from", "File names the summary lists, and the workbook sheet that holds each now"),
]


def _month_label(month):
    return pd.Period(month, "M").strftime("%b %Y")


def _previous_month(month):
    return str(pd.Period(month, "M") - 1)


def _lookup(series, key):
    try:
        return series.loc[key]
    except KeyError:
        return np.nan


def _money(value):
    if pd.isna(value):
        return "n/a"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def _pct(value, decimals=1, sign=False):
    if pd.isna(value):
        return "n/a"
    return f"{value:+.{decimals}f}%" if sign else f"{value:.{decimals}f}%"


def _ratio_text(value):
    return "n/a" if pd.isna(value) else f"{value:.2f}x"


def _growth_pct(series, month):
    current, before = _lookup(series, month), _lookup(series, _previous_month(month))
    return (current / before - 1) * 100 if pd.notna(current) and pd.notna(before) and before != 0 else np.nan


def _by_month(frame, value_column, month_column="calendar_month"):
    return frame.set_index(month_column)[value_column]


def _segment_value(long_frame, segment_column, segment, month):
    match = long_frame[(long_frame[segment_column] == segment) & (long_frame["calendar_month"] == month)]
    return match["nrr_percentage"].iloc[0] if len(match) else np.nan


def build_summary_tables(kpis):
    """Every table (and every figure quoted in the text) of the VC funding readiness
    summary, rebuilt from the full-history KPIs. Returns {sheet name: table}."""
    mrr = kpis["total_mrr_by_month"]
    arr = kpis["arr_by_month"]
    nrr = kpis["nrr_overall"]
    arpu = _by_month(kpis["arpu_by_month"], "arpu")
    counts = kpis["customer_counts_by_month"]
    active = _by_month(counts, "active_customers")
    new_customers = _by_month(counts, "new_customers")
    logo_churn = _by_month(kpis["logo_churn_rate"], "churn_rate_percentage")
    revenue_churn = _by_month(kpis["revenue_churn_rate"], "revenue_churn_rate_pct")
    movements = kpis["mrr_movements"].set_index("calendar_month")
    payback = kpis["ltv_cac_payback"].set_index("cohort_month")
    blended_cac = kpis["blended_cac_by_cohort"]
    month_columns = {m: _month_label(m) for m in SUMMARY_MONTHS}
    frames = {}

    # Executive Summary
    rows = []
    for signal, make in [
        ("Logo growth", lambda m: f"{_pct(_growth_pct(active, m), 1, True)} MoM"),
        ("Revenue growth", lambda m: f"{_pct(_growth_pct(mrr, m), 1, True)} MoM"),
        ("LTV:CAC (24-month, December cohort)", lambda m: _ratio_text(_lookup(payback["latest_ratio"], m))),
        ("NRR", lambda m: _pct(_lookup(nrr, m))),
        ("Churn (logo)", lambda m: _pct(_lookup(logo_churn, m))),
        ("Payback (December cohort)", lambda m: "n/a" if pd.isna(_lookup(payback["payback_lifetime_month"], m))
         else f"Lifetime month {int(_lookup(payback['payback_lifetime_month'], m))}"),
    ]:
        rows.append({"Signal": signal, **{month_columns[m]: make(m) for m in SUMMARY_MONTHS}})
    frames["summary_exec"] = pd.DataFrame(rows)

    # 1. Growth & Scale
    rows = []
    for metric, make in [
        ("Total MRR", lambda m: f"{_money(_lookup(mrr, m))} (from {_money(_lookup(mrr, _previous_month(m)))}, {_pct(_growth_pct(mrr, m), 1, True)})"),
        ("ARR (run-rate)", lambda m: _money(_lookup(arr, m))),
        ("ARPU", lambda m: f"{_money(_lookup(arpu, m))} ({_pct(_growth_pct(arpu, m), 1, True)})"),
        ("Active customers", lambda m: f"{_lookup(active, m):,.0f} ({_pct(_growth_pct(active, m), 1, True)})"),
    ]:
        rows.append({"Metric": metric, **{month_columns[m]: make(m) for m in SUMMARY_MONTHS}})
    frames["summary_growth"] = pd.DataFrame(rows)

    frames["summary_mom_growth"] = pd.DataFrame([
        {"Period": m, "MoM MRR growth": _pct(_growth_pct(mrr, m))} for m in SUMMARY_MOM_MONTHS
    ])

    movement_labels = [("New business", "New Business"), ("Expansion", "Expansion"),
                       ("Contraction", "Contraction"), ("Churn", "Churn"), ("Net MRR change", "Net MRR Growth")]
    frames["summary_mrr_movement"] = pd.DataFrame([
        {"MRR movement": label, **{_month_label(m): _money(_lookup(movements[column], m))
                                   for m in SUMMARY_MOVEMENT_MONTHS}}
        for label, column in movement_labels
    ])
    frames["summary_mrr_movement_pct"] = pd.DataFrame([
        {"MRR movement as % of previous month's MRR": label,
         **{_month_label(m): _pct(_lookup(movements[column], m) / _lookup(mrr, _previous_month(m)) * 100, 2)
            for m in SUMMARY_MOVEMENT_MONTHS}}
        for label, column in movement_labels
    ])

    # 2. Retention & Churn
    def with_from(series, m, decimals=1):
        return f"{_pct(_lookup(series, m), decimals)} (from {_pct(_lookup(series, _previous_month(m)), decimals)})"
    frames["summary_retention_churn"] = pd.DataFrame([
        {"Metric": "Net Revenue Retention (NRR)", **{month_columns[m]: _pct(_lookup(nrr, m)) for m in SUMMARY_MONTHS}},
        {"Metric": "Revenue churn rate", **{month_columns[m]: with_from(revenue_churn, m) for m in SUMMARY_MONTHS}},
        {"Metric": "Customer (logo) churn rate", **{month_columns[m]: with_from(logo_churn, m) for m in SUMMARY_MONTHS}},
    ])

    segment_rows = []
    for plan in ["Basic", "Pro", "Enterprise"]:
        segment_rows.append({"NRR by segment": plan, **{month_columns[m]: _pct(_segment_value(
            kpis["nrr_by_plan_tier"], "plan_tier", plan, m)) for m in SUMMARY_MONTHS}})
    for channel in ["Ads", "Organic", "Referral"]:
        segment_rows.append({"NRR by segment": channel, **{month_columns[m]: _pct(_segment_value(
            kpis["nrr_by_channel"], "channel", channel, m)) for m in SUMMARY_MONTHS}})
    frames["summary_nrr_segment"] = pd.DataFrame(segment_rows)

    grid = kpis["cohort_retention_grid"]
    grid.columns = [int(c) if str(c).lstrip("-").isdigit() else c for c in grid.columns]
    frames["summary_cohort_retention"] = pd.DataFrame([
        {"Cohort": _month_label(c),
         **{f"Month {n}": _pct(grid.loc[c, n]) if c in grid.index and n in grid.columns else "n/a"
            for n in SUMMARY_RETENTION_MONTHS}}
        for c in SUMMARY_RETENTION_COHORTS
    ])

    # 3. Unit economics, December cohorts
    cohort_columns = {m: f"{_month_label(m)} cohort" for m in SUMMARY_MONTHS}
    frames["summary_unit_econ_dec"] = pd.DataFrame([
        {"Metric": "CAC per new customer (total spend / total new customers)",
         **{cohort_columns[m]: _money(_lookup(payback["starting_cac"], m)) for m in SUMMARY_MONTHS}},
        {"Metric": "LTV:CAC (24-month)",
         **{cohort_columns[m]: _ratio_text(_lookup(payback["latest_ratio"], m)) for m in SUMMARY_MONTHS}},
        {"Metric": "Payback (lifetime month CAC is recovered)",
         **{cohort_columns[m]: "n/a" if pd.isna(_lookup(payback["payback_lifetime_month"], m))
            else f"{int(_lookup(payback['payback_lifetime_month'], m))}" for m in SUMMARY_MONTHS}},
        {"Metric": "Full 24 months observed",
         **{cohort_columns[m]: "Yes" if bool(_lookup(payback["is_mature_24m"], m)) else "No" for m in SUMMARY_MONTHS}},
    ])

    unit_table = kpis["unit_economics"].copy()
    unit_table["channel"] = pd.Categorical(unit_table["channel"], ["Ads", "Organic", "Referral"], ordered=True)
    unit_table["plan_tier"] = pd.Categorical(unit_table["plan_tier"], ["Basic", "Pro", "Enterprise"], ordered=True)
    unit_table = unit_table.sort_values(["channel", "plan_tier"])
    frames["summary_segment_ltv_cac"] = pd.DataFrame({
        "Segment": [f"{c} / {p}" for c, p in zip(unit_table["channel"], unit_table["plan_tier"])],
        "LTV:CAC (realized)": [_ratio_text(v) for v in unit_table["ltv_to_cac_ratio"]],
        "Mature customers": [f"{v:,.0f}" for v in unit_table["mature_customers"]],
        "24-month LTV": [_money(v) for v in unit_table["ltv_24m"]],
        "Average CAC": [_money(v) for v in unit_table["average_cac"]],
    })

    # Figures quoted in the text
    prose = []

    def add(section, statement, value, how):
        prose.append({"summary_section": section, "figure": statement, "value": value, "how_calculated": how})

    last = SUMMARY_MONTHS[-1]
    add("1. Growth & Scale", f"Yearly ARPU, {_month_label(last)}", _money(_lookup(arpu, last) * 12), "ARPU x 12")
    for first, second in zip(SUMMARY_MOVEMENT_MONTHS[:-1], SUMMARY_MOVEMENT_MONTHS[1:]):
        add("1. Growth & Scale", f"MRR growth {_month_label(first)} to {_month_label(second)}",
            _pct((_lookup(mrr, second) / _lookup(mrr, first) - 1) * 100), "MRR in the later month / MRR in the earlier month - 1")
    for m in SUMMARY_MOVEMENT_MONTHS:
        add("1. Growth & Scale", f"New customers in {_month_label(m)}", f"{_lookup(new_customers, m):,.0f}", "new_customers on the customer_counts sheet")
    add("1. Growth & Scale", f"New customers, {_month_label(SUMMARY_MONTHS[1])} vs {_month_label(SUMMARY_MONTHS[0])}",
        f"{_lookup(new_customers, SUMMARY_MONTHS[1]) / _lookup(new_customers, SUMMARY_MONTHS[0]):.2f}x", "later month / earlier month")
    flat_year = SUMMARY_SIGNUP_FLAT_FROM[:4]
    flat_months = new_customers[new_customers.index.str.startswith(flat_year)]
    if SUMMARY_SIGNUP_FLAT_FROM in new_customers.index:  # absent when the data is cut before this month
        add("1. Growth & Scale", f"New customers, {_month_label(SUMMARY_SIGNUP_FLAT_FROM)}",
            f"{_lookup(new_customers, SUMMARY_SIGNUP_FLAT_FROM):,.0f}", "new_customers on the customer_counts sheet")
    if len(flat_months):
        add("1. Growth & Scale", f"New customers per month, {flat_year} average (low to high {flat_months.min():,.0f} to {flat_months.max():,.0f})",
            f"{flat_months.mean():,.0f}", f"average of the {flat_year} months")
    add("2. Retention & Churn", f"NRR points below the {SUMMARY_NRR_BAR:.0f}% bar, {_month_label(last)}",
        f"{SUMMARY_NRR_BAR - _lookup(nrr, last):.1f} points", f"{SUMMARY_NRR_BAR:.0f} - NRR")
    enterprise = [_segment_value(kpis["nrr_by_plan_tier"], "plan_tier", "Enterprise", m) for m in SUMMARY_MONTHS]
    add("2. Retention & Churn", "Enterprise NRR change over the year", f"{enterprise[1] - enterprise[0]:+.1f} points",
        f"{_month_label(SUMMARY_MONTHS[1])} less {_month_label(SUMMARY_MONTHS[0])}")
    in_range = grid.loc[SUMMARY_PAYBACK_RANGES[0][0]:SUMMARY_PAYBACK_RANGES[0][1]]
    if 1 in grid.columns and len(in_range):
        add("2. Retention & Churn", f"Month 1 retention across cohorts {SUMMARY_PAYBACK_RANGES[0][0]} to {SUMMARY_PAYBACK_RANGES[0][1]} (low to high)",
            f"{in_range[1].min():.1f}% to {in_range[1].max():.1f}%", "cohort_retention_heatmap, column 1")
    blended = kpis["blended_unit_economics"]
    add("3. Unit Economics", "Mature customers, full dataset", f"{blended['mature_customers']:,.0f}", "unit_economics_blended")
    add("3. Unit Economics", "24-month LTV, full dataset", _money(blended["ltv_24m"]), "unit_economics_blended")
    add("3. Unit Economics", "Average CAC, full dataset", _money(blended["average_cac"]), "unit_economics_blended")
    add("3. Unit Economics", "Blended LTV:CAC, full dataset", _ratio_text(blended["ltv_to_cac_ratio"]), "unit_economics_blended")
    last_data_month = str(mrr.index.max())
    tracked_through = min(str(pd.Period(last, "M") + 23), last_data_month)
    add("3. Unit Economics", "Dec 2025 cohort is tracked through", _month_label(tracked_through),
        "cohort month + 23 lifetime months, or the last month in the data if that comes first")
    if blended["cohort_count"]:
        add("3. Unit Economics", "Cohorts behind the full-dataset figures above",
            f"{blended['first_cohort']} to {blended['last_cohort']} ({blended['cohort_count']} cohorts)",
            "unit_economics_blended")
    for m in ("2023-12", *SUMMARY_MONTHS):
        add("3. Unit Economics", f"CAC per new customer, {_month_label(m)} cohort", _money(_lookup(blended_cac, m)),
            "cac_blended sheet (total spend / total new customers)")
    channel_cac = kpis["cac_by_channel"]
    for m in SUMMARY_MONTHS:
        for channel in ["Ads", "Organic", "Referral"]:
            match = channel_cac[(channel_cac["cohort_month"] == m) & (channel_cac["channel"] == channel)]
            add("5. Recommended Next Steps", f"CAC per customer, {channel}, {_month_label(m)} cohort",
                _money(match["cac_per_customer_dollars"].iloc[0]) if len(match) else "n/a", "cac_by_channel sheet")
    low_segments = unit_table[unit_table["ltv_to_cac_ratio"] < 3]
    add("Executive Summary", "Segments below the 3x LTV:CAC floor", f"{len(low_segments)} of {len(unit_table)}",
        f"lowest is {unit_table.loc[unit_table['ltv_to_cac_ratio'].idxmin(), 'channel']} / "
        f"{unit_table.loc[unit_table['ltv_to_cac_ratio'].idxmin(), 'plan_tier']} at "
        f"{_ratio_text(unit_table['ltv_to_cac_ratio'].min())}")
    for start, end in SUMMARY_PAYBACK_RANGES:
        window = payback.loc[start:end, "payback_lifetime_month"].value_counts().sort_index()
        split = ", ".join(f"{int(count)} in month {int(month)}" for month, count in window.items())
        add("3. Unit Economics", f"Payback month, cohorts {start} to {end}", split, "count of cohorts by payback_lifetime_month")
    not_yet = payback[payback["payback_lifetime_month"].isna()].index.tolist()
    add("3. Unit Economics", "Cohorts with no payback yet", f"{len(not_yet)} ({', '.join(not_yet) if not_yet else 'none'})",
        "ltv_cac_payback rows with a blank payback month")
    frames["summary_prose_numbers"] = pd.DataFrame(prose)

    frames["summary_source_map"] = pd.DataFrame([
        {"file_named_in_summary": old, "now_in_sheet": new} for old, new in [
            ("total_mrr_by_month.csv", "total_mrr"), ("arr_by_month.csv", "arr"),
            ("arpu_by_month.csv", "arpu"), ("customer_counts_by_month.csv", "customer_counts"),
            ("mrr_movements.csv", "mrr_movements"), ("nrr_overall.csv", "nrr_all"),
            ("nrr_by_plan_tier.csv", "nrr_by_plan_tier"), ("nrr_by_channel.csv", "nrr_by_channel"),
            ("logo_churn_rate.csv", "customer_churn"), ("revenue_churn_rate.csv", "revenue_churn"),
            ("cohort_retention_grid.csv", "cohort_retention_heatmap"), ("ltv_cac_payback.csv", "ltv_cac_payback"),
            ("blended_cac_by_cohort.csv", "cac_blended"), ("cac_by_channel.csv", "cac_by_channel"),
            ("blended_unit_economics.csv", "unit_economics_blended"), ("unit_economics.csv", "unit_economics_table"),
        ]
    ])
    return frames


def write_summary_csvs(summary_frames, data_dir):
    folder = os.path.join(data_dir, "summary")
    os.makedirs(folder, exist_ok=True)
    for sheet, frame in summary_frames.items():
        frame.to_csv(os.path.join(folder, f"{sheet}.csv"), index=False)
    return len(summary_frames)


def write_window_csvs(frames_by_window, data_dir):
    """One folder per timeframe, one CSV per sheet. Returns the number of files written."""
    count = 0
    for slug, frames in frames_by_window.items():
        folder = os.path.join(data_dir, slug)
        os.makedirs(folder, exist_ok=True)
        for sheet, frame in frames.items():
            frame.to_csv(os.path.join(folder, f"{sheet}.csv"), index=False)
            count += 1
    return count


def write_workbook(frames_by_window, path, summary_frames=None):
    """All timeframes in ONE workbook. A contents sheet comes first. Every other sheet
    stacks the timeframes, with a timeframe column in front. Values only, no formulas."""
    from openpyxl.styles import Font, PatternFill

    stacked = {}
    for _key, sheet, *_ in EXPORT_SHEETS:
        parts = []
        for slug, frames in frames_by_window.items():
            part = frames[sheet].copy()
            part.insert(0, "timeframe", slug)
            parts.append(part)
        stacked[sheet] = pd.concat(parts, ignore_index=True)

    contents = pd.DataFrame([
        {"sheet": sheet, "tab": tab, "dashboard_card": card, "what_the_rows_are": description,
         "rows": len(stacked[sheet]), "timeframes": ", ".join(frames_by_window)}
        for _key, sheet, tab, card, description in EXPORT_SHEETS
    ])
    summary_frames = summary_frames or {}
    summary_contents = pd.DataFrame([
        {"sheet": sheet, "tab": "Summary report", "dashboard_card": section, "what_the_rows_are": table,
         "rows": len(summary_frames[sheet]), "timeframes": "full history"}
        for sheet, section, table in SUMMARY_SHEETS if sheet in summary_frames
    ])
    contents = pd.concat([summary_contents, contents], ignore_index=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in {"contents": contents, **summary_frames, **stacked}.items():
            frame.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes = "A2"
            for row in ws.iter_rows():
                for cell in row:
                    cell.font = Font(name="Arial", size=10, bold=(cell.row == 1))
                    if cell.row == 1:
                        cell.fill = PatternFill("solid", start_color="D9E1F2")
            for column_cells in ws.columns:
                longest = max(len(str(c.value)) if c.value is not None else 0 for c in column_cells[:200])
                ws.column_dimensions[column_cells[0].column_letter].width = min(max(longest + 2, 8), 60)
    return path


def main():
    parser = argparse.ArgumentParser(description="Build the standalone SaaS Plotly dashboard, one HTML file per timeframe.")
    parser.add_argument("--exports-dir", default="csv_exports",
                        help="folder with the dbt export CSV files (default: csv_exports). "
                             "Files are also looked up in its reporting/ subfolder.")
    parser.add_argument("--output-dir", default="docs",
                        help="folder for every HTML file (default: docs). The 'All' page is index.html.")
    parser.add_argument("--data-dir", default="dashboard_data",
                        help="folder for the workbook and the per-timeframe CSV files (default: dashboard_data).")
    parser.add_argument("--only", nargs="+", metavar="SLUG",
                        help="build only these timeframes, e.g. --only all 2022-2023 (default: every option)")
    parser.add_argument("--plotly", choices=["inline", "external"], default="inline",
                        help="inline: plotly.js inside every file. external: one shared plotly.min.js file.")
    parser.add_argument("--as-of", default=AS_OF_MONTH, metavar="YYYY-MM",
                        help="last month that has happened. Later rows are dropped. 'none' keeps every month. "
                             f"(default: {AS_OF_MONTH})")
    args = parser.parse_args()

    valid_slugs = [option[0] for option in TIMEFRAME_OPTIONS]
    if args.only:
        chosen, chosen_source = args.only, "--only"
    elif TIMEFRAMES_TO_BUILD:
        chosen, chosen_source = TIMEFRAMES_TO_BUILD, "TIMEFRAMES_TO_BUILD"
    else:
        chosen, chosen_source = valid_slugs, "default (every option)"
    print(f"Timeframes to build, from {chosen_source}: {chosen}")
    unknown = [slug for slug in chosen if slug not in valid_slugs]
    if unknown:
        parser.error(f"unknown timeframe(s) {unknown}. Choose from: {valid_slugs}")

    exports = load_exports(args.exports_dir)
    as_of = None if str(args.as_of).lower() == "none" else args.as_of
    if as_of:
        rows_before = len(exports["cohort"]) + len(exports["monthly"])
        exports = cut_to_as_of_month(exports, as_of)
        rows_after = len(exports["cohort"]) + len(exports["monthly"])
        print(f"Data cut at {as_of}: kept {rows_after:,} of {rows_before:,} cohort and monthly rows.")
    kpis = build_all_kpis(exports)  # done once for every file

    # A timeframe that starts after the last month on record has nothing to draw.
    last_year = int(str(exports["last_month"])[:4])
    empty_slugs = [o[0] for o in TIMEFRAME_OPTIONS if o[0] in chosen and o[2] is not None and o[2] > last_year]
    if empty_slugs:
        print(f"Skipping timeframes with no months up to {exports['last_month']}: {empty_slugs}")
        chosen = [slug for slug in chosen if slug not in empty_slugs]
    kpis = add_movement_percentages(kpis)  # % of prior-month MRR for the MRR Movements hover

    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)
    if args.plotly == "external":
        with open(os.path.join(out_dir, "plotly.min.js"), "w", encoding="utf-8") as f:
            f.write(pyo.get_plotlyjs())

    frames_by_window = {}
    for option in TIMEFRAME_OPTIONS:
        if option[0] not in chosen:
            continue
        path = os.path.join(out_dir, timeframe_filename(option[0]))
        sink = {}
        html = build_dashboard_html(kpis, option, args.plotly, chosen, export_sink=sink)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {path} ({len(html) / 1e6:.1f} MB)")
        frames_by_window[option[0]] = tidy_window_frames(sink["window_kpis"], sink["cards"])

    data_dir = os.path.abspath(args.data_dir)
    csv_count = write_window_csvs(frames_by_window, data_dir)
    summary_frames = build_summary_tables(kpis)
    summary_count = write_summary_csvs(summary_frames, data_dir)
    workbook_path = write_workbook(frames_by_window, os.path.join(data_dir, WORKBOOK_NAME), summary_frames)
    print(f"Wrote {summary_count} summary report tables in {os.path.join(data_dir, 'summary')}")
    print(f"Wrote {csv_count} CSV files in {data_dir}, one folder per timeframe")
    print(f"Wrote {workbook_path}")

    # Pages from earlier runs are not touched. They keep their old buttons.
    built_names = {timeframe_filename(o[0]) for o in TIMEFRAME_OPTIONS if o[0] in chosen}
    old_pages = sorted(
        name for name in os.listdir(out_dir)
        if name.endswith(".html") and name not in built_names
        and (name == HOME_FILENAME or name.startswith(WINDOW_FILE_PREFIX + "_"))
    )
    if old_pages:
        print(f"Note: these pages in {out_dir} are from an earlier run and were NOT rebuilt. "
              f"They still show their old buttons. Delete them or rebuild them: {old_pages}")


if __name__ == "__main__":
    main()

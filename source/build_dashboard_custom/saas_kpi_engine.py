"""
saas_kpi_engine.py

Reframed from saas_validation_v5d.ipynb. This module only computes numbers.
It takes the two raw CSVs the generator script produces and returns clean
DataFrames and Series, one function per KPI. Nothing here draws a chart or
writes a file -- that split belongs in build_dashboard.py.

Expected input schema (saas_generation_v9_2.py output)
------------------------------------------------------
The engine reads only the columns listed here. Extra columns are ignored.

customer_month_panel_df: one row per customer per active calendar month
    customer_id             str, e.g. "2022-01_Ads_Basic_00000"
    calendar_month          str, "YYYY-MM"
    cohort_month            str, "YYYY-MM" (the customer's signup month)
    lifetime_month          int, 0 at signup, +1 per calendar month since
    mrr                     float
    channel                 str: "Ads" / "Organic" / "Referral"
    plan_tier               str: "Basic" / "Pro" / "Enterprise"
    customer_clv_24m        float, MRR summed over lifetime_month 0-23.
                            Repeated on every row of the same customer.
    customer_cac            float, CAC paid for this customer's segment and cohort
    unit_clv_cac_ratio_24m  float, customer_clv_24m / customer_cac
    is_mature_24m           bool, True when the cohort has 24+ months observed.
                            Unit economics filters on this, never on whether
                            the customer survived.

cost_per_customer_df: one row per cohort_month x channel x plan_tier
    cohort_month                    str, "YYYY-MM"
    channel                         str
    plan_tier                       str
    cac_per_customer_dollars        float
    total_acquisition_cost_dollars  float
    new_customers                   int
"""

import numpy as np
import pandas as pd

# LTV is measured over the first 24 lifetime months (lifetime_month 0 to 23).
# Keep in sync with CLV_HORIZON_MONTHS in the generator's calibration config.
CLV_HORIZON_MONTHS = 24


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_data(panel_csv_path, cost_csv_path):
    """Read the two generator outputs. Fails loudly if a required column is missing."""
    panel_df = pd.read_csv(panel_csv_path)
    cost_df = pd.read_csv(cost_csv_path)

    required_panel_columns = {
        "customer_id", "calendar_month", "cohort_month",
        "lifetime_month", "mrr", "channel", "plan_tier",
        "customer_clv_24m", "customer_cac", "unit_clv_cac_ratio_24m", "is_mature_24m",
    }
    required_cost_columns = {
        "cohort_month", "channel", "plan_tier",
        "cac_per_customer_dollars", "total_acquisition_cost_dollars", "new_customers",
    }
    missing_panel = required_panel_columns - set(panel_df.columns)
    missing_cost = required_cost_columns - set(cost_df.columns)
    if missing_panel:
        raise ValueError(f"customer_month_panel_df is missing columns: {sorted(missing_panel)}")
    if missing_cost:
        raise ValueError(f"cost_per_customer_df is missing columns: {sorted(missing_cost)}")

    return panel_df, cost_df


def cut_to_as_of_month(panel_df, cost_df, as_of_month):
    """
    Treat the data as if the world ended at as_of_month ("YYYY-MM"), for example "2025-12".
    Rows after that month are dropped. So are cost rows for cohorts that sign up after it.

    The CLV columns written by the generator were summed over the full simulated history,
    so they would still include revenue from after the cut. They are recomputed here from the
    months that remain:
      customer_clv_24m        MRR over lifetime months 0 to 23, using only months up to the cut
      is_mature_24m           True when the cohort has 24 or more months observed by the cut
      unit_clv_cac_ratio_24m  customer_clv_24m / customer_cac
    CAC is a one-time charge and is left as it is.
    """
    panel = panel_df[panel_df["calendar_month"] <= as_of_month].copy()
    cost = cost_df[cost_df["cohort_month"] <= as_of_month].copy()

    in_horizon = panel["lifetime_month"] < CLV_HORIZON_MONTHS
    panel["customer_clv_24m"] = (
        panel["mrr"].where(in_horizon, 0).groupby(panel["customer_id"]).transform("sum")
    )
    month_numbers = {m: _month_number(m) for m in panel["cohort_month"].unique()}
    months_observed = _month_number(as_of_month) - panel["cohort_month"].map(month_numbers) + 1
    panel["is_mature_24m"] = months_observed >= CLV_HORIZON_MONTHS
    panel["unit_clv_cac_ratio_24m"] = panel["customer_clv_24m"] / panel["customer_cac"].replace(0, np.nan)
    return panel, cost


# ---------------------------------------------------------------------------
# Shared ledger: month-over-month MRR delta per customer, categorized.
# MRR Movements, Revenue Churn Rate, and Active/New/Churned counts all read
# from this same ledger instead of each rebuilding their own reindex.
# ---------------------------------------------------------------------------

def build_customer_movements_ledger(panel_df):
    """
    Reindex every customer across every calendar month (filling gaps with
    $0 MRR), then tag each customer-month row with a movement_type:
    New Business, Expansion, Contraction, Churn, or No Change.

    Returns
    -------
    pandas.DataFrame with columns: customer_id, calendar_month, mrr,
        prev_mrr, mrr_delta, movement_type
    """
    all_customers = panel_df["customer_id"].unique()
    all_months = panel_df["calendar_month"].unique()
    full_index = pd.MultiIndex.from_product(
        [all_customers, all_months], names=["customer_id", "calendar_month"]
    )

    # Merge rather than reindex-with-fill_value=0: a mixed-dtype frame (mrr is
    # numeric, channel/plan_tier are strings) can't share one fill value, so
    # we only need to backfill the numeric mrr column here. mrr = 0 on a row
    # correctly means "not an active customer that month" for the movement
    # categorization below.
    ledger = pd.DataFrame(index=full_index).reset_index()
    ledger = ledger.merge(
        panel_df[["customer_id", "calendar_month", "mrr"]],
        on=["customer_id", "calendar_month"],
        how="left",
    )
    ledger["mrr"] = ledger["mrr"].fillna(0)
    ledger = ledger.sort_values(["customer_id", "calendar_month"])

    ledger["prev_mrr"] = ledger.groupby("customer_id")["mrr"].shift(1).fillna(0)
    ledger["mrr_delta"] = ledger["mrr"] - ledger["prev_mrr"]

    conditions = [
        (ledger["prev_mrr"] == 0) & (ledger["mrr"] > 0),
        (ledger["prev_mrr"] > 0) & (ledger["mrr"] > ledger["prev_mrr"]),
        (ledger["prev_mrr"] > 0) & (ledger["mrr"] < ledger["prev_mrr"]) & (ledger["mrr"] > 0),
        (ledger["prev_mrr"] > 0) & (ledger["mrr"] == 0),
    ]
    categories = ["New Business", "Expansion", "Contraction", "Churn"]
    ledger["movement_type"] = np.select(conditions, categories, default="No Change")

    return ledger


# ---------------------------------------------------------------------------
# Revenue tab
# ---------------------------------------------------------------------------

def compute_total_mrr_by_month(panel_df):
    """Series indexed by calendar_month, total MRR across all customers."""
    return panel_df.groupby("calendar_month")["mrr"].sum().sort_index()


def compute_arr_by_month(total_mrr_by_month_series):
    """ARR run-rate = MRR x 12. Same shape as compute_total_mrr_by_month's output."""
    return (total_mrr_by_month_series * 12).rename("arr_run_rate")


def compute_mrr_movements(ledger_df):
    """
    Monthly grid: New Business / Expansion / Contraction / Churn dollar
    totals, plus Net MRR Growth (their sum).
    """
    categories = ["New Business", "Expansion", "Contraction", "Churn"]
    monthly = (
        ledger_df.groupby(["calendar_month", "movement_type"])["mrr_delta"]
        .sum()
        .unstack(fill_value=0)
    )
    for category in categories:
        if category not in monthly.columns:
            monthly[category] = 0.0
    monthly = monthly[categories].reset_index().sort_values("calendar_month")
    monthly["Net MRR Growth"] = monthly[categories].sum(axis=1)
    return monthly


def compute_arpu_by_month(panel_df):
    """Total MRR / count of customers with mrr > 0, per calendar month."""
    active_counts = (
        panel_df[panel_df["mrr"] > 0]
        .groupby("calendar_month")["customer_id"]
        .nunique()
    )
    total_mrr = panel_df.groupby("calendar_month")["mrr"].sum()

    arpu_df = pd.DataFrame({
        "calendar_month": total_mrr.index,
        "total_mrr": total_mrr.values,
        "active_customers": active_counts.reindex(total_mrr.index, fill_value=0).values,
    })
    arpu_df["arpu"] = arpu_df["total_mrr"] / arpu_df["active_customers"]
    return arpu_df.sort_values("calendar_month")


def compute_revenue_churn_rate(ledger_df, total_mrr_by_month_series):
    """
    |Churned MRR this month| / total MRR the prior month, as a percentage.
    Dollar-weighted, distinct from logo churn.
    """
    churned_mrr_by_month = (
        ledger_df[ledger_df["movement_type"] == "Churn"]
        .groupby("calendar_month")["prev_mrr"]
        .sum()
    )
    starting_mrr_by_month = total_mrr_by_month_series.shift(1)

    revenue_churn_df = pd.DataFrame({
        "calendar_month": total_mrr_by_month_series.index,
        "starting_mrr": starting_mrr_by_month.values,
        "churned_mrr": churned_mrr_by_month.reindex(total_mrr_by_month_series.index, fill_value=0).values,
    })
    revenue_churn_df["revenue_churn_rate_pct"] = (
        revenue_churn_df["churned_mrr"] / revenue_churn_df["starting_mrr"] * 100
    )
    return revenue_churn_df.sort_values("calendar_month")


def compute_nrr_by_month(customer_month_panel_df):
    """
    Blended monthly NRR. Compares the SAME customers active in month M-1
    against their combined MRR in month M. New signups in month M are
    excluded from both sides, so this isolates expansion/contraction/churn.
    """
    mrr_by_customer_month = customer_month_panel_df.pivot_table(
        index="customer_id", columns="calendar_month", values="mrr", aggfunc="sum"
    )
    sorted_months = sorted(mrr_by_customer_month.columns)

    nrr_lookup = {}
    for i in range(1, len(sorted_months)):
        prev_month, curr_month = sorted_months[i - 1], sorted_months[i]
        cohort_customers = mrr_by_customer_month[prev_month].dropna().index
        starting_mrr = mrr_by_customer_month.loc[cohort_customers, prev_month].sum()
        retained_mrr = mrr_by_customer_month.loc[cohort_customers, curr_month].fillna(0).sum()
        nrr_lookup[curr_month] = (retained_mrr / starting_mrr) * 100

    nrr_series = pd.Series(nrr_lookup).sort_index()
    nrr_series.index.name = "calendar_month"
    nrr_series.name = "nrr_percentage"
    return nrr_series


def compute_nrr_by_segment(customer_month_panel_df, group_column_name):
    """Long-form NRR: one row per (calendar_month, segment value). group_column_name is 'channel' or 'plan_tier'."""
    rows = []
    for segment_value in sorted(customer_month_panel_df[group_column_name].unique()):
        segment_df = customer_month_panel_df[customer_month_panel_df[group_column_name] == segment_value]
        segment_nrr = compute_nrr_by_month(segment_df)
        for month, value in segment_nrr.items():
            rows.append({"calendar_month": month, group_column_name: segment_value, "nrr_percentage": value})
    return pd.DataFrame(rows)


def compute_retention_grid(panel_df, group_column_name=None, group_value=None):
    """
    Cohort-month x lifetime-month grid of % of customers retained, relative
    to each cohort's month-0 headcount. Pass group_column_name + group_value
    to slice to one channel or plan tier first; omit both for the blended view.
    """
    working_df = panel_df
    if group_column_name is not None:
        working_df = working_df[working_df[group_column_name] == group_value]

    counts = (
        working_df.groupby(["cohort_month", "lifetime_month"])["customer_id"]
        .nunique()
        .reset_index(name="active_customer_count")
    )
    initial_counts = (
        counts[counts["lifetime_month"] == 0]
        .set_index("cohort_month")["active_customer_count"]
    )
    counts["initial_customer_count"] = counts["cohort_month"].map(initial_counts)
    counts["retention_percentage"] = counts["active_customer_count"] / counts["initial_customer_count"] * 100

    grid = counts.pivot(index="cohort_month", columns="lifetime_month", values="retention_percentage")
    return grid.sort_index()


def compute_mrr_retention_grid(panel_df):
    """
    Cohort-month x lifetime-month grid of % of MRR retained, relative to
    each cohort's month-0 total bill. Blended across every segment. Values
    above 100% are expected -- upsell revenue lifting the cohort past its
    starting bill.
    """
    mrr_by_cohort_lifetime = (
        panel_df.groupby(["cohort_month", "lifetime_month"])["mrr"]
        .sum()
        .reset_index(name="total_mrr")
    )
    initial_mrr = (
        mrr_by_cohort_lifetime[mrr_by_cohort_lifetime["lifetime_month"] == 0]
        .set_index("cohort_month")["total_mrr"]
    )
    mrr_by_cohort_lifetime["initial_mrr"] = mrr_by_cohort_lifetime["cohort_month"].map(initial_mrr)
    mrr_by_cohort_lifetime["mrr_retention_percentage"] = (
        mrr_by_cohort_lifetime["total_mrr"] / mrr_by_cohort_lifetime["initial_mrr"] * 100
    )
    grid = mrr_by_cohort_lifetime.pivot(
        index="cohort_month", columns="lifetime_month", values="mrr_retention_percentage"
    )
    return grid.sort_index()


# ---------------------------------------------------------------------------
# Customer tab
# ---------------------------------------------------------------------------

def compute_customer_counts_by_month(ledger_df):
    """Active / new / churned customer counts per calendar month, from the shared ledger."""
    counts = ledger_df.groupby("calendar_month").agg(
        active_customers=("mrr", lambda col: (col > 0).sum()),
        new_customers=("movement_type", lambda col: (col == "New Business").sum()),
        churned_customers=("movement_type", lambda col: (col == "Churn").sum()),
    ).reset_index()
    return counts.sort_values("calendar_month")


def compute_logo_churn_rate(panel_df):
    """
    Monthly logo churn rate: customers active in M-1 but absent in M,
    divided by customers active in M-1. New signups in M don't enter the
    denominator, since churn only applies to an existing base.
    """
    active_ids_by_month = panel_df.groupby("calendar_month")["customer_id"].apply(set)
    sorted_months = sorted(active_ids_by_month.index)

    rows = []
    for i in range(1, len(sorted_months)):
        prev_month, curr_month = sorted_months[i - 1], sorted_months[i]
        prev_ids = active_ids_by_month[prev_month]
        curr_ids = active_ids_by_month[curr_month]
        churned = len(prev_ids - curr_ids)
        starting = len(prev_ids)
        rows.append({
            "calendar_month": curr_month,
            "customers_at_start": starting,
            "customers_churned": churned,
            "churn_rate_percentage": churned / starting * 100,
        })
    return pd.DataFrame(rows)


def _as_bool(column):
    """CSV booleans normally load as bool. This also handles the strings 'True' / 'False'."""
    if column.dtype == bool:
        return column
    return column.astype(str).str.strip().str.lower().eq("true")


def _month_number(month_string):
    """'2023-05' -> a running month count, so two months can be subtracted."""
    year, month = str(month_string).split("-")[:2]
    return int(year) * 12 + int(month)


def _customer_weighted_cac(cost_df, group_columns):
    """
    Total acquisition spend / total new customers for each group. A cohort with
    300 signups counts 300 times as much as a cohort with 1. This is the same
    CAC the payback table starts from.
    """
    totals = cost_df.groupby(group_columns)[
        ["total_acquisition_cost_dollars", "new_customers"]
    ].sum()
    cac = totals["total_acquisition_cost_dollars"] / totals["new_customers"].replace(0, np.nan)
    return cac.rename("cac_per_customer_dollars")


def compute_cac_by_channel(cost_df):
    """Customer-weighted CAC per cohort_month x channel (all plan tiers together), long form for a multi-line chart."""
    return (
        _customer_weighted_cac(cost_df, ["cohort_month", "channel"])
        .reset_index()
        .sort_values(["channel", "cohort_month"])
    )


def compute_blended_cac_by_cohort(cost_df):
    """
    Series indexed by cohort_month: total acquisition spend / total new customers
    across every channel and plan tier. One definition, used by the CAC card and
    by the payback table, so the two always agree.
    """
    return _customer_weighted_cac(cost_df, "cohort_month").rename("blended_cac_dollars").sort_index()


def _mature_customers(panel_df):
    """One row per customer, only for cohorts observed for the full 24 months."""
    mature_rows = panel_df[_as_bool(panel_df["is_mature_24m"])]
    return mature_rows.drop_duplicates("customer_id")


def compute_unit_economics(panel_df):
    """
    24-month LTV, CAC, and LTV:CAC ratio by channel x plan tier.

    Only customers in mature cohorts count (is_mature_24m), so every customer
    has had the same 24 months to earn revenue. LTV is customer_clv_24m and CAC
    is customer_cac, both written by the generator. Each customer counts once,
    so a segment's averages are customer-weighted.

    ltv_to_cac_ratio is ltv_24m / average_cac, so the three columns reconcile.
    mean_customer_ratio is the average of the generator's own per-customer
    unit_clv_cac_ratio_24m, kept as a cross-check. The two should be very close.
    """
    customers = _mature_customers(panel_df)
    unit_economics = (
        customers.groupby(["channel", "plan_tier"])
        .agg(
            mature_customers=("customer_id", "nunique"),
            ltv_24m=("customer_clv_24m", "mean"),
            average_cac=("customer_cac", "mean"),
            mean_customer_ratio=("unit_clv_cac_ratio_24m", "mean"),
        )
        .reset_index()
    )
    unit_economics["ltv_to_cac_ratio"] = unit_economics["ltv_24m"] / unit_economics["average_cac"]
    return unit_economics.sort_values(["channel", "plan_tier"])


def compute_blended_unit_economics(panel_df):
    """
    One 24-month LTV:CAC for all mature customers together. Every customer counts
    once, so big segments weigh more than small ones. Returns a dict.

    first_cohort, last_cohort and cohort_count say which signup cohorts the
    mature customers come from.
    """
    customers = _mature_customers(panel_df)
    if customers.empty:
        return {"mature_customers": 0, "first_cohort": None, "last_cohort": None, "cohort_count": 0,
                "ltv_24m": np.nan, "average_cac": np.nan, "ltv_to_cac_ratio": np.nan}
    ltv = customers["customer_clv_24m"].mean()
    cac = customers["customer_cac"].mean()
    return {
        "mature_customers": int(len(customers)),
        "first_cohort": customers["cohort_month"].min(),
        "last_cohort": customers["cohort_month"].max(),
        "cohort_count": int(customers["cohort_month"].nunique()),
        "ltv_24m": ltv,
        "average_cac": cac,
        "ltv_to_cac_ratio": ltv / cac,
    }


def compute_ltv_cac_payback(panel_df, cost_df):
    """
    For each cohort, the earliest lifetime_month where cumulative average
    revenue per customer crosses the cohort's CAC (ratio >= 1), looking only
    inside the first 24 lifetime months. Reduces the full cohort x
    lifetime-month ratio grid down to one row per cohort for a table.

    latest_ratio is the ratio at the last month inside that 24-month window
    that the cohort has actually lived through. For mature cohorts that is the
    full 24-month LTV:CAC. For younger cohorts it is a to-date figure, flagged
    by is_mature_24m = False.
    """
    cohort_sizes = (
        panel_df[panel_df["lifetime_month"] == 0]
        .groupby("cohort_month")["customer_id"]
        .nunique()
    )
    within_horizon = panel_df[panel_df["lifetime_month"] < CLV_HORIZON_MONTHS]
    mrr_grid = within_horizon.groupby(["cohort_month", "lifetime_month"])["mrr"].sum().unstack(fill_value=0)
    avg_mrr_grid = mrr_grid.div(cohort_sizes, axis=0)
    cumulative_ltv_grid = avg_mrr_grid.cumsum(axis=1)

    # Mask cells a cohort has not lived through yet. The months a cohort has been
    # observed come from its distance to the last calendar month in the data.
    last_month_number = _month_number(panel_df["calendar_month"].max())
    for cohort in cumulative_ltv_grid.index:
        months_observed = last_month_number - _month_number(cohort)
        cumulative_ltv_grid.loc[cohort, cumulative_ltv_grid.columns > months_observed] = np.nan

    cohort_cac = compute_blended_cac_by_cohort(cost_df).reindex(cumulative_ltv_grid.index)
    cohort_maturity = _as_bool(panel_df["is_mature_24m"]).groupby(panel_df["cohort_month"]).first()

    ratio_grid = cumulative_ltv_grid.div(cohort_cac, axis=0)

    rows = []
    for cohort in ratio_grid.index:
        row = ratio_grid.loc[cohort].dropna()
        crossed = row[row >= 1]
        payback_month = int(crossed.index.min()) if len(crossed) else None
        latest_observed_month = int(row.index.max()) if len(row) else None
        latest_ratio = row.iloc[-1] if len(row) else np.nan
        rows.append({
            "cohort_month": cohort,
            "starting_cac": cohort_cac.get(cohort, np.nan),
            "payback_lifetime_month": payback_month,
            "latest_observed_month": latest_observed_month,
            "latest_ratio": latest_ratio,
            "is_mature_24m": bool(cohort_maturity.get(cohort, False)),
        })
    return pd.DataFrame(rows).sort_values("cohort_month")


# ---------------------------------------------------------------------------
# One call, everything the dashboard needs
# ---------------------------------------------------------------------------

def build_all_kpis(panel_df, cost_df):
    """
    Run every computation once and hand back a flat dict of DataFrames /
    Series, keyed by name. build_dashboard.py reads from this dict only --
    it never touches panel_df or cost_df directly.
    """
    ledger_df = build_customer_movements_ledger(panel_df)
    total_mrr_by_month = compute_total_mrr_by_month(panel_df)

    return {
        # Revenue tab
        "total_mrr_by_month": total_mrr_by_month,
        "arr_by_month": compute_arr_by_month(total_mrr_by_month),
        "mrr_movements": compute_mrr_movements(ledger_df),
        "arpu_by_month": compute_arpu_by_month(panel_df),
        "revenue_churn_rate": compute_revenue_churn_rate(ledger_df, total_mrr_by_month),
        "nrr_overall": compute_nrr_by_month(panel_df),
        "nrr_by_channel": compute_nrr_by_segment(panel_df, "channel"),
        "nrr_by_plan_tier": compute_nrr_by_segment(panel_df, "plan_tier"),
        "mrr_retention_grid": compute_mrr_retention_grid(panel_df),

        # Customer tab
        "customer_counts_by_month": compute_customer_counts_by_month(ledger_df),
        "logo_churn_rate": compute_logo_churn_rate(panel_df),
        "cac_by_channel": compute_cac_by_channel(cost_df),
        "blended_cac_by_cohort": compute_blended_cac_by_cohort(cost_df),
        "cohort_retention_grid": compute_retention_grid(panel_df),
        "retention_grid_by_channel": {
            channel: compute_retention_grid(panel_df, "channel", channel)
            for channel in sorted(panel_df["channel"].unique())
        },
        "retention_grid_by_plan_tier": {
            plan_tier: compute_retention_grid(panel_df, "plan_tier", plan_tier)
            for plan_tier in sorted(panel_df["plan_tier"].unique())
        },
        "unit_economics": compute_unit_economics(panel_df),
        "blended_unit_economics": compute_blended_unit_economics(panel_df),
        "ltv_cac_payback": compute_ltv_cac_payback(panel_df, cost_df),
    }

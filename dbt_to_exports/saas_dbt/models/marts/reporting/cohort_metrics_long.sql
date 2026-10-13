-- Standard shape for the reporting engine's generic cohort heatmap/line
-- component: cohort_month, segment_type, segment_value, period, metric_name,
-- metric_value. One table covers retention, MRR grid, avg MRR, cumulative
-- LTV, LTV:CAC, and MRR retention -- the engine filters by metric_name
-- instead of the data_provider picking a different file per chart.

with retention_counts as (
    select
        segment_type, segment_value, cohort_month, lifetime_month as period,
        'active_customers' as metric_name, active_customer_count::double as metric_value
    from {{ ref('int_retention_base') }}
),

retention_rate as (
    select
        segment_type, segment_value, cohort_month, lifetime_month as period,
        'retention_rate' as metric_name, retention_percentage as metric_value
    from {{ ref('int_retention_percentage') }}
),

mrr_total as (
    select
        'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month as period,
        'mrr_total' as metric_name, sum(mrr) as metric_value
    from {{ ref('stg_revenue') }}
    group by cohort_month, lifetime_month
),

avg_mrr as (
    select
        'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month as period,
        'avg_mrr' as metric_name, avg_mrr as metric_value
    from {{ ref('int_avg_mrr') }}
),

cumulative_ltv as (
    select
        'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month as period,
        'cumulative_ltv' as metric_name, cumulative_ltv as metric_value
    from {{ ref('int_cumulative_ltv') }}
),

ltv_cac_ratio as (
    select
        'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month as period,
        'ltv_cac_ratio' as metric_name, ltv_cac_ratio as metric_value
    from {{ ref('int_ltv_cac_ratio') }}
),

mrr_retention_rate as (
    select
        'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month as period,
        'mrr_retention_rate' as metric_name, mrr_retention_percentage as metric_value
    from {{ ref('int_mrr_retention_percentage') }}
)

select * from retention_counts
union all select * from retention_rate
union all select * from mrr_total
union all select * from avg_mrr
union all select * from cumulative_ltv
union all select * from ltv_cac_ratio
union all select * from mrr_retention_rate

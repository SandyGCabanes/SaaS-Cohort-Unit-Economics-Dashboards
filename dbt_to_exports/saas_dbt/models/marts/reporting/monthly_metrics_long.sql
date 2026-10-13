-- Standard shape for the reporting engine's line/bar chart component:
-- segment_type, segment_value, calendar_month (period), metric_name,
-- metric_value. Blended (segment_type='all') for now; extend with
-- channel/plan_tier cuts the same way cohort_metrics_long does, if the
-- dashboard needs a segmented trend line later.

with total_mrr as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'total_mrr' as metric_name, sum(mrr) as metric_value
    from {{ ref('stg_revenue') }}
    group by calendar_month
),

arpu as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'arpu' as metric_name, arpu as metric_value
    from {{ ref('arpu_by_month') }}
),

active_customers as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'active_customers' as metric_name, active_customers::double as metric_value
    from {{ ref('customer_counts_by_month') }}
),

new_customers as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'new_customers' as metric_name, new_customers::double as metric_value
    from {{ ref('customer_counts_by_month') }}
),

churned_customers as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'churned_customers' as metric_name, churned_customers::double as metric_value
    from {{ ref('customer_counts_by_month') }}
),

logo_churn_rate as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'logo_churn_rate_pct' as metric_name, churn_rate_percentage as metric_value
    from {{ ref('churn_rate_by_month') }}
),

revenue_churn_rate as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month,
           'revenue_churn_rate_pct' as metric_name, revenue_churn_rate_pct as metric_value
    from {{ ref('revenue_churn_rate_by_month') }}
)

select * from total_mrr
union all select * from arpu
union all select * from active_customers
union all select * from new_customers
union all select * from churned_customers
union all select * from logo_churn_rate
union all select * from revenue_churn_rate

with churned as (
    select calendar_month, sum(prev_mrr) as churned_mrr
    from {{ ref('customer_level_movements_mrr') }}
    where movement_type = 'Churn'
    group by calendar_month
),

total_by_month as (
    select calendar_month, sum(mrr) as total_mrr
    from {{ ref('stg_revenue') }}
    group by calendar_month
),

starting as (
    select calendar_month, lag(total_mrr) over (order by calendar_month) as starting_mrr
    from total_by_month
)

select
    t.calendar_month,
    s.starting_mrr,
    coalesce(c.churned_mrr, 0) as churned_mrr,
    coalesce(c.churned_mrr, 0) / s.starting_mrr * 100 as revenue_churn_rate_pct
from total_by_month t
join starting s using (calendar_month)
left join churned c using (calendar_month)
order by t.calendar_month

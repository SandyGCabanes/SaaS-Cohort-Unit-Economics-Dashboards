with active as (
    select calendar_month, count(distinct customer_id) as active_customers
    from {{ ref('stg_revenue') }}
    where mrr > 0
    group by calendar_month
),

total as (
    select calendar_month, sum(mrr) as total_mrr
    from {{ ref('stg_revenue') }}
    group by calendar_month
)

select
    t.calendar_month,
    t.total_mrr,
    coalesce(a.active_customers, 0) as active_customers,
    t.total_mrr / coalesce(a.active_customers, 0) as arpu
from total t
left join active a using (calendar_month)
order by t.calendar_month

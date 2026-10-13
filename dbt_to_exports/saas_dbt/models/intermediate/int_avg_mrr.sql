with mrr_by_cohort_lifetime as (
    select cohort_month, lifetime_month, sum(mrr) as total_mrr
    from {{ ref('stg_revenue') }}
    group by cohort_month, lifetime_month
),

cohort_sizes as (
    select cohort_month, count(distinct customer_id) as cohort_size
    from {{ ref('stg_revenue') }}
    where lifetime_month = 0
    group by cohort_month
)

select
    m.cohort_month,
    m.lifetime_month,
    m.total_mrr / c.cohort_size as avg_mrr
from mrr_by_cohort_lifetime m
join cohort_sizes c using (cohort_month)

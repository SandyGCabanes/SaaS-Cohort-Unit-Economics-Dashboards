with mrr_by_cohort_lifetime as (
    select cohort_month, lifetime_month, sum(mrr) as total_mrr
    from {{ ref('stg_revenue') }}
    group by cohort_month, lifetime_month
),

initial as (
    select cohort_month, total_mrr as initial_mrr
    from mrr_by_cohort_lifetime
    where lifetime_month = 0
)

select
    m.cohort_month,
    m.lifetime_month,
    m.total_mrr,
    i.initial_mrr,
    m.total_mrr / i.initial_mrr * 100 as mrr_retention_percentage
from mrr_by_cohort_lifetime m
join initial i using (cohort_month)

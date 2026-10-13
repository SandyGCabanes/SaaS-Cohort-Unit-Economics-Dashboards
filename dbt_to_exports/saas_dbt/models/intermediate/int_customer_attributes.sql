-- channel, plan_tier, cohort_month are fixed per customer for the life of
-- the account. min() just collapses the group deterministically.

select
    customer_id,
    min(channel)      as channel,
    min(plan_tier)    as plan_tier,
    min(cohort_month) as cohort_month
from {{ ref('stg_revenue') }}
group by customer_id

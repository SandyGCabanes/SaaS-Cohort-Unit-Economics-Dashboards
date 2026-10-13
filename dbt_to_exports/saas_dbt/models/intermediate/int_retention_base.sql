-- Built from stg_revenue directly (real active rows only), not the
-- reindexed spine -- churn is defined by absence, and reindexing would
-- double count zero-mrr rows as "active".

with base as (
    select customer_id, channel, plan_tier, cohort_month, lifetime_month
    from {{ ref('stg_revenue') }}
)

select 'all' as segment_type, 'all' as segment_value, cohort_month, lifetime_month,
       count(distinct customer_id) as active_customer_count
from base
group by cohort_month, lifetime_month

union all

select 'channel' as segment_type, channel as segment_value, cohort_month, lifetime_month,
       count(distinct customer_id) as active_customer_count
from base
group by channel, cohort_month, lifetime_month

union all

select 'plan_tier' as segment_type, plan_tier as segment_value, cohort_month, lifetime_month,
       count(distinct customer_id) as active_customer_count
from base
group by plan_tier, cohort_month, lifetime_month

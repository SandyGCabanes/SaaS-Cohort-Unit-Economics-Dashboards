-- Every customer x every calendar_month in the dataset, missing months
-- filled with mrr = 0. This is the ~98k-row expanded grid the movement
-- deltas are calculated from.

select
    s.customer_id,
    s.channel,
    s.plan_tier,
    s.cohort_month,
    s.calendar_month,
    date_diff(
        'month',
        cast(s.cohort_month || '-01' as date),
        cast(s.calendar_month || '-01' as date)
    )                                    as lifetime_month,
    coalesce(r.mrr, 0)                   as mrr,
    coalesce(r.mrr, 0) > 0               as is_active,
    c.customer_clv_24m,
    c.customer_cac,
    c.unit_clv_cac_ratio_24m,
    c.is_mature_24m
from {{ ref('int_customer_calendar_spine') }} s
left join {{ ref('stg_revenue') }} r
  on r.customer_id = s.customer_id and r.calendar_month = s.calendar_month
left join {{ ref('int_customer_clv_24m') }} c
  on c.customer_id = s.customer_id

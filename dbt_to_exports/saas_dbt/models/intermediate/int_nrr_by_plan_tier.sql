with distinct_months as (
    select distinct plan_tier, calendar_month from {{ ref('stg_revenue') }}
),

month_pairs as (
    select
        plan_tier,
        calendar_month as current_month,
        lag(calendar_month) over (partition by plan_tier order by calendar_month) as previous_month
    from distinct_months
),

customers_prev as (
    select mp.plan_tier, mp.current_month, r.customer_id, r.mrr as prev_mrr
    from month_pairs mp
    join {{ ref('stg_revenue') }} r
      on r.plan_tier = mp.plan_tier and r.calendar_month = mp.previous_month
    where mp.previous_month is not null
),

joined as (
    select
        cp.plan_tier,
        cp.current_month,
        cp.customer_id,
        cp.prev_mrr,
        coalesce(cur.mrr, 0) as current_mrr
    from customers_prev cp
    left join {{ ref('stg_revenue') }} cur
      on cur.customer_id = cp.customer_id
     and cur.calendar_month = cp.current_month
     and cur.plan_tier = cp.plan_tier
)

select
    plan_tier,
    current_month as calendar_month,
    sum(current_mrr) / sum(prev_mrr) * 100 as nrr_percentage
from joined
group by plan_tier, current_month

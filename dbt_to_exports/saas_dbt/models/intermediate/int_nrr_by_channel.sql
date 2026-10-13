with distinct_months as (
    select distinct channel, calendar_month from {{ ref('stg_revenue') }}
),

month_pairs as (
    select
        channel,
        calendar_month as current_month,
        lag(calendar_month) over (partition by channel order by calendar_month) as previous_month
    from distinct_months
),

customers_prev as (
    select mp.channel, mp.current_month, r.customer_id, r.mrr as prev_mrr
    from month_pairs mp
    join {{ ref('stg_revenue') }} r
      on r.channel = mp.channel and r.calendar_month = mp.previous_month
    where mp.previous_month is not null
),

joined as (
    select
        cp.channel,
        cp.current_month,
        cp.customer_id,
        cp.prev_mrr,
        coalesce(cur.mrr, 0) as current_mrr
    from customers_prev cp
    left join {{ ref('stg_revenue') }} cur
      on cur.customer_id = cp.customer_id
     and cur.calendar_month = cp.current_month
     and cur.channel = cp.channel
)

select
    channel,
    current_month as calendar_month,
    sum(current_mrr) / sum(prev_mrr) * 100 as nrr_percentage
from joined
group by channel, current_month

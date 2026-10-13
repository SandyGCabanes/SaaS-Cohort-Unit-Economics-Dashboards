-- NRR_M = (month M MRR from month M-1's customers) / (month M-1 MRR from
-- those same customers) x 100. New signups in month M are excluded from
-- both sides -- only customers already present in M-1 are compared.

with distinct_months as (
    select distinct calendar_month from {{ ref('stg_revenue') }}
),

month_pairs as (
    select
        calendar_month as current_month,
        lag(calendar_month) over (order by calendar_month) as previous_month
    from distinct_months
),

customers_prev as (
    select mp.current_month, mp.previous_month, r.customer_id, r.mrr as prev_mrr
    from month_pairs mp
    join {{ ref('stg_revenue') }} r on r.calendar_month = mp.previous_month
    where mp.previous_month is not null
),

joined as (
    select
        cp.current_month,
        cp.customer_id,
        cp.prev_mrr,
        coalesce(cur.mrr, 0) as current_mrr
    from customers_prev cp
    left join {{ ref('stg_revenue') }} cur
      on cur.customer_id = cp.customer_id and cur.calendar_month = cp.current_month
)

select
    current_month as calendar_month,
    sum(prev_mrr)                          as starting_mrr,
    sum(current_mrr)                       as retained_mrr,
    sum(current_mrr) / sum(prev_mrr) * 100  as nrr_percentage
from joined
group by current_month

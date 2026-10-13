-- Logo churn: customers active in month M-1 who are absent (not zero,
-- absent) in month M. Built from stg_revenue directly, same reasoning as
-- int_retention_base.

with active_by_month as (
    select distinct calendar_month, customer_id
    from {{ ref('stg_revenue') }}
),

months as (
    select distinct calendar_month from {{ ref('stg_revenue') }}
),

month_pairs as (
    select
        calendar_month as current_month,
        lag(calendar_month) over (order by calendar_month) as previous_month
    from months
),

prev_customers as (
    select mp.current_month, mp.previous_month, a.customer_id
    from month_pairs mp
    join active_by_month a on a.calendar_month = mp.previous_month
    where mp.previous_month is not null
),

churn_calc as (
    select
        pc.current_month,
        count(distinct pc.customer_id) as customers_at_start,
        count(distinct case when cur.customer_id is null then pc.customer_id end) as customers_churned
    from prev_customers pc
    left join active_by_month cur
      on cur.customer_id = pc.customer_id and cur.calendar_month = pc.current_month
    group by pc.current_month
)

select
    current_month as calendar_month,
    customers_at_start,
    customers_churned,
    customers_churned::double / customers_at_start * 100 as churn_rate_percentage
from churn_calc
order by calendar_month

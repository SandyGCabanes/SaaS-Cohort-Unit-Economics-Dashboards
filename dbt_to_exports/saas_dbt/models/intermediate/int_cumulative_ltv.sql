-- Masking mirrors the notebook exactly: it is based on each cohort's rank
-- among cohorts (oldest = 0), not on today's date. With N cohorts, the
-- oldest can show up to N-1 lifetime months, the newest shows 0 -- this
-- only produces the correct triangle when cohorts are consecutive months.
--
-- Capped at the CLV horizon (24 lifetime months, 0 to 23). The last column of
-- this table is therefore the 24-month LTV, and the ratio model that reads it
-- (int_ltv_cac_ratio) is the 24-month LTV:CAC.

with cum as (
    select
        cohort_month,
        lifetime_month,
        sum(avg_mrr) over (partition by cohort_month order by lifetime_month) as cumulative_ltv
    from {{ ref('int_avg_mrr') }}
    where lifetime_month < {{ var('clv_horizon_months') }}
),

cohort_rank as (
    select
        cohort_month,
        row_number() over (order by cohort_month) - 1 as idx,
        count(*) over ()                              as total_cohorts
    from (select distinct cohort_month from {{ ref('int_avg_mrr') }})
)

select
    c.cohort_month,
    c.lifetime_month,
    case
        when c.lifetime_month > (r.total_cohorts - r.idx - 1) then null
        else c.cumulative_ltv
    end as cumulative_ltv
from cum c
join cohort_rank r using (cohort_month)

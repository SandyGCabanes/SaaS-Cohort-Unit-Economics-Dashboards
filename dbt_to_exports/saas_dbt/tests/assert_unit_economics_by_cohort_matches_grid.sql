-- Rolls unit_economics_by_cohort up over all cohorts and compares the result
-- with unit_economics_grid. Returns a row for every channel x plan tier where
-- the two disagree. A passing test returns no rows.
--
-- Customer counts must match exactly. LTV and CAC must match to 6 decimal
-- places of relative error, which only allows for floating point noise.

with rolled as (
    select
        channel,
        plan_tier,
        sum(mature_customers)                                      as mature_customers,
        sum(mature_customers * ltv_24m) / sum(mature_customers)    as clv_24m,
        sum(mature_customers * average_cac) / sum(mature_customers) as average_cac
    from {{ ref('unit_economics_by_cohort') }}
    group by channel, plan_tier
)

select
    coalesce(g.channel, r.channel)        as channel,
    coalesce(g.plan_tier, r.plan_tier)    as plan_tier,
    g.mature_customers                    as grid_customers,
    r.mature_customers                    as rolled_customers,
    g.clv_24m                             as grid_clv_24m,
    r.clv_24m                             as rolled_clv_24m,
    g.average_cac                         as grid_average_cac,
    r.average_cac                         as rolled_average_cac
from {{ ref('unit_economics_grid') }} as g
full outer join rolled as r
    on g.channel = r.channel
   and g.plan_tier = r.plan_tier
where g.channel is null
   or r.channel is null
   or g.mature_customers <> r.mature_customers
   or abs(g.clv_24m - r.clv_24m)           > 0.000001 * (abs(g.clv_24m) + 1)
   or abs(g.average_cac - r.average_cac)   > 0.000001 * (abs(g.average_cac) + 1)

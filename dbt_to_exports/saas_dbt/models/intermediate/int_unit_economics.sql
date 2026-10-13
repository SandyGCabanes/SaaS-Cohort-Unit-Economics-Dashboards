-- Kept numeric (no $ / "x" string formatting) so the dashboard can format
-- and sum/filter these values freely. Format at the presentation layer.
--
-- 24-month CLV, CAC and CLV:CAC by channel x plan tier. Only customers in
-- mature cohorts count (see int_customer_clv_24m), and each customer counts
-- once, so a segment's averages are customer-weighted.
-- clv_to_cac_ratio = clv_24m / average_cac, so the three columns reconcile.

select
    channel,
    plan_tier,
    count(*)                                  as mature_customers,
    avg(customer_clv_24m)                     as clv_24m,
    avg(customer_cac)                         as average_cac,
    avg(customer_clv_24m) / avg(customer_cac) as clv_to_cac_ratio
from {{ ref('int_customer_clv_24m') }}
where is_mature_24m
group by channel, plan_tier

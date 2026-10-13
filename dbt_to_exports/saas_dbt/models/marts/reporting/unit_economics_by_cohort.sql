-- 24-month CLV, CAC and customer count for each cohort x channel x plan tier.
-- Mature cohorts only (see int_customer_clv_24m), each customer counted once.
--
-- This is unit_economics_grid before it is rolled up over cohorts. The grid
-- has one row per channel x plan tier for the whole history. This table keeps
-- cohort_month, so a consumer can rebuild the grid for any window of cohorts,
-- for example only the 2022-2023 sign-ups.
--
-- To get a window's ratio, weight each row by mature_customers:
--   ratio = sum(mature_customers * ltv_24m) / sum(mature_customers * average_cac)
-- The singular test assert_unit_economics_by_cohort_matches_grid.sql checks
-- that rolling this table up over all cohorts gives unit_economics_grid again.
--
-- ltv_24m = average 24-month revenue per customer (customer_clv_24m).
-- average_cac = average CAC per customer (customer_cac).
-- Both are kept numeric. Format at the presentation layer.

select
    cohort_month,
    channel,
    plan_tier,
    count(*)                 as mature_customers,
    avg(customer_clv_24m)    as ltv_24m,
    avg(customer_cac)        as average_cac
from {{ ref('int_customer_clv_24m') }}
where is_mature_24m
group by cohort_month, channel, plan_tier
order by cohort_month, channel, plan_tier

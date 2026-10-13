-- One row per customer with the 24-month CLV the generator wrote into
-- customer_month_panel.csv (customer_clv_24m: MRR summed over lifetime
-- months 0 to 23, repeated on every row of the customer, so min() just
-- collapses it). Every CLV, LTV and ratio model reads from here, or from
-- int_cumulative_ltv, which applies the same 24-month cap.
--
-- is_mature_24m is the generator's flag: true when the cohort has been
-- observed for the full 24 months. Unit economics filter on this, never on
-- whether the customer survived, so every customer in the average has had
-- the same 24 months.

select
    customer_id,
    min(channel)                  as channel,
    min(plan_tier)                as plan_tier,
    min(cohort_month)             as cohort_month,
    min(customer_clv_24m)         as customer_clv_24m,
    min(customer_cac)             as customer_cac,
    min(unit_clv_cac_ratio_24m)   as unit_clv_cac_ratio_24m,
    bool_or(is_mature_24m)        as is_mature_24m
from {{ ref('stg_revenue') }}
group by customer_id

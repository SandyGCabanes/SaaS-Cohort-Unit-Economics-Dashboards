-- Thin pass-through: casts and standardizes column names/types only.
-- No business logic lives here.

select
    customer_id,
    channel,
    plan_tier,
    cast(cohort_year as integer)       as cohort_year,
    cohort_month,                                 -- text 'YYYY-MM'
    calendar_month,                                -- text 'YYYY-MM'
    cast(lifetime_month as integer)    as lifetime_month,
    cast(is_active as boolean)         as is_active,
    cast(mrr as double)                as mrr,
    cast(customer_clv_24m as double)   as customer_clv_24m,
    cast(customer_cac as double)       as customer_cac,
    cast(unit_clv_cac_ratio_24m as double) as unit_clv_cac_ratio_24m,
    cast(is_mature_24m as boolean)     as is_mature_24m
from {{ source('saas_data', 'fct_revenue') }}

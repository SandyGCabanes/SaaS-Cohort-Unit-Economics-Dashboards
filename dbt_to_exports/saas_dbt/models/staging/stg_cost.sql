select
    cast(cohort_year as integer)                    as cohort_year,
    cohort_month,
    channel,
    plan_tier,
    cast(new_customers as integer)                  as new_customers,
    cast(segment_mix_share_percentage as double)     as segment_mix_share_percentage,
    cast(cac_per_customer_dollars as double)         as cac_per_customer_dollars,
    cast(total_acquisition_cost_dollars as double)   as total_acquisition_cost_dollars
from {{ source('saas_data', 'fct_cost') }}

select
    cohort_month,
    sum(total_acquisition_cost_dollars) / sum(new_customers) as cohort_cac
from {{ ref('stg_cost') }}
group by cohort_month

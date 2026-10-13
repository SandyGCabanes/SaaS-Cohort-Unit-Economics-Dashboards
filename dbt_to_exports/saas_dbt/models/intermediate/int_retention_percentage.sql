with initial as (
    select segment_type, segment_value, cohort_month, active_customer_count as initial_customer_count
    from {{ ref('int_retention_base') }}
    where lifetime_month = 0
)

select
    b.segment_type,
    b.segment_value,
    b.cohort_month,
    b.lifetime_month,
    b.active_customer_count,
    i.initial_customer_count,
    b.active_customer_count::double / i.initial_customer_count * 100 as retention_percentage
from {{ ref('int_retention_base') }} b
join initial i using (segment_type, segment_value, cohort_month)

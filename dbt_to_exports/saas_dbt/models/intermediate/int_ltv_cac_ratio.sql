select
    l.cohort_month,
    l.lifetime_month,
    l.cumulative_ltv / c.cohort_cac as ltv_cac_ratio
from {{ ref('int_cumulative_ltv') }} l
join {{ ref('int_cohort_cac_summary') }} c using (cohort_month)

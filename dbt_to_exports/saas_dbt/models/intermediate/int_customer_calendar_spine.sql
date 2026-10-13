-- Mirrors the notebook's pd.MultiIndex.from_product([all_customers, all_months]):
-- every customer gets a row for every calendar month in the dataset, including
-- months before their own cohort_month. Those pre-cohort rows are harmless --
-- they carry mrr = 0 and never trigger a movement_type other than "No Change".

select
    a.customer_id,
    a.channel,
    a.plan_tier,
    a.cohort_month,
    m.calendar_month
from {{ ref('int_customer_attributes') }} a
cross join {{ ref('int_calendar_months') }} m

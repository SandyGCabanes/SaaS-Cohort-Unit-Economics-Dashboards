-- Customer-weighted CAC for each cohort month and channel, all plan tiers
-- together: total acquisition spend divided by total new customers.
-- A cohort with 300 signups counts 300 times as much as a cohort with 1.
--
-- This is the same rule saas_kpi_engine.py uses (compute_cac_by_channel).
-- It feeds the CAC-by-channel chart, and it lets the dashboard builder work
-- out blended CAC per cohort without reading the raw cost file.
--
-- A channel with zero new customers in a cohort has no CAC, so it gets no row.

select
    cohort_month,
    channel,
    sum(total_acquisition_cost_dollars) / sum(new_customers) as cohort_cac
from {{ ref('stg_cost') }}
group by cohort_month, channel
having sum(new_customers) > 0
order by channel, cohort_month

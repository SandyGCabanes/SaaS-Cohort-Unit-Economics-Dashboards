select
    calendar_month,
    sum(case when mrr > 0 then 1 else 0 end)                       as active_customers,
    sum(case when movement_type = 'New Business' then 1 else 0 end) as new_customers,
    sum(case when movement_type = 'Churn' then 1 else 0 end)        as churned_customers
from {{ ref('customer_level_movements_mrr') }}
group by calendar_month
order by calendar_month

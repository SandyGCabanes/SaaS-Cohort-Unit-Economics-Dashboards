-- Long form of mrr_movements_summary for a stacked-bar / waterfall chart
-- component: one row per calendar_month x movement_type, not one column
-- per category.
select calendar_month, movement_type, sum(mrr_delta) as delta_value
from {{ ref('customer_level_movements_mrr') }}
group by calendar_month, movement_type
order by calendar_month, movement_type

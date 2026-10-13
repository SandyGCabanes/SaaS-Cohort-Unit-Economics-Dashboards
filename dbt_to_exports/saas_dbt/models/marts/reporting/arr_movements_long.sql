select calendar_month, movement_type, sum(arr_delta) as delta_value
from {{ ref('customer_level_movements_arr') }}
group by calendar_month, movement_type
order by calendar_month, movement_type

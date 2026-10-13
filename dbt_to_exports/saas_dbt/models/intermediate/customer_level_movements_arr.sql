with with_prev as (
    select
        *,
        coalesce(lag(arr_run_rate) over (partition by customer_id order by calendar_month), 0) as prev_arr
    from {{ ref('reindexed_panel_audit_arr') }}
)

select
    *,
    arr_run_rate - prev_arr as arr_delta,
    case
        when prev_arr = 0 and arr_run_rate > 0                             then 'New Business'
        when prev_arr > 0 and arr_run_rate > prev_arr                      then 'Expansion'
        when prev_arr > 0 and arr_run_rate < prev_arr and arr_run_rate > 0 then 'Contraction'
        when prev_arr > 0 and arr_run_rate = 0                             then 'Churn'
        else 'No Change'
    end as movement_type
from with_prev

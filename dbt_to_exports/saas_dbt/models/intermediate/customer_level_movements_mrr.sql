with with_prev as (
    select
        *,
        coalesce(lag(mrr) over (partition by customer_id order by calendar_month), 0) as prev_mrr
    from {{ ref('reindexed_panel_audit_mrr') }}
)

select
    *,
    mrr - prev_mrr as mrr_delta,
    case
        when prev_mrr = 0 and mrr > 0                    then 'New Business'
        when prev_mrr > 0 and mrr > prev_mrr              then 'Expansion'
        when prev_mrr > 0 and mrr < prev_mrr and mrr > 0  then 'Contraction'
        when prev_mrr > 0 and mrr = 0                     then 'Churn'
        else 'No Change'
    end as movement_type
from with_prev

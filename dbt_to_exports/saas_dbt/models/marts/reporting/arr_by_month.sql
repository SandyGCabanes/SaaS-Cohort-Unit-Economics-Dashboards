-- From the terminal, inside the dbt project folder:
-- dbt run --select arr_by_month

-- models/marts/reporting/arr_by_month.sql

{{ config(materialized='table') }}

with monthly_mrr as (

    select
        calendar_month,
        metric_value as total_mrr
    from {{ ref('monthly_metrics_long') }}
    where segment_type = 'all'
      and segment_value = 'all'
      and metric_name = 'total_mrr'

)

select
    calendar_month,
    total_mrr,
    total_mrr * 12 as arr_value
from monthly_mrr
order by calendar_month
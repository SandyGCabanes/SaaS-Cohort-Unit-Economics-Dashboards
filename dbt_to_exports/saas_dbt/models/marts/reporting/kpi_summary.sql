-- Feeds the KPI card component directly: current value, previous period's
-- value, and pct_change already computed. The engine picks the latest
-- period per metric_name for cards, or plots the full series for a trend
-- sparkline -- no calculation happens in Python either way.

with with_prev as (
    select
        segment_type,
        segment_value,
        metric_name,
        calendar_month as period,
        metric_value as current_value,
        lag(metric_value) over (
            partition by segment_type, segment_value, metric_name
            order by calendar_month
        ) as previous_value
    from {{ ref('monthly_metrics_long') }}
)

select
    *,
    case
        when previous_value is null or previous_value = 0 then null
        else (current_value - previous_value) / abs(previous_value) * 100
    end as pct_change
from with_prev
order by metric_name, period

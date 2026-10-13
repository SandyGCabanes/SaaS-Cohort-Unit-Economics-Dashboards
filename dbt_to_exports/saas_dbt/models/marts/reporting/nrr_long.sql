-- Unifies nrr_by_month / nrr_by_month_and_channel / nrr_by_month_and_plan_tier
-- into the standard segment_type/segment_value shape. Keep the three
-- original tables too (simpler for a quick SQL check); the engine reads
-- this one.

with blended as (
    select 'all' as segment_type, 'all' as segment_value, calendar_month, nrr_percentage
    from {{ ref('int_nrr_base') }}
),

by_channel as (
    select 'channel' as segment_type, channel as segment_value, calendar_month, nrr_percentage
    from {{ ref('int_nrr_by_channel') }}
),

by_plan_tier as (
    select 'plan_tier' as segment_type, plan_tier as segment_value, calendar_month, nrr_percentage
    from {{ ref('int_nrr_by_plan_tier') }}
)

select * from blended
union all select * from by_channel
union all select * from by_plan_tier

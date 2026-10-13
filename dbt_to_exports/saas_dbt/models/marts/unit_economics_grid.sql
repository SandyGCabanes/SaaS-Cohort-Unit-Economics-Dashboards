select * from {{ ref('int_unit_economics') }}
order by channel, plan_tier

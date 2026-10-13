select distinct calendar_month
from {{ ref('stg_revenue') }}

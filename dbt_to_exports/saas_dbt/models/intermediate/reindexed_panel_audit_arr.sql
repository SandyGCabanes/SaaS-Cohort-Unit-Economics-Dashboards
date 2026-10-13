-- Same expanded grid as reindexed_panel_audit_mrr, scaled to an annual
-- figure (ARR = MRR x 12). Kept as its own table so it never gets
-- overwritten by the MRR audit, matching the notebook's two separate files.

select
    *,
    mrr * 12.0 as arr_run_rate
from {{ ref('reindexed_panel_audit_mrr') }}

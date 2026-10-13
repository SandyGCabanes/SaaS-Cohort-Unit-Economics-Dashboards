```mermaid
flowchart TD
    start["Start: create data<br/>saas_dataset_*.csv<br/>GROUND-TRUTH PANEL"]
    excel["Excel validation"]
    python["Python validation"]
    dashboards["Create html dashboards:<br/>kpi_engine + build dashboards"]
    disaggregate["Disaggregate to marketing<br/>and stripe csv files,<br/>3rd-party api extracts simulated"]
    dbt1["dbt 1: from raw csv,<br/>creates GROUND-TRUTH PANEL files<br/>(staging reconstruction)"]
    upload["Manual upload to cloud storage,<br/>simulated bucket (local folder)<br/>ideally automated with dated<br/>folders and lifecycle rules"]
    dbt2["dbt 2: to exports<br/>export kpis and metrics<br/>for new dashboards (separate folder)"]
    end["End of Flowchart"]

    start --> excel --> python
    python --> dashboards
    dashboards --> disaggregate
    disaggregate --> dbt1
    dbt1 --> upload --> dbt2 --> end

    python -. "metrics off" .-> start
    dashboards -. "metrics off" .-> start
```

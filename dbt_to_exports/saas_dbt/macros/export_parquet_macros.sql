{% macro export_marts_to_parquet(folder='parquet_exports') %}
  {# Writes every mart model to a Parquet file. Run after dbt build:
     dbt run-operation export_marts_to_parquet
     Files go to parquet_exports/reporting.
     The shared mart goes to the top of parquet_exports. #}
  {% set written = [] %}
  {% for node in graph.nodes.values()
       if node.resource_type == 'model' and node.path.replace('\\', '/').startswith('marts/') %}
    {% set parts = node.path.replace('\\', '/').split('/') %}
    {% set subfolder = parts[1] if parts | length > 2 else '' %}
    {% set target = folder ~ ('/' ~ subfolder if subfolder else '') ~ '/' ~ node.name ~ '.parquet' %}
    {% do run_query("copy " ~ node.schema ~ "." ~ node.name ~ " to '" ~ target ~ "' (format parquet, compression zstd)") %}
    {% do written.append(target) %}
  {% endfor %}
  {{ log("Wrote " ~ written | length ~ " Parquet files to " ~ folder, info=True) }}
{% endmacro %}


{% macro export_marts_after_build(results) %}
  {# Runs at the end of dbt build and dbt run (see on-run-end in dbt_project.yml).
     It writes the Parquet and CSV files only when every mart was built successfully
     and every step passed. Otherwise it skips and says why in the log, so a
     half-finished build never overwrites good files with partial data. #}
  {% if execute and flags.WHICH in ['build', 'run'] %}

    {% set mart_nodes = [] %}
    {% for node in graph.nodes.values()
         if node.resource_type == 'model' and node.path.replace('\\', '/').startswith('marts/') %}
      {% do mart_nodes.append(node.name) %}
    {% endfor %}

    {% set built_marts = [] %}
    {% set problems = [] %}
    {% for r in results %}
      {% set status = r.status | string | lower %}
      {% if status not in ['success', 'pass', 'warn'] %}
        {% do problems.append(r.node.name) %}
      {% elif r.node.resource_type == 'model' and r.node.name in mart_nodes %}
        {% do built_marts.append(r.node.name) %}
      {% endif %}
    {% endfor %}

    {% if problems | length > 0 %}
      {{ log("Parquet and CSV export skipped: " ~ problems | length ~ " step(s) did not succeed, for example " ~ problems[0], info=True) }}
    {% elif built_marts | length < mart_nodes | length %}
      {{ log("Parquet and CSV export skipped: only " ~ built_marts | length ~ " of " ~ mart_nodes | length ~ " mart models were built in this run. Run a full dbt build to export.", info=True) }}
    {% else %}
      {{ export_marts_to_parquet() }}
      {{ export_marts_to_csv() }}
    {% endif %}

  {% endif %}
{% endmacro %}

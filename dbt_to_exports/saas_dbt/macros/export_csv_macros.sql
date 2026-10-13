{% macro export_marts_to_csv(folder='csv_exports') %}
  {# Writes every mart model to a CSV file. Run after dbt build:
     dbt run-operation export_marts_to_csv
     Files go to csv_exports/reporting.
     The shared mart goes to the top of csv_exports. #}
  {% set written = [] %}
  {% for node in graph.nodes.values()
       if node.resource_type == 'model' and node.path.replace('\\', '/').startswith('marts/') %}
    {% set parts = node.path.replace('\\', '/').split('/') %}
    {% set subfolder = parts[1] if parts | length > 2 else '' %}
    {% set target = folder ~ ('/' ~ subfolder if subfolder else '') ~ '/' ~ node.name ~ '.csv' %}
    {% do run_query("copy " ~ node.schema ~ "." ~ node.name ~ " to '" ~ target ~ "' (format csv, header)") %}
    {% do written.append(target) %}
  {% endfor %}
  {{ log("Wrote " ~ written | length ~ " CSV files to " ~ folder, info=True) }}
{% endmacro %}

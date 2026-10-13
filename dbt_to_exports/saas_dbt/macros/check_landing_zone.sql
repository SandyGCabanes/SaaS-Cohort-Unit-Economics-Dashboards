{% macro check_landing_zone() %}
  {# Stops the run with a plain message if an expected CSV file is missing. #}
  {% if execute %}
    {% set expected = ['customer_month_panel.csv', 'cost_per_customer.csv'] %}
    {% for f in expected %}
      {% set path = var('landing_zone') ~ '/' ~ f %}
      {% set result = run_query("select count(*) from glob('" ~ path ~ "')") %}
      {% if result.columns[0].values()[0] == 0 %}
        {{ exceptions.raise_compiler_error(
          "Missing file: " ~ path ~ ". Place " ~ f ~ " in the landing zone folder, "
          ~ "and run dbt from the project folder, then run dbt build again.") }}
      {% endif %}
    {% endfor %}
  {% endif %}
{% endmacro %}

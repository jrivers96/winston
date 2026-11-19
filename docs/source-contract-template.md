# Source Contract Template

This document defines the slots that must be filled for live Databricks and Datadog integration.
All fields below are **empty templates**—do not fill with invented production values.

## Databricks Source Mapping

### Index Definitions Table

```yaml
table_name: ""           # e.g., catalog.schema.index_definitions
columns:
  index_id: ""           # Column name for index identifier
  environment: ""        # Column name for environment (prod/uat/etc)
  owner: ""              # Column name for owner/team
  calendar_ref: ""       # Column name for calendar reference
  timezone: ""           # Column name for timezone
  state_schema: ""       # Column name for state schema definition
  methodology_ref: ""    # Column name for methodology reference
  stages: ""             # Column name for calculation stages
  predecessor_rules: ""  # Column name for predecessor/lookback rules
```

### Calendar Table

```yaml
table_name: ""
columns:
  calendar_id: ""
  business_date: ""
  is_calculation_day: ""
  previous_calculation_date: ""
  timezone: ""
```

### Executions Table

```yaml
table_name: ""
columns:
  execution_id: ""
  index_id: ""
  environment: ""
  business_date: ""
  attempt_id: ""
  start_time: ""
  end_time: ""
  status: ""
  input_manifest_id: ""
  code_manifest_id: ""
  output_ref: ""
  state_ref: ""
```

### Input Manifests Table

```yaml
table_name: ""
columns:
  manifest_id: ""
  execution_id: ""
  parent_state_refs: ""   # JSON array of parent state references
  input_dataset_refs: ""  # JSON array of input dataset references
  configuration_ref: ""
```

### State/Output Artifacts Table

```yaml
table_name: ""
columns:
  artifact_id: ""
  execution_id: ""
  artifact_type: ""       # state | output
  schema_version: ""
  content_hash: ""
  storage_ref: ""
```

### Selected Revisions Table

```yaml
table_name: ""
columns:
  index_id: ""
  environment: ""
  business_date: ""
  selected_execution_id: ""
  selection_policy: ""
  selection_time: ""
```

## Datadog Metric Mappings

### Execution Metrics

```yaml
metrics:
  - name: ""              # Metric name for execution duration
    service_tag: ""
    environment_tag: ""
    index_tag: ""
    aggregation: ""
    
  - name: ""              # Metric name for error rate
    service_tag: ""
    environment_tag: ""
    index_tag: ""
    aggregation: ""
    
  - name: ""              # Metric name for resource usage (CPU)
    service_tag: ""
    environment_tag: ""
    aggregation: ""
```

### Service Mappings

```yaml
services:
  - index_id: ""
    datadog_service: ""
    datadog_env: ""
    additional_tags: []
```

## Calendar Rules

```yaml
calendars:
  - id: ""
    timezone: ""
    weekday_rule: ""      # e.g., "Mon-Fri"
    holiday_source: ""    # Reference to holiday calendar
    custom_closures: []   # List of additional closure dates
```

## Index Formulas

Winston does not implement client methodology. This section documents where formula definitions live:

```yaml
formula_locations:
  - index_id: ""
    repository_id: ""
    path: ""
    entrypoint: ""
```

## Run Lineage Source

```yaml
lineage:
  source: ""              # unity_catalog | custom_table | none
  table_name: ""          # If custom_table
  coverage: ""            # What lineage captures (queries, jobs, etc)
  retention_days: ""
```

## Authentication

```yaml
databricks:
  auth_method: ""         # oauth_m2m | pat | azure_cli | etc
  host: ""
  warehouse_id: ""
  catalog: ""
  
datadog:
  site: ""                # e.g., datadoghq.com, datadoghq.eu
  auth_method: ""         # api_key | oauth
```

---

**Instructions**: Copy this template to a live configuration file and fill in actual values.
Do not commit credentials. Use environment variables or credential providers.

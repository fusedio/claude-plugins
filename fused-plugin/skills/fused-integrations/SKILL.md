---
name: fused-integrations
description: Reference for using Fused's built-in integration connections inside UDFs. Covers Snowflake, BigQuery, GCS, S3, Airtable, and Notion — the fused.api connect helpers, secrets access, and common operations (query, write, list). Use when the user is writing a UDF that reads from or writes to a connected data source.
---

# Fused Integrations

Once an integration is configured (via the Workbench → Integrations UI or `fused integrations <provider> connect`), use the helpers below inside any UDF. You do **not** need to manage credentials manually — connections and secrets are resolved by the runtime.

Available integrations: `snowflake`, `bigquery`, `gcs`, `s3`, `airtable`, `notion`, `slack` (experimental).

---

## Snowflake

Docs: https://docs.fused.io/workbench/integrations/snowflake

### Simple query

```python
@fused.udf
def udf():
    import fused.api
    return fused.api.snowflake_query(
        "SELECT * FROM my_db.my_schema.my_table LIMIT 10"
    )
```

### Reusable connection (multiple operations)

```python
@fused.udf
def udf():
    import fused.api
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH",
        database="ANALYTICS",
        schema="PUBLIC",
        role="ANALYST",
    )
    print("Tables:", conn.list_tables("ANALYTICS", "PUBLIC"))
    return conn.query("""
        SELECT region, SUM(amount) AS total
        FROM orders
        WHERE order_date >= '2025-01-01'
        GROUP BY region
        ORDER BY total DESC
    """)
```

### Write a DataFrame back to Snowflake

```python
@fused.udf
def udf():
    import fused.api, pandas as pd
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH", database="ANALYTICS", schema="PUBLIC"
    )
    df = pd.DataFrame({"id": [1, 2, 3], "value": [10.5, 20.3, 30.1]})
    conn.write(df, "ANALYTICS.PUBLIC.METRICS", mode="overwrite")
    return df
```

### Read from a Snowflake Stage

```python
@fused.udf
def udf():
    import fused.api
    conn = fused.api.snowflake_connect(
        warehouse="COMPUTE_WH", database="RAW_DATA", schema="INGEST"
    )
    files = conn.list_stage_files("@csv_stage", pattern=".*[.]csv")
    if files:
        return conn.read_stage(f"@csv_stage/{files[0].split('/')[-1]}")
```

**Connection methods:** `.query()`, `.list_tables()`, `.write(df, table, mode=)`, `.list_stage_files()`, `.read_stage()`

---

## BigQuery

Docs: https://docs.fused.io/workbench/integrations/bigquery

Credentials are stored as a service-account JSON string in `fused.secrets["gcs_fused"]`.

```python
@fused.udf
def udf():
    import json
    from google.cloud import bigquery
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(fused.secrets["gcs_fused"]),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)
    query = """
        SELECT * FROM `bigquery-public-data.new_york.tlc_yellow_trips_2015`
        LIMIT 10
    """
    return client.query(query).to_dataframe()
    # For geospatial results: .to_geodataframe(geography_column="geometry")
```

---

## Google Cloud Storage (GCS)

Docs: https://docs.fused.io/workbench/integrations/gcs

Credentials are stored as a service-account JSON string in `fused.secrets["gcs_fused"]`.

### List files in a bucket

```python
@fused.udf
def udf():
    import os
    from google.cloud import storage

    with open("/tmp/gcs_key.json", "w") as f:
        f.write(fused.secrets["gcs_fused"])
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/gcs_key.json"

    client = storage.Client()
    bucket = client.bucket("your_bucket_name")
    blobs = bucket.list_blobs(prefix="path/to/your/data")
    print({blob.name for blob in blobs})
```

---

## Amazon S3

Docs: https://docs.fused.io/workbench/integrations/s3

S3 access is granted via IAM role (configured once in the Integrations UI). No credentials are needed inside the UDF.

### List files

```python
@fused.udf
def udf():
    return fused.api.list("s3://<BUCKET_NAME>/")
```

Reading and writing S3 files from UDFs works with standard libraries (`boto3`, `s3fs`, `pandas`) once the role is attached — the runtime inherits the IAM permissions automatically.

---

## Airtable

Docs: https://docs.fused.io/workbench/integrations/airtable

All operations go through `fused.api.airtable_connect()`.

### List bases

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect()
    bases = at.list_bases()
    for base in bases:
        print(base["id"], base["name"])
```

### Read records

```python
@fused.udf()
def udf():
    import pandas as pd
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    records = at.list_records(
        "Tasks",
        view="Grid view",
        filterByFormula="{Status} = 'Done'",
        maxRecords=100,
    )
    rows = [{"id": r["id"], **r["fields"]} for r in records]
    return pd.DataFrame(rows)
```

### Create records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    created = at.create_records("Tasks", [
        {"fields": {"Name": "Buy groceries", "Status": "Todo"}},
        {"fields": {"Name": "Write docs", "Status": "In Progress"}},
    ])
    for r in created:
        print(r["id"])
```

### Update records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    at.update_records("Tasks", [
        {"id": "recXXXXXXXXXXXXXX", "fields": {"Status": "Done"}},
    ])
```

### Delete records

```python
@fused.udf()
def udf():
    at = fused.api.airtable_connect(base_id="appXXXXXXXXXXXXXX")
    at.delete_records("Tasks", ["recAAAAAAAAAAAA", "recBBBBBBBBBBBB"])
```

**Connection methods:** `.list_bases()`, `.list_records(table, view=, filterByFormula=, maxRecords=)`, `.create_records(table, rows)`, `.update_records(table, rows)`, `.delete_records(table, ids)`

---

## Notion

Docs: https://docs.fused.io/workbench/integrations/notion

All operations go through `fused.api.notion_connect()`, which returns a thin wrapper. Call `.client()` to get a full `notion-client` SDK instance.

### Search pages

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    results = client.search(query="Q4 Planning")
    pages = client.search(query="Meeting", filter={"value": "page", "property": "object"})
```

### Get / update a page

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    page = client.pages.retrieve(page_id="a1b2c3d4-...")
    client.pages.update(
        page_id="your-page-id",
        properties={"Status": {"status": {"name": "Done"}}},
    )
```

### Query a database

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    response = client.databases.query(database_id="your-database-id")
    for page in response["results"]:
        print(page["id"], page["properties"])
```

### Create a page in a database

```python
@fused.udf()
def udf():
    nt = fused.api.notion_connect()
    client = nt.client()
    client.pages.create(
        parent={"database_id": "your-database-id"},
        properties={
            "Name": {"title": [{"text": {"content": "Weekly Report"}}]},
            "Status": {"select": {"name": "Draft"}},
        },
    )
```

### Pull all pages into a DataFrame

```python
@fused.udf()
def udf():
    import pandas as pd
    nt = fused.api.notion_connect()
    client = nt.client()
    response = client.search(filter={"value": "page", "property": "object"})
    rows = []
    for p in response["results"]:
        props = p.get("properties", {})
        title_parts = props.get("Name", {}).get("title", [])
        title = "".join(t["plain_text"] for t in title_parts)
        rows.append({"id": p["id"], "title": title, "url": p.get("url"), "last_edited": p.get("last_edited_time")})
    return pd.DataFrame(rows)
```

---

## Secrets (generic key/value)

Any secret stored via `fused secrets set KEY VALUE` (or the Workbench UI) is available as `fused.secrets["KEY"]` inside any UDF. Use this for API keys, tokens, or JSON credential blobs that don't have a first-class connect helper.

```python
@fused.udf
def udf():
    api_key = fused.secrets["my_api_key"]
```

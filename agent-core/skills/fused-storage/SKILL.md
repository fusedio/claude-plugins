---
name: fused-storage
description: The fused storage and secrets MCP tools — inspecting cloud-native datasets and managing secrets. Use when finding/listing/counting S3 objects, reading a Parquet/Arrow/CSV schema, minting a download URL, uploading content, or storing/reading/deleting secrets, via mcp__openfused__{list_files,count_files,get_file,get_file_schema,upload_file,get_secret,put_secret,list_secrets,delete_secret}. For running code over the data see fused-execute; for the equivalent CLI commands see fused-cli.
---

# Storage & secrets in fused

These tools are the **find → load → explore** front of the workflow: locate data,
understand its shape, and move bytes in/out — *before* you run code over it with
`execute_code`. All are **always-on** MCP tools (no `--enable-infra` /
`--enable-destructive` flags needed) — except `delete_secret`, which requires
`--enable-destructive` — and back the same operations as the CLI's
`files …` / `secrets …` commands (see fused-cli). They operate on the **active
environment's** storage backend — real S3 on AWS, the local filesystem on the
local backend — so the same calls work on either of them.

## Inspect before you compute

The cheapest way to avoid a wasted `execute_code` run is to look first. Typical
flow: `list_files` → `count_files` → `get_file_schema`, then write code against a
known schema.

### `list_files(bucket?, prefix?, page_size=100, page_token?)`

- **No `bucket`** → lists buckets: `{"buckets": [...], "count": N}`.
- **With `bucket`** → one page of keys under `prefix` plus a `next_page_token`.
  **Paginate**: follow `next_page_token` in successive calls until it is `null`.
  Do not assume one call returns everything — `page_size` defaults to 100.

```
list_files()                                   # what buckets exist?
list_files(bucket="my-data", prefix="events/") # first page of keys
list_files(bucket="my-data", prefix="events/", page_token="<next>")  # next page
```

### `count_files(bucket, prefix?, extensions?)`

Counts objects under a prefix, optionally filtered by extension — cheaper than
paging all keys when you only need a tally or a partition count.

```
count_files(bucket="my-data", prefix="events/", extensions=[".parquet"])
```

### `get_file_schema(bucket, key)`

Column schema + metadata for a **Parquet, Arrow IPC, or CSV** file — read this to
learn column names/dtypes (and row count for Parquet/CSV) before writing a query.
Arrow IPC reports record-batch count rather than a row count. Use it to confirm a
file's shape so your `execute_code` doesn't guess column names.

### `get_file(bucket, key, expires_in=3600)`

Returns a **presigned download URL** (default 1 h). For fetching a result or
sample to the caller. On the local backend this is a short-lived HMAC-signed
`http://` URL served by a local file server, so it behaves like the cloud path.
Treat the URL as a bearer token — anyone with it can fetch the object until it
expires.

### `upload_file(bucket, key, content, base64_encoded=False)`

Write content to object storage.

- **Text** (CSV, JSON): pass `content` as a UTF-8 string.
- **Binary** (Parquet, Arrow, images): base64-encode and set
  `base64_encoded=True`.

For large or computed outputs, prefer writing **from inside `execute_code`** (the
code has direct S3 access via the execution role) rather than round-tripping bytes
through the MCP boundary — see fused-execute.

## Secrets

Secrets let executing code reach databases/APIs without hard-coding credentials.
The model is **the execution principal reads the store directly** — values are
never injected into the `execute_code` payload.

### `put_secret(name, value)` — mind the name prefix

On AWS the Lambda execution role can only read secrets under the environment's
`function_prefix` (e.g. `openfused-*`). `put_secret` **enforces this at write
time**: a name outside the prefix is rejected with an actionable error rather than
becoming an invisible-at-runtime secret. So name secrets `openfused-<thing>`:

```
put_secret(name="openfused-pg-conn", value="postgresql://user:pass@host/db")
```

Then read it *inside* the execution using `openfused.get_secret` — works on both
AWS and the local backend (via the `fused` shim):

```python
import openfused

conn = openfused.get_secret("openfused-pg-conn")
result = ...  # use conn
```

(`examples/duckdb_with_secret.py` is a full DuckDB-over-Postgres example.)

### `get_secret(name)` / `list_secrets(prefix?)`

`get_secret` returns the secret string (raises if absent or binary — text only).
`list_secrets` returns `[{"name", "arn", …}]`, prefix-filtered. On the local
backend secrets live in the OS keychain (one JSON blob per environment, keyed by
the resolved store path); access control is OS-keychain, not IAM.

> **Linux/WSL has no native keychain.** Where no usable OS keychain exists, every
> local secret operation **raises a `RuntimeError`** naming both remedies: install
> the file-based fallback (`pip install keyrings.alt`, which stores secrets
> *unencrypted* on disk — dev only) or switch to the AWS backend for headless/CI
> use. Without `keyrings.alt` and without a keychain, secrets simply fail loud.

### `delete_secret(name)` — gated behind `--enable-destructive`

Unlike the always-on trio above, `delete_secret` is a **destructive** tool: it
is only registered when the server runs with `--enable-destructive` (the same
gate as `env_delete`/`infra_teardown`). It raises if the secret does not exist
and returns `{"deleted": name}` on success. On AWS the secret is **scheduled**
for deletion with the default 30-day recovery window (recoverable via AWS
tooling until it elapses); on the local backend the name is removed from the
keychain map immediately. CLI equivalent: `fused secrets delete
<name>` (prompts; `--yes` to skip). Do not "delete" by overwriting with an
empty value — that leaves a readable (empty) secret in place.

## Notes

- Apart from `delete_secret` (`--enable-destructive`), these tools never gate
  on feature flags; they are available in every server session.
- For destructive cleanup of cached/spilled result objects use `cache_clear`
  (covered in fused-execute), not these tools.
- CLI equivalents: `fused files list|count|get|schema|upload` and
  `fused secrets get|put|list|delete` (fused-cli).

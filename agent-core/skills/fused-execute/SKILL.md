---
name: fused-execute
description: Best practices for running code through fused's execute_code tool. Use when writing or reviewing any mcp__openfused__execute_code call — covers how to structure user code, choose a data library, handle results, and write outputs to the file store. For security scanning, spec checks, and testing see fused-verify.
---

# Running code via fused

## Core principle: code should do one thing

The code string passed to `execute_code` should be as focused as possible:
- One clear task per execution
- No boilerplate, no CLI argument parsing, no `if __name__ == "__main__"` guards
- Return the result from a `@fused.udf`-decorated function (preferred), or assign it to a top-level `result` variable

## Choosing how to return: `@fused.udf` vs `result`

**Prefer a `@fused.udf` entrypoint over a top-level `result =` assignment.** Both
return the value identically, but a UDF is the more capable, portable form:

- It takes parameters, so the same code runs standalone *and* as a fan-out worker
  (`.map()` / `fused.load()`) or a served route — kwargs arrive via `_openfused_args.json`.
- It matches the real `fused` SDK, so code moves between fused and Fused unchanged.
- It keeps the return value in an explicit `return`, not a magic module global.

```python
import fused

@fused.udf
def main(threshold: int = 0):
    ...
    return {"count": n}        # becomes the return value
```

Use a bare `result = <scalar>` only for a quick one-off where there are no
parameters and you won't reuse the code (e.g. `result = df.shape[0]`).

The two are **mutually exclusive** — a script returns via a `@fused.udf` *or* a
`result` variable, never both; using both (including `result = None` alongside a
UDF) is an error.

## Returning results

**Prefer writing to S3 over returning data inline.**

The return value (whether from a `@fused.udf` or a `result` variable) is serialized as a string in the response. That works fine for scalars (a URL, a count, a status message), but large DataFrames or binary blobs will be truncated or unusable.

The right pattern:

1. Compute the output inside `execute_code`
2. Write it to S3 using `boto3` inside the same code block
3. Return the S3 key or a presigned URL — not the data itself
4. After execution, call `mcp__openfused__get_file` with that key if a download URL is needed

Only return inline when the value is a simple scalar: a number, a short string, a boolean.

## Writing DataFrames to S3 inside execute_code

Always write DataFrames to the environment's **cache bucket** rather than returning them inline. Get the bucket name first with `mcp__openfused__env_show`, then embed it in the code string (it is not a secret).

```python
# Step 1: get bucket name
# mcp__openfused__env_show()  →  { "cache_bucket": "openfused-abc123", ... }

# Step 2: write to cache bucket inside execute_code
code = """
import boto3, io

# ... compute df ...

buf = io.BytesIO()
df.to_parquet(buf, index=False)
buf.seek(0)

s3 = boto3.client("s3")
bucket = "openfused-abc123"   # from env_show cache_bucket
key = "outputs/my_result.parquet"
s3.put_object(Bucket=bucket, Key=key, Body=buf.read())

result = f"s3://{bucket}/{key}"
"""
```

**Choosing what to return as `result`:**

| Use case | Return |
|---|---|
| Internal / follow-up tool calls | `f"s3://{bucket}/{key}"` (path only) |
| User download / public sharing | Presigned URL — either from `mcp__openfused__get_file` after execution, or generated inside `execute_code` with `boto3` |

For a presigned URL via a follow-up tool call: `mcp__openfused__get_file(bucket="openfused-abc123", key="outputs/my_result.parquet")`.

To generate the URL inside `execute_code` (avoids an extra round-trip when the user explicitly asks for a URL):

```python
import boto3, io

# ... compute and write file ...
s3 = boto3.client("s3", region_name="us-west-2")
bucket, key = "openfused-abc123", "outputs/my_result.parquet"
s3.put_object(Bucket=bucket, Key=key, Body=buf.read())

url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600,
)
result = url
```

When writing output via DuckDB `COPY … TO 's3://…'` is not possible due to region/credential mismatch, write to `/tmp/` first then upload with `boto3`:

```python
conn.execute("COPY (SELECT …) TO '/tmp/output.parquet'")
with open("/tmp/output.parquet", "rb") as f:
    s3.put_object(Bucket=bucket, Key=key, Body=f.read())
```

## Choosing a data library

Prefer libraries in this order:

1. **DuckDB** — best default for SQL-style analysis, reading Parquet/CSV directly from S3, and aggregations over large files. Zero-copy, no materialisation until needed.
2. **Polars** — preferred for Python-native DataFrame transformations. Lazy API, fast, low memory footprint.
3. **Pandas** — use only when an existing snippet, library, or output format requires it.

## DuckDB S3 setup

**AWS Lambda:** Lambda has no writable home directory by default. Always create one in `/tmp` and pass it via the `config` dict — using `SET home_directory=...` after connection does not work reliably in Lambda.

```python
import duckdb, os

os.makedirs("/tmp/duckdb_home", exist_ok=True)
conn = duckdb.connect(config={"home_directory": "/tmp/duckdb_home"})
conn.execute("SET s3_region='us-east-1'")   # match the bucket's region
conn.execute("INSTALL httpfs; LOAD httpfs")
```

**S3 region**: set `s3_region` to the region of the bucket you are reading from, which may differ from the Lambda's own region. Public buckets (e.g. `fused-asset`) are typically in `us-east-1`; the fused cache bucket (`openfused-cache`) is in `us-west-2`. If you read from one and write to the other, update `s3_region` between the two operations.

```python
# DuckDB reading Parquet directly from S3 (no download needed)
requirements = ["duckdb"]
code = """
import duckdb
con = duckdb.connect()
result_df = con.execute(
    "SELECT col, COUNT(*) FROM read_parquet('s3://my-bucket/data/*.parquet') GROUP BY col"
).df()
# write result_df to S3 cache bucket ...
"""

# Polars for in-memory transforms
requirements = ["polars", "pyarrow"]
code = """
import polars as pl
df = pl.read_parquet("/tmp/context/input.parquet")
out = df.filter(pl.col("value") > 0).group_by("category").agg(pl.col("value").sum())
# write out to S3 cache bucket ...
"""
```

### Passing file paths to DuckDB — Python variables vs SQL

DuckDB's `conn.execute(sql)` runs SQL; it cannot reference Python variables by name. A common mistake when building file lists dynamically:

```python
# WRONG — 'paths' is a Python list; DuckDB SQL treats it as a column name
paths = ["s3://bucket/a.parquet", "s3://bucket/b.parquet"]
conn.execute("SELECT * FROM read_parquet(paths)")   # BinderError

# RIGHT — use parameter binding
conn.execute("SELECT * FROM read_parquet(?)", [paths])
```

## Geospatial data

For any spatial analysis involving latitude/longitude points, use **H3** (Uber's hierarchical hexagonal grid). It is faster to join, aggregate, and visualize than raw coordinates.

Common patterns:

```python
requirements = ["h3", "polars", "pyarrow"]
code = """
import h3
import polars as pl

df = pl.read_parquet("/tmp/context/points.parquet")  # has lat, lng columns

# Index points into H3 hexagons at resolution 8 (~460 m)
df = df.with_columns(
    pl.struct(["lat", "lng"])
    .map_elements(lambda r: h3.latlng_to_cell(r["lat"], r["lng"], 8), return_dtype=pl.Utf8)
    .alias("h3_cell")
)

# Aggregate per cell
agg = df.group_by("h3_cell").agg(pl.len().alias("count"))

buf = __import__("io").BytesIO()
agg.write_parquet(buf)
buf.seek(0)
__import__("boto3").client("s3").put_object(Bucket="openfused-abc123", Key="outputs/h3_agg.parquet", Body=buf.read())
result = "s3://openfused-abc123/outputs/h3_agg.parquet"
"""
```

Choose the H3 resolution based on desired granularity:

| Resolution | Avg cell area | Typical use |
|---|---|---|
| 5 | ~252 km² | Country/region |
| 7 | ~5.2 km² | City district |
| 8 | ~0.7 km² | Neighborhood |
| 10 | ~15 000 m² | Block |
| 12 | ~320 m² | Parcel / fine-grained point |

## Requirements

Requirements are configured per-environment via `fused env update -p <pkg>` and applied automatically to every `execute_code` call — no `requirements` field on the call itself.

```sh
fused env update prod -p duckdb -p polars
```

**AWS backend:** The `-p/--package` list drives the Docker image build (`image_build.packages`). Packages are pre-baked into the env's container image — nothing is pip-installed at invocation time. After changing packages, run `fused infra build-image` (builds + pushes the image and records its digest URI as `docker_image`), then `fused infra apply` to point the env's single `<prefix>container` Lambda function at the new image.

**Local backend:** The `-p/--package` list is **AWS-only** (drives the Docker image build). For the local backend, third-party dependencies belong to a project's `pyproject.toml` (managed with `uv add` inside the project directory). Without a project, execution runs in a bare stdlib-only venv — add the dependency to a project's pyproject.toml and run `uv sync` there.

> **Per-call `requirements` is backend-split.** Only the **local** backend honors a `requirements` list passed on the call (it materializes them into the run venv). On **Lambda/AWS** the container image is prebuilt, so **per-call `requirements` are ignored at execution time** — packages must already be baked into the env image (see AWS backend above). On the realtime/Fused runtime, passing `requirements` raises a clear error. The cache key still incorporates `requirements`, but on Lambda it does not change what is installed.

## Project venvs on the local backend

When executing against a **local** environment, pass `project=<name>` (MCP) or one of the two CLI selectors to run inside a project's `.venv`.

### MCP: `project` parameter

```python
# MCP — workspace-registered project only
mcp__openfused__execute_code(
    code="import pandas as pd; result = pd.__version__",
    project="taxi-pipeline",   # uses ~/.openfused/workspaces/default/taxi-pipeline/.venv
)
```

The `project` parameter is **workspace-registered only** and is **not available as a path** on the MCP tools. For path-based access use the CLI `--project-dir` option (see below).

### CLI: `--project NAME` (workspace mode)

```sh
fused code run myanalysis.py --project taxi-pipeline
```

- Resolves `<workspace>/taxi-pipeline/scripts/.venv/bin/python`.
- Venv must already exist (`uv sync` in `<project>/scripts/`).

### CLI: `--project-dir PATH` (ad-hoc / path mode)

```sh
# Run a skill-folder bundle anywhere on disk — no workspace registration needed
fused code run myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline

# Code test with path-addressed project
fused code test mymodule.py --test-file test_mymodule.py \
    --project-dir ~/.claude/skills/taxi-pipeline

# Dep-scan verify using the project dir's pyproject.toml (no backend execute)
fused code verify myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

- Reads `<dir>/openfused.toml` for the manifest (name defaults to directory basename).
- Materialises `<dir>/scripts/.venv` via `uv sync` on first run; subsequent runs reuse it.
- **Local-only**: if the resolved env is not `local`, the CLI raises a clear error.
- **Mutually exclusive with `--project`** on all three commands.
- Available on `code run`, `code test`, and `code verify` — **not** on the MCP `execute_code`/`test_code` tools.

What both project selectors do:
- Select the project's `.venv/bin/python` as the interpreter (all installed packages are available).
- Use a project-aware cache identity: `openfused-workflow-venv:<interpreter_id>:<lock_hash>`. Two calls with the same code but different lock files get separate cache entries.
- If the venv is **stale** (pyproject.toml or uv.lock is newer than pyvenv.cfg), the response includes a `warnings` list explaining which file changed — and **caching is skipped** for that call. Run `uv sync` inside `<project>/scripts/` to resolve.
- Local fan-out children (`_openfused.invoke` / `fused.map`) inherit the parent call's project interpreter, so workers see the same project dependencies as the coordinator — not the bare stdlib fallback.

**Sharp edges:**
- `project` / `--project` / `--project-dir` are **local-only**. Passing them to an AWS or Fused backend raises a clear error.
- `test_code` / `code test` **requires** `project` or `--project-dir` on the local backend. Without one of these, the call raises a guided error. pytest and coverage must be declared as dev dependencies in the project's `pyproject.toml`; add them in one step with `fused project add-dep <project> pytest coverage --dev` (runs `uv add --dev` + `uv sync`). They are not auto-installed in the project venv (unlike the AWS backend where they are pip-installed on first use).
- **Stale project venv → auto-reconciled.** When the project's `uv.lock` is newer than its `.venv` (e.g. after adding deps out-of-band), the local execute/test path runs `uv sync` once before executing, then proceeds with caching on. If the sync fails it falls back to running on the stale venv, skipping the cache and returning a `warnings` list. Set `OPENFUSED_NO_VENV_SYNC=1` to disable auto-reconcile (CI / locked-down). `fused doctor` reports staleness without syncing.
- Without a project selector, local execution runs in a bare stdlib-only venv. Third-party imports will fail.
- If the workspace project does not exist (`--project`), the backend raises a `ValueError` pointing at `fused project new <name>`. If the directory has no `openfused.toml` (`--project-dir`), the CLI raises a clear manifest-not-found error.

Only list packages not available in the base image / host interpreter. Common stdlib is always present; `boto3` is always present on AWS Lambda but may not be in a local venv (add it explicitly if needed).

## Reading secrets inside UDF code

Use `openfused.get_secret(name)` — a uniform accessor that works unchanged on
both AWS and the local backend with no extra dependency declaration. Never
interpolate secret values into the code string; that exposes them in logs and
tool call history.

Store the secret first (name must be prefixed with the environment's function
prefix, e.g. `openfused-`, so the Lambda execution role can read it):

```sh
fused secrets put openfused-my-password "s3cr3t"
```

Then read it inside the code:

```python
code = """
import openfused

secret = openfused.get_secret("openfused-my-password")

import psycopg2
conn = psycopg2.connect(password=secret, ...)
...
result = "done"
"""
```

`get_secret` raises `KeyError` if the secret does not exist — never returns
`None`. No `requirements` entry is needed; `fused` is injected into every
call directory automatically.

**AWS** — the shim reads Secrets Manager directly via boto3 inside the Lambda
(execution-role scoped to `openfused-*`). **Local** — the shim dispatches
through the host invoke broker; the project venv needs neither `fused` nor
`cryptography` installed.

## Tool call sequence for a typical analysis

1. `mcp__openfused__list_files` — find the input file
2. `mcp__openfused__get_file_schema` — confirm columns / row count before running heavy code
3. `mcp__openfused__execute_code` — run the analysis; write output to S3; set `result` to the output key
4. `mcp__openfused__get_file` — return a presigned URL for the output

## Parallel fan-out across partitions

When a task spans many partitions or files, don't loop sequentially. The right strategy depends on per-partition weight:

- **Light per-partition work** (counts, small aggregations) → a `ThreadPoolExecutor` inside a single `execute_code` call.
- **Heavy per-partition work**, or a partition that would OOM or exceed `lambda_timeout` → fan out to child Lambdas via the `_openfused` SDK or a coordinator that dispatches workers.

Both patterns use thread fan-out, `_openfused.invoke`, the coordinator/worker pattern, `monitor_concurrency_limit`, validating a worker before dispatch, batching oversized partitions, and avoiding recursion storms.

## Fused realtime backend constraints

The Fused realtime backend (`compute_mode="realtime"`, the default) has specific limitations when running code:

- **No arbitrary `requirements`** — the realtime runtime does not install pip packages at invocation time. Only packages pre-baked into the runtime image are available (plus stdlib and code injected via `Udf.headers`). Passing `requirements` raises a clear error pointing you to the AWS or local backend for arbitrary packages.
- **No `test_code`** — pytest harness is not available on the Fused runtime. Use the AWS or local backend to run tests.
- **Fused-native caching only** — result memoization uses Fused's own run cache, not fused's content-addressed cache. Pass `cache_max_age` (e.g. `"15m"`) to memoize a run on Fused's server; use `cache_refresh=True` to force a fresh execution. The `cache_clear` tool and `cache_object_key` parameter are not supported (raise a clear error); `cache_refresh` is the per-call escape hatch for stale results.
- **`input_files` staging** — files are uploaded via the files API to `fd://tmp` (the `staging_path` default) and passed as a mapping of original filename → staged `fd://` path to the UDF. For a **decorated UDF** (`@fused.udf def fn(...)`), the function must declare an `input_files` parameter. For a **synthesized UDF** (plain `result =` Python), `input_files` is an in-scope variable. Filenames with path separators, `..`, or leading slashes are rejected as unsafe.
- **Large and cached results work** — Fused delivers the result body via a presigned redirect (`x-fused-redirect`, used for both cached and large responses). With `large_result_delivery="presign"`, fused returns the redirect URL without downloading. With `large_result_delivery="inline"` (default), fused probes the size; results ≥ 5 MiB fall back to the redirect URL. Otherwise the data is downloaded and deserialized inline. UDF errors with a redirect present return `None` (error propagates). The data is returned as-is (no re-caching — Fused owns its run cache).
- **Batch mode (`compute_mode="batch`) not yet implemented** — selecting batch compute raises `NotImplementedError` with guidance.

## Monitoring

After each `execute_code` call, the response may include a `monitoring` key with runtime metrics. The shape differs by backend.

**AWS backend** — CloudWatch metrics for the Lambda function over the last 5 minutes:

```json
{
  "monitoring": {
    "poll_interval_s": 30,
    "snapshots": [
      {
        "function_name": "openfused-container",
        "window_minutes": 5,
        "note": "CloudWatch metrics lag ~1 min; this invocation may not yet be reflected.",
        "concurrent_executions_max": 1,
        "invocations": 3,
        "errors": 0,
        "throttles": 0,
        "duration_avg_ms": 450,
        "duration_max_ms": 800,
        "warnings": []
      }
    ]
  }
}
```

**Always check `warnings` before proceeding.** Warnings are emitted for:
- `concurrent_executions_max > baseline + monitor_concurrency_limit` — possible recursion runaway; stop and investigate before running more code
- `throttles > 0` — invocations were rejected due to concurrency limits
- `errors > 0` — function errors in the recent window (distinct from the current call's own error)

`monitor_concurrency_limit` (default `1`) raises the threshold for the concurrency warning above. Fanning out intentionally trips it, so set it to the fan-out count + 1.

**Local backend** — `monitoring` is accepted but returns no snapshots (there is no metrics source to poll on the host).

To skip monitoring (e.g. in tight loops where latency matters), pass `monitoring=false`.

While a long call runs, `execute_code` streams each monitoring snapshot to the MCP client as a live progress notification (in addition to the final `monitoring` key in the response). This is purely informational — the underlying execution is never affected if the client cannot receive updates.

## @fused.udf compatibility

Code that uses the `@fused.udf` decorator runs without modification inside `execute_code`. The handler injects a `fused` mock module into every execution directory, so no real `fused` package is required.

### How it works

The mock provides:

- **`@fused.udf`** — transparent decorator; the function is directly callable normally.
- **`@fused.udf(filename="worker.py")`** — same, but pins a default worker file for `.map()`.
- **`fused.load("worker")`** — returns a worker reference bound to a file (the `.py` is implied: `fused.load("worker")` loads `worker.py`). Call it (`worker(state="ak")`) to dispatch a single child Lambda, or use `.map()` to fan out. Not registered for auto-call. The file is not read until the worker is called or `.map()`'d.
- **`udf.map(items, filename=None, max_workers=16)`** — fans out to child Lambdas (see below).
- **`fused.run(udf_fn, **kwargs)`** — equivalent to `udf_fn(**kwargs)`; prefer calling directly.
- **`fused.Response(body, *, media_type, status_code=200, headers=None)`** and helpers **`fused.HTMLResponse` / `fused.PlainTextResponse` / `fused.JSONResponse`** — return one (as `result` or from a UDF) to set the HTTP content type/status/headers when the code is served via `code serve`. Any non-Response value is sent as JSON. Outside a serve context the body is just the return value.

```python
import fused

@fused.udf
def resolution_frame(resolution=10):
    import pandas as pd
    return pd.DataFrame({"res": [resolution]})

result = resolution_frame(resolution=8)   # direct call — no fused.run() needed
```

### Fan-out with `.map()`

`udf.map(items, filename, max_workers=16)` dispatches one child Lambda per item using
`_openfused.invoke()` under the hood, collecting results in submission order.

```python
import fused

worker = fused.load("count_state")  # loads count_state.py; worker(state=...) dispatches one child; .map() fans out

@fused.udf
def coordinator(bucket=BUCKET, prefix=PREFIX, max_workers=51):
    states = list_states(bucket, prefix)
    results = worker.map(
        [{"state": s} for s in states],
        max_workers=max_workers,
    )
    return {"total": sum(r["rows"] for r in results)}
```

`items` is an iterable of dicts; each dict becomes the kwargs for one child invocation.
The child's `@fused.udf` receives those kwargs via the auto-call mechanism.

`filename` resolution order:
1. `filename` argument to `.map()`
2. `filename` argument to `@fused.udf(filename=...)`
3. `"user_code.py"` (the current execution's file inside Lambda)

**Per-child caching.** `_openfused.invoke(filename, …, cache_max_age="0s")` takes
the same `cache_max_age` parameter as `execute_code`. Its default is **`"0s"`**:
a child caches only when its own `invoke(...)` opts in, **independently of the
parent's `cache_max_age`** — fanning out under a cached coordinator does not
implicitly cache the children.

### Auto-call behaviour

If the code defines a `@fused.udf` function but never assigns to `result`, the **last decorated function is called automatically** after the code block finishes. Arguments are loaded from `_openfused_args.json` in the working directory (populated by `_openfused.invoke()` kwargs) if that file exists; otherwise the UDF is called with no arguments.

```python
# No explicit result= needed — the UDF is auto-called with no args
import fused

@fused.udf
def compute():
    return 42
```

```python
# When invoked via _openfused.invoke("worker.py", x=10):
# _openfused_args.json contains {"x": 10}, so double_value(x=10) is called automatically.
import fused

@fused.udf
def double_value(x=0):
    return x * 2
```

### Rules

- **Direct call** — `udf(x=5)` works; no need for `fused.run(udf, x=5)`.
- **`result` and `@fused.udf` cannot coexist** — a script returns via a `result` variable *or* a registered `@fused.udf`, never both. Defining a `@fused.udf` and also assigning `result` (including `result = None`) is an **error**; the runner does not guess which was intended. Pick one return mechanism per script.
- **Only the last decorated function** is auto-called when multiple `@fused.udf` functions are defined.
- **Errors in the UDF** (wrong argument count, runtime exception) appear in `stderr` and `error` just like any other execution error.
- **`fused.py`** is a framework file and is not packed into child invocation zips; child Lambda invocations receive a fresh copy from the handler.

## What NOT to do

- Do not set `result` to a large DataFrame, dict, or list — serialize to Parquet/JSON and write to S3 instead
- Do not use `print` as a return mechanism — `stdout` is captured but not a structured return channel
- Do not import packages in `requirements` that are already in stdlib
- Do not run multiple unrelated analyses in one `execute_code` call — split them
- Do not fan out more than one level deep — workers must never invoke child Lambdas

## Verification, expectations, and testing

When verify is enabled on the resolved environment, `execute_code` accepts two quality parameters and may return a `verify` key in its response. The full security model — `verify_code`, the findings table, spec conformance, the audit log, `test_code`, and verify configuration — lives in the **fused-verify** skill; only the two `execute_code` parameters are covered here.

- **`spec`** — a natural-language description of intent. Claude checks the code against it before execution; a mismatch blocks the call. Required when the environment sets `require_spec`.
- **`expectations`** — a data-quality contract validated against the return value after execution. Violations are WARN-level and never block.

```python
execute_code(
    code="...",
    spec="Compute total revenue grouped by region from the input CSV.",   # optional
    expectations={                                                          # optional
        "expected_columns": [{"name": "region", "dtype": "object"},
                             {"name": "revenue", "dtype": "float64"}],
        "max_null_rate": 0.01,
        "row_count": {"min": 1, "max": 200},
        "bounds": {"revenue": {"min": 0}},
    },
)
```

Response shapes when verify is active:
- **Blocked:** `{"blocked": true, "error": "Execution blocked by security policy", "verify": {"findings": [...], "blocked": true}}`
- **Proceeded with warnings:** `{"return_value": "...", "verify": {"findings": [...], "blocked": false, "summary": {"warn": 2, "block": 0}}}`

To confirm behaviour rather than just safety, run a pytest suite inside the real Lambda with `test_code` — see **fused-verify**.

## Execution isolation & tenancy

Each `execute_code` call runs in a fresh subprocess under a unique working dir, so module state, monkeypatches, and files don't leak between calls. On the **AWS backend**, every compute function is additionally created with **Lambda tenant isolation mode**, and each call carries a *tenant id* so it runs in an execution environment dedicated to that tenant:

- The tenant id is the caller identity from `OPENFUSED_CALLER_NAME` (free-form names are sanitized to Lambda's allowed character set). When it's unset, all calls share a single placeholder tenant (`openfused-shared`).
- Set distinct `OPENFUSED_CALLER_NAME` values per caller to keep mutually-distrusting workloads on separate warm-container pools. This isolates **compute only** — it does not scope the IAM role, so data isolation still needs a bucket-scoped role.

## Resetting the compute backend

Call `mcp__openfused__infra_lambda_reset` (or `fused infra lambda-reset` from the CLI) to reset the resolved compute backend. Use this when:

- The backend is stuck in a broken state
- You need to force a fresh environment (e.g. after updating packages or handler logic)
- The local image cache or Lambda ARN cache has diverged from actual state

**AWS backend:** Deletes all Lambda functions for the resolved environment, clears the local ARN cache, and immediately recreates a fresh function. After reset, a fresh function is created immediately so the next `execute_code` call is warm. The IAM role, ECR repository, and S3 cache bucket are **not** affected.

**Local backend:** Clears the in-process venv ready-cache. No venvs are deleted from disk; the next `execute_code` call re-checks the on-disk markers (and rebuilds anything missing).

The MCP tool deletes every prefix-matched Lambda before recreating one, so it is registered only when the server is started with `--enable-infra` (and can be suppressed even then with `--disable-reset`). The `fused infra lambda-reset` CLI command is unaffected.

## Large results and result caching

`execute_code` writes large return values to S3 instead of stuffing them into
the 6 MB synchronous invoke payload (which would fail). When this happens the
response gains a `result_ref` (`{bucket, key, content_type, length}`):

- `large_result_delivery="inline"` (default) — the backend transparently
  downloads the spilled value, so `return_value` is exactly what the code
  returned.
- `large_result_delivery="presign"` — the backend skips the download and
  returns `return_value = '{"result_url": "<presigned URL>"}'` (~1 h TTL) plus
  the `result_ref`. Use this when the result is large enough that pulling it
  through the MCP boundary is itself the problem; fetch it on demand.

**Caching (`cache_max_age`).** Pass a duration (`"90s"`, `"15m"`, `"24h"`,
`"7d"`) to memoize the result. A later call with the **same code, requirements,
and inputs** returns the stored value without re-executing — a seconds-long
Lambda call collapses to a single S3 HEAD. `execute_code` defaults to `"1h"`
(ITEM-11856), so repeated calls memoize for an hour unless you override it; pass
`"0s"` to disable caching for live/non-deterministic code. (`test_code` stays
opt-in at `"0s"`.)

**When to cache.** Match `cache_max_age` to how often the underlying data changes:

| Query type | Suggested `cache_max_age` | Rationale |
|---|---|---|
| Historical/immutable S3 data (e.g. AIS, satellite imagery, archived logs) | `"7d"` or `"30d"` | Source data never changes; safe to cache indefinitely |
| Partition/schema discovery (which chunk covers a bounding box, column names) | `"24h"` | Layout is stable; re-check daily is sufficient |
| Iterative analysis over the same dataset in one session | `"1h"` | Avoids re-downloading the same large file for each follow-up query |
| Live/streaming data | `"0s"` (off) | Results change with each read |
| Code that calls `datetime.now()`, `random()`, or any non-deterministic API | `"0s"` (off) | Cache key does not capture runtime state |

**Practical pattern for large historical datasets** — cache the expensive load step, not the cheap aggregation:

```python
# Step 1: cache the filtered dataset (expensive — downloads a 500 MB parquet file)
execute_code(
    code=LOAD_AND_FILTER,   # reads S3, clips to bounding box, writes filtered parquet to cache bucket
    cache_max_age="7d",
    spec="...",
)

# Step 2: run aggregations against the cached output (cheap — small result set)
execute_code(
    code=AGGREGATE,   # reads the filtered parquet from Step 1
    cache_max_age="1h",
    spec="...",
)
```

If you ran the same query without `cache_max_age` earlier in a session, add `cache_refresh=True` on the first cached call to populate the entry from a fresh run.

- The key is a content hash of `(runner version, execution environment, code,
  input file bytes)`, scoped per environment — two environments never share
  entries even on a shared cache bucket. On **AWS** the environment component
  is the resolved container image **digest**, so re-pushing the same tag (e.g.
  `:latest`) invalidates prior entries.
- **Both backends**: caching works the same on AWS and the **local** backend
  (local stores the entry on its own filesystem and replays hits inline —
  no S3/presign). The local env component of the key is the venv identity
  (interpreter path + version + package set). `cache_clear` is wired for both.
- The response carries `cache: {hit, hash, object_key, age_s}`. On a hit,
  `stdout`/`stderr`/`duration_ms` are the **original** run's values (replayed);
  no `monitoring` snapshot is returned (nothing executed).
- **Volatility caveat:** the hash captures the *inputs shipped with the call*,
  never what the code reads at run time (S3 objects, secrets, `now()`,
  network). Pick a `cache_max_age` no longer than the staleness you can
  tolerate, and leave it at `"0s"` for code that reads live data. Pin
  requirement versions (`pandas==2.2.1`) for a reproducible cache identity.
- `cache_refresh=True` (requires `cache_max_age > "0s"`) bypasses the read,
  re-executes, and **rewrites** the entry — use it when you know the underlying
  data changed. `cache_refresh=True` with `cache_max_age="0s"` is rejected.
- `test_code` accepts the same `cache_max_age`/`cache_refresh`; outcomes +
  coverage are memoized and the test file is folded into the key.
- **Result formats.** A cached result is stored by kind: a `DataFrame`/
  `GeoDataFrame`/Arrow table as **Parquet** (directly queryable via
  `get_file_schema`/`pd.read_parquet` on the `result_ref`), a binary
  `fused.Response` as its **raw bytes** (a presigned GET returns the image/PDF
  verbatim), and any other value as JSON. The inline `return_value` is
  identical whether the call executed or hit the cache.

Reclaim cached/spilled bytes with `cache_clear(route?, object_key?, all?)`. The
default clears the current environment's scope; `object_key=K` (from a prior
`cache.object_key`) clears one object; `all=True` clears every environment's
cache objects (`results/`) plus un-scoped spill objects (`spill/`). It is not
destructive-gated but is always audited.

**Expiry vs. freshness.** The two object classes live under different prefixes
and have different lifetimes:

- `spill/` — one-shot artifacts written only when caching is off; read once via
  the returned `result_ref`, then garbage. A bucket lifecycle rule expires them
  after **1 day**.
- `results/` — content-addressed cache entries. Freshness is decided at read
  time by `cache_max_age`, *not* by S3 expiry; a lifecycle rule expires them
  after **30 days** purely as a storage backstop, so keep `cache_max_age` well
  under 30d. (Spilled large *cache* bodies live here too, under the entry's
  hash key — they are part of the cache, not separate spills.)

These lifecycle rules are provisioned on the cache bucket by `infra_apply`; see
the fused-infra skill.

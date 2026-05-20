---
name: fused-overview
description: Orientation to what Fused is and when to use it. Use when deciding whether to build something with Fused, structuring a new Fused project, or explaining to an agent what Fused offers as a Python execution and sharing platform.
---

# What is Fused — and when should you use it

Fused is a platform for running Python in the cloud, organized into projects and independently callable functions. The two core primitives are **canvases** and **UDFs**.

---

## The mental model

**Canvas = project.** A canvas is the container for a piece of work — equivalent to a repo or a folder. All UDFs in a canvas share the same permissions and access controls. When you want to control who can see or call something, you do it once at the canvas level.

**UDF = callable function with its own compute.** Each UDF (`@fused.udf def udf(...)`) is independently deployed and callable. It gets its own API endpoint, its own compute, and its own cache. You can call one UDF without touching any other.

```
canvas (project)
├── udf_a.py        → callable at /udf_a, own compute
├── udf_b.py        → callable at /udf_b, own compute
└── widget.json     → optional UI layer on top
```

UDFs within a canvas can call each other via `fused.load("udf_name")`, so you can compose them into pipelines while keeping each piece independently testable and callable.

---

## When to use Fused instead of a local script

| Situation | Use Fused? |
|---|---|
| Results need to be shared with others via a URL | ✓ |
| Multiple people or systems need to call the same function | ✓ |
| Work needs to run in parallel across many inputs | ✓ use `.map()` |
| Compute exceeds the local machine (memory, CPU, dataset size) | ✓ use `engine="medium/large"` |
| Work needs to persist and be callable after the session ends | ✓ |
| Building a dashboard or interactive UI on top of Python logic | ✓ |
| One-off analysis, no sharing, runs in seconds locally | — local script is fine |
| Needs interactive terminal input | — not supported |
| Single job that runs longer than 120 seconds | — split into smaller UDFs and use `.map()` |

The clearest signal: **if someone other than you needs to call it, or if it needs to still work tomorrow**, put it in Fused.

---

## What you get from this structure

**Each UDF is an API endpoint.** Once pushed, a UDF is callable via HTTP with parameters as query strings. No server to manage, no deploy pipeline — `fused canvas push` is the whole deploy step.

**Permissions live at the canvas level.** Set a canvas to private (author only), team (everyone in your org), or public. All UDFs inherit this. You don't manage access per-function.

**Results are cached automatically.** Fused caches UDF output for 14 days by default. Repeated calls with the same parameters return instantly. Override with `cache_max_age` on the decorator or `--no-cache` at call time.

**UDFs scale independently.** Each UDF has its own compute allocation. A heavy data-processing UDF and a lightweight lookup UDF in the same canvas don't interfere with each other.

**Secrets and integrations are resolved by the runtime.** `fused.secrets["KEY"]` and `fused.api.notion_connect()` etc. work automatically in deployed UDFs — no credential management in code.

---

## Parallelism and scale

This is one of the biggest advantages of structuring work as UDFs. Two levers:

### Run many jobs in parallel with `.map()`

Call any UDF across a list of inputs — each input spawns its own instance, all running concurrently:

```python
@fused.udf
def udf(item: str = ""):
    # process one item
    import pandas as pd
    return pd.DataFrame({"result": [item.upper()]})

# From another UDF or from Python:
pool = udf.map(["a", "b", "c", "d", "e"])
results = pool.df()       # collect all results into a DataFrame
pool.times()              # inspect per-job execution times
```

Design principle: **split a large job into many small UDFs rather than one big one.** A task that processes 100 items sequentially in 10 minutes becomes 100 parallel 6-second jobs. The 120-second per-job limit is easy to stay under when each UDF does one unit of work.

### Attach larger compute with `engine`

By default UDFs run on `small` (2 vCPU, 2 GB RAM). For memory-heavy or CPU-heavy work, specify a larger engine on the decorator:

```python
@fused.udf(engine="medium")
def udf():
    # 16 vCPU, 64 GB RAM available
    import pandas as pd
    ...

@fused.udf(engine="large")
def udf():
    # 64 vCPU, 512 GB RAM available
    ...
```

| Engine | vCPU | RAM | When to use |
|---|---|---|---|
| `small` (default) | 2 | 2 GB | Most tasks |
| `medium` | 16 | 64 GB | Large datasets, ML inference, heavy computation |
| `large` | 64 | 512 GB | Very large in-memory workloads |

Tradeoff: larger engines have a longer cold-start time. Use `small` by default; only upgrade when you've confirmed the bottleneck is memory or compute.

You can also specify engine at call time via `.map()`:

```python
pool = udf.map(inputs, engine="medium")
pool.wait()
```

### Combining both

Split + parallelize + scale:

```python
# Each chunk runs on medium compute, all in parallel
pool = process_chunk.map(chunks, engine="medium")
results = pool.df()
```

---

## How to structure a new project

1. **One canvas per project.** Don't put unrelated work in the same canvas — permissions and sharing apply to everything in it.
2. **One UDF per logical function.** If two things have different inputs, outputs, or scaling needs, they should be separate UDFs.
3. **Prefer many small UDFs over one large one.** Small UDFs can be parallelized with `.map()`, called independently, and are easier to debug. A UDF that does one thing is a good UDF.
4. **Keep each UDF under ~30–45 seconds.** The 120-second hard timeout applies per execution. Use `.map()` to parallelize across inputs rather than looping inside a single UDF.
5. **Add a widget if humans need a UI.** A `widget.json` alongside a UDF gives you an interactive panel in the Workbench — inputs, charts, maps, tables — without any frontend code.

---

## Constraints to know upfront

- **120s execution timeout** per UDF call — hard limit, not configurable
- **All imports must be inside the UDF function body** — module-level imports are not executed
- **No persistent in-memory state** between calls — treat each invocation as stateless; use external storage (Fused files, S3, Notion, etc.) for state
- **Canvas names: `[a-zA-Z0-9_]` only** — no hyphens or spaces; `feedback_pipeline` not `feedback-pipeline`
- **`fused run` executes the deployed version** — push before running to pick up local changes
- **`fused.secrets` raises `SecretKeyNotFound`** on missing keys, not `None`

---

## Worked example

A customer feedback pipeline that fetches meeting notes, extracts issues with Claude, and creates Notion tickets:

```
feedback_pipeline/        ← canvas (one set of permissions, one push)
├── run_pipeline.py       ← UDF: fetch + extract + dedup + create tickets
└── pipeline_widget.json  ← widget: URL input + results table
```

`run_pipeline` is independently callable (`fused run feedback_pipeline run_pipeline --url=...`), has its own compute, and the widget provides a browser UI for non-CLI users. Permissions are set once on `feedback_pipeline` — no per-UDF config.

---

## See also

- `fused:fused-cli` — pushing, running, and managing canvases from the CLI
- `fused:fused-udfs` — writing UDFs: structure, types, caching, performance
- `fused:fused-integrations` — connecting UDFs to Notion, Snowflake, S3, etc.
- `fused:canvas-toml` — canvas folder layout and `canvas.toml` format
- `fused:json-ui-schemas` — building widget UIs on top of UDFs

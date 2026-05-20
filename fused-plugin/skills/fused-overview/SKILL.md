---
name: fused-overview
description: Orientation to what Fused is and when to use it. Use when deciding whether to use Fused for a task, planning a new Fused project, or understanding Fused's capabilities as a remote Python execution platform.
---

# What is Fused — and when should you use it

Fused is a platform for running Python in the cloud, organized into projects and independently callable functions. The two core primitives are **canvases** and **UDFs**.

---

## The mental model

**Canvas = project.** A canvas is the container for a piece of work — equivalent to a repo or a folder. All UDFs in a canvas share the same permissions and access controls (private / team / public). Set it once; all UDFs inherit it.

**UDF = callable function with its own compute.** Each UDF (`@fused.udf def udf(...)`) is independently deployed, has its own API endpoint, its own compute, and its own cache. You can call one UDF without touching any other. Secrets and integrations (`fused.secrets`, `fused.api.notion_connect()`, etc.) are resolved automatically by the runtime — no credential management in code.

```
canvas (project)
├── udf_a.py        → own endpoint, own compute, own cache
├── udf_b.py        → own endpoint, own compute, own cache
└── widget.json     → optional browser UI on top
```

UDFs within a canvas call each other via `fused.load("udf_name")`, so you can compose them into pipelines while keeping each piece independently testable.

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
| Single job runs longer than 120 seconds | — split into smaller UDFs and use `.map()` |

The clearest signal: **if someone other than you needs to call it, or if it needs to still work tomorrow**, put it in Fused.

---

## Parallelism and scale

This is the biggest advantage of structuring work as UDFs rather than scripts.

### Run many jobs in parallel with `.map()`

Call any UDF across a list of inputs — each input spawns its own instance, all running concurrently:

```python
@fused.udf
def process_item(item: str = ""):
    import pandas as pd
    # ... do work on one item ...
    return pd.DataFrame({"result": [item]})

pool = process_item.map(["item_1", "item_2", "item_3", ...])
results = pool.df()     # collect all results into a DataFrame
pool.times()            # inspect per-job execution times
```

**Design principle: prefer many small UDFs over one large one.** A task that processes 100 items sequentially in 10 minutes becomes 100 parallel 6-second jobs. The 120s per-job limit is easy to stay under when each UDF does one unit of work.

### Attach larger compute with `engine`

By default UDFs run on `small`. For memory-heavy or CPU-heavy work, specify a larger engine on the decorator:

```python
@fused.udf(engine="medium")
def udf():
    # 16 vCPU, 64 GB RAM
    ...
```

| Engine | vCPU | RAM | When to use |
|---|---|---|---|
| `small` (default) | 4 | 10 GB | Most tasks |
| `medium` | 16 | 64 GB | Large datasets, ML inference, heavy computation |
| `large` | 64 | 512 GB | Very large in-memory workloads |

Tradeoff: larger engines have a longer cold-start. Use `small` by default; upgrade when you've confirmed memory or CPU is the bottleneck.

You can also override engine per `.map()` call:

```python
pool = process_item.map(inputs, engine="medium")
pool.wait()
results = pool.df()
```

---

## How to structure a new project

1. **One canvas per project.** Permissions and sharing apply to everything in it — don't mix unrelated work.
2. **One UDF per logical function.** If two things have different inputs, outputs, or scaling needs, they're separate UDFs.
3. **Prefer many small UDFs.** Small UDFs are parallelizable with `.map()`, independently callable, and easier to debug. Loop inside a UDF → can't parallelize. Split into UDFs → can.

---

## Constraints to know upfront

- **120s execution timeout** per UDF call — hard limit; split long work across UDFs
- **All imports must be inside the UDF function body** — module-level imports are not executed
- **No persistent in-memory state** between calls — use external storage (Fused files, S3, Notion, etc.) for state
- **Canvas names: `[a-zA-Z0-9_]` only** — no hyphens; `my_project` not `my-project`

---

## See also

- `fused:fused-cli` — pushing, running, and managing canvases from the CLI
- `fused:fused-udfs` — writing UDFs: structure, types, caching, performance
- `fused:fused-integrations` — connecting UDFs to Notion, Snowflake, S3, etc.
- `fused:canvas-toml` — canvas folder layout and `canvas.toml` format
- `fused:json-ui-schemas` — building widget UIs on top of UDFs

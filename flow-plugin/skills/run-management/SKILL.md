---
name: run-management
description: Read and write agent run records (and read per-run transcripts) in the OpenFused App store. The durable system of record for runs. Use when inspecting or persisting OpenFused agent run state — status, costs, prompts, transcripts.
disable-model-invocation: true
---

# run-management

The App run store exposed as live UDFs — the **durable system of record for run
records**. Reads and writes `~/.openfused/app/state.json` (run records) and reads
`~/.openfused/app/runs/<runId>.ndjson` (per-run transcripts). These UDFs own that
local store; an agent drives them over the local execution layer started with
`fused dev serve`.

## What this project is

Ten UDFs over the App run state — two reads and eight writes:

- `read` — `RunRecord` rows from `state.json` (`runs[]`).
- `transcript` — a single run's NDJSON event log (read-only on the hot path; the
  app appends it line-by-line as events stream).
- `create` — append a new run record (caller-supplied id), status `queued`.
- `mark_started` — promote a run `queued → started` at launch (non-terminal; does
  NOT stamp `finishedAt`). The one status write between `create` and `finish`.
- `finish` — stamp a terminal transition (`completed`/`failed`/`cancelled`) +
  `finishedAt`.
- `set_prompt` — update a queued run's stored prompt.
- `fail_started` — boot orphan recovery's sweep of live runs (`started` → `failed`).
- `cancel_queued` — boot orphan recovery's sweep of never-launched runs (`queued` →
  `cancelled`; they never ran, so they are cancelled, not failed).
- `bulk_seed` — restore run records + per-run transcripts **verbatim**
  (insert-if-absent, idempotent). The **first transcript WRITER** in this project.
- `delete_project` — purge a whole project's run records + their transcript files
  (the **first transcript DELETER**, on the project-delete path). Idempotent.

Every UDF touches the App files directly with stdlib; no third-party imports in
UDF logic.

## Division of labor — record vs effect

These UDFs own the **durable run record**. The app keeps the **in-memory
orchestration** that a sandboxed UDF physically cannot perform: spawning /
killing the agentbridge subprocess, the live SSE buffer
(`GET /api/runs/:id/events`), and the run queue. So a run's *effects* stay
app-side while its *record* is owned here. The `fused inloop` app routes its run
reads **and** writes through these UDFs over the shared `dev serve`
(`createRun`→`create`, `markRunStarted`→`mark_started`, `finishRun`→`finish`,
`setRunPrompt`→`set_prompt`, boot `recoverOrphans`'s two run sweeps→`fail_started`
+ `cancel_queued`).
Like the task UDFs, each write is a whole-document read-modify-write that
preserves every other noun, so `state.json` has three whole-document writers (the
task UDFs, the run UDFs, and the app's `save()` for the remaining nouns),
reconciled last-write-wins.

`transcript` stays read-only: the NDJSON log is appended line-by-line by the live
run as events stream, which is an app-side effect, not a record write. This
project reads that log back as a snapshot; live streaming stays the app's SSE
channel. The one transcript WRITER is `bulk_seed` (below): it restores whole
transcript files at seed/restore time (idempotent, skip-if-exists) — it never
participates in the live append path, so the hot-path read-only invariant holds.

## Access pattern

Start the local execution layer. `fused dev serve` binds a loopback server,
prints ONE JSON handshake line, then runs in the foreground:

```
fused dev serve
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}

# Export the origin + token from that handshake line:
ORIGIN=http://127.0.0.1:<port>
TOKEN=<token>

# read — POST to the SQL endpoint; {{read}} is backed by the read UDF
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=run-management" \
  -d '{"sql": "SELECT * FROM {{read}} WHERE taskId = '\''task_…'\''"}'

# transcript / writes — POST to the UDF endpoint (run-scoped or single-record
# results, not tabular)
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=run-management" \
  -d '{"udf": "transcript", "overrides": {"run_id": "run_…"}}'
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=run-management" \
  -d '{"udf": "finish", "overrides": {"id": "run_…", "status": "completed"}}'
```

Response shape: `{"data": <result>, "error": null}` on success;
`{"data": null, "error": "<message>"}` on failure.

## State files

The app directory is resolved per operation, highest precedence first:

1. The `app_dir` parameter on any operation (e.g. `create(..., app_dir="/path/to/app")`) — use this to run the skill standalone against your own store, no environment setup required.
2. The `$OPENFUSED_APP_DIR_STATE` env var when it names an app directory.
3. `~/.openfused/app` (default).

- Runs: `<app_dir>/state/runs.json`.
- Transcripts: `<app_dir>/runs/<runId>.ndjson` (one `RunEvent` per line).

Every operation (including `transcript` and `bulk_seed`) accepts the optional
`app_dir` string param; when omitted the env-var/default chain applies, so
existing callers are unaffected.

Records are camelCase JSON. Writes go through whole-document read-modify-write
(all top-level keys preserved) + atomic `tmp` + `os.replace`, matching the
Express app's `JSON.stringify(data, null, 2)` + `fs` writes byte-for-byte.

## RunRecord shape

The 13-field camelCase record the `read` UDF returns and the write UDFs produce:

`id`, `taskId`, `prompt`, `status`
(`queued`/`started`/`completed`/`failed`/`cancelled`), `createdAt`, `finishedAt`,
`errorMessage`, `errorFamily`, `retryNotBefore`, `summary`, `costUsd`, `usage`
(`{inputTokens, outputTokens, cachedInputTokens}` or null), `model`. A run is
`queued` from `create` until it launches; `mark_started` promotes it to `started`
(the only live state), then `finish` makes it terminal.

## Operations

All parameters arrive as strings. Empty string is the zero value for optional
params; for nullable record fields, empty string → JSON `null`.

### read

```
read(task_ids: str = "") -> list[dict]
```

Returns `RunRecord` dicts from `state.json`, oldest-first by `createdAt`
(mirrors the Express `listRuns`). `task_ids` — a JSON array string
(`'["t1","t2"]'`) or comma-separated list — filters to that SET of tasks' runs
(camelCase `taskId`); empty string returns all runs, an explicit `"[]"` returns
none. Callers pass exactly the task ids they render, so a future read optimisation
(caching/indexing keyed by the id set) needs no caller change. `get-one` is just
`SELECT * FROM {{read}} WHERE id = '...'`.

### transcript

```
transcript(run_id: str = "") -> list[dict]
```

Reads `<app_dir>/runs/<run_id>.ndjson` and returns the run's `RunEvent`
envelopes (`{runId, seq, type, payload}`) in file order. Empty `run_id`, a
missing file, or a `run_id` whose resolved path would escape `runs/` returns
`[]` — the path is confined to the real `runs/` directory before opening, since
`run_id` is caller-controlled. Torn trailing lines are skipped (the valid prefix
is preserved — mirrors `replayEvents`). This is a **snapshot**, refreshed by
re-resolving; live streaming stays the app's SSE channel.

### create

```
create(id: str = "", task_id: str = "", prompt: str = "") -> dict
```

Appends a new run with the **caller-supplied `id`** (the app mints `run_<hex>`
before persisting because it also keys an in-memory live buffer by that id — the
UDF does not mint one). `status="queued"`, `createdAt=now`, every other field
null. Returns the created record. Mirrors `createRun`.

### mark_started

```
mark_started(id: str = "") -> dict
```

Promotes a run's `status` to `"started"` (the launch transition). **Non-terminal:**
`finishedAt` is left untouched (only `finish` stamps it). Idempotent; returns the
updated record, or `{"ok": false, "error": "not found"}` for an unknown id. The
launcher calls this the moment `hub.run` fires, so a run reads `started` (live)
only while its process actually runs. Mirrors `markRunStarted`.

### finish

```
finish(id, status, error_message="", error_family="", retry_not_before="",
       summary="", cost_usd="", usage_json="", model="") -> dict
```

Patches a terminal transition onto an existing run and stamps `finishedAt=now`.
`status` is `completed`/`failed`/`cancelled`; the nullable fields take their
value or `null` when empty; `cost_usd` is parsed with `float()`; `usage_json` is
`json.loads`-ed into the `{inputTokens, outputTokens, cachedInputTokens}` object.
Returns the **updated record** (the app reads `finishedAt` off this response, so
no separate read is needed on the hot path). Missing run →
`{"ok": false, "error": "not found"}`. Mirrors `finishRun`.

### set_prompt

```
set_prompt(id: str = "", prompt: str = "") -> dict
```

Sets `prompt` on an existing not-yet-finished run; returns the updated record.
Missing run → `{"ok": false, "error": "not found"}`. Used when a queued resume
accumulates follow-ups. Mirrors `setRunPrompt`.

### fail_started

```
fail_started(error_message: str = "") -> dict
```

Boot orphan recovery's live-run sweep: sets every run currently `status=="started"`
to `status="failed"`, `finishedAt=now`, `errorMessage=error_message`. Returns
`{"runIds": [<ids it failed>]}` (an empty sweep returns `{"runIds": []}` and
writes nothing). Mirrors the started-run-sweep of `recoverOrphans`; the task-side
reconciliation stays app-owned (it routes through `_core.task-management`).

### cancel_queued

```
cancel_queued(error_message: str = "") -> dict
```

Boot orphan recovery's queued-run sweep: sets every run currently `status=="queued"`
(minted but never launched — its in-process queue died with the previous process) to
`status="cancelled"`, `finishedAt=now`, `errorMessage=error_message`. **Cancelled, not
failed** — it never ran. Returns `{"runIds": [<ids it cancelled>]}` (empty sweep →
`{"runIds": []}`, writes nothing). Boot redispatch re-mints a fresh queued run for the
still-`todo` task. Mirrors the queued-run-sweep of `recoverOrphans`.

### bulk_seed

```
bulk_seed(runs: str = "", transcripts: str = "") -> dict
```

Restores run records + per-run transcripts **verbatim** — the seed/restore
counterpart of `create`, used to seed the shipped pre-built showcase project's
run history on first boot. `runs` is a JSON **array** of full `RunRecord`s,
inserted into `runs.json` **insert-if-absent by `id`** (a run whose `id` already
exists is skipped — no duplicate, no overwrite; ids/timestamps/status are never
minted). `transcripts` is a JSON **object** `{ "<runId>": [<RunEvent>, …] }`;
each list is written to `runs/<runId>.ndjson` (one event per line, atomic
`tmp`+`os.replace`), **path-confined to `runs/`** (reusing `_transcript_path` —
a traversal-shaped id is skipped) and **skipped if the file already exists**. Both
params are JSON-encoded strings; `""`/missing → nothing to do. Returns
`{"runs": {"inserted": n, "skipped": m}, "transcripts": {"written": n, "skipped": m}}`.

This is the **first transcript WRITER** in run-management — but only at
seed/restore time. The live append path (events streaming during a run) stays an
app-side effect, and `transcript` stays a read; `bulk_seed` never writes a file
that already exists, so it cannot collide with a live run's log.

- These writes are **unconditional setters** (like `task-management`'s
  `update_status`): no state-machine validation in the UDF — the app gates
  legality before calling.
- UDF logic is stdlib-only; no imports from `openfused.*` (the exec sandbox
  shadows the package with a shim). Reach the App files directly.
- All params are strings.

### delete_project

```
delete_project(project: str = "", task_ids: str = "") -> dict
```

Purges a whole project from the run store: drops the project's run records and
deletes each removed run's per-run transcript `<app_dir>/runs/<runId>.ndjson`.
This is the **first destructive write op** in run-management (and the **first
transcript DELETER**) — on the cross-skill project-delete path.

**Matching.** Run records carry no `project` (the `create` UDF stamps only
`taskId`; only `bulk_seed`-restored runs may carry one), so a run is removed if
EITHER its `taskId` is in `task_ids` — a JSON-encoded list of the project's
deleted task ids, passed by Flow from `task-management.delete_project`'s
`deletedTaskIds` (**the real path**) — OR `project` is non-empty and
`run["project"]` matches (the `bulk_seed`-restored fallback). Transcript deletion
REUSES the `runs/`-confined `_transcript_path` helper, so a traversal-shaped run
id can never remove a file outside `runs/` (it counts as skipped).

**Resumable ordering.** Under the `runs` flock, transcript `.ndjson` files are
deleted FIRST and the pruned `runs.json` is written LAST. The run record is the
recovery anchor: a crash after some transcripts are gone but before the prune
leaves every record intact, so a rerun (same `task_ids`) re-finds them and cleans
the remaining transcripts. Pruning first would orphan any not-yet-deleted
transcript. Idempotent: both `project` and `task_ids` empty, or no runs match,
returns zero counts and writes nothing; a missing transcript file counts as
skipped. Returns an ack:

```json
{ "runsRemoved": 3, "transcriptsRemoved": 2 }
```

`transcriptsRemoved ≤ runsRemoved` — a removed run whose `.ndjson` was already
absent (or whose id resolved outside `runs/`) is skipped, not counted.

## Rendering as a `sql-table` widget

The `read` UDF is enough to render the run log as a table — no app run store, no
other UI. A saved `sql-table` widget reads through `{{_core.run-management.read}}`,
so a single JSON-UI node gives you a sortable / filterable grid over the live
runs. (`transcript` is run-scoped and nested rather than tabular, so it has no
table widget — reach it through the UDF endpoint.)

The config ships **inside the wheel** as a saved widget of this project, at
`run-management/widgets/runs_table.json`. It materializes alongside the UDFs to
`~/.openfused/core/run-management/widgets/runs_table.json`, so it is available on
first run with no authoring step — open it with:

```bash
fused widget open ~/.openfused/core/run-management/widgets/runs_table.json
```

The shipped config:

```json
{
  "type": "sql-table",
  "props": {
    "title": "Runs",
    "sql": "SELECT id, taskId, status, model, costUsd, createdAt, finishedAt FROM {{_core.run-management.read}} ORDER BY createdAt DESC",
    "sortable": true,
    "filterable": true
  }
}
```

The projection drops the bulky `prompt`/`summary` columns for readability; widen
or filter the `SELECT` to taste (`SELECT *` returns every `RunRecord` field, incl.
the nested `usage` object).

> **Where it resolves.** The `{{_core.*}}` cross-project ref needs an `_core`
> resolve context, which today means the In-Loop app's dev serve
> (`fused dev serve` / `fused inloop`). The deployed-serve bundle has no
> `_core` resolve context, so a public URL is not supported for this widget.

## Layout (skill-folder convention)

```
scripts/
├── pyproject.toml          # project deps (duckdb/pandas/pyarrow for SQL resolver)
├── read/                   # {main.py, spec.md}
├── transcript/
├── create/
├── mark_started/
├── finish/
├── set_prompt/
├── fail_started/
├── cancel_queued/
├── bulk_seed/
└── delete_project/
```

Source lives in the wheel under `fused/_core/run-management/` (read-only).
The local-backend venv materializes at
`~/.openfused/core/run-management/scripts/.venv` on first startup. Adding a new
op = add `scripts/<name>/{main.py,spec.md}`.

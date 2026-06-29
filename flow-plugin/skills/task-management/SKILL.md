---
name: task-management
description: Read, create, assign, and re-status tasks in the OpenFused App task store (~/.openfused/app/state.json) through live UDFs, and render the standalone task-board widget. Use when working with OpenFused tasks, the kanban/task board, or the app's task state.
disable-model-invocation: true
---

# task-management

The App task store exposed as live UDFs. These UDFs own the local task store at
`~/.openfused/app/state.json`; an agent drives them over the local execution
layer started with `fused dev serve`.

## What this project is

Ten UDFs over the App state file: six that read/mutate task records (`read`,
`create`, `assign`, `update_status`, `set_blocked_by`, `delete`), two that
manage comments (`list_comments`, `add_comment`), one that seeds whole
collections verbatim (`bulk_seed`), and one that purges a whole project's tasks +
comments (`delete_project`). Every UDF touches `state.json` directly with
stdlib; no third-party imports in UDF logic.

The split is: **read via SQL** (any query over `{{read}}`, via the `/api/exec/sql`
endpoint), **write via UDF** (any mutation, via the `/api/exec/udf` endpoint).
Both endpoints are addressed with `?t=<token>&workspace=_core&project=task-management`
— see the access pattern below.

## Access pattern

Start the local execution layer. `fused dev serve` binds a loopback server,
prints ONE JSON handshake line, then runs in the foreground:

```
fused dev serve
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}

# Export the origin + token from that handshake line:
ORIGIN=http://127.0.0.1:<port>
TOKEN=<token>

# Read — POST to the SQL endpoint; {{read}} is backed by the read UDF
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=task-management" \
  -d '{"sql": "SELECT * FROM {{read}} WHERE project = '\''my-project'\''"}'

# Write — POST to the UDF endpoint
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=task-management" \
  -d '{"udf": "create", "overrides": {"project": "my-project", "title": "hello"}}'
```

Response shape: `{"data": <result>, "error": null}` on success;
`{"data": null, "error": "<message>"}` on failure.

The two endpoints differ in how `data` is shaped:

- **UDF endpoint** (`/api/exec/udf`) — `data` is the UDF's return value directly
  (a record dict, an ack dict, or a list). Parse it as documented per op below.
- **SQL endpoint** (`/api/exec/sql`) — `data` is a **per-query envelope keyed by
  query id**, not the row list. A single query lands under `q0`:
  `{"data": {"q0": {"columns": [...], "rows": [<task>, ...]}}, "error": null}`.
  The task records are at **`data.q0.rows`** (column names at `data.q0.columns`).
  Read them with `data["q0"]["rows"]`, not `data` directly.

> Note: some environments intercept raw `curl` (e.g. a context-mode hook that
> redirects it). If `curl` is blocked, issue the same POST from whatever
> sandboxed-exec tool is available — the request body and response shape are
> identical.

## State file

Path resolution, highest precedence first:

1. The `app_dir` parameter on any operation (e.g. `create(..., app_dir="/path/to/app")`) — use this to run the skill standalone against your own store, no environment setup required.
2. The `$OPENFUSED_APP_DIR_STATE` env var when it names an app directory.
3. `~/.openfused/app` (default).

State lives under `<app_dir>/state/`. Records are camelCase JSON, written with
`indent=2, ensure_ascii=False`, via atomic `tmp + os.replace`. Every operation
accepts the optional `app_dir` string param; when omitted the env-var/default
chain applies, so existing callers are unaffected.

Two-writer last-write-wins clobber is accepted in this POC (locking is out of
scope). The exec runtime injects an `fused` shim that shadows the real
package, so UDFs reach `state.json` directly.

## Operations

All parameters arrive as strings. Empty string is the zero value for optional
params. Missing-task responses return `{"ok": false, "error": "not found"}`.

### read

```
read(project: str = "") -> list[dict]
```

Returns tasks from `state.json`, newest-first by `createdAt`. `project` filters
to one project slug; empty string returns all projects.

SQL shorthand: `SELECT * FROM {{read}}` (no `project` override needed; pass an
`overrides: {"project": "..."}` to scope to one project, or filter in SQL).

Columns returned (via the SQL endpoint, under `data.q0`): `id`, `project`,
`number`, `title`, `description`, `status`, `agentId`, `createdBy`, `createdAt`,
`updatedAt`, `parentId`, `workMode`, `blockedBy`, `runs`, plus the derived
`isLive` (bool) and `liveRunCount` (int) live-run rollups.

### create

```
create(
    project: str = "",
    title: str = "",
    description: str = "",    # defaults to title when empty
    status: str = "pending",  # "pending" or "todo"
    parent_id: str = "",      # empty → null parentId
    created_by: str = "user",
    work_mode: str = "standard",
) -> dict
```

Mints a new `task_<12hex>` id, auto-numbers within the project, appends to
`state.json`, returns the full 13-field camelCase record.

### assign

```
assign(id: str = "", agent_id: str = "") -> dict
```

Sets `agentId` on the task and promotes `pending → todo`. Returns the updated
record, or the not-found ack.

### update_status

```
update_status(id: str = "", status: str = "") -> dict
```

Sets `status` unconditionally (`pending`, `todo`, `in_progress`, `completed`,
`failed`, `cancelled`). Returns the updated record.

### set_blocked_by

```
set_blocked_by(id: str = "", blocked_by: str = "") -> dict
```

Replaces the `blockedBy` list on the task. `blocked_by` accepts a JSON array
string (`'["t1","t2"]'`) or a comma-separated string (`"t1,t2"`); empty string
sets `blockedBy: []`. Returns the updated record.

### delete

```
delete(id: str = "") -> dict
```

Hard-deletes the task and all transitive descendants. Cascades to `runs`,
`comments`, `inbox`, `cards`, `costEvents`. Scrubs deleted ids
from remaining tasks' `blockedBy`. Returns an ack:

```json
{
  "deletedTaskIds": ["..."],
  "runsRemoved": 0,
  "commentsRemoved": 0,
  "inboxRemoved": 0,
  "cardsRemoved": 0,
  "costEventsRemoved": 0
}
```

### list_comments

```
list_comments(task_id: str = "") -> list[dict]
```

Returns comments for `task_id`, oldest-first by `createdAt`. Empty list when
`task_id` is empty or no comments match.

### add_comment

```
add_comment(task_id: str = "", author: str = "", body: str = "", kind: str = "", widget: str = "") -> dict
```

Appends a new `cmt_<12hex>` comment to `state.json`. Returns the core 5-field
record: `{id, taskId, author, body, createdAt}`. A non-empty `kind` (e.g.
`notify`, marking a `notify_user` FYI the inbox Updates feed surfaces) and a
non-empty `widget` (a JSON-UI
config JSON string, parsed and stored as the object) are added **only when set**,
so a plain thread `note` stays byte-identical to the pre-Phase-4 5-field shape.

### bulk_seed

```
bulk_seed(tasks: str = "", comments: str = "") -> dict
```

Inserts task + comment records **verbatim** — the restore/seed counterpart of
`create`. `tasks`/`comments` are **JSON-encoded array strings** of full records
(the all-strings boundary; empty string / missing → nothing to do). Each record
is written exactly as given (preserving `id`/`number`/`createdAt`/`updatedAt`/
`agentId`/`status`/`parentId`/`blockedBy`); nothing is minted. It is
**idempotent by `id`** — a record whose `id` already exists is skipped, never
duplicated or overwritten. Writes the `tasks` and `comments` collections (each
under its own flock), and returns the per-collection counts:

```json
{
  "tasks": { "inserted": 6, "skipped": 0 },
  "comments": { "inserted": 3, "skipped": 0 }
}
```

This is the only supported way to seed app-state from host Python — seeding goes
through this UDF, never a direct file write.

### delete_project

```
delete_project(project: str = "") -> dict
```

Purges a whole project from the task store: removes every task whose `project`
matches (by `project` directly — an id-less matching task is removed too), and
every comment on those tasks (comments carry no `project`, so they join via
`taskId`). Scrubs the removed ids from every surviving task's `blockedBy` (mirrors
the single-task `delete`), so a cross-project task blocked on a deleted task does
not stay stuck. The task-management half of the cross-skill project-delete
cascade — it touches ONLY `tasks` + `comments` and leaves `runs`/`cards`/
`costEvents` to their owners (`run-management` / `feedback-management` / Flow).
Idempotent: an empty/whitespace `project`, or one with no tasks, returns zero
counts and writes nothing. Returns an ack:

```json
{
  "deletedTaskIds": ["task_abc", "task_def"],
  "tasksRemoved": 2,
  "commentsRemoved": 3
}
```

`deletedTaskIds` is the sorted list of removed task ids — Flow uses it to drive
per-task cleanup (`mcp/<taskId>.json`, sessions) outside this UDF.

## Rendering as a `task-board` widget (standalone)

These UDFs are enough to drive the `task-board` widget on their own — no app
task store, no reserved `__openfused_tasks` built-ins, no other UI. The widget
reads through `{{_core.task-management.read}}` and writes through this project's
CRUD UDFs (`update_status` / `create` / `assign`) directly, so a single JSON-UI
node gives you a live list / kanban / tree over `state.json`.

The config ships **inside the wheel** as a saved widget of this project, at
`task-management/widgets/task_board.json`. It materializes alongside the UDFs to
`~/.openfused/core/task-management/widgets/task_board.json`, so it is available
on first run with no authoring step — open it with:

```bash
fused widget open ~/.openfused/core/task-management/widgets/task_board.json
```

The shipped config:

```json
{
  "type": "task-board",
  "props": {
    "project": "all",
    "sql": "SELECT * FROM {{_core.task-management.read?rev=$ofTasksRev}}",
    "defaultView": "board",
    "defaultGroupBy": "status"
  }
}
```

How the seams map onto this project's UDFs:

- **Read** — `props.sql` resolves `{{_core.task-management.read}}`, which returns
  the seam-① row columns (`id`, `project`, `number`, `title`, `description`,
  `status`, `agentId`, `createdBy`, `createdAt`, `updatedAt`, `parentId`,
  `blockedBy`). The `?rev=$ofTasksRev` kwarg is an opaque re-resolve nonce the
  `read` UDF ignores; the board bumps it after each write to refetch
  (mutate-then-refetch). An override may add a `WHERE` / projection but **must**
  keep both the seam-① columns and the `?rev=$ofTasksRev` kwarg.
- **Drag-to-change-status** → `_core.task-management.update_status` `{id, status}`
  (a drag into the `cancelled` lane is a `move` to `status: "cancelled"`). Only
  `pending↔todo` and cancel are hand-settable; every other lane is reached by an
  agent run, so other drops snap back.
- **Create** → `_core.task-management.create` `{id, project, title, description}` (the
  composer's prompt maps to `title`; the client `id` makes retries idempotent —
  get-or-create). v1 writes the row only — it does not
  dispatch an agent run. The `create` UDF takes no `agentId`; an assignee picked
  in the composer is applied by a chained `_core.task-management.assign` call.
- **Assign / reassign** → `_core.task-management.assign` `{id, agent_id}`.

Scope to one project by setting `"project": "<slug>"` and filtering in the read
SQL (`... WHERE project = '<slug>'`).

> **Where it resolves.** The board needs `_core.*` cross-project refs to resolve.
> That works on every **local** surface — `fused widget open`
> / the parley (dev serve's directory-addressed mode injects the built-in `_core`
> shared root) and the app's dev serve (`fused dev serve` / `fused inloop`).
> Only the **deployed-serve** bundle has no `_core` resolve context (no daemon),
> so the task-board renders "unavailable" there.
>
> **Not yet wired through `_core`:** the `update_status`/`create` ops above are
> live; assignee-on-create, delete, assign, blocked-by, and comments are not yet
> reachable from the widget (use the UDF endpoint directly for those).

## Layout (skill-folder convention)

```
scripts/
├── pyproject.toml          # project deps (duckdb/pandas/pyarrow for SQL resolver)
├── read/
│   ├── main.py
│   └── spec.md
├── create/
│   ├── main.py
│   └── spec.md
├── assign/ …
├── update_status/ …
├── set_blocked_by/ …
├── delete/ …
├── list_comments/ …
├── add_comment/ …
├── bulk_seed/ …
└── delete_project/ …
```

Source lives in the wheel under `fused/_core/task-management/` (read-only).
The local-backend venv materializes at `~/.openfused/core/task-management/scripts/.venv`
on first startup. Adding a new op = add `scripts/<name>/{main.py,spec.md}` and
re-register in `openfused.toml`.

## Conventions

- UDF logic is stdlib-only; no imports from `openfused.*` (the exec sandbox
  shadows the package with a shim). Reach `state.json` directly.
- All params are strings; parse non-string inputs (e.g. `blocked_by`) inside the
  UDF before use.
- Writes are atomic: `tmp + os.replace` only; never write directly to
  `state.json`.

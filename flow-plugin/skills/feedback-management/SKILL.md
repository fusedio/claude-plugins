---
name: feedback-management
description: Read AND write interaction cards — the typed, idempotent, resolvable HITL decisions an agent posts into a task thread — in the OpenFused App state store (~/.openfused/app/state.json) through live UDFs. The system of record for interaction cards. Use when working with OpenFused interaction cards, the inbox decision feed, or the app's feedback state.
disable-model-invocation: true
---

# feedback-management

The App's **interaction-card** store exposed as live UDFs — the **durable system
of record for interaction cards**. Reads AND writes `~/.openfused/app/state.json`.
These UDFs own that local store; an agent drives them over the local execution
layer started with `fused dev serve`.

## What this project is

The system of record for **interaction cards** — the typed, idempotent,
resolvable human-in-the-loop request an agent posts into a task thread — and the
home of the **inbox view** (a derived cross-task feed, not a fourth store). This
is the fifth `_core` project, joining
task / run / secrets / agent-roster management. The other feedback primitive, the
**`comment`** (every non-blocking note, incl. a `notify_user` FYI), is owned by the
`add_comment` UDF in **`_core.task-management`** — the `inbox_view` here reads
those comments from the one shared
`state.json` (overview F1), so no cross-project call is needed.

> **Phase 1 — system of record for cards.** Both the **read** side
> (`list_cards`, `get_card`, `list_open_cards`) and the **write** side
> (`create_card`, `resolve_card`, `cancel_task_cards`, `delete_project`) live here. The app's
> card store is now a **thin async client** over these
> UDFs — the app no longer writes `state.json.cards`
> directly. The per-effect 422 resolve VALIDATION + the resolve input →
> `{action, params}` `result` MAPPING still live in the app's card routes; the write
> UDFs are dumb persisters. (`cancel_card` is gone — a wake-bearing `create_card`
> supersedes the task's open ask in its place.)

> **The inbox is a derived view (Phase 5) + notify is a comment (Phase 4).** The
> `inbox_view` read UDF assembles the human inbox feed (`{items, pending}`) from the
> one shared `state.json` (overview F1) — there is **no stored `inbox[]` array**
> (retired): the pending wake-bearing card `question` projection (`reply` /
> `approval_gate`) + the **work-product review cards** (the
> `effect == "review_work_product"` cards, projected as `type:"message"` Updates
> rows carrying `sourceCardId` + the `card`) + the **`notify` comments** (the
> Phase-4 `notify_user` → comment swap, projected as Updates `message` rows) +
> **derived** completion/failure (from run + task status; no longer stored) +
> pending-triage tasks. The Express `GET /api/inbox` / `GET /api/projects/:name/inbox`
> routes are thin callers of the `inboxView` client; the run lifecycle
> does not mint `completion`/`failure` inbox items, `notify_user` writes a `notify`
> comment via `add_comment` (not a stored `message`), and work-product review is a card
> (not a stored `message`). A human dismiss/respond on a derived item / notify comment
> appends its synthetic id to the flat `dismissedFeedbackKeys` set (the view excludes
> acked ids) — not a tombstone row.

Every UDF touches `state.json` directly with stdlib; no third-party imports in
UDF logic.

The split is: **read via SQL or UDF** (`{{list_cards}}` / `{{list_open_cards}}`,
or the `get_card` / `inbox_view` UDFs), **write via UDF** (`create_card` /
`resolve_card` / `cancel_task_cards` / `delete_project`). Reads go via the `/api/exec/sql` endpoint
and writes via the `/api/exec/udf` endpoint, both addressed with
`?t=<token>&workspace=_core&project=feedback-management` — see the access pattern
below.

## Access pattern

Start the local execution layer. `fused dev serve` binds a loopback server,
prints ONE JSON handshake line, then runs in the foreground:

```
fused dev serve
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}

# Export the origin + token from that handshake line:
ORIGIN=http://127.0.0.1:<port>
TOKEN=<token>

# Read — POST to the SQL endpoint; {{list_cards}} is backed by the list_cards UDF
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=feedback-management" \
  -d '{"sql": "SELECT * FROM {{list_cards}} WHERE taskId = '\''task_abc'\''"}'

# Read a single card — POST to the UDF endpoint
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=feedback-management" \
  -d '{"udf": "get_card", "overrides": {"id": "card_abc123"}}'

# Write — POST to the UDF endpoint; payload/result travel as JSON strings
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=feedback-management" \
  -d '{"udf": "create_card", "overrides": {"project": "p", "task_id": "task_abc", "effect": "reply", "continuation_policy": "wake_assignee", "payload": "{\"widget\":{\"type\":\"text\"}}", "source_run_id": "run_x"}}'
```

Response shape: `{"data": <result>, "error": null}` on success;
`{"data": null, "error": "<message>"}` on failure.

## State file

Path resolution, highest precedence first:

1. The `app_dir` parameter on any operation (e.g. `create_card(..., app_dir="/path/to/app")`) — use this to run the skill standalone against your own store, no environment setup required.
2. The `$OPENFUSED_APP_DIR_STATE` env var when it names an app directory.
3. `~/.openfused/app` (default).

State lives under `<app_dir>/state/`. Records are camelCase JSON, written with
`indent=2, ensure_ascii=False`, via atomic `tmp + os.replace`. Every operation
accepts the optional `app_dir` string param; when omitted the env-var/default
chain applies, so existing callers are unaffected.

This project owns the `state.json.cards` array — both reads and writes. The read
UDFs read the `InteractionCardRecord` raw (no schema reconstruction) so they
preserve every on-disk field, and the write UDFs build records in exactly that
shape. Each write is a whole-document
read-modify-write that preserves every other noun, so `state.json` has multiple
whole-document writers (the task UDFs, the run UDFs, these card UDFs, and the
app's `save()` for the remaining nouns), reconciled **last-write-wins**.
The app's card store is now a thin async client; it
does not write `cards[]` directly.

## Operations

All parameters arrive as strings. Empty string is the zero value for optional
params. Missing-card responses return `{"ok": false, "error": "not found"}`.

### list_cards

```
list_cards(task: str = "") -> list[dict]
```

Returns interaction-card records for `task`, **oldest-first by `createdAt`**
(mirrors `listCards`). Empty `task` returns all cards across all
tasks.

SQL shorthand: `SELECT * FROM {{list_cards}}` (filter in SQL, or pass an
`overrides: {"task": "..."}` to scope to one task).

### get_card

```
get_card(id: str = "") -> dict
```

Returns the single card record for `id` (mirrors `getCard`), or
the not-found ack `{"ok": false, "error": "not found"}` for an unknown/empty id.

### list_open_cards

```
list_open_cards(project: str = "") -> list[dict]
```

Returns the **inbox decision-half feed**: every `pending` card whose
`continuationPolicy` would wake the assignee (`wake_assignee`), across all
effects, **oldest-first by `createdAt`**. The `inbox_view` UDF reads this
(narrowing it — dropping `review_work_product` cards — for the inbox `question`
projection) — the projection lives server-side in the UDF, so there is no TS
pending-question wrapper. A `none`-policy card never blocks and is excluded. Empty
`project` returns the open cards across all projects.

### create_card

```
create_card(project, task_id, effect, continuation_policy, idempotency_key,
            summary, payload, created_by, source_run_id) -> dict
```

Mints a fresh `pending` card and appends it (mirrors `createCard`
+ the route's §7 idempotency lookup). `payload` (the `{widget, effectArgs?}`
object) arrives **JSON-encoded** and is parsed into the stored object. Empty
`continuation_policy` → `wake_assignee`; the nullable string fields
(`idempotency_key`/`summary`) read `"" → null`; `created_by` is stored verbatim.
The minted card has `status="pending"`, `result=null`, `resolvedBy=null`,
`resolvedAt=null`, `createdAt=now`. **Supersede:** a wake-bearing create
(`continuation_policy != "none"`) first sets every pending wake-bearing card on
the same `(project, taskId)` to `status="superseded"`, `result=null` — the re-ask
replaces the open ask (this is what replaced the removed `cancel_card`).
Non-blocking (`none`-policy) cards are exempt. **Idempotency (§7):** when
`idempotency_key` is set and a card with the same `(project, taskId, key)`
already exists, the UDF returns that existing card **unchanged** (writes nothing,
supersedes nothing); `sourceRunId` is excluded from the equivalence concern. The
200-return-existing vs 409-conflict equivalence decision stays in the app's card
routes. See `create_card/spec.md`.

### resolve_card

```
resolve_card(id, status, result, resolved_by) -> dict
```

The single guarded `pending → terminal` flip (mirrors `resolveCard`,
§4.6). The terminal `status` is one of `answered` / `superseded` / `cancelled`.
`result` (the generic `{action, params}`) arrives **JSON-encoded** (empty →
`null`). Guards on `status == "pending"`: a card that is unknown or already
terminal returns `{"ok": false, "error": "not found"}` / `{"ok": false, "error":
"already resolved"}` and writes nothing (the caller maps that to a 409). On
success sets `status`/`result`/`resolvedBy`/`resolvedAt=now`. **The UDF is a dumb
persister** — the per-effect 422 VALIDATION + the resolve input → `{action,
params}` `result` MAPPING stay in the app's card routes. See `resolve_card/spec.md`.

### cancel_task_cards

```
cancel_task_cards(task) -> list[dict]
```

Task-cancel cascade: sweeps EVERY `pending` card on `task` to `cancelled`
(no result, no wake) in ONE whole-document write (mirrors
`cancelTaskCards`, §5.1). Returns the cancelled records; an empty
sweep returns `[]` and writes nothing. See `cancel_task_cards/spec.md`.

### delete_project

```
delete_project(project: str = "") -> dict
```

Project-delete cascade: removes EVERY interaction card (any status — `pending`
and terminal alike) whose `project` matches, in ONE whole-document write — the
feedback-management half of the cross-skill project-delete path. Idempotent: an
empty/whitespace `project`, or one with no cards, returns `{"cardsRemoved": 0}`
and writes nothing. Leaves the flat `dismissedFeedbackKeys` set alone (a dangling
entry for a deleted project is harmless). Returns `{"cardsRemoved": <int>}`. See
`delete_project/spec.md`.

### inbox_view

```
inbox_view(project: str = "") -> {"items": list[dict], "pending": list[dict]}
```

The **inbox view** (Phase 5) — the derived cross-task human feed, returning the
SAME `{items, pending}` shape the Express inbox routes return (so the UI is
unchanged). Reads the one shared `state.json` (overview F1) and assembles five
sources — there is **no stored `inbox[]` array** (retired): pending wake-bearing
cards whose `effect` is `reply` / `approval_gate` projected as read-only
`question` views (carrying `sourceCardId` + the full `card`); the **work-product
review cards** (pending cards whose `effect == "review_work_product"`, projected
as `type:"message"` Updates rows carrying `sourceCardId` + the full `card` so the
UI renders the interactive card); **`notify` comments** (the Phase-4 `notify_user`
→ comment swap, projected as `type:"message"` Updates rows keyed on the comment id);
**derived** `completion`/`failure` items from each task's latest terminal run + task
status (no longer stored — synthetic id `derived:<type>:<runId>`); and pending-triage
tasks (`pending` list). Empty `project` is the global feed. A human dismiss/respond on
a derived item OR a notify comment (neither has a stored row) appends its
synthetic/comment id to the flat `dismissedFeedbackKeys` set; the view excludes acked
ids so they do not re-appear. See `inbox_view/spec.md`.

The `InteractionCardRecord` — the typed, idempotent, resolvable
HITL request:

| Field | Type | Notes |
|---|---|---|
| `id` | str | `card_<12hex>` — app-minted, stable, opaque |
| `project` | str | Project slug |
| `taskId` | str | Task the card was posted into |
| `effect` | str | The resolve-time behaviour selector: `reply` / `approval_gate` / `review_work_product` (the closed set; never agent-invented) |
| `status` | str | `pending` (only non-terminal) / `answered` / `superseded` / `cancelled` |
| `continuationPolicy` | str | `none` / `wake_assignee` |
| `idempotencyKey` | str \| null | Unique per (project, taskId, key); null when the agent opts out |
| `summary` | str \| null | Optional human summary (the only human label) |
| `payload` | dict | `{widget, effectArgs?}` — the agent-authored render surface + per-effect args |
| `result` | dict \| null | Generic `{action, params}` result; null while pending |
| `createdBy` | str | Posting agent's slug |
| `sourceRunId` | str | The run that posted it (required provenance) |
| `resolvedBy` | str \| null | `"user"` once resolved, null while pending |
| `createdAt` | str | ISO-8601 timestamp |
| `resolvedAt` | str \| null | ISO-8601 timestamp; null while pending |

The card carries a generic widget + an **`effect`** discriminator; the agent
authors the whole rendered surface in `payload.widget`, and `effect` selects only
the resolve-time server behaviour. The record keeps (a) a generic `{action,
params}` result, (b) its `continuationPolicy`, and (c) idempotency
(`idempotencyKey` + required `sourceRunId`). The `effect` set —
`reply` / `approval_gate` / `review_work_product` — is **closed**.

## Layout (skill-folder convention)

```
scripts/
├── pyproject.toml          # project deps (duckdb/pandas/pyarrow for SQL resolver)
├── list_cards/             # read
│   ├── main.py
│   └── spec.md
├── get_card/               # read
│   ├── main.py
│   └── spec.md
├── list_open_cards/        # read (inbox decision-half feed)
│   ├── main.py
│   └── spec.md
├── inbox_view/             # read (the derived inbox feed: items + pending)
│   ├── main.py
│   └── spec.md
├── create_card/            # write
│   ├── main.py
│   └── spec.md
├── resolve_card/           # write (pending → terminal)
│   ├── main.py
│   └── spec.md
├── cancel_task_cards/      # write (sweep a task's pending cards)
│   ├── main.py
│   └── spec.md
└── delete_project/         # write (purge a project's cards)
    ├── main.py
    └── spec.md
```

Source lives in the wheel under `fused/_core/feedback-management/`
(read-only). The local-backend venv materializes at
`~/.openfused/core/feedback-management/scripts/.venv` on first startup. Adding a
new op = add `scripts/<name>/{main.py,spec.md}` (auto-discovered from the
directory; no Python-side registration).

## Conventions

- UDF logic is stdlib-only; no imports from `openfused.*` (the exec sandbox
  shadows the package with a shim). Reach `state.json` directly.
- All params are strings; empty string is the zero value. Object params
  (`payload`, `result`) cross the boundary **JSON-encoded** and are parsed inside
  the UDF.
- Read UDFs return the default empty result on a missing/corrupt `state.json`
  (they can't lose data). Write UDFs raise on a corrupt-but-present file rather
  than clobber it (a missing file is the fresh-install default).

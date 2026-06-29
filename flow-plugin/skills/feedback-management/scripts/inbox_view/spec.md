# inbox_view

Assemble the human **inbox feed** — the derived cross-task attention queue — from
the live app state file (`~/.openfused/app/state.json`, or the directory named by
`OPENFUSED_APP_DIR_STATE`). The inbox is a **view**, not a fourth store: this UDF
replaces the hand-assembly the Express routes did, and
returns the **same `{items, pending}` shape** so the UI is unchanged.

Because every `_core` UDF reads the one shared `state.json` (overview F1), this
single read joins `cards`, `comments`, `tasks`, and `runs` with no cross-project
call. There is **no `inbox[]` array** — the inbox owns no stored record; every row
is derived/projected (the array, its CRUD, and the legacy stored item shapes are
retired).

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `project` | string | `""` | Project slug to scope to. Empty string is the GLOBAL inbox: items across all projects + global pending-triage tasks. |

## Output

```
{ "items": list[dict], "pending": list[dict] }
```

`items` are inbox rows in the `InboxItem` wire shape the UI consumes (the union
of the five sources below), **newest-first by `createdAt`**. `pending` are full
task records with `status == "pending"` (scoped by `project`).

Each `items` row carries: `id`, `project`, `type`
(`question` / `message` / `completion` / `failure`), `taskId`, `agentSlug`,
`body`, `details`, `diffPaths`, `widget`, `workProductId`, `createdAt`,
`resolvedAt`, `response`, `taskTitle`, `taskNumber`, `sourceCardId`, `card`.

### The five assembled sources

1. **Card-view questions** — pending wake-bearing cards
   (`continuationPolicy == "wake_assignee"`) whose `effect` is NOT
   `review_work_product` (i.e. `reply` / `approval_gate`), projected as a
   read-only `type:"question"` view carrying `sourceCardId` + the full `card`.
   Body = the card's `summary` (the only human label; fallback `"(question)"`).
   `widget` comes from the payload — the agent-authored render surface owns all
   content, so `details`/`diffPaths` are always `null`. The client resolves these
   through the **card route**, not the inbox respond route. (The pending-question
   projection, now server-side.)
2. **Work-product review cards** — pending cards whose
   `effect == "review_work_product"` (the `publish_work_product` fold).
   Projected as a `type:"message"` Updates row
   carrying `sourceCardId` + the full `card` (so the UI renders the interactive card
   and resolves it through the **card route**, exactly like a card-view question, but
   in the Updates tab). `workProductId` is copied from `payload.effectArgs.workProductId`
   for the row; `widget` rides through from `payload.widget`; `body` = the card's
   `summary`, then `"(review)"`. These cards are non-blocking
   (`continuationPolicy: "none"`), so they do **not** appear in source 1. An open
   review card suppresses the task's derived completion (source 4) — the review IS
   the report.
3. **`notify` comments** — `comments[]` rows with `kind == "notify"` (the Phase-4
   `notify_user` → comment swap), projected as `type:"message"` Updates rows keyed
   on the comment id (`cmt_…`) so the Updates feed is unchanged. The inbox
   respond/dismiss routes recover the task from the comment and spawn the prose→run
   reply path; a comment id present in `dismissedFeedbackKeys` excludes an
   acknowledged one.
4. **Derived `completion`** — for a task whose LATEST terminal run is `completed`
   and whose `status` is `completed`, with **no** open `notify` comment and **no**
   open work-product review card (mirrors the run launcher's `!hasUnresolvedMessage`
   mint condition — an open review IS the report). Synthetic id
   `derived:completion:<runId>`; `body` = the run's `summary` (else
   `"Task completed."`); `agentSlug = null`; `createdAt` = the run's `finishedAt`.
5. **Derived `failure`** — for a task whose LATEST terminal run is `failed` and
   whose `status` is `failed`. Synthetic id `derived:failure:<runId>`; `body` =
   the run's `errorMessage` (else `"run failed"`).

### Derived items: id scheme + the dismissal handling

`completion` / `failure` are **no longer stored** — the run lifecycle stopped
minting them; the view derives them from run + task `status`. Their ids are the
stable synthetic `derived:<type>:<runId>` so the UI keys/renders them and the
respond/dismiss routes can recover the run + task.

Because a derived item has no stored row, a human DISMISS / RESPOND records the
synthetic id in the flat **`dismissedFeedbackKeys: string[]`** state field
(written via `acknowledgeFeedbackKey`). This view EXCLUDES
any derived item / notify comment whose synthetic id (`derived:<type>:<runId>` or
`cmt_<id>`) is present in `dismissedFeedbackKeys`, so a dismissed/answered item
does not re-appear on the next view. The acked set's source is
`doc.get("dismissedFeedbackKeys", [])` — **not** a scan of `inbox[]` rows. (Before
the dismissal-to-keyset move it was a resolved tombstone row in `inbox[]`; the
exclusion *semantics* are identical — only the storage of the ack changed.)

The key is **run-scoped** (`derived:completion:<runId>`): a re-run of the task
mints a *new* terminal run, so its derived item carries a *new* synthetic id NOT
in the set — a prior dismissal does not suppress the new run's item (the
**resurfacing** property). A derived item also disappears naturally when its task
moves off the terminal status (e.g. a retry launches a fresh `started` run → the
task is `in_progress`, so no `failure` derives).

## Source

Reads `state.json` directly with stdlib (`json`, `os`); no third-party imports.
State path resolution:
- `OPENFUSED_APP_DIR_STATE` is a **directory** (not a file path); when set, used verbatim.
- Otherwise: `~/.openfused/app`.
- State file is always `<app_dir>/state.json`.

Missing file or JSON parse errors return the empty feed `{"items": [], "pending": []}`
(no exception raised — a read UDF can't lose data).

## Constraints

- Stdlib-only; no third-party packages.
- Parameterized via `@udf def inbox_view(project: str = "")` (the injected decorator form).
- Preserves raw on-disk camelCase keys; does not reconstruct via any schema model.
- Read-only. Returns the production `{items, pending}` shape.

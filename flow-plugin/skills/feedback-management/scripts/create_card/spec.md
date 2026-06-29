# create_card

Mints a fresh `pending` interaction card and appends it to the live app state
file (`~/.openfused/app/state.json` or the directory given by
`OPENFUSED_APP_DIR_STATE`).

Mirrors `createCard` (+ the route's §7 idempotency lookup). This is the WRITE side of the
feedback-management system of record (the read side is `get_card` /
`list_cards` / `list_open_cards`).

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `project` | `""` | Project slug for the new card |
| `task_id` | `""` | The task the card is posted into (stored as `taskId`) |
| `effect` | `""` | The resolve-time behaviour selector: `reply` / `approval_gate` / `review_work_product` |
| `continuation_policy` | `""` | `none` / `wake_assignee` (stored as `continuationPolicy`); empty → `wake_assignee` |
| `idempotency_key` | `""` | Unique per `(project, taskId, key)`; empty → `null` (the agent opts out of dedup) |
| `summary` | `""` | Optional human summary (the only human label); empty → `null` |
| `payload` | `""` | The `{widget, effectArgs?}` payload, **JSON-encoded**; parsed into the stored object |
| `created_by` | `""` | The posting agent's slug (a non-nullable string; the route always supplies it, default `"agent"`), stored verbatim |
| `source_run_id` | `""` | The run that posted it (`app-runs.md` provenance), stored as `sourceRunId` |

`payload` is a JSON string because every UDF param is a string at the boundary;
an empty or unparseable `payload` raises a `ValueError` (a card with no payload is
never valid). The agent authors the whole rendered surface in `payload.widget`;
`effect` selects only the resolve-time server behaviour, and `payload.effectArgs`
carries the per-effect data (`approval_gate`: `{verb, detail}`;
`review_work_product`: `{workProductId}`; `reply`: absent).

## Idempotency (§7 — preserved server-side)

When `idempotency_key` is non-empty, the UDF scans for an existing card under the
same `(project, taskId, idempotencyKey)`. If one exists, the UDF returns it
**unchanged** (no new card minted, nothing superseded). This UDF does NOT decide
200-return-existing vs 409-conflict; it only does the (project, taskId, key) lookup
and returns the existing record on a hit. `sourceRunId` is **excluded** from the
equivalence concern (it differs on every retry), so the returned existing card
keeps its original `sourceRunId`.

## Supersede (replaces the removed `cancel_card`)

When the create is **wake-bearing** (`continuation_policy != "none"`, i.e. the
effective policy is `wake_assignee`), the UDF first sets every **pending
wake-bearing** card on the SAME `(project, taskId)` to `status = "superseded"`,
`result = null` before inserting the new card — the re-ask replaces the open ask.
Non-blocking cards (`continuationPolicy == "none"`, e.g. `review_work_product`)
are exempt: they never supersede and are never superseded. An idempotent hit
(above) short-circuits before this step, so an equivalent re-post supersedes
nothing.

## Output ack shape

Returns the card record (newly minted, or the existing one on an idempotent hit)
as a dict with the 15 camelCase `InteractionCardRecord` fields:

```json
{
  "id": "card_<hex>",
  "project": "<project>",
  "taskId": "<task_id>",
  "effect": "reply",
  "status": "pending",
  "continuationPolicy": "wake_assignee",
  "idempotencyKey": null,
  "summary": null,
  "payload": { "widget": { "type": "text" } },
  "result": null,
  "createdBy": "data-analyst",
  "sourceRunId": "run_<hex>",
  "resolvedBy": null,
  "createdAt": "2026-06-20T09:39:43.009Z",
  "resolvedAt": null
}
```

A freshly minted card is always `status="pending"`, `result=null`,
`resolvedBy=null`, `resolvedAt=null` (`pending` is the only non-terminal state).

## Behaviour

1. Parse `payload` from JSON (raise `ValueError` on empty/invalid).
2. Load `state.json` (raises on a corrupt-but-present file; default empty doc
   when missing).
3. If `idempotency_key` is set and a card with the same `(project, taskId,
   idempotencyKey)` exists, return that card unchanged (write nothing).
4. If the effective policy is wake-bearing (`!= "none"`), supersede the task's
   open wake-bearing cards (set `status="superseded"`, `result=null`).
5. Build the record: `id = "card_" + token_hex(6)`, `effect`, `status="pending"`,
   `continuationPolicy = continuation_policy or "wake_assignee"`, the nullable
   string fields (`idempotencyKey`/`summary`) `"" → None`, `createdBy` stored
   verbatim, `result/resolvedBy/resolvedAt = None`, `createdAt = now` (ISO-8601
   ms, `Z`-suffixed).
6. Append it to `cards[]`, write the document back atomically (tmp +
   `os.replace`), preserving all top-level keys.
7. Return the created record.

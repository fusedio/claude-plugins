# list_cards

Return interaction-card records for a task from the live app state file
(`~/.openfused/app/state.json`, or the directory named by
`OPENFUSED_APP_DIR_STATE`).

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `task` | string | `""` | Task id (`taskId`) to filter on. Empty string returns all cards across all tasks. |

## Output

A list of interaction-card records (raw camelCase dicts from `state.json.cards`),
**oldest-first by `createdAt`** — mirroring `listCards`.

Each record is the current `InteractionCardRecord` (the authoritative shape):

| Field | Type | Description |
|---|---|---|
| `id` | str | `card_<12hex>` — app-minted, stable, opaque |
| `project` | str | Project slug the card belongs to |
| `taskId` | str | Task the card was posted into |
| `effect` | str | The resolve-time behaviour selector: `reply` / `approval_gate` / `review_work_product` |
| `status` | str | `pending` (only non-terminal) / `answered` / `superseded` / `cancelled` |
| `continuationPolicy` | str | `none` / `wake_assignee` |
| `idempotencyKey` | str \| null | Unique per (project, taskId, key); null when the agent opts out |
| `summary` | str \| null | Optional human summary (the only human label) |
| `payload` | dict | `{widget, effectArgs?}` — the agent-authored render surface + per-effect args |
| `result` | dict \| null | Generic `{action, params}` result; null while pending |
| `createdBy` | str | Posting agent's slug |
| `sourceRunId` | str | The run that posted it (required) |
| `resolvedBy` | str \| null | `"user"` once resolved, null while pending |
| `createdAt` | str | ISO-8601 timestamp |
| `resolvedAt` | str \| null | ISO-8601 timestamp; null while pending |

## Source

Reads `state.json` directly with stdlib (`json`, `os`); no third-party imports.
State path resolution:
- `OPENFUSED_APP_DIR_STATE` is a **directory** (not a file path); when set, used verbatim.
- Otherwise: `~/.openfused/app`.
- State file is always `<app_dir>/state.json`.

Missing file or JSON parse errors return an empty list (no exception raised).

## Constraints

- Stdlib-only; no third-party packages.
- Parameterized via `@udf def list_cards(task: str = "")` (the injected decorator form).
- Preserves raw on-disk camelCase keys; does not reconstruct via any schema model.
- Read-only this step — the app still owns the `cards[]` write path (Phase 0). Step 02
  flips the system of record by adding the write UDFs.

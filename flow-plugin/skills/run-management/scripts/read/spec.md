# read — run records from the App state file

```
read(task_ids: str = "") -> list[dict]
```

Returns `RunRecord` dicts from `~/.openfused/app/state.json` (`runs[]`),
oldest-first by `createdAt` — mirroring the Express `listRuns` ordering. `task_ids` — a JSON array string
(`'["t1","t2"]'`) or comma-separated list (`"t1,t2"`) — filters to that SET of
tasks' runs (matched against the camelCase `taskId` field); empty string returns
all runs across all tasks, and an explicit empty set (`"[]"`) returns none.
Callers (the Express `listRunsForTasks`) pass exactly the task ids they will
render, so a future read optimisation (caching/indexing keyed by the id set)
benefits every caller without further changes.

SQL shorthand (the read endpoint): `SELECT * FROM {{read}}` returns every run;
pass `overrides: {"task_ids": "[\"...\"]"}` (or filter in SQL with
`WHERE taskId IN (...)`) to scope to a set of tasks. `get-one` is just
`SELECT * FROM {{read}} WHERE id = '...'` — there is no separate get UDF.

## Record shape

Each row is the camelCase `RunRecord` exactly as written by the app:

| field | type | notes |
|---|---|---|
| `id` | str | `run_<6-byte-hex>` |
| `taskId` | str | the task this run advances |
| `prompt` | str | composed prompt sent to the adapter |
| `status` | str | `started` / `completed` / `failed` / `cancelled` |
| `createdAt` | str | ISO-8601 `Z` |
| `finishedAt` | str \| null | ISO-8601 `Z`; null until terminal |
| `errorMessage` | str \| null | |
| `errorFamily` | str \| null | agentbridge `ErrorFamily` |
| `retryNotBefore` | str \| null | rate-limit retry hint |
| `summary` | str \| null | final assistant text |
| `costUsd` | float \| null | |
| `usage` | object \| null | `{inputTokens, outputTokens, cachedInputTokens}` |
| `model` | str \| null | |

`status: "started"` is the on-disk representation for both *queued* and *live*
runs (there is no separate queued value).

## Notes

- Read-only. The Express app/launcher is the sole writer of run state.
- Stdlib-only; reaches `state.json` directly (the exec sandbox shadows the real
  `fused` package with a shim, so the store class is not importable).
- A missing / unparseable `state.json` yields an empty `runs` list, not an error.

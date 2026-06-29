# finish

Patches a terminal transition onto an existing run record and stamps
`finishedAt` to the current UTC time.

Mirrors `finishRun`.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The run id to finish |
| `status` | `""` | Terminal status: `completed` / `failed` / `cancelled` |
| `error_message` | `""` | Failure message; empty → `null` |
| `error_family` | `""` | agentbridge `ErrorFamily`; empty → `null` |
| `retry_not_before` | `""` | Rate-limit retry hint (ISO timestamp); empty → `null` |
| `summary` | `""` | Final assistant text; empty → `null` |
| `cost_usd` | `""` | Cost in USD, parsed with `float()`; empty → `null` |
| `usage_json` | `""` | JSON `{inputTokens, outputTokens, cachedInputTokens}`; empty → `null` |
| `model` | `""` | Model id; empty → `null` |

No transition validation is performed — this is an unconditional setter; the app
gates legality before calling.

## Output ack shape

**Success** — returns the updated `RunRecord` (13 camelCase fields, same shape as
the `create` UDF output). `finishedAt` is set to the current UTC ISO timestamp,
`status` reflects the terminal value, and the nullable patch fields reflect the
supplied values (empty string → `null`). The app reads `finishedAt` off this
response, so no separate read is needed on the finish hot path.

**Not found** — returns:
```json
{"ok": false, "error": "not found"}
```

(`finishRun` is a silent no-op on a missing run; the UDF returns an
informative ack so callers can detect the miss without exception handling.)

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. Find the run by `id`; return the not-found ack if absent.
3. Apply the patch: set `status`; set the nullable fields (`errorMessage`,
   `errorFamily`, `retryNotBefore`, `summary`, `model`) to the supplied value or
   `null`; set `costUsd = float(cost_usd)` or `null`; set
   `usage = json.loads(usage_json)` or `null`.
4. Stamp `finishedAt` with the current UTC ISO timestamp.
5. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
6. Return the updated record.

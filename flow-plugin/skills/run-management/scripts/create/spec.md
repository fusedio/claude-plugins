# create

Appends a new run record to the live app state file (`~/.openfused/app/state.json`
or the directory given by `OPENFUSED_APP_DIR_STATE`).

Mirrors `createRun`.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The run id (`run_<hex>`); **caller-supplied**, never minted here |
| `task_id` | `""` | The task this run advances (stored as `taskId`) |
| `prompt` | `""` | The composed prompt sent to the adapter |

The id is supplied by the caller because the app mints `run_<hex>` before
persisting — it also keys an in-memory live buffer by that id — so a fresh id
here would orphan that buffer.

## Output ack shape

Returns the newly created `RunRecord` as a dict with 13 camelCase fields:

```json
{
  "id": "run_<hex>",
  "taskId": "<task_id>",
  "prompt": "<prompt>",
  "status": "started",
  "createdAt": "2026-06-20T09:39:43.009Z",
  "finishedAt": null,
  "errorMessage": null,
  "errorFamily": null,
  "retryNotBefore": null,
  "summary": null,
  "costUsd": null,
  "usage": null,
  "model": null
}
```

`status` is always `"started"` on creation (the on-disk representation for both
*queued* and *live* runs). Every field other than `id`/`taskId`/`prompt`/
`status`/`createdAt` is `null` until the run finishes (see the `finish` UDF).

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file; default empty doc
   when missing).
2. Build the record with `status="started"`, `createdAt=now`, all else null.
3. Append it to `runs[]`.
4. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
5. Return the created record.

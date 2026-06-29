# fail_started

Boot orphan recovery's run sweep: fails every run currently `status == "started"`.

Mirrors the run-sweep half of `recoverOrphans`. A run still `"started"` at boot was live when the
previous server process died — its hub process is gone, so it can never finish.

The task-side reconciliation of `recoverOrphans` (failing a stranded
`in_progress` task) stays in the app, which routes it through the
`_core.task-management.update_status` UDF — it is not part of this sweep.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `error_message` | `""` | Failure message stamped on each swept run; empty → `null` |

The app passes `"app restarted while this run was live"`.

## Output ack shape

```json
{"runIds": ["run_a", "run_b"]}
```

`runIds` lists the ids of the runs this call failed, in `runs[]` order. An empty
sweep (no run was `"started"`) returns `{"runIds": []}` and writes nothing.

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. For each run with `status == "started"`: set `status="failed"`,
   `finishedAt=now`, `errorMessage = error_message or null`; collect its `id`.
3. If at least one run was swept, write the document back atomically (tmp +
   `os.replace`), preserving all top-level keys; otherwise leave the file
   untouched.
4. Return `{"runIds": [...]}`.

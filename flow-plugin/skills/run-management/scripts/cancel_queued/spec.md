# cancel_queued

Boot orphan recovery's queued-run sweep: cancels every run currently
`status == "queued"`.

The sibling of `fail_started` for the queued lane of `recoverOrphans`. A run still `"queued"` at boot was minted but
never launched — it only ever sat in the in-process queue, which the dead process
took with it. It never ran, so it is **cancelled**, not failed (`fail_started`
fails genuinely-live `"started"` runs). Boot redispatch re-mints a fresh queued
run for the still-`todo` task, so cancelling the orphan keeps the run history
honest and stops queued orphans accumulating across restarts.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `error_message` | `""` | Message stamped on each swept run; empty → `null` |

The app passes `"app restarted before this run launched"`.

## Output ack shape

```json
{"runIds": ["run_a", "run_b"]}
```

`runIds` lists the ids of the runs this call cancelled, in `runs[]` order. An empty
sweep (no run was `"queued"`) returns `{"runIds": []}` and writes nothing.

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. For each run with `status == "queued"`: set `status="cancelled"`,
   `finishedAt=now`, `errorMessage = error_message or null`; collect its `id`.
3. If at least one run was swept, write the document back atomically (tmp +
   `os.replace`), preserving all top-level keys; otherwise leave the file
   untouched.
4. Return `{"runIds": [...]}`.

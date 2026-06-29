# mark_started

Promote a run from `queued` to `started` — the launch transition.

Mirrors `markRunStarted(id)`. A run is minted
`"queued"` by `create` and stays queued while it waits for a concurrency slot or a
dependency blocker; the launcher calls this the moment the agent process actually
goes live, so a run reads `"started"` (the only live state) strictly while it runs.

This is the one **non-terminal** status write — unlike `finish`, it does **not**
stamp `finishedAt`.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The run id (`run_<hex>`) to promote |

## Output ack shape

The updated `RunRecord` dict, or `{"ok": false, "error": "not found"}` when no run
carries that id.

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. Find the run by `id`; return the not-found ack if absent.
3. Set `status="started"` (leave `finishedAt` and every other field untouched).
4. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys. Idempotent — promoting an already-`"started"` run is a no-op.
5. Return the updated record.

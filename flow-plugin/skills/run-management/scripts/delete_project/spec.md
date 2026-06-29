# delete_project

Remove the named project's run records from the live app state, and delete each
removed run's per-run transcript file. The run-management half of the cross-skill
**project-delete** cascade.

This is the **first destructive write op** in run-management (only `bulk_seed`
wrote before; `transcript` stays read-only). It REUSES the `runs/`-confined
`_transcript_path` helper (copied from `transcript`/`bulk_seed`) so a
traversal-shaped run id can never delete a file outside `runs/`.

## Matching a run for removal

Run records do **not** carry a `project` field: `create` stamps only `taskId`, so
a real (live) run has a `taskId` but no `project` (only `bulk_seed`-restored
records may carry one). Matching on `project` alone would miss every live run. So
a run is removed if EITHER:

- its `taskId` is in `task_ids` — the project's deleted task ids, passed by Flow
  from `task-management.delete_project`'s `deletedTaskIds` (**the real path**), OR
- `project` is non-empty **and** `run["project"] == project` — the
  `bulk_seed`-restored fallback.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `project` | `""` | Project slug; matches `bulk_seed`-restored runs that carry a `project` field |
| `task_ids` | `""` | JSON-encoded list of task ids (the project's deleted task ids). A run whose `taskId` is in this set is removed. `""`/missing → empty set |

Both `project` and `task_ids` empty → no-op. A non-list `task_ids` raises a clear
error.

## Output ack shape

```json
{
  "runsRemoved": 3,
  "transcriptsRemoved": 2
}
```

- `runsRemoved` — run records dropped from `runs.json` (matched by `taskId` ∈
  `task_ids`, or by `project`).
- `transcriptsRemoved` — `runs/<runId>.ndjson` files actually deleted. A removed
  run whose transcript file was already absent — or whose id resolves outside
  `runs/` — counts as skipped, not removed, so `transcriptsRemoved ≤ runsRemoved`.

## Behaviour

1. **No-op guard.** Both `project` (after strip) and `task_ids` (parsed) empty →
   return zero counts, no lock, no write, never an error.
2. `_load_doc("runs")` (exclusive flock on the `runs` collection across the whole
   op); raises on a corrupt-but-present `runs.json`.
3. Collect the `id` of every run matched by the rule above, and compute the pruned
   `runs` list — but do **not** write yet.
4. **Transcripts FIRST.** For each removed run id, resolve `runs/<runId>.ndjson`
   with the `runs/`-confined `_transcript_path` (a traversal-shaped id → skip); if
   the file exists, `os.remove` it and count it; a missing file or a racing
   deleter leaves nothing to remove (skip, never raise).
5. **Prune records LAST.** `_save_doc(doc)` writes only the changed `runs`
   collection (dirty-snapshot logic) via atomic `tmp` + `os.replace`, then
   releases the lock. Every other collection is left untouched.
6. Return the runs-removed + transcripts-removed counts.

## Resumability — why transcripts are deleted before the prune

The order in steps 4→5 is load-bearing. The run **record** is the recovery
anchor: each transcript is only re-findable through the record whose id names it.
If the prune ran first, a crash mid-op would orphan every transcript not yet
deleted — its record is gone, so nothing re-finds the file. By deleting
transcripts first and pruning last, a crash leaves all records intact, so a rerun
(same `task_ids`) re-finds them and cleans the remaining transcripts (an
already-gone file is an idempotent skip). Both steps run under the same `runs`
flock held from step 2.

## Idempotency

Re-running `delete_project` on an already-deleted project (no run's `taskId`
matches and no run carries the `project`) returns `{"runsRemoved": 0,
"transcriptsRemoved": 0}` and writes nothing. Transcript deletion is best-effort,
so a partially-deleted project re-run cleans up whatever remains without crashing.

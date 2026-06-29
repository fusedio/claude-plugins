# bulk_seed

Restores run records and per-run transcripts **verbatim** into the live app
state — the seed/restore counterpart of `create`. It inserts caller-supplied
`RunRecord`s into `<app_dir>/state/runs.json` and writes per-run NDJSON
transcripts to `<app_dir>/runs/<runId>.ndjson`, **never minting** any
id/timestamp/status. This is the **first transcript WRITER** in run-management
(the `transcript` UDF stays read-only).

Used to seed the shipped pre-built showcase project's run history on first boot.
Writes go through the UDF layer (never a direct file write) so the storage
backing stays swappable behind the UDF contract.

## Inputs (all strings — JSON-encoded)

| Param | Default | Description |
|---|---|---|
| `runs` | `""` | JSON **array** of full `RunRecord` dicts, inserted verbatim (each record's own `id`/`taskId`/`status`/`createdAt`/`finishedAt`/`costUsd`/`usage`/… preserved). `""`/missing → nothing to insert |
| `transcripts` | `""` | JSON **object** `{ "<runId>": [<RunEvent>, …], … }` written one event per line to `runs/<runId>.ndjson`. `""`/missing → no transcripts |

Both params arrive as JSON-encoded strings (the all-strings boundary); the UDF
`json.loads` them and tolerates `""`/missing as "nothing to do". A non-list `runs`
or non-object `transcripts` raises a clear error.

## Output ack shape

```json
{
  "runs": { "inserted": 2, "skipped": 1 },
  "transcripts": { "written": 2, "skipped": 1 }
}
```

- `runs.inserted` / `runs.skipped` — records appended vs. skipped because their
  `id` already existed.
- `transcripts.written` / `transcripts.skipped` — `runs/<runId>.ndjson` files
  created vs. skipped because the file already existed **or** the `runId` was
  traversal-shaped (resolved outside `runs/`).

## Behaviour

1. Parse `runs` (`json.loads` → list) and `transcripts` (`json.loads` → object).
2. `_load_doc("runs")` (exclusive flock on the `runs` collection across
   load→save); raises on a corrupt-but-present `runs.json`.
3. **Insert-if-absent by `id`** (idempotent): build the set of existing run ids;
   append only records whose `id` is new, preserving insertion order; count
   inserted vs. skipped. Records are stored verbatim — no field is minted or
   overwritten.
4. `_save_doc(doc)` — writes only the changed `runs` collection (dirty-snapshot
   logic leaves every other collection's file untouched) via atomic `tmp` +
   `os.replace`, `json.dumps(indent=2, ensure_ascii=False)` (byte parity with the
   TS store), then releases the lock.
5. **Transcripts**: for each `runId → events`, resolve `runs/<runId>.ndjson` with
   the `runs/`-confined `_transcript_path` (a traversal-shaped id → skip); if the
   file already exists → skip; else write one `json.dumps(event, ensure_ascii=False)`
   per line + trailing newline, atomically (`tmp` + `os.replace`), creating
   `<app_dir>/runs/` if needed.
6. Return the inserted/skipped + written/skipped counts.

## Idempotency

Re-running `bulk_seed` with the same payload is a no-op: every run `id` already
exists (all skipped) and every `runs/<runId>.ndjson` already exists (all skipped).
Restore/seed semantics, not the id-minting `create`.

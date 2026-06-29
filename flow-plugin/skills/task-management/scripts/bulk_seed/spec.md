# bulk_seed

Inserts task + comment records **verbatim** into the live app state files
(`~/.openfused/app/state/tasks.json` + `state/comments.json`, or the directory
given by `OPENFUSED_APP_DIR_STATE`). This is the restore/seed counterpart of
`create`: it does **not** mint ids/numbers/timestamps — it preserves each
supplied record exactly — and it is **idempotent by `id`**.

It is the only supported way to seed app-state from host Python: seeding goes
through this UDF (the sole writer of the `tasks`/`comments` collections),
never a direct file write, so the storage backing stays
swappable behind the UDF contract.

## Inputs (all strings, JSON-encoded)

| Param | Default | Description |
|---|---|---|
| `tasks` | `""` | JSON-encoded **array** of full task records; empty string / missing → no tasks |
| `comments` | `""` | JSON-encoded **array** of full comment records; empty string / missing → no comments |

Each param is the JSON *text* of a list (the all-strings boundary). A non-empty
value that does not decode to a JSON array raises a clear error.

## Semantics — verbatim, idempotent by `id`

- **Verbatim insert.** Every field of each supplied record is written exactly as
  given — `id`, `number`, `createdAt`, `updatedAt`, `agentId`, `status`,
  `parentId`, `blockedBy` for tasks; `id`, `taskId`, `author`, `body`,
  `createdAt`, … for comments. No field is minted, defaulted, or rewritten.
- **Idempotent by `id`.** A record whose `id` already exists in its collection is
  **skipped** (no duplicate, no overwrite). Insertion order of new records is
  preserved. A repeated `bulk_seed` of the same records therefore inserts 0.
- **Per-collection write.** The `tasks` and `comments` collections are each
  loaded under their own `fcntl.flock` and written dirty-only with atomic
  `tmp + os.replace`, byte-format `json.dumps(indent=2, ensure_ascii=False)` —
  identical to the other `task-management` write UDFs.

## Output ack shape

```json
{
  "tasks": { "inserted": 6, "skipped": 0 },
  "comments": { "inserted": 3, "skipped": 0 }
}
```

`inserted` counts records newly appended; `skipped` counts records whose `id` was
already present. A second identical call returns
`{"tasks": {"inserted": 0, "skipped": 6}, "comments": {"inserted": 0, "skipped": 3}}`.

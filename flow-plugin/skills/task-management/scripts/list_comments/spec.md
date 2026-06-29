# list_comments

Read-only UDF. Returns comment records for a single task from the live app state file
(`~/.openfused/app/state.json`).

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_id` | `str` | `""` | Task id to filter on. Empty string returns `[]`. |

## Output

`list[dict]` — raw camelCase comment records for the given task, **oldest-first** by
`createdAt`. Each record has five fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Comment id (e.g. `cmt_a1b2c3d4e5f6`) |
| `taskId` | `str` | Task id this comment belongs to |
| `author` | `str` | Identity of the comment author |
| `body` | `str` | Comment text |
| `createdAt` | `str` | ISO-8601 UTC timestamp with milliseconds, `Z` suffix |

## Behaviour

- Empty `task_id` → returns `[]` immediately without reading state.
- `task_id` with no matching comments → returns `[]`.
- Missing or unreadable `state.json` → returns `[]` (treated as empty document).
- Records are returned in ascending `createdAt` order (oldest first), matching
  `list_comments`.
- Raw dict round-trip: no schema reconstruction; all fields are returned exactly
  as stored on disk.

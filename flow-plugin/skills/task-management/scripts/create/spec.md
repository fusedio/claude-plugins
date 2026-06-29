# create

Appends a new task record to the live app state file (`~/.openfused/app/state.json`
or the directory given by `OPENFUSED_APP_DIR_STATE`).

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `project` | `""` | Project slug for the new task |
| `title` | `""` | Short task title |
| `description` | `""` | Longer description; falls back to `title` when empty |
| `status` | `"pending"` | Initial status: `pending` or `todo` |
| `parent_id` | `""` | Parent task id; empty string is stored as JSON `null` |
| `created_by` | `"user"` | Identity of the creator |
| `work_mode` | `"standard"` | Work mode value |
| `id` | `""` | Client-provided task id / idempotency key; when present, retries return the existing task |

## Output ack shape

Returns the existing or newly created task record as a dict with 13 camelCase fields:

```json
{
  "id": "task_<12 hex chars> or client-provided id",
  "project": "<project>",
  "number": 1,
  "title": "<title>",
  "description": "<description>",
  "status": "pending",
  "agentId": null,
  "createdBy": "user",
  "createdAt": "2026-06-18T09:39:43.009Z",
  "updatedAt": "2026-06-18T09:39:43.009Z",
  "parentId": null,
  "workMode": "standard",
  "blockedBy": []
}
```

When `id` is non-empty and a task with that id already exists, `create` returns
that existing record without appending a duplicate. Otherwise, `number` is
`MAX(number for project) + 1`, or `1` when the project has no tasks yet.
Sequences are independent per project.

`createdAt` and `updatedAt` are always equal on creation.

`agentId` is always `null` on creation (use the `assign` UDF to set it).

## Not implemented in this POC

- **Depth-ceiling check**: `TasksStore.create_task` raises `TaskDepthExceededError`
  when the parent is already at `MAX_TASK_DEPTH`.  This guard is omitted here to
  keep the UDF stdlib-only.  Upgrade path: port `task_depth` + `would_exceed_depth`
  into the inline helpers, or add a shared helper module once the
  POC graduates to a proper package.

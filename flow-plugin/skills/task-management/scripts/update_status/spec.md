# update_status

Sets the `status` field on a task record unconditionally.

Mirrors `TasksStore.update_task_status`.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The task id to update |
| `status` | `""` | The new status value |

Common status values: `pending`, `todo`, `in_progress`, `completed`, `failed`,
`cancelled`.  No transition validation is performed (the real store method also
applies no transition checks at the Python layer).

## Output ack shape

**Success** — returns the updated task record (13 camelCase fields, same shape as
the `create` UDF output).  `status` reflects the new value; `updatedAt` is
re-stamped to the current UTC time.

**Not found** — returns:
```json
{"ok": false, "error": "not found"}
```

Note: the real `TasksStore.update_task_status` raises `TaskNotFoundError` on a
missing task.  The UDF returns an informative ack dict instead so callers can
detect the miss without exception handling.

## Behaviour

1. Load `state.json`.
2. Find the task by `id`; return the not-found ack if absent.
3. Set `status = status`.
4. Stamp `updatedAt` with the current UTC ISO timestamp.
5. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
6. Return the updated task record.

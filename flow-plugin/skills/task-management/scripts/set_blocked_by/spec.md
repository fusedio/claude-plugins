# set_blocked_by

Sets the `blockedBy` edge on a task record.

Mirrors `TasksStore.set_blocked_by` minus cycle detection.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The task id to update |
| `blocked_by` | `""` | Blocker ids as a JSON array string or comma-separated list |

### `blocked_by` parsing

The param arrives as a plain string (all UDF params are strings).  Accepted
formats:

| Input | Result |
|---|---|
| `""` (empty) | `[]` |
| `'["task_abc","task_def"]'` | `["task_abc", "task_def"]` |
| `"task_abc,task_def"` | `["task_abc", "task_def"]` |
| `"task_abc"` | `["task_abc"]` |

## Output ack shape

**Success** — returns the updated task record (13 camelCase fields, same shape as
the `create` UDF output).  `blockedBy` reflects the new list; `updatedAt` is
re-stamped to the current UTC time.

**Not found** — returns:
```json
{"ok": false, "error": "not found"}
```

Note: the real `TasksStore.set_blocked_by` no-ops silently on an absent task.
The UDF returns an informative ack dict instead so callers can detect the miss.

## Behaviour

1. Load `state.json`.
2. Find the task by `id`; return the not-found ack if absent.
3. Parse `blocked_by` to `list[str]` using the rules above.
4. Set `blockedBy = <parsed list>`.
5. Stamp `updatedAt` with the current UTC ISO timestamp.
6. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
7. Return the updated task record.

## Not implemented in this POC

- **Cycle detection**: `TasksStore.set_blocked_by` raises `BlockerCycleError`
  when the proposed `blockedBy` list would form a dependency cycle.  This guard
  is omitted here to keep the UDF stdlib-only.  Upgrade path: port
  `_would_form_blocker_cycle_in` into the inline helpers, or add
  a shared helper module once the POC graduates to a proper package.

# assign

Sets `agentId` on a task record and promotes `pending` → `todo` if applicable.

Mirrors `TasksStore.assign_task`.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The task id to assign |
| `agent_id` | `""` | The agent identifier to assign |

## Output ack shape

**Success** — returns the updated task record (13 camelCase fields, same shape as
the `create` UDF output).  `agentId` reflects the new value; `updatedAt` is
re-stamped to the current UTC time; `status` is `"todo"` if it was previously
`"pending"`, otherwise unchanged.

**Not found** — returns:
```json
{"ok": false, "error": "not found"}
```

## Behaviour

1. Load `state.json`.
2. Find the task by `id`; return the not-found ack if absent.
3. Set `agentId = agent_id`.
4. If `status == "pending"`, promote to `"todo"`.
5. Stamp `updatedAt` with the current UTC ISO timestamp.
6. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
7. Return the updated task record.

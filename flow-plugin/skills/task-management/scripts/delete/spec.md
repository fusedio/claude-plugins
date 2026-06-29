# delete UDF spec

Hard-delete a task and all its transitive descendants from the live app state,
with full cascade across every related collection.

## Input

| Parameter | Type   | Default | Description                   |
|-----------|--------|---------|-------------------------------|
| `id`      | string | `""`    | The task id to delete.        |

## Behaviour

One atomic `_load_doc → mutate → _save_doc` cycle.

### Steps

1. **Not-found guard.** If no task with `id` exists in `doc["tasks"]`, return
   `{"ok": false, "error": "not found"}` immediately without writing.

2. **Transitive descendant collection.** Build a `parentId → [childId, ...]`
   map over all tasks. BFS from `id`, accumulating the full set of ids to
   delete (the target plus every descendant, transitively). A visited guard
   prevents infinite loops if a `parentId` cycle ever exists in the data.

3. **Cascade removal.** Remove every record whose camelCase `taskId` field is
   in the deleted set from each of the following top-level lists. Absent or
   `null` keys are treated as empty lists (no error).

   | Key              | Record field checked |
   |------------------|----------------------|
   | `runs`           | `taskId`             |
   | `comments`       | `taskId`             |
   | `inbox`          | `taskId`             |
   | `cards`          | `taskId`             |
   | `costEvents`     | `taskId`             |

4. **Task removal.** Remove all tasks whose `id` is in the deleted set from
   `doc["tasks"]`.

5. **`blockedBy` scrub.** For every task that survives, remove any deleted id
   from its `blockedBy` list.

6. **Save.** Persist via atomic tmp+rename. All other top-level document keys
   (`serveMcp`, `gatePolicies`, `onboarding`, …) are preserved verbatim.

## Return value

On success:

```json
{
  "deletedTaskIds": ["task_abc", "task_def"],
  "runsRemoved": 2,
  "commentsRemoved": 1,
  "inboxRemoved": 0,
  "cardsRemoved": 0,
  "costEventsRemoved": 0
}
```

When the task is not found:

```json
{"ok": false, "error": "not found"}
```

## Notes

- Mirrors `TasksStore.delete_task` exactly, adapted for the UDF
  boundary (returns an ack instead of raising `TaskNotFoundError`).
- Uses camelCase throughout to match the on-disk JSON format written by the
  TypeScript app.

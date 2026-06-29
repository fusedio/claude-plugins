# cancel_task_cards

Task-cancel cascade: sweep EVERY `pending` card on a task to `cancelled` (no
result, no wake) in ONE whole-document read-modify-write. Mirrors
`cancelTaskCards`.

The whole sweep is a single atomic write so it cannot half-cancel a task's
cards.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `task` | `""` | The task id whose pending cards are swept (matched against `taskId`) |

## Output ack shape

The list of cards this call cancelled (the cards that were `pending` on the
task), in `cards[]` order. An empty sweep returns `[]` and writes nothing:

```json
[
  {
    "id": "card_<hex>",
    "status": "cancelled",
    "result": null,
    "resolvedBy": "user",
    "resolvedAt": "2026-06-20T09:42:00.000Z",
    "...": "the other unchanged fields"
  }
]
```

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. For each card with `taskId == task` and `status == "pending"`: set
   `status="cancelled"`, `resolvedBy="user"`, `resolvedAt=now` (a single shared
   `now` for the whole sweep, mirroring `cancelTaskCards`), `result` left as-is
   (it is already `null` while pending); collect the record.
3. If at least one card was cancelled, write the document back atomically (tmp +
   `os.replace`), preserving all top-level keys; otherwise leave the file
   untouched.
4. Return the list of cancelled records.

Only `pending` cards are touched — already-terminal cards on the task (answered,
superseded, etc.) and cards on other tasks are untouched.

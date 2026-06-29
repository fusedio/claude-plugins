# delete_project

Remove every interaction card for one project from the live app state, in ONE
whole-document read-modify-write. The feedback-management half of the cross-skill
**project-delete** cascade.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `project` | `""` | The project slug whose cards are removed (matched against the card's `project` field). `""`/whitespace → no-op |

## Output ack shape

```json
{ "cardsRemoved": 4 }
```

`cardsRemoved` is the number of card records dropped from `cards.json` for the
project (every status — `pending` and terminal alike).

## Behaviour

1. **Empty-project guard.** `""`/whitespace `project` → return `{"cardsRemoved":
   0}`, no lock, no write, never an error.
2. `_load_doc("cards")` (exclusive flock on the `cards` collection across
   load→save); raises on a corrupt-but-present `cards.json`.
3. Drop every card whose `project` equals `project` from `doc["cards"]`. Cards of
   every status are removed (unlike `cancel_task_cards`, which only touches
   `pending` cards) — the whole project is going away.
4. `_save_doc(doc)` — writes only the changed `cards` collection (dirty-snapshot
   logic) via atomic `tmp` + `os.replace`, preserving every other top-level key,
   then releases the lock.
5. Return the cards-removed count.

## Notes

- **`dismissedFeedbackKeys` is left alone.** A dangling synthetic-id entry for a
  deleted project is harmless: the derived inbox item it suppresses can never
  re-appear once the project's tasks/runs are gone.
- **Idempotent.** A re-run on an already-deleted project (or one with no cards)
  matches nothing, returns `{"cardsRemoved": 0}`, and writes nothing.

# resolve_card

Atomically transitions a `pending` card to a terminal state — the single guarded
`pending → terminal` flip. Mirrors `resolveCard`.

> **The UDF is a dumb persister.** This UDF receives an already-validated `status` + `result`
> and only persists them under the pending-guard. Moving validation into the UDF
> is explicitly out of scope.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The `card_<hex>` id to resolve |
| `status` | `""` | The terminal status the route computed: `answered` / `superseded` / `cancelled` (never `pending`) |
| `result` | `""` | The generic `{action, params}` result, **JSON-encoded**; empty string → `null` (e.g. a cancel carries no result) |
| `resolved_by` | `""` | Who resolved it; empty → `null`. The route passes `"user"` |

`result` is a JSON string because every UDF param is a string at the boundary; a
non-empty value that does not parse as JSON raises a `ValueError`.

## Pending-guard (§4.6 — the resolve lock)

The flip only happens when the card is currently `pending`. The whole-document
atomic write IS the resolve lock (there is no row lock). On a card that is
unknown OR already terminal, the UDF returns `{"ok": false, "error": "..."}`
(not-found / already resolved) and writes nothing — the caller maps that to a
409.

## Output ack shape

On success, the resolved card record (16 camelCase fields), now terminal:

```json
{
  "id": "card_<hex>",
  "status": "answered",
  "result": { "action": "submit", "params": { "region": "us-west" } },
  "resolvedBy": "user",
  "resolvedAt": "2026-06-20T09:40:00.000Z",
  "...": "the other unchanged fields"
}
```

On a miss:

```json
{"ok": false, "error": "not found"}
{"ok": false, "error": "already resolved"}
```

## Behaviour

1. Parse `result` from JSON when non-empty (raise `ValueError` on invalid);
   empty → `None`.
2. Load `state.json` (raises on a corrupt-but-present file).
3. Find the card by `id`. Absent → `{"ok": false, "error": "not found"}`,
   writes nothing.
4. If its `status != "pending"` → `{"ok": false, "error": "already resolved"}`,
   writes nothing.
5. Else set `status`, `result`, `resolvedBy = resolved_by or None`,
   `resolvedAt = now` (ISO-8601 ms, `Z`-suffixed); write the document back
   atomically, preserving all top-level keys.
6. Return the resolved record.

# acknowledge_feedback

Dedup-appends a synthetic feedback id to the flat `dismissedFeedbackKeys` ACK
ledger — idempotent, write-only-on-change. Mirrors `acknowledgeFeedbackKey`.

Reads/writes `~/.openfused/app/state.json` (or the directory named by
`OPENFUSED_APP_DIR_STATE`) directly with stdlib because the in-sandbox
`fused` package shadows the real one — there is no SDK call back to the host.

## Why a key, not a stored row

`dismissedFeedbackKeys` is the ACK set for inbox rows that own NO stored record:
a DERIVED completion/failure (`derived:<type>:<runId>`) or a `notify` comment
(`cmt_…`, the Phase-4 `notify_user` → comment swap). `inbox_view` re-derives
these every read; appending the synthetic id here is what stops a
dismissed/answered one from re-appearing. The key is run-scoped for derived
items, so a re-run mints a new id NOT in the set and the outcome resurfaces.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `key` | `""` | The synthetic feedback id to acknowledge. Empty string → no-op ack |

## Output ack shape

```json
{"ok": true, "alreadyAcked": false}
```

`alreadyAcked` is `true` when the key was already present (idempotent — nothing
written), `false` when it was freshly appended (or the key was empty). The
`alreadyAcked` return lets a caller subsume the `is_feedback_key_dismissed`
pre-check at the call site.

## Behaviour

1. Empty `key` → `{"ok": true, "alreadyAcked": false}`, writes nothing.
2. Load `state.json` (raises `RuntimeError` on a corrupt-but-present file — a
   write UDF never clobbers an unparseable store).
3. Read `dismissedFeedbackKeys` defensively (an old store may omit it → treat as
   `[]`).
4. If `key` is already present → `{"ok": true, "alreadyAcked": true}`, writes
   nothing.
5. Else append `key`, write the document back atomically (tmp + `os.replace`),
   preserving all other top-level keys, and return
   `{"ok": true, "alreadyAcked": false}`.

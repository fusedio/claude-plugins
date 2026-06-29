# is_feedback_key_dismissed

Returns whether a synthetic feedback id is in the flat `dismissedFeedbackKeys`
ACK ledger. Mirrors `isFeedbackKeyDismissed`.

Reads `~/.openfused/app/state.json` (or the directory named by
`OPENFUSED_APP_DIR_STATE`) directly with stdlib because the in-sandbox
`fused` package shadows the real one.

## Why

The respond/dismiss routes guard on this for a DERIVED completion/failure id
(`derived:<type>:<runId>`) so a repeat action on the same id is rejected (404)
rather than spawning a second run — mirroring `find_notify_comment`'s own ack
check for a `notify` comment id.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The synthetic feedback id to check. Empty string → never dismissed |

## Output

`bool` — `True` iff `id` is present in `dismissedFeedbackKeys`, else `False`.

## Behaviour

1. Empty `id` → `False`.
2. Load `state.json` (a read UDF; a missing or corrupt file → the empty-default
   doc, no raise).
3. Read `dismissedFeedbackKeys` defensively (an old store may omit it → `[]`).
4. Return whether `id` is a member of that list.

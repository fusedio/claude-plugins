# find_notify_comment

Returns a `notify` comment record by id — a read for the inbox respond/dispatch
path. Mirrors `findNotifyComment` exactly.

Reads `~/.openfused/app/state.json` (or the directory named by
`OPENFUSED_APP_DIR_STATE`) directly with stdlib because the in-sandbox
`fused` package shadows the real one.

## Why

A `notify` comment (`cmt_…`, the Phase-4 `notify_user` → comment swap) is
projected into the inbox Updates feed by `inbox_view` but owns NO stored inbox
row of its own. When a human replies to / dismisses it, the respond/dismiss
routes recover the task from the comment and spawn the prose→run reply path; this
read returns the raw comment so they can. A comment already acknowledged (its id
in `dismissedFeedbackKeys`) is treated as not-found so a replied/dismissed report
is never re-actioned.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `comment_id` | `""` | The `cmt_…` id to look up. Empty string → not-found ack |

## Output ack shape

On a hit, the raw comment dict (the fields read):

```json
{
  "id": "cmt_…",
  "taskId": "t1",
  "author": "alpha",
  "body": "FYI done",
  "kind": "notify",
  "widget": null,
  "createdAt": "2026-06-20T09:40:00.000Z"
}
```

On any miss:

```json
{"ok": false, "error": "not found"}
```

The TS client maps `{ok: false}` → `null`, matching today's behaviour.

## Behaviour

1. Empty `comment_id` → `{"ok": false, "error": "not found"}`.
2. Load `state.json` (a read UDF; a missing or corrupt file → the empty-default
   doc, no raise).
3. Build the `acked` set from `dismissedFeedbackKeys` (defensive: drop `""` and
   non-string keys, like `inbox_view`).
4. Find the comment by `id`. Absent OR `kind != "notify"` → not-found ack.
5. If its id is in `acked` → not-found ack.
6. Else return the raw comment dict.

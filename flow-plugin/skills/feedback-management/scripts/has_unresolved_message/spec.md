# has_unresolved_message

Returns whether a task has an open report that IS its completion report. When it
does, the system skips the auto `completion` item. Mirrors
`hasUnresolvedMessage`.

Reads `~/.openfused/app/state.json` (or the directory named by
`OPENFUSED_APP_DIR_STATE`) directly with stdlib because the in-sandbox
`fused` package shadows the real one.

## Why

A `notify_user` IS the completion report (Phase-4 swap → a `notify` comment), and
an open work-product REVIEW CARD IS the report (the review fold,
app-artifacts.md §4). Either suppresses the derived `completion` item — the
report is the surfaced attention item, so a duplicate completion must not appear
alongside it. This is the SAME union the `inbox_view` UDF applies to its
derived-completion guard (`tasks_with_open_message`); keeping it in one place
keeps the launcher's SSE-pointer publish and the view's derivation in agreement.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `task_id` | `""` | The task id to check. Empty string → never unresolved |

## Output

`bool` — `True` iff the task has EITHER:

- (a) an open work-product REVIEW CARD — a pending card whose
  `effect == "review_work_product"` (mirrors `inbox_view`'s
  `_is_work_product_review_card`); OR
- (b) an open (un-acked) `notify` comment — a `comments[]` row with
  `kind == "notify"` whose id is NOT in `dismissedFeedbackKeys`.

Else `False`.

## Behaviour

1. Empty `task_id` → `False`.
2. Load `state.json` (a read UDF; a missing or corrupt file → the empty-default
   doc, no raise).
3. Scan `cards[]`: if any pending card on the task has
   `effect == "review_work_product"` → `True`.
4. Build the `acked` set from `dismissedFeedbackKeys` (defensive: drop `""` and
   non-string keys).
5. Scan `comments[]`: if any `notify` comment on the task is not in `acked` →
   `True`.
6. Else `False`.

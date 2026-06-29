# add_comment

Write UDF. Appends a new comment record to a task in the live app state file
(`~/.openfused/app/state.json`).

## Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_id` | `str` | `""` | Task id to attach the comment to. |
| `author` | `str` | `""` | Identity of the comment author. |
| `body` | `str` | `""` | Comment text. |
| `kind` | `str` | `""` | Comment kind. `""` is a plain thread `note`; `notify` marks a `notify_user` FYI that the inbox Updates feed surfaces. Stored verbatim. |
| `widget` | `str` | `""` | OPTIONAL JSON-UI widget config (a JSON string) a `notify` comment may carry for inline display in the Updates feed. `""` → no widget. Opaque to the UDF; stored as the parsed object. |

## Output

`dict` — the newly created camelCase comment record. A plain `note` carries the
five core fields; a `notify` comment additionally carries `kind` and (when
supplied) `widget`:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Minted comment id: `"cmt_"` + 12 hex chars (matches `new_id("cmt")`) |
| `taskId` | `str` | Task id this comment belongs to |
| `author` | `str` | Identity of the comment author |
| `body` | `str` | Comment text |
| `createdAt` | `str` | ISO-8601 UTC timestamp with milliseconds, `Z` suffix |
| `kind` | `str` | Present only when a non-empty `kind` was passed (e.g. `notify`); OMITTED on a plain note |
| `widget` | `object` | Present only when a non-empty `widget` was passed; the parsed JSON-UI config |

## Behaviour

- Mints a `cmt_`-prefixed id using `secrets.token_hex(6)` (12 hex chars).
- Stamps `createdAt` with the current UTC time at millisecond precision
  (e.g. `2026-06-19T09:39:43.009Z`), matching `_now_iso()`.
- Writes `kind` / `widget` **only when set**, so a plain thread note stays
  byte-identical to the pre-Phase-4 5-field shape (read-time backfill on the app
  side treats a missing `kind` as `note`, a missing `widget` as `null`).
- A non-empty `widget` is `json.loads`-parsed and stored as the object; a malformed
  JSON string RAISES (a daemon-vetted widget arrives well-formed, so a parse error
  is a real bug, not a value to silently drop).
- Appends the new record to `doc["comments"]`; treats an absent `"comments"` key
  as an empty list.
- Writes atomically via a `<path>.tmp` + `os.replace` round-trip (mirrors
  `_save`); creates the parent directory if absent.
- Preserves ALL other top-level keys in the document (raw-dict round-trip).
- Missing or unreadable `state.json` is treated as an empty document; the file is
  created on first write.

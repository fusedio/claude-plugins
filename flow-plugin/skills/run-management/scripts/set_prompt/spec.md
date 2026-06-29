# set_prompt

Updates the stored `prompt` on a not-yet-finished run.

Mirrors `setRunPrompt` — used when a queued
resume accumulates further human follow-ups so the
prompt the UI shows matches the one the agent will receive at launch.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `id` | `""` | The run id to update |
| `prompt` | `""` | The new composed prompt |

The app only calls this for a not-yet-finished (queued) run; the UDF performs no
status check (it is an unconditional setter — the app gates legality).

## Output ack shape

**Success** — returns the updated `RunRecord` (13 camelCase fields, same shape as
the `create` UDF output) with `prompt` set to the new value.

**Not found** — returns:
```json
{"ok": false, "error": "not found"}
```

(`setRunPrompt` is a silent no-op on a missing run; the UDF returns
an informative ack instead.)

## Behaviour

1. Load `state.json` (raises on a corrupt-but-present file).
2. Find the run by `id`; return the not-found ack if absent.
3. Set `prompt = prompt`.
4. Write the document back atomically (tmp + `os.replace`), preserving all
   top-level keys.
5. Return the updated record.

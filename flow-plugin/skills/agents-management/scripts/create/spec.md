# create

Add a new custom persona to the live app roster. Mirrors `createAgent`.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `name` | string | `""` | Display name (required). |
| `title` | string | `""` | Persona title (required). |
| `role` | string | `""` | Free-label role (required). |
| `description` | string | `""` | One-line description (required). |
| `prompt` | string | `""` | System prompt body (required). |
| `model` | string | `""` | Model override; empty → null. |
| `adapter` | string | `""` | Adapter; empty → `claude_code`. |
| `slug` | string | `""` | Explicit slug; empty → derived from `name` (lowercase, non-alnum → `-`). |

## Output

The new `AgentRecord` dict (`builtin: false`), or an error ack
`{"ok": false, "error": "<reason>"}` when a required field is empty, the name has
no alnum characters, or the slug collides with an existing persona.

## Source

Writes `<agents>/<slug>/AGENTS.md` + (when non-default adapter/model) the
`.openfused.yaml` sidecar entry, atomically (tmp + `os.replace`). Seeds the
defaults first so creating at a default slug collides like any other. YAML via
PyYAML.

## Constraints

- No `openfused.*` imports; roster-format logic hand-written. PyYAML is a
  project-venv dependency.
- All params are strings; empty string is the zero value.

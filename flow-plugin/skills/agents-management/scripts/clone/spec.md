# clone

Create a custom (`builtin: false`) editable copy of any persona — the edit path
for a built-in default. Mirrors `cloneAgent`.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `id` | string | `""` | The source persona's slug or derived id. |
| `name` | string | `""` | The new persona's name (required; slug derived from it). |

## Output

The new `AgentRecord` dict (`builtin: false`), copying the source's
title/role/description/prompt/model/adapter under the new name/slug. Error ack
`{"ok": false, "error": "<reason>"}` when `name` is empty, the source is not
found, or the derived slug collides.

## Source

Resolves the source via the roster read, then writes a new
`<agents>/<slug>/AGENTS.md` (+ sidecar) the same way `create` does. YAML via
PyYAML.

## Constraints

- No `openfused.*` imports; roster-format logic hand-written. PyYAML is a
  project-venv dependency.

# update

Patch fields on an existing persona. Mirrors `updateAgent`.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `id` | string | `""` | The persona's slug or derived id. |
| `name` | string | `""` | New name (empty → unchanged). |
| `title` | string | `""` | New title (empty → unchanged). |
| `role` | string | `""` | New role (empty → unchanged). |
| `description` | string | `""` | New description (empty → unchanged). |
| `prompt` | string | `""` | New prompt (empty → unchanged). |
| `adapter` | string | `""` | New adapter (empty → unchanged). |
| `model` | string | `""` | New model (empty → unchanged). |

## Output

The updated `AgentRecord` dict, or `{"ok": false, "error": "not found"}` when the
id/slug resolves to no persona. The slug never changes (the file path is stable).

## Intentional divergence from the app

Over the all-strings UDF boundary, an empty string means **leave unchanged** for
every field — whereas the Express `updateAgent` *rejects* an explicitly-empty
required field with a 400. Clearing `model` back to null is likewise not
expressible here; use `reset` (defaults) or `clone` (a fresh copy).

## Source

Resolves by slug/id via the roster read, applies the patch, writes through
`<agents>/<slug>/AGENTS.md` + sidecar atomically. YAML via PyYAML.

## Constraints

- No `openfused.*` imports; roster-format logic hand-written. PyYAML is a
  project-venv dependency.

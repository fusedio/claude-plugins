# delete

Remove a persona from the live app roster. Mirrors `deleteAgent`.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `id` | string | `""` | The persona's slug or derived id. |

## Output

`{"deleted": true}` on success, or `{"ok": false, "error": "not found"}`.

## Behavior

Removes `<agents>/<slug>/` (recursively, stdlib only) and the persona's
`.openfused.yaml` sidecar entry. **Does not touch the seed ledger** — so a deleted
default stays deleted on the next seed pass (the ledger still lists it as seeded,
which is exactly what keeps it from reappearing). A dangling `task.agentId`
elsewhere is tolerated.

## Constraints

- No `openfused.*` imports; roster-format logic hand-written. PyYAML is a
  project-venv dependency.

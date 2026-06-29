# reset

Restore a default persona to its shipped seed. Mirrors `resetAgent`.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `id` | string | `""` | The default persona's slug or derived id. |

## Output

The restored `AgentRecord` dict (`builtin: true`), or an error ack
`{"ok": false, "error": "<reason>"}`:
- `"not found"` — the id/slug matches no persona and no shipped seed.
- `"only default agents can be reset"` — the persona exists but is custom.

Addressing a **deleted** default by its slug re-creates it from the seed (the
editable-defaults safety net).

## Source

Reads the slug's seed from `scripts/seed_agents.json` (the 5 defaults, transcribed
verbatim), then writes
`<agents>/<slug>/AGENTS.md` (+ sidecar, `builtin: true`). YAML via PyYAML.

`createdAt` is derived from the file mtime (never persisted), so it is not
preserved across the rewrite — the returned record reports the post-write mtime.

## Constraints

- No `openfused.*` imports; roster-format + seed logic hand-written. PyYAML is a
  project-venv dependency.
- The seed file is located via the project venv anchor
  (`<scripts>/.venv/bin/python` → `<scripts>/seed_agents.json`), the
  `OPENFUSED_PROJECT_ROOT` env, or the `OPENFUSED_AGENTS_SEED_FILE` override.

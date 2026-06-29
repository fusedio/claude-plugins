# read

Return persona records from the live app roster directory
(`~/.openfused/app/agents/`, or `$OPENFUSED_APP_DIR_STATE/agents`). Backs the SQL
`{{read}}` ref. Seeds the 5 default personas on first read (like the app's
`listAgents` → `seedDefaultRoster`).

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `slug` | string | `""` | Filter to one persona by slug **or** derived id. Empty returns every persona, slug-sorted. |

## Output

A list of `AgentRecord` dicts (slug-sorted):

| Field | Type | Description |
|---|---|---|
| `id` | str | `agent_<sha256(slug)[:12]>` (derived from the slug) |
| `slug` | str | Portable identity (directory name) |
| `name` | str | Display name |
| `title` | str | Persona title |
| `role` | str | Free-label role (engineer/analyst/qa/architect/pm/…) |
| `description` | str | One-line description |
| `adapter` | str | Adapter (`claude_code` default), from the sidecar |
| `model` | str \| null | Model override, from the sidecar |
| `prompt` | str | The system prompt (the `AGENTS.md` body) |
| `builtin` | bool | Provenance flag (true for shipped defaults), from the sidecar |
| `createdAt` | str | ISO-8601 from the `AGENTS.md` file mtime |

## Source

Reads `<agents>/<slug>/AGENTS.md` (YAML frontmatter + prompt body) merged with the
`<agents>/.openfused.yaml` sidecar (adapter/model/builtin), mirroring `loadRoster`.
YAML via PyYAML (declared in `scripts/pyproject.toml`).
A malformed agent file is skipped, not fatal (same as the app). Missing roster dir
→ `[]`.

## Constraints

- No `openfused.*` imports (the exec sandbox shadows the package); roster-format +
  seed logic is hand-written in the UDF. PyYAML is a project-venv dependency.
- Parameterized via `@udf def read(slug: str = "")` (the injected decorator form).
- Read-only: never raises on a malformed/missing file.

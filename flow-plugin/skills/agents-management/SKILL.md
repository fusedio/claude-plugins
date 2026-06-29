---
name: agents-management
description: Create, read, update, delete, clone, and reset entries in the OpenFused App agent roster (~/.openfused/app/agents/). Use when managing the OpenFused agent roster.
disable-model-invocation: true
---

# agents-management

The App **agent roster** exposed as live UDFs. These UDFs are the **sole owner**
of the file tree `~/.openfused/app/agents/`: they own this local roster store,
and an agent drives them over the local execution layer started with
`fused dev serve`.

## What this project is

Six UDFs over the global roster directory: one read (`read` — list/get personas)
and five writes (`create`, `update`, `delete`, `clone`, `reset`). The managed
entity is the **persistent persona** — slug, name, title, role, description,
adapter, model, prompt, and a `builtin` provenance flag. Live runs, sessions, and
per-agent cost stats are **out of scope** (those live in the app's `state.json`,
covered by the `task-management` project).

The split is: **read via SQL** (any query over `{{read}}`, via the `/api/exec/sql`
endpoint), **write via UDF** (any mutation, via the `/api/exec/udf` endpoint).
Both endpoints are addressed with `?t=<token>&workspace=_core&project=agents-management`
— see the access pattern below.

## Access pattern

Start the local execution layer. `fused dev serve` binds a loopback server,
prints ONE JSON handshake line, then runs in the foreground:

```
fused dev serve
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}

# Export the origin + token from that handshake line:
ORIGIN=http://127.0.0.1:<port>
TOKEN=<token>

# Read — POST to the SQL endpoint; {{read}} is backed by the read UDF
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=agents-management" \
  -d '{"sql": "SELECT slug, name, role, builtin FROM {{read}}"}'

# Write — POST to the UDF endpoint
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=agents-management" \
  -d '{"udf": "create", "overrides": {"name": "Geo Wizard", "title": "Geospatial Engineer", "role": "engineer", "description": "...", "prompt": "..."}}'
```

Response shape: `{"data": <result>, "error": null}` on success;
`{"data": null, "error": "<message>"}` on failure.

## The store

The app directory is resolved per operation, highest precedence first:

1. The `app_dir` parameter on any operation (e.g. `read(app_dir="/path/to/app")`) — use this to run the skill standalone against your own store, no environment setup required.
2. The `$OPENFUSED_APP_DIR_STATE` env var when it names an app directory.
3. `~/.openfused/app` (default).

```
<app_dir>/                                 # app_dir param, else $OPENFUSED_APP_DIR_STATE, else ~/.openfused/app
├── agents/
│   ├── <slug>/AGENTS.md                   # --- YAML frontmatter --- + prompt body
│   └── .openfused.yaml                    # schema: fused/v1; per-slug adapter/model/builtin
└── agents-seed-ledger.json                # {"slugs":[...]} — keeps a deleted default deleted
```

Every operation also accepts an optional `seed_file` string param: the source of
the default roster seeded on first touch (precedence over `$OPENFUSED_AGENTS_SEED_FILE`).
When omitted, the built-in five personas in `scripts/seed_agents.json` are seeded as
today — so existing callers are unaffected. A standalone caller can supply its own
roster JSON (a list of `{slug,name,title,role,description, adapter?,model?,prompt?}`)
via `seed_file`.

- `AGENTS.md` is the portable `agentcompanies/v1` base: frontmatter
  `schema/name/title/slug/role/description`, body = the prompt.
- `.openfused.yaml` is the OpenFused vendor sidecar: it carries `adapter`, `model`,
  and `builtin` per slug, and is written **only** for a persona with non-default
  fidelity (non-default adapter, a non-null model, or `builtin: true`). A custom
  persona on the adapter default needs no sidecar entry.
- The id is **derived** from the slug: `agent_<sha256(slug)[:12]>` — the file
  carries no id. `createdAt` is the `AGENTS.md` file mtime.

These UDFs are the **canonical** implementation of the on-disk format + the
CRUD/seed semantics; the app's `/api/agents*` routes now delegate to these
UDFs over its shared `dev serve`. Last-write-wins is accepted (no in-UDF locking);
the app serializes its own roster writes with a process-side mutex, so the only
residual clobber window is between two concurrent UDF callers.

## Default personas + the seed ledger

Five defaults ship in `scripts/seed_agents.json` — the **sole source of truth**
for the default personas: `architect`, `project-manager`, `data-engineer`,
`data-analyst`, `data-qa`. Every UDF seeds the roster first (idempotent, additive),
exactly like the app's former `seedDefaultRoster`:

- A fresh roster gets all five written with `builtin: true`.
- A **newly-shipped** default reaches an existing install via the seed ledger.
- A **user-deleted** default stays deleted (the ledger still lists it), and an
  **edited** default is never clobbered.
- `reset` restores a default to its seed — and re-creates it if it was deleted
  (addressed by slug). Resetting a custom persona is an error.

## Operations

All parameters arrive as strings; empty string is the zero value. A missing
persona returns `{"ok": false, "error": "not found"}`.

### read

```
read(slug: str = "") -> list[dict]
```

Returns persona records (slug-sorted). `slug` filters to one persona by slug or
derived id; empty returns all. SQL shorthand: `SELECT * FROM {{read}}`.

### create

```
create(name, title, role, description, prompt,   # all required (non-empty)
       model="", adapter="", slug="") -> dict
```

Mints a `builtin: false` persona. `slug` defaults to `deriveSlug(name)`; `model`
empty → null; `adapter` empty → `claude_code`. Rejects an empty required field or
a slug collision.

### update

```
update(id, name="", title="", role="", description="", prompt="",
       adapter="", model="") -> dict
```

Patches the resolved persona (by slug or id). **Empty string = leave unchanged**
for every field (an intentional divergence from the app, which rejects an
explicitly-empty required field). Clearing `model` to null is not expressible —
use `reset`/`clone`.

### delete

```
delete(id="") -> dict
```

Removes `agents/<slug>/` + the sidecar entry. Leaves the seed ledger untouched, so
a deleted default does not reappear. Returns `{"deleted": true}`.

### clone

```
clone(id="", name="") -> dict
```

Creates a `builtin: false` copy of any persona under a new name (slug derived from
it) — the edit path for a built-in.

### reset

```
reset(id="") -> dict
```

Restores a default to its `seed_agents.json` seed (`builtin: true`); re-creates a
deleted default by slug. Rejects a custom persona.

## Rendering as a `sql-table` widget

The `read` UDF is enough to render the roster as a table — no app agent store,
no other UI. A saved `sql-table` widget reads through `{{_core.agents-management.read}}`,
so a single JSON-UI node gives you a sortable / filterable grid over the live
roster.

The config ships **inside the wheel** as a saved widget of this project, at
`agents-management/widgets/agents_table.json`. It materializes alongside the UDFs
to `~/.openfused/core/agents-management/widgets/agents_table.json`, so it is
available on first run with no authoring step — open it with:

```bash
fused widget open ~/.openfused/core/agents-management/widgets/agents_table.json
```

The shipped config:

```json
{
  "type": "sql-table",
  "props": {
    "title": "Agent roster",
    "sql": "SELECT slug, name, title, role, adapter, model, builtin FROM {{_core.agents-management.read}} ORDER BY slug",
    "sortable": true,
    "filterable": true
  }
}
```

The projection drops the bulky `prompt`/`description` columns for readability;
widen or filter the `SELECT` to taste (`SELECT *` returns every persona field).
This is a **read-only** view — the roster's writes (`create`/`update`/`delete`/
`clone`/`reset`) have no widget seam, so mutate through the UDF endpoint directly.

> **Where it resolves.** The `{{_core.*}}` cross-project ref needs an `_core`
> resolve context, which today means the In-Loop app's dev serve
> (`fused dev serve` / `fused inloop`). The deployed-serve bundle has no
> `_core` resolve context, so a public URL is not supported for this widget.

## Layout (skill-folder convention)

```
scripts/
├── pyproject.toml          # duckdb/pandas/pyarrow (SQL resolver) + pyyaml (roster format)
├── seed_agents.json        # the 5 default personas — read at runtime via the venv anchor
├── read/      {main.py, spec.md}
├── create/    {main.py, spec.md}
├── update/    {main.py, spec.md}
├── delete/    {main.py, spec.md}
├── clone/     {main.py, spec.md}
└── reset/     {main.py, spec.md}
```

Source lives in the wheel under `fused/_core/agents-management/` (read-only).
The local-backend venv materializes at
`~/.openfused/core/agents-management/scripts/.venv` on first startup.

## Conventions

- UDF logic imports no `openfused.*` (the exec sandbox shadows the package with a
  shim) — the roster format + seed logic is **hand-written** into each UDF, which
  therefore duplicate a self-contained helper block. Only the bulky default
  **prompts** are centralized in `seed_agents.json`, located at runtime via the
  project venv interpreter (`<scripts>/.venv/bin/python` → `<scripts>/seed_agents.json`),
  the `OPENFUSED_PROJECT_ROOT` env, or the `OPENFUSED_AGENTS_SEED_FILE` override.
- YAML (the roster format) is not in the stdlib, so the UDFs use **PyYAML** — a
  project-venv dependency declared in `scripts/pyproject.toml`, exactly like
  `duckdb`. It round-trips with the app's npm `yaml`.
- All params are strings; writes are atomic (`tmp + os.replace`).
- This project is meaningful on the **local backend** only (the roster store is a
  local host path), the same as `task-management`.

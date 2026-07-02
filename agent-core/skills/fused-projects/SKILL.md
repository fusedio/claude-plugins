---
name: fused-projects
description: The canonical end-to-end guide for an agent driving Fused — pick an environment, create a project, decompose a task into UDFs, author specs and code, validate + commit, run/preview locally (often as a rendered widget), and deploy through preview to release. Code is authored by the driving agent (no codegen command, no API key); fused supplies validation, the spec↔code pairing hook, and run/deploy. Use to take a user request from prompt to a running, viewable result.
---

# Driving Fused end-to-end (spec-first, agent-authored)

Fused organises work as **workspace ⊃ project ⊃ UDF**. You — the driving
agent — author the specs and the code; Fused supplies the scaffold, the
deterministic validators, a spec↔code consistency hook, and the run/deploy
machinery. There is **no code-generation command and no API key** in the loop:
authoring code *is your job*.

> **Built-in `_core` workspace.** Fused provides a read-only `_core` workspace.
> Its source trees are **no longer bundled in the wheel** — they are cloned at
> runtime from an external git repo into `~/.openfused/core/`, materializing at
> `~/.openfused/core/skills/<project>/` (first boot needs `git` + network).
> Its projects (e.g. `task-management`) are
> available immediately via `fused dev serve` as
> `workspace="_core", project="task-management"`. User projects live in the
> `default` workspace (or any named workspace) — `_core` (and any name starting
> with `_`) is reserved and cannot be created by users.

The full loop:

```
user request
  → pick an environment (local-first for dev)
  → decompose into projects + UDFs (py data + json widget)
    → write spec.md per UDF  → user approves SPECS (never code)
      → author main.py / main.json yourself
        → verify_code → git commit (the pairing hook keeps spec+code in sync)
          → run / preview locally (data, or a rendered widget)
            → view in the flow UI (separate tool)
              → deploy to preview → promote to release (AWS)
```

The **spec is the only artifact the user reviews**. Most tasks want a **widget**
back, not raw data — see the **fused-widgets** skill for the
py-UDF-computes → json-widget-renders pattern.

> ### What's MCP vs what's CLI
>
> The whole loop is reachable without a bespoke codegen command — you author files
> with your editor tools and use these surfaces:
>
> | Step | Surface |
> |---|---|
> | Create/select an env | **CLI** (`env create`; MCP `env_create`/`env_update` need the server started with `--enable-infra`). `list_envs`/`env_show` are read-only MCP |
> | Create a project | MCP `project_new` **or** CLI `project new` |
> | Write spec.md / author code | **you write the files** (no command) |
> | Validate code | MCP `verify_code` **or** CLI `code verify` |
> | Commit (spec+code together) | `git commit` — the pre-commit hook enforces pairing |
> | Inspect a project / sync manifest | MCP `project_show` (re-syncs `[udfs.*]` from disk) / CLI `project show` (context packet; lists UDFs but does not rewrite the manifest) |
> | Run / test code | MCP `execute_code`/`test_code` **or** CLI `code run`/`code test` |
> | Preview a widget | **CLI only** (`widget open`, the parley) — no MCP |
> | Deploy/promote/rollback | MCP (`--enable-infra`) **or** CLI |

---

## Step 0 — Pick an environment (local-first)

You do not need a cloud account to build and preview. For development, use the
**local** backend (code runs in a project venv on the host):

```sh
fused env create dev --backend local
```

AWS is the production target (deploys UDFs to stable URLs); set it up later via
the **fused-setup** skill. **Resolution:** if more than one env exists,
nothing is auto-selected — pin the project (`fused project set <project>
--env dev`) or pass `--env`/`OPENFUSED_ENV`. Verify with
`get_project_context` (`environment.resolved_env`).

> An unpinned project with multiple envs makes `code run`/widget-resolve and other
> commands warn and degrade. Pin early.

---

## Step 1 — Decompose into UDFs

Decide the UDFs. The common shape is **one or more `py` data UDFs + a `json`
widget UDF on top**:

- **`py`** (`scripts/<name>/main.py`) — computation/API; returns a value (usually a
  DataFrame).
- **`json`** (`scripts/<name>/main.json`) — a JSON-UI **widget** that visualizes a
  `py` UDF's output via the `{{ref}}` grammar. See **fused-widgets**.

> **Where the widget lives decides where it renders.** The app's project surface
> live-renders only **saved dashboards** at `widgets/<stem>.json`; a `json` UDF
> (`scripts/<name>/main.json`) is the **deployable** form and shows as *source* there.
> So when the goal is "the human views the dashboard in the flow UI", author the
> widget as `widgets/<stem>.json` — not a `json` UDF. Reach for a `json` UDF only
> when you need a deployable widget URL (preview it with `fused widget open`).
> See **fused-widgets** › "What a widget is".

Each UDF is one independent capability — lean small. Slugs:
`^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, ≤64 chars — `-` and `_` are both accepted as
segment separators, so snake_case names like `list_comments` are valid
(e.g. `sessions`, `dashboard`, `list_comments`).

---

## Step 2 — Create the project

```sh
fused project new taxi-pipeline        # or MCP: project_new("taxi-pipeline")
```

Scaffolds `openfused.toml`, `SKILL.md`, and the
`scripts/ widgets/ references/ assets/` convention dirs (with `scripts/pyproject.toml`
and `scripts/tests/`); on first use it initialises the `default` workspace as a
git repo with the openfused-managed pre-commit hook.

**It also seeds `scripts/.venv` for you** (runs `uv sync` with the baseline
widget-resolver deps — duckdb/pandas/pyarrow/pyyaml/cryptography) so a fresh
project runs one-shot on the local backend: the *first* `execute_code` / `code run`
/ widget render works without a manual `uv sync`. Seeding is best-effort — if
`uv` is missing, `OPENFUSED_LOCAL_INSTALLER=pip` is set, or `uv sync` fails (e.g.
no network), the project is still created and `project new` **returns a warning**
(CLI stderr / MCP `warnings`) telling you to seed manually.

**If you see a seeding warning (or you need more deps), extend the venv before the run step.** Use `project add-dep`, which runs `uv add` + `uv sync` in one step so the venv is never left stale (a bare `uv add` would trip the stale-venv warning until the next `uv sync`):

```sh
fused project add-dep taxi-pipeline duckdb pandas       # UDF-specific runtime deps
fused project add-dep taxi-pipeline pytest coverage --dev  # only if you'll run `code test`
```

(Equivalent manual form: `cd …/taxi-pipeline/scripts && uv add … && uv sync`. A stale venv left by a bare `uv add` is auto-reconciled on the next local `execute_code`/`code test` anyway — unless `OPENFUSED_NO_VENV_SYNC` is set — but `add-dep` keeps it clean up front.)

> `project new <name>` is the simple scaffold. `project create <name>` is the same
> scaffold plus `--description` / `--env` / `--use` flags (pin the env and make it
> active in one shot). Use whichever fits; prefer `project new` for the plain case.

---

## Step 3 — Write the specs

For each UDF, **write `scripts/<name>/spec.md` yourself** (create the folder if
needed). Fused does not draft specs — you do. A `py` spec:

```markdown
# taxi-analysis

Joins NYC taxi trips to zone boundaries and returns mean fare per zone.

## Inputs
- `bucket` (str), `prefix` (str)

## Output
DataFrame: `zone_id`, `zone_name`, `mean_fare`, `trip_count`

## Notes
- Use DuckDB for the join; filter zones with < 10 trips.
```

A `json` widget UDF also gets a `spec.md` (what it shows + which `py` UDFs it
references). Specs are free-form markdown; the more precise, the better the code.

---

## Step 4 — Get approval on the SPECS (in a widget)

**Stop and get the user to review the specs before writing code** — and **render
them in a widget**, the same way the UI's spec-review gate does, rather than
pasting the spec prose into the chat. Specs are the human-review surface; make
that surface a real rendered review, not a wall of text.

Write a **spec-review widget** and put it in front of the human with `fused
widget open` (the CLI/standalone analog of the architect's `ask_user` gate).
Mirror what the UI does:

- Render the **spec content as `markdown`** (one `markdown` node per UDF/widget
  spec) — proper headings/lists/code, not flattened into `text`. On a **revision
  round**, render a **`diff`** node instead (`before` = the previously-approved
  spec, `after` = the new one) so the human sees exactly what changed — `diff` is
  built for reviewing markdown spec changes.
- Add a slim decision control: a `text-input` (`param: "feedback"`,
  "Requested changes (optional)") and two submit buttons — **Approve**
  (`action: "approve"`) and **Request changes** (`action: "request-changes"`).

```json
{
  "type": "div",
  "props": { "style": "display: flex; flex-direction: column; gap: 16px; padding: 16px" },
  "children": [
    { "type": "text", "props": { "value": "Spec review — approve to build, or request changes", "variant": "h3" } },
    { "type": "markdown", "props": { "value": "<the full taxi-analysis spec.md here>" } },
    { "type": "markdown", "props": { "value": "<the full trip-dashboard spec.md here>" } },
    { "type": "text-input", "props": { "param": "feedback", "label": "Requested changes (optional)", "placeholder": "What should change before this is approved?" } },
    { "type": "div", "props": { "style": "display: flex; flex-direction: row; gap: 8px; justify-content: flex-end" }, "children": [
      { "type": "button", "props": { "label": "Request changes", "action": "request-changes", "submit": true, "variant": "secondary" } },
      { "type": "button", "props": { "label": "Approve specs", "action": "approve", "submit": true, "variant": "primary" } }
    ] }
  ]
}
```

`widget open` blocks until the human submits and returns the final `$param` state
(the chosen `action` + any `feedback`) to you. On **`approve`** → author the code
(Step 5). On **`request-changes`** (or any feedback) → edit the specs and re-open a
fresh review widget; loop until approved. Summarise if multiple UDFs are pending.

> **In-app worker exception.** An agent spawned by the flow app does this
> through the teamwork MCP, not `widget open`: the architect runs the `ask_user`
> spec-review gate by authoring ONE complete widget (the plan body as `text`, a
> `diff` node per changed spec file, and the approve/request-changes buttons — no
> separate `details`/`paths` args). The
> `widget open` form above is the **CLI / standalone** path.

---

## Step 5 — Author the code yourself

Write `main.py` / `main.json` into each UDF folder to satisfy its spec. **You are
the codegen** — there is no `udf generate`. Iterate by editing the spec *and* the
code together (keep them consistent — Step 6's hook enforces it).

**UDF return form (`py`):**

```python
import fused

@fused.udf
def main(threshold: int = 0):
    ...
    return df          # a DataFrame, or a scalar
```

- Prefer a `@fused.udf` entrypoint (takes params; portable; works as a fan-out
  worker and a served route). A bare top-level `result = <value>` is fine for a
  quick no-param script. **Never both** in one file.
- A `@fused.udf` UDF works as a widget `{{ref}}` source too (the resolver runs the
  same form). See **fused-execute** for libraries/secrets/S3 patterns.

**Widget (`json`):** author `main.json` as a component tree that binds to your
`py` UDFs with `SELECT … FROM {{udf-name?arg=$param}}`. See **fused-widgets**
for the config document, the `{{ref}}`/`$param` grammar, and previewing.

---

## Step 6 — Validate, then commit

Validate the code through the deterministic scanners (AST code scanner, dep
scanner, input firewall), then commit the spec+entrypoint **together**:

```sh
fused code verify scripts/taxi-analysis/main.py        # or MCP verify_code(...)
git -C ~/.openfused/workspaces/default add taxi-pipeline/scripts/taxi-analysis/
git -C ~/.openfused/workspaces/default commit -m "taxi-analysis: spec + impl"
```

The **pre-commit hook blocks one-sided commits** — a `spec.md` without its
entrypoint, or vice versa — so every committed state is internally consistent.
`git commit --no-verify` is the escape hatch for a genuine one-sided change (e.g.
fixing spec prose with no code change).

UDFs are discovered by **directory listing** (`scripts/<name>/` with `main.py` or
`main.json`), so a freshly authored UDF is already visible to run/preview — you do
not need to register it. The manifest's `[scripts.*]`/`kind` table is synced by the
**MCP `project_show` tool** and at deploy time; the CLI `project show` returns the
read-only context packet and lists UDFs but does not rewrite the manifest.

> **`archive/` — soft-deleted artifacts, never enumerated.** A project may carry a
> top-level **`archive/`** directory that mirrors the layout
> (`archive/scripts/<udf>/`, `archive/widgets/<stem>.json`,
> `archive/references/<name>.md`, `archive/canvas.toml`). It holds artifacts a human
> **archived** in the app — a reversible soft-delete. Because discovery is a shallow,
> by-name scan of the *live* dirs, archived artifacts are **invisible** to everything
> you drive: they never appear in `get_project_context` / `project show`, the pipeline
> canvas, or deploy, and a deploy of an archived UDF is simply "not found". `archive/`
> is **git-tracked** (provenance travels with the repo) but it is **not yours to
> author into**: archive/restore is an app + human operation, not a CLI step, so never
> write into `archive/`, treat it as a UDF source, or "restore" by hand-moving files.
> The one place archived source is still read is the widget resolve fallback (see
> **fused-widgets** › archived widgets).

> **`work-products.json` — the app-owned provenance manifest, read-only to you.**
> A project created/managed in the app carries a **`work-products.json` at the
> project root** (beside `openfused.toml`, **git-tracked**, one per project). It is
> the app/shell's record of each artifact (widget / UDF / reference): its `status`
> (draft/active/archived), `reviewState`, whether it's `isPrimary`, a `summary`, a
> `version` (`sha256:` of the file's content), and provenance (`producedByRunId`,
> `taskId`, `createdBy`, timestamps). Treat it exactly like `archive/`: **the shell
> is its single writer — never hand-author, edit, or "fix" it, and don't commit a
> change to it yourself.** The `fused` CLI has no command or UDF that writes it, by
> design. Editing a widget/UDF file leaves that artifact's `version` (and review
> state) in the manifest **stale**; that is expected and **self-heals on the app
> side** — new CLI-authored files are picked up by the app's catalog auto-adopt, and
> edits to existing records re-hash on the next app publish. You don't need to read
> it either: `get_project_context` already surfaces the published-artifact metadata
> derived from it, so orient from the context packet, not from the raw manifest.

> **Hard-delete a whole project: `fused project delete <name>`.** Distinct from
> the app's soft-delete `archive/`, this removes the project from the workspace:
> `git rm -rf -- <name>` + a `--no-verify` commit, then cleans gitignored residue
> (`scripts/.venv`, `__pycache__`). It rejects `_core` and any underscore-prefixed
> (reserved) name with a `ValueError`, and prints JSON `{name, deleted, root}`.

---

## Step 7 — Run / preview locally

**Local backend needs a project venv.** You should have seeded it back in Step 2
(`uv add duckdb pandas && uv sync`). If you skipped that, or a UDF you just wrote
imports something new, top it up now before running:

```sh
cd ~/.openfused/workspaces/default/taxi-pipeline/scripts
uv add <new-dep>                # whatever the py UDFs newly import
uv sync
```

A missing/incomplete `.venv` raises a guided error telling you to `uv sync`.

**Run a `py` UDF** (see its output as data):

```sh
fused code run scripts/taxi-analysis/main.py --project taxi-pipeline
# or MCP: execute_code(code=<main.py contents>, project="taxi-pipeline")
```

`test_code`/`code test` **requires `--project` on the local backend.**

**Preview a widget** (the result comes back as a rendered widget, not rows). A
**saved dashboard** (`widgets/<stem>.json`) renders in the flow UI
(Step 8) or via `widget open widgets/<stem>.json`. A **`json` UDF**
(`scripts/<name>/main.json`) is *not* live-rendered on the flow project surface — preview
it with `widget open scripts/<name>/main.json` or the parley (standing loop). To
self-verify a widget resolves *headlessly* before showing a human, drive the
resolve daemon — recipe in **fused-widgets**.

> **You open the widget — don't tell the user to** (CLI / standalone). After
> authoring and self-verifying the file, *run* `fused widget open <file>`
> yourself (it launches/reuses the widget-host, opens the browser, and blocks until the
> human responds, returning their reply). Ending your turn with "open it in
> the flow UI" strands the human — drive the surface and bring back the result.
> **Exception — an agent spawned by the flow app** (an architect/worker
> run) must NOT run `widget open`/the parley (they wait on a human and would
> hang the run): it writes `widgets/<stem>.json`, the flow UI live-renders it, and it
> asks for feedback via `ask_user` (the single human-ask tool). See **fused-widgets** › the
> decision tree.

---

## Step 8 — View in the flow UI (separate tool, out of scope)

The local web UI is **flow** — a separate client (`fusedio/flow`), started with the
`flow` CLI (or `npx @fusedio/flow` once published). Its project surface renders a
project's **saved dashboards** (`widgets/<stem>.json`) natively and hosts agent runs.
Driving flow is out of scope here — from the CLI, preview widgets with `fused widget
open` (Step 7). A `json` UDF (`scripts/<name>/main.json`) shows as source in flow,
not a live render.

---

## Step 9 — Deploy to preview (AWS)

Prerequisites (AWS only): an AWS env with `cache_bucket`, resolved for this
project, and a provisioned serving plane (`fused infra serve`). Verify the
resolved env first (`fused project show` → `environment.resolved_env`).

```sh
fused project deploy taxi-pipeline                  # all UDFs → preview
fused udf deploy taxi-analysis --project taxi-pipeline
```

A `py` UDF deploys to an HTTP route; a **`json` widget UDF deploys to a rendered
widget URL** (preview → release). The response echoes `env: <name>` and a preview
URL per UDF — **verify the env matches your intent.** Deploy always targets
`preview`; release moves only via promote/rollback.

Via MCP (`--enable-infra`): `udf_deploy("taxi-analysis", project="taxi-pipeline")`.

---

## Step 10 — Promote to release

```sh
fused project promote taxi-pipeline
fused udf promote taxi-analysis --project taxi-pipeline
```

Repoints release to whatever commit preview runs; the release URL is stable from
first promote. Roll back with `udf rollback … [--to <commit>]` (only prior
release commits are valid targets). MCP: `udf_promote`/`udf_rollback`
(`--enable-infra`).

---

## Iterating

Behaviour wrong? **Edit `spec.md` and the code together** (both under `scripts/<name>/`),
re-`verify_code`, re-run/preview, and commit (the hook keeps the pair consistent).
For widgets, re-open to re-preview. There is no regenerate command — you re-author
the changed UDFs.

---

## Guardrails

### Spec-first, agent-authored
The user reviews specs, not code. Author code only after spec approval. Keep
`spec.md` and the entrypoint consistent — the pre-commit hook enforces it on
commit.

### The env is resolved per project — verify before deploying
Every deploy/promote/rollback echoes `env: <name>`. If it is wrong, pin
(`fused project set <project> --env <name>`) or override (`--env` /
`OPENFUSED_ENV`). With a single env it auto-selects; with several you must pin.

### Deploy to preview first; promote to release
The two-channel model exists so code passes through preview before release.
`udf deploy --channel release` is only for bootstrapping the very first release
URL.

### Retiring a UDF
`fused udf retire <udf> --project <p> --yes` revokes both channel mounts and
drops the UDF from the cloud snapshot (the on-disk folder stays). Destructive
(`--enable-destructive` on MCP). A UDF present in the cloud snapshot but absent
on disk shows as **orphaned** in `project status`.

### Charts use fused components — never Vega-Lite / Plotly / matplotlib

A dashboard widget is a `{"type": <component>, "props": {…}}` JSON file in
`widgets/`. The `type` MUST be a built-in fused component — charts are
`line-chart`, `bar-chart`, `stacked-bar-chart`, `stacked-area-chart`,
`scatter-chart`, `donut-chart`, `heatmap-chart` (plus `metric`, `sql-table`,
`text`, `html`, inputs, …). **Do NOT** emit a Vega-Lite / Vega / Plotly /
matplotlib spec or inline a data array — those are not fused components and
render as `unknown component: <type>`. The supported set is generated from the
widgets package (`components.json`, the hard type gate); when unsure, read
the component catalog in the **fused-widgets** skill rather than guessing.

A chart gets its data from a **`sql` prop** (DuckDB) that reads a UDF via
`{{udf_name}}` and aliases the result columns to the chart's contract — e.g.
`SELECT month AS label, sum(revenue) AS value FROM {{sales}} GROUP BY 1`. The
DuckDB resolver is sandboxed and **cannot read files**, so every chart needs a
backing UDF in `scripts/`; it cannot read a `references/` file directly. Author
each widget UDF with a `udf(...)` entry function returning a DataFrame (helper
functions alongside it are fine); on the local backend its imports come from the
project `.venv` (`uv add …`).

---

## MCP gating reference

| Operation | MCP tool | Gate |
|---|---|---|
| Create / inspect project | `project_new` / `project_show` / `list_projects` / `project_status` | ungated |
| Validate code | `verify_code` | ungated |
| Run / test code | `execute_code` / `test_code` | ungated |
| Deploy / promote / roll back a UDF | `udf_deploy` / `udf_promote` / `udf_rollback` | `--enable-infra` |
| Retire a UDF | `udf_retire` | `--enable-destructive` |

There is **no codegen MCP tool** — authoring is `Write` + `verify_code` + `git` +
`project_show`, all already agent-reachable. Widget preview is CLI/app-only.

---

## See also

- **fused-widgets** — authoring + previewing widgets (the usual "result").
- **fused-execute** — `execute_code`/`code run` patterns (libraries, S3, secrets).
- **fused-setup** — install + AWS env provisioning.
- **fused-cli** — full command/flag reference and the local-servers inventory.

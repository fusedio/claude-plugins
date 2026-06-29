---
name: openfused-widgets
description: Authoring and previewing JSON-UI widgets as the response of running a project — the py-UDF-computes → json-widget-visualizes pattern, the {{ref}}/$param data grammar, how resolution runs through the compute backend, and the CLI/app surfaces (widget open, parley, fused inloop, deployed URL) that put a rendered widget in front of a human. Use whenever the desired output of a UDF/project is a widget, not raw data.
---

# Widgets — getting a rendered result back

In most OpenFused flows the thing a human wants back is a **widget** (an
interactive dashboard), not a raw value. A widget is a JSON config; running it
yields *resolved rows that a renderer turns into a visual*. This skill covers
authoring widgets and getting them in front of a human.

**There are NO MCP widget tools.** Agents author widget *files*; humans *view*
them through the CLI (`fused widget open` / the parley) or the app
(`fused inloop`). Everything below is CLI/app, never MCP. (See
`openfused-projects` for where this sits in the project lifecycle, and
`openfused-cli` for the full `widget` command flag tables.)

---

## What a widget is

A widget is a single JSON document — a tree of nodes, each
`{ "type": "<component>", "props": { … }, "children": [ … ] }`. It lives in one
of two places in a project — **and the two render on different surfaces, so the
choice matters:**

- **`widgets/<stem>.json`** — a **saved project dashboard**. This is the form the
  app's **project surface live-renders**: in `fused inloop` the project's **Widget**
  tab lists it and it draws the rendered widget (an **Open ↗** card). **Author here
  when the human will browse the dashboard in the app.**
- **`scripts/<name>/main.json`** — a **`json`-kind UDF**: a first-class, **deployable**
  entrypoint (deploys to a stable widget URL). On the project surface it appears as
  **source** ("View source ↗"), **not** a live render. Preview it rendered with
  `fused widget open scripts/<name>/main.json` (the file render path) or by
  deploying it — **not** by browsing the project in `fused inloop`.

> The config is identical either way (same `{{ref}}`/`$param` grammar), so this is
> purely *where the file lives*. The default for "show the human a dashboard" is
> `widgets/<stem>.json`. If you also need a shareable URL, keep the deployable copy
> at `scripts/<name>/main.json` as well.

> **Always pair a widget with a spec.** For every `widgets/<stem>.json` you save,
> write a `widgets/<stem>.spec.md` contract sidecar next to it — purpose, the
> `{{udf}}` data it binds, and the components + their SQL — the SAME spec↔file
> pairing a UDF has (`scripts/<stem>/spec.md`). The app renders it in the widget's
> **Preview ⇄ Spec** toggle, and `data-qa` verifies the widget against it; a widget
> without its `spec.md` is incomplete.

The renderable component set is fixed and comes from a single generated source
of truth (`widgets/components.json`); a `type` outside it is a hard error. The
current components:

| Group | Components |
|---|---|
| Layout / display | `div`, `form`, `text`, `markdown`, `diff`, `html`, `image`, `video`, `iframe`, `canvas`, `button`, `metric` |
| Charts | `bar-chart`, `line-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`, `stacked-bar-chart`, `stacked-area-chart` |
| Data | `sql-table` |
| **Inputs** (write a `$param`) | `dropdown`, `checkbox-group`, `slider`, `number-input`, `text-input`, `text-area`, `datetime-input`, `color-input`, `file-upload`, `camera-input`, `gallery-input`, `video-review` |

Input components carry a `param` prop and a `defaultValue`; they seed the param
store on first paint and re-resolve dependent queries when the human changes
them.

> **This is OpenFused, not Fused.** Author widgets ONLY against this catalog.
> Do **not** use any Fused-branded skill (`fused:*`, e.g. `fused:json-ui-schemas`,
> `fused:canvas-toml`) or Fused's JSON-UI schema — it carries components OpenFused
> does not support, and an unsupported `type` is a hard render error. The live,
> authoritative list for the project you're in is the `widget_components` array in
> `get_project_context` (`[{type, hasChildren, isInput}, …]`) — orient on it.

### Component reference (key props — `style` applies to all, omit unless overriding)

Charts read **fixed result columns** (alias your SELECT to them), not props:

| type | reads columns | key props |
|---|---|---|
| `bar-chart` | `label`, `value` | `sql`, `title`, `barColor`, `horizontal`, `showValues`, `xAxisLabel`, `yAxisLabel` |
| `line-chart` | `label`, `value`, opt `series` | `sql`, `title`, `lineColor`, `curveType`, `showArea`, `xAxisLabel`, `yAxisLabel` |
| `stacked-area-chart` | `label`, `value`, opt `series` | `sql`, `title`, `curveType`, `showLegend`, `showBrush`, `xAxisLabel`, `yAxisLabel` |
| `stacked-bar-chart` | `label`, `value`, opt `series` | `sql`, `title`, `horizontal`, `showLegend`, `barColor`, `xAxisLabel`, `yAxisLabel` |
| `donut-chart` | name, value | `sql`, `title`, `innerRadius`, `showLabels`, `showCenterTotal` |
| `scatter-chart` | `x`, `y`, opt `series`/`size`/`label` | `sql`, `title`, `pointColor`, `xLabel`, `yLabel` |
| `heatmap-chart` | `x`, `y`, `value` | `sql`, `title`, `lowColor`, `highColor`, `showValues` |

**Always title chart axes.** Set `xAxisLabel`/`yAxisLabel` on the cartesian charts above
(and `xLabel`/`yLabel` on `scatter-chart`) so each axis names what it shows — an unlabeled
axis is an incomplete chart. These are axis *titles*, separate from the per-tick labels.

Display / data:

| type | key props |
|---|---|
| `text` | `value` / `sql`, `variant` (default/muted/small/large/h1–h4) — a single value |
| `markdown` | `value` / `sql` — GitHub-flavored prose (headings/lists/tables/code) |
| `diff` | `before` + `after` (computed) OR `diff` (unified string), `oldLabel`, `newLabel` |
| `metric` | `value` / `sql`, `label`, `format`, `prefix`, `suffix`, `decimals` |
| `sql-table` | `sql`, `title`, `sortable`, `filterable`, `maxRows` |
| `image` / `video` | `src` (+ `alt`/`poster`/`controls`…) |
| `html` | `value` (raw HTML — escape hatch; prefer `markdown`) |
| `iframe` | `src` (absolute http(s)), `title`, `allow` |
| `div` / `form` | `style` (layout container; `children`) |
| `map` | `layers` (UDF geometry), `mapStyle` — simple geometry |
| `fused-map` | `layers` (deck.gl: h3/heatmap/arc/tiles), `showLegend`, `showLayerPanel` — advanced |
| `map-bounds` | `param` — viewport-as-input only (no data) |

Inputs (write `param`; all take `param`, `label`, `defaultValue`):

| type | extra key props |
|---|---|
| `dropdown` | `options` `[{value,label}]` (REQUIRED, non-empty), opt `sql` |
| `checkbox-group` | `options` `[{value,label}]` — multi-select (writes an array) |
| `slider` | `min`, `max`, `step` |
| `number-input` / `text-input` / `text-area` | `placeholder` (+ `rows` for text-area) |
| `datetime-input` / `color-input` | — |
| `button` | `label`, `action`, `submit`, `variant` |

Prose vs raw HTML vs scalar: use **`text`** for a single value (a label, a count),
**`markdown`** for prose / reports / notes (headings, lists, tables, code — GitHub
flavored), and **`html`** only when you need raw HTML. Use **`diff`** to show the
change between two texts — pass `before` + `after` (the line diff is computed for
you) or a precomputed unified-diff string in `diff`; built for reviewing markdown
spec changes. Lean on the built-in defaults — omit `style` unless you need a
deliberate override (one consistent default look across every surface).

> **`checkbox-group` is the multi-select reply channel** — the array twin of
> `dropdown`. It is the input to reach for when an ask allows **more than one**
> answer (an `ask_user` widget whose question allows more than one choice). It
> writes the chosen option
> `value`s to its `param` as a **`string[]`**. Because the param holds an array,
> it (like `sql-table`'s `selectionParam` and `video-review`) **must never be
> referenced in SQL** — `$param` is text substitution and only scalars are
> SQL-safe. Use a `dropdown` for single-select.

---

## The core pattern: a `py` UDF computes, a `json` widget visualizes

This is the shape of almost every project. A `py` UDF returns a DataFrame; a
`json` widget binds to it in a DuckDB SQL string via the `{{ref}}` grammar.

**`scripts/sales/main.py`** — the data UDF:

```python
import fused

@fused.udf
def main(region: str = "all"):
    import pandas as pd
    df = pd.read_parquet("s3://my-bucket/sales.parquet")
    if region != "all":
        df = df[df["region"] == region]
    return df[["month", "region", "revenue"]]
```

**`widgets/sales-board.json`** — the saved dashboard that renders it (use
`scripts/sales-board/main.json` instead if this widget is a deployable entrypoint):

```json
{
  "type": "div",
  "props": { "style": "display: grid; gap: 16px; padding: 16px" },
  "children": [
    { "type": "text", "props": { "value": "Revenue across regions", "variant": "h3" } },
    { "type": "dropdown", "props": {
        "param": "region", "label": "Region",
        "options": [{"value": "all", "label": "All"}, {"value": "emea", "label": "EMEA"}],
        "defaultValue": "all" } },
    { "type": "slider", "props": {
        "param": "min_revenue", "label": "Min revenue",
        "min": 0, "max": 500, "defaultValue": 0 } },
    { "type": "metric", "props": {
        "label": "Total revenue", "format": "currency", "prefix": "$",
        "sql": "select sum(revenue) as value from {{sales?region=$region}}" } },
    { "type": "bar-chart", "props": {
        "sql": "select month, sum(revenue) as revenue from {{sales?region=$region}} where revenue >= $min_revenue group by month order by month" } },
    { "type": "sql-table", "props": {
        "title": "Raw rows",
        "sql": "select month, region, revenue from {{sales?region=$region}} where revenue >= $min_revenue order by month limit 50" } }
  ]
}
```

The `dropdown`/`slider` write `$region`/`$min_revenue`; the `metric`,
`bar-chart`, and `sql-table` read them and re-resolve when they change.

**Reading a bundled project asset** (a file under the project's `assets/`): use
`openfused.asset_path(...)`, never a relative `./assets/...`, a `__file__`-relative
path, or a hard-coded absolute path. A UDF runs in a throwaway sandbox cwd, so only
a project-root-anchored path resolves — and the widget *render* path is exactly where
the relative forms silently break (blank dashboard / `FileNotFoundError`):

```python
import openfused
df = pd.read_parquet(openfused.asset_path("data.parquet"))   # robust, one-shot
```

**Geo data → always a map.** When the data has a geographic dimension (lat/lon,
geometry, or geocodable place/address columns), include a `fused-map` in the
dashboard by default — unless the user explicitly says not to. A map is the default
for geo data, not an optional extra.

### The `{{ref}}` / `$param` grammar (essentials)

- `{{sales}}` — the whole result of the `sales` UDF, default params.
- `{{sales?region=$region}}` — pass kwarg `region` bound to the param `$region`.
- `{{sales?region=emea&limit=50}}` — bare literals (string `emea`, number `50`);
  single-quote a value that must stay a string or contain `& = ` whitespace:
  `{{sales?region='emea, west'}}`.
- `name` may contain `-` (`{{my-udf}}`). Two refs with identical name+args share
  one UDF run / one DuckDB view; distinct args run the UDF again.
- **Cross-project (`{{_core.proj.udf}}`)** — a bare `{{udf}}` resolves in the
  current project; a three-segment ref reuses a UDF from the built-in `_core`
  workspace, e.g. `{{_core.task-management.create}}` (read path) or a button
  `executor` firing the same name (write path). Only the allowlisted `_core`
  workspace is reachable (any other first segment → `unknown endpoint`); its
  source is the packaged `core_source_dir()` but it RUNS under the
  **consuming** project's venv, so keep shared UDFs dependency-light. `_core` refs
  resolve on every local surface — they all route through `fused dev serve`,
  whose directory-addressed modes (`?dir=`/`?projectDir=`, used by `widget open` /
  parley) inject the built-in `_core` shared root by default — so a standalone
  widget (e.g. the task-board's `mutateBackend: "core"`) can drive the built-in
  `_core` UDFs; only the deployed-serve bundle can't.
  App-parity note: this is an OpenFused-only extension — a cross-project ref won't
  resolve if pasted into the Fused app.
- `$name` is an **inline text substitution** (not a DuckDB bind param), so it
  works anywhere — including inside `'…'` and `"…"`. Grammar: `$[A-Za-z_]\w*`.
  Substitution is context-aware (quotes are doubled; comments/dollar-quoted
  bodies are left verbatim). This matches the Fused app byte-for-byte, so a
  config authored here pastes into the app and behaves identically.

The `{{ref}}` / `$param` grammar above is the full contract.

> **Archived widgets (soft-deleted, reachable by link).** When a human archives a
> widget in the app it moves to `archive/widgets/<stem>.json` and is **read-only** —
> gone from the canvas, the Widget tab, and `get_project_context`, but still loadable
> through a **task deep-link**. A bare `{{udf}}` resolves from the live `scripts/`
> dir; if that UDF was *also* archived, the resolver falls back to
> `archive/scripts/<udf>/` so a fully-archived **widget + UDF** pair still resolves its
> data when opened via the link. The fallback fires only for the **exact ref** the
> widget names — archived UDFs are never enumerated, so they stay out of every catalog.
> You don't author or restore archived widgets from here (that's an app + human
> action); just know an archived widget you reach by link still renders.

### Core UDFs → custom views (no project setup)

The built-in `_core` workspace ships ready-to-use UDFs that **any ad-hoc widget can
read or act on directly** via a `{{_core.<project>.<udf>}}` ref (read) or a button
`executor` firing the same name (write). This is how a user gets a **custom view**
of OpenFused's own state — a bespoke task board, an inbox triage panel, a run
monitor — without authoring any backing UDF: bind a chart/table straight to a
core UDF. No setup, no env, no `uv add` for the core source itself — the
directory-addressed surfaces (`widget open`, parley, `fused dev serve`) inject
the `_core` root automatically.

The shipped `_core` projects and their UDFs:

| Project | Read UDFs (for views) | Write/act UDFs (button `executor`) |
|---|---|---|
| `task-management` | `read`, `list_comments` | `create`, `update_status`, `assign`, `add_comment`, `set_blocked_by`, `delete` |
| `feedback-management` | `inbox_view`, `list_cards`, `list_open_cards`, `get_card` | `create_card`, `resolve_card`, `cancel_task_cards`, `acknowledge_feedback` |
| `run-management` | `read`, `transcript` | `create`, `finish`, `set_prompt`, `fail_started` |
| `agents-management` | `read` | `create`, `update`, `clone`, `delete`, `reset` |
| `secrets-management` | `list` | `get`, `put`, `delete` |

Example — a custom open-tasks board bound directly to the core task store:

```json
{ "type": "sql-table", "props": {
    "title": "Open tasks",
    "sql": "select title, assignee, status from {{_core.task-management.read}} where status != 'completed' order by updatedAt desc" } }
```

A write needs a `button` whose `executor` fires the qualified name, e.g.
`"executor": "_core.task-management.update_status?id=$selectedId&status='completed'"`.
Same rules as any `{{ref}}`: the UDF runs under the **consuming** widget's venv, so
core UDFs are kept dependency-light. Only the deployed-serve bundle can't reach
`_core`; every local surface can.

---

## How "running" a widget works

A widget does **not** return a `result` value the way a `py` UDF does. Instead,
each data-bound node's `sql` is **scanned → planned → resolved into rows**:

1. **Plan** — scan each `props.sql`, stamp a stable `queryId`, harvest input
   defaults, build the `param → [queryId]` dependency map.
2. **Resolve sources** — map each `{{name}}` to a UDF source on disk
   (`scripts/<name>/main.py`).
3. **Resolve** — build a self-contained resolver program (DuckDB runtime + the
   per-query SQL + the resolved UDF sources) and run it through
   **`ComputeBackend.execute`** — the *same backend and content-addressed cache
   as `execute_code`*. In the sandbox: run each `{{ref}}` fresh → register a
   DuckDB view → rewrite the SQL to those views → substitute `$param` → execute
   → encode rows. Returns `{ "data": {queryId: {columns, rows}}, "errors": {…} }`.

**List/dict-valued UDF columns.** When a `py` UDF returns a DataFrame with
columns that contain Python lists or dicts (e.g. `blockedBy: []` in task
records), the resolver JSON-encodes those cells before registering the DuckDB
view (so DuckDB can accept them as strings), then decodes them back to
arrays/objects in the output rows. This is transparent — the renderer receives
the original list/dict values, not strings.

**Consequence for the local backend:** because resolution runs through the
project's compute backend, the project venv must contain `duckdb` (plus
`pandas`/`pyarrow`, provided automatically) **and** any libraries the referenced
`py` UDFs import. Add them and sync before previewing:

```sh
cd ~/.openfused/workspaces/default/<project>
uv add duckdb pandas        # + whatever the py UDFs import
uv sync
```

A missing/incomplete `.venv` surfaces a guided error telling you to run
`uv sync`. (`project new` does **not** create `.venv`.) Best practice: seed the
venv right after `project new`, not when the first resolve fails — see
`openfused-projects` Step 2.

---

## Triggering a UDF on a button press (act, not just read)

The flow above is **read** — data flows UDF → rows → widget. A `button` can also
**act**: run a UDF *on press* via its `executor` prop.

```json
{ "type": "button", "props": {
    "label": "Promote",
    "executor": "promote-udf?id=$selectedId&channel='release'"
} }
```

- `executor` is a **brace-less `{{ref}}` body** — the SAME grammar as SQL: a UDF
  name, optional `?k=v&k2=$param` args, `$param` bound against the live params at
  click time (single-quote literals as in SQL). Authoring it is just the
  `{{ref}}` grammar above minus the braces. The UDF name is its **project slug**
  (kebab-case, e.g. `promote-udf`), the same name a `{{ref}}` reads it under — or a
  qualified `_core.task-management.create` to fire a built-in `_core` UDF (same
  cross-project rule as reads).
- The press fires the UDF **once** (it is event-triggered, not reactive like a
  `$param` change). The button shows a running state and disables mid-flight; an
  error surfaces on hover. The UDF is **invoked directly** (the args become typed
  kwargs — no SQL is synthesized), and its **raw return value** comes back as
  `data` in the `{data, error}` envelope: a DataFrame/Arrow table as records, a
  dict/list/scalar verbatim.
- It runs through the same compute backend as reads — **so the project venv needs
  the UDF's imports**, same as the read path. Caching is forced off (a write must
  re-run every press).
- **Surface scope:** works where there is a local host (the `fused inloop` app,
  `widget open`, parley). On the deployed-serve bundle / MCP-Apps sandbox there is
  no executor, so an `executor` press is a visible no-op (the button still
  renders). Pair `executor` with `action` on the same button to ALSO report a
  feedback event.
- v1 is fire-and-forget: the button does not yet auto-refresh dependent queries
  from the UDF's result. To reflect a write, have the UDF mutate state a read
  `{{ref}}` re-reads, and re-resolve (e.g. bump a `$param` the read depends on).


---

## Self-verify a widget resolves (headless)

Before showing a human, confirm the widget actually resolves to data — there is
no GUI in the loop and `widget open` blocks for a human. Drive the resolve daemon
the app uses (`fused dev serve`) directly: it prints one handshake line
(`{origin, port, token, pid}`), then serves the token-gated
`POST /api/exec/widget`. Address it in flat directory mode with `?dir=<abs>` (the
sibling `*.py` next to the widget are passed as inline `sources`):

```sh
DIR=~/.openfused/workspaces/default/<project>/scripts/<widget>
fused dev serve --timeout 60 >/tmp/ds.out 2>/tmp/ds.err &
# read the handshake (first stdout line)
read ORIGIN TOKEN < <(python3 -c 'import json;h=json.load(open("/tmp/ds.out"));print(h["origin"],h["token"])')
# POST the widget config; the body is {"config": <the main.json contents>}
curl -s -X POST "$ORIGIN/api/exec/widget?t=$TOKEN&dir=$DIR" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json;print(json.dumps({"config":json.load(open("'"$DIR"'/main.json"))}))')"
```

The response is `{"data": {queryId: {columns, rows}}, "errors": {…}, …}`. **Success
= `errors` is empty and `data` has rows.** A per-query failure (bad SQL, a UDF
error, a missing `{{ref}}` source, a missing `$param`) appears under
`errors[queryId]` and never blanks the rest — read it to fix the SQL or the
referenced UDF. A source that returns `[]` (zero rows) is a **success**, not an
error: it lands in `data` as an empty result (`{columns: [], rows: []}`) and the
widget renders empty — so a zero-row dataset is a clean empty widget, not an
in-card error. The daemon resolves through the project's compute backend, so it
needs the project venv (`duckdb` + the py UDFs' deps; see above).

> `fused dev serve` is normally internal plumbing the app spawns — driving it
> directly is the supported way for an **agent** to self-check a widget headlessly.

---

## Getting a widget in front of a human — decision tree

> **CLI / standalone agent: open the widget yourself — do not tell the human to
> open it.** Once you have authored (and headlessly self-verified) the widget file,
> *you* run the surface command — `fused widget open <file>` for a one-shot, or
> push it into the parley for a standing loop. `widget open` launches/reuses the app
> server, opens the browser, and blocks until the human responds, handing you their
> reply. Never end your turn with "open the file in `fused up` to see it" — that
> strands the human; drive the surface and bring back the result.
>
> **⚠ Agents spawned by the `fused up` app (architect / data-analyst / QA
> worker runs) MUST NOT run `fused widget open` / `widget push` / `fused
> up`.** Those surfaces wait on a human at a keyboard and would **hang the run** (or
> collide with the already-running app). In that context the widget flow is
> different: a `data-analyst` just **writes `widgets/<stem>.json`** and the app
> **live-renders it natively** in the Widget tab — no command to run; feedback is
> asked via the teamwork MCP (`ask_user` — the single human-ask tool), and `data-qa` self-checks a
> widget headless via `POST /api/exec/widget`. The "run `widget open` yourself" rule
> is for an agent driving OpenFused from the CLI, not for an in-app worker.

All four surfaces render the **same config** through the **same resolver**. Pick
by the interaction you need:

| You want… | Use | Command | Response back to the agent |
|---|---|---|---|
| **One-shot** feedback ("show this, tell me when done") | `widget open` | `fused widget open scripts/sales-board/main.json` | Blocks until the human submits/closes; prints the final `$param` state as one JSON line to stdout |
| **A standing loop** (push successive views, stream human events) | **parley** | `widget push <cfg>` + `widget watch` (or `widget agent`) | NDJSON event stream (`action`/`close`); push a new view and keep watching |
| **The project surface** (browse **saved dashboards** with project data) | the app | `fused inloop` → open the project → **Widget** tab | Human-driven; a feedback task can spawn a follow-up agent run with the human's response. **Only `widgets/<stem>.json` live-renders here** — a `json` UDF shows as source. |
| **A shareable URL** (stakeholder, no local server) | deploy | `fused udf deploy sales-board --project <p>` | A rendered widget URL (preview → promote to release) |

- `widget open <target>`: `<target>` is a `.json` path or a saved-widget stem.
  It launches/reuses the app server, opens the browser, and blocks. `--no-open`
  still blocks (prints the URL). This is the canonical "ask the human" path for
  an agent.
  - **`-c/--config TEXT` (or `--config -` for stdin):** pass the widget config
    **inline** instead of a `<target>` — one call instead of `Write` a `.json`
    then `open` it. Mutually exclusive with `<target>`. Best for **one-shot**
    asks (approvals, questions) that settle and exit; the config is **not
    editable** (no durable file), so for an edit-and-refresh loop keep authoring a
    named `.json` and `open` its path. `widget push -c/--config` is the parley
    counterpart (no temp file; `--source PATH` sets the edit anchor).
  - **`--project-dir PATH`** (only for `.json` file targets): pins `fused dev
    serve`'s `?projectDir=` mode to a project directory so UDFs in `scripts/` and the project
    `.venv` are available. Use this when the widget file sits outside the project
    tree but needs that project's UDFs/environment. Mutually exclusive with
    `--project`.
- **parley** (`widget push`/`watch`/`parley`/`agent`) is the standing
  agent↔human channel — successive views land on one persistent page and the
  human's events stream back as NDJSON. Use it for iterative refinement. Details
  + flags: `openfused-cli` (widget section).
- `fused inloop` renders **saved dashboards** (`widgets/<stem>.json`) **natively**
  (no iframe/bundle) with data resolved by the single headless daemon the app
  owns (`fused dev serve` — internal plumbing; you never start it yourself). A
  `json` UDF (`scripts/<name>/main.json`) is **not** live-rendered on the project
  surface — it appears under the UDF drill-in as source/spec; preview a json UDF
  with `widget open` (above) or deploy it.
- **Deployed** `json` UDFs build a self-contained `widget.html` bundle + a gated
  resolver data route → a stable widget URL. This is the one place a renderer
  bundle (not the app) serves the widget.

---

## Authoring checklist for an agent

1. Decide the split: which `py` UDF(s) compute the data, and the `json` widget
   that visualizes them via `{{ref}}`.
2. Write each UDF's `spec.md`, get spec approval, then write the entrypoint
   yourself: `scripts/<name>/main.py` for a `py` UDF. For the **widget**, pick the
   home by goal (see "What a widget is"): **`widgets/<stem>.json`** if the human
   will browse it in `fused inloop` (the only form the project surface
   live-renders), or **`scripts/<name>/main.json`** if it's a deployable entrypoint
   (preview via `widget open`, not the project surface). **A `widgets/<stem>.json`
   gets its own `widgets/<stem>.spec.md` sidecar too** (purpose + the data/components
   it binds) — the same spec↔file pairing UDFs have; the app shows it in the widget's
   Preview ⇄ Spec toggle. Validate py code with `fused code verify <file>` (or
   MCP `verify_code`) before committing. There is no `udf generate` command — the
   agent authors the file. See `openfused-projects` for the full spec-first flow.
3. Local backend: `uv add` the deps the py UDFs (and DuckDB) need, then
   `uv sync`.
4. Preview — **run the surface command yourself; never hand the human a path to
   open.** A **saved dashboard** (`widgets/<stem>.json`): if the human is already in
   `fused inloop` it live-renders in the Widget tab, otherwise *you* run `fused
   widget open widgets/<stem>.json`. A **`json` UDF** (`scripts/<name>/main.json`):
   *you* run `fused widget open scripts/<name>/main.json` (one-shot) or push it
   into the parley — the project surface in `fused inloop` shows it as **source**,
   not a render. `widget open` blocks until the human responds and returns their
   reply to you. (This is the **CLI / standalone** path. An **in-app worker** never
   runs `widget open` — it writes the `.json` and the app live-renders it; see the
   ⚠ note under the decision tree.)
5. Iterate by editing `spec.md` then updating the entrypoint to match (both under
   `scripts/<name>/`); commit both together (the pre-commit hook enforces
   spec+entrypoint pairing); re-open to re-preview.
6. Deploy the `json` UDF to a widget URL when ready (`udf deploy` → promote).

---

## See also

- `openfused-projects` — the end-to-end lifecycle (env → project → UDF gen →
  run → widget → `fused inloop` → deploy), and the spec-first generation loop.
  Includes the `_core` built-in workspace note.
- `openfused-cli` — full `widget` command flags (`open`/`push`/`watch`/`parley`/
  `serve`) and the app (`up`); also documents `fused dev serve` which can
  address the built-in `_core` workspace (`workspace="_core"`) with no user setup.

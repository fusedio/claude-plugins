---
name: fused-widgets
description: Authoring and previewing JSON-UI widgets as the response of running a project — the py-UDF-computes → json-widget-visualizes pattern, the {{ref}}/$param data grammar, how resolution runs through the compute backend, and the CLI surfaces (widget open, parley, deployed URL) that put a rendered widget in front of a human. Use whenever the desired output of a UDF/project is a widget, not raw data.
---

# Widgets — getting a rendered result back

In most Fused flows the thing a human wants back is a **widget** (an
interactive dashboard), not a raw value. A widget is a JSON config; running it
yields *resolved rows that a renderer turns into a visual*. This skill covers
authoring widgets and getting them in front of a human.

**There are NO MCP widget tools.** Agents author widget *files*; humans *view*
them through the CLI (`fused widget open` / the parley). The separate **flow** UI
(`fusedio/flow` — started with the `flow` CLI, or `npx @fusedio/flow` once
published) can also render them, but driving flow is **out of scope** for this
skill; everything below is the `fused` CLI, never MCP. (See
`fused-projects` for where this sits in the project lifecycle, and
`fused-cli` for the full `widget` command flag tables.)

---

## What a widget is

A widget is a single JSON document — a tree of nodes, each
`{ "type": "<component>", "props": { … }, "children": [ … ] }`. It lives in one
of two places in a project — **and the two render on different surfaces, so the
choice matters:**

- **`widgets/<stem>.json`** — a **saved project dashboard**, addressed by its
  **stem** (`fused widget open <stem> --project <p>`). This is also the form the
  separate **flow** UI live-renders on its project surface (out of scope here).
  **Use this form when the human will browse the dashboard.**
- **`scripts/<name>/main.json`** — a **`json`-kind UDF**: a first-class, **deployable**
  entrypoint (deploys to a stable widget URL). Preview it rendered with
  `fused widget open scripts/<name>/main.json` (the file render path) or by
  deploying it. In the flow UI it appears as **source** ("View source ↗"), **not**
  a live render.

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
| **Inputs** (write a `$param`) | `dropdown`, `checkbox-group`, `slider`, `number-input`, `text-input`, `text-area`, `datetime-input`, `color-input`, `file-upload`, `camera-input`, `gallery-input` |
| **Feedback primitives** (Fused-owned; carry intent beyond a scalar value — never SQL-referenced) | `button`, `video-review`, `canvas`, `task-board` |
| **Source** | `sql-runner` |

Input components carry a `param` prop and a `defaultValue`; they seed the param
store on first paint and re-resolve dependent queries when the human changes
them.

> **Use this catalog — not the external Fused-branded skills.** Author widgets
> ONLY against this catalog (the `agent_core` widget set). Do **not** use any
> external Fused-branded skill (`fused:*`, e.g. `fused:json-ui-schemas`,
> `fused:canvas-toml`) or the hosted Fused product's JSON-UI schema — those target
> a different product and carry components this catalog does not support, and an
> unsupported `type` is a hard render error. The live,
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
| `map` | `layers` (UDF geometry), `mapStyle`, `centerLng`, `centerLat`, `zoom`, `param`, `sendParam` — simple geometry |
| `fused-map` | `layers` (deck.gl: scatterplot/geojson/h3/heatmap/arc/mvt/raster), `basemap`, `centerLng`, `centerLat`, `zoom`, `param`, `showLegend`, `showLayerPanel`, `showBasemapSwitcher` — advanced |
| `map-bounds` | `param`, `centerLng`, `centerLat`, `zoom`, `mapStyle`, `autoSend`, `buttonLabel` — viewport-as-input only (no data) |
| `sql-runner` | `name`, `sql` — server-side **source** container (runs a named query once, exposes it to descendants as `{{name}}`); not a rendered output. Renders everywhere (no heavy deps). |

> **Maps render in the native renderer only.** `map`, `map-bounds`, and `fused-map`
> need heavy WebGL deps + external tiles the self-contained deployed bundle does
> not ship, so the deployed build aliases the map modules to a **placeholder** —
> they render only in the native renderer (`fused widget open` / the parley / the
> flow UI), not on a deployed URL.

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
  App-parity note: this is an extension specific to this platform (`agent_core`) —
  a cross-project ref won't resolve if pasted into the external Fused app.
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
of Fused's own state — a bespoke task board, an inbox triage panel, a run
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
`fused-projects` Step 2.

### Live dashboards: `refreshInterval` (client-side polling)

A data-bound node can **poll** on its own — set `props.refreshInterval` to an
interval in **milliseconds** and the renderer re-resolves that source on a timer
(a `map`/`fused-map` node also accepts a per-layer `refreshInterval` under each
layer). Use it for live dashboards (a metric or chart that should track changing
UDF output without a human interaction).

```json
{ "type": "metric", "props": {
    "label": "Active runs", "refreshInterval": 5000,
    "sql": "select count(*) as value from {{_core.run-management.read}} where status = 'started'" } }
```

- **Floor is 1000 ms.** Sub-floor values are clamped up to 1000 ms; a
  non-positive / non-finite / non-number value is rejected (no timer scheduled).
- It's **purely client-side** — timers live in the renderer (the widget-host
  viewer, the flow UI, and the deployed static bundle). The Python server, planner, and resolver
  are **unchanged**: a tick is just an ordinary resolve POST for that source's
  query, the same path a `$param` change takes. Because of that it's **deduped by
  the cache** — a tick landing inside the source's `cache_max_age` window returns
  the stored entry with no recompute, so pair a short interval with a short cache
  age (or `0s`) if you actually want fresh data each tick.
- `verify` never ticks (it's one-shot), so a `refreshInterval` has no effect on a
  headless check — confirm live-refresh behavior on the real renderer.

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
- **Surface scope:** works where there is a local host (`widget open`, the
  parley, the flow UI). On the deployed-serve bundle / MCP-Apps sandbox there is
  no executor, so an `executor` press is a visible no-op (the button still
  renders). Pair `executor` with `action` on the same button to ALSO report a
  feedback event.
- v1 is fire-and-forget: the button does not yet auto-refresh dependent queries
  from the UDF's result. To reflect a write, have the UDF mutate state a read
  `{{ref}}` re-reads, and re-resolve (e.g. bump a `$param` the read depends on).


---

## Self-verify a widget resolves (headless)

Confirm a widget resolves to data with **`fused widget verify`** — the fast
headless check (no GUI in the loop). Run it *alongside* `open`, not as a serial
gate in front of it (see [Optimistic open + background verify](#optimistic-open--background-verify)):
it resolves the widget in **one shot**, prints the data envelope to
stdout, and exits — spawning and reaping nothing (no daemon, no port, no token,
no browser). It reuses the same resolution path as the render surfaces
in-process, so a clean `verify` faithfully predicts what `open` would render. It
is the headless counterpart of `open`/`push`/`watch` and **replaces** the old
hand-driven `fused dev serve` dance (spawn → read handshake → POST
`/api/exec/widget` → parse → kill).

```sh
# a .json config file, pinned to its project (the usual real-widget case)
fused widget verify scripts/<widget>/main.json \
  --project-dir ~/.openfused/workspaces/default/<project>

# a saved widgets/<stem>.json owned by a project
fused widget verify <stem> --project <project>

# inline / from stdin; bind $param values; force a fresh run (or pin a max age)
cat main.json | fused widget verify --config -
fused widget verify <stem> --project <project> --params '{"region":"emea"}' --cache-refresh
fused widget verify <stem> --project <project> --cache-max-age 0s
```

The response is `{"data": {queryId: {columns, rows}}, "errors": {…}, "depMap":
{…}, "config": {…}, "warnings": […]}`. **Success = `errors` is empty and `data`
has rows.** A
per-query failure (bad SQL, a UDF error, a missing `{{ref}}` source, a missing
`$param`) lands under `errors[queryId]` and never blanks the rest — read it to
fix the SQL or the referenced UDF; the command **still exits `0`** because
per-query failures are *in-band*. A source that returns `[]` (zero rows) is a
**success**, not an error: it's an empty result and the widget renders empty — a
clean empty widget, not an in-card error. Only a **hard** failure (bad input,
unknown/unresolvable widget, resolver crash) prints **no stdout JSON**, a message
on stderr, and exits **non-zero**. Resolution runs through the project's compute
backend, so the project venv needs `duckdb` + the py UDFs' deps (see above).
Full flags + the exit-code table: `fused-cli` (widget section).

The `warnings` array is a **best-effort advisory** — `[{"type","props":[…]}, …]`,
empty `[]` when clean — flagging config props the server's catalog doesn't
recognize (a typo'd or unsupported prop name). It is strictly additive and
**never changes the exit code** (a warning is not an error), and because it comes
from the shared resolve path the interactive surfaces (`open`/`push`/`watch`)
carry it too. See the caveat below for what it does and doesn't catch.

### Pick the right addressing mode

`verify` resolves `{{ref}}` sources in one of two modes, chosen by the flag you
pass. **Picking the wrong one is the most common failure here** — and it surfaces
as a misleading `unknown endpoint` error, not as "wrong mode", so know the rule
up front:

| Mode | How to select | What it can resolve | Use when |
|---|---|---|---|
| **Widget-dir** | a bare `.json`/`--config` with **no** `--project`/`--project-dir` (`?dir=`) | Only the `*.py` under the widget file's own `<dir>/udfs/`. **Cannot** see other UDFs in the project's `scripts/`, and **cannot** resolve `{{_core.*}}` or any `{{ref}}` whose UDF lives elsewhere. | The widget is self-contained — every `{{ref}}` resolves from its own `udfs/` folder. |
| **Project** | `--project-dir <abs project root>` (a `.json`/`--config`) or `--project <name>` (a stem) | The whole project: every `scripts/<name>/main.py`, the project `.venv`, and the injected built-in `_core` workspace (so `{{_core.task-management.read}}` etc. resolve). | The widget reads a UDF elsewhere in `scripts/`, a `{{_core.*}}` ref, or is a deployable `scripts/<name>/main.json` — i.e. almost any real project widget. **This is the default.** |

> **`unknown endpoint` ⇒ wrong mode (90% of the time).** If a `{{ref}}` resolves
> to `unknown endpoint`, you almost certainly ran a bare `.json` (widget-dir mode)
> against a UDF that folder can't see. Add `--project-dir <project root>` (or
> `--project <name>` for a stem) before suspecting the SQL or the UDF itself.
> Being *inside* the project tree is **not** enough — the mode is set by the flag,
> not by cwd. The reverse — a truly missing/misnamed `{{ref}}` — also reads
> `unknown endpoint`, so confirm the mode first, then the name.

> **⚠ What this proves — and what it does NOT.** A clean `verify` proves the
> widget's SQL **resolves to data**, and its `warnings` array now catches props
> the **server catalog** doesn't recognize (a typo'd or unsupported prop name).
> But it still does **not** prove the renderer will **honor** a prop it *does*
> recognize — `verify` returns raw rows and never renders. The gap it can't see is
> **version skew**: a prop the server catalog knows but a **stale/old `@fusedio/flow`
> bundle** doesn't (e.g. `idColumn`/`parentColumn` row-grouping added after that
> bundle) resolves clean, warns nothing, and still draws wrong. So when you add a
> **newer config prop**, don't trust the headless pass alone: confirm the prop is
> actually applied on the real renderer (the widget-host viewer via `fused widget
> open`, the flow UI, or the deployed widget URL) and check the renderer version supports it. The headless check is a
> data + catalog gate, not a render gate.

> **⚠ Build-freshness: verify sees source, `open` serves a compiled bundle.**
> `verify` resolves in-process against the source on disk, but `open` serves the
> **compiled `widget-host` bundle** (`widget-host/dist`). If that bundle is stale
> — older than its `src/` — `open` can render old/wrong behavior while `verify`
> stays green, and you'll burn a whole session debugging config that is already
> correct. So when `open` misbehaves but `verify` is clean, **suspect the running
> artifact before your config**: confirm the bundle is newer than its source (and
> actually contains the symbol you're testing), rebuild (`pnpm build` in
> `widget-host`), and re-open — *before* re-editing the widget. Attribute a render
> bug to source only once you've confirmed the artifact you're running is fresh.
> This is the general rule for any compiled surface: verify the thing you're
> actually running, not the thing you're reading.

---

## Getting a widget in front of a human — decision tree

> **CLI / standalone agent: open the widget yourself — do not tell the human to
> open it.** Once you have authored (and headlessly self-verified) the widget file,
> *you* run the surface command — `fused widget open <file>` for a one-shot, or
> push it into the parley for a standing loop. `widget open` launches/reuses the app
> server, opens the browser, and blocks until the human responds, handing you their
> reply. Never end your turn with "open the file in the flow UI to see it" — that
> strands the human; drive the surface and bring back the result.
>
> **⚠ Agents spawned by the flow app (architect / data-analyst / QA
> worker runs) MUST NOT run `fused widget open` / `widget push` / the parley.**
> Those surfaces wait on a human at a keyboard and would **hang the run** (or
> collide with the already-running UI). In that context the widget flow is
> different: a `data-analyst` just **writes `widgets/<stem>.json`** and the flow UI
> **live-renders it natively** — no command to run; feedback is
> asked via the teamwork MCP (`ask_user` — the single human-ask tool), and `data-qa` self-checks a
> widget headless via `POST /api/exec/widget`. The "run `widget open` yourself" rule
> is for an agent driving Fused from the CLI, not for an in-app worker.

All four surfaces render the **same config** through the **same resolver**. Pick
by the interaction you need:

| You want… | Use | Command | Response back to the agent |
|---|---|---|---|
| **One-shot** feedback ("show this, tell me when done") | `widget open` | `fused widget open scripts/sales-board/main.json` | Blocks until the human submits/closes (or `--timeout`, default 600s); prints the final `$param` state as one JSON line to stdout |
| **A standing / long-running widget** (push successive views, stream human events) | **parley** | `widget push <cfg>` + `widget watch` (or `widget agent`) | NDJSON event stream (`action`/`close`); the view persists on `/parley`, push a new one and keep watching. See [Long-running / standing widgets](#long-running--standing-widgets). |
| **A comment-driven revise loop** (human pins comments on the widget; an agent edits the file) | **parley + `widget agent`** | `widget push <file.json>` (or `--project-dir <root>`) in one terminal, `widget agent` in another | The human comments on the file-backed parley page (no flow app); `widget agent` turns each comment into a file edit + re-push. See `fused-feedback` → *CLI-native comment feedback*. |
| **The flow UI** (browse **saved dashboards**) — *separate tool, out of scope* | flow | `flow` (or `npx @fusedio/flow` once published) | Human-driven. **Only `widgets/<stem>.json` live-renders** — a `json` UDF shows as source. |
| **A shareable URL** (stakeholder, no local server) | deploy | `fused udf deploy sales-board --project <p>` | A rendered widget URL (preview → promote to release) |

- **Finding the target (don't `ls` the workspace).** When the human just names a
  widget and/or project ("open the `session_cost` widget of `cc-open`"), resolve
  it with the CLI, not by listing directories:
  - `fused project list` → JSON array of every project (`name`, `path`, `exists`).
    Skip it when the human already named the project.
  - `fused project show <project>` → includes a `"widgets": [...]` array of the
    project's saved-widget **stems** (the `widgets/<stem>.json` you'd pass to
    `open`), plus its references and components. One call confirms the project
    **and** lists its widgets — replacing a `ls ~/.openfused/workspaces/…` + `ls
    widgets/` walk with one structured command. When the human named both the
    project and an obvious widget, skip discovery entirely and go straight to
    `fused widget open <stem> --project <project>`.
- `widget open <target>`: `<target>` is a `.json` path or a saved-widget stem.
  It launches/reuses the app server, opens the browser, and blocks. `--no-open`
  still blocks (prints the URL). This is the canonical "ask the human" path for
  an agent. The block is **time-bounded**: `--timeout` seconds (**default 600 =
  10 min**), after which it prints `{"action":"timeout"}` and exits **3**;
  `--timeout 0` waits forever (see [Long-running / standing widgets](#long-running--standing-widgets)).
  - **`-c/--config TEXT` (or `--config -` for stdin):** pass the widget config
    **inline** instead of a `<target>` — one call instead of `Write` a `.json`
    then `open` it. Mutually exclusive with `<target>`. Best for **one-shot**
    asks (approvals, questions) that settle and exit; the config is **not
    editable** (no durable file), so for an edit-and-refresh loop keep authoring a
    named `.json` and `open` its path. `widget push -c/--config` is the parley
    counterpart (no temp file; `--source PATH` sets the edit anchor).
  - **`--project-dir PATH`** (`.json`/`--config` targets only; on both `widget
    open` **and** `widget push`): pins `fused dev serve`'s `?projectDir=` mode to a
    project directory so UDFs in `scripts/` and the project `.venv` are available.
    **Pass this for almost any real project widget** — one that references a UDF
    elsewhere in `scripts/` or a `{{_core.*}}` ref. Omitting it leaves the surface in
    widget-dir (`?dir=`) mode, which sees **only** the `.py` files sitting next to the
    widget file; a `{{ref}}` to anything else then fails (often a misleading `unknown
    endpoint`/ValueError). Being *inside* the project tree is **not** enough — the mode
    is set by this flag, not by file location
    (see [Pick the right addressing mode](#pick-the-right-addressing-mode)).
    Mutually exclusive with `--project`. **On `push`, it is the entry point to
    feedback mode:** a `.json` path pushed `--project-dir` resolves against the
    project *and* stays file-backed, so the parley comment loop works on a
    `scripts/`-backed widget — the only push form that is both project-addressed and
    editable (a `{project, stem}` push resolves but is not editable). See
    `fused-feedback` → *CLI-native comment feedback*.
- **parley** (`widget push`/`watch`/`parley`/`agent`) is the standing
  agent↔human channel — successive views land on one persistent page and the
  human's events stream back as NDJSON. Use it for iterative refinement. Details
  + flags: `fused-cli` (widget section).
- **The flow UI** (separate tool, out of scope) renders **saved dashboards**
  (`widgets/<stem>.json`) natively, with data resolved through `fused dev serve`. A
  `json` UDF (`scripts/<name>/main.json`) is **not** live-rendered there — it
  appears as source/spec; preview a `json` UDF with `widget open` (above) or deploy it.
- **Deployed** `json` UDFs build a self-contained `widget.html` bundle + a gated
  resolver data route → a stable widget URL. This is the one place a renderer
  bundle (not the app) serves the widget.

### Long-running / standing widgets

**Yes — a widget can stay up long-term, but `widget open` is the wrong tool for
it.** An `open` *session* lives only **as long as its command runs**: the block
gives up after `--timeout` seconds (**default 600 = 10 min** → `{"action":"timeout"}`,
exit 3), and on *any* exit (timeout, Ctrl-C, the tab closing) it **de-registers
the widget** — so you cannot "open it and walk away." Pick by what "long-running"
means:

- **One long-lived ask that just needs more patience — `widget open --timeout 0`**
  (wait forever). The block never expires; it returns only when the human acts (or
  you interrupt). Because it then blocks *indefinitely*, you MUST drive it from
  `run_in_background` and Monitor its **stderr** for the `widget page:` URL — never
  a foreground `--timeout 0` you can't get back from (same rule as
  [Optimistic open + background verify](#optimistic-open--background-verify)).
- **A widget that genuinely persists across a long session — the parley** (the
  real long-running surface). Unlike an `open` session, a pushed parley view
  **persists in the widget-host independently of the short-lived `push` command**:
  `widget push <cfg>` posts a view and **exits immediately**, the view stays on the
  standing `/parley` page, and `widget watch` (its `--timeout` defaults to **0 =
  watch forever**) streams the human's events as NDJSON. Push successive views onto
  the same page over time; run `watch` in the background for the life of the
  collaboration. This is the surface to reach for when the widget must outlive a
  single blocking call.

Either way, the **widget-host itself is a detached background process that
outlives the CLI call** — it binds a fixed loopback port (default 4410) and a
later `widget` command *reuses* it — so the host (and any parley view on it) keeps
serving between commands. What's transient is the per-`open` **session**, not the
host.

### Optimistic open + background verify

`widget open` **blocks until the human responds**, so you cannot both open a
widget and do anything else from the same foreground call. Two rules follow — and
together they kill the blind-`sleep` anti-pattern.

**Open optimistically; verify in the background — don't gate the human's view on
the headless check.** `verify` is a data + catalog gate, not a render gate, and
it's fast. Launch `open` first so the human sees the widget the moment the server
is up, and run `verify` *concurrently* to catch resolve/catalog problems — then
react (push a fix, flag an empty result) if it comes back dirty. Serialising
verify → open only adds latency to the human's first paint for a check that
rarely fails once the SQL is written.

**Poll for readiness — never blind-`sleep`.** Because `open` blocks, start it
with `run_in_background` and watch its output for the `http://…` URL instead of
guessing with `sleep 8; cat log`. A fixed sleep is both too slow (you pay the
worst case every time) and too fragile (a cold server misses the window). Use a
`Monitor` until-loop that greps the background log for `http://` and returns the
instant the URL appears, with a timeout ceiling (~30s). Foreground `sleep` is
blocked by the harness precisely to push you onto this pattern.

```sh
# start open in the background (it blocks for the human); --no-open still prints the URL
fused widget open scripts/<name>/main.json --project-dir <project-root> --no-open 2>open.err &
# → the URL lands on STDERR as a `widget page: <url>` line (stdout is reserved for the
#   final terminal-event JSON), so Monitor stderr for `widget page:` (don't sleep-then-cat),
#   and in parallel run `fused widget verify` to gate the data.

# CAPTURE THE URL AND OPEN THE BROWSER IN ONE STEP — don't split "cat the log" and
# "open the browser" into two separate tool calls (two model round-trips). Fold them:
url=$(timeout 30 sh -c 'until u=$(sed -n "s/^widget page: //p" open.err); [ -n "$u" ]; do sleep 0.2; done; echo "$u"')
cmux open "$url" || open "$url"      # --no-open opens NOTHING; you must open it yourself
```

> **`--no-open` + open-it-yourself is only needed in a remote/cmux env** (where the
> CLI's built-in browser launch can't reach the human's browser). **Locally, drop
> `--no-open`** and `fused widget open` opens the browser itself — no URL capture,
> no separate open step. Either way, capturing the URL and opening the browser is
> **one** action: never spend a round-trip on a standalone `cat`/`Read` of the log
> just to read the URL, then another to open it.

> Interim vs. end state: this poll is the mitigation until `open` emits the URL
> as an immediate machine-readable readiness line (`{"url":"…"}`) — at which
> point waiting collapses to a single read. Until then, poll; never blind-sleep.

---

## Authoring checklist for an agent

1. Decide the split: which `py` UDF(s) compute the data, and the `json` widget
   that visualizes them via `{{ref}}`.
2. Write each UDF's `spec.md`, get spec approval, then write the entrypoint
   yourself: `scripts/<name>/main.py` for a `py` UDF. For the **widget**, pick the
   home by goal (see "What a widget is"): **`widgets/<stem>.json`** if the human
   will browse it (the form the flow UI live-renders), or
   **`scripts/<name>/main.json`** if it's a deployable entrypoint
   (preview via `widget open`). **A `widgets/<stem>.json`
   gets its own `widgets/<stem>.spec.md` sidecar too** (purpose + the data/components
   it binds) — the same spec↔file pairing UDFs have; the flow UI shows it in the widget's
   Preview ⇄ Spec toggle. Validate py code with `fused code verify <file>` (or
   MCP `verify_code`) before committing. There is no `udf generate` command — the
   agent authors the file. See `fused-projects` for the full spec-first flow.
3. Local backend: `uv add` the deps the py UDFs (and DuckDB) need, then
   `uv sync`.
4. Preview — **run the surface command yourself; never hand the human a path to
   open.** A **saved dashboard** (`widgets/<stem>.json`): if the human is already in
   the flow UI it live-renders, otherwise *you* run `fused
   widget open widgets/<stem>.json`. A **`json` UDF** (`scripts/<name>/main.json`):
   *you* run `fused widget open scripts/<name>/main.json` (one-shot) or push it
   into the parley — the flow UI shows it as **source**,
   not a render. `widget open` blocks until the human responds and returns their
   reply to you. **Open optimistically and run `fused widget verify` in the
   background rather than gating the open on it, and poll for the URL instead of a
   blind `sleep`** — see [Optimistic open + background verify](#optimistic-open--background-verify).
   (This is the **CLI / standalone** path. An **in-app worker** never runs `widget
   open` — it writes the `.json` and the flow UI live-renders it; see the ⚠ note under
   the decision tree.)
5. Iterate by editing `spec.md` then updating the entrypoint to match (both under
   `scripts/<name>/`); commit both together (the pre-commit hook enforces
   spec+entrypoint pairing); re-open to re-preview.
6. Deploy the `json` UDF to a widget URL when ready (`udf deploy` → promote).

---

## See also

- `fused-projects` — the end-to-end lifecycle (env → project → UDF gen →
  run → widget → deploy), and the spec-first generation loop.
  Includes the `_core` built-in workspace note.
- `fused-cli` — full `widget` command flags (`open`/`push`/`watch`/`parley`/
  `verify`) and the widget-host; also documents `fused dev serve` which can
  address the built-in `_core` workspace (`workspace="_core"`) with no user setup.

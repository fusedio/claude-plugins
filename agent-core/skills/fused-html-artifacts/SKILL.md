---
name: fused-html-artifacts
description: Authoring standalone HTML artifacts — `scripts/<name>/main.html` documents that Fused and Flow serve full-bleed and wire to a `window.fused` runtime (callUdf / runSql / params). Use when the output of a project is a bespoke interactive HTML page — a custom chart, a form, a report, a small app — that calls UDFs and runs SQL directly, rather than a JSON-UI widget. Covers the `window.fused` API, the `{{ref}}`/`$param` data grammar, load-order gotchas, host differences, and how the artifact gets rendered in front of a human.
---

# HTML artifacts — authoring a `main.html` that talks to Fused

An **HTML artifact** is an agent-authored, standalone HTML document —
`scripts/<name>/main.html` — that the host (Fused's `widget-host`, or the Flow app)
serves full-bleed in an iframe and wires to a `window.fused` runtime. You write one
self-contained page; the host injects `window.fused`, and your page calls UDFs, runs
SQL, and reads/writes params through it. It is backed by the **same UDFs and SQL** the
rest of the project uses.

It is the **third shape** a `scripts/<name>/` folder can take, alongside a Python UDF
(`main.py`) and a JSON UDF (`main.json`): where those are **functions the host runs**,
an HTML artifact is a **document the host serves and frames** — a small, self-contained
app you author once and the human interacts with directly.

## When to author one (vs a JSON-UI widget)

Reach for an HTML artifact when the JSON-UI widget catalog (`fused-widgets`) can't
express the interface — a bespoke layout, a custom visualization, a multi-step form, a
mini-app with its own interaction logic. Reach for a **JSON-UI widget** (the default)
when a dashboard of standard charts / tables / inputs is enough: it's less code, renders
on more surfaces (including deployed URLs), and is self-verifiable headlessly.

> **HTML artifacts are completely independent from JSON-UI widgets.** Different folder
> (`scripts/<name>/main.html`, not `widgets/<stem>.json`), different runtime
> (`window.fused`, not the widget renderer). Don't carry a widget assumption over, and
> vice versa. Say **HTML artifact**, never **widget**, for this surface.

## What you author: one self-contained document

Author a **single `scripts/<name>/main.html`**. That's the whole deliverable.

- **Do NOT wire the runtime yourself.** The host injects `window.fused` into the page
  before your code runs — you never add a `<script>` tag for it, never import a bridge,
  never configure a URL or token. Just call `window.fused.*`.
- **Prefer self-contained.** Inline your CSS and JS (or an inlined framework build). The
  page is framed and may be sandboxed on some surfaces, so external CDN scripts, fonts,
  and remote fetches are not guaranteed to load. Everything the page needs to render
  should be in the file. All data comes through `window.fused`, not `fetch`.
- **Write plain HTML/CSS/JS** (or any framework you inline). There is no required
  structure beyond a normal HTML document.

An optional sibling **`scripts/<name>/spec.md`** is docs-only (purpose, the UDFs/SQL it
binds) — same spec↔file pairing a UDF has. It carries no runtime role; the Flow app
shows it in the artifact's **Main ⇄ Spec** toggle.

## The `window.fused` API

`window.fused` is the only thing your page needs. The **portable core** below works
**identically on both hosts** (Fused `widget open` and the Flow app). Every method is
**async-safe and never throws** — failures come back in the result, not as an exception.

| Method | Returns | What it does |
|---|---|---|
| `callUdf(name, overrides?, opts?)` | `Promise<{ data, error? }>` | Run a named UDF once and get its decoded output. |
| `runSql(sql, params?, opts?)` | `Promise<{ rows, columns, error? }>` | Run ad-hoc SQL host-side over the project's UDFs. |
| `getParam(name)` | `unknown` | Read the current value of a param. |
| `setParam(name, value)` | `void` | Set a param (notifies every subscriber). |
| `clearParam(name)` | `void` | Clear a param (notifies subscribers). |
| `onParam(name, cb)` | `() => void` | Subscribe to one param; `cb(value)` on every change. Returns an unsubscribe fn. |
| `fused.ready` | `Promise<void>` | Resolves once param state is available — **`await` it before reading params on load** (see below). |

```html
<script>
  async function main() {
    await window.fused.ready;                       // params are ready

    // Run a UDF, render its output
    const { data, error } = await window.fused.callUdf("sales", { region: "emea" });
    if (error) { showError(error); return; }
    renderChart(data);

    // Run ad-hoc SQL over the same UDFs (see the data grammar below)
    const res = await window.fused.runSql(
      "select month, sum(revenue) as revenue from {{sales?region=$region}} group by month order by month",
      { region: "emea" },
    );
    if (res.error) { showError(res.error); return; }
    renderTable(res.columns, res.rows);
  }
  main();
</script>
```

### `callUdf(name, overrides?, opts?)`

- **`name`** is the UDF's **project slug** (kebab-case, e.g. `"sales"`, `"my-udf"`) — the
  same name a `{{ref}}` reads it under.
- **`overrides`** become the UDF's keyword args. **Values are coerced to strings**
  (query params always travel as strings): a string passes through, numbers/booleans are
  stringified, objects/arrays are JSON-serialized, `null`/`undefined` become `""`. If the
  UDF needs structured input, JSON-encode it and decode inside the UDF.
- **`opts.format`** selects the decode: `"json"` (default parsed value), `"html"`, or
  `"text"`. **`opts.signal`** is an `AbortSignal` to cancel the call.
- Returns `{ data, error? }` — `data` is `null` when `error` is set. **Always check
  `error`.**

### `runSql(sql, params?, opts?)`

- **`sql`** is DuckDB SQL using the **same `{{ref}}` / `$param` grammar** JSON-UI widgets
  use — see `fused-widgets` for the full grammar. In short:
  - `{{sales}}` — the whole result of the `sales` UDF; `{{sales?region=$region}}` — pass
    a kwarg bound to the `$region` param; `{{sales?region=emea&limit=50}}` — bare
    literals.
  - `$name` is an **inline text substitution** for the value in `params` — works anywhere,
    including inside strings.
  - Cross-project `{{_core.<project>.<udf>}}` refs resolve the same way they do for
    widgets (task-management, run-management, …).
- **`params`** supplies the `$param` values the statement references. **`opts.signal`**
  cancels.
- Returns `{ rows, columns, error? }` — flat rows/columns. **Check `error`.**

### Params: reactive state that outlives a reload

`getParam` / `setParam` / `clearParam` / `onParam` are a small reactive store the **host
owns**, not your page — so param state **survives a document reload**. Use params to hold
selection/filter state and to drive re-rendering:

```html
<script>
  window.fused.onParam("region", (region) => refresh(region));   // re-render on change
  document.querySelector("#emea").onclick = () => window.fused.setParam("region", "emea");
</script>
```

Because the store is host-owned, `getParam` before the first snapshot returns nothing —
**`await window.fused.ready`** before reading params on load. (On the Fused host `ready`
resolves immediately; on Flow it resolves on the first param snapshot. Awaiting it is
safe and portable on both.)

On the **Fused** host, param changes also drive automatic URL query-sync and
parley/session reporting — you get that for free by using `setParam`, no extra code.

### Events (`emit` / `on`) — Flow-only, experimental

`window.fused.emit(name, payload?)` / `window.fused.on(name, cb)` are a fire-and-forget,
two-way event channel with the host. **Available on Flow only; on the Fused host they are
absent.** Even on Flow, nothing consumes them yet in v0. **Do not build critical behavior
on events** — treat them as an experimental hook. For anything load-bearing, use params
or UDF/SQL calls. If you do use them, feature-detect: `window.fused.emit?.(…)`.

## Load-order & robustness rules

- **`await window.fused.ready` first**, before reading any param, on every entry path.
- **Guard `window.fused` may be undefined.** It only exists when the document is rendered
  by a host (framed). Opened as a bare file it won't appear — the host logs to the console
  and your `fused.*` call fails at the call site. Don't crash the whole page on load;
  degrade gracefully (`if (!window.fused) { … }`).
- **Never assume a call succeeded** — branch on `.error` for `callUdf`/`runSql`, render a
  visible error state.
- **All data flows through `window.fused`.** The page makes no direct network calls of its
  own; there is no API base URL or token for you to hold.

## How the artifact gets rendered in front of a human

Same document, two hosts — you author once:

- **Fused CLI** — `fused widget open scripts/<name>/main.html` serves the document,
  injects `window.fused`, opens the browser, and blocks until the human is done. The
  document is served fresh on every load, so your next edit is live on reload.
- **Flow app** — the artifact appears in the project **Explorer** as an `html` leaf and
  renders as a full-bleed **product surface** (with a **Main ⇄ Spec** toggle). Live on
  save; no command to run.

## Host differences (author-relevant)

| | Fused (`widget open`) | Flow app |
|---|---|---|
| Portable core (`callUdf`/`runSql`/params/`ready`) | ✅ | ✅ |
| `emit` / `on` events | ✗ (absent) | ⚠ present, experimental, unconsumed |
| `fused.ready` timing | resolves immediately | resolves on first param snapshot |
| URL query-sync + parley reporting from params | ✅ automatic | ✗ (v0) |
| Render surface | browser via `widget open` | in-app product surface (Explorer leaf) |

**Author to the portable core** (`callUdf`/`runSql`/`getParam`/`setParam`/`clearParam`/
`onParam` + `await fused.ready`) and the artifact runs unchanged on both.

## Authoring checklist

1. Decide the split: which UDF(s) compute the data (`scripts/<name>/main.py` or
   `main.json`), and the HTML artifact that presents them. Confirm a JSON-UI widget
   (`fused-widgets`) genuinely can't do the job before choosing HTML.
2. Write the backing UDF(s) and their `spec.md`; verify they run (see `fused-execute` /
   `fused-verify`).
3. Author a **single self-contained `scripts/<name>/main.html`**: inline CSS/JS, no
   external CDNs, no bridge wiring. Optionally add `scripts/<name>/spec.md`.
4. Use only `window.fused.*`; `await window.fused.ready` before reading params; check
   `.error` on every `callUdf`/`runSql`; guard `window.fused` being absent.
5. Stick to the portable core so it runs on both hosts; feature-detect `emit`/`on` if used.
6. Render it: `fused widget open scripts/<name>/main.html` (Fused CLI) or open it in the
   Flow app Explorer. Iterate — edits are live on reload/save.

## See also

- `fused-widgets` — the JSON-UI widget alternative, and the authoritative **`{{ref}}` /
  `$param` data grammar** `runSql` shares.
- `fused-projects` — the `scripts/` folder-per-entrypoint layout and project lifecycle.
- `fused-execute` / `fused-verify` — writing and validating the UDFs the artifact calls.
- `fused-cli` — the `fused widget open` command surface.

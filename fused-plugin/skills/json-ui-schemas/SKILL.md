---
name: json-ui-schemas
description: JSON schemas for Fused canvas UI widget components (text, text-input, button, dropdown, charts, maps, sql-table, form, transformer, etc.). Use when authoring or editing widget JSON files (e.g. `widget_*.json` in canvas directories), validating widget props, or answering questions about which fields a given widget type accepts.
---

# Fused JSON UI widget schemas

Reference for every supported widget `type` and its prop schema.

The full JSON Schema for each component (with descriptions, defaults, required fields, and enum values) is available from the fused CLI. See the `fused-cli` skill for how to read it. Read it before authoring or modifying widget JSON.

The authoritative reference to JSON schema is available from the CLI. There is also a reference in `reference.md`, but it is an offline copy that may be out of date.

JSON UI files are in JSON5 format, which may have trailing commas, comments, etc.

## Available widget types

- **Layout / containers:** `div`, `form`, `sql-runner` (children: yes)
- **Inputs:** `text-input`, `text-area`, `number-input`, `datetime-input`, `camera-input`, `color-input`, `dropdown`, `slider`, `button`, `code-editor`, `gallery-input`
- **Display:** `text`, `image`, `metric`, `iframe`, `html`
- **Charts:** `bar-chart`, `line-chart`, `stacked-bar-chart`, `stacked-area-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Tables:** `sql-table`
- **Maps:** `map`, `map-bounds`, `map-h3`, `fused-map`
- **Meta / advanced:** `widget-builder`, `transformer`, `ai-chat`

## Common conventions

- `param` syncs a widget's value with a canvas parameter (or a form field when nested in `form`).
- `sql` fields accept DuckDB queries with `{{udf_name}}` and `$param_name` placeholders. Required output columns vary by widget — check the schema.
- `style` is always a CSS string (`"padding: 8px; color: red"`), not an object.
- Charts default `barColor`/`lineColor` to Fused lime yellow (`#E8FF59`).

## Widget control values are strings; node-to-node edges pass typed values

Values set through UI widget controls — `dropdown`, `slider`, `number-input`, etc. — are passed to the UDF as **strings**, even when the UDF parameter is typed as `bool` or `int`.

However, when a UDF parameter receives its value from **another UDF node** via a canvas edge, it gets the actual typed Python value (a real `bool`, `int`, etc.). Because the same parameter can be driven by either source, always guard with `isinstance` before coercing:

```python
@fused.udf
def udf(dry_run: bool = False, limit: int = 100):
    # widget dropdown passes "true"/"false"; node-to-node edge passes True/False directly
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() in ("true", "1", "yes")
    # widget number-input passes "100"; node-to-node edge passes 100 directly
    if isinstance(limit, str):
        limit = int(limit)
```

The `isinstance` guard is essential for `bool` coercion — calling `.lower()` on a real `bool` raises `AttributeError`.

## How to use this skill

1. Open `reference.md` and find the section for the widget `type` you're working with.
2. Honor `required` props and respect `enum` constraints.
3. When constructing a widget JSON, prefer SQL-driven options/data over static when a UDF is available.
4. Validate with `fused json-ui validate <file>` — unknown keys and missing required props will be flagged.

## Debugging widgets with the Fused CLI

The `fused json-ui` subcommands are the fastest way to check your work without round-tripping through the canvas UI. See the `fused:fused-cli` skill for full flag details; the common debugging flow is:

- **Verify the schema you're targeting** — `fused json-ui schemas <type>` prints the live JSON Schema for one or more component types (or all of them if omitted). Use this when `reference.md` and the CLI disagree; the CLI is authoritative.
- **Validate a widget JSON before pushing** — `fused json-ui validate path/to/widget_foo.json` (or a path to a `.json5` file, or an inline JSON5 string). Run this after every non-trivial edit; it catches missing required props, unknown keys, and bad enum values without needing a canvas push.
- **See a widget rendered without opening a browser tab** — once the canvas is shared (`fused canvas share <ref>`), use `fused json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` to render the widget headlessly and save a PNG. Add `--wait N` if the widget loads data asynchronously. `run-inline-widget` does the same for an inline JSON5 config string, which is useful for iterating on a widget that isn't committed yet.
- **Refresh the catalog** — `fused json-ui catalog-prompt` prints the high-level component catalog; handy when a new widget type appears in the CLI before it lands in `reference.md`.

Recommended loop when authoring a new widget JSON: write → `fused json-ui validate <file>` → fix → push → confirm it renders.

**Always verify the widget renders correctly** before reporting the task complete. Use one of these methods:

- **CLI (preferred for quick iteration):** `fused json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` — renders headlessly and saves a PNG. Review the PNG to confirm layout, labels, and data look correct.
- **Browser:** open the canvas URL and interact with the widget directly. This is required when testing interactivity (dropdowns, form submission, map panning, etc.) that a screenshot cannot capture.

Do not claim success after `validate` alone — validation only checks schema conformance, not runtime behavior or visual correctness.

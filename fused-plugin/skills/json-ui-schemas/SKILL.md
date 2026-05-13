---
name: json-ui-schemas
description: JSON schemas for Fused canvas UI widget components (text, input, button, dropdown, charts, maps, sql-table, form, transformer, etc.). Use when authoring or editing widget JSON files (e.g. `widget_*.json` in canvas directories), validating widget props, or answering questions about which fields a given widget type accepts.
---

# Fused JSON UI widget schemas

Reference for every supported widget `type` and its prop schema.

The full JSON Schema for each component (with descriptions, defaults, required fields, and enum values) lives in `reference.md` next to this file. Read it before authoring or modifying widget JSON.

## Available widget types

- **Layout / containers:** `div`, `form`, `sql-runner` (children: yes)
- **Inputs:** `input`, `dropdown`, `slider`, `button`, `code-editor`
- **Display:** `text`, `image`, `big-number`, `iframe`
- **Charts:** `bar-chart`, `line-chart`, `stacked-bar-chart`, `stacked-area-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Tables:** `sql-table`
- **Maps:** `map`, `map-bounds`, `map-h3`, `fused-map`
- **Meta / advanced:** `widget-builder`, `transformer`, `ai-chat`

## Common conventions

- `param` syncs a widget's value with a canvas parameter (or a form field when nested in `form`).
- `sql` fields accept DuckDB queries with `{{udf_name}}` and `$param_name` placeholders. Required output columns vary by widget — check the schema.
- `style` is always a CSS string (`"padding: 8px; color: red"`), not an object.
- Charts default `barColor`/`lineColor` to Fused lime yellow (`#E8FF59`).

## How to use this skill

1. Open `reference.md` and find the section for the widget `type` you're working with.
2. Honor `required` props and respect `enum` constraints.
3. When constructing a widget JSON, prefer SQL-driven options/data over static when a UDF is available.
4. Validate output against the schema's `additionalProperties: false` — unknown keys will be rejected.

## Debugging widgets with the Fused CLI

The `fused json-ui` subcommands are the fastest way to check your work without round-tripping through the canvas UI. See the `fused:fused-cli` skill for full flag details; the common debugging flow is:

- **Verify the schema you're targeting** — `fused json-ui schemas <type>` prints the live JSON Schema for one or more component types (or all of them if omitted). Use this when `reference.md` and the CLI disagree; the CLI is authoritative.
- **Validate a widget JSON before pushing** — `fused json-ui validate path/to/widget_foo.json` (or a path to a `.json5` file, or an inline JSON5 string). Run this after every non-trivial edit; it catches missing required props, unknown keys, and bad enum values without needing a canvas push.
- **See a widget rendered without opening a browser tab** — once the canvas is shared (`fused canvas share <ref>`), use `fused json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` to render the widget headlessly and save a PNG. Add `--wait N` if the widget loads data asynchronously. `run-inline-widget` does the same for an inline JSON5 config string, which is useful for iterating on a widget that isn't committed yet.
- **Refresh the catalog** — `fused json-ui catalog-prompt` prints the high-level component catalog; handy when a new widget type appears in the CLI before it lands in `reference.md`.

Recommended loop when authoring a new widget JSON: write → `fused json-ui validate <file>` → fix → push → `fused json-ui run-shared-widget` to confirm it renders.

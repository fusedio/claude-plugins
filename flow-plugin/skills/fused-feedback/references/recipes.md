# Recipes — copy-paste feedback widgets

Each recipe is a complete JSON-UI config. Open it from a file:

```bash
fused widget open /abs/path/<recipe>.json --port 4477 --timeout 600
```

…or, for a one-shot ask, skip the file and pipe it inline on stdin (`--config -`):

```bash
printf '%s' "$RECIPE_JSON" | fused widget open --config - --port 4477 --timeout 600
```

stdout is one JSON line: `{"action":"<button-action>","params":{…}}`. Branch on
`action`; read inputs from `params`. (`"closed"`/`"timeout"` = no answer.)

---

## 1. Approval (Approve / Reject) with an optional comment

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:640px" },
  "children": [
    { "type": "text", "props": { "value": "Deploy build #1423 to production?", "variant": "h3" } },
    { "type": "text", "props": { "value": "Promotes the current preview to the release channel.", "variant": "muted" } },
    { "type": "text-area", "props": { "param": "comment", "label": "Notes (optional)", "placeholder": "Anything to flag…", "rows": 3 } },
    { "type": "div", "props": { "style": "display:flex; gap:12px" }, "children": [
      { "type": "button", "props": { "label": "Approve", "action": "approve", "submit": true, "variant": "primary" } },
      { "type": "button", "props": { "label": "Reject",  "action": "reject",  "submit": true, "variant": "secondary" } }
    ]}
  ]
}
```

→ `{"action":"approve","params":{"comment":"ship it"}}` · `{"action":"reject",…}` · `{"action":"closed",…}`

---

## 2. Single-choice question

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:560px" },
  "children": [
    { "type": "text", "props": { "value": "Which database should we target?", "variant": "h3" } },
    { "type": "dropdown", "props": {
        "param": "db", "label": "Target",
        "options": [
          { "value": "postgres",  "label": "PostgreSQL" },
          { "value": "duckdb",    "label": "DuckDB" },
          { "value": "snowflake", "label": "Snowflake" }
        ],
        "defaultValue": "postgres" } },
    { "type": "button", "props": { "label": "Confirm", "action": "submit", "submit": true, "variant": "primary" } }
  ]
}
```

→ `{"action":"submit","params":{"db":"duckdb"}}`

---

## 3. Multi-select question (returns an array)

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:560px" },
  "children": [
    { "type": "text", "props": { "value": "Which steps should I run?", "variant": "h3" } },
    { "type": "checkbox-group", "props": {
        "param": "steps", "label": "Steps",
        "options": [
          { "value": "lint",   "label": "Lint" },
          { "value": "test",   "label": "Tests" },
          { "value": "build",  "label": "Build" },
          { "value": "deploy", "label": "Deploy" }
        ],
        "defaultSelected": ["lint", "test"] } },
    { "type": "button", "props": { "label": "Run selected", "action": "run", "submit": true, "variant": "primary" } }
  ]
}
```

→ `{"action":"run","params":{"steps":["lint","test","deploy"]}}`  *(note the array)*

---

## 4. Free-text question

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:600px" },
  "children": [
    { "type": "text", "props": { "value": "What should I name the new service?", "variant": "h3" } },
    { "type": "text-input", "props": { "param": "name", "label": "Service name", "placeholder": "e.g. billing-api" } },
    { "type": "button", "props": { "label": "Use this name", "action": "submit", "submit": true, "variant": "primary" } }
  ]
}
```

→ `{"action":"submit","params":{"name":"billing-api"}}`

---

## 5. Plan review — show the plan, collect a verdict + edits

A single page that lays out the proposed plan and gathers everything in one
submit: a tunable, a set of guards, free-text changes, and Approve / Request-changes.

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:24px; max-width:760px" },
  "children": [
    { "type": "text", "props": { "value": "Review the migration plan", "variant": "h2" } },
    { "type": "text", "props": { "value": "**Goal.** Add the new column safely.\n\n1. Snapshot the table\n2. Add the new column (nullable)\n3. Backfill in batches\n4. Swap reads to the new column" } },
    { "type": "diff", "props": { "before": "purpose: read orders\noutput: rows", "after": "purpose: read orders\noutput: rows + new_column", "newLabel": "scripts/clean/spec.md" } },
    { "type": "dropdown", "props": {
        "param": "batch_size", "label": "Backfill batch size",
        "options": [ { "value": "1000" }, { "value": "10000" }, { "value": "50000" } ],
        "defaultValue": "10000" } },
    { "type": "checkbox-group", "props": {
        "param": "guards", "label": "Safety guards",
        "options": [
          { "value": "dry_run",     "label": "Dry run first" },
          { "value": "backup",      "label": "Take a backup" },
          { "value": "maintenance", "label": "Maintenance window" }
        ],
        "defaultSelected": ["dry_run", "backup"] } },
    { "type": "text-area", "props": { "param": "notes", "label": "Changes you want", "placeholder": "e.g. skip step 3 on staging", "rows": 4 } },
    { "type": "div", "props": { "style": "display:flex; gap:12px" }, "children": [
      { "type": "button", "props": { "label": "Approve plan",     "action": "approve", "submit": true, "variant": "primary" } },
      { "type": "button", "props": { "label": "Request changes",  "action": "changes", "submit": true, "variant": "secondary" } }
    ]}
  ]
}
```

→ `{"action":"approve","params":{"batch_size":"10000","guards":["dry_run","backup"],"notes":""}}`
→ or `{"action":"changes","params":{…,"notes":"do staging only"}}` — re-plan from `notes`.

> **For a spec review, author the whole surface in the widget.** Put the plan body
> in `text` (markdown) and one **`diff`** node per changed spec file
> (`{ "type": "diff", "props": { "before": "<old spec>", "after": "<new spec>",
> "newLabel": "<stem>.spec.md" } }` — you inline the old + new text; `diff` is not
> data-bound). There is **no** separate `details`/`paths` argument — the widget IS
> the whole review surface.

---

## 6. Tunable numeric input

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:520px" },
  "children": [
    { "type": "text", "props": { "value": "How many parallel workers?", "variant": "h3" } },
    { "type": "slider", "props": { "param": "workers", "label": "Workers", "min": 1, "max": 32, "step": 1, "defaultValue": 8 } },
    { "type": "button", "props": { "label": "Set", "action": "submit", "submit": true, "variant": "primary" } }
  ]
}
```

→ `{"action":"submit","params":{"workers":12}}`

---

## Notes that keep these correct

- Each input's **`param`** becomes a key in `params`. Choose stable, meaningful
  names — that's your answer schema.
- **`checkbox-group` → array**; every other input → scalar.
- Only **`submit: true`** buttons return control to you. Distinct `action` names
  let you tell Approve from Reject.
- `"closed"` / `"timeout"` / `"interrupted"` mean **no decision** — never treat a
  closed tab as approval.

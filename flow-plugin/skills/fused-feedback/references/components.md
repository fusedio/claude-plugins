# Component reference (feedback widgets)

Every node is `{ "type": <name>, "props": { … }, "children"?: [ … ] }`. **Every**
prop goes under `props`. An unknown `type` is a hard error. Inputs carry a
`param` (the answer key in the returned `params`) and seed it from `defaultValue`.

These are the components you need for questions / approvals / plan reviews — the
**static** set (no environment required). The full catalog (charts, tables, maps —
all data-bound) is in the `fused-widgets` skill.

`style` is universal: an inline CSS declaration string merged over the
component's defaults (e.g. `"display:grid; gap:16px; padding:20px"`).

---

## Containers

### `div` — layout box (has `children`)
| prop | type | notes |
|---|---|---|
| `style` | string | CSS string; default layout is a flex column. Use `display:grid; gap:…` or `display:flex; gap:…` to arrange children. |

### `form` — bundle child fields (has `children`)
| prop | type | notes |
|---|---|---|
| `param` | string (opt) | If set, on submit all child field values are bundled into **one** JSON object broadcast to this param. If omitted, each child writes its own param individually. |
| `submitLabel` | string (opt) | Submit button text (default `"Submit"`). |
| `style` | string (opt) | CSS string. |

> For approve/reject style decisions, prefer a `div` + explicit `button`s (so each
> decision has its own `action` name). Use `form` when you just want one bundled
> object and a single submit.

---

## Display (no `param`)

### `text`
| prop | type | notes |
|---|---|---|
| `value` | string | The text to show. (In fused, `$param`/`{{ref}}` in `value` render verbatim — use a data-bound node for live data.) |
| `variant` | enum | `default`, `muted`, `small`, `large`, `h1`, `h2`, `h3`, `h4`. Picks the element + styling. |
| `style` | string | CSS string. |

### `html`
| prop | type | notes |
|---|---|---|
| `value` | string | **Verbatim** HTML — *no* `$param`/`{{ref}}` substitution. Good for static lists/bold in a plan. |
| `style` | string | CSS string. |

### `diff` — show a before/after change (static, not data-bound)
| prop | type | notes |
|---|---|---|
| `before` | string (opt) | Old text; the line diff against `after` is computed for you. Use `""` for a brand-new file. |
| `after` | string (opt) | New text. |
| `diff` | string (opt) | A precomputed unified-diff string (use instead of `before`/`after`). |
| `oldLabel` / `newLabel` | string (opt) | Header labels (e.g. the file name). |

> Ideal for a **spec review**: inline the old + new `<stem>.spec.md` text in
> `before`/`after` so the human sees exactly what changed. The content is inlined by
> you — `diff` does no `$param`/`{{ref}}` substitution.

### `image`
| prop | type | notes |
|---|---|---|
| `src` | string | Image URL. |
| `alt` | string | Alt text. |

> `metric`, charts, `sql-table`, and maps are **data-bound** (need an environment
> + venv). Out of scope for static feedback widgets.

---

## Inputs (write a `param`)

### `dropdown` — single choice → scalar string
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` | string (opt) | Label above the control. |
| `options` | `[{value:string, label?:string}]` | Choices. `label` defaults to `value`. |
| `defaultValue` | string (opt) | Initial selection. |
| `placeholder` | string (opt) | Shown when nothing selected. |
| `nullable` | boolean (opt) | If true, nothing auto-selected (param starts null). If false/absent, the first option is selected when there's no `defaultValue`. |
| `disabled` | boolean (opt) | |

### `checkbox-group` — multi choice → **string[]**
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. Receives an **array** of chosen `value`s. |
| `label` | string (opt) | |
| `options` | `[{value:string, label?:string}]` | Choices. |
| `defaultSelected` | `string[]` (opt) | Values ticked on mount. |
| `minSelected` / `maxSelected` | number (opt) | Advisory min/max (helper text; max disables extra rows). |
| `disabled` | boolean (opt) | |

> The param holds an **array** — never reference it in SQL (arrays aren't
> SQL-substitutable). For single-select, use `dropdown`.

### `text-input` — short free text → scalar string
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` / `placeholder` / `defaultValue` | string (opt) | |
| `type` | string (opt) | HTML input type — `"text"` (default), `"email"`, `"password"`, … |
| `debounceMs` | number (opt) | Broadcast delay after typing (default 300). |
| `disabled` | boolean (opt) | |

### `text-area` — long free text → scalar string
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` / `placeholder` / `defaultValue` | string (opt) | |
| `rows` | number (opt) | Visible rows (default 3). |
| `debounceMs` | number (opt) | Default 300. |
| `disabled` | boolean (opt) | |

### `number-input` — number → scalar number
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` / `placeholder` | string (opt) | |
| `defaultValue` | number (opt) | |
| `min` / `max` | number (opt) | |
| `step` | number (opt) | Default 1. |
| `disabled` | boolean (opt) | |

### `slider` — number → scalar number
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` | string (opt) | |
| `min` / `max` / `step` | number | Defaults 0 / 100 / 1. |
| `defaultValue` | number (opt) | Default 0. |

### `datetime-input` — date/time → scalar string
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key. |
| `label` / `defaultValue` | string (opt) | |

### `color-input` — color → scalar string
| prop | type | notes |
|---|---|---|
| `param` | string | Answer key (hex string). |
| `label` / `defaultValue` | string (opt) | |

---

## `button` — the decision (reports an action; writes no param)

| prop | type | notes |
|---|---|---|
| `label` | string | Button text. |
| `action` | string (opt) | Action name reported on press; the event carries the full `params` snapshot. This is the value that comes back as `action` from `widget open`. |
| `submit` | boolean | **`true` = terminal**: settles the session and returns control to you. Default `false` = intermediate signal, page stays open. |
| `variant` | enum (opt) | `"primary"` (main action) / `"secondary"` (alternative). |
| `style` | string (opt) | |

- A button with `submit: true` is what **ends** `widget open`. Give every submit
  button a **distinct `action`** so you can tell which was pressed.
- A button with neither `action` nor `executor` is inert.
- (`executor` — running a UDF on press — is a data/act feature that needs a
  project + environment; not used for static feedback. See `fused-widgets`.)

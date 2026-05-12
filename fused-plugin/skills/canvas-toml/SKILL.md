---
name: canvas-toml
description: Format reference for `canvas.toml` files that define a Fused canvas (nodes, edges, viewport) plus the surrounding folder layout (`<udfName>.py`, `.json`, `.md`, `.html`, `_shared.fused`). Use when creating, editing, or validating any `canvas.toml`, adding/removing UDF nodes, wiring edges, defining folder groupings, or scaffolding a new canvas folder.
---

# Fused canvas folder + `canvas.toml`

A Fused canvas stored in git is a folder containing one `canvas.toml` plus per-UDF source files. Push to the connected repo and Fused picks up the changes automatically.

## Folder layout

```
my_canvas/
  canvas.toml           # required: layout and node metadata
  udf_0.py              # Python UDF source
  udf_1.py
  widget.json           # optional: json_ui widget (stem = udfName)
  textbox.md            # optional: textbox/markdown widget (stem = udfName)
  page.html             # optional: html_template widget (stem = udfName)
  _shared.fused         # optional: access control
```

- `<name>.py` / `.json` / `.md` / `.html` — source for a UDF; the **stem must match a node's `udfName`**.
- `_shared.fused` — omit ⇒ private (author only). Empty file ⇒ team. Set `access_scope = "public"` for public. Set `token = "<value>"` to control the URL slug.

Do **not** mix `canvas.toml` with the legacy `collection.json` layout in one folder — `canvas.toml` wins if both are present.

## `canvas.toml` example

```toml
type = "canvas"
version = 2
# previewImageUrl = "https://example.com/preview.png"  # optional

[canvas]
edges = []  # [["sourceUdfName", "targetUdfName"], ...]

[[canvas.nodes]]
udfName = "udf_0"
description = "My first UDF"
title = "udf_0"
visible = true
x = -2515.89
y = -288.929
zIndex = 1
width = 700
height = 500

[[canvas.nodes]]
udfName = "udf_1"
description = "My second UDF"
title = "udf_1"
visible = true
x = -2415.89
y = -288.929
zIndex = 2
width = 700
height = 500

[canvas.viewport]
x = 1437.76
y = -80.62
zoom = 0.5

[canvas.viewportBounds]
minX = -2875.52
minY = 161.24
maxX = -1843.52
maxY = 1703.24
```

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `type` | string | Always `"canvas"` |
| `version` | integer | Always `2` |
| `name` | string | Optional display name (server falls back to folder name) |
| `previewImageUrl` | string | Optional preview image URL |

## `[canvas]`

| Field | Type | Notes |
|---|---|---|
| `edges` | array of `[source, target]` pairs | Each pair references `udfName` values |
| `nodes` | array of node tables | See node fields below |
| `viewport` | table | Optional — `x`, `y`, `zoom` |
| `viewportBounds` | table | Optional — `minX`, `minY`, `maxX`, `maxY` |

## `[[canvas.nodes]]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `udfName` | string | yes | Must match a source file stem |
| `x`, `y` | float | yes | Canvas coordinates |
| `zIndex` | integer | yes | Layer order |
| `width`, `height` | integer | yes | Pixel dimensions |
| `description` | string | no | Defaults to `"UDF: <name> (auto)"` |
| `title` | string | no | Defaults to `udfName` |
| `visible` | boolean | no | Output panel visibility; default `true` |
| `type` | string | no | Omit for standard UDF; `"udf-folder"` for folder nodes |
| `textBoxColor` | string | no | Background color for textbox nodes |
| `textBoxGradient` | boolean | no | Textbox gradient toggle |
| `textBoxScaleFactor` | number | no | Textbox content scale |
| `textBoxAlignment` | string | no | Textbox content alignment |

## Folder nodes (`type = "udf-folder"`)

Visual grouping only — child UDFs still live as flat files in the canvas folder.

```toml
[[canvas.nodes]]
type = "udf-folder"
folderName = "Section_1"
folderColor = "#9370DB40"
childUdfOrder = ["udf_0", "udf_1"]
# isLocked = true  # optional, default false
x = -2600.0
y = -350.0
zIndex = 0
width = 1000
height = 700
```

| Field | Notes |
|---|---|
| `folderName` | Display name |
| `folderColor` | Optional hex+alpha color |
| `childUdfOrder` | Ordered `udfName` list for UDFs in this folder |
| `isLocked` | Locks child editing; default `false` |

## Authoring rules

- Ephemeral UI state (selection, sidebar) is **not** stored — only nodes, edges, viewport.
- When adding a UDF: create the `.py` (and any widget file) **and** add a matching `[[canvas.nodes]]` entry with the same stem.
- When removing a UDF: delete its source file(s) **and** its node entry, plus any `edges` referencing it.
- UDFs can call each other via `fused.load("<udfName>")`. For multiprocessing, split into a new UDF.

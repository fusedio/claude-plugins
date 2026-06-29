# list_open_cards

Return the inbox decision-half feed: every **open blocking card that needs a
human**, from the live app state file (`~/.openfused/app/state.json`, or the
directory named by `OPENFUSED_APP_DIR_STATE`).

A card is in this feed iff its `status` is `pending` **and** its
`continuationPolicy` would wake the assignee (`wake_assignee`), across **all
effects** — so the inbox view can surface every blocking decision (`reply`,
`approval_gate`). The `inbox_view` UDF reads this feed and narrows it (dropping
`review_work_product` cards) for the inbox `question` projection. A `none`-policy
card never blocks and is excluded.

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `project` | string | `""` | Project slug to filter on. Empty string returns open cards across all projects. |

## Output

A list of interaction-card records (raw camelCase dicts from `state.json.cards`),
**oldest-first by `createdAt`**. Each record is the `InteractionCardRecord` shape
`list_cards` documents.

Filter applied (in order):
1. `status == "pending"`,
2. `continuationPolicy == "wake_assignee"`,
3. optional `project` match,
4. sort by `createdAt` ascending.

## Source

Reads `state.json` directly with stdlib (`json`, `os`); no third-party imports.
State path resolution:
- `OPENFUSED_APP_DIR_STATE` is a **directory** (not a file path); when set, used verbatim.
- Otherwise: `~/.openfused/app`.
- State file is always `<app_dir>/state.json`.

Missing file or JSON parse errors return an empty list (no exception raised).

## Constraints

- Stdlib-only; no third-party packages.
- Parameterized via `@udf def list_open_cards(project: str = "")` (the injected decorator form).
- Preserves raw on-disk camelCase keys; does not reconstruct via any schema model.
- Read-only this step (Phase 0). Step 05 wires this into the derived inbox view.

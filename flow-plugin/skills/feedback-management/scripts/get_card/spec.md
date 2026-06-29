# get_card

Return a single interaction-card record by id from the live app state file
(`~/.openfused/app/state.json`, or the directory named by
`OPENFUSED_APP_DIR_STATE`).

## Inputs

| Param | Type | Default | Description |
|---|---|---|---|
| `id` | string | `""` | The `card_<hex>` id to look up. Empty string never matches. |

## Output

The matching interaction-card record (raw camelCase dict from `state.json.cards`)
— the same `InteractionCardRecord` shape `list_cards` documents. Mirrors `getCard`.

When no card matches (unknown id, empty id, or missing state file), returns the
not-found ack:

```json
{"ok": false, "error": "not found"}
```

## Source

Reads `state.json` directly with stdlib (`json`, `os`); no third-party imports.
State path resolution:
- `OPENFUSED_APP_DIR_STATE` is a **directory** (not a file path); when set, used verbatim.
- Otherwise: `~/.openfused/app`.
- State file is always `<app_dir>/state.json`.

Missing file or JSON parse errors are treated as an empty store → not-found ack
(no exception raised).

## Constraints

- Stdlib-only; no third-party packages.
- Parameterized via `@udf def get_card(id: str = "")` (the injected decorator form).
- Preserves raw on-disk camelCase keys; does not reconstruct via any schema model.
- Read-only this step (Phase 0). Step 02 adds the write UDFs.

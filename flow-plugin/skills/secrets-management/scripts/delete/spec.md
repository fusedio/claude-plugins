# delete

Removes a secret from the OS keychain store (`~/.openfused/secrets.json` or the path
named by `OPENFUSED_SECRETS_FILE` is used as the keychain account key).

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `name` | `""` | The secret name to delete |

## Output shape

On success:

```json
{"deleted": "openfused-token"}
```

When the secret is absent (ack, not a raised error):

```json
{"ok": false, "error": "not found"}
```

## Notes

- **Ungated** on the UDF surface — mirrors the app's delete route, which passes
  `--yes`. The MCP `delete_secret` tool's `--enable-destructive` gate does not apply
  here.
- After deletion the same OS keychain store is what the CLI / MCP / in-sandbox shim see,
  so a subsequent `LocalSecretsBackend.get_secret` raises `KeyError`.
- Write via the UDF endpoint: `{"udf": "delete", "overrides": {"name": "..."}}`.

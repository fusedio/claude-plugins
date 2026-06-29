# get

Reveals the cleartext value of a single secret from the OS keychain store
(`~/.openfused/secrets.json` or the path named by `OPENFUSED_SECRETS_FILE` is used as
the keychain account key).

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `name` | `""` | The secret name to reveal |

## Output shape

On success:

```json
{"name": "openfused-token", "value": "s3cr3t"}
```

When the secret is absent (ack, not a raised error):

```json
{"ok": false, "error": "not found"}
```

## Notes

- Returns cleartext through the dev-serve `{"data": ...}` envelope — accepted for this
  surface (localhost + token, the same posture as the app's lazy-reveal route).
- Readable over the SQL endpoint with a `name` override, e.g.
  `SELECT * FROM {{get?name='openfused-token'}}`, or via the UDF endpoint.

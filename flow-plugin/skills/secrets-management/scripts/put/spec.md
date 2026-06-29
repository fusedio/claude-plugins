# put

Creates or overwrites a secret in the OS keychain store
(`~/.openfused/secrets.json` or the path named by `OPENFUSED_SECRETS_FILE` is used as
the keychain account key).

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `name` | `""` | The secret name to create or overwrite |
| `value` | `""` | The cleartext value |

## Output shape

```json
{"name": "openfused-token", "arn": "/Users/me/.openfused/secrets.json"}
```

The store path stands in for the provider `arn`, matching
`LocalSecretsBackend.put_secret`.

## Notes

- A value written here is readable by `LocalSecretsBackend.get_secret` (and the CLI /
  MCP / in-sandbox `get_secret` shim) — both use the same OS keychain blob.
- **No `function_prefix` gate.** That gate is AWS-only (it keeps names within the
  Lambda role's IAM read scope) and does not apply to the local store.
- Write via the UDF endpoint:
  `{"udf": "put", "overrides": {"name": "...", "value": "..."}}`.

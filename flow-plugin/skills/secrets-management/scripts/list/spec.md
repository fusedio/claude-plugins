# list

Returns the **names** of secrets in the OS keychain store
(`~/.openfused/secrets.json` or the path named by `OPENFUSED_SECRETS_FILE` is used as
the keychain account key). Values are never returned by this UDF.

## Inputs (all strings)

| Param | Default | Description |
|---|---|---|
| `prefix` | `""` | Optional name-prefix filter; empty string returns all names |

## Output shape

A list of single-field dicts, sorted by name:

```json
[{"name": "openfused-db-url"}, {"name": "openfused-token"}]
```

Names only — this is a **deliberate divergence** from
`LocalSecretsBackend.list_secrets`, which also returns an `arn`. The UDF strips to
`name` to match the app's list adapter. Do not "fix" it toward backend parity.

## Notes

- Reads the same OS keychain store as `LocalSecretsBackend`; a missing keychain item
  yields `[]`.
- Readable over the SQL endpoint as `SELECT * FROM {{list}}`.

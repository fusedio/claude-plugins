---
name: secrets-management
description: Get, put, list, and delete secrets in the local Fernet-encrypted OpenFused secrets store (~/.openfused/secrets.json). Use when managing OpenFused secrets through live UDFs.
disable-model-invocation: true
---

# secrets-management

The local secrets store exposed as live UDFs. Reads and writes the **same**
OS-keychain store as `LocalSecretsBackend` (`~/.openfused/secrets.json`, or the
path named by `OPENFUSED_SECRETS_FILE` — used as the keychain account key) — so
this surface, the `fused secrets` CLI, and the in-sandbox `get_secret` shim
all share one live store. An agent drives these UDFs over the local execution
layer started with `fused dev serve`.

## What this project is

Four UDFs over the local OS-keychain secrets store: `list` (names), `get` (reveal a
value), `put` (create/update), `delete` (remove). **Local backend only.**

The split is: **read via SQL** (`{{list}}`, `{{get}}`), **write via UDF**
(`put`, `delete`). Both endpoints are addressed with
`?workspace=_core&project=secrets-management`.

## Access pattern

Start the local execution layer. `fused dev serve` binds a loopback server,
prints ONE JSON handshake line, then runs in the foreground:

```
fused dev serve
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}

# Export the origin + token from that handshake line:
ORIGIN=http://127.0.0.1:<port>
TOKEN=<token>

# Read — POST to the SQL endpoint
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=secrets-management" \
  -d '{"sql": "SELECT * FROM {{list}}"}'
curl -s -X POST "$ORIGIN/api/exec/sql?t=$TOKEN&workspace=_core&project=secrets-management" \
  -d '{"sql": "SELECT * FROM {{get?name='\''openfused-token'\''}}"}'

# Write — POST to the UDF endpoint
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=secrets-management" \
  -d '{"udf": "put", "overrides": {"name": "openfused-token", "value": "s3cr3t"}}'
curl -s -X POST "$ORIGIN/api/exec/udf?t=$TOKEN&workspace=_core&project=secrets-management" \
  -d '{"udf": "delete", "overrides": {"name": "openfused-token"}}'
```

Response shape: `{"data": <result>, "error": null}` on success;
`{"data": null, "error": "<message>"}` on failure.

## The store (differs from task-management)

Store path resolution, highest precedence first:

1. The `secrets_file` parameter on any operation (e.g. `get(name="x", secrets_file="/path/to/secrets.json")`) — use this to run the skill standalone against your own store, no environment setup required.
2. The `$OPENFUSED_SECRETS_FILE` env var when set.
3. `~/.openfused/secrets.json` (default).

Unlike the task-management UDFs — stdlib-only over a *plain-JSON* file — this store
lives in the **OS keychain**. The keychain item's coordinates are
`service=<service>`, `account=<resolved store path>`. The value is a JSON
`name → value` map stored directly in the keychain item — no on-disk file.

The keychain **service name** is likewise resolvable per operation via the optional
`service` param (precedence over `$OPENFUSED_KEYRING_SERVICE`, default `"openfused"`),
so two standalone uses on one machine can keep separate namespaces. Both `secrets_file`
and `service` default to today's values when omitted, so existing callers are unaffected.
Each UDF therefore depends on `keyring` and inlines the exact keychain-access logic
of the local secrets backend. Keeping that logic identical is the interop
contract: a value written by `put` must be readable by `LocalSecretsBackend.get_secret`,
and vice-versa.

> **Keychain access prompt (interop note).** The materialized `_core` venv
> interpreter is a *different* binary than the one that started the MCP server;
> macOS may raise a per-binary access prompt the first time it reads the keychain
> item. Grant access when prompted. If the venv binary is denied access or the run is
> headless, the operation raises a `RuntimeError` (there is no key-file fallback).

## Operations

All parameters arrive as strings. Empty string is the zero value. Missing-secret
reads/deletes return `{"ok": false, "error": "not found"}`.

### list

```
list(prefix: str = "") -> list[dict]
```

Returns `[{"name": <name>}, ...]` sorted by name, optionally filtered by `prefix`.
**Names only — never values** (mirrors the app's list adapter). Deliberate divergence
from `LocalSecretsBackend.list_secrets`, which also returns `arn`.

SQL shorthand: `SELECT * FROM {{list}}`.

### get

```
get(name: str = "") -> dict
```

Reveals one secret as `{"name", "value"}`; missing → the not-found ack. Returns
cleartext through the response envelope (accepted for this surface).

### put

```
put(name: str = "", value: str = "") -> dict
```

Creates or overwrites a secret; always writes encrypted. Returns
`{"name", "arn"}` (store path as `arn`). **No `function_prefix` gate** (AWS-only).

### delete

```
delete(name: str = "") -> dict
```

Removes a secret; returns `{"deleted": <name>}` or the not-found ack. **Ungated**
(mirrors the app's `--yes` delete route).

## Rendering as a `sql-table` widget

The `list` UDF is enough to render the secret inventory as a table — no other UI.
A saved `sql-table` widget reads through `{{_core.secrets-management.list}}`, so a
single JSON-UI node gives you a sortable / filterable grid of secret **names**.

It is backed by `list`, **never `get`** — the widget shows names only and never
puts a cleartext value on the rendered surface. There is no widget seam for the
write ops (`put`/`delete`); mutate through the UDF endpoint directly.

The config ships **inside the wheel** as a saved widget of this project, at
`secrets-management/widgets/secrets_table.json`. It materializes alongside the UDFs
to `~/.openfused/core/secrets-management/widgets/secrets_table.json`, so it is
available on first run with no authoring step — open it with:

```bash
fused widget open ~/.openfused/core/secrets-management/widgets/secrets_table.json
```

The shipped config:

```json
{
  "type": "sql-table",
  "props": {
    "title": "Secrets",
    "sql": "SELECT name FROM {{_core.secrets-management.list}} ORDER BY name",
    "sortable": true,
    "filterable": true
  }
}
```

> **Where it resolves.** The `{{_core.*}}` cross-project ref needs an `_core`
> resolve context, which today means the In-Loop app's dev serve
> (`fused dev serve` / `fused inloop`). The deployed-serve bundle has no
> `_core` resolve context, so a public URL is not supported for this widget.

## Layout (skill-folder convention)

```
scripts/
├── pyproject.toml          # deps: duckdb/pandas/pyarrow (SQL resolver) + keyring (store)
├── list/   {main.py, spec.md}
├── get/    {main.py, spec.md}
├── put/    {main.py, spec.md}
└── delete/ {main.py, spec.md}
```

Source lives in the wheel under `fused/_core/secrets-management/` (read-only).
The local-backend venv materializes at
`~/.openfused/core/secrets-management/scripts/.venv` on first startup. Adding a new op
= add `scripts/<name>/{main.py,spec.md}`.

## Conventions

- Each UDF is self-contained: the store helpers (`_store_path`, `_load`, `_save`, …)
  are duplicated in every `main.py` — no cross-UDF imports in the sandbox. Keep every
  copy identical to the others and to the local secrets backend.
- UDF logic does not import `openfused.*` (the exec sandbox shadows the package with a
  shim that exposes only `get_secret`); reach the store directly via the inlined
  keychain helpers.
- All params are strings.
- `_save` calls `keyring.set_password` directly (no on-disk file write) to stay
  byte-identical to the backend's writer.
- Two-writer last-write-wins clobber is accepted in this POC (locking is out of scope).
- Store path resolves from the per-call `secrets_file` param, else `OPENFUSED_SECRETS_FILE`,
  else the default; the keychain service name resolves from the per-call `service` param,
  else `OPENFUSED_KEYRING_SERVICE`, else `"openfused"`.

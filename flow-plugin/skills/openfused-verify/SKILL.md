---
name: openfused-verify
description: Security scanning, testing, and correctness validation for code running in openfused. Use when writing or reviewing verify_code, test_code, get_audit_log calls, or when advising on security policy, spec checks, data expectations, or code quality in the fused context.
---

# Security, testing, and validation in fused

## Overview

fused has several complementary quality layers that can be applied to code before or after execution:

| Layer | Tool | What it checks |
|---|---|---|
| Security scan | `verify_code` / `fused code verify` | Code patterns, input file safety |
| Spec conformance | `verify_code(spec=...)` | LLM check: does code match intent? |
| Correctness | `execute_code(expectations=...)` | Output schema, null rates, row counts |
| Test suite | `test_code` / `fused code test` | Pytest + line/branch coverage in Lambda |
| Audit | `get_audit_log` / `fused audit log` | What ran, what was blocked |

These layers are complementary. Use them in combination for critical or production code paths.

---

## Security scanning (`verify_code`)

`verify_code` scans code and input files **without executing** anything. Use it before `execute_code` when you want to catch problems early, or as a gate in CI. The scanners run in the same single canonical pre-execution order as the `execute_code` pipeline (spec required → input firewall → code → type check → spec → dependencies → input PII); it streams a best-effort progress message that never affects the findings returned.

> **Advisory, not a sandbox.** The code scan is static (AST) pattern matching. It catches honest mistakes and low-effort misuse, but it is **not a containment boundary** — a dynamic lookup such as `importlib.import_module("subprocess")` or `getattr(builtins, "exec")` slips past it, and a BLOCK finding only means *this scanner* refused, not that the code could not have run. The real isolation for executed code is `execute_code`'s per-call subprocess plus the execution role's IAM scope. Scope that IAM role tightly; do not rely on verify findings as your security perimeter.

```python
result = await mcp__openfused__verify_code(
    code="import os\nresult = os.listdir('/')",
)
# result["blocked"] == False  # WARN findings don't block
# result["findings"][0]["rule_id"] == "code/dangerous-import"
```

### Finding reference (all rules)

This is the master table of every rule the verify pipeline can emit. `verify_code` surfaces the `code/*`, `dep/*`, and `input/*` rows (pre-execution); `output/*` come from the post-execution firewall, `spec/*` from the spec scanner, and `correctness/*` from `execute_code(expectations=...)`.

| Rule ID | Severity | What triggers it |
|---|---|---|
| `code/dangerous-import` | WARN | `import os`, `import sys`, `import subprocess`, `import socket`, etc. |
| `code/exec-eval` | BLOCK | `exec(...)` or `eval(...)` calls |
| `code/__import__` | BLOCK | `__import__(...)` call |
| `code/network-import` | WARN | `urllib`, `requests`, `httpx`, `boto3`, `aiohttp`, etc. |
| `code/credential-string` | BLOCK | Hard-coded credential string detected |
| `code/path-traversal` | WARN | Path traversal pattern in a string literal |
| `code/sql-injection` | WARN | String concatenation inside a SQL call |
| `code/syntax-error` | BLOCK | Code fails to parse |
| `dep/cve` | WARN | Known CVE in a scanned package (AWS: env image packages; local: the `--project`/`project=` project's `pyproject.toml` deps) |
| `dep/typosquatting` | WARN | Package name resembles a well-known package (e.g. `numppy`) |
| `dep/osv-unavailable` | INFO | OSV vulnerability database unreachable |
| `input/path-traversal` | BLOCK | Input filename contains `..` sequences |
| `input/zip-bomb` | BLOCK | Input archive expands to an unsafe size |
| `input/pii` | WARN | Input file content contains email, SSN, credit card, or phone patterns |
| `output/aws-key` | BLOCK | `AKIA…` or `ASIA…` AWS access key ID in output (long-term and session credentials) |
| `output/secret-pattern` | BLOCK | Credential pattern in output: `password=`, `token=`, `api_key=`, `secret=`, `AWS_SECRET_ACCESS_KEY` |
| `output/pii` | WARN | Email, SSN, etc. in the execution output |
| `code/type-error` | WARN | `ty` static type error or unresolved name in Python code |
| `spec/mismatch` | BLOCK | LLM judges code doesn't match the provided spec |
| `spec/review-error` | WARN | LLM call failed (API timeout, missing key, etc.) |
| `spec/required` | BLOCK | No spec provided but `require_spec` is enabled on the environment |
| `correctness/schema-mismatch` | WARN | Column name or dtype doesn't match expected |
| `correctness/null-rate` | WARN | Null rate exceeds declared threshold |
| `correctness/row-count` | WARN | Row count outside declared range |
| `correctness/bounds` | WARN | Numeric column outside declared min/max |

BLOCK findings prevent execution and set `blocked: true` in the response. WARN findings are attached to the response under `verify.findings` but execution proceeds.

### Input file safety

When passing files to `execute_code`, `test_code`, or `verify_code` — via `input_files` (a host path) or `input_file_contents` (base64) — two checks run automatically:

- **Path traversal**: the in-Lambda *filename* (the mapping key) is checked; keys like `../../etc/passwd` are blocked before the file reaches Lambda. Always use bare filenames (e.g. `"data.csv"`, not `"../data.csv"`).
- **PII in inputs**: if a file contains recognizable PII (email addresses, SSNs, credit card numbers), a `input/pii` warning is added. This is a heads-up, not a block — the caller is responsible for deciding whether sending PII into a Lambda execution is appropriate.

---

## Spec conformance checking

Pass `spec` to `verify_code` to have Claude review whether the code matches a natural-language description of intent. This is a pre-execution check — it runs before `execute_code` is called.

```python
result = await mcp__openfused__verify_code(
    code="import subprocess\nresult = subprocess.check_output(['ls', '/'])",
    spec="return the number of rows in the dataset",
)
# result["blocked"] == True  (spec/mismatch at BLOCK severity)
# result["findings"][0]["rule_id"] == "spec/mismatch"
```

`execute_code` also accepts `spec=` directly — the spec check runs as part of the pre-execution pipeline and blocks the call if a mismatch is detected.

When to use spec checks:
- Agent-generated code that should match a user's stated goal
- High-stakes transformations where incorrect code would silently produce wrong results
- Any time you want a second opinion before running expensive or destructive code

Requires an Anthropic API key, resolved in order: `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) in the server environment, then the `anthropic-api-key` secret in the resolved environment's secrets backend — store it once with `put_secret("anthropic-api-key", "sk-ant-...")` (or `fused secrets put anthropic-api-key sk-ant-...`) and no server env var is needed. On AWS environments the secret name must carry the env's function prefix (the standard `put_secret` naming rule), e.g. `openfused-anthropic-api-key`. If no key is found, a `spec/review-error` warning is emitted and execution proceeds.

### Per-UDF specs (`spec.md`)

In the workspace model, each UDF carries a `spec.md` in its own folder under `scripts/` — `taxi-pipeline/scripts/taxi-analysis/spec.md`, `taxi-pipeline/scripts/trip-dashboard/spec.md`. The flat `<stem>.spec.md` sidecar convention is removed.

- `fused code verify <file> --spec "..."` still works for ad-hoc verification outside a UDF folder.
- The flat sidecar auto-discovery and `--no-spec` flag are **removed** (Sub-plan A). Pass `--spec TEXT` explicitly when you want a spec check outside a UDF context.
- Over MCP, pass the UDF's `spec.md` content as `spec=` when executing or verifying that UDF's entrypoint.
- The per-call `spec=` parameter to `execute_code` and `verify_code` is unchanged.

---

## Correctness expectations (`execute_code`)

After execution, fused can validate the return value against a data quality contract. Pass `expectations` to `execute_code`:

```python
result = await mcp__openfused__execute_code(
    code="...",
    expectations={
        "expected_columns": [
            {"name": "user_id", "dtype": "int64"},
            {"name": "score", "dtype": "float64"},
        ],
        "max_null_rate": 0.05,         # max 5% nulls in any column
        "row_count": {"min": 1000, "max": 100000},
        "bounds": {"score": {"min": 0.0, "max": 1.0}},
    },
)
```

For expectations to work, the code must assign `result` to a JSON string with this shape (fused's DataFrame helper does this automatically):

```json
{
  "columns": {"user_id": "int64", "score": "float64"},
  "null_rates": {"user_id": 0.0, "score": 0.02},
  "row_count": 5000,
  "stats": {"score": {"min": 0.1, "max": 0.95}}
}
```

Violations are returned as `correctness/*` warnings under `result["verify"]["findings"]`. Correctness findings are always WARN (never BLOCK) — they flag drift, they don't halt the pipeline.

---

## Testing code in Lambda (`test_code`)

`test_code` runs a pytest test file against user code **inside the actual Lambda environment**. This catches import errors, missing packages, and runtime behaviour that static analysis misses.

```python
result = await mcp__openfused__test_code(
    code="""
def add(a, b):
    return a + b
""",
    test_file="""
from user_code import add

def test_add_integers():
    assert add(1, 2) == 3

def test_add_floats():
    assert abs(add(1.1, 2.2) - 3.3) < 1e-9
""",
)
# result["results"]["passed"] == True
# result["results"]["summary"] == {"total": 2, "passed": 2, "failed": 0, ...}
# result["results"]["coverage"]["line_rate"] == 1.0
```

**Rules for the test file:**
- Import user code via `from user_code import <name>` — the module is always named `user_code`.
- Standard pytest conventions apply: functions prefixed `test_`, `assert` statements, fixtures.
- No need to declare pytest as a requirement; it is auto-installed on first use.

**Coverage report fields:**
- `line_rate`: fraction of lines executed (0.0–1.0)
- `branch_rate`: fraction of branches taken
- `files.user_code.missing_lines`: list of line numbers not reached
- `files.user_code.missing_branches`: list of `[from_line, to_line]` branch pairs not taken

When to use test_code vs verify_code:
- Use `verify_code` for fast security pre-screening (no Lambda cold start).
- Use `test_code` when you need behavioural confidence — that the code is correct, not just safe.
- Both are complementary: verify first, then test.

---

## Audit log (`get_audit_log`)

Every `execute_code` and `verify_code` call is recorded in a local SQLite database (`~/.openfused/audit.db`). Unlike an in-process ring buffer, events survive server restarts. Use `get_audit_log` to inspect what ran and what was blocked.

```python
result = await mcp__openfused__get_audit_log(limit=20, status="blocked")
# result["events"][0] == {
#   "event_type": "execute_code",
#   "status": "blocked",
#   "findings": [...],
#   "timestamp": "2026-05-25T12:00:00Z",
#   ...
# }
# result["s3_read"] == False  (True when S3 was also queried)
```

Filter parameters:
- `limit`: max events to return (default 50)
- `status`: `"allowed"`, `"blocked"`, or `"warned"`
- `event_type`: `"execute_code"`, `"verify_code"`, or `"cache_clear"`
- `project`: the workspace project the event was recorded under (every event is stamped with the resolved project's name — `null` in global scope). CLI: `fused audit log --project NAME`.
- `start_date` / `end_date`: ISO date strings (`"YYYY-MM-DD"`). When provided and an `audit_bucket` is configured, S3 is also queried so events from past sessions or other server instances are included.

For durable cross-instance audit history, configure an `audit_bucket` (S3 with Object Lock) in the environment via `fused env update --audit-bucket`. Events are written to both the local DB and S3; `get_audit_log` with a date range merges both sources.

---

## Verify configuration

Verify policy is configured **per environment** via `fused env create/update`. There is no separate config file.

### Common fields

| Environment field | CLI flag | Effect |
|---|---|---|
| `audit_bucket` | `--audit-bucket` | S3 bucket for WORM audit records. Setting this automatically enables verify. |
| `require_spec` | `--require-spec` / `--no-require-spec` | Block any `execute_code` call that omits a `spec`. |

```bash
# Enable verify + audit logging
fused env update myenv --audit-bucket my-audit-bucket

# Require a spec on every execution
fused env update myenv --require-spec
```

Verify is **automatically enabled** when either `audit_bucket` or `require_spec` is set. It is disabled when both are absent.

### Full verify config (JSON)

For complete control, pass a JSON object to `--verify`:

```bash
fused env update myenv --verify '{"enabled": true, "typecheck": true}'
```

| Field | Default | Effect |
|---|---|---|
| `enabled` | `false` | Master switch for the verify pipeline |
| `audit_bucket` | `null` | S3 bucket for WORM audit records |
| `require_spec` | `false` | Block calls that omit a spec |
| `typecheck` | `false` | Run `ty` type-checking on Python code before execution |
| `typecheck_docker` | `false` | Install packages in Docker before type-checking (resolves third-party imports) |
| `scan_deps` | `true` | Scan requirements against OSV vulnerability database. Requirements come from the AWS env image's packages, or — on the local backend — the selected project's `pyproject.toml` `[project].dependencies` (declared deps; pass `--project`/`project=`). No project ⇒ nothing to scan. |

### Type-checking (`code/type-error`)

When `typecheck: true`, fused runs `ty` (Astral's fast type-checker) on Python code before execution:

- **Fast mode** (default): runs `ty` from the host `PATH`; import-resolution errors (`import-unresolved`, etc.) are suppressed since user packages aren't installed in the server process.
- **Docker mode** (`typecheck_docker: true` + requirements provided): builds a Docker image with user packages + `ty` installed, so all imports resolve correctly. The typecheck image is content-addressed on the base image + package set, so a repeat scan with the same inputs reuses it. Requires the `docker` CLI on PATH.

```bash
# Fast type-checking (no Docker required)
fused env update myenv --verify '{"enabled": true, "typecheck": true}'

# Full type-checking with package installs
fused env update myenv --verify '{"enabled": true, "typecheck": true, "typecheck_docker": true}'
```

Type errors appear as `code/type-error` WARN findings. They do not block execution by default; raise the severity to BLOCK if needed via the `rules` field.

### Caller attribution

Set `OPENFUSED_CALLER_NAME` in the server environment to include an identity string in every audit event. This overrides `caller_name` in the verify config.

Individual rule severities can be overridden via the `rules` list in `VerifyConfig` if you construct the config programmatically, but there is no CLI flag for per-rule overrides. The defaults are shown in the findings table above.

---

## Recommended workflow for production code

1. **`verify_code(code, spec=...)`** — pre-screen for security issues and spec conformance before any execution.
2. **`execute_code(code, expectations=...)`** — run with correctness contract; check `result["verify"]` for warnings.
3. **`test_code(code, test_file)`** — run the test suite; require `results.passed == True` before promoting code.
4. **`get_audit_log(status="blocked")`** — periodically review what the policy blocked.

---

## Caching and the verify pipeline

When `execute_code`/`test_code` is called with `cache_max_age > "0s"`, a cache
hit returns a stored result **without re-running the code**. The verify pipeline
treats the two stage kinds differently:

- **Code-dependent stages** (input firewall, dependency scanner, spec check,
  code scanner) decide from inputs already folded into the cache key, so they
  run **before** the lookup. Blocked code never reaches the cache — no HEAD is
  issued for code that cannot execute.
- **Data-dependent stages** (output firewall, `expectations`) inspect the
  *result*, which the key does not capture, so they **replay on every hit**
  against the stored value. A result that today's policy forbids is blocked on
  the hit exactly as on a fresh run (audited `status="blocked"`,
  `cache_hit: true`); the cached object itself is not deleted.

Every cache-enabled call is recorded as an `execute_code` audit event with
`cache_hit` (and `cache_hash`/`age_s` on a hit), so the trail never has a gap
where "nothing ran". `cache_clear` emits its own `event_type: "cache_clear"`
event recording the cleared scope and deleted count.

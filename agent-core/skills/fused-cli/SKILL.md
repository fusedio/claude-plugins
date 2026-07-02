---
name: fused-cli
description: Reference for the fused CLI — environment management, file storage, secrets, code execution, and infrastructure commands. Use when writing or explaining shell commands that invoke `fused`, or when helping users set up, switch between, or provision environments.
---

# fused CLI reference

Check the installed version with `fused --version` (useful for confirming an install before configuring anything).

## Environment selection

Every command targets a specific backend. Two ways to select it:

**Named environment (recommended)** — stored config in `~/.openfused/envs.json`:
```sh
fused --env prod files list
fused --env staging secrets list
```
`--env` can be omitted when the environment is resolved by project manifest or sole-env auto-selection (see resolution rules below).

**Legacy inline selection** — reads config from environment variables:
```sh
fused --backend aws files list        # reads OPENFUSED_* env vars
fused --backend local files list      # host venvs (uv/pip)
fused --backend fused files list      # Fused's managed fused
```

`--env` always wins over `--backend`. `OPENFUSED_ENV` is the env-var form of `--env`.

**Environment resolution order** (first match wins):
1. `--env` flag or `OPENFUSED_ENV` → explicit override (beats everything)
2. Inside a project with `[project].default_env` in `openfused.toml` → manifest pin
3. Exactly one named environment exists → sole-env auto-select
4. Multiple environments, no pin → error naming both fixes: set `default_env` (`fused project set <project> --env <name>`) or pass `--env`
5. No environments → error: run `fused env create`

### Logging

Host logs (`openfused.*` loggers) go to stderr with a timestamp + level + logger-name
format. Set verbosity with `OPENFUSED_LOG_LEVEL` (default `INFO`; accepts `DEBUG`,
`INFO`, `WARNING`, `ERROR`, `CRITICAL`). Use `DEBUG` to surface Lambda cache hits and
cold-start/digest-resolution details when troubleshooting.

```sh
OPENFUSED_LOG_LEVEL=DEBUG fused --env prod code run --file job.py
```

---

## Environment management (`env`)

Named environments bundle all backend config into a named entry in `~/.openfused/envs.json`.

### Create

```sh
# AWS — provisions IAM role + Lambda automatically
fused env create prod --backend aws --prefix myapp- --region us-east-1

# AWS — skip provisioning (config only)
fused env create staging --backend aws --prefix myapp-staging- --no-provision

# Local — bare stdlib venv; scaffolds ~/.openfused/envs/dev/data automatically
fused env create dev --backend local
```

AWS `env create` runs `infra apply` automatically unless `--no-provision` is given. Pass `--no-provision` when the IAM role / Lambda already exist or when you want to review the plan first.

### List and inspect

```sh
fused env list            # all envs with their backend
fused env show prod       # JSON dump of config
fused env show            # config for the resolved environment
```

To pin an environment to a project (the recommended way to avoid per-command `--env`):
```sh
fused project set my-project --env prod   # validates env exists, writes default_env
fused project set my-project --clear-env  # remove the pin
```

### Update fields

```sh
fused env update prod --region us-east-1
fused env update prod --prefix newprefix- --lambda-timeout 600
fused env update prod --audit-bucket my-audit-bucket   # add/change audit bucket
fused env update prod --no-audit-bucket                # remove audit bucket
fused env update prod --require-spec                   # block executions without a spec
fused env update prod --no-require-spec                # remove spec requirement
fused env update prod -p pandas -p duckdb   # set packages (AWS only: baked into the container image)
```

`env update` accepts all the same flags as `env create` (patch semantics — only specified fields change). Use `--no-cache-bucket` / `--no-audit-bucket` to clear a bucket field, and `--no-require-spec` to remove the spec requirement.

### Delete

```sh
fused env delete staging --yes   # removes config only; does NOT teardown AWS resources
```

### Full option reference for `env create`

| Option | Default | Notes |
|---|---|---|
| `--backend` | `aws` | `aws` (Lambda), `local` (host bare venv), or `fused` (Fused cloud). |
| `--region` | `us-west-2` | AWS region |
| `--prefix` | `openfused-` | Lambda function name prefix |
| `--role-arn` | — | Use an existing IAM role instead of creating one |
| `--role-name` | derived | Override the managed IAM role name |
| `--lambda-timeout` | `300` | Execution timeout in seconds |
| `--lambda-memory-mb` | `1024` | Lambda memory (MB). **AWS only.** |
| `--lambda-tmp-storage-mb` | `512` | Lambda `/tmp` ephemeral storage (MB). **AWS only.** |
| `--lambda-architecture` | `x86_64` | Lambda CPU architecture (`x86_64` or `arm64`). **AWS only.** |
| `--lambda-externally-managed` | off | Don't auto-manage the execution Lambda. **AWS only.** Skips the `GetFunction` existence check + `CreateFunction` at execute time (invokes it by name) and skips planning/applying it in `infra plan`/`apply`. Use when the Lambda lifecycle is managed separately (e.g. external IaC). Orthogonal to `--role-arn`, which only short-circuits the IAM role. On `env update`, toggle with `--lambda-externally-managed` / `--no-lambda-externally-managed`. |
| `--docker-image` | — | ECR image URI for the Lambda function. Normally set automatically by `infra build-image`; pass it only to register a pre-built image. |
| `--cache-bucket` | auto-derived | S3 bucket for `input_files` in `execute_code`. Auto-named `<prefix>-cache` by default |
| `--no-cache-bucket` | off | Disable the cache bucket for this env |
| `--audit-bucket` | — | S3 bucket for WORM audit logs. Must have Object Lock enabled; `infra apply` creates it. Also enables verify. |
| `--require-spec` | off | Block `execute_code` calls that omit a `spec`. Also enables verify. Works on all backends. |
| `-p / --package` | — | Pip package to pre-install (repeatable). **AWS only** — baked into the Lambda container image (`image_build.packages`). Errors if passed to a local env. |
| `--system-dep` | — | System package via `dnf` (repeatable). **AWS only** — errors if passed to a local env. |
| `--python-version` | `3.12` | Python version for the container image. **AWS only** — errors if passed to a local env. |
| `--image-platform` | `linux/amd64` | Docker build platform for the container image. **AWS only** — errors if passed to a local env. |
| `--image-repo` | derived from prefix | ECR repository name. **AWS only** — errors if passed to a local env. |
| `--image-tag` | `latest` | Tag for the container image. **AWS only** — errors if passed to a local env. |
| `--builder` | `codebuild` | Image builder. **AWS only** — `codebuild` (default; remote AWS CodeBuild, no local Docker; uses the cache bucket) or `local` (docker build on host). Errors if passed to a local env. |
| `--dockerfile` | — | Path to a user Dockerfile within `--context-dir` (requires `--context-dir`). **AWS only.** |
| `--context-dir` | — | User build-context directory to build instead of the generated Dockerfile. **AWS only.** |
| `--local-path` | `~/.openfused/envs/<name>/data` | Local data directory (**local only**) |
| `--secrets-file` | `~/.openfused/envs/<name>/secrets.json` | Keychain account key identifying the per-env secrets store (**local only**; no file is written) |
| `--no-provision` | off | Skip `infra apply` on AWS |

### Fused (managed-openfused) backend — `--backend fused`

It runs code on **Fused's hosted, managed fused** environment over its data-plane MCP endpoint (an MCP client of the remote fused tool surface). The local side provisions nothing and runs no code itself. Note: `serve` and `infra` commands are not supported on Fused. Create an env with `--backend fused`:

| Option | Default | Purpose |
|---|---|---|
| `--tier` | `prod` | Service tier selecting the base URL (`prod`/`staging`/`unstable`). |
| `--mcp-base-url` | — | Explicit data-plane base URL override (dev/self-host). |
| `--fused-org` / `--fused-env-id` | — | Org + environment (UUID or slug) for the scoped URL; set **together**. Omit both to use the bare endpoint with an env-bound key. |
| `--api-key-secret` | — | Name in fused's local secrets store holding the `ofs_` API key. |

```bash
fused env create fused-prod --backend fused --tier prod \
  --fused-org acme --fused-env-id default --api-key-secret fused/prod-key
```

The API key is resolved (first hit wins) from `--api-key-secret` (local secrets store) → `FUSED_API_KEY` → `FUSED_JWT` (scoped URL only). `serve`/`infra` are not applicable (Fused operates the runtime). Storage is read + presign only (`list_files`/`get_file`); writes and secrets are not exposed by the managed surface yet and raise a clear error.

#### Guided onboarding — the `fused cloud` group

Instead of hand-building the env above, the `fused cloud` group runs the control-plane flow (login → find org/env → wait ready → mint an API key → store it → create the env). Auth0 config defaults to Fused's tenant + the `openfused-server-api` audience; override with `FUSED_CLOUD_AUTH0_DOMAIN` / `FUSED_CLOUD_AUTH0_CLIENT_ID` / `FUSED_CLOUD_AUTH0_AUDIENCE`.

```bash
fused cloud login [--no-browser]            # Auth0 PKCE; caches a control-plane JWT
fused cloud redeem CODE [--tier prod]       # redeem a beta invite: admit + create your org + env
fused cloud orgs [--tier prod]              # list your orgs + envs and their provision_state
fused cloud setup [--tier prod] \           # the one-shot guided flow:
  [--beta-code CODE] \                          #   (optional) redeem a beta invite first, then
  [--org O --env E] [--env-name NAME]           #   pick org/env (auto if you have one), wait ready,
                                                #   mint a key, store it, create the `fused` env
fused cloud key create --org O --env E      # mint + store a key for an existing managed env
fused cloud key revoke --org O --id K       # revoke a data-plane key by id
fused cloud logout [--no-browser]           # delete the cached control-plane JWT
fused cloud logout --env NAME               # ALSO delete that env's stored data-plane key (full logout)
```

`setup` stores the minted key in the local secrets store (e.g. `fused/<env-name>-key`) and writes a `FusedCloudEnvironmentConfig` referencing it — never the raw key in `envs.json`. The fused env name defaults to `fused` for the canonical `default` managed env (else `fused-<env>`). The control-plane JWT is flow-scoped; the MCP server never holds it.

Token resolution at request time (first hit wins): **`FUSED_API_KEY`** env var (an explicit override) → the stored **`api_key_secret`** → **`FUSED_JWT`** (scoped-URL only). A configured-but-absent secret falls through rather than failing. **Logging out:** `fused cloud logout` clears the control-plane JWT; add `--env NAME` to also delete that environment's stored data-plane key (then `fused key revoke` to revoke it server-side).

Tune a managed env after creation with `env update <name>` — the managed-fused fields `--tier`, `--mcp-base-url`, `--fused-org`, `--fused-env-id`, and `--api-key-secret` are accepted (mirroring `env create --backend fused`). `infra` commands are not applicable (Fused operates the runtime) and report that posture.

If you have a **beta invite code**, redeem it during the beta gate either as a standalone step (`fused cloud redeem CODE`, after `login`) or folded into setup (`fused cloud setup --beta-code CODE`). Redeeming admits your account and creates a personal org with a `default` environment, which setup then waits on and wires up. The code is single-use; an invalid or already-redeemed code raises a clear error.

### Verify / security options (all backends)

The `verify` sub-object controls the pre/post-execution security pipeline for `execute_code`. Set fields via JSON patch with `env update`:

```sh
# Enable the verify pipeline with type-checking
fused env update prod --verify '{"enabled": true, "typecheck": true}'

# Also run ty inside Docker so user packages are installed (more accurate)
fused env update prod --verify '{"enabled": true, "typecheck": true, "typecheck_docker": true}'
```

| Field | Default | Notes |
|---|---|---|
| `enabled` | `false` | Master toggle for the full verify pipeline |
| `typecheck` | `false` | Run `ty` type-checking before execution |
| `typecheck_docker` | `false` | When `true` and requirements are set, install packages in Docker first for full import resolution |
| `scan_deps` | `true` | Query OSV for CVEs and typosquatting in requirements |
| `audit_bucket` | — | S3 bucket for WORM audit logs |
| `audit_key_prefix` | `"audit/"` | Key prefix for audit objects |
| `audit_object_lock_days` | — | Retention days for S3 Object Lock (requires bucket with Object Lock enabled) |
| `rules` | — | List of `{"rule_id": str, "severity": "BLOCK"\|"WARN"\|"INFO", "enabled": bool}` overrides |

`typecheck_docker` builds a local mirror image (identified by a hash of base image + requirements, cached across runs) with the user's packages installed, using the env's `docker_image` (or `python:3.12-slim`) as the base. It requires the `docker` CLI on PATH — this is verify tooling only, not an execution backend.

---

## Projects (`project`)

Projects are versioned, deployable collections of UDFs. The on-disk model is: **workspace ⊃ project ⊃ UDF**. All project commands implicitly target the `default` workspace at `~/.openfused/workspaces/default/` (override with `OPENFUSED_WORKSPACES_DIR`).

The first `project new` call auto-creates the default workspace (git init + installs the openfused-managed v5 pre-commit hook). The hook blocks manual commits that touch a UDF's `spec.md` without its entrypoint or vice versa. Use `git commit --no-verify` to bypass it when needed.

### Create a project

```sh
fused project new taxi-pipeline
# Created project 'taxi-pipeline' at ~/.openfused/workspaces/default/taxi-pipeline
```

| Argument | Notes |
|---|---|
| `NAME` | Project name; must match `^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, max 64 chars |

### List projects

```sh
fused project list
```

Prints all project names in the default workspace, sorted. Prints a help message when none exist yet.

### Add dependencies to a project

```sh
fused project add-dep taxi-pipeline duckdb pandas        # runtime deps
fused project add-dep taxi-pipeline pytest coverage --dev # dev deps (for `code test`)
```

Runs `uv add [--dev] <packages>` then `uv sync` inside the project's `scripts/`
dir in one step, so the lockfile and the installed venv stay in step — avoiding
the stale-venv warning (and silent cache-disable) a bare `uv add` would leave
behind. Never hard-fails on tooling problems (missing `uv`, `OPENFUSED_LOCAL_INSTALLER=pip`,
non-zero exit) — it prints a guided `Warning:` instead. Errors only on an unknown project.

### Show a project

```sh
fused project show taxi-pipeline
```

Re-syncs the `openfused.toml` manifest from disk first (structured merge: discovers UDF folders under `scripts/`, rewrites inventory, preserves user-set fields like `description`/`auth`/`cache_max_age` and TOML comments), then prints JSON with keys `name`, `path`, and `udfs`. Exits with an error when the project does not exist.

### Delete a project

```sh
fused project delete taxi-pipeline
```

Removes a project from the default workspace: `git rm -rf -- <name>` followed by
a `--no-verify` commit, then cleans gitignored/untracked residue (`scripts/.venv`,
`__pycache__`). Rejects `_core` and any underscore-prefixed (reserved) name with a
`ValueError`. Prints JSON `{name, deleted, root}` on success.

### Naming rules

Project and UDF names are **lowercase slugs**: `^[a-z][a-z0-9]*([-_][a-z0-9]+)*$`, max 64 chars. Both `-` and `_` are accepted as segment separators, so snake_case UDF names like `list_comments` are valid. Lowercase-only prevents case-collision bugs on case-insensitive filesystems and in S3 key segments.

### Workspace layout

```
~/.openfused/workspaces/default/    # the default workspace (one git repo)
├── .git/                           # openfused-managed pre-commit hook installed here
├── taxi-pipeline/                  # a project = one folder
│   ├── openfused.toml              # manifest (synced by the MCP project_show tool / at deploy)
│   ├── SKILL.md                    # project contract (agents read this for context)
│   ├── assets/                     # static project assets
│   ├── references/                 # dataset notes + findings (one file per topic)
│   ├── widgets/                    # saved project dashboards
│   └── scripts/
│       ├── pyproject.toml          # uv-managed Python deps (note: uv's [project] table, not fused's)
│       ├── tests/                  # project-level pytest suites
│       ├── taxi-analysis/          # a UDF, kind: py
│       │   ├── main.py
│       │   ├── spec.md
│       │   └── test_main.py
│       └── trip-dashboard/         # a UDF, kind: json
│           ├── main.json
│           └── spec.md
└── sales-app/
```

UDF kind is inferred from the entrypoint: `main.py` → `py`, `main.json` → `json`. A folder with both is an error (ambiguous kind). Dot-prefixed and underscore-prefixed directories are skipped.

### Authoring UDFs (agent-authored)

There is no `udf generate` or `project regenerate` command. UDFs are authored by the driving agent:

1. Write `scripts/<name>/spec.md` and get it approved.
2. Write the entrypoint — `scripts/<name>/main.py` for a `py` UDF, or `scripts/<name>/main.json` for a `json` widget UDF.
3. Validate with `fused code verify <file>` (CLI) or MCP `verify_code` before committing.
4. Commit `spec.md` + entrypoint together — the pre-commit hook enforces that spec and entrypoint are always paired in the same commit.

See the **fused-projects** skill for the full spec-first, agent-authored flow (env → project → UDF → run → widget → deploy).

### Deploy a project (`project deploy`)

Batch-deploys all UDFs in a project to a channel. The workspace must be clean (all changes committed) unless `--force` is used.

```sh
fused project deploy taxi-pipeline                     # deploy all UDFs to preview
fused project deploy taxi-pipeline --channel release   # deploy all UDFs to release
fused project deploy taxi-pipeline --force             # bypass dirty-tree check
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | Project name |
| `--channel` | `preview` | `preview` or `release` |
| `--force` | false | Deploy even with uncommitted changes |

> `--channel release` bypasses the preview gate and breaks the rollback
> invariant (rollback targets must be prior release events). Use it only for
> bootstrapping the very first release URL — never for a routine production
> release, which goes `deploy` (preview) → `promote`. See the `fused-projects`
> guardrails.

Requires AWS env + `cache_bucket` + provisioned serving plane (`fused infra serve`). Echoes the resolved env name; prints one URL per UDF. Exits 1 if any UDF fails to deploy.

### Promote a project (`project promote`)

Batch-promotes all UDFs in a project from preview to release.

```sh
fused project promote taxi-pipeline
```

### Show project deploy status (`project status`)

Shows the live cloud deploy snapshot for a project. Marks UDFs that are in the cloud snapshot but absent on disk as **orphaned** (prompt to restore or retire).

```sh
fused project status taxi-pipeline
```

Output columns: `UDF`, `CHANNEL`, `COMMIT`, `ORPHANED`, `URL`.

### Deploy a single UDF (`udf deploy`)

```sh
fused udf deploy analysis --project taxi-pipeline
fused udf deploy analysis --project taxi-pipeline --channel release
fused udf deploy analysis --project taxi-pipeline --force
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--channel` | `preview` | `preview` or `release` |
| `--force` | false | Deploy even with uncommitted changes |

Requires a clean git tree (or `--force`), AWS env + `cache_bucket`, and a provisioned serving plane. Echoes the resolved env on stderr and prints the channel URL on stdout.

### Promote a single UDF (`udf promote`)

Repoints the release channel to whatever commit preview is currently running.

```sh
fused udf promote analysis --project taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |

### Roll back a single UDF (`udf rollback`)

Rolls back the release channel to a prior commit. Defaults to the previous release commit when `--to` is omitted.

```sh
fused udf rollback analysis --project taxi-pipeline
fused udf rollback analysis --project taxi-pipeline --to abc123def
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--to COMMIT` | previous release | Target commit SHA |

### Retire a UDF (`udf retire`)

Revokes the UDF's preview + release mounts, appends a retire event, and drops the UDF from the deploy snapshot. **This cannot be undone via this command.** Prompts for confirmation unless `--yes` is passed.

Retire enforces the same workspace-id conflict gate as deploy/promote/rollback: if the live snapshot was written by a different workspace it refuses unless `--force` is passed (an intentional takeover).

```sh
fused udf retire analysis --project taxi-pipeline
fused udf retire analysis --project taxi-pipeline --yes
fused udf retire analysis --project taxi-pipeline --yes --force   # take over a foreign-owned UDF
```

| Option | Default | Notes |
|---|---|---|
| `NAME` | required | UDF name |
| `--project WF` | required | Project that owns the UDF |
| `--yes` | false | Skip the confirmation prompt |
| `--force` | false | Take over a UDF deployed from a different workspace |

### Pre-commit hook (v5)

The workspace `.git/hooks/pre-commit` is installed/upgraded by `project new` (and by any `bootstrap_workspace` call). Current version: `v5`.

The hook blocks manual commits that touch a UDF's `spec.md` without its entrypoint (`main.py`/`main.json`), or vice versa — including one-sided deletions. The pairing is enforced at depth 4: `<project>/scripts/<udf>/<file>`. Tests, resource files, and other files commit freely. fused's own auto-commits are always paired and pass through without `--no-verify`.

Use `git commit --no-verify` to bypass the hook when needed (e.g. fixing a typo in spec.md alone), but note this bypasses the spec↔entrypoint pairing check.

The hook body embeds `# openfused-managed pre-commit hook v5`. On re-install, older managed versions are upgraded; unmanaged hooks (no marker) are warned about and never overwritten.

---

## File storage (`files`)

### List

```sh
fused files list                        # list all buckets
fused files list --bucket my-bucket     # list all keys in bucket
fused files list --bucket my-bucket --prefix data/2024/
```

### Count

```sh
fused files count --bucket my-bucket
fused files count --bucket my-bucket --prefix logs/ --ext .parquet --ext .csv
```

### Get presigned URL

```sh
fused files get --bucket my-bucket --key data/report.parquet
fused files get --bucket my-bucket --key data/report.parquet --expires-in 7200
```

### Schema inspection

Prints column names, types, row count, and file metadata for Parquet, Arrow IPC, or CSV files.

```sh
fused files schema --bucket my-bucket --key data/report.parquet
```

### Upload

```sh
fused files upload data.parquet --bucket my-bucket --key uploads/data.parquet
cat data.csv | fused files upload - --bucket my-bucket --key uploads/data.csv
```

`SRC` defaults to stdin when omitted; `-` also reads from stdin.

---

## The web UI (flow) — separate tool, out of scope

The local web UI (project pages, task → agent runs with live transcripts, the
widget board) is **flow** — a **separate client** (`fusedio/flow`), started with
the `flow` CLI (or `npx @fusedio/flow` once published). It is **not** a `fused`
subcommand and is **out of scope** for this reference. flow talks to this backend
over `fused dev serve` and the `_core` UDFs. The `fused` CLI's own human-facing
widget surfaces are `fused widget open` / the parley on the standalone
**widget-host** (below) — no full UI needed.

---

## Health check (`doctor`)

`fused doctor` surveys **every** workspace under `~/.openfused/workspaces/`
plus the built-in `_core` workspace and reports per-project health findings. It
exists to turn latent layout/venv drift — the kind that makes a project's widgets
render empty with a confusing `` `.venv` not found `` error only at use time — into
one up-front, actionable report.

```sh
fused doctor          # read-only survey (default)
fused doctor --fix    # remediate the fixable findings, then re-diagnose
```

**Read-only by default** — diagnosis runs the existing resolvers as pure probes
(never `uv sync`, never rewrites a manifest, never re-materializes `_core`). It
prints one block per scope (`_core` first, then `<workspace>/<project>`); a scope
with no issues prints `OK`.

Findings carry a severity — `BLOCK` (broken / won't run) or `WARN` (degraded):

| `rule_id` | Severity | Meaning | Fixable by `--fix`? |
|---|---|---|---|
| `invalid-name` | BLOCK | Project dir name is not a valid slug | no (rename manually) |
| `legacy-layout` | BLOCK | Legacy v1 UDF folder (`main.py`/`main.json`) at project root, no `scripts/` dir | yes (migrate) |
| `venv-missing` | BLOCK | `scripts/.venv` absent/incomplete | yes (`uv sync`) |
| `venv-stale` | WARN | venv older than `pyproject.toml`/`uv.lock` | yes (rebuild) |
| `stray-root-venv` | WARN | Stale root `.venv` beside a valid `scripts/.venv` | yes (remove) |
| `manifest-legacy` | WARN | `openfused.toml` uses `[workflow]` not `[project]` | yes (migrate) |
| `manifest-unreadable` | BLOCK | `openfused.toml` missing/unparseable | no (repair manually) |
| `env-unresolved` | BLOCK | Project env doesn't resolve | no (create/pin an env) |
| `core-uv-missing` | BLOCK | `uv` not on PATH | no (install uv) |
| `core-cache-broken` | BLOCK | A `_core` project lacks its built venv | yes (re-materialize) |
| `core-stale` | WARN | `_core` cache stamp ≠ installed wheel | yes (re-materialize) |

**`--fix`** applies the fixable findings — migrate first (so `scripts/` exists),
then build/refresh the venv, remove stray root venvs, and re-materialize `_core` —
then re-diagnoses and prints the residual. `invalid-name`, `env-unresolved`, and
`manifest-unreadable` always need a human and are never auto-fixed.

**Exit code:** `doctor` exits `1` when any `BLOCK` finding remains (after
remediation, under `--fix`); `WARN`-only or clean exits `0` — so it works as a CI
gate.

---

## Workspace projects (`project`)

A **project** is a directory rooted at an `openfused.toml` manifest — the unit of
scope and memory. Projects are discovered by directory listing
under `~/.openfused/workspaces/default/` (no registry file). Resolution is
git-style: explicit name → `OPENFUSED_PROJECT` → manifest walk-up from cwd →
global scope (pre-project behavior unchanged).

```sh
fused project create taxi --description "NYC taxi analysis"   # scaffold under workspaces/default/taxi
fused project create taxi --env prod-aws                      # scaffold and pin default_env (validates env exists)
fused project list                       # registered projects (name + path + exists flags)
fused project show [NAME]                # the context packet (same as get_project_context)
fused project set NAME --description "new words" --env prod   # update the manifest's [project] keys
fused project set NAME --clear-env       # remove default_env from the manifest
fused project serve --mcp --project NAME # serve ONE project as a READ-ONLY stdio MCP (the product tier)
```

> **`project use` was removed (ITEM-11816).** Select a project with one of:
> - `export OPENFUSED_PROJECT=NAME` — persists across commands in the shell
> - `cd` into the project directory — cwd walk-up resolves automatically
> - `--project NAME` per individual tool/CLI call

`set` updates the `[project]` table of a registered project's `openfused.toml`
(at least one of `--description` / `--env` / `--clear-env` required; `--env`
and `--clear-env` are mutually exclusive). Edits are style-preserving —
comments, formatting, and unknown keys/tables in the manifest survive — and it
prints the updated `{name, description, default_env}` as JSON.

`create` scaffolds the standard layout: `openfused.toml`, a `SKILL.md` contract,
and the `scripts/`, `widgets/`, `references/`, `assets/` convention directories
(each with a README stating its purpose; `scripts/` also contains `pyproject.toml`
and `tests/`). Each UDF lives as a folder `scripts/<name>/` with `main.py` (or
`main.json`) as the entrypoint and `spec.md` as its contract — UDFs anywhere else
are not listed or served. A project scopes:

- **environment** — the manifest's `default_env` is used when no `--env` /
  `OPENFUSED_ENV` override is given (explicit override always wins); with a single
  named environment and no project pin, the sole env is auto-selected;
- **widget workspace** — `widget open/push/watch/parley` default to the
  project's `widgets/` directory (explicit `--dir` wins);
- **audit** — every event is stamped with the project name; filter with
  `audit log --project NAME`.

Start agent work in a project with `fused project show` (or the
`get_project_context` MCP tool) — one call returns identity, the SKILL.md
contract, reference notes, widgets, UDF scripts, and the resolved environment.

### Serve a project as a read-only MCP (`project serve --mcp`)

`fused project serve --mcp [--project NAME]` publishes **one** project as the
**read-only external MCP product tier** — a queryable data
source any MCP client (Claude Desktop, a BI tool, another agent stack) can connect
to. The closed surface is:

- **`get_project_context`** — the orientation packet (a pure read);
- **one tool per published UDF** in `scripts/` (named by its stable node `udfName` —
  the file stem; params from the `@fused.udf` signature; calling it runs the UDF as
  a *cached query* against the project's `default_env` — never arbitrary code). When
  the project has a readable pipeline graph (`canvas.toml`, or the implicit floor
  derived from `{{ref}}`/`fused.load` scans), each UDF tool's description is enriched
  read-only with **upstream/downstream lineage** (`reads: …` / `feeds: …`) and the
  `{{ref}}` **argument names** that drive it. A missing/corrupt
  `canvas.toml` simply omits the annotation — it never breaks tool publishing;
- **`widget://` / `reference://` resources** — each saved widget (config + resolved
  data) and reference note, readable point-in-time.

```sh
fused project serve --mcp --project taxi-analysis   # read-only stdio MCP for one project
fused code serve ./taxi --mcp                       # equivalent: serve the project DIR read-only
```

`--mcp` is **required** (the only serve mode in Phase 2 — stdio-only). `--project`
is **authoritative** (wins the resolution chain); the process `cwd` is set to the
project root so the data plane resolves `default_env` and the convention
directories. `code serve <project-dir> --mcp` is the equivalent path (it serves the
project at that directory).

**It never registers a write tool.** This is the one hard difference from the bare
`fused` stdio server (run with no subcommand), which registers the full *gated*
RW surface (`upload_file`, `put_secret`, `cache_clear`, and the
`--enable-infra`/`--enable-destructive` tools). The read-only path is a **separate
registry** that never *constructs* those tools — they are unreachable, not merely
gated. It is the binary the app's "Serve as MCP" connect snippet bakes:
`<openfused-bin> project serve --mcp --project <name>`.

---

## Pipeline graph (`pipeline`)

The project's UDFs wired into a persisted, versioned graph — nodes, `{{ref}}`
edges, and a `canvas.toml` home. Both commands resolve the
project the same way as `project show` (explicit `--project` → `OPENFUSED_PROJECT`
→ `openfused.toml` walk-up) and emit the `Pipeline` JSON
(`{name, path, version, nodes, edges, viewport}`) to stdout. They are the seam the
flow UI reads/writes the canvas through; the graph is a **design-time
lens** and never enters the resolve loop.

```sh
fused pipeline graph                        # read the derived/persisted graph as JSON
fused pipeline graph --project taxi          # explicit project
fused pipeline graph --canvas pipelines/reporting/canvas.toml  # a named canvas
fused pipeline derive                        # "create canvas": write canvas.toml + emit reloaded graph
fused pipeline derive --project taxi          # explicit project
```

- **`graph`** reads the graph: it unions the **implicit** edges (widget→UDF from
  the shared `{{ref}}` SQL scanner, UDF→UDF from a static `fused.load(...)` scan)
  with any **explicit** `[canvas].edges` authored in `canvas.toml`. A **missing**
  `canvas.toml` still yields the derivable graph (the implicit-scan floor, `version`
  null); a **corrupt** `canvas.toml` surfaces as a CLI error (non-zero exit), never
  a crash.
- **`derive`** is the derive-and-persist write path: it runs
  the implicit scan, lays nodes out left-to-right by stage depth, and writes a
  `canvas.toml` at the project root (or `--canvas PATH`) capturing the derived nodes
  + edges as **explicit lineage** (whole-document atomic write). It then emits the
  **reloaded** graph, so `version` is the `sha256:<hex>` content hash of the file
  just written. The Python core is the only `canvas.toml` writer (the mutation
  boundary).

---

## Audit log (`audit`)

```sh
fused audit log                          # last 50 events
fused audit log --limit 100
fused audit log --status blocked         # blocked executions only
fused audit log --event-type execute_code --status warned
fused audit log --project taxi           # events recorded under one project
```

Events are read from the local SQLite audit store (`~/.openfused/audit.db`) — the same database the `get_audit_log` MCP tool reads, so they persist across server restarts. For durable cross-session/cross-instance history, configure an `audit_bucket` in the environment; the `get_audit_log` MCP tool then merges S3-stored events when given a date range.

---

## Secrets (`secrets`)

```sh
fused secrets put db-password "s3cr3t"       # create or update
fused secrets get db-password                # print value
fused secrets list                           # all secrets
fused secrets list --prefix db-             # filter by prefix
fused secrets delete db-password             # delete (prompts; --yes to skip)
```

`secrets delete` errors on a missing secret (`Secret '<name>' not found`). On
AWS the secret is **scheduled** for deletion with the default 30-day recovery
window, not force-deleted; on the local backend the name is removed from the
OS keychain map immediately. The MCP equivalent (`delete_secret`) requires the
server to run with `--enable-destructive`.

**Naming requirement for Lambda access**: the Lambda execution role can only read secrets whose name starts with the environment's function prefix (e.g. `openfused-`). Always prefix secret names with the function prefix when they need to be read from `execute_code`:

```sh
fused secrets put openfused-db-password "s3cr3t"   # readable from Lambda
fused secrets put db-password "s3cr3t"             # NOT readable from Lambda
```

Never pass secret values through `code run` inline code strings — retrieve them inside the execution using `openfused.get_secret("openfused-...")` (works on AWS and the local backend).

---

## Code execution (`code run`)

Runs Python code on the active backend (Lambda for AWS, a host-venv subprocess for local). Assign `result` to return a value.

```sh
# Inline code — requires -c/--code
fused code run -c "result = 1 + 1"

# From a file (auto-detected; --file flag is optional)
fused code run myanalysis.py

# From stdin
cat myanalysis.py | fused code run

# Pass local files into the execution context
fused code run myanalysis.py --input-file data.parquet --input-file config.json
```

pip requirements are configured per-environment via `env update -p`, not per-call. Set them once:

```sh
fused env update prod -p pandas -p duckdb
```

Output format:
- `stdout` is printed as-is
- `stderr` goes to stderr
- `result: <value>` is printed when `result` is set

**Keep the package set stable across calls.** On AWS, packages are baked into the container image — changing them means rerunning `fused infra build-image` (build + ECR push). On local, venvs are cached by a hash of the package set — changing it rebuilds the venv (seconds with uv).

**Caching (`cache_max_age` / `cache_refresh`) is not available via `code run`** — it is only exposed through the MCP `execute_code` tool. Use the MCP tool when you need result memoization.

`--monitor-interval` (CloudWatch poll seconds during a run) defaults to **10** on `code run`; the MCP `execute_code` tool defaults to **30**.

**Local backend — project venv (`--project` or `--project-dir`).** On a local environment, pass one of:

- `--project <name>` — workspace-registered project; venv must already exist (`uv sync`).
- `--project-dir <path>` — ad-hoc path to any directory containing `openfused.toml`; venv is materialised in place on first run via `uv sync` in `<dir>/scripts/`. Use this for skill-folder bundles (e.g. `~/.claude/skills/<project>`) without registering them in the workspace.

The two flags are **mutually exclusive**. Both are **local-only** — rejected with a clear error on AWS and Fused backends. Without either flag, local execution uses a bare stdlib-only venv (third-party imports fail).

```sh
# Workspace-registered project (venv must already exist)
fused code run myanalysis.py --project taxi-pipeline

# Ad-hoc path (venv materialised on first run via uv sync)
fused code run myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

---

## Security scan without execution (`code verify`)

Scans code and input files for security issues without running it. Packages configured in the resolved environment are scanned for CVEs. Exits 1 if any BLOCK-severity finding is produced.

```sh
# Scan a file
fused code verify myanalysis.py

# Inline scan
fused code verify -c "import subprocess; result = 1"

# Scan code + input files for PII and path traversal
fused code verify myanalysis.py --input-file data.csv

# Spec check — Claude reviews whether code matches description (requires an Anthropic
# API key: ANTHROPIC_API_KEY env var, or `fused secrets put anthropic-api-key ...`)
fused code verify myanalysis.py --spec "compute the mean of column A"

# Scan using a workspace project's deps
fused code verify myanalysis.py --project taxi-pipeline

# Scan using an ad-hoc project dir's deps (local-only; no backend execute)
fused code verify myanalysis.py --project-dir ~/.claude/skills/taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to scan |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--input-file PATH` | — | File to scan for path traversal and PII (repeatable) |
| `--spec TEXT` | — | Natural language description; triggers LLM spec-vs-code check |
| `--project NAME` | — | Scan this project's `pyproject.toml` deps for CVEs (local). Without it, the dep scan uses the AWS env image packages, or nothing on local. Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Scan using `<dir>/scripts/pyproject.toml` deps (local-only). Mutually exclusive with `--project`. |

The flat `<stem>.spec.md` sidecar auto-discovery and `--no-spec` flag are **removed**. Each UDF now carries one `spec.md` in its own folder. Pass `--spec` explicitly when verifying outside a UDF context.

See the **fused-projects** skill for the spec-first, agent-authored UDF flow.

---

## Test code in Lambda (`code test`)

Runs pytest tests against user code inside the same Lambda environment it will execute in. Returns per-test outcomes, line coverage, and branch coverage. Packages configured in the resolved environment are pre-installed. Exits 1 if any tests fail.

```sh
# Basic usage
fused code test mymodule.py --test-file test_mymodule.py

# With input files available on disk during test run
fused code test mymodule.py --test-file test_mymodule.py --input-file data.csv
```

The test file must import from `user_code`:
```python
from user_code import my_function

def test_basic():
    assert my_function(1) == 2
```

pytest and coverage are auto-installed to `/tmp` on first use when they are not baked into the container image (~30s; warm containers reuse `/tmp/_test_deps`).

**Local backend — `--project` or `--project-dir` is required.** On a local environment, `code test` requires one of these flags. pytest and coverage must be declared as dev dependencies in the project's pyproject.toml; they are not auto-installed in the project venv. Add them in one step with `fused project add-dep <project> pytest coverage --dev` (runs `uv add --dev` + `uv sync`, so the venv isn't left stale). A stale project venv is auto-reconciled on `code run`/`code test` before executing (set `OPENFUSED_NO_VENV_SYNC=1` to opt out).

```sh
# Workspace-registered project
fused code test mymodule.py --test-file test_mymodule.py --project taxi-pipeline

# Ad-hoc path (venv materialised in place on first run)
fused code test mymodule.py --test-file test_mymodule.py \
    --project-dir ~/.claude/skills/taxi-pipeline
```

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to test |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--test-file PATH` | required | Pytest file to run (must import from `user_code`) |
| `--input-file PATH` | — | File extracted to Lambda working directory (repeatable) |
| `--project NAME` | — | Project venv to use (required on local backend; rejected on AWS/Fused). Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Ad-hoc project dir venv (local-only; materialised on first run). Mutually exclusive with `--project`. |

---

## HTTP serving (`code serve`)

Serves Python code as a live HTTP endpoint (GET and POST) backed by the active compute backend (Lambda or a local host venv). Same source interface as `code run`, plus `--port` and `--host`.

```sh
# From a file → GET+POST /<stem>
fused code serve myudf.py --port 8000

# Inline code — requires -c/--code → GET+POST /run
fused code serve -c "result = 1 + 1"

# From stdin with custom route name → GET+POST /tiles
cat myudf.py | fused code serve --name tiles

# Override route name for a file → GET+POST /api
fused code serve myudf.py --name api --port 8000

# With static files available in every request's execution context
fused code serve myudf.py --input-file model.pkl --input-file config.json

# Bind publicly
fused code serve myudf.py --host 0.0.0.0 --port 8080

# Serve a project directory (multi-entrypoint).
# Folder-per-UDF layout (scripts/ present): each scripts/<name>/main.py → route /<name>.
#   JSON-kind UDFs (main.json) are excluded from HTTP routes.
# Flat layout (no scripts/): each top-level .py file → route /<stem>.
#   Excludes test_*.py / *_test.py / conftest.py / _*.py.
# In both modes, project-root _*.py files are shipped as shared resources.
# (A legacy root-level UDF-folder project must be migrated to scripts/ first —
#  `fused project migrate` — it is not served as-is.)
fused code serve ./my_project   # → GET+POST /daily, /stars, …

# Serve a project directory as the READ-ONLY MCP product tier (stdio, not HTTP)
fused code serve ./taxi --mcp   # equivalent to `project serve --mcp` for that project
```

`--name` is rejected with a directory (each file is its own route); the reserved
route `health` is refused. A single file, `-c`, or stdin is one route.

`--mcp` reframes a **project directory** `SRC` as the **read-only project MCP**
instead of an HTTP endpoint — exactly the surface of `project serve --mcp`
(`get_project_context` + one tool per UDF + `widget://`/`reference://`
resources, never a write tool; see "Serve a project as a read-only MCP" above). It
requires `SRC` to be a directory (not `-c`/stdin/`--file`) and is stdio-only
(`--port`/`--host` do not apply). The read-only registry is a *separate assembly*
from the bare `fused` server's gated RW surface.

`code serve` is the **local dev server only** — there is no `--deploy`: deployed
serving is share-only (`infra serve` provisions the plane, `share create` mints
each URL; see those sections).

**GET** — query params become `_params.json`:
```sh
curl "http://localhost:8000/myudf?lat=37.7&lon=-122.4"
```

**POST** — JSON body becomes `_params.json`:
```sh
curl -X POST http://localhost:8000/myudf -H "Content-Type: application/json" \
     -d '{"lat": 37.7, "lon": -122.4}'
```

Access params inside the execution context:
```python
import json
params = json.load(open("_params.json"))
lat = float(params.get("lat", 37.7))
result = {"lat": lat}
```

`result` is serialized as the JSON response body. Unhandled exceptions return `{"error": "<traceback>"}` with status 500. `GET /health` is always registered.

| Option | Default | Notes |
|---|---|---|
| `-c / --code CODE` | — | Inline code string to serve |
| `--file` | off | Force-treat SRC as a file path (auto-detected when SRC exists on disk) |
| `--name` | file stem or `run` | Override the route name |
| `--input-file PATH` | — | File included in every request's execution context (repeatable) |
| `--port` | `8000` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind (use `0.0.0.0` for public) |
| `--cache-max-age TTL` | `0s` | Cache route results for `TTL` (`s`/`m`/`h`/`d`); `0s` disables. On a hit the compute backend is not invoked; the body returns inline with `X-Openfused-Cache: hit; age=<s>` / `miss` |
| `--cache-allow-bypass` | off | Honour `Cache-Control: no-cache` to force a fresh execution and rewrite the entry |

### Deployed serving moved (`infra serve` + `share`)

`code serve --deploy`, `code serve --teardown`, and `code serve-list` **no longer
exist** (on any backend — the local background-process deploy is gone too).
Deployed serving is share-only:

- **`fused infra serve`** provisions the environment's serving plane (one
  HTTP API + one dispatcher Lambda) — see *Infrastructure* below;
- **`fused share create`** publishes an app and mints its URL with the access
  control you choose — see the `share` section below;
- **`fused share revoke`** / **`infra serve --rate-limit 0`** /
  **`infra serve --teardown`** take things down at the URL / plane level.

---

## Served URLs / share links (`share`)

The share-only URL model: `share create` is the **only**
URL-minting operation — it publishes an app (a `.py` file or a project directory)
as a content-addressed artifact in the env's cache bucket and writes the mount
record binding a token to it with the access control you choose. Publishing never
builds infrastructure; the serving plane that answers these URLs is provisioned
separately by `infra serve` (see Infrastructure). Requires an **AWS environment
with a `cache_bucket`**. Every lifecycle op is audited
(`share_create`/`share_revoke`/`share_recreate`/`share_repoint` in `audit log`).

```sh
# Authed mount (default: Login with Fused) — token auto-derived from the stem
# (my_file.py → /my-file); audience from --jwt-audience or the env's
# serve_auth.default_audience (required — errors without one)
fused share create my_file.py

# Public share link — mints a crypto-random opaque token (the token IS the
# credential; a guessable public URL is never produced by accident)
fused share create --public my_file.py

# Named public mount — deliberately guessable; requires the explicit --token
# (prints a warning)
fused share create --public --token acme-dash my_file.py

# Custom issuer (must be on the env's serve_auth.issuer_allowlist) / ACL
fused share create --jwt-issuer https://idp.acme.io/ --jwt-audience proj my_file.py
fused share create --acl-subject alice@acme.io --acl-group analysts my_file.py

# Allow a browser origin to call the mount (repeatable for multiple origins)
fused share create --public --cors-origin https://app.acme.io my_file.py

# Whole project directory (entrypoints discovered like `code serve <dir>`),
# or a single entrypoint of it; --not-after sets a hard expiry
fused share create ./project
fused share create ./project --entrypoint daily --not-after 2026-12-31T00:00:00Z

# Inspect (list shows YOUR mounts; --all for everyone's)
fused share list
fused share list --all
fused share show my-file

# Revoke — the record becomes a tombstone: the token stays reserved (no other
# principal can ever claim it) and the mount goes dark within the plane's
# mount-cache TTL; --confirm forces the strong flush (dispatcher recycle —
# no new invocation sees the old record)
fused share revoke my-file
fused share revoke my-file --confirm

# Recreate: a FRESH opaque token for the same target (default — right for a
# leaked link), or revive the SAME token in place (owner-only)
fused share recreate my-file
fused share recreate my-file --same-token

# Repoint: update an ACTIVE mount's target in place — URL/token UNCHANGED.
# Publishes new-code.py, bumps the mount's version, and emits share_repoint
# in the audit log. Auth flags update the gate; omit to keep the existing gate.
fused share repoint my-file new-code.py
fused share repoint my-file new-code.py --entrypoint daily
fused share repoint my-file new-code.py --public
fused share repoint my-file new-code.py --jwt-audience new-proj
# --confirm forces the strong flush so the change is visible immediately
# (without it the update is visible within the mount-cache TTL, typically ≤5 min)
fused share repoint my-file new-code.py --confirm
```

Key rules: token auto-generation is gate-aware (authed → stem-derived name,
public → crypto-random opaque; `--random-token` forces opaque on an authed
mount). Creation is **owner-bound** — only the principal that published an app
(the normalized STS caller ARN, or `OPENFUSED_CALLER_NAME` without AWS
credentials) may mint mounts of it, and revoke/recreate are owner-guarded the
same way. Re-running `share create` with identical content is an idempotent
republish. `recreate` requires the mount to be revoked first. `repoint`
requires the mount to be **active** — revive a tombstone first with
`recreate --same-token` before repointing it.

---

## Infrastructure (`infra`)

The `infra` commands work for the AWS and local backends; each command
dispatches by the resolved environment's backend (they are not supported on the
Fused backend).

### Plan / apply / teardown

```sh
fused infra plan        # dry run — exits 1 if changes needed
fused infra apply       # reconcile IAM role, Lambda functions to desired state
fused infra teardown    # delete all fused Lambdas + IAM role (prompts for confirmation)
fused infra teardown --yes   # skip prompt
```

`infra plan` is useful in CI: a non-zero exit code signals drift.

`infra teardown` does **not** delete S3 buckets or Secrets Manager secrets — it removes Lambda functions, the managed IAM role, and optionally the ECR repository.

### Local backend

For a `backend: "local"` environment, "infra" is the data/secrets/venvs
directories and the cached venv holding the env's `packages` (no cloud
resources):

```sh
fused infra plan          # reports missing dirs (exits 1 on drift)
fused infra apply         # create dirs (idempotent; bare venv is created lazily on first execute)
fused infra teardown      # remove the venvs dir + data dir (prompts); serve endpoints survive
fused infra lambda-reset  # clear the in-process venv ready-cache (nothing deleted from disk)
```

- `infra build-image` **errors** for local envs — there is no image; packages go
  into a cached venv, provisioned by `infra apply` (or lazily on first execute).

### The serving plane (`infra serve`)

Deployed serving's compute, managed like every other resource family. Provisions
one HTTP API (v2) + one dispatcher Lambda per environment; **mints no URLs** —
URLs come only from `share create`. Requires an AWS env with `cache_bucket`, and
Docker to build the dispatcher image (the fused package on the Lambda Python
base; `--image-uri` registers a pre-built image instead). Idempotent.

```sh
# Provision (or reconcile) the plane
fused infra serve

# Plane-wide rate limit; 0 = kill-switch (every mount answers 429, URLs stay
# stable; re-apply with N>0 to re-enable). Omitted = leave unchanged.
fused infra serve --rate-limit 50
fused infra serve --rate-limit 0

# Custom domain (every mount is hosted under it by path)
fused infra serve --domain api.example.com --cert-arn arn:aws:acm:...

# Remove the plane: every mount goes dark; mount records + published apps
# persist until `infra teardown`. Prompts unless --yes; takes no other options.
fused infra serve --teardown --yes
```

`infra teardown` also sweeps the plane (the `{prefix}serve` API, the dispatcher
Lambda, the serve ECR repo) along with everything else.

### Container image

AWS Lambda execution is **container-only**: the ECR image built here is the function's code (one `{prefix}container` function per env). There is no fallback — until an image is configured, `execute_code` fails with an error telling you to run `infra build-image`. Bake the packages you need into the image; per-call pip installs do not happen.

**Step 1 — configure the image in the environment** (one-time or when packages change):

```sh
fused env update prod \
  -p pandas -p pyarrow -p duckdb \
  --python-version 3.12
```

**Step 2 — build and push** (run again whenever you want to rebuild):

```sh
fused infra build-image
```

| Option | Default | Notes |
|---|---|---|
| `--image-uri` | — | Skip build; register a pre-built image |
| `--push / --no-push` | push | Push to ECR after build |
| `--builder` | env's `builder` (`codebuild`) | `codebuild` (default; remote AWS CodeBuild, no local Docker) or `local` (docker build on host) |

Build parameters (`-p/--package`, `--system-dep`, `--python-version`, `--image-platform`, `--image-repo`, `--image-tag`, `--builder`, `--dockerfile`, `--context-dir`) live in the environment config and are set via `env create` or `env update`. `infra build-image` reads them automatically.

After a successful build and push, the image is resolved to its digest URI (`…@sha256:…`) and stored in the resolved environment's `docker_image` field. Using the digest rather than the mutable tag (`:latest`) means `infra plan` can detect when a new image has been built and flag the Lambda function for update.

**CodeBuild is the default (no local Docker).** `infra build-image` builds remotely in AWS CodeBuild by default — no Docker daemon needed on your machine — using the env's cache bucket (the build source is uploaded there). Pass `--builder local` to build with the host Docker daemon instead. CodeBuild also accepts a user-supplied build context:

```sh
fused infra build-image                               # builds in CodeBuild (default); streams logs
fused env update prod --context-dir ./img --dockerfile Prod.Dockerfile  # your own Dockerfile + context
fused infra build-image --builder local -p duckdb    # opt into a host docker build
```

CodeBuild builds in your own AWS account and pushes via a service role whose ECR push is scoped to just the env's repo. `infra apply` also uses CodeBuild when the env's `builder` is `codebuild` (the default). `infra teardown` removes the CodeBuild project and its role. With no cache bucket configured (a deliberate `--no-cache-bucket`), the CodeBuild build fails fast with guidance to set one or pass `--builder local`. Limitation: concurrent builds sharing the same image tag aren't supported (the digest is resolved by the mutable tag).

---

## Widgets (`widget`)

JSON-UI widgets are rendered and served through the `widget` group. A widget is a `{type, props, children}` config; data-bound nodes carry DuckDB `sql` with `{{udf}}` refs that resolve through the resolved environment's compute backend.

### Widget component catalog (the supported `type` set)

Author a widget as a JSON tree of `{type, props, children?}` nodes (the root is usually a `div`; **every** prop goes under `props`). A node whose `type` is outside the supported set is rejected ("unknown component …") — so only use these:

- **Containers** (take `children`): `div`, `form`, `sql-runner`
- **Inputs** (write a `param`): `text-input`, `text-area`, `number-input`, `datetime-input`, `color-input`, `camera-input`, `file-upload`, `gallery-input`, `dropdown`, `slider`, `button`
- **Display**: `text`, `metric`, `image`, `html`, `iframe`, `video`, `video-review`
- **Charts** (data-bound `sql` → fixed columns): `bar-chart`, `line-chart`, `stacked-area-chart`, `stacked-bar-chart`, `scatter-chart`, `donut-chart`, `heatmap-chart`
- **Table**: `sql-table` · **Layout**: `canvas`
- **Maps**: `map`, `map-bounds`, `fused-map`

Full prop schemas live in the **fused-widgets** skill's component catalog. **Not implemented — do not author**: `map-h3`, `kepler-map`, `code-editor`, `transformer`, `ai-chat`, `widget-builder`, `pdf-gallery-viewer`. `html` does **not** substitute `{{udf}}`/`$param` (it reads `value` verbatim) — for data on a map, use a map widget, not an HTML/Leaflet hack.

### Maps — authoring contracts (read before authoring any map)

Fused maps render with **MapLibre + deck.gl and NO Mapbox token** (open basemap tiles); geometry comes from SQL. They render in the **native app / `widget open` / parley** only — the deployed-serve bundle shows a placeholder.

- **`map`** — deck.gl, **UDF-layer-bound**: `props.layers: [{udf, visible?, vizConfig?}]` (no flat `sql`). Each `udf` is a UDF (or a `sql-runner` name) returning a **geometry column** of GeoJSON strings (e.g. `'{"type":"Point","coordinates":[' || lng || ',' || lat || ']}' AS geometry`), or set `vizConfig.latColumn`/`lngColumn`. `vizConfig` (FLAT): `geometryColumn`, static `fillColor`/`lineColor`/`pointRadius`/`opacity`, or data-driven `radiusColumn`+`radiusRange` and `colorColumn`+`colorRange`. Plus `mapStyle` (dark/light/satellite/blank), `centerLng`/`centerLat`/`zoom`, `param`+`sendParam`.
- **`fused-map`** — deck.gl **multi-layer**: `props.layers: [{id, type, sql, ...}]`, `type` ∈ `scatterplot`/`geojson`/`deck-geojson`/`h3`/`heatmap`/`arc`/`mvt`/`raster`. Each layer carries its own `sql`; point layers use `latColumn`/`lngColumn`, `geojson` uses `geometryColumn`, `h3` uses `h3Column` (valid H3 indexes), `arc` needs `sourceLng/sourceLat/targetLng/targetLat` columns, `mvt`/`raster` use `tileUrl`. `style.fillColor`/`lineColor` are `[r,g,b]` / CSS / **data-driven** `{type:"continuous"|"categorical", attr, domain, palette}`. Palettes: Sunset, Viridis, Magma, Plasma, Teal, BluYl, Purp, OrYel, Mint. Plus `tooltip` (bool|string[]), `legend`, `showLegend`/`showLayerPanel`/`showBasemapSwitcher`/`showControls`/`showScale`, `basemap`, `param`+`autoSend`.
- **`map-bounds`** — viewport picker, no data input. Writes bounds to `param` as a **`"west,south,east,north"` string**.
- **Bounds in SQL** — the bounds param is a STRING, never an array. Filter with `split_part`/`try_cast`, guarded for the empty (pre-send) value:
  `where '$bbox' = '' OR (lng between try_cast(split_part('$bbox',',',1) as double) and try_cast(split_part('$bbox',',',3) as double) and lat between try_cast(split_part('$bbox',',',2) as double) and try_cast(split_part('$bbox',',',4) as double))`

### The widget-host (the standalone viewer)

The `widget open`/`push`/`watch`/`parley` commands are served by the
**widget-host** — a small standalone terminal app (its own Express server + a
chromeless client SPA), a sibling of the separate flow UI, not part of
it. (This **supersedes** the prior "fold" model, where these commands ran inside
the flow app's Express process behind an `appProtocol` handshake; the standalone
viewer + parley now live in their own host.) You **do not** start it yourself: each widget
command **boots-or-reuses** the widget-host transparently.

- **Own port, no state file.** The widget-host binds a fixed loopback port (default
  **4410**, distinct from the flow UI's port; override with `OPENFUSED_WIDGET_HOST_PORT`).
  Discovery is a **fixed-port `GET /health` probe** — there is no
  `~/.openfused/widget-servers/` state file. The CLI reuses an already-listening
  widget-host (and only when its bundle version matches — a stale or foreign process
  on the port surfaces a clear "restart the widget-host" error); otherwise it spawns
  one (detached, surviving the CLI invocation) and proceeds.
- **Project-ignorant.** Project targets (`widget open {project,stem}`, project parley
  pushes) are **delegated to `fused dev serve`'s `?workspace=&project=`
  addressing** — the Python side resolves the project and hot-reads its config. The
  widget-host owns no projects registry; it just views one widget config (+ its
  sibling UDFs) and streams feedback back.
- **Own `dev serve` child.** The widget-host spawns its **own** headless `fused
  dev serve` daemon (separate from the one the flow app spawns) and resolves
  all widget data through it. `dev serve` resolution is per-request/stateless, so two
  daemons is correct — no shared-daemon coupling, no stale-backend bug. A data-bound
  widget requires a resolved environment with a compute backend (`local` resolves
  queries in a host venv; `aws` in Lambda); env resolution follows the standard rules
  (`OPENFUSED_ENV` → project's `default_env` → sole-env auto) and is per request, so an
  env change needs no restart.

Omitted, the `--dir` on `open`/`push`/`watch`/`parley` defaults to the resolved
project's `widgets/` directory (created when absent), else the
current directory; an explicit directory always wins.

### Open a widget with a feedback loop (`widget open`)

Opens a widget in the browser and **blocks until the session settles** — the tab closing, or the user pressing a `submit` button — then prints the final canvas `$param` values (and the terminal action's name) to stdout as one JSON line — the agent's feedback channel (the user dials in values, presses a button or closes the tab, the agent reads them).

```sh
fused widget open sales_overview                  # a saved widget (stem of ./sales_overview.json)
fused widget open ./draft.json --title "Draft"    # any config file → temporary /_tmp/<id> path
fused widget open sales_overview --timeout 0      # wait forever
fused widget open sales_overview --stream         # NDJSON: every event as it happens
```

| Option | Default | Notes |
|---|---|---|
| `--project NAME` | — | Project owning a saved-widget stem TARGET (default: resolved project). Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Pin the resolve daemon to a project directory (`.json` targets only). Drives `fused dev serve`'s `?projectDir=<PATH>` mode (UDFs from `<PATH>/scripts/`, run under `<PATH>/scripts/.venv`) so the project's UDFs and `.venv` are available. Mutually exclusive with `--project`. |
| `--title TEXT` | — | Title for a local-file widget |
| `--timeout` | `600` | Give up after N seconds without a terminal event; `0` = wait forever |
| `--open / --no-open` | `--open` | `--no-open` prints the URL to stderr and still blocks |
| `--stream` | off | Emit every session event as it happens (NDJSON) instead of one final line |

Default-mode stdout/exit contract:

| Outcome | stdout (one JSON line) | Exit |
|---|---|---|
| terminal event (tab close, or a `submit` button) | `{"action":"<closed\|name>","params":{"days":10,…}[,"actions":[…]]}` — `actions` lists non-terminal button presses (`{action,params,seq,ts}`), present only when non-empty | `0` |
| timeout | `{"action":"timeout"}` | `3` |
| Ctrl-C | `{"action":"interrupted"}` | `130` |
| other failure | none (message on stderr) | `1` |

`--stream` mode emits NDJSON, one JSON object per line, flushed per line — every non-terminal event as it arrives, then a final `end` line with the same action vocabulary and exit codes:

```
{"event":"params","seq":1,"params":{"days":60}}
{"event":"action","seq":2,"action":"flag","params":{"days":60}}
{"event":"end","action":"<closed|name|timeout|interrupted>","params":{…}}
```

A page **refresh counts as a close** (the browser fires the same event); a crashed browser sends nothing and the command ends at the timeout.

**Driving it from an agent (open optimistically, poll — never blind-`sleep`).** Because the command blocks until the human settles, an agent that needs the URL should start it with `run_in_background` and read the URL off **stderr** — it prints as a `widget page: <url>` line there (stdout is reserved for the final terminal-event JSON), so `Monitor` stderr for `widget page:` until it appears with a timeout ceiling — do **not** `sleep N; cat`. Run `fused widget verify` **concurrently** rather than serialising verify → open; the open is optimistic and the headless check gates the data in parallel. See `fused-widgets` → *Optimistic open + background verify* for the full rationale.

### The parley — a standing channel (`widget push` / `widget watch` / `widget parley` / `widget agent`)

Unlike a session (one-shot: tab closes, command exits), the **parley** never settles: the agent pushes successive views into one persistent page at `<origin>/parley`, and the human's events stream on a standing log. One parley per widget-host, in-memory. Like `open`, the commands boot-or-reuse the widget-host (no separate server to start).

```sh
fused widget push sales_overview        # push a saved widget into the parley page
fused widget push ./draft.json --title "Draft"   # any config file works too
fused widget push ./dash.json --project-dir ~/.openfused/workspaces/default/cc-open   # scripts/-backed + editable
fused widget push -c "$CONFIG" --source /abs/plan.json   # inline config, but anchor edits at a file
fused widget watch                      # stream the human's actions (NDJSON, runs until stopped)
fused widget watch --verbose            # ...also every per-input params change (noisy)
fused widget parley                     # print/open the parley page URL
fused widget agent                      # action comments the human pins on the page (needs `claude` on PATH)
```

**Agent workflow**: run `widget watch` as a **background process** for the life of the collaboration, then `widget push` once per view — react to what streams in, push the next view, repeat. The open tab re-renders in place on every push (params reset to the new config's defaults).

By default `watch` emits only **`action`** and **`close`** events — the low-volume signals you act on. The page also reports a debounced `params` event on every input change (a note typed, a slider dragged); those are suppressed unless you pass `--verbose`. A terminal `action` always carries the full `params` snapshot, so you get state on every decision without the keystroke noise. Reach for `--verbose` only when you want to react *while* the human explores (e.g. drill-down) rather than on their submit.

| Command | Key options | stdout | Exit |
|---|---|---|---|
| `widget push TARGET` | `-c/--config` (inline; `-` = stdin), `--source PATH` (with `--config`: the file the config came from → the edit anchor), `--project`, `--project-dir PATH` (`.json`/`--config` only; keeps the view file-backed → editable), `--title`, `--open/--no-open` (default `--open`: opens the parley page only when no tab is watching — `viewers == 0`) | exactly one line `{"rev":N,"viewers":M}` | `0`; failures: stderr only, `1` |
| `widget watch` | `--dir .`, `--from latest\|all\|<seq>` (default `latest`), `--timeout 0` (= forever), `--verbose` (also emit `params`; default off) | NDJSON per event: `{"event":"action"\|"close"\|"params","seq":N,"rev":R[,"action"][,"terminal"],"params":{…}}`; final `{"event":"end","reason":"interrupted"\|"timeout"}` | Ctrl-C `130`, timeout `3`, server lost `1` (no end line) |
| `widget parley` | `--dir .`, `--no-open` | none (URL on stderr) | `0` |
| `widget agent` | `--port`, `--model <m>` | logs on stderr; foreground until Ctrl-C | `0` |

A `close` event is a presence signal, not an ending — the human left the tab; the parley continues; reopening the page resumes reporting.

**`--project-dir` on `push` (feedback-mode entry point).** Path-address a `.json`/`--config` push against a project directory (local backend only, mutually exclusive with `--project`): the push resolves via `fused dev serve`'s `?projectDir=` mode (UDFs from `<PATH>/scripts/`, run under its `.venv`) **while the view stays file-backed** — so a widget whose data comes from a project's `scripts/` UDFs (endpoint refs like `{{session_cost}}`) resolves *and* keeps the parley comment loop live. It is the **only** push form that is both project-addressed and editable: a `{project, stem}` push resolves but is not file-backed, and a bare `--config --project-dir` (no `--source`) resolves the same way but stays one-shot/non-editable. Only valid for `.json`/`--config` targets (a saved-widget stem errors).

**`widget agent` + the CLI-native comment loop.** With a file-backed view pushed (a `.json` path, `--config --source PATH`, or a `--project-dir` push), the parley page mounts the widget's **comment layer** — no flow app needed. The human enters comment mode (bottom-right comment FAB or the `C` key), pins a comment to a node, and it rides the existing debounced `params` reporter as the `__comments` param (no new transport). `fused widget agent` consumes those off `GET /api/parley/events` — the **live** stream, so start it *before* the human comments (it does not replay comments pinned while it wasn't running). It spawns a `claude -p` worker per open comment (parallel across disjoint nodes, serialized on the same/nested node), applies the resulting patch to the source config as its single writer, and re-pushes — marking each comment in-progress → resolved. It reads `status.projectDir` and **echoes it on every re-push**, so a `--project-dir` view keeps resolving in `?projectDir=` mode across agent updates. Editability gate: on a non-file-backed view (`status.source == null` — a plain inline `--config` or `{project, stem}` push) the page shows a short "not file-backed, comments won't be actioned" note and suppresses authoring (it still renders the widget). See `fused-feedback` → *CLI-native comment feedback* for the two-terminal loop.

### Verify a widget resolves, headless (`widget verify`)

The CI/agent counterpart of `open`/`push`/`watch`: resolves a widget **in one shot** and prints its data envelope to stdout — no browser, no session, no daemon, no port, nothing left running. It answers one question — *does this config resolve, and to what data?* — and exits. It reuses the same `POST /api/exec/widget` resolution path in-process, so a `verify` result faithfully predicts what `open` would render.

Use it instead of hand-driving `fused dev serve` (the old spawn → read-handshake → POST → parse → kill dance) whenever you just need to confirm a widget resolves before showing a human.

```sh
fused widget verify session_cost --project cc-open   # a saved-widget stem
fused widget verify ./draft.json                     # a .json config file
fused widget verify ./draft.json --project-dir ~/.openfused/workspaces/default/cc-open
cat draft.json | fused widget verify --config -      # inline config from stdin
fused widget verify sales_overview --params '{"region":"emea"}' --cache-refresh
```

`TARGET` mirrors `widget open` — exactly one of a saved-widget stem, a `.json` config file, or an inline `-c/--config` (`--config -` reads stdin); a stem needs `--project` (or a resolved ambient project). `--config` and `TARGET` are mutually exclusive.

| Option | Default | Notes |
|---|---|---|
| `-c/--config TEXT` | — | Inline JSON config instead of a TARGET; `-` reads stdin. Mutually exclusive with TARGET. |
| `--project NAME` | — | Project owning a saved-widget stem TARGET (default: resolved project). Mutually exclusive with `--project-dir`. |
| `--project-dir PATH` | — | Pin resolution to a project dir (local backend only). **Only valid for `.json`/`--config` targets** (not a stem), drives `fused dev serve`'s `?projectDir=` mode (UDFs from `<PATH>/scripts/`, run under `<PATH>/scripts/.venv`). Mutually exclusive with `--project`. |
| `--params JSON` | — | JSON object of `$param` values to bind before resolving (the values a browser would post on interaction). |
| `--cache-refresh` | off | Ignore cached UDF results — force a fresh run. |
| `--cache-max-age AGE` | engine `1h` | Max cached-result age (e.g. `0s`, `1h`). |

**Addressing** follows `widget open`: a `.json`/`--config` target with neither flag resolves **project-less** via `?dir=` mode, rooted at the `.json` file's own directory (its cwd for an inline `--config`), so `{{ref}}`s to sibling `<dir>/udfs/*.py` resolve — but sibling flat `*.py` are *not* auto-injected (deferred), so a widget depending on inline sibling bodies rather than `<dir>/udfs/` may under-resolve. For a real project widget (a `{{ref}}` elsewhere in `scripts/`, or a `{{_core.*}}` ref), pass `--project` (stem) or `--project-dir` (`.json`).

stdout / exit-code contract:

| Outcome | stdout | Exit |
|---|---|---|
| Resolved (incl. per-query failures) | `{"data":{…},"errors":{…},"depMap":{…},"config":{…},"warnings":[…]}` | `0` |
| Hard failure — bad/missing input, unknown/unresolvable widget, ambiguous env, resolver crash | *no stdout JSON* — message on stderr | non-zero |

**Per-query failures are in-band, not fatal** — a widget whose queries partially fail still resolves and exits `0`, with the failing query IDs under `errors` (empty `{}` when all succeed). This mirrors the render envelope: a partial resolve is a normal, inspectable outcome. Only a *hard* failure (the config never resolves at all) exits non-zero. So the success gate is **`errors` empty and `data` populated** — a zero-row `{{ref}}` is still a success (empty result, clean empty widget), not an error.

**`warnings` is a best-effort advisory, never fatal** — `[{"type","props":[…]}, …]` (empty `[]` when clean) flagging config props the server catalog doesn't recognize (a typo'd or unsupported prop name). It comes from the shared resolve path, so `open`/`push`/`watch` carry it too; it is strictly additive and **never changes the exit code**. It catches catalog-unknown props but not version skew — a prop the server knows that a stale browser bundle doesn't still resolves clean and warns nothing, so it's not a substitute for checking a new prop on the real renderer.

```sh
fused widget verify session_cost --project cc-open
# exit 0, errors {}, 7 queries resolved
```

### Headless resolve daemon (`fused dev serve`)

`fused dev serve` is the **single widget-data serving daemon** — it executes
UDFs, resolves SQL, and resolves widget configs for any project in any workspace.
The flow app spawns it and manages its lifecycle; it is not a user-facing
command in normal use. (The former per-project `widget data-serve` command and its
`POST /api/widget-data` route were removed; `dev serve` is the one daemon now.)

Routes (all token-gated): `POST /api/exec/widget` (full config plan + resolve —
replaces the old `POST /api/widget-data`), `POST /api/exec/sql`, `POST /api/exec/udf`,
and `GET /health`. Prints one JSON handshake line (`{"origin","port","token","pid"}`)
to stdout, then runs until `--timeout`/SIGTERM.

The dev serve command itself is documented below.

---

## `dev` — multi-tenant execution layer

`fused dev serve` starts a single long-running loopback HTTP server that
executes UDFs, resolves SQL, and resolves widget configs for any project in any
workspace, without pinning a project or environment at startup.  It is the one
widget-data serving daemon (no separate per-project daemon exists).

```sh
fused dev serve                              # ephemeral port, runs until stopped
fused dev serve --host 127.0.0.1 --port 9100
fused dev serve --timeout 300               # auto-stop after 5 minutes
```

**Handshake** — exactly one JSON line on stdout before serving:

```json
{"origin": "http://127.0.0.1:<port>", "port": <port>, "token": "<token>", "pid": <pid>}
```

**Addressing is via query params alongside `?t=<token>`** — so the request **body
carries only the payload**.  Three addressing modes:

- `?workspace=<ws>&project=<proj>` — the app project-resolution path (UDFs from the
  registered project's `scripts/`). `workspace`/`project` are path-safety validated
  (a missing value, or one with `/`, `\`, `..`, or a bare `.`, → 400).
- `?dir=<abs>` — flat directory mode: `udfs_dir = <dir>/udfs`, with sibling `*.py`
  passed as inline `sources`. Used by `widget open <file>` and the parley path/config
  pushes.
- `?projectDir=<abs>` — skill-folder mode: `udfs_dir = <dir>/scripts`, UDFs run under
  `<dir>/scripts/.venv`. Used by `widget open --project-dir`.

Both directory modes inject the built-in `_core` shared root so `{{_core.proj.udf}}`
refs resolve.

**Endpoints** (all POST endpoints require `?t=<token>`):

| Endpoint | Body (payload only) | Description |
|---|---|---|
| `GET /health` | — | Liveness probe — no token required |
| `POST /api/exec/udf` | `udf`, `overrides?` | Run a named UDF in `scripts/` |
| `POST /api/exec/sql` | `sql`, `params?` | Resolve ad-hoc DuckDB SQL |
| `POST /api/exec/widget` | `config`, `params?`, `only?`, `sources?`, `cache_max_age?`, `cache_refresh?` | Resolve a full widget config → `{data, errors, depMap, config}` (the render-surface seam) |

Each request resolves its own project directory and environment from the project's
`openfused.toml`.  No project or env is pinned at startup; picking up env changes
requires no server restart.

`"_core"` is an addressable built-in workspace backed by the packaged wheel source
(read-only).  Example: `{"workspace":"_core","project":"task-management","udf":"read"}`
executes the built-in task-management read UDF without needing a user workspace.

| Option | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `0` | Port; `0` = ephemeral (reported in handshake) |
| `--timeout SECONDS` | `0` | Auto-shutdown; `0` = run until stopped |

The CLI starts the server; it is not a client.

---

## Common patterns

### First-time AWS setup

```sh
fused env create prod --backend aws --prefix myapp- -p pandas
# Provisions IAM role + cache bucket
fused infra build-image   # build + push the Lambda container image (required before execution)
fused infra apply         # creates the {prefix}container Lambda from the image
fused infra plan          # verify no further drift
```

### Targeting a specific environment for a single command

```sh
fused --env staging secrets list   # uses staging for this command only
```

### CI drift check

```sh
fused infra plan || echo "Infrastructure out of sync — run apply"
```

### Inspecting a dataset before running expensive code

```sh
fused files schema --bucket my-bucket --key data/large.parquet
fused files count --bucket my-bucket --prefix data/ --ext .parquet
```

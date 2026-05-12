---
name: fused-cli
description: Reference for the Fused Python SDK command line interface (`fused`). Use when the user asks how to run, push, share, or otherwise manage UDFs, canvases, files, or secrets via the Fused CLI, or when authoring shell commands that invoke `fused`.
---

# Fused CLI

Invoke via `uv run fused` in this repo. Global flags:

- `--env TEXT` (env: `FUSED_ENV`)
- `--format [json|text]` (env: `FUSED_CLI_FORMAT`) — set to `json` for machine-readable output

## Top-level commands

| Command      | Purpose |
| ---          | --- |
| `canvas`     | Manage canvases |
| `completion` | Print or install shell tab completion |
| `files`      | Manage files stored in Fused |
| `login`      | Authenticate and persist credentials |
| `logout`     | Clear local credentials |
| `run`        | Run a UDF and print the result |
| `secrets`    | Manage kernel and user secrets |
| `whoami`     | Show info about the authenticated user |

## `fused canvas`

Most canvas subcommands take a `CANVAS_REF` (name or ID) plus:
- `--id` — treat the ref as a canvas ID rather than a name
- `--team` (where supported) — treat the name as a team canvas name

| Subcommand | Args / notable options |
| --- | --- |
| `create NAME` | Create a new canvas |
| `delete CANVAS_REF` | `--id` |
| `export CANVAS_REF` | `--output FILE` (required), `--team`, `--id` — downloads a zip bundle |
| `list [CANVAS_REF]` | `--team`, `--id` — lists all, or shows one |
| `pull CANVAS_REF` | `-o/--output DIR`, `--team`, `--id`, `-f/--force`, `-n/--dry-run` — same as `export` then extracts; prompts per file on conflict unless `--force` |
| `push SOURCE_DIR` | `--canvas TEXT` (defaults to dir name), `--id`. Replaces remote UDF list — UDFs missing locally are removed |
| `rename CANVAS_REF NEW_NAME` | `--id` |
| `share CANVAS_REF` | `--client-id TEXT`, `--new-token`, `--id` |
| `unshare CANVAS_REF` | `--id` |

## `fused files`

| Subcommand | Args / notable options |
| --- | --- |
| `delete PATH` | `--max-deletion-depth TEXT` (integer or `"unlimited"`) |
| `download PATH LOCAL_PATH` | `-r/--recursive`, `--dry-run` (with `-r`) |
| `get PATH` | Prints file contents to stdout |
| `list PATH` | `--details`, `-r/--recursive` |
| `sign_url PATH` | Returns a signed URL |
| `upload LOCAL_PATH REMOTE_PATH` | `--timeout FLOAT`, `-r/--recursive`, `--dry-run` (with `-r`) |

## `fused secrets`

User secrets are read-only — `--user` is only valid on `get` and `list`.

| Subcommand | Args / notable options |
| --- | --- |
| `delete KEY` | `--client-id TEXT` |
| `get KEY` | `--user`, `--client-id TEXT` |
| `list` | `--user`, `--client-id TEXT` |
| `set KEY VALUE` | `--client-id TEXT` |

## `fused run CANVAS UDF`

Runs a UDF and prints the result. The `UDF` argument is passed to `fused.load`, which accepts:

- Fused identifier: `user@example.com/my_udf` or `my_udf` (resolved against `CANVAS` as the collection)
- Local Python file: `udf.py` or any `.py` path
- GitHub tree/blob URL: `https://github.com/org/repo/tree/...` or `.../blob/...`
- Inline UDF source: a string containing at least one newline is treated as Python module text

Options:

- `--engine [remote|local]`
- `--instance-type TEXT` — remote instance type override
- `--max-retry INTEGER`
- `--cache-max-age TEXT` — e.g. `10s`, `5m`, `1h`
- `--cache / --no-cache`
- `--disk-size-gb INTEGER`
- `--stdin` — read UDF source from stdin instead of passing `UDF` (do not pass `UDF` with `--stdin`)
- `--verbose / --no-verbose` — show UDF stdout/stderr (default on)

Additionally, `fused run` accepts **arbitrary keyword args matching the UDF's signature**, e.g. `--abc=123` is forwarded as the `abc` parameter to the UDF. These pass-through args are not listed in `--help`.

## Tips

- Always prefix with `uv run` in this project so the right environment is used.
- For machine-readable output in scripts, pass `--format json`.
- Run `uv run fused <command> --help` to confirm flags before scripting — this reference may lag the CLI.
- When appropriate, give the user the URL to the created canvas so they can open it in their browser and see the result.

---
name: fused-cli
description: Reference for the Fused Python SDK command line interface (`fused`). Use when the user asks how to run, push, share, or otherwise manage UDFs, canvases, files, or secrets via the Fused CLI, or when authoring shell commands that invoke `fused`.
---

# Fused CLI

## Finding the CLI

`fused` is installed as part of the `fused` Python package. The CLI ships in `fused>=2`, which requires **Python 3.10 or newer** — on Python 3.9 `pip install fused` falls back to a 1.x release that has no `fused` entry point. If `fused` is not on `PATH`, locate or install it before running any commands:

1. **Check PATH first:** `which fused` — if found, use it directly.
2. **No virtual environment detected? Use uvx (recommended):** `uvx fused` — runs the latest version without installation and selects a compatible Python automatically, so it works even when the system Python is 3.9.
3. **Project venv:** if the project uses a `.venv`, run `uv run fused` or `.venv/bin/fused`. Confirm the venv is Python 3.10+ (`.venv/bin/python --version`); if it's 3.9, recreate it with `uv venv --python 3.11 .venv` before installing.
4. **Conda env:** the binary may live inside a conda environment (`~/miniforge3/envs/<env>/bin/fused`). Activate the env or call the full path. If the env is on Python 3.9, create a new one with `conda create -n fused python=3.11`.
5. **Fresh install (when uvx isn't available):**
   ```bash
   uv venv --python 3.11 ~/.fused-cli-env
   uv pip install 'fused>=2' --python ~/.fused-cli-env/bin/python
   # then call ~/.fused-cli-env/bin/fused
   ```
   Pinning `--python 3.11` and `'fused>=2'` avoids the silent 1.x fallback. Save the full path for future use so the same env is reused.

Always confirm the CLI is working with `fused whoami` before proceeding. If `fused: command not found` appears right after a `pip install fused`, check `python --version` — Python 3.9 or older is the most common cause and is fixed by switching to `uvx` or installing into a 3.10+ environment.

### Windows

On Windows the same rules apply, with a few differences:

- **Check PATH:** use `where fused` (not `which`) in cmd/PowerShell.
- **Python Launcher:** Windows ships a `py` launcher — use `py --version` to check the active version and `py -3.11 -m pip install "fused>=2"` to target a specific version.
- **`fused` not found after `pip install`:** the Scripts directory (`%APPDATA%\Python\Python3XX\Scripts\` or `%LocalAppData%\Programs\Python\Python3XX\Scripts\`) is often not on PATH. Run `python -m site --user-scripts` to print the exact path, then add it to PATH (search "environment variables" in the Start menu → edit the `Path` user variable) and open a new terminal.
- **Install `uv` on Windows (if not present):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Restart the terminal after installing, then use `uvx fused` as usual.

## Global flags

- `--env TEXT` (env: `FUSED_ENV`)
- `--format [json|text]` (env: `FUSED_CLI_FORMAT`) — set to `json` for machine-readable output

## Top-level commands

| Command        | Purpose |
| ---            | --- |
| `canvas`       | Manage canvases |
| `claude`       | Manage the Fused plugin for Claude Code |
| `completion`   | Print or install shell tab completion |
| `files`        | Manage files stored in Fused |
| `integrations` | Manage third-party integration OAuth and tokens |
| `json-ui`      | Inspect JSON-UI component schemas |
| `login`        | Authenticate and persist credentials |
| `logout`       | Clear local credentials |
| `run`          | Run a UDF and print the result |
| `secrets`      | Manage kernel and user secrets |
| `udf-schema`   | Print the API schema for a UDF |
| `whoami`       | Show info about the authenticated user (`--team` for the team) |

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
| `pull CANVAS_REF` | `-o/--output DIR`, `--team`, `--id`, `-f/--force`, `-n/--dry-run`, `--show-diff` — same as `export` then extracts; prompts per file on conflict unless `--force`. Pass `--show-diff` (recommended when invoked by an AI assistant) to print a unified diff for every file write or removal so you can summarize the change set back to the user. The changes will be applied with `--show-diff`. |
| `push SOURCE_DIR` | `--canvas TEXT` (defaults to dir name), `--id`. Replaces remote UDF list — UDFs missing locally are removed. If no canvas with that name exists, a new one is created. **Canvas names must match `[a-zA-Z0-9_]` — no spaces or hyphens.** |
| `rename CANVAS_REF NEW_NAME` | `--id` |
| `share CANVAS_REF` | `--client-id TEXT`, `--new-token`, `--id` |
| `unshare CANVAS_REF` | `--id` |
| `serve-mcp CANVAS_REF` | `--token` (treat ref as `fc_…` share token), `--team`, `--id`, `--host TEXT` (default `127.0.0.1`), `--port INTEGER` (default `8765`), `--path TEXT` (default `/mcp`), `--claude` (register with Claude Code via `claude` CLI) — serves the shared canvas's OpenAPI as a local MCP server. The canvas must be shared first (`fused canvas share <ref>`) |

- When pushing a canvas, prefer to test the canvas to make sure your changes work. For JSON UI nodes, you can run using `fused json-ui run-inline-widget`/`fused json-ui run-shared-widget`, for UDFs, you can run them using `fused run`.

**Directory name ≠ canvas name.** By default `push` uses the source directory's name as the canvas name. If your local folder is named differently from the remote canvas (e.g. folder is `fused-canvas/`, remote canvas is `feedback_pipeline`), the push will try to create a new canvas with the folder's name — and fail if that name contains hyphens. Always pass `--canvas` explicitly when the names differ:

```bash
# Push ./fused-canvas/ to the existing canvas named "feedback_pipeline"
fused canvas push ./fused-canvas --canvas feedback_pipeline
```

If you're unsure of the remote canvas name, run `fused canvas list` first.

## Reading an existing canvas

To understand what a canvas contains, pull it locally first, then read the files:

```bash
fused canvas pull CANVAS_REF -o ./local_canvas
```

Once pulled, the output directory contains:
- `canvas.toml` — nodes, edges, viewport (see the `fused:canvas-toml` skill for the full format)
- `*.py` / `*.json` / `*.md` / `*.html` — one source file per UDF node

To inspect a single UDF's parameters without pulling the full canvas, use `fused udf-schema CANVAS UDF`.

### Anti-patterns

| Avoid | Why | Instead |
| --- | --- | --- |
| `fused canvas export` to inspect a canvas | Downloads a zip that needs manual extraction | `fused canvas pull -o ./dir` extracts automatically |
| `fused canvas pull --dry-run` then reading local files | `--dry-run` prints what would be created/updated/removed but writes nothing to disk | Omit `--dry-run` when you need to read files locally |
| Running `fused run` on each UDF to understand what it does | Executes UDFs remotely — slow and consumes compute | Read the `.py` source files after pulling |
| `fused canvas list` to see canvas structure | Only shows metadata (name, ID) — not nodes or UDF content | Pull the canvas and read `canvas.toml` |

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

## `fused integrations`

OAuth-style connectors for third-party services. Each provider exposes the same three subcommands (`connect`, `token`, `revoke`); Snowflake's `connect` takes extra flags because it uses customer-owned OAuth clients.

| Subcommand | Args / notable options |
| --- | --- |
| `list` | List integrations and their connection status |
| `<provider> connect` | `--open / --no-open` — start OAuth and print the authorization URL (opens automatically in a tty unless `--no-open`) |
| `<provider> token` | Print a short-lived access token for the provider (sensitive output) |
| `<provider> revoke` | Disconnect the provider and remove stored tokens |
| `snowflake connect` | Adds `--account-identifier TEXT`, `--client-id TEXT`, `--client-secret TEXT`, `--client-secret-2 TEXT` (for key rotation) on top of `--open/--no-open` |

Providers: `airtable`, `google-drive` (alias `gdrive`), `hubspot`, `notion`, `snowflake`.

## `fused json-ui`

Inspect, validate, and render JSON-UI widget component schemas (the same schemas covered by the `fused:json-ui-schemas` skill). Use these subcommands as your primary debugging tools when authoring or editing `widget_*.json` files — they're faster than round-tripping through the canvas UI.

| Subcommand | Args / notable options |
| --- | --- |
| `catalog-prompt` | Print the JSON-UI catalog prompt (component overview) |
| `schemas [COMPONENTS]...` | Print JSON Schemas for one or more component names, or all if omitted. The CLI is authoritative when it disagrees with `reference.md` |
| `validate CONFIG_OR_PATH` | Validate an inline JSON5 config string or a path to a `.json`/`.json5` file. Run this after every non-trivial widget edit to catch missing required props, unknown keys, and enum violations before pushing |
| `run-inline-widget CANVAS_SHARE_TOKEN WIDGET_CONFIG` | Open a share URL with an inline widget query and capture a screenshot. `--print-url-only`, `--browser [chrome\|firefox]`, `--wait INTEGER` (give async data time to load), `--screenshot-filename FILE` (save PNG to file instead of printing base64). Screenshotting requires `fused[browser]` extras |
| `run-shared-widget CANVAS_SHARE_TOKEN WIDGET_NAME` | Open a shared widget page and capture a screenshot. Same options as `run-inline-widget`. Requires the canvas to be shared first (`fused canvas share <ref>`) |

**Debugging flow:** edit the widget JSON → `fused json-ui validate <file>` → push → `fused json-ui run-shared-widget <share-token> <widget-name> --screenshot-filename out.png` to confirm it renders. Use `run-inline-widget` when iterating on a widget that hasn't been committed yet.

## `fused claude`

Manage Fused for Claude Code via the `claude` CLI.

| Subcommand | Purpose |
| --- | --- |
| `plugin add` | Register the marketplace and install `fused@fused-marketplace` |
| `plugin update` | Update `fused@fused-marketplace` to the latest version |
| `plugin remove` | Remove the fused plugin |
| `add-mcp CANVAS_REF` | Register the hosted canvas MCP endpoint with Claude Code (same as Workbench "Copy MCP"). Options: `--token`, `--team`, `--id`, `--create-session-token/--no-create-session-token` (default: on), `--session-max-age TEXT` (default `1h`) |

## `fused completion`

| Subcommand | Args / notable options |
| --- | --- |
| `install` | `--shell [auto\|bash\|zsh\|fish]`, `--dry-run`, `-y/--yes` — append a one-liner to `~/.bashrc`/`~/.zshrc` or write fish's completion file |
| `print {bash\|zsh\|fish}` | Print a completion script suitable for `eval` or fish's completions dir |

## Calling UDFs: HTTP vs `fused run`

Use this to decide which approach to suggest:

| | `fused run` | HTTP API |
| --- | --- | --- |
| **When to use** | Local development, testing, debugging | External integrations, bots, callers without Fused credentials |
| **Canvas must be shared?** | No — works on private canvases | Yes — `fused canvas share` must be run first |
| **Auth required?** | Yes — must be authenticated as the canvas owner | No — share token in the URL is sufficient |
| **Caller environment** | Anywhere `fused` CLI is installed | Any HTTP client (curl, browser, another service) |

**Default to `fused run` during development.** Only suggest HTTP when the goal is an external caller or a production integration that runs without Fused credentials. Never suggest an HTTP call on a canvas that hasn't been shared — it will return 404 or 403.

## Calling UDFs via HTTP

Every shared canvas exposes a public HTTP API — no Fused SDK or credentials required on the caller side. This is the foundation for building bots, external integrations, and any service that calls Fused from outside Python.

### HTTP API URL format

Once the canvas is public, each UDF is callable as:

```
GET https://udf.ai/<share_token>/<udf_name>?param1=value1&param2=value2&format=json
```

- `format=json` returns a JSON array of row objects (one per DataFrame row). Omitting it returns a binary format.
- Parameters are passed as query string values — strings, integers, and booleans all work.

**Example:**
```bash
curl "https://udf.ai/fc_abc123/ask_question?question=what+is+fused&format=json"
# → [{"answer": "Fused is a platform for running Python in the cloud..."}]
```

### Discover available UDFs

The `.api.json` endpoint returns an OpenAPI spec listing all UDFs in the canvas and their parameters:

```bash
curl "https://udf.ai/<share_token>.api.json"
```

Use this to build tool lists for LLM agents — the `summary` field in each path is the UDF's docstring, which the canvas bot uses as the tool description.

---

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

> **`--with pandas` required for local result deserialization.** When running via `uv run`, the result DataFrame is deserialized locally and requires `pandas` to be available in that environment. Without it you get `ModuleNotFoundError: No module named 'pandas'` even if the UDF itself doesn't use pandas. Always add `--with pandas`:
>
> ```bash
> uv run --no-project --with fused --with pandas fused run my_canvas my_udf --param=value
> ```
>
> `--no-project` avoids pulling in the current directory's dependencies, which can conflict with fused's requirements.

Additionally, `fused run` accepts **arbitrary keyword args matching the UDF's signature**, e.g. `--abc=123` is forwarded as the `abc` parameter to the UDF. These pass-through args are not listed in `--help`.

When running locally via `uv run`, include `--with pandas` if the UDF returns a DataFrame — the CLI needs pandas to deserialize the result, and the error (`ModuleNotFoundError: No module named 'pandas'`) appears at result-read time, not inside the UDF itself:

```bash
uv run --with fused --with pandas fused run my_canvas my_udf --param=value
```

## `fused udf-schema CANVAS UDF`

Prints a UDF's API schema (parameter types, return shape) without executing it. The `UDF` argument is passed to `fused.load` and accepts the same forms as `fused run`:

- Fused identifier: `user@example.com/my_udf` or `my_udf` (resolved against `CANVAS` as the collection)
- Local Python file: `udf.py` or any `.py` path
- GitHub tree/blob URL
- Inline UDF source (a string containing at least one newline is treated as Python module text)

Options:

- `--stdin` — read UDF source from stdin instead of passing `UDF` (do not pass `UDF` with `--stdin`)

Use this to introspect parameters before calling `fused run` with `--<param>=<value>` kwargs, or to confirm a UDF's signature matches what a widget or downstream UDF expects.

## Tips

- If the CLI lives in a project venv, prefix with `uv run` so the right environment is used.
- For machine-readable output in scripts, pass `--format json`.
- Run `fused <command> --help` to confirm flags before scripting — this reference may lag the CLI.
- When appropriate, give the user the URL to the created canvas so they can open it in their browser and see the result.
- **Prefer the CLI for debugging.** Before asking the user to open the canvas UI to check a change, try to reproduce locally: `fused run` for UDFs, `fused json-ui validate` / `run-shared-widget` for widgets, `fused canvas pull --dry-run` to inspect what changed remotely. This catches most issues without a round trip.

# Findings — Fused skill CLI install fails on Python 3.9

## What I found

The Notion ticket says: *"Fused skill CLI install fails on Python 3.9 due to missing CLI entry point."* I couldn't fetch the page body (no `notion-fetch` MCP available, page requires auth), so I reproduced the failure from PyPI metadata.

The README's recommended flow today is:

```sh
pip install --upgrade fused
fused claude plugin add
```

On Python 3.9 this breaks because:

- `fused` 2.x — the line that introduces the `fused` CLI and the `claude plugin add` subcommand — declares `requires-python = ">=3.10,<4"` (confirmed against `fused-2.8.0/pyproject.toml`, which contains `[project.scripts]` with `fused = "fused.cli:main"`).
- On Python 3.9, pip's resolver falls back to the latest 3.9-compatible release, `fused 1.18.0`. Its `pyproject.toml` (Poetry) has **no `[tool.poetry.scripts]` / `[project.scripts]` block** — it is a library-only release.
- Result: `pip install --upgrade fused` succeeds quietly, but no `fused` binary lands on `PATH`. The next command `fused claude plugin add` exits with "command not found", matching the customer report exactly.

`uvx fused …` works on the same machine because `uvx` picks its own toolchain Python (3.10+) instead of using the system 3.9.

## What I changed

Focused doc fix — no install scripts in the repo to alter.

- **`README.md`** — leads with `uvx fused claude plugin add` (the path that works regardless of system Python), then a `pip install --upgrade 'fused>=2'` fallback for users who want it in their current env. Added a one-paragraph callout explaining the Python 3.10+ requirement and the silent 1.x fallback on 3.9 so users recognize the failure mode.
- **`fused-plugin/skills/fused-cli/SKILL.md`** — the "Finding the CLI" section now says the CLI ships in `fused>=2` and requires Python 3.10+, calls out the silent 1.x fallback in the troubleshooting note, and pins `--python 3.11` + `'fused>=2'` in the fresh-install snippet. Adds a "if you see `fused: command not found` right after `pip install`, check `python --version`" hint so the assistant invoking this skill can diagnose the same failure on a user's machine.

## Verification

- Pulled `fused-1.18.0.tar.gz` and `fused-2.8.0.tar.gz` from PyPI directly. 1.18.0 has no script entry points; 2.8.0 declares `[project.scripts] fused = "fused.cli:main"`.
- PyPI metadata: `fused 2.x` is `<4,>=3.10`; `fused 1.18.0` is `<4,>=3.9`. Confirms pip's fallback path on Python 3.9.

## Limitations / open questions

- I couldn't read the original Notion ticket body, so I'm inferring the customer's exact command sequence from the title and the README. If their actual failure was something else (e.g. `pip` errored out with a resolver message instead of silently installing 1.x), the doc still helps, but the framing in the README callout could be sharpened.
- I didn't add a hard runtime check (e.g. an `install.sh` that aborts on Python 3.9). The repo doesn't currently ship an installer script; adding one felt out of scope for a doc-level customer report. If we keep hitting this, the next step is to have `fused claude plugin add` itself print a clearer message when run on Python 3.9 — but that lives in the `fused` Python package, not in this repo.
- The repo's `marketplace.json` / `plugin.json` don't expose any Python-version metadata to Claude Code, so there's no marketplace-side gate to add here.

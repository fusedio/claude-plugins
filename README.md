# Fused Skills

Install the Fused plugin for Claude Code:

```sh
uv tool install fused
fused claude plugin add
```

Then open a new Claude Code session. `fused` is now permanently on your PATH — Claude can find it in any future session without reinstalling.

If `uv` is not found, install it first, then re-run the commands above:

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh` (restart terminal after)
- **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (restart terminal after)

## Reinstall / update

```sh
uv tool install fused --upgrade
fused claude plugin add
```

## Alternative: pip

If Python 3.10+ is already installed and you prefer not to use `uv`:

```sh
pip install --upgrade 'fused>=2'
fused claude plugin add
```

> **Python 3.9 note:** `pip install fused` on Python 3.9 silently installs `fused 1.x`, which has no `fused` command. Pinning `>=2` makes pip fail loudly instead. Use `uv tool install fused` above to avoid this entirely.

### Windows (pip path)

If `fused` is not found after `pip install`, the Scripts directory is likely missing from your PATH. Run:

```powershell
python -m site --user-scripts
```

This prints the exact Scripts path (e.g. `C:\Users\You\AppData\Roaming\Python\Python311\Scripts`). Add it to your `PATH` (search "environment variables" in the Start menu → edit the `Path` user variable), then open a new terminal and retry `fused claude plugin add`.

## Manual installation

### Claude Code

To install the `fused` plugin:

```sh
claude plugin marketplace add fusedio/claude-plugins
claude plugin install fused@fused-marketplace
```

To update the `fused` plugin:

```sh
claude plugin update fused@fused-marketplace
```

To remove the `fused` plugin:

```sh
claude plugin remove fused
# Or, for the entire marketplace:
claude plugin marketplace remove fused-marketplace
```

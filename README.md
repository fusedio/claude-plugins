# Fused Plugins for Claude Code

The `fused-marketplace` ships two Claude Code plugins:

- **[`agent-core`](agent-core/)** — the primary plugin. Usage/guide skills for building with **Fused** end-to-end: setup, infra, the `fused` CLI/MCP toolkit, project authoring, execution, verification, storage, and widgets.
- **[`workbench`](workbench/)** — legacy skills for the Fused **workbench** SDK CLI (`fused workbench …`): canvas.toml, JSON-UI widgets, UDFs, and integrations.

> **Heads up — CLI namespace change.** The original Fused repo was consolidated with OpenFused and now ships as a single `fused` package. The bare `fused` command is now the **OpenFused agent toolkit**; the legacy proprietary SDK CLI now lives under **`fused workbench`** (e.g. `fused canvas push` → `fused workbench canvas push`). The package and install command (`uv tool install 'fused[vector]'`) are unchanged.

## Install the plugins

```sh
claude plugin marketplace add fusedio/claude-plugins
claude plugin install agent-core@fused-marketplace   # primary
claude plugin install workbench@fused-marketplace      # legacy workbench skills
```

To update or remove:

```sh
claude plugin update agent-core@fused-marketplace
claude plugin remove agent-core
# Or, for the entire marketplace:
claude plugin marketplace remove fused-marketplace
```

You can also load a plugin directly from a local checkout without the marketplace:

```sh
claude --plugin-dir ./agent-core
```

## Installing the `fused` CLI

Both plugins drive the `fused` CLI. Install it once:

```sh
uv tool install 'fused[vector]'
```

Then open a new Claude Code session. `fused` is now permanently on your PATH — Claude can find it in any future session without reinstalling.

> **Why `fused[vector]`?** The `vector` extra installs `geopandas` (and therefore `pandas`) plus `shapely`. Without these, running UDFs locally fails with `ModuleNotFoundError: No module named 'pandas'` when the result DataFrame is deserialized. Plain `uv tool install fused` only gives you the CLI itself.

If `uv` is not found, install it first, then re-run the commands above:

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh` (restart terminal after)
- **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (restart terminal after)

### Reinstall / update the CLI

```sh
uv tool install 'fused[vector]' --upgrade
```

### Alternative: pip

If Python 3.10+ is already installed and you prefer not to use `uv`:

```sh
pip install --upgrade 'fused[vector]>=2'
```

> **Python 3.9 note:** `pip install fused` on Python 3.9 silently installs `fused 1.x`, which has no `fused` command. Pinning `>=2` makes pip fail loudly instead. Use `uv tool install 'fused[vector]'` above to avoid this entirely.

#### Windows (pip path)

If `fused` is not found after `pip install`, the Scripts directory is likely missing from your PATH. Run:

```powershell
python -m site --user-scripts
```

This prints the exact Scripts path (e.g. `C:\Users\You\AppData\Roaming\Python\Python311\Scripts`). Add it to your `PATH` (search "environment variables" in the Start menu → edit the `Path` user variable), then open a new terminal and retry.

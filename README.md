# Fused Skills

Fused skills and plugins for AI

The `fused` CLI requires **Python 3.10 or newer**. On Python 3.9 or older, `pip install fused` silently installs `fused 1.x`, which is library-only and does not ship a `fused` command — `fused claude plugin add` will fail with "command not found". Check your Python version with `python --version` before installing.

The easiest install path is `uvx`, which fetches a compatible Python automatically:

```sh
uvx fused claude plugin add
```

If you'd rather install into your current environment, make sure it's Python 3.10+ and run:

```sh
pip install --upgrade 'fused>=2'
fused claude plugin add
```

Pinning `>=2` makes `pip` fail loudly on Python 3.9 instead of falling back to a library-only release.

After running `fused claude plugin add`, **restart Claude Code** and open a brand-new session — the plugin will not be visible in the session where the install ran.

## Windows

On Windows, `uv` is the most reliable path because it manages Python for you and avoids the Python 3.9 / PATH pitfalls common on Windows machines.

**Step 1 — install `uv` (no Python required):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after this step.

**Step 2 — install the Fused plugin:**

```powershell
uvx fused claude plugin add
```

**Step 3 — restart Claude Code** (see note above).

---

**Alternative: if Python 3.10+ is already installed**

```powershell
pip install --upgrade "fused>=2"
fused claude plugin add
```

If `fused` is not found after install, the Scripts directory is likely missing from your PATH. Run:

```powershell
python -m site --user-scripts
```

This prints the exact Scripts path (e.g. `C:\Users\You\AppData\Roaming\Python\Python311\Scripts`). Add it to your `PATH` in System Settings → Environment Variables, then open a new terminal and retry `fused claude plugin add`.

> **Note:** Python 3.9 is too old. `pip install fused` on Python 3.9 silently installs `fused 1.x`, which has no `fused` command. Check with `py --version` or `python --version` and upgrade to 3.10+ (or just use `uvx` above, which handles this automatically).

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

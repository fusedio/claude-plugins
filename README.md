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

# Fused Skills

Fused skills and plugins for AI

To install `fused`:

```sh
uv add fused
# or
pip install fused
```

Then install this as a Claude plugin:

```sh
fused claude plugin add
```

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

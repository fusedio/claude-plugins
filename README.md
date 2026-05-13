# claude-plugins
Fused plugins for Claude

To install `fused`:

```sh
uv add fused
# or
pip install fused
```

Then install this plugin:

```sh
fused claude plugin add
```

## Manual installation

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

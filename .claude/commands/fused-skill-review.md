# Fused Skill Review

Review a PR (or current branch) for quality issues specific to Fused Claude Code skills.

## Usage

```
/fused-skill-review [PR_NUMBER]
```

If a PR number is given, fetch the diff from `fusedio/skills`. Otherwise diff the current branch against `main`.

## Steps

### 1. Get the diff

```bash
# With PR number
gh pr diff <PR_NUMBER> --repo fusedio/skills

# Without (current branch)
git diff main...HEAD
```

### 2. Check every URL in changed files

- Extract all markdown links `[text](url)` and bare `https://` URLs from the diff
- `curl -sI <url>` each one — flag anything that isn't HTTP 200 or 301/302
- Skip: `localhost`, any `YOUR_*` placeholder, `example.com`, and any URL inside a fenced code block that is clearly illustrative (e.g. `https://udf.ai/fc_TOKEN/udf_name`)

### 3. Check Fused code patterns

For every Python code block added in the diff:

- **Imports inside UDF body** — no module-level imports; all `import` statements must be indented inside the function
- **Decorator form** — `@fused.udf` with no parens unless `engine=` is set (i.e. `@fused.udf()` with empty parens is wrong)
- **Cross-UDF calls** — `fused.load("udf_name")()` not direct function calls or imports
- **Engine values** — if `engine=` appears, value must be one of `"remote"`, `"small"`, `"medium"`, `"large"`
- **No stray returns** — no `return` statement outside a function body

### 4. Check packages

For any package name in `pip install` commands or bare `import X` statements in new code examples:

```bash
pip index versions <package> 2>&1 | head -1
```

Flag anything that returns "no matching distribution found". Skip known Fused builtins: `fused`, `geopandas`, `pandas`, `numpy`, `fsspec`.

### 5. Fix every issue found

After identifying issues, **fix them directly in the checked-out files** — don't just report them. For each issue:

- Check out the PR branch locally if not already on it: `gh pr checkout <PR_NUMBER> --repo fusedio/skills`
- Edit the file to correct the violation (use the Edit tool)
- Do not add a commit — leave the changes staged for the author to review

Broken links are the exception: if a URL is genuinely dead (not a placeholder), flag it in the report but don't guess at a replacement — note "manual fix needed" and move on.

## Output format

Produce a concise report grouped by file after fixes are applied. One ✅ line per passing check. For fixed issues use 🔧.

```
## fused-integrations/SKILL.md
✅ Links (3 checked): all valid
🔧 Code patterns: fixed `@fused.udf()` → `@fused.udf` (line 42)
✅ Packages: none flagged

## fused-cli/SKILL.md
✅ Links (1 checked): all valid
✅ Code patterns: no violations
✅ Packages: none to check
```

Don't repeat the diff content back. Be specific when describing a fix: quote the before and after.

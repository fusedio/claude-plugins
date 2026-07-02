---
name: fused-guide
description: Entry-point router for the Fused skills in this repo. Use when a user asks how to get started with, set up, or install Fused, how to build a project or UDF, how to get a widget UI / dashboard out of Fused, or is unsure which Fused skill to load. Maps a goal to the specific skill(s) to read next.
---

# Fused — start here

This repo is a Claude Code plugin for **Fused** (end-to-end data work on
cloud-native datasets via MCP and CLI). The model is **workspace ⊃ project ⊃
UDF**. This guide routes your goal to the skill that covers it — load that skill
and follow it. Don't try to do the work from this page; it only points.

## Pick by goal

### Set up / install Fused
1. **`fused-setup`** — install the package, check AWS credentials (or pick
   the local backend, no cloud needed), create an environment, and verify.
2. **`fused-infra`** — what infrastructure each backend provisions (AWS: IAM,
   Lambda, ECR, S3; local: data dirs + venvs), and how to provision/troubleshoot it.

### Build a project end-to-end and get its widget UI
This is the main path from a user request to a running, viewable result.
1. **`fused-projects`** — the canonical end-to-end flow: pick an environment,
   create a project, decompose the task into UDFs, author specs + code, validate,
   commit, run/preview, and deploy. Start here for any "take this from prompt to
   result" request.
2. **`fused-widgets`** — when the desired output is a **widget/dashboard**
   rather than raw data: the py-UDF-computes → json-widget-visualizes pattern,
   the `{{ref}}`/`$param` data grammar, and the surfaces that render it
   (`fused widget open`, the parley, deployed URL).
3. **`fused-feedback`** — to put a question, approval, or plan-review UI in
   front of the human and get the answer back as JSON (`fused widget open` /
   parley). Use whenever a structured choice beats plain terminal text.

### Run and validate code
- **`fused-execute`** — best practices for `execute_code`: structuring user
  code, choosing a data library, handling results, writing outputs to storage.
- **`fused-verify`** — security scanning, spec checks, testing, and the audit
  log (`verify_code`, `test_code`, `get_audit_log`).
- **`fused-storage`** — inspect datasets (list/count files, read schemas,
  mint download URLs, upload) and manage secrets via the MCP tools.

### Reach for the CLI
- **`fused-cli`** — full `fused` command/flag reference: environments,
  file storage, secrets, code execution, infra. Use when writing or explaining
  shell commands that invoke `fused`.

### Manage the Fused App state (`_core`)
The App state store (tasks, runs, feedback, secrets, agent roster) is exposed at
runtime as built-in `_core` workspace UDFs — e.g. `{{_core.task-management.read}}`.
This plugin ships the CLI/usage guides only; the `_core` UDFs are documented
inline where you'll use them — see **`fused-widgets`** (referencing `_core.*` from
widgets) and **`fused-cli`** (invoking `_core` UDFs from the shell).

## Customizing or fixing a skill

Before editing any skill in this repo, pick the right path (see `CONTRIBUTING.md`):

- **Changing what a skill *means*** — different defaults, a repurposed UDF op, a
  team-specific workflow — **do not modify the shipped skill in place.** Create a
  new skill or Fused project in the user's own workspace and diverge there;
  an in-place meaning change affects everyone who loads this plugin and is lost
  on the next pull. Tell the user this and author the new skill/project instead.
- **Fixing a bug or making an additive improvement** — a doc fix, a wrong/missing
  field, a clarified caveat, a genuinely additive op — **contribute it back as a
  PR** (branch off `main`, focused change, behavior-preserving). Tell the user to
  upstream it rather than keep a local divergence.

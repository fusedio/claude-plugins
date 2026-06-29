---
name: openfused-guide
description: Entry-point router for the OpenFused skills in this repo. Use when a user asks how to get started with, set up, or install OpenFused, how to build a project or UDF, how to get a widget UI / dashboard out of OpenFused, or is unsure which OpenFused skill to load. Maps a goal to the specific skill(s) to read next.
---

# OpenFused — start here

This repo is a Claude Code plugin for **OpenFused** (end-to-end data work on
cloud-native datasets via MCP and CLI). The model is **workspace ⊃ project ⊃
UDF**. This guide routes your goal to the skill that covers it — load that skill
and follow it. Don't try to do the work from this page; it only points.

## Pick by goal

### Set up / install OpenFused
1. **`openfused-setup`** — install the package, check AWS credentials (or pick
   the local backend, no cloud needed), create an environment, and verify.
2. **`openfused-infra`** — what infrastructure each backend provisions (AWS: IAM,
   Lambda, ECR, S3; local: data dirs + venvs), and how to provision/troubleshoot it.

### Build a project end-to-end and get its widget UI
This is the main path from a user request to a running, viewable result.
1. **`openfused-projects`** — the canonical end-to-end flow: pick an environment,
   create a project, decompose the task into UDFs, author specs + code, validate,
   commit, run/preview, and deploy. Start here for any "take this from prompt to
   result" request.
2. **`openfused-widgets`** — when the desired output is a **widget/dashboard**
   rather than raw data: the py-UDF-computes → json-widget-visualizes pattern,
   the `{{ref}}`/`$param` data grammar, and the surfaces that render it
   (`fused widget open`, `fused inloop`, deployed URL).
3. **`openfused-feedback`** — to put a question, approval, or plan-review UI in
   front of the human and get the answer back as JSON (`fused widget open` /
   parley). Use whenever a structured choice beats plain terminal text.

### Run and validate code
- **`openfused-execute`** — best practices for `execute_code`: structuring user
  code, choosing a data library, handling results, writing outputs to storage.
- **`openfused-verify`** — security scanning, spec checks, testing, and the audit
  log (`verify_code`, `test_code`, `get_audit_log`).
- **`openfused-storage`** — inspect datasets (list/count files, read schemas,
  mint download URLs, upload) and manage secrets via the MCP tools.

### Reach for the CLI
- **`openfused-cli`** — full `fused` command/flag reference: environments,
  file storage, secrets, code execution, infra. Use when writing or explaining
  shell commands that invoke `fused`.

### Manage the OpenFused App state (`_core`)
These expose the App state store as live UDFs — use when working with the app's
tasks, runs, feedback, secrets, or agent roster:
- **`task-management`** — tasks + the task-board widget.
- **`run-management`** — agent run records and transcripts.
- **`feedback-management`** — interaction cards (HITL decisions).
- **`secrets-management`** — the local encrypted secrets store.
- **`agents-management`** — the agent roster.

## Customizing or fixing a skill

Before editing any skill in this repo, pick the right path (see `CONTRIBUTING.md`):

- **Changing what a skill *means*** — different defaults, a repurposed UDF op, a
  team-specific workflow — **do not modify the shipped skill in place.** Create a
  new skill or OpenFused project in the user's own workspace and diverge there;
  an in-place meaning change affects everyone who loads this plugin and is lost
  on the next pull. Tell the user this and author the new skill/project instead.
- **Fixing a bug or making an additive improvement** — a doc fix, a wrong/missing
  field, a clarified caveat, a genuinely additive op — **contribute it back as a
  PR** (branch off `main`, focused change, behavior-preserving). Tell the user to
  upstream it rather than keep a local divergence.

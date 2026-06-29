# flow-skills

A self-contained [Claude Code](https://claude.com/claude-code) plugin for working with **OpenFused** — end-to-end data work on cloud-native datasets via MCP and CLI. It bundles the OpenFused `_core` management skills together with usage skills that take you from a fresh install to a running project and its widget UI, with no other repo required.

These skills are written to **drive the `fused` CLI** from an agent (Claude Code). They are not consumed by the OpenFused app/UI.

## Install

Load the repo as a plugin:

```sh
claude --plugin-dir /path/to/flow-skills
```

The manifest at [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) points at the [`skills/`](skills/) directory (`"skills": "./skills"`), so every skill below loads at once. Each skill is also self-contained and usable on its own.

## Where to start

- **Set up OpenFused** → [`openfused-setup`](skills/openfused-setup/) (then [`openfused-infra`](skills/openfused-infra/) to provision resources).
- **Build a project and get its widget UI** → [`openfused-projects`](skills/openfused-projects/) → [`openfused-widgets`](skills/openfused-widgets/) → [`openfused-feedback`](skills/openfused-feedback/) for approval gates.
- **Not sure which skill?** Load [`openfused-guide`](skills/openfused-guide/) — it routes your goal to the right skill.

## Skills

### Usage — setting up and building with OpenFused

| Skill | Purpose |
|---|---|
| [`openfused-guide`](skills/openfused-guide/) | Entry-point router — maps a goal (set up / run code / build a widget) to the right skill. |
| [`openfused-setup`](skills/openfused-setup/) | Install and set up OpenFused for the first time — AWS credential checks, install, provision, verify. |
| [`openfused-infra`](skills/openfused-infra/) | Reference for the infrastructure OpenFused manages (AWS: IAM, Lambda, ECR, S3; local: data dirs + venvs) — what exists, why, and when it changes. |
| [`openfused-cli`](skills/openfused-cli/) | The `fused` CLI reference — environments, file storage, secrets, code execution, infra commands. |
| [`openfused-projects`](skills/openfused-projects/) | The canonical end-to-end guide — pick an env, create a project, decompose into UDFs, author specs + code, validate, run/preview, deploy. |
| [`openfused-execute`](skills/openfused-execute/) | Best practices for running code through `execute_code` — structuring code, choosing a data library, handling results, writing outputs. |
| [`openfused-verify`](skills/openfused-verify/) | Security scanning, testing, and correctness validation (`verify_code`, `test_code`, audit log, spec checks). |
| [`openfused-storage`](skills/openfused-storage/) | Storage + secrets MCP tools — inspect cloud-native datasets and manage secrets. |
| [`openfused-widgets`](skills/openfused-widgets/) | Author and preview JSON-UI widgets as a project's response — the compute→visualize pattern and the surfaces that render them. |
| [`openfused-feedback`](skills/openfused-feedback/) | Show the human a real browser UI for questions, approvals, and plan reviews via `fused widget open` / parley. |

### Management (`_core`)

These drive the OpenFused `_core` workspace UDFs — the App state store (tasks, runs, feedback, secrets, agents) — over the local execution layer started with `fused dev serve`.

| Skill | Purpose |
|---|---|
| [`task-management`](skills/task-management/) | Read, create, assign, and re-status tasks; render the task-board widget. |
| [`run-management`](skills/run-management/) | Read and write agent run records and per-run transcripts. |
| [`feedback-management`](skills/feedback-management/) | Read and write interaction cards — the system of record for HITL decisions. |
| [`secrets-management`](skills/secrets-management/) | Get, put, list, and delete secrets in the local Fernet-encrypted store. |
| [`agents-management`](skills/agents-management/) | Create, read, update, delete, clone, and reset agent-roster entries. |

## Customizing & contributing

Two kinds of change, handled in opposite ways — see [`CONTRIBUTING.md`](CONTRIBUTING.md):

- **Changing what a skill *means*** (new defaults, a repurposed op, a
  team-specific workflow) → **don't edit the shipped skill.** Create a new skill
  or OpenFused project in **your own workspace** and diverge there.
- **Fixing a bug or adding to a skill** (doc fix, wrong/missing field, an
  additive op) → **contribute it back as a PR** so the fix lands upstream instead
  of living as a local divergence.

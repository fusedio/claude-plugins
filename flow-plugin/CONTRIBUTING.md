# Contributing to flow-skills

These skills are shared, versioned source that many people load as one plugin.
Two kinds of change are handled in **opposite** ways — pick the path that matches
what you're doing before you touch a file.

## Changing what a skill *means* → make your own, don't edit the repo's

If a change would alter a skill's **behavior, contract, or intent** — different
defaults, a renamed/repurposed UDF op, a new opinion about how the work should be
done, a workflow tailored to your team — **do not modify the shipped skill in
place.** Editing a repo skill's meaning silently changes it for everyone who
loads this plugin, and your change will be overwritten on the next pull.

Instead, create a **new skill or project in your own workspace** and diverge
there:

- **A new skill** — author it under your own `skills/` (or a personal plugin
  dir) following [`utilities:writing-skills`](https://docs.claude.com/claude-code).
  Start from a copy of the repo skill if you like, give it a new `name`, and
  evolve it freely. Load it alongside this plugin.
- **A new OpenFused project** — if you're adding domain UDFs or a custom
  task/run/widget flow, create a project in your environment (see
  `openfused-projects`) rather than editing the `_core` skills here. The `_core`
  management skills are the shared substrate; your behavior belongs in your own
  project on top of them.

Rule of thumb: **if someone else loading this plugin would be surprised by your
change, it belongs in your workspace, not in the repo skill.**

## Fixing a bug or adding to a skill → contribute it back as a PR

If a change makes a shipped skill **more correct or more complete without
changing its intent** — a documentation fix, a corrected response shape, a
missing column, a clarified caveat, a genuinely additive new UDF op — that
benefits everyone. **Contribute it back as a pull request** so the fix lands
upstream instead of living as a local divergence:

1. Branch off `main` (don't commit fixes straight to `main`).
2. Make the focused change; keep meaning-changing edits out of the same PR.
3. Open a PR with a clear summary of what was wrong/missing and why the fix is
   behavior-preserving.

Bug fixes and additive improvements are exactly what should flow upstream — keep
them out of your private fork and send them here.

## Which path am I on?

| Your change | Path |
|---|---|
| New defaults, renamed/repurposed op, team-specific workflow, different opinion | New skill/project in **your workspace** |
| Doc fix, wrong/missing field, clarified caveat, additive new op | **PR back to this repo** |
| Not sure | Treat it as meaning-changing → fork to your workspace, and open an issue to discuss upstreaming |

## Skill invocation

The `_core` management skills (`task-management`, `run-management`,
`feedback-management`, `secrets-management`, `agents-management`) carry
`disable-model-invocation: true` in their frontmatter — they are meant to be
invoked **explicitly** (e.g. `/flow-skills:task-management`), not auto-triggered
by the model. The `openfused-*` usage skills stay model-invokable.

> **Known caveat:** as of the current Claude Code release, `disable-model-invocation`
> is **silently ignored for plugin skills** (the loader hardcodes plugin skills to
> `"on"`) — see [claude-code#22345](https://github.com/anthropics/claude-code/issues/22345),
> open/unfixed. The frontmatter is kept as a declaration of intent: it takes effect
> automatically once that bug is fixed, or if a skill is loaded as a user skill
> (`~/.claude/skills/`). To suppress auto-invocation today, the only working
> options are to load the skill from `~/.claude/skills/` or wait for the upstream fix.

---
name: fused-feedback
description: Show the human a real browser UI — to ask a question, get an approval/decision, or review a plan — built from Fused's JSON-UI primitives and opened with `fused widget open` (one-shot — inline `--config` or a `.json` file) or the parley (`widget push`/`widget watch`, standing). Use in Claude Code whenever a structured choice, form, approval, or plan review would be clearer than plain terminal text, and you want the human's answer back as JSON.
---

# Fused feedback — ask the human through a visual UI

Instead of asking the human a question as terminal text, render a **real browser
UI** and get a **structured answer back as JSON**. You author a small JSON-UI
config (a tree of `{type, props, children}` nodes — text, inputs, buttons), open
it with `fused widget open`, and the command **blocks until the human
responds**, then prints their answer on stdout.

This is Fused's local feedback loop repackaged for
**Claude Code**: a visual-planning surface for questions, approvals, and plan
reviews, in the user's own workspace.

> **CLI vs in-app.** This skill is the **CLI** `widget open`/parley surface — you
> author a static widget and read the human's submitted `action`/`params`. The
> separate **in-app** `ask_user(summary, widget, effect)` tool (with its `effect:
> "reply"` / `effect: "approval_gate"` discriminator) is the flow app's agent surface.
> The `effect` argument does not apply here.

## When to use this

Reach for a widget instead of a plain text question when the answer is
**structured**:

- **A choice** — single-select (`dropdown`) or multi-select (`checkbox-group`).
- **An approval / decision** — Approve / Reject / Request-changes buttons.
- **A form** — several fields filled at once (target, batch size, flags, notes).
- **A plan review** — show the proposed plan, collect a verdict + edits in one go.

Stick to plain text for a quick yes/no in the middle of a flow, or when there's
no browser at the machine. Use [`AskUserQuestion`](#vs-askuserquestion) for a
lightweight in-terminal multiple-choice; use this skill when you want a **richer,
visual** surface (free-text + choices + a plan laid out together, a persistent
planning page you iterate on).

## Prerequisites

- The **`fused` CLI** on `PATH`. (Inside an Fused source checkout, use
  `uv run fused …` instead of `fused …`.)
- **Node 20+** on `PATH`. The first `widget open`/`push` **cold-boots two
  servers** — the Node/Express app *and* a Python `dev serve` daemon (first paint
  always resolves through it). Measured: **a few seconds, up to ~13 s** on a truly
  cold machine (cold OS cache + first `_core` venv materialization — i.e. the first
  question of a work session); later calls reuse both and are near-instant (a warm
  resolve is ~2 ms). Don't pay that boot on the human's first question — **warm it
  at the start** (see [Make it appear instantly](#make-it-fast)).
- **No project, environment, or venv *config*** is needed for
  question/approval/plan widgets — they are **static** (only `text`/inputs/`button`,
  no `sql`/`{{ref}}`), so there's nothing to *resolve*. (The Python `dev serve`
  daemon still boots and first paint still routes through it — it just hands the
  config straight back.) You only need a configured environment + venv once you add
  a **data-bound** component (a chart/table with SQL) — see
  [Going further](#going-further-show-data).

## The one-shot loop (the default)

1. **Author** a JSON-UI config — a `div` wrapping some `text`, input components
   (each with a `param`), and one or more `submit` buttons (each with a distinct
   `action`).
2. **Open** it and **block** for the human. Pass the config **inline** (one call,
   no scratch file) or **from a file** — but not both (passing a config *and* a
   path errors):
   - **Inline via stdin** (`--config -`) — the robust one-call path; piping avoids
     shell-quoting a JSON blob full of labels/quotes/`$`. Ideal for one-shot asks:
     ```bash
     printf '%s' "$CONFIG_JSON" | fused widget open --config - --port 4477 --timeout 600
     ```
     (`-c '<json>'` accepts a literal string too, but stdin is safer.)
   - **From a file** — use this when you want **edit-and-refresh** (the app
     hot-reads the file on each render) or the parley revise loop:
     ```bash
     fused widget open /abs/path/ask.json --port 4477 --timeout 600
     ```
3. **Read** the single JSON line on stdout — the human's answer.

### Worked example — an approval

`approve.json`:

```json
{
  "type": "div",
  "props": { "style": "display:grid; gap:16px; padding:20px; max-width:640px" },
  "children": [
    { "type": "text", "props": { "value": "Deploy build #1423 to production?", "variant": "h3" } },
    { "type": "text", "props": { "value": "Promotes the current preview to the release channel.", "variant": "muted" } },
    { "type": "text-area", "props": { "param": "comment", "label": "Notes (optional)", "placeholder": "Anything to flag…", "rows": 3 } },
    { "type": "div", "props": { "style": "display:flex; gap:12px" }, "children": [
      { "type": "button", "props": { "label": "Approve", "action": "approve", "submit": true, "variant": "primary" } },
      { "type": "button", "props": { "label": "Reject",  "action": "reject",  "submit": true, "variant": "secondary" } }
    ]}
  ]
}
```

```bash
fused widget open /abs/path/approve.json --port 4477 --timeout 600
```

Or skip the scratch file and pipe the same config inline (one call):

```bash
printf '%s' "$APPROVE_JSON" | fused widget open --config - --port 4477 --timeout 600
```

The human's browser opens, they pick a button, and stdout gets **one line**:

```json
{"action":"approve","params":{"comment":"ship it, watch error rate"}}
```

You branch on `action` (`"approve"` vs `"reject"`) and read `params.comment`.

## The response contract (exact)

stderr carries logs + the page URL. **stdout is the answer channel** — exactly one
JSON line in default mode:

| Outcome | stdout | Exit |
|---|---|---|
| The human pressed a `submit` button | `{"action":"<name>","params":{…}[,"actions":[…]]}` | `0` |
| The human closed the tab (or refreshed) | `{"action":"closed","params":{…}}` | `0` |
| `--timeout` elapsed with no answer | `{"action":"timeout"}` | `3` |
| Ctrl-C while waiting | `{"action":"interrupted"}` | `130` |
| App wouldn't start / died / unknown widget | *(no stdout)* — message on stderr | `1` |

- **`action`** is the pressed button's `action` name, or `"closed"`/`"timeout"`/
  `"interrupted"`.
- **`params`** is the full param snapshot — every input's current value, keyed by
  its `param`. (`actions` only appears if you used non-`submit` buttons; for
  simple asks it's absent.)
- **`"closed"` is not consent.** Treat `closed`/`timeout`/`interrupted` as *no
  decision* — re-ask or fall back; never read a tab-close as approval.
- **`checkbox-group` writes an array** (`"steps":["lint","test"]`); every other
  input writes a scalar.

## Components you'll use

Author each node as `{ "type": …, "props": { … }, "children"?: [ … ] }`. Inputs
carry a **`param`** (the answer key) and usually a **`defaultValue`**. Full prop
tables: **[references/components.md](references/components.md)**.

| Need | Component | Writes to `param` |
|---|---|---|
| Heading / body / hint text | `text` (`variant`: `h1`–`h4`, `default`, `muted`, `small`, `large`) | — |
| Static rich text (lists, bold) | `html` (`value` is verbatim HTML — no substitution) | — |
| **Single choice** | `dropdown` (`options: [{value,label?}]`) | scalar string |
| **Multi choice** | `checkbox-group` (`options`, `defaultSelected`) | **string[]** |
| Short free text | `text-input` | scalar string |
| Long free text | `text-area` (`rows`) | scalar string |
| A number | `number-input` (`min`/`max`/`step`) or `slider` | scalar number |
| A date/time | `datetime-input` | scalar string |
| Layout container | `div` (CSS via `style`) | — |
| **The decision** | `button` (`action`, `submit:true`, `variant`) | — (reports the action) |

**Button rules (the part that makes it work):**
- A **`submit: true`** button is what **unblocks** `widget open`. A button without
  it is an intermediate signal (the page stays open) — don't use it for the final
  answer.
- Give each submit button a **distinct `action`** name so you can tell which was
  pressed.
- `variant: "primary"` for the main action, `"secondary"` for alternatives.

## <a name="make-it-fast"></a>Make it appear instantly

The human's first question is slow **only because the runtime cold-boots two
servers lazily, while they wait** — the widget-host *and* the Python `dev serve`
daemon (a few seconds, **up to ~13 s** cold). Once both are up, the resolve is
**~2 ms** and a warm `widget open` is **~0.4 s** + the browser. So the whole game
is: **pay the boot before there's a question, and reuse one warm widget-host.** Three
moves, in order:

**1 — Pin a port the skill owns.** The default `4410` is *reused if anything
already answers there* — a foreign/stale widget-host makes your widget 404 (the slow,
confusing failure). Claim a dedicated port up front and pass it on every command:
```bash
export OPENFUSED_WIDGET_HOST_PORT=4477     # then --port 4477 on every open/push/watch
```

**2 — Warm it in the background, immediately.** The moment a widget looks likely,
fire a throwaway `push` **in the background** (Bash `run_in_background: true`).
`push` does a server-side resolve, so it boots **both** the app *and* the daemon —
unlike `open --no-open`, which boots only the app and leaves the ~13 s daemon
spawn for the human's first paint. Pipe the placeholder inline with `--config -`
so there's no temp file to manage:
```bash
printf '{"type":"text","props":{"value":"warming up…"}}' | fused widget push --config - --no-open --port 4477
```
By the time you author the real question, the visible call is the ~0.4 s warm
path, not ~13 s.

**3 — For more than one ask, use the parley — not repeated `open`.** Each
one-shot `open` opens a **new browser tab and reloads a ~2 MB SPA**. The parley
keeps **one** tab and re-renders **in place over SSE** on each `push` — no new
tab, no re-handshake, no bundle re-parse — so the 2nd…Nth questions are
effectively instant. Open the human's tab early with a placeholder (loads the
bundle once while you think), then `push` the real question into it. See
**Iterative planning — the parley**, below.

## Running it cleanly in Claude Code (blocking & timeouts)

`widget open` **blocks** until the human acts (up to `--timeout`, default 600s),
and the Bash tool has its own timeout, so:

- **Quick confirmations (< ~90s):** foreground with a short `--timeout` and a
  matching Bash `timeout`:
  ```bash
  fused widget open /abs/path/ask.json --port 4477 --timeout 90
  ```
  (Set the Bash tool `timeout` a little above `--timeout`.)
- **Anything open-ended (recommended default):** run it **in the background**
  (Bash `run_in_background: true`) so it can wait minutes without tripping the
  tool timeout. You're re-invoked when it exits; read the captured stdout (the
  one JSON line):
  ```bash
  fused widget open /abs/path/ask.json --port 4477 --timeout 1800
  ```
- For a one-shot ask, **`--config -`** skips the scratch file — pipe the JSON in
  on stdin. Use an **absolute file path** instead when you want edit-and-refresh or
  the parley revise loop. Either way the browser opens automatically; pass
  **`--no-open`** on a headless/remote box to just print the page URL to stderr.
- If `fused` isn't on `PATH`, prefix with `uv run` from the source checkout.

## Iterative planning — the parley

For a **standing** back-and-forth (push plan v1 → human reacts → push v2 → …) use
the **parley** instead of one-shot `open`: `fused widget push <file>` updates
one persistent page, and `fused widget watch` streams the human's events back
as NDJSON. It's also the **fast path for any multi-ask flow**: one tab, the ~2 MB
SPA parsed once, and each push re-renders in place over SSE — so repeated
questions skip the new-tab + bundle reload that one-shot `open` pays every time.

> **Push a named file for the revise loop — not `--config`.** Inline pushes
> (`push --config -`) are **fire-and-forget**: the config lives only in memory, so
> there's nothing to hot-read and the parley `status.source` is null. For the
> revise loop (edit → re-push as the human reacts/comments), push a **named
> `.json`** and keep editing that file — or pass `push --config - --source
> /abs/plan.json` to point the edit anchor at a file you maintain, so the
> comment-agent can patch the source.

**React live with a Monitor — don't poll.** `watch` streams forever, so a plain
background task only notifies you when it *exits* (it never does). Run `watch` as a
**`Monitor`** (`persistent: true`) so each event line wakes you the instant the
human acts; then parse it, author the next view, and `push`. Arm the Monitor
**before** the first push:

```
Monitor(description: "parley human events", persistent: true,
        command: "fused widget watch --port 4477 --from latest")
```

`--from` selects the replay start: **`latest`** (default — only events after the
current `lastSeq`, the usual choice when arming before the first push), **`all`**
(replay every event from seq 0, e.g. reattaching to an in-progress session), or a
**numeric `SEQ`** (resume strictly after that sequence number).
```bash
fused widget push /abs/path/plan-v1.json --port 4477   # then: react → push → repeat
```

Each notification is an **event, not a user reply.** A terminal `action`
(`"terminal":true`) is a submit and carries the **full `params` snapshot** (the
human's whole state — no `--verbose`); a non-terminal `action` is an intermediate
signal; `close` is "stepped away," not "done." The Monitor stays armed across
pushes — `TaskStop` it when the collaboration ends. Full loop:
**[references/parley.md](references/parley.md)**.

## CLI-native comment feedback — `widget agent`

The parley also carries a **comment loop with no flow app** — two terminals and a
browser. The human pins comments directly onto the widget on the parley page, and
`fused widget agent` turns each comment into a **file edit** and re-pushes the
updated view. Use it when the human's feedback is best expressed *on* the widget
("this axis should be log", "drop this column", "make this the headline number")
rather than as a form submit.

```bash
# terminal 1 — serve a file-backed widget onto the parley (opens the page)
fused widget push /abs/path/dashboard.json --port 4477
# ...or for a widget whose data comes from a project's scripts/ UDFs (e.g. {{session_cost}}):
fused widget push /abs/path/dashboard.json --project-dir /abs/path/to/project --port 4477

# terminal 2 — turn the human's comments into file edits (needs `claude` on PATH)
# START THIS BEFORE the human comments — it acts on the live event stream, not a replay.
fused widget agent --port 4477            # --model <m> overrides the worker model (default claude-sonnet-4-6)
```

On the page the human presses **`C`** (or clicks the bottom-right comment **FAB**),
pins a comment to a node, and `widget agent` spawns a `claude -p` worker per open
comment, edits the backing `.json`, re-pushes so the widget updates in place, and
marks the comment resolved. Workers run in parallel across disjoint nodes and
serialize on the same/nested node; the agent is the **single writer** of the file.

**Start `agent` before the human comments — ordering matters.** `widget agent`
reacts to the parley's **live** SSE stream ("the instant a comment appears"); it
does **not** replay comments pinned while it wasn't running. So the sequence is
`push` the view → start `widget agent` → *then* tell the human to comment. A
comment dropped before the agent is up is not actioned — nudge the human to re-pin
it (or restart the loop) rather than waiting.

**Lifecycle — it's a foreground long-runner, not a one-shot.** Unlike `widget
open` (blocks, prints one JSON line, exits) or `widget verify` (one-shot data
envelope), `widget agent` **boots/reuses the widget-host and runs in the
foreground until Ctrl-C**. It has **no stdout answer contract** — its "output" is
the side effects you watch in the browser: comments flip to in-progress, the file
is edited, the view re-pushes (~1 s) and re-resolves, the comment resolves
(progress logs go to stderr). Run it in its own terminal (or a background task)
for the life of the comment session and stop it with Ctrl-C when done.

**The editability gate — the view must be file-backed.** Comment authoring is
enabled **only when the pushed view has a `source`** (mirrors `status.source`):

| Push form | `source` | Comment authoring |
|---|---|---|
| A **`.json` file path** (`push /abs/plan.json`) | the file | **on** — agent edits that file |
| `--config --source /abs/plan.json` | the declared file | **on** — agent edits that file |
| `--project-dir` on a `.json` path | the file | **on**, *and* project UDFs resolve (`?projectDir=` mode) |
| Plain inline `--config` (no `--source`) | `null` | **off** — page shows a "not file-backed, comments won't be actioned" note |
| A `{project, stem}` push | `null` | **off** — resolves but is not editable |

So `--project-dir` on a `.json` path is the **only** push form that is both
project-addressed (resolves `scripts/` UDFs + `{{endpoint}}` refs under the project
`.venv`) **and** editable — the entry point to feedback mode for a real project
widget. The agent reads `status.projectDir` and **echoes it on every re-push**, so a
`--project-dir` view keeps resolving in `?projectDir=` mode across comment edits
(without it the re-push would fall back to flat `?dir=` and break the project's UDF
refs). The `widget agent` verb is separate from `widget watch`/manual planning —
reach for `agent` when you want comments actioned automatically; drive the parley
by hand (§ above) when you're authoring successive views yourself.

## Recipes

Copy-paste templates for the common asks — single/multi choice, free text,
approval-with-comment, and a multi-field plan review — are in
**[references/recipes.md](references/recipes.md)**.

## Going further: show data

Everything above is **static** (no environment needed). To put **live data** in
front of the human (a chart of affected rows, a table of files a migration
touches), add a data-bound component (`sql-table`, `bar-chart`, a map) whose
`sql` reads a UDF via `{{ref}}`. That needs a resolved Fused environment and a
project venv — out of scope here; see the **`fused-widgets`** skill.

## <a name="vs-askuserquestion"></a>vs. AskUserQuestion

Claude Code's built-in `AskUserQuestion` is great for a fast, in-terminal
multiple-choice. Use **this skill** when you want a **visual** surface: free-text
alongside choices, a plan laid out for review, several fields at once, or a
persistent page you iterate on with the parley.

## Troubleshooting

If `widget open`/`push` errors out, it's almost always **environment**, not the
config. Check in this order:

1. **Is `fused` healthy?** Run `fused --version`. A traceback / `No module
   named …` means the install is broken — reinstall it (e.g. `uv tool install
   --reinstall --editable .` from the source checkout, or `pip install -U
   fused`). Inside a source checkout, prefer `uv run fused …`.
2. **`… did not hand-shake within 30s` / `No such command 'data-serve'` / `Cannot
   GET /widget-file/…`** — a **stale widget-host build** is being booted (its bundled
   viewer code predates the current data daemon). Fix the bundle, not the config: from a
   source checkout rebuild it (`cd widget-host && pnpm build`) or reinstall `fused`
   from a current source so it ships a fresh `widget-host/dist`.
3. **A foreign/stale widget-host is squatting the port → "Cannot GET /widget-file/…" in
   the browser.** The widget-host binds one loopback port (default `4410`) and **reuses
   whatever already answers there**. If another process (e.g. a stale dev server
   or a stale build) holds the port, a widget command
   reuses it and the browser 404s. The tell: it answers `/health` with `200`
   but `GET /widget-file/<id>` returns **`Cannot GET`** (no viewer bundle).
   **Preflight** the port before opening:
   ```bash
   # a stale bundle answers /health but 404s the viewer routes; free it or use another
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4410/health
   lsof -nP -iTCP:4410 -sTCP:LISTEN     # who holds it
   ```
   Fix: free the port (`kill <pid>`) so a current widget-host boots, **or** pin a
   dedicated port the skill owns (below). Note: a fresh `--port` *forces a new
   boot*, which also surfaces a stale bundle (item 2) that port-reuse was hiding.
4. **Verify headlessly** before involving a human — the answer should be a clean
   timeout, not an error:
   ```bash
   fused widget open /abs/path/ask.json --no-open --timeout 8
   # expect: {"action":"timeout"}  (exit 3), and a "widget page: …/widget-file/…" line on stderr
   ```

## Gotchas

- **`closed` ≠ approved.** A closed tab / timeout means *no answer* — handle it.
- **`checkbox-group` is an array**, scalars otherwise — branch accordingly.
- **Only `submit: true` returns control.** A plain button keeps the page open.
- **`html` does not substitute** `$param`/`{{ref}}` — it renders `value` verbatim.
  For static plan text that's exactly right; for live data use a data-bound node.
- **The widget-host is loopback-bound** (`127.0.0.1:4410`) and single-user — the human
  must be at (or tunneled to) the same machine.
- **First call cold-boots two servers** (a few seconds, up to ~13 s cold — the
  Node app + the Python `dev serve` daemon); reuse is near-instant. Warm them at
  the start — see [Make it appear instantly](#make-it-fast).
- **Unknown `type` is a hard error** — only use components from the catalog
  ([references/components.md](references/components.md)).

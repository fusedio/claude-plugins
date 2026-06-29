"""Read UDF — assemble the human inbox feed (the derived cross-task queue).

Reads ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

This is the **inbox view**: the inbox is a *derivation*, not a fourth store.
It returns the SAME ``{items, pending}`` shape the Express routes
``GET /api/inbox`` (global) and ``GET /api/projects/:name/inbox`` (drill-in)
returned by hand-assembly, so the UI is unchanged.

The inbox owns **no stored array** — every row is derived/projected. It assembles
five sources from the ONE shared ``state.json`` (F1 — every ``_core`` UDF reads the
same file, so there is no cross-project call):

1. **Card-view questions** — pending wake-bearing cards
   (``continuationPolicy == "wake_assignee"``) whose ``effect`` is NOT
   ``review_work_product`` (i.e. ``reply`` / ``approval_gate``), projected as a
   read-only ``type:"question"`` view carrying ``sourceCardId`` + the full
   ``card`` (the pending-question projection,
   now server-side here). The client resolves these through the card route, not
   the inbox respond route.
2. **Work-product review cards** — pending cards whose
   ``effect == "review_work_product"`` (the ``publish_work_product`` fold),
   projected as ``type:"message"`` Updates rows
   carrying ``sourceCardId`` + the full ``card`` so the UI renders the interactive
   card and resolves it through the card route. Non-blocking
   (``continuationPolicy: "none"``), so they never appear in source 1. An open
   review card suppresses the task's derived completion (source 4) — the review
   IS the report.
3. **``notify`` comments** — ``comments[]`` rows with ``kind == "notify"`` (the
   Phase-4 ``notify_user`` → comment swap), projected as ``type:"message"`` Updates
   rows so the UI's Updates feed is unchanged. The row carries the comment id
   (``cmt_…``), so the inbox respond/dismiss routes recognise it and spawn the
   prose→run reply path; a comment id present in ``dismissedFeedbackKeys`` (appended
   on a human reply/dismiss) excludes an acknowledged one (same mechanism as the
   derived items, source 4/5).
4. **Derived ``completion`` items** — for a task whose LATEST run is terminal
   ``completed`` and whose ``status`` is ``completed`` with no open ``notify``
   comment (a ``notify_user`` IS the completion report). Synthetic
   id ``derived:completion:<runId>``.
5. **Derived ``failure`` items** — for a task whose LATEST run is terminal
   ``failed`` and whose ``status`` is ``failed``. Synthetic id ``derived:failure:<runId>``.

Completion/failure are NO LONGER stored (the run lifecycle stopped minting them);
they are derived here from run + task ``status``. A human DISMISS / RESPOND on a
derived item / notify comment appends its synthetic id (``derived:<type>:<runId>``
or ``cmt_<id>``) to the flat ``dismissedFeedbackKeys`` state field (written by the
respond/dismiss routes via ``acknowledgeFeedbackKey``); this view EXCLUDES any
derived item / notify comment whose id is in that set, so a dismissed item does not
re-appear on the next view (the derived-dismissal
handling). The key is run-scoped, so a re-run mints a new id NOT in the set and the
outcome resurfaces.

Params
------
project : str
    Filter to a single project slug. Empty string (the default) is the GLOBAL
    inbox: items across all projects + global pending-triage tasks.

Returns
-------
dict
    ``{"items": list[dict], "pending": list[dict]}``. ``items`` are inbox rows
    (the InboxItem wire shape the UI consumes), newest-first by ``createdAt``;
    ``pending`` are full task records with ``status == "pending"``.
"""

import atexit
import fcntl
import json
import os

# --- per-entity state helpers -------------------------------
# Each top-level collection is its own <app_dir>/state/<key>.json. A write UDF
# names the collection(s) it mutates in `_load_doc(...)`; the helper holds an
# exclusive flock on each `<app_dir>/state/.<key>.lock` sentinel across the whole
# load->save section so concurrent same-collection writers serialize (no lost
# updates). Locking a stable sentinel (never renamed) survives the atomic
# tmp+rename of the data file. This UDF runs as a one-shot subprocess (exactly
# one load->save), so the module-level lock fds + snapshot need no extra guard.
_COLLECTION_KEYS = (
    "tasks",
    "runs",
    "comments",
    "inbox",
    "cards",
    "serveMcp",
    "costEvents",
    "gatePolicies",
    "onboarding",
    "dismissedFeedbackKeys",
)
_COLLECTION_DEFAULTS = {
    "serveMcp": {},
    "gatePolicies": {},
    "onboarding": {"completed": False, "version": 1},
}
_HELD_LOCKS: list[int] = []
_SNAPSHOT: dict[str, str] = {}


def _release_locks() -> None:
    """Release every held flock (idempotent). Registered with atexit so a write
    UDF that returns early or raises before _save_doc still frees its locks
    promptly rather than only on interpreter teardown."""
    while _HELD_LOCKS:
        fd = _HELD_LOCKS.pop()
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass


atexit.register(_release_locks)


def _state_dir() -> str:
    """Resolve <app_dir>/state. ``OPENFUSED_APP_DIR_STATE`` (a DIRECTORY) is used
    verbatim when set (no expanduser); else ~/.openfused/app."""
    env_val = os.environ.get("OPENFUSED_APP_DIR_STATE")
    app_dir = env_val if env_val else os.path.expanduser("~/.openfused/app")
    return os.path.join(app_dir, "state")


def _collection_default(key: str):
    default = _COLLECTION_DEFAULTS.get(key)
    return dict(default) if default is not None else []


def _load_doc(*lock_collections: str) -> dict:
    """Assemble the document from the per-entity files. For each collection in
    *lock_collections* (those this UDF will mutate) hold an exclusive flock on its
    sentinel lock file across load->save (released in ``_save_doc``). A
    present-but-corrupt file RAISES on the write path (so a later save cannot
    clobber it) and falls back to the default on a pure read."""
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    for col in sorted(lock_collections):
        fd = os.open(os.path.join(state_dir, f".{col}.lock"), os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        _HELD_LOCKS.append(fd)
    doc: dict = {}
    for key in _COLLECTION_KEYS:
        path = os.path.join(state_dir, f"{key}.json")
        try:
            with open(path, encoding="utf-8") as fh:
                doc[key] = json.load(fh)
        except FileNotFoundError:
            doc[key] = _collection_default(key)
        except json.JSONDecodeError as exc:
            if key in lock_collections:
                raise RuntimeError(
                    f"{path} is corrupt and could not be parsed ({exc}); "
                    "inspect or restore it before retrying this write."
                ) from exc
            doc[key] = _collection_default(key)
    _SNAPSHOT.clear()
    for key in _COLLECTION_KEYS:
        _SNAPSHOT[key] = json.dumps(doc[key], indent=2, ensure_ascii=False)
    return doc


def _save_doc(doc: dict) -> None:
    """Write each collection whose serialization changed since ``_load_doc`` to its
    own <key>.json via a crash-safe tmp+rename, then release every held lock."""
    state_dir = _state_dir()
    os.makedirs(state_dir, exist_ok=True)
    try:
        for key in _COLLECTION_KEYS:
            if key not in doc:
                continue
            text = json.dumps(doc[key], indent=2, ensure_ascii=False)
            if text == _SNAPSHOT.get(key):
                continue
            dest = os.path.join(state_dir, f"{key}.json")
            tmp = dest + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, dest)
            _SNAPSHOT[key] = text
    finally:
        _release_locks()


# --- end per-entity state helpers ------------------------------------------


# Policies that block the task's assignee (and so surface a card as an inbox
# question). A `none`-policy card never blocks.
_WAKE_POLICIES = ("wake_assignee",)


def _task_index(tasks: list) -> dict:
    """Map task id → task record for the title/number join."""
    return {t.get("id"): t for t in tasks if isinstance(t, dict)}


def _latest_terminal_run_by_task(runs: list) -> dict:
    """Map task id → its LATEST terminal (completed/failed) run record.

    The launcher minted completion/failure for the run that just ended; deriving
    those items from the task's *latest* terminal run reproduces that while
    naturally clearing once the task is retried/resumed (a fresh run is
    `started`, so the task is no longer `completed`/`failed`). Cancelled runs are
    not terminal-for-inbox (the human did it — the launcher minted nothing).
    "Latest" is by createdAt, falling back to list order.
    """
    by_task: dict = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        if run.get("status") not in ("completed", "failed"):
            continue
        task_id = run.get("taskId")
        if task_id is None:
            continue
        prev = by_task.get(task_id)
        if prev is None or (run.get("createdAt", "") >= prev.get("createdAt", "")):
            by_task[task_id] = run
    return by_task


def _acknowledged_feedback_keys(doc: dict) -> set:
    """Synthetic ids of items the human already dismissed/responded to.

    A respond/dismiss on a derived completion/failure OR a notify comment (neither
    has a stored row of its own) appends its synthetic id (`derived:<type>:<runId>`
    or `cmt_<id>`) to the flat `dismissedFeedbackKeys` state field
    (`acknowledgeFeedbackKey`). The view drops any derived item / notify comment
    whose id is in this set, so a dismissed/answered item does not re-appear (the
    derived-dismissal handling, contract.md). Because the key is run-scoped, a
    re-run mints a new id NOT in the set and the outcome resurfaces.
    """
    keys = doc.get("dismissedFeedbackKeys")
    if not isinstance(keys, list):
        return set()
    return {k for k in keys if isinstance(k, str) and k}


def _card_question_view(card: dict, by_id: dict) -> dict:
    """Project a pending wake-bearing card into a `question` inbox view.

    The pending-question projection: the
    card's `summary` is the question body (the only human label); the `widget` is
    the agent-authored render surface, which owns ALL content — there is no
    server-side `details`/`diffPaths` projection. Carries `sourceCardId` + the
    full `card` so the client renders the SAME interactive surface the thread does
    and resolves through the card route (not the inbox respond route).
    """
    payload = card.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    body = card.get("summary") or "(question)"
    task = by_id.get(card.get("taskId"))
    return {
        "id": card.get("id"),
        "project": card.get("project"),
        "type": "question",
        "taskId": card.get("taskId"),
        "agentSlug": card.get("createdBy"),
        "body": body,
        "details": None,
        "diffPaths": None,
        "widget": payload.get("widget"),
        "workProductId": None,
        "createdAt": card.get("createdAt"),
        "resolvedAt": None,
        "response": None,
        "taskTitle": task.get("title") if isinstance(task, dict) else None,
        "taskNumber": task.get("number") if isinstance(task, dict) else None,
        "sourceCardId": card.get("id"),
        "card": card,
    }


def _is_work_product_review_card(card: dict) -> bool:
    """A pending card whose ``effect`` is ``review_work_product``.

    The publish_work_product fold: a review card is
    a system-posted card with ``effect == "review_work_product"``. These are
    non-blocking (``continuationPolicy: "none"``), so they never surface as a
    card-view question (source 1) — only as an Updates review row (source 2).
    """
    return card.get("status") == "pending" and card.get("effect") == "review_work_product"


def _review_card_view(card: dict, by_id: dict) -> dict:
    """Project an open work-product review card into a ``type:"message"`` Updates row.

    The same Updates feed position the old stored review ``message`` held, but
    carrying ``sourceCardId`` + the full ``card`` so the UI renders the interactive
    card and resolves it through the **card route** (the ``review_work_product``
    resolve effect sets the review state + spawns, ``app-artifacts.md`` §4).
    ``workProductId`` is copied from ``payload.effectArgs.workProductId`` (the
    durable key); ``widget`` rides through from ``payload.widget``. Body = the
    card's ``summary``, then ``"(review)"``.
    """
    payload = card.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    effect_args = payload.get("effectArgs")
    effect_args = effect_args if isinstance(effect_args, dict) else {}
    body = card.get("summary") or "(review)"
    task = by_id.get(card.get("taskId"))
    return {
        "id": card.get("id"),
        "project": card.get("project"),
        "type": "message",
        "taskId": card.get("taskId"),
        "agentSlug": card.get("createdBy"),
        "body": body,
        "details": None,
        "diffPaths": None,
        "widget": payload.get("widget"),
        "workProductId": effect_args.get("workProductId"),
        "createdAt": card.get("createdAt"),
        "resolvedAt": None,
        "response": None,
        "taskTitle": task.get("title") if isinstance(task, dict) else None,
        "taskNumber": task.get("number") if isinstance(task, dict) else None,
        "sourceCardId": card.get("id"),
        "card": card,
    }


def _notify_comment_view(comment: dict, by_id: dict) -> dict:
    """Project a ``notify`` comment into a ``type:"message"`` Updates row.

    The Phase-4 swap: ``notify_user`` writes a ``notify``-flagged comment instead
    of a stored ``message`` inbox item. This rebuilds the exact InboxItem wire
    shape the Updates feed expects (so the UI is unchanged), keyed on the comment
    id (``cmt_…``) — the inbox respond/dismiss routes recover the task from the
    comment and spawn the prose→run reply path. ``agentSlug`` is the comment's
    ``author``; ``widget`` rides through (a notify may carry an inline JSON-UI
    widget). ``sourceCardId``/``card`` are null (this is not a card view).
    """
    task = by_id.get(comment.get("taskId"))
    return {
        "id": comment.get("id"),
        "project": task.get("project") if isinstance(task, dict) else None,
        "type": "message",
        "taskId": comment.get("taskId"),
        "agentSlug": comment.get("author"),
        "body": comment.get("body") or "",
        "details": None,
        "diffPaths": None,
        "widget": comment.get("widget"),
        "workProductId": None,
        "createdAt": comment.get("createdAt") or "",
        "resolvedAt": None,
        "response": None,
        "taskTitle": task.get("title") if isinstance(task, dict) else None,
        "taskNumber": task.get("number") if isinstance(task, dict) else None,
        "sourceCardId": None,
        "card": None,
    }


def _derived_item(item_type: str, run: dict, task: dict, body: str) -> dict:
    """Build a derived completion/failure inbox item from a terminal run + task.

    The synthetic id `derived:<type>:<runId>` is stable for a given run, so the
    UI keys/render it consistently and the respond/dismiss routes can recover the
    run + task from it. agentSlug is null (system-raised, like the old stored
    lifecycle items). createdAt is the run's finishedAt (falling back to its
    createdAt) so the newest-first sort places it correctly.
    """
    run_id = run.get("id", "")
    created_at = run.get("finishedAt") or run.get("createdAt") or ""
    return {
        "id": f"derived:{item_type}:{run_id}",
        "project": task.get("project"),
        "type": item_type,
        "taskId": task.get("id"),
        "agentSlug": None,
        "body": body,
        "details": None,
        "diffPaths": None,
        "widget": None,
        "workProductId": None,
        "createdAt": created_at,
        "resolvedAt": None,
        "response": None,
        "taskTitle": task.get("title"),
        "taskNumber": task.get("number"),
        "sourceCardId": None,
        "card": None,
    }


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def inbox_view(project: str = "", app_dir: str = "") -> dict:
    """Assemble the inbox feed {items, pending} from the shared state.json.

    Args:
        project: project slug to scope to; empty string is the global inbox.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc()
    tasks: list = doc.get("tasks") or []
    runs: list = doc.get("runs") or []
    cards: list = doc.get("cards") or []
    comments: list = doc.get("comments") or []

    by_id = _task_index(tasks)
    # `acked` keys cover BOTH the derived completion/failure synthetic ids AND a
    # notify comment's `cmt_…` id (a human reply/dismiss appends the id to
    # `dismissedFeedbackKeys`), so a replied/dismissed notify comment drops out of
    # Updates the same way an acked derived item does.
    acked = _acknowledged_feedback_keys(doc)

    items: list = []

    # The inbox owns no stored array — every row is derived/projected.
    # (1) Card-view questions — pending wake-bearing cards (reply / approval_gate;
    #     effect != review_work_product).
    # (2) Work-product review cards — pending cards with effect ==
    #     review_work_product (non-blocking, continuationPolicy "none"), so they
    #     are NOT wake-policy cards and surface only as Updates review rows.
    review_card_task_ids: set = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        if project and card.get("project") != project:
            continue
        if (
            card.get("status") == "pending"
            and card.get("continuationPolicy") in _WAKE_POLICIES
            and card.get("effect") != "review_work_product"
        ):
            items.append(_card_question_view(card, by_id))
        elif _is_work_product_review_card(card):
            review_card_task_ids.add(card.get("taskId"))
            items.append(_review_card_view(card, by_id))

    # (3) notify comments — comments[] rows flagged kind=="notify" (the Phase-4
    # notify_user → comment swap), projected as Updates `message` rows. An acked
    # one (whose comment id is in dismissedFeedbackKeys) is excluded.
    open_notify_task_ids: set = set()
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        if comment.get("kind") != "notify":
            continue
        cmt_id = comment.get("id")
        if isinstance(cmt_id, str) and cmt_id in acked:
            continue
        task = by_id.get(comment.get("taskId"))
        comment_project = task.get("project") if isinstance(task, dict) else None
        if project and comment_project != project:
            continue
        open_notify_task_ids.add(comment.get("taskId"))
        items.append(_notify_comment_view(comment, by_id))

    # (4)/(5) Derived completion / failure — from the task's LATEST terminal run.
    latest_terminal = _latest_terminal_run_by_task(runs)
    # Tasks with an OPEN notify report (notify_user IS the completion report) OR an
    # open work-product REVIEW CARD get no derived completion — an open review IS the
    # report (mirrors the launcher's `!hasUnresolvedMessage`).
    tasks_with_open_message = open_notify_task_ids | review_card_task_ids
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if project and task.get("project") != project:
            continue
        task_id = task.get("id")
        run = latest_terminal.get(task_id)
        if run is None:
            continue
        status = task.get("status")
        if run.get("status") == "completed" and status == "completed":
            if task_id in tasks_with_open_message:
                continue
            key = f"derived:completion:{run.get('id', '')}"
            if key in acked:
                continue
            body = (run.get("summary") or "").strip() or "Task completed."
            items.append(_derived_item("completion", run, task, body))
        elif run.get("status") == "failed" and status == "failed":
            key = f"derived:failure:{run.get('id', '')}"
            if key in acked:
                continue
            body = (run.get("errorMessage") or "").strip() or "run failed"
            items.append(_derived_item("failure", run, task, body))

    # Newest-first by createdAt.
    items.sort(key=lambda i: i.get("createdAt") or "", reverse=True)

    pending = [
        t
        for t in tasks
        if isinstance(t, dict)
        and t.get("status") == "pending"
        and (not project or t.get("project") == project)
    ]

    return {"items": items, "pending": pending}

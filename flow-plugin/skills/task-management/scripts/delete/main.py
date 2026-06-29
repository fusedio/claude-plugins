"""Delete UDF — hard-deletes a task and all its transitive descendants,
cascading to all related records in every collection.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

Params
------
id : str
    The task id to delete.

Returns
-------
dict
    On success: camelCase ack with counts per collection::

        {
            "deletedTaskIds": [...],
            "runsRemoved": N,
            "commentsRemoved": N,
            "inboxRemoved": N,
            "cardsRemoved": N,
            "costEventsRemoved": N,
        }

    When the task is not found: ``{"ok": false, "error": "not found"}``.

Cascade semantics
-----------------
Mirrors ``TasksStore.delete_task`` exactly:

1. If no task with ``id`` exists, return the not-found ack (instead of
   raising ``TaskNotFoundError`` — over the UDF boundary an informative ack
   is more useful than an exception).
2. Collect the transitive descendant set: BFS over ``doc["tasks"]`` following
   ``parentId``, starting from ``id``.  A visited/seen guard ensures
   termination even if a cycle exists in the data.
3. Cascade-remove every record whose camelCase ``taskId`` is in the deleted
   set from each of: ``runs``, ``comments``, ``inbox``, ``cards``, and
   ``costEvents``.  Missing or absent keys are treated as empty lists.
4. Remove the deleted tasks from ``doc["tasks"]``.
5. Scrub every REMAINING task's ``blockedBy`` list of any deleted id.
6. Save and return the ack.
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


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def delete(id: str = "", app_dir: str = "") -> dict:
    """Hard-delete a task and its transitive descendants with full cascade.

    Args:
        id: the task id to delete.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc("cards", "comments", "costEvents", "inbox", "runs", "tasks")
    tasks: list[dict] = doc.get("tasks") or []

    # Step 1 — verify target exists
    if not any(t.get("id") == id for t in tasks):
        return {"ok": False, "error": "not found"}

    # Step 2 — collect transitive descendant set (target + all children)
    # Build a parent→children map for efficient BFS
    children_map: dict[str, list[str]] = {}
    for t in tasks:
        parent_id = t.get("parentId")
        if parent_id is not None:
            children_map.setdefault(parent_id, []).append(t["id"])

    deleted: set[str] = set()
    worklist = [id]
    while worklist:
        current = worklist.pop()
        if current in deleted:
            continue  # cycle guard
        deleted.add(current)
        for child_id in children_map.get(current, []):
            if child_id not in deleted:
                worklist.append(child_id)

    # Step 3 — cascade: remove related records whose taskId is in deleted
    runs: list[dict] = doc.get("runs") or []
    original_runs = len(runs)
    runs = [r for r in runs if r.get("taskId") not in deleted]
    runs_removed = original_runs - len(runs)

    comments: list[dict] = doc.get("comments") or []
    original_comments = len(comments)
    comments = [c for c in comments if c.get("taskId") not in deleted]
    comments_removed = original_comments - len(comments)

    inbox: list[dict] = doc.get("inbox") or []
    original_inbox = len(inbox)
    inbox = [i for i in inbox if i.get("taskId") not in deleted]
    inbox_removed = original_inbox - len(inbox)

    cards: list[dict] = doc.get("cards") or []
    original_cards = len(cards)
    cards = [c for c in cards if c.get("taskId") not in deleted]
    cards_removed = original_cards - len(cards)

    cost_events: list[dict] = doc.get("costEvents") or []
    original_cost_events = len(cost_events)
    cost_events = [ce for ce in cost_events if ce.get("taskId") not in deleted]
    cost_events_removed = original_cost_events - len(cost_events)

    # Step 4 — remove the deleted tasks
    tasks = [t for t in tasks if t.get("id") not in deleted]

    # Step 5 — scrub deleted ids from remaining tasks' blockedBy
    for t in tasks:
        blocked_by: list[str] = t.get("blockedBy") or []
        if any(bid in deleted for bid in blocked_by):
            t["blockedBy"] = [bid for bid in blocked_by if bid not in deleted]

    # Write back all mutated lists; all other keys are untouched
    doc["tasks"] = tasks
    doc["runs"] = runs
    doc["comments"] = comments
    doc["inbox"] = inbox
    doc["cards"] = cards
    doc["costEvents"] = cost_events

    _save_doc(doc)

    return {
        "deletedTaskIds": sorted(deleted),
        "runsRemoved": runs_removed,
        "commentsRemoved": comments_removed,
        "inboxRemoved": inbox_removed,
        "cardsRemoved": cards_removed,
        "costEventsRemoved": cost_events_removed,
    }

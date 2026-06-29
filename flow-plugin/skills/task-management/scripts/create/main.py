"""Create UDF — gets or appends a task record in the live app state file.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

Params
------
project : str
    Project slug for the new task.
title : str
    Short title.
description : str
    Longer description (defaults to title when empty).
status : str
    Initial status; one of ``pending`` (default) or ``todo``.
parent_id : str
    Parent task id; empty string is stored as null.
created_by : str
    Identity of the creator (default ``"user"``).
work_mode : str
    Work mode (default ``"standard"``).
id : str
    Client-provided task id / idempotency key; empty string mints a new id.
    A repeated id is get-or-create (returns the existing row, no duplicate).

Returns
-------
dict
    The existing or newly created camelCase task record (13 fields).

Not implemented in this POC
---------------------------
- Depth-ceiling check (``would_exceed_depth`` / ``MAX_TASK_DEPTH``): the real
  ``TasksStore.create_task`` raises ``TaskDepthExceededError`` when the parent
  is already at the maximum nesting depth.  That guard requires loading the full
  task tree and walking parent links; it is omitted here to keep the UDF to
  stdlib only.  Upgrade path: port ``task_depth`` + ``would_exceed_depth``
  into the inline helpers, or add a shared helper module once the
  POC graduates to a proper package.
"""

import atexit
import fcntl
import json
import os
import secrets
from datetime import UTC, datetime

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
def create(
    project: str = "",
    title: str = "",
    description: str = "",
    status: str = "pending",
    parent_id: str = "",
    created_by: str = "user",
    work_mode: str = "standard",
    id: str = "",
    app_dir: str = "",
) -> dict:
    """Create a new task, or return the existing task for a repeated id.

    Args:
        project: project slug.
        title: short task title.
        description: longer description; defaults to title when empty.
        status: initial status (``pending`` or ``todo``).
        parent_id: parent task id; empty string → null.
        created_by: identity of the creator.
        work_mode: work mode (``standard`` or other values).
        id: client-provided task id / idempotency key; empty string mints a new id.
        app_dir: storage location override; when non-empty, takes precedence over
            the OPENFUSED_APP_DIR_STATE env var and the ~/.openfused/app default.
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc("tasks")
    tasks: list[dict] = doc.get("tasks") or []

    # Idempotency: a supplied id that already exists is get-or-create — return the
    # existing record untouched so a retried create never duplicates a row.
    if id:
        for t in tasks:
            if t.get("id") == id:
                return t

    # Use the client id when supplied, else mint "task_" + 12 hex chars
    # (matches new_id("task")).
    task_id = id or ("task_" + secrets.token_hex(6))

    # next number = MAX(number for project) + 1, else 1
    max_num = 0
    for t in tasks:
        if t.get("project") == project:
            n = t.get("number", 0)
            if isinstance(n, int) and n > max_num:
                max_num = n
    number = max_num + 1

    # ISO-8601 with milliseconds + Z suffix (matches _now_iso)
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    record: dict = {
        "id": task_id,
        "project": project,
        "number": number,
        "title": title,
        "description": description if description else title,
        "status": status,
        "agentId": None,
        "createdBy": created_by,
        "createdAt": now,
        "updatedAt": now,
        "parentId": parent_id if parent_id else None,
        "workMode": work_mode,
        "blockedBy": [],
    }

    tasks.append(record)
    doc["tasks"] = tasks
    _save_doc(doc)
    return record

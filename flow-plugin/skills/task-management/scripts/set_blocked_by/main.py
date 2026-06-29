"""Set-blocked-by UDF — sets the blockedBy edge on a task record.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

Params
------
id : str
    The task id to update.
blocked_by : str
    Either a JSON array string (``'["t1","t2"]'``) or a comma-separated list
    (``"t1,t2"``).  An empty string sets ``blockedBy`` to ``[]``.

Returns
-------
dict
    The updated camelCase task record on success, or
    ``{"ok": false, "error": "not found"}`` when the task is absent.

Not implemented in this POC
---------------------------
- Cycle detection (``would_form_blocker_cycle``): the real
  ``TasksStore.set_blocked_by`` raises ``BlockerCycleError`` when the proposed
  ``blockedBy`` list would form a dependency cycle.  That guard requires
  traversing the full blocker graph; it is omitted here to keep the UDF to
  stdlib only.  Upgrade path: port ``_would_form_blocker_cycle_in``
  into the inline helpers, or add a shared helper module once the
  POC graduates to a proper package.
"""

import atexit
import fcntl
import json
import os
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


_PARSE_ERROR = object()  # sentinel: caller must check with `is _PARSE_ERROR`


def _parse_blocked_by(raw: str) -> "list | object":
    """Parse the blocked_by string param into a list of ids.

    Accepts:
    - Empty string → []
    - JSON array string: ``'["t1","t2"]'`` → ["t1", "t2"]
    - Comma-separated: ``"t1,t2"`` → ["t1", "t2"]

    Returns the ``_PARSE_ERROR`` sentinel when the input looks like a JSON
    array (starts with ``[``) but is malformed or is not actually a list.
    The caller must test ``result is _PARSE_ERROR`` before using the value.
    """
    raw = raw.strip()
    if not raw:
        return []
    # Input looks like a JSON value — parse strictly; never fall through to CSV.
    if raw.startswith(("[", "{")):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return _PARSE_ERROR
        if not isinstance(parsed, list):
            return _PARSE_ERROR
        return [str(item) for item in parsed]
    # Fall back to comma-separated
    return [item.strip() for item in raw.split(",") if item.strip()]


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def set_blocked_by(id: str = "", blocked_by: str = "", app_dir: str = "") -> dict:
    """Set the blockedBy edge on a task.

    Mirrors ``TasksStore.set_blocked_by`` minus cycle detection.
    The real method no-ops on an absent task; here we return an informative ack
    dict instead so callers can detect the miss.

    Args:
        id: the task id to update.
        blocked_by: JSON array string or comma-separated list of blocker ids;
            empty string sets blockedBy to [].
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc("tasks")
    tasks: list[dict] = doc.get("tasks") or []

    task = next((t for t in tasks if t.get("id") == id), None)
    if task is None:
        return {"ok": False, "error": "not found"}

    parsed = _parse_blocked_by(blocked_by)
    if parsed is _PARSE_ERROR:
        return {"ok": False, "error": f"invalid blocked_by JSON: {blocked_by!r}"}
    task["blockedBy"] = parsed
    task["updatedAt"] = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    doc["tasks"] = tasks
    _save_doc(doc)
    return task

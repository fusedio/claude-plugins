"""add_comment UDF — appends a new comment record to the live app state file.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

Params
------
task_id : str
    The task id to attach the comment to.
author : str
    Identity of the comment author.
body : str
    Comment text.
kind : str
    The comment kind. The empty
    string (the default) is a plain thread ``note``; ``notify`` marks an agent
    ``notify_user`` FYI so the inbox VIEW surfaces it in the Updates feed. Any
    other value is stored verbatim (forward-compatible).
widget : str
    OPTIONAL JSON-UI widget config (a JSON string) a ``notify`` comment may carry
    for inline display in the Updates feed. The empty string (the default) → no
    widget (``None``). Opaque to the UDF — stored as the parsed object.

Returns
-------
dict
    The newly created camelCase comment record. A plain ``note`` carries the 5
    core fields (``id`` (cmt_-prefixed), ``taskId``, ``author``, ``body``,
    ``createdAt``); a ``notify`` comment additionally carries ``kind`` and
    ``widget``. The two marker fields are OMITTED on a plain note so historical
    notes stay byte-identical (read-time backfill treats a missing ``kind`` as
    ``note``).
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
def add_comment(
    task_id: str = "", author: str = "", body: str = "", kind: str = "", widget: str = "", app_dir: str = ""
) -> dict:
    """Append a new comment to state.json and return the created record.

    Args:
        task_id: task id to attach the comment to.
        author: identity of the comment author.
        body: comment text.
        kind: comment kind; "" (default) is a plain ``note``, ``notify`` marks a
            ``notify_user`` FYI the inbox Updates feed surfaces.
        widget: OPTIONAL JSON-UI widget config (a JSON string); "" → no widget.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc("comments")
    comments: list[dict] = doc.get("comments") or []

    # Mint a new id: "cmt_" + 12 hex chars (matches new_id("cmt"))
    comment_id = "cmt_" + secrets.token_hex(6)

    # ISO-8601 with milliseconds + Z suffix (matches _now_iso)
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    record: dict = {
        "id": comment_id,
        "taskId": task_id,
        "author": author,
        "body": body,
        "createdAt": now,
    }
    # The two marker fields are written ONLY when set, so a plain thread note stays
    # byte-identical to the pre-Phase-4 5-field shape (read-time backfill on the app
    # side treats a missing `kind` as "note", a missing `widget` as null). A `notify`
    # comment carries the marker + its optional inline widget (parsed from the JSON
    # string; a daemon-vetted widget arrives well-formed, so a parse error RAISES —
    # better than silently dropping the agent's widget).
    if kind:
        record["kind"] = kind
    if widget:
        record["widget"] = json.loads(widget)

    comments.append(record)
    doc["comments"] = comments
    _save_doc(doc)
    return record

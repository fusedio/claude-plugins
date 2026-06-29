"""Bulk-seed UDF — inserts task + comment records VERBATIM into the live app state.

Unlike ``create`` (which mints ids/numbers/timestamps for a single new task),
``bulk_seed`` restores/seeds whole collections from already-shaped records: it
writes each supplied record exactly as given (preserving
``id``/``number``/``createdAt``/``updatedAt``/``agentId``/``status``/``parentId``/
``blockedBy``) and is **idempotent by ``id``** — a record whose ``id`` already
exists in the collection is skipped (no duplicate, no overwrite).

This is the only supported way to seed app-state from host Python: it goes through
the ``task-management`` UDF layer (the sole writer of the ``tasks``/``comments``
collections) rather than a direct file write, keeping the storage
backing swappable behind the UDF contract.

Writes ``<app_dir>/state/tasks.json`` and ``<app_dir>/state/comments.json`` (or the
directory named by ``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party
imports.

Params
------
tasks : str
    JSON-encoded array of full task records. Empty string / missing → nothing to do.
comments : str
    JSON-encoded array of full comment records. Empty string / missing → nothing to do.

Returns
-------
dict
    ``{"tasks": {"inserted": n, "skipped": m},
       "comments": {"inserted": n, "skipped": m}}``.
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


def _parse_records(raw: str, label: str) -> list:
    """Parse a JSON-encoded array param. Empty string / missing → empty list.

    The boundary is all-strings (params arrive JSON-encoded), so ``raw`` is the
    JSON text of a list. A non-list payload is a caller error and raises with a
    clear message."""
    if not raw:
        return []
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError(f"{label!r} must be a JSON array of records, got {type(value).__name__}")
    return value


def _insert_verbatim(existing: list, incoming: list) -> tuple[int, int]:
    """Append each incoming record VERBATIM to *existing* unless its ``id`` is
    already present. Mutates *existing* in place; returns ``(inserted, skipped)``.
    Preserves insertion order; idempotent by ``id``."""
    seen = {r.get("id") for r in existing if isinstance(r, dict)}
    inserted = 0
    skipped = 0
    for rec in incoming:
        rec_id = rec.get("id") if isinstance(rec, dict) else None
        if rec_id is not None and rec_id in seen:
            skipped += 1
            continue
        existing.append(rec)
        if rec_id is not None:
            seen.add(rec_id)
        inserted += 1
    return inserted, skipped


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def bulk_seed(tasks: str = "", comments: str = "", app_dir: str = "") -> dict:
    """Insert task + comment records VERBATIM, idempotent by ``id`` (seed/restore).

    Args:
        tasks: JSON-encoded array of full task records; empty string → no tasks.
        comments: JSON-encoded array of full comment records; empty string → no comments.

    Returns the per-collection insert/skip counts.
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    incoming_tasks = _parse_records(tasks, "tasks")
    incoming_comments = _parse_records(comments, "comments")

    doc = _load_doc("tasks", "comments")
    existing_tasks: list = doc.get("tasks") or []
    existing_comments: list = doc.get("comments") or []

    t_ins, t_skip = _insert_verbatim(existing_tasks, incoming_tasks)
    c_ins, c_skip = _insert_verbatim(existing_comments, incoming_comments)

    doc["tasks"] = existing_tasks
    doc["comments"] = existing_comments
    _save_doc(doc)

    return {
        "tasks": {"inserted": t_ins, "skipped": t_skip},
        "comments": {"inserted": c_ins, "skipped": c_skip},
    }

"""Delete-project UDF — remove every interaction card for one project.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

This is the feedback-management half of the cross-skill **project-delete**
cascade: it deletes the cards whose camelCase ``project`` field equals the named
project. The flat ``dismissedFeedbackKeys`` set is left alone — a dangling
synthetic-id entry for a deleted project is harmless (its derived item can never
re-appear once the tasks/runs are gone).

Params (all strings)
--------------------
project : str
    The project slug whose interaction cards are removed.

Returns
-------
dict
    A camelCase ack ``{"cardsRemoved": N}``.

Idempotency
-----------
An empty/whitespace ``project`` — and any project with no matching cards — is a
no-op that returns zero and writes nothing, so a re-run never raises.
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
def delete_project(project: str = "", app_dir: str = "") -> dict:
    """Remove every interaction card for ``project`` in one atomic write.

    One ``_load_doc → mutate → _save_doc`` cycle over ``cards``. Idempotent: an
    empty/whitespace ``project`` — or one with no cards — returns
    ``{"cardsRemoved": 0}`` and writes nothing. Leaves ``dismissedFeedbackKeys``
    alone (a harmless dangling set).

    Args:
        project: the project slug whose interaction cards are removed.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir

    # No-op for an empty/whitespace project: never lock or write, never raise.
    if not project.strip():
        return {"cardsRemoved": 0}

    doc = _load_doc("cards")
    cards: list[dict] = doc.get("cards") or []

    remaining = [c for c in cards if c.get("project") != project]
    cards_removed = len(cards) - len(remaining)

    doc["cards"] = remaining
    _save_doc(doc)

    return {"cardsRemoved": cards_removed}

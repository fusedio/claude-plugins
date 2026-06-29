"""Read UDF — returns run records from the live app state file.

Reads ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

Params
------
task_ids : str
    A JSON array string (``'["t1","t2"]'``) or comma-separated list (``"t1,t2"``)
    of task ids to filter on (matched against the camelCase ``taskId`` field).
    Empty string (the default) returns all runs across all tasks; an explicit
    empty set (``"[]"``) returns no runs. Callers pass exactly the task ids they
    will render, so a future read optimisation (caching/indexing keyed by the id
    set) benefits every caller without further changes.

Returns
-------
list[dict]
    Raw camelCase ``RunRecord`` dicts, oldest-first by ``createdAt`` (mirrors
    the Express ``listRuns`` ordering).
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


def _parse_task_ids(raw: str) -> list[str]:
    """Parse the ``task_ids`` filter param into a list of ids.

    Accepts a JSON array string (``'["t1","t2"]'``) or a comma-separated list
    (``"t1,t2"``) — the same shape ``set_blocked_by`` accepts for ``blocked_by``.
    A malformed JSON array yields ``[]``: an under-fetch is safer than silently
    leaking every task's runs on a bad filter.
    """
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    return [item.strip() for item in raw.split(",") if item.strip()]


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def read(task_ids: str = "", app_dir: str = "") -> list:
    """Return run records from state.json, oldest-first by createdAt.

    Args:
        task_ids: JSON array string or comma-separated list of task ids to filter
            on; empty string returns all runs across all tasks.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc()
    runs: list[dict] = doc.get("runs") or []
    # An empty param string means "no filter" (all runs); a present param — even
    # "[]" — scopes to that set (so a zero-task caller gets []). The distinction is
    # made on the RAW string before parsing, since both ""→[] and "[]"→[] parse to
    # an empty list.
    if task_ids.strip():
        wanted = set(_parse_task_ids(task_ids))
        runs = [r for r in runs if r.get("taskId") in wanted]
    return sorted(runs, key=lambda r: r.get("createdAt", ""))

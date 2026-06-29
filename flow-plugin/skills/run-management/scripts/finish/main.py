"""Finish UDF — patches a terminal transition onto an existing run record.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.
Mirrors ``finishRun``.

Params (all strings)
--------------------
id : str
    The run id to finish.
status : str
    The terminal status: ``completed`` / ``failed`` / ``cancelled``.
error_message : str
    Failure message; empty string → null.
error_family : str
    agentbridge ``ErrorFamily``; empty string → null.
retry_not_before : str
    Rate-limit retry hint (ISO timestamp); empty string → null.
summary : str
    Final assistant text; empty string → null.
cost_usd : str
    Cost in USD; parsed with ``float()``; empty string → null.
usage_json : str
    JSON-encoded ``{inputTokens, outputTokens, cachedInputTokens}`` object;
    empty string → null.
model : str
    Model id; empty string → null.

Returns
-------
dict
    The updated camelCase ``RunRecord`` on success (the app reads ``finishedAt``
    off this response), or ``{"ok": false, "error": "not found"}`` when the run
    is absent.
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


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def finish(
    id: str = "",
    status: str = "",
    error_message: str = "",
    error_family: str = "",
    retry_not_before: str = "",
    summary: str = "",
    cost_usd: str = "",
    usage_json: str = "",
    model: str = "",
    app_dir: str = "",
) -> dict:
    """Stamp a terminal transition on a run unconditionally.

    Mirrors ``finishRun(id, patch)``: it
    applies the patch and stamps ``finishedAt`` now. No state-machine
    validation — the app gates legality before calling. Empty strings become
    ``null`` for the nullable fields.

    Args:
        id: the run id to finish.
        status: terminal status (``completed`` / ``failed`` / ``cancelled``).
        error_message: failure message; empty → null.
        error_family: agentbridge error family; empty → null.
        retry_not_before: rate-limit retry hint; empty → null.
        summary: final assistant text; empty → null.
        cost_usd: cost in USD (``float``); empty → null.
        usage_json: JSON usage object; empty → null.
        model: model id; empty → null.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    doc = _load_doc("runs")
    runs: list[dict] = doc.get("runs") or []

    run = next((r for r in runs if r.get("id") == id), None)
    if run is None:
        return {"ok": False, "error": "not found"}

    run["status"] = status
    run["errorMessage"] = error_message or None
    run["errorFamily"] = error_family or None
    run["retryNotBefore"] = retry_not_before or None
    run["summary"] = summary or None
    run["model"] = model or None
    run["costUsd"] = float(cost_usd) if cost_usd else None
    run["usage"] = json.loads(usage_json) if usage_json else None
    run["finishedAt"] = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    doc["runs"] = runs
    _save_doc(doc)
    return run

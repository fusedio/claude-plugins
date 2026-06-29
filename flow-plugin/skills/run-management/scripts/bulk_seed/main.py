"""Bulk-seed UDF — restore run records + per-run transcripts VERBATIM.

The seed/restore counterpart of ``create``: it inserts caller-supplied
``RunRecord``s into ``<app_dir>/state/runs.json`` **without minting** any
``id``/timestamp/status, and writes per-run NDJSON transcripts to
``<app_dir>/runs/<runId>.ndjson``. It is idempotent by ``id`` (a run whose ``id``
already exists is skipped, never duplicated or overwritten) and by transcript file
(a ``runs/<runId>.ndjson`` that already exists is skipped). This is the FIRST
transcript WRITER in run-management — the ``transcript`` UDF stays read-only.

Used to seed the shipped pre-built showcase project's run history on first boot.
Writes through the UDF layer (never a direct file write) so the storage backing
stays swappable behind the UDF contract.

Params (both JSON-encoded strings — the all-strings boundary)
------
runs : str
    A JSON array of full ``RunRecord`` dicts. Each record is inserted VERBATIM
    (its own ``id``/``taskId``/``status``/``createdAt``/``finishedAt``/``costUsd``/
    ``usage``/… preserved). ``""``/missing → nothing to insert.
transcripts : str
    A JSON object ``{ "<runId>": [<RunEvent>, …], … }``. Each list is written as
    one ``json.dumps(event)`` per line to ``<app_dir>/runs/<runId>.ndjson``,
    path-confined to ``runs/`` and skipped if the file already exists. ``""``/
    missing → no transcripts.

Returns
-------
dict
    ``{"runs": {"inserted": n, "skipped": m},
       "transcripts": {"written": n, "skipped": m}}``.
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


def _app_dir() -> str:
    """Resolve the app directory (the dir that holds state/ and runs/).

    ``OPENFUSED_APP_DIR_STATE`` is a DIRECTORY; when set it is used verbatim (no
    expanduser). Otherwise fall back to ``~/.openfused/app``.
    Distinct from ``_state_dir()`` (which appends ``state``) so the caller can
    join ``runs/<id>.ndjson`` — copied from ``transcript/main.py``.
    """
    env_val = os.environ.get("OPENFUSED_APP_DIR_STATE")
    if env_val:
        return env_val
    return os.path.expanduser("~/.openfused/app")


def _state_dir() -> str:
    """Resolve <app_dir>/state. ``OPENFUSED_APP_DIR_STATE`` (a DIRECTORY) is used
    verbatim when set (no expanduser); else ~/.openfused/app."""
    env_val = os.environ.get("OPENFUSED_APP_DIR_STATE")
    app_dir = env_val if env_val else os.path.expanduser("~/.openfused/app")
    return os.path.join(app_dir, "state")


def _transcript_path(run_id: str) -> str | None:
    """Resolve the transcript path, confined to the ``runs/`` directory.

    ``run_id`` is caller-controlled, so a traversal-shaped value (``..``, an
    absolute path, a symlink) must not let the UDF write ``.ndjson`` files outside
    ``runs/``. The resolved real path must be a direct child of the real ``runs/``
    directory; otherwise return ``None`` (the caller counts it as skipped). A valid
    run id is a flat ``run_<hex>`` with no separators. Copied from
    ``transcript/main.py``.
    """
    runs_dir = os.path.realpath(os.path.join(_app_dir(), "runs"))
    path = os.path.realpath(os.path.join(runs_dir, f"{run_id}.ndjson"))
    if os.path.dirname(path) != runs_dir:
        return None
    return path


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


def _parse_list(raw: str, label: str) -> list:
    """json.loads a JSON-array string param; ""/missing → []. Require a list."""
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must be a JSON array, got {type(parsed).__name__}")
    return parsed


def _insert_if_absent(collection: list[dict], records: list) -> dict:
    """Append each record whose ``id`` is new (insertion order preserved); skip the
    rest. Returns ``{"inserted": n, "skipped": m}``. Mutates *collection* in place."""
    existing = {r.get("id") for r in collection if isinstance(r, dict)}
    inserted = 0
    skipped = 0
    for rec in records:
        rec_id = rec.get("id") if isinstance(rec, dict) else None
        if rec_id in existing:
            skipped += 1
            continue
        collection.append(rec)
        existing.add(rec_id)
        inserted += 1
    return {"inserted": inserted, "skipped": skipped}


def _write_transcripts(transcripts: dict) -> dict:
    """Write each ``{runId: [events]}`` to ``<app_dir>/runs/<runId>.ndjson`` (one
    JSON object per line + trailing newline), atomically. Path-confined to
    ``runs/`` (a traversal-shaped id → skipped) and skipped if the file exists.
    Returns ``{"written": n, "skipped": m}``."""
    written = 0
    skipped = 0
    for run_id, events in transcripts.items():
        path = _transcript_path(run_id)
        if path is None or os.path.exists(path):
            # traversal-shaped id OR file already present → idempotent skip.
            skipped += 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = "".join(json.dumps(ev, ensure_ascii=False) + "\n" for ev in events)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        written += 1
    return {"written": written, "skipped": skipped}


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def bulk_seed(runs: str = "", transcripts: str = "", app_dir: str = "") -> dict:
    """Insert run records + per-run transcripts VERBATIM, idempotent by id/file.

    The seed/restore counterpart of ``create``: it never mints ids/timestamps/
    status. A run whose ``id`` already exists in ``runs.json`` is skipped (no
    duplicate, no overwrite); a transcript whose ``runs/<runId>.ndjson`` already
    exists is skipped.

    Args:
        runs: JSON array of full ``RunRecord`` dicts (insert-if-absent by ``id``).
        transcripts: JSON object ``{runId: [event, …]}`` written one event per
            line to ``runs/<runId>.ndjson``, path-confined to ``runs/``.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    run_records = _parse_list(runs, "runs")

    raw_transcripts = json.loads(transcripts) if transcripts else {}
    if not isinstance(raw_transcripts, dict):
        raise ValueError(f"transcripts must be a JSON object, got {type(raw_transcripts).__name__}")

    doc = _load_doc("runs")
    collection: list[dict] = doc.get("runs") or []
    runs_result = _insert_if_absent(collection, run_records)
    doc["runs"] = collection
    _save_doc(doc)

    transcripts_result = _write_transcripts(raw_transcripts)

    return {"runs": runs_result, "transcripts": transcripts_result}

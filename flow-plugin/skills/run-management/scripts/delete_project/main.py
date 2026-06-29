"""Delete-project UDF — remove every run record (and its transcript) for one project.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.

This is the run-management half of the cross-skill **project-delete** cascade:
it deletes the run records belonging to the named project, and removes each
removed run's per-run transcript ``<app_dir>/runs/<runId>.ndjson``. It is the
FIRST destructive write op in run-management — only ``bulk_seed`` wrote before
(``transcript`` stays read-only, ``create``/``finish``/… only mutate single
records). It REUSES ``_transcript_path`` (copied from ``transcript``/``bulk_seed``)
so a traversal-shaped run id can never delete an ``.ndjson`` file outside
``runs/``.

Matching a run for removal
--------------------------
Run records do NOT carry a ``project`` field: ``create`` stamps only ``taskId``,
so a real (live) run has a ``taskId`` but no ``project`` (only ``bulk_seed``-
restored records may carry one). Matching on ``project`` alone would miss every
live run. So a run is removed if EITHER:

- its ``taskId`` is in *task_ids* — the project's deleted task ids, passed by Flow
  from ``task-management.delete_project``'s ``deletedTaskIds`` (the real path), OR
- *project* is non-empty AND ``run.get("project") == project`` — the
  ``bulk_seed``-restored fallback.

Params (all strings)
--------------------
project : str
    The project slug; matches ``bulk_seed``-restored runs that carry a ``project``.
task_ids : str
    A JSON-encoded list of task ids (the project's deleted task ids). A run whose
    ``taskId`` is in this set is removed. ``""``/missing → empty set.

Returns
-------
dict
    A camelCase ack::

        {
            "runsRemoved": N,
            "transcriptsRemoved": N,
        }

Idempotency
-----------
Both *project* and *task_ids* empty → a no-op that returns zero counts and writes
nothing. A removed run whose transcript file is already absent (or whose id
resolves outside ``runs/``) counts as skipped, so a re-run never raises.
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


def _parse_task_ids(raw: str) -> set:
    """``task_ids`` is a JSON-encoded list of task ids; ``""``/missing → empty set.
    A non-list payload is a hard error (the caller controls the boundary shape)."""
    if not raw:
        return set()
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"task_ids must be a JSON array, got {type(parsed).__name__}")
    return set(parsed)


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def delete_project(project: str = "", task_ids: str = "", app_dir: str = "") -> dict:
    """Remove the named project's run records and their per-run transcript files.

    A run is removed if its ``taskId`` is in *task_ids* (the project's deleted task
    ids — the real path, since live runs carry no ``project``) OR *project* is
    non-empty and ``run["project"] == project`` (the ``bulk_seed``-restored
    fallback). One ``_load_doc → mutate → _save_doc`` cycle over ``runs``, holding
    the ``runs`` flock the whole time.

    **Resumability — order is load-bearing.** Under the lock, transcript
    ``.ndjson`` files are deleted FIRST (path-confined via ``_transcript_path`` — a
    traversal-shaped id is skipped), and ONLY THEN is the pruned ``runs.json``
    written LAST. The run RECORD is the recovery anchor: a crash after some
    transcripts are gone but before the prune leaves every record intact, so a
    rerun (same ``task_ids``) re-finds them and idempotently cleans the remaining
    transcripts (an already-gone file is skipped). Pruning first would orphan any
    transcript not yet deleted — no record left to re-find it by.

    Idempotent: both *project* and *task_ids* empty — or no runs match — returns
    zero counts and writes nothing; a missing transcript file counts as skipped.

    Args:
        project: project slug; matches ``bulk_seed``-restored runs carrying a ``project``.
        task_ids: JSON-encoded list of task ids; a run whose ``taskId`` is in it is removed.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir

    task_id_set = _parse_task_ids(task_ids)

    # No-op when there is nothing to match on: never lock or write, never raise.
    # `.strip()` is used ONLY here, for the empty/whitespace guard — the value
    # matched against stored records below stays the RAW `project`, identical to
    # task-management/feedback-management's comparison (a whitespace-variant slug
    # must NOT match the trimmed name and remove another project's runs).
    if not project.strip() and not task_id_set:
        return {"runsRemoved": 0, "transcriptsRemoved": 0}

    def _matches(run: dict) -> bool:
        # Match on taskId (the real live path) OR a bulk_seed-restored project field.
        # `project` is the RAW arg (not stripped) — consistent with the sibling ops.
        return run.get("taskId") in task_id_set or (bool(project) and run.get("project") == project)

    doc = _load_doc("runs")
    runs: list[dict] = doc.get("runs") or []

    # Collect matching run ids and the pruned list, but do NOT save yet.
    removed_ids = [r.get("id") for r in runs if _matches(r)]
    remaining_runs = [r for r in runs if not _matches(r)]
    runs_removed = len(runs) - len(remaining_runs)

    # Delete transcripts FIRST (still under the runs flock, before the prune). A
    # missing file, or an id that resolves outside runs/, counts as skipped. If we
    # crash here, every run record is still present, so a rerun re-finds it.
    transcripts_removed = 0
    for run_id in removed_ids:
        if not run_id:
            continue
        path = _transcript_path(run_id)
        if path is None or not os.path.exists(path):
            continue
        try:
            os.remove(path)
            transcripts_removed += 1
        except OSError:
            # A racing deleter (or a vanished file) leaves nothing to remove.
            pass

    # Prune the run records LAST, releasing the lock in _save_doc.
    doc["runs"] = remaining_runs
    _save_doc(doc)

    return {"runsRemoved": runs_removed, "transcriptsRemoved": transcripts_removed}

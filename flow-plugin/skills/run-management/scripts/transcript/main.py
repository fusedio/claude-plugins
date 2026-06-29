"""Transcript UDF — returns a run's NDJSON event log from the app run dir.

Reads ``<app_dir>/runs/<run_id>.ndjson`` directly with stdlib (after confining
the resolved path to ``runs/`` — ``run_id`` is caller-controlled); no
third-party imports.  ``<app_dir>`` is ``$OPENFUSED_APP_DIR_STATE`` (verbatim) or
``~/.openfused/app`` — matching ``APP_DIR``, under
which ``runLogPath`` joins ``runs/<id>.ndjson``.

Params
------
run_id : str
    The run id whose transcript to read. Empty string returns ``[]``.

Returns
-------
list[dict]
    The ``RunEvent`` envelopes (``{runId, seq, type, payload}``) for the run,
    in file order. A missing file, an empty ``run_id``, or a ``run_id`` whose
    resolved path would escape ``runs/`` returns ``[]``. Torn / invalid trailing
    lines are skipped (mirrors the Express ``replayEvents``): a crashed run's partial transcript still
    replays its valid prefix.
"""

import json
import os


def _app_dir() -> str:
    """Resolve the app directory (the dir that holds state.json and runs/).

    ``OPENFUSED_APP_DIR_STATE`` is a DIRECTORY; when set it is used verbatim
    (no expanduser). Otherwise fall back to
    ``~/.openfused/app``. NOTE: distinct from read/main.py's ``_state_path()``
    on purpose — that helper appends ``state.json``; this one returns the
    directory so the caller can join ``runs/<id>.ndjson``.
    """
    env_val = os.environ.get("OPENFUSED_APP_DIR_STATE")
    if env_val:
        return env_val
    return os.path.expanduser("~/.openfused/app")


def _transcript_path(run_id: str) -> str | None:
    """Resolve the transcript path, confined to the ``runs/`` directory.

    ``run_id`` is caller-controlled, so a traversal-shaped value (``..``, an
    absolute path, a symlink) must not let the UDF read ``.ndjson`` files
    outside ``runs/``. The resolved real path must be a direct child of the
    real ``runs/`` directory; otherwise return ``None`` (the caller maps that
    to an empty result, like a missing file). A valid run id is a flat
    ``run_<hex>`` with no separators.
    """
    runs_dir = os.path.realpath(os.path.join(_app_dir(), "runs"))
    path = os.path.realpath(os.path.join(runs_dir, f"{run_id}.ndjson"))
    if os.path.dirname(path) != runs_dir:
        return None
    return path


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def transcript(run_id: str = "", app_dir: str = "") -> list:
    """Return the RunEvent list for ``run_id`` from its NDJSON transcript.

    Args:
        run_id: the run id whose transcript to read; empty string returns [].
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    if not run_id:
        return []
    path = _transcript_path(run_id)
    if path is None:
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return []
    events: list[dict] = []
    for line in raw.split("\n"):
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # A torn/partial line (realistically only the last) — keep the
            # valid prefix rather than discarding the whole transcript.
            continue
    return events

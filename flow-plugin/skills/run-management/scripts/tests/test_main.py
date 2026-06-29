"""Storage-location resolution tests for the run-management UDFs.

Covers the precedence contract: explicit ``app_dir`` param > OPENFUSED_APP_DIR_STATE
env var > ~/.openfused/app default — for both the state file and run transcripts.
"""

import json
from pathlib import Path


def _runs_file(app_dir) -> Path:
    return Path(app_dir) / "state" / "runs.json"


def test_app_dir_param_honored(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    run = load_udf("create", "create")(id="run_1", task_id="t", prompt="p", app_dir=str(tmp_path))
    assert run.get("id") == "run_1"
    assert _runs_file(tmp_path).exists()


def test_env_fallback_when_param_omitted(load_udf, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(tmp_path))
    load_udf("create", "create")(id="run_1", task_id="t", prompt="p")
    assert _runs_file(tmp_path).exists()


def test_param_overrides_env(load_udf, tmp_path, monkeypatch):
    env_dir = tmp_path / "env"
    param_dir = tmp_path / "param"
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(env_dir))
    load_udf("create", "create")(id="run_1", task_id="t", prompt="p", app_dir=str(param_dir))
    assert _runs_file(param_dir).exists()
    assert not _runs_file(env_dir).exists()


def test_transcript_path_honors_app_dir(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    runs = json.dumps([{"id": "run_x", "taskId": "t", "status": "completed"}])
    transcripts = json.dumps({"run_x": [{"type": "msg", "text": "hi"}]})
    load_udf("bulk_seed", "bulk_seed")(runs=runs, transcripts=transcripts, app_dir=str(tmp_path))
    # transcript lands under <app_dir>/runs/, read back via the same param
    assert (tmp_path / "runs" / "run_x.ndjson").exists()
    events = load_udf("transcript", "transcript")(run_id="run_x", app_dir=str(tmp_path))
    assert events == [{"type": "msg", "text": "hi"}]
    # a different store sees no transcript
    assert load_udf("transcript", "transcript")(run_id="run_x", app_dir=str(tmp_path / "other")) == []


# --- delete_project --------------------------------------------------------


def _seed_runs(load_udf, app_dir, runs, transcripts):
    load_udf("bulk_seed", "bulk_seed")(
        runs=json.dumps(runs), transcripts=json.dumps(transcripts), app_dir=str(app_dir)
    )


def test_delete_project_removes_only_named_project_by_task_ids(load_udf, tmp_path, monkeypatch):
    """The REAL path: live runs carry `taskId` but NO `project`. Flow passes the
    project's deleted task ids as `task_ids`; only runs on those tasks (and their
    transcripts) are removed, other projects' runs+transcripts stay intact."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    # Realistic records: taskId set, no project field (as `create` would stamp).
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[
            {"id": "run_a1", "taskId": "t1", "status": "completed"},
            {"id": "run_a2", "taskId": "t2", "status": "failed"},
            {"id": "run_b1", "taskId": "t3", "status": "completed"},
        ],
        transcripts={
            "run_a1": [{"type": "msg", "text": "a1"}],
            "run_a2": [{"type": "msg", "text": "a2"}],
            "run_b1": [{"type": "msg", "text": "b1"}],
        },
    )

    # alpha owned tasks t1, t2 (its deleted task ids); beta owned t3.
    ack = load_udf("delete_project", "delete_project")(
        project="alpha", task_ids=json.dumps(["t1", "t2"]), app_dir=str(tmp_path)
    )
    assert ack == {"runsRemoved": 2, "transcriptsRemoved": 2}

    # beta's run + transcript survive; alpha's records and files are gone
    remaining_ids = {r["id"] for r in load_udf("read", "read")(app_dir=str(tmp_path))}
    assert remaining_ids == {"run_b1"}
    assert (tmp_path / "runs" / "run_b1.ndjson").exists()
    assert not (tmp_path / "runs" / "run_a1.ndjson").exists()
    assert not (tmp_path / "runs" / "run_a2.ndjson").exists()


def test_delete_project_matches_bulk_seed_project_fallback(load_udf, tmp_path, monkeypatch):
    """The fallback path: a `bulk_seed`-restored run may carry a `project` field.
    With no `task_ids`, such runs are matched on `project` alone."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[
            {"id": "run_a1", "taskId": "t1", "project": "alpha", "status": "completed"},
            {"id": "run_b1", "taskId": "t2", "project": "beta", "status": "completed"},
        ],
        transcripts={"run_a1": [{"type": "msg", "text": "a1"}]},
    )

    # project only (no task_ids) still removes the project-stamped run.
    ack = load_udf("delete_project", "delete_project")(project="alpha", app_dir=str(tmp_path))
    assert ack == {"runsRemoved": 1, "transcriptsRemoved": 1}
    assert {r["id"] for r in load_udf("read", "read")(app_dir=str(tmp_path))} == {"run_b1"}


def test_delete_project_matches_raw_project_not_stripped(load_udf, tmp_path, monkeypatch):
    """Regression: matching must use the RAW `project` arg (like task/feedback), not
    a stripped value. A run tagged with the trimmed slug "alpha" must NOT be removed
    when delete_project is called with a whitespace variant " alpha " — otherwise a
    whitespace-variant call would delete another (trimmed) project's runs while its
    tasks/cards (matched raw) survive: inconsistent, data-corrupting matching."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[{"id": "run_a1", "taskId": "t1", "project": "alpha", "status": "completed"}],
        transcripts={"run_a1": [{"type": "msg", "text": "a1"}]},
    )

    delete_project = load_udf("delete_project", "delete_project")

    # Whitespace-variant slug must NOT match the trimmed-tag run (raw comparison).
    for variant in (" alpha", "alpha ", "  alpha  "):
        ack = delete_project(project=variant, app_dir=str(tmp_path))
        assert ack == {"runsRemoved": 0, "transcriptsRemoved": 0}, variant
        assert {r["id"] for r in load_udf("read", "read")(app_dir=str(tmp_path))} == {"run_a1"}
        assert (tmp_path / "runs" / "run_a1.ndjson").exists()

    # Sanity: the EXACT raw slug does match and removes it.
    assert delete_project(project="alpha", app_dir=str(tmp_path)) == {
        "runsRemoved": 1,
        "transcriptsRemoved": 1,
    }
    assert load_udf("read", "read")(app_dir=str(tmp_path)) == []


def test_delete_project_idempotent_rerun_and_empty(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    delete_project = load_udf("delete_project", "delete_project")
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[
            {"id": "run_a1", "taskId": "t1", "status": "completed"},
            {"id": "run_b1", "taskId": "t2", "status": "completed"},
        ],
        transcripts={"run_a1": [{"type": "msg", "text": "a1"}]},
    )

    first = delete_project(task_ids=json.dumps(["t1"]), app_dir=str(tmp_path))
    assert first == {"runsRemoved": 1, "transcriptsRemoved": 1}

    # re-run with the same task_ids: nothing matches now, no transcript to remove
    second = delete_project(task_ids=json.dumps(["t1"]), app_dir=str(tmp_path))
    assert second == {"runsRemoved": 0, "transcriptsRemoved": 0}

    # both project AND task_ids empty → no-op (also empty/whitespace project + "[]")
    assert delete_project(app_dir=str(tmp_path)) == {"runsRemoved": 0, "transcriptsRemoved": 0}
    assert delete_project(project="   ", task_ids="", app_dir=str(tmp_path)) == {
        "runsRemoved": 0,
        "transcriptsRemoved": 0,
    }
    assert delete_project(task_ids="[]", app_dir=str(tmp_path)) == {"runsRemoved": 0, "transcriptsRemoved": 0}

    # beta untouched throughout
    assert {r["id"] for r in load_udf("read", "read")(app_dir=str(tmp_path))} == {"run_b1"}


def test_delete_project_deletes_transcripts_before_pruning_records(load_udf, tmp_path, monkeypatch):
    """Resumability: transcript files must be deleted BEFORE runs.json is pruned,
    so a crash mid-op leaves the records as the recovery anchor. We assert order by
    wrapping the module's `_save_doc` (the prune step) to record, at the moment it
    runs, whether the matched transcript files are already gone — and confirm a
    rerun on the half-/fully-deleted state is a clean no-op."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    delete_project = load_udf("delete_project", "delete_project")
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[
            {"id": "run_a1", "taskId": "t1", "status": "completed"},
            {"id": "run_a2", "taskId": "t1", "status": "failed"},
        ],
        transcripts={
            "run_a1": [{"type": "msg", "text": "a1"}],
            "run_a2": [{"type": "msg", "text": "a2"}],
        },
    )
    t1 = tmp_path / "runs" / "run_a1.ndjson"
    t2 = tmp_path / "runs" / "run_a2.ndjson"
    assert t1.exists() and t2.exists()

    # Wrap _save_doc (the prune) in the function's own module namespace, capturing
    # whether the transcripts still exist at the instant the prune is about to run.
    ns = delete_project.__globals__
    real_save = ns["_save_doc"]
    transcripts_present_at_prune = {}

    def _spy_save(doc):
        transcripts_present_at_prune["t1"] = t1.exists()
        transcripts_present_at_prune["t2"] = t2.exists()
        return real_save(doc)

    monkeypatch.setitem(ns, "_save_doc", _spy_save)

    ack = delete_project(task_ids=json.dumps(["t1"]), app_dir=str(tmp_path))
    assert ack == {"runsRemoved": 2, "transcriptsRemoved": 2}

    # Order proof: both transcripts were ALREADY deleted when the prune ran.
    assert transcripts_present_at_prune == {"t1": False, "t2": False}
    # And the records were pruned (the prune did happen, last).
    assert not t1.exists() and not t2.exists()
    assert load_udf("read", "read")(app_dir=str(tmp_path)) == []

    # A rerun on the fully-deleted state is a clean no-op (idempotent).
    assert delete_project(task_ids=json.dumps(["t1"]), app_dir=str(tmp_path)) == {
        "runsRemoved": 0,
        "transcriptsRemoved": 0,
    }


def test_delete_project_skips_traversal_shaped_id(load_udf, tmp_path, monkeypatch):
    """A run whose id resolves outside runs/ must not let delete_project remove a
    foreign file: the run record is still dropped, but the file is left alone and
    counted as skipped (transcriptsRemoved < runsRemoved). Driven via task_ids,
    the real path."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)

    # A sentinel that a traversal id like "../state/secret" would resolve onto.
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    sentinel = state_dir / "secret.ndjson"
    sentinel.write_text("keep me\n", encoding="utf-8")

    # Seed two alpha-task runs: one with a normal id (real transcript), one with a
    # traversal-shaped id (bulk_seed itself path-confines, so no file is written).
    _seed_runs(
        load_udf,
        tmp_path,
        runs=[
            {"id": "run_ok", "taskId": "t1", "status": "completed"},
            {"id": "../state/secret", "taskId": "t2", "status": "completed"},
        ],
        transcripts={"run_ok": [{"type": "msg", "text": "ok"}]},
    )
    assert (tmp_path / "runs" / "run_ok.ndjson").exists()

    ack = load_udf("delete_project", "delete_project")(
        task_ids=json.dumps(["t1", "t2"]), app_dir=str(tmp_path)
    )
    # both run records dropped; only the legitimate transcript removed
    assert ack == {"runsRemoved": 2, "transcriptsRemoved": 1}
    assert not (tmp_path / "runs" / "run_ok.ndjson").exists()
    # the traversal target outside runs/ is untouched
    assert sentinel.read_text(encoding="utf-8") == "keep me\n"
    assert load_udf("read", "read")(app_dir=str(tmp_path)) == []

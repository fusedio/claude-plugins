"""Storage-location resolution tests for the feedback-management UDFs.

Covers the precedence contract: explicit ``app_dir`` param > OPENFUSED_APP_DIR_STATE
env var > ~/.openfused/app default — and that reads honor the same param.
"""

import json
from pathlib import Path

PAYLOAD = '{"widget": {}}'


def _cards_file(app_dir) -> Path:
    return Path(app_dir) / "state" / "cards.json"


def _dismissed_file(app_dir) -> Path:
    return Path(app_dir) / "state" / "dismissedFeedbackKeys.json"


def test_app_dir_param_honored(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    card = load_udf("create_card", "create_card")(
        project="p", task_id="t", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path)
    )
    assert "id" in card
    assert _cards_file(tmp_path).exists()


def test_env_fallback_when_param_omitted(load_udf, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(tmp_path))
    load_udf("create_card", "create_card")(
        project="p", task_id="t", effect="reply", payload=PAYLOAD
    )
    assert _cards_file(tmp_path).exists()


def test_param_overrides_env(load_udf, tmp_path, monkeypatch):
    env_dir = tmp_path / "env"
    param_dir = tmp_path / "param"
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(env_dir))
    load_udf("create_card", "create_card")(
        project="p", task_id="t", effect="reply", payload=PAYLOAD, app_dir=str(param_dir)
    )
    assert _cards_file(param_dir).exists()
    assert not _cards_file(env_dir).exists()


def test_list_cards_round_trip_honors_app_dir(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    created = load_udf("create_card", "create_card")(
        project="p", task_id="t", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path)
    )
    rows = load_udf("list_cards", "list_cards")(app_dir=str(tmp_path))
    assert any(c["id"] == created["id"] for c in rows)
    assert load_udf("list_cards", "list_cards")(app_dir=str(tmp_path / "other")) == []


# --- delete_project --------------------------------------------------------


def test_delete_project_removes_only_named_project(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    create_card = load_udf("create_card", "create_card")
    a1 = create_card(project="alpha", task_id="t1", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))
    a2 = create_card(project="alpha", task_id="t2", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))
    b1 = create_card(project="beta", task_id="t3", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))

    ack = load_udf("delete_project", "delete_project")(project="alpha", app_dir=str(tmp_path))
    assert ack == {"cardsRemoved": 2}

    # beta's card survives; alpha's are gone
    remaining_ids = {c["id"] for c in load_udf("list_cards", "list_cards")(app_dir=str(tmp_path))}
    assert remaining_ids == {b1["id"]}
    assert a1["id"] not in remaining_ids and a2["id"] not in remaining_ids


def test_delete_project_idempotent_rerun_and_empty(load_udf, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    create_card = load_udf("create_card", "create_card")
    delete_project = load_udf("delete_project", "delete_project")
    create_card(project="alpha", task_id="t1", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))
    keep = create_card(project="beta", task_id="t2", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))

    assert delete_project(project="alpha", app_dir=str(tmp_path)) == {"cardsRemoved": 1}
    # re-run on the now-empty project is a zero-count no-op
    assert delete_project(project="alpha", app_dir=str(tmp_path)) == {"cardsRemoved": 0}
    # empty/whitespace project deletes nothing
    assert delete_project(project="", app_dir=str(tmp_path)) == {"cardsRemoved": 0}
    assert delete_project(project="   ", app_dir=str(tmp_path)) == {"cardsRemoved": 0}

    # beta untouched throughout
    assert {c["id"] for c in load_udf("list_cards", "list_cards")(app_dir=str(tmp_path))} == {keep["id"]}


def test_delete_project_leaves_dismissed_feedback_keys(load_udf, tmp_path, monkeypatch):
    """delete_project locks/rewrites only `cards`; the flat dismissedFeedbackKeys
    set is a harmless dangling collection and must be left byte-identical."""
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    create_card = load_udf("create_card", "create_card")
    create_card(project="alpha", task_id="t1", effect="reply", payload=PAYLOAD, app_dir=str(tmp_path))

    # Seed a dismissedFeedbackKeys set on disk (incl. an alpha-derived key).
    dismissed = ["derived:completion:run_a1", "derived:failure:run_b9"]
    _dismissed_file(tmp_path).write_text(json.dumps(dismissed, indent=2), encoding="utf-8")
    before = _dismissed_file(tmp_path).read_text(encoding="utf-8")

    assert load_udf("delete_project", "delete_project")(project="alpha", app_dir=str(tmp_path)) == {
        "cardsRemoved": 1
    }

    # the dismissed set is untouched (same bytes), even the alpha-derived key
    assert _dismissed_file(tmp_path).read_text(encoding="utf-8") == before
    assert json.loads(_dismissed_file(tmp_path).read_text(encoding="utf-8")) == dismissed

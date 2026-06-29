"""Storage-location + seed-source resolution tests for the agents-management UDFs.

Covers: explicit ``app_dir`` param > OPENFUSED_APP_DIR_STATE > ~/.openfused/app
default for the roster directory; and ``seed_file`` overriding the default 5-persona
seed, while an omitted ``seed_file`` still seeds the built-in roster.
"""

import json
from pathlib import Path

DEFAULT_SLUGS = {"architect", "project-manager", "data-engineer", "data-analyst", "data-qa"}


def _agents_dir(app_dir) -> Path:
    return Path(app_dir) / "agents"


def _clean_seed_env(monkeypatch):
    monkeypatch.delenv("OPENFUSED_APP_DIR_STATE", raising=False)
    monkeypatch.delenv("OPENFUSED_AGENTS_SEED_FILE", raising=False)
    monkeypatch.delenv("OPENFUSED_PROJECT_ROOT", raising=False)


def test_app_dir_param_honored(load_udf, tmp_path, monkeypatch):
    _clean_seed_env(monkeypatch)
    roster = load_udf("read", "read")(app_dir=str(tmp_path))
    assert _agents_dir(tmp_path).is_dir()
    assert {a["slug"] for a in roster} >= DEFAULT_SLUGS


def test_env_fallback_when_param_omitted(load_udf, tmp_path, monkeypatch):
    _clean_seed_env(monkeypatch)
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(tmp_path))
    load_udf("read", "read")()
    assert _agents_dir(tmp_path).is_dir()


def test_param_overrides_env(load_udf, tmp_path, monkeypatch):
    _clean_seed_env(monkeypatch)
    env_dir = tmp_path / "env"
    param_dir = tmp_path / "param"
    monkeypatch.setenv("OPENFUSED_APP_DIR_STATE", str(env_dir))
    load_udf("read", "read")(app_dir=str(param_dir))
    assert _agents_dir(param_dir).is_dir()
    assert not _agents_dir(env_dir).exists()


def test_seed_file_overrides_default_roster(load_udf, tmp_path, monkeypatch):
    _clean_seed_env(monkeypatch)
    custom = tmp_path / "custom_seed.json"
    custom.write_text(
        json.dumps(
            [{"slug": "captain", "name": "Captain", "title": "Captain", "role": "lead", "description": "d"}]
        ),
        encoding="utf-8",
    )
    roster = load_udf("read", "read")(app_dir=str(tmp_path / "app"), seed_file=str(custom))
    slugs = {a["slug"] for a in roster}
    assert "captain" in slugs
    assert not (slugs & DEFAULT_SLUGS)


def test_default_roster_when_seed_file_omitted(load_udf, tmp_path, monkeypatch):
    _clean_seed_env(monkeypatch)
    roster = load_udf("read", "read")(app_dir=str(tmp_path / "app"))
    assert {a["slug"] for a in roster} >= DEFAULT_SLUGS

"""Read UDF — return persona records from the live app roster directory.

Reads the global agent roster In-Loop (``fused inloop``) owns —
``~/.openfused/app/agents/`` (or ``$OPENFUSED_APP_DIR_STATE/agents``) — one
``<slug>/AGENTS.md`` per persona (YAML frontmatter + prompt body) merged with the
``.openfused.yaml`` vendor sidecar (adapter / model / builtin). Mirrors
``loadRoster``/``listAgents``.

The roster format is YAML, so this UDF imports PyYAML (a project-venv dependency
declared in ``scripts/pyproject.toml`` — NOT an ``openfused.*`` import, which the
exec sandbox shadows). All roster-format + seed logic is hand-written here; the
sandbox forbids sharing a Python helper module across UDFs, so each UDF inlines the
block below. Only the bulky default *prompts* are centralized — in
``scripts/seed_agents.json`` — and located via the project venv anchor.

Params
------
slug : str
    Filter to a single persona by slug OR derived id. Empty string (the default)
    returns every persona, slug-sorted.

Returns
-------
list[dict]
    ``AgentRecord``-shaped dicts: id, slug, name, title, role, description,
    adapter, model, prompt, builtin, createdAt.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import yaml

# --- roster format + store constants ----------

AGENT_FILE = "AGENTS.md"
SIDECAR_FILE = ".openfused.yaml"
AGENT_SCHEMA = "agentcompanies/v1"
SIDECAR_SCHEMA = "openfused/v1"
DEFAULT_ADAPTER = "claude_code"
DEFAULT_MODEL: str | None = None
# The default team that shipped BEFORE the seed ledger existed. Never
# extend — new defaults are picked up via the ledger, not the baseline.
PRE_LEDGER_BASELINE_SLUGS = ["data-engineer", "data-analyst", "data-qa"]


class _RosterError(Exception):
    """A malformed agent file — collected by ``_load_roster`` and skipped."""


# --- path resolution ----------------------------------------------------------


def _app_dir() -> str:
    """Resolve the app dir (a DIRECTORY): ``$OPENFUSED_APP_DIR_STATE`` verbatim, else
    ``~/.openfused/app`` — matching the app's ``APP_DIR``."""
    env_val = os.environ.get("OPENFUSED_APP_DIR_STATE")
    return env_val if env_val else os.path.expanduser("~/.openfused/app")


def _agents_dir() -> str:
    return os.path.join(_app_dir(), "agents")


def _sidecar_path() -> str:
    return os.path.join(_agents_dir(), SIDECAR_FILE)


def _ledger_path() -> str:
    return os.path.join(_app_dir(), "agents-seed-ledger.json")


def _seed_path() -> str:
    """Locate ``seed_agents.json`` shipped in this project's ``scripts/`` dir.

    Resolution order: an explicit ``$OPENFUSED_AGENTS_SEED_FILE`` (test seam), the
    ``$OPENFUSED_PROJECT_ROOT`` the local backend exports under a project, then the
    project venv interpreter (``<scripts>/.venv/bin/python`` → ``<scripts>``).
    """
    override = os.environ.get("OPENFUSED_AGENTS_SEED_FILE")
    if override:
        return override
    root = os.environ.get("OPENFUSED_PROJECT_ROOT")
    if root:
        cand = os.path.join(root, "scripts", "seed_agents.json")
        if os.path.exists(cand):
            return cand
    # Use .absolute(), NOT .resolve(): resolve() follows the venv's python
    # symlink out of the project tree and would miss the seed file.
    try:
        return str(Path(sys.executable).absolute().parents[2] / "seed_agents.json")
    except IndexError:
        return ""


def _load_seeds() -> list[dict]:
    """Read the 5 default personas from ``seed_agents.json`` (raises if unavailable)."""
    with open(_seed_path(), encoding="utf-8") as fh:
        return json.load(fh)


# --- identity helpers ---


def _derive_id(slug: str) -> str:
    return "agent_" + sha256(slug.encode()).hexdigest()[:12]


def _derive_slug(name: str) -> str:
    out = []
    prev_dash = False
    for ch in name.lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


# --- YAML round-trip -------------------------


def _split_frontmatter(markdown: str) -> tuple[str | None, str]:
    """Split a leading ``---`` YAML block from the body (mirror splitFrontmatter)."""
    text = markdown.replace("\r\n", "\n")
    if not text.startswith("---\n") and text != "---":
        return None, markdown
    after_open = text[4:]
    idx = -1
    search_from = 0
    while True:
        nl = after_open.find("\n---", search_from)
        if nl == -1:
            break
        rest = after_open[nl + 4 :]
        if rest == "" or rest[0] == "\n" or rest.lstrip(" \t")[:1] in ("", "\n"):
            # closing delimiter is a line that is exactly `---` (+ optional spaces)
            line_end = rest.find("\n")
            tail = rest if line_end == -1 else rest[:line_end]
            if tail.strip(" \t") == "":
                idx = nl
                break
        search_from = nl + 4
    if idx == -1:
        return None, markdown
    frontmatter = after_open[:idx]
    rest = after_open[idx + 4 :]
    body = rest[rest.find("\n") + 1 :] if "\n" in rest else ""
    return frontmatter, body


def _as_str(value: object) -> str:
    if isinstance(value, str):
        return value
    return "" if value is None else str(value)


def _parse_agent_file(
    slug: str, markdown: str, sidecar_entry: dict | None, created_at: str
) -> dict:
    """Parse one ``AGENTS.md`` into an AgentRecord dict (mirror parseAgentFile)."""
    frontmatter, body = _split_frontmatter(markdown)
    if frontmatter is None:
        raise _RosterError(f'agent "{slug}" has no YAML frontmatter')
    try:
        parsed = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise _RosterError(f'agent "{slug}" has invalid YAML frontmatter: {exc}') from exc
    scalars = parsed if isinstance(parsed, dict) else {}
    description = _as_str(scalars.get("description")).strip()
    if not description:
        raise _RosterError(f'agent "{slug}" has no non-empty description')
    for field in ("name", "title", "role"):
        if not _as_str(scalars.get(field)).strip():
            raise _RosterError(f'agent "{slug}" is missing required frontmatter "{field}"')
    return {
        "id": _derive_id(slug),
        "slug": slug,
        "name": _as_str(scalars.get("name")).strip(),
        "title": _as_str(scalars.get("title")).strip(),
        "role": _as_str(scalars.get("role")).strip(),
        "description": description,
        "adapter": (sidecar_entry or {}).get("adapter", DEFAULT_ADAPTER),
        "model": (sidecar_entry or {}).get("model", DEFAULT_MODEL),
        "prompt": body.strip(),
        "builtin": bool((sidecar_entry or {}).get("builtin", False)),
        "createdAt": created_at,
    }


def _serialize_agent_file(agent: dict) -> tuple[str, dict | None]:
    """Serialize an AgentRecord back to ``AGENTS.md`` markdown + sidecar entry."""
    front = {
        "schema": AGENT_SCHEMA,
        "name": agent["name"],
        "title": agent["title"],
        "slug": agent["slug"],
        "role": agent["role"],
        "description": agent["description"],
    }
    front_yaml = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=4096).rstrip("\n")
    body = (agent.get("prompt") or "").strip()
    markdown = f"---\n{front_yaml}\n---\n\n{body}\n"
    adapter = agent.get("adapter") or ""
    model = agent.get("model")
    builtin = bool(agent.get("builtin"))
    is_default = (adapter == DEFAULT_ADAPTER or adapter == "") and model is None and not builtin
    if is_default:
        return markdown, None
    return markdown, {"adapter": adapter or DEFAULT_ADAPTER, "model": model, "builtin": builtin}


def _parse_sidecar(yaml_text: str) -> dict:
    """Parse ``.openfused.yaml`` into ``{slug: {adapter, model, builtin}}``."""
    out: dict = {}
    doc = yaml.safe_load(yaml_text)
    if not isinstance(doc, dict):
        return out
    agents = doc.get("agents")
    if not isinstance(agents, dict):
        return out
    for slug, raw in agents.items():
        if not isinstance(raw, dict):
            continue
        adapter = DEFAULT_ADAPTER
        model: str | None = DEFAULT_MODEL
        adapter_raw = raw.get("adapter")
        if isinstance(adapter_raw, dict):
            t = adapter_raw.get("type")
            if isinstance(t, str) and t.strip():
                adapter = t.strip()
            config = adapter_raw.get("config")
            if isinstance(config, dict):
                m = config.get("model")
                model = m if isinstance(m, str) and m.strip() else None
        out[slug] = {"adapter": adapter, "model": model, "builtin": raw.get("builtin") is True}
    return out


def _serialize_sidecar(entries: dict) -> str:
    """Serialize ``{slug: entry}`` to a ``.openfused.yaml`` document."""
    agents: dict = {}
    for slug, entry in entries.items():
        node: dict = {"adapter": {"type": entry["adapter"], "config": {"model": entry["model"]}}}
        if entry["builtin"]:
            node["builtin"] = True
        agents[slug] = node
    return yaml.safe_dump(
        {"schema": SIDECAR_SCHEMA, "agents": agents}, sort_keys=False, allow_unicode=True
    )


# --- roster read/write (mirror loadRoster) ------


def _iso_from_mtime(path: str) -> str:
    return (
        datetime.fromtimestamp(os.stat(path).st_mtime, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _now_iso() -> str:
    """ISO-8601 with milliseconds + ``Z`` suffix (matches ``new Date().toISOString()``)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_sidecar() -> dict:
    try:
        with open(_sidecar_path(), encoding="utf-8") as fh:
            return _parse_sidecar(fh.read())
    except FileNotFoundError:
        return {}


def _load_roster() -> list[dict]:
    """Read every ``<slug>/AGENTS.md`` + sidecar; skip malformed files (loadRoster)."""
    agents_dir = _agents_dir()
    try:
        entries = sorted(os.listdir(agents_dir))
    except FileNotFoundError:
        return []
    sidecar = {}
    try:
        with open(_sidecar_path(), encoding="utf-8") as fh:
            sidecar = _parse_sidecar(fh.read())
    except (FileNotFoundError, yaml.YAMLError):
        sidecar = {}
    out: list[dict] = []
    seen: set[str] = set()
    for slug in entries:
        agent_file = os.path.join(agents_dir, slug, AGENT_FILE)
        if not os.path.isfile(agent_file):
            continue
        key = slug.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            created_at = _iso_from_mtime(agent_file)
            with open(agent_file, encoding="utf-8") as fh:
                markdown = fh.read()
            out.append(_parse_agent_file(slug, markdown, sidecar.get(slug), created_at))
        except (_RosterError, OSError):
            continue
    return out


def _atomic_write(target: str, content: str) -> None:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, target)


def _write_sidecar_entry(slug: str, entry: dict | None) -> None:
    sidecar = _read_sidecar()
    if entry is not None:
        sidecar[slug] = entry
    else:
        sidecar.pop(slug, None)
    path = _sidecar_path()
    if not sidecar:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    _atomic_write(path, _serialize_sidecar(sidecar))


def _write_agent_files(agent: dict) -> None:
    markdown, sidecar_entry = _serialize_agent_file(agent)
    _atomic_write(os.path.join(_agents_dir(), agent["slug"], AGENT_FILE), markdown)
    _write_sidecar_entry(agent["slug"], sidecar_entry)


# --- seeding -------------------


def _read_ledger() -> set[str]:
    try:
        with open(_ledger_path(), encoding="utf-8") as fh:
            return set(json.load(fh).get("slugs") or [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def _seed_record(seed: dict) -> dict:
    return {
        "slug": seed["slug"],
        "name": seed["name"],
        "title": seed["title"],
        "role": seed["role"],
        "description": seed["description"],
        "adapter": seed.get("adapter") or DEFAULT_ADAPTER,
        "model": seed.get("model"),
        "prompt": seed.get("prompt") or "",
        "builtin": True,
    }


def _seed_default_roster() -> None:
    """Idempotent additive seed of the 5 defaults + ledger (best-effort: a missing
    seed file is a no-op so ops on an existing roster still work)."""
    try:
        seeds = _load_seeds()
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return
    agents_dir = _agents_dir()
    dir_exists = os.path.isdir(agents_dir)
    ledger_exists = os.path.exists(_ledger_path())
    on_disk = {a["slug"] for a in _load_roster()} if dir_exists else set()
    has_any_default = any(s["slug"] in on_disk for s in seeds)
    # Never inject defaults into a curated custom roster built without the team.
    if dir_exists and not ledger_exists and not has_any_default:
        return
    if ledger_exists:
        seeded = _read_ledger()
    elif dir_exists:
        seeded = set(on_disk) | set(PRE_LEDGER_BASELINE_SLUGS)
    else:
        seeded = set()
    changed = not ledger_exists
    for seed in seeds:
        slug = seed["slug"]
        if slug not in seeded and slug not in on_disk:
            _write_agent_files(_seed_record(seed))
            changed = True
        if slug not in seeded:
            seeded.add(slug)
            changed = True
    if changed:
        os.makedirs(agents_dir, exist_ok=True)
        _atomic_write(_ledger_path(), json.dumps({"slugs": sorted(seeded)}, indent=2))


# --- the UDF ------------------------------------------------------------------


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def read(slug: str = "", app_dir: str = "", seed_file: str = "") -> list:
    """Return persona records from the roster, slug-sorted.

    Args:
        slug: filter to one persona by slug or derived id; empty returns all.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
        seed_file: default-roster seed source override (precedence over OPENFUSED_AGENTS_SEED_FILE).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    if seed_file:
        os.environ["OPENFUSED_AGENTS_SEED_FILE"] = seed_file
    _seed_default_roster()
    roster = _load_roster()
    if slug:
        roster = [a for a in roster if a["slug"] == slug or a["id"] == slug]
    return roster

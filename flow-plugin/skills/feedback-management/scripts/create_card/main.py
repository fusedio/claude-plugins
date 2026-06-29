"""Create UDF — mints a new pending interaction card in the live app state file.

Writes ``~/.openfused/app/state.json`` (or the directory named by
``OPENFUSED_APP_DIR_STATE``) directly with stdlib; no third-party imports.
Mirrors ``createCard`` (+ the route's §7 idempotency lookup).

Params (all strings)
--------------------
project : str
    Project slug for the new card.
task_id : str
    The task this card is posted into (stored as the camelCase ``taskId``).
effect : str
    The resolve-time server behaviour selector: ``reply`` / ``approval_gate`` /
    ``review_work_product``. The agent authors the whole rendered surface in
    ``payload.widget``; ``effect`` selects only what the server does on resolve.
continuation_policy : str
    ``none`` / ``wake_assignee``; empty string → ``wake_assignee`` (stored as
    ``continuationPolicy``).
idempotency_key : str
    Unique per ``(project, taskId, key)``; empty string → null.
summary : str
    Optional human summary (the only human label); empty string → null.
payload : str
    The ``{widget, effectArgs?}`` payload, JSON-encoded; parsed into the stored
    object. Empty or unparseable → ValueError (a card with no payload is never
    valid).
created_by : str
    The posting agent's slug; empty string → null.
source_run_id : str
    The run that posted it (stored as ``sourceRunId``).

Returns
-------
dict
    The card record (newly minted, or the existing STILL-PENDING one on an
    idempotent hit) as the 15-field camelCase ``InteractionCardRecord``.

Supersede
---------
Posting a **wake-bearing** card (``continuation_policy != "none"``) first sets
every **pending wake-bearing** card on the SAME ``(project, taskId)`` to
``status = "superseded"``, ``result = null`` before the new card is inserted —
the re-ask replaces the open ask. Non-blocking cards
(``continuationPolicy == "none"``) are exempt: they never supersede and are never
superseded. An idempotent hit (below) returns the existing pending card WITHOUT
superseding anything.
"""

import atexit
import fcntl
import json
import os
import secrets
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
def create_card(
    project: str = "",
    task_id: str = "",
    effect: str = "",
    continuation_policy: str = "",
    idempotency_key: str = "",
    summary: str = "",
    payload: str = "",
    created_by: str = "",
    source_run_id: str = "",
    app_dir: str = "",
) -> dict:
    """Mint a new pending card and append it to state.json.

    Mirrors ``createCard``: ``status``
    starts ``"pending"``, ``result``/``resolvedBy``/``resolvedAt`` are null, and
    ``createdAt`` is stamped now. Honors §7 idempotency PENDING-ONLY: a
    still-``pending`` card under ``(project, taskId, idempotency_key)`` is
    returned unchanged; if the keyed card(s) are all terminal a fresh pending
    card is minted (the dead one is never returned). A wake-bearing create first
    supersedes the task's open wake-bearing cards (the re-ask replaces them).

    Args:
        project: project slug.
        task_id: the task this card is posted into.
        effect: the resolve-time behaviour selector (``reply`` /
            ``approval_gate`` / ``review_work_product``).
        continuation_policy: wake policy (``none`` / ``wake_assignee``);
            empty → ``wake_assignee``.
        idempotency_key: dedup key; empty → null.
        summary: optional human summary; empty → null.
        payload: the ``{widget, effectArgs?}`` payload, JSON-encoded.
        created_by: the posting agent's slug; empty → null.
        source_run_id: the run that posted it.
        app_dir: storage location override (precedence over OPENFUSED_APP_DIR_STATE / default).
    """
    if app_dir:
        os.environ["OPENFUSED_APP_DIR_STATE"] = app_dir
    # payload is JSON at the string boundary; a card with no typed payload is
    # never valid, so an empty/unparseable payload is a hard error.
    if not payload:
        raise ValueError("create_card requires a non-empty JSON `payload`")
    try:
        payload_obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"create_card `payload` is not valid JSON: {exc}") from exc

    doc = _load_doc("cards")
    cards: list[dict] = doc.get("cards") or []

    key = idempotency_key or None
    # §7 idempotency — dedup is PENDING-ONLY: a STILL-PENDING card under
    # (project, taskId, key) is returned UNCHANGED (the route's
    # equivalence/conflict decision happens before this call). A terminal
    # (answered/dismissed/cancelled/rejected) card under the same key is DEAD —
    # short-circuiting on it would hand back a card that creates no blocker, so
    # the task could complete with the human never re-prompted. So a key whose
    # cards are all terminal falls through and MINTS A FRESH pending card,
    # re-blocking the task. sourceRunId is excluded from the equivalence concern
    # by design.
    if key is not None:
        for existing in cards:
            if (
                existing.get("status") == "pending"
                and existing.get("project") == project
                and existing.get("taskId") == task_id
                and existing.get("idempotencyKey") == key
            ):
                return existing

    # Supersede — replaces the deleted cancel_card. A wake-bearing create
    # (continuation_policy != "none") replaces the task's OPEN ask: every pending
    # wake-bearing card on the SAME (project, taskId) is set to "superseded"
    # (result cleared) before the new card is inserted. Non-blocking cards
    # (continuationPolicy "none", e.g. review_work_product) are exempt — they
    # never supersede and are never superseded. The idempotency early-return
    # above means an equivalent re-post supersedes nothing.
    effective_policy = continuation_policy or "wake_assignee"
    if effective_policy != "none":
        for existing in cards:
            if (
                existing.get("status") == "pending"
                and existing.get("project") == project
                and existing.get("taskId") == task_id
                and existing.get("continuationPolicy") != "none"
            ):
                existing["status"] = "superseded"
                existing["result"] = None

    # ISO-8601 with milliseconds + Z suffix (matches new Date().toISOString()).
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    record: dict = {
        "id": "card_" + secrets.token_hex(6),
        "project": project,
        "taskId": task_id,
        "effect": effect,
        "status": "pending",
        "continuationPolicy": effective_policy,
        "idempotencyKey": key,
        "summary": summary or None,
        "payload": payload_obj,
        "result": None,
        # createdBy is a non-nullable string (InteractionCardRecord);
        # the route always supplies it ("agent" default), so store it verbatim.
        "createdBy": created_by,
        "sourceRunId": source_run_id,
        "resolvedBy": None,
        "createdAt": now,
        "resolvedAt": None,
    }

    cards.append(record)
    doc["cards"] = cards
    _save_doc(doc)
    return record

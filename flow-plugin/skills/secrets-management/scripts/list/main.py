"""List UDF — returns secret NAMES (never values) from the OS keychain store.

Reads the same keychain-backed store as ``LocalSecretsBackend``:
the name→value map is stored as a JSON blob in
the OS keychain under service=``"openfused"`` and account=``str(_store_path())``.
The storage helpers below are ported verbatim from that backend so the two readers
stay byte-interoperable.

Params
------
prefix : str
    Optional name prefix filter. Empty string (the default) returns all names.

Returns
-------
list[dict]
    ``[{"name": <name>}, ...]`` sorted by name. Names only — values are never
    returned by this UDF (mirrors the app's list adapter, which strips to ``name``).
    This is a deliberate divergence from ``LocalSecretsBackend.list_secrets``, which
    also returns ``arn``; do not "fix" it toward backend parity.
"""

from __future__ import annotations

import builtins
import importlib
import json
import os
from pathlib import Path
from typing import Any


def _import_keyring() -> tuple[Any, type[Exception]]:
    """Import keyring if installed; else return (None, a never-raised error type)."""
    try:
        keyring = importlib.import_module("keyring")
        errors = importlib.import_module("keyring.errors")
    except ImportError:  # headless/CI/container: keyring not installed
        return None, RuntimeError
    return keyring, getattr(errors, "KeyringError", RuntimeError)


_keyring, _KeyringError = _import_keyring()

# Keychain service name; the account (username) is the per-env store path.
def _keyring_service() -> str:
    """Resolve the keychain service name: ``OPENFUSED_KEYRING_SERVICE`` else the
    default ``"openfused"``. The per-call ``service`` param sets that env var."""
    return os.environ.get("OPENFUSED_KEYRING_SERVICE") or "openfused"


def _store_path() -> Path:
    """Resolve the secrets store path: ``OPENFUSED_SECRETS_FILE`` else the default.

    The env var is the UDF-side test-isolation seam (LocalSecretsBackend takes its
    path as a constructor arg with no env override). Must produce the same string
    as the backend's ``self._path`` so the keychain account matches.
    """
    raw = os.environ.get("OPENFUSED_SECRETS_FILE") or "~/.openfused/secrets.json"
    return Path(raw).expanduser().resolve()


def _require_keyring() -> Any:
    """Return the keyring module or raise a clear, actionable RuntimeError.

    Fail-loud boundary: never fall back to a file or swallow the error.
    """
    if _keyring is None:
        raise RuntimeError(
            "OS keychain unavailable: the 'keyring' package is not installed "
            "(install the 'local' extra: `pip install fused[local]`). "
            "To use secrets without the local extra, switch to the AWS backend."
        )
    return _keyring


def _load() -> dict[str, str]:
    """Load the name->value map from the OS keychain. Missing item → {}."""
    kr = _require_keyring()
    account = str(_store_path())
    try:
        blob = kr.get_password(_keyring_service(), account)
    except _KeyringError as exc:
        raise RuntimeError(
            f"OS keychain unavailable for store {_store_path()}: {exc}. "
            "To use secrets in a headless/CI environment, switch to the AWS backend."
        ) from exc
    if blob is None:
        return {}
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Secrets store for {_store_path()} is corrupt: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Secrets store for {_store_path()} is corrupt: not a JSON object")
    return {str(k): str(v) for k, v in data.items()}


@udf  # ty: ignore[unresolved-reference]  # noqa: F821 — injected by the exec runtime
def list(  # noqa: A001 — UDF name must match the dir
    prefix: str = "", secrets_file: str = "", service: str = ""
) -> builtins.list:
    """Return secret names (not values) from the store, sorted, optionally filtered.

    Args:
        prefix: name prefix filter; empty string returns all names.
        secrets_file: secrets store path override (precedence over OPENFUSED_SECRETS_FILE).
        service: keychain service-name override (precedence over OPENFUSED_KEYRING_SERVICE; default "openfused").
    """
    if secrets_file:
        os.environ["OPENFUSED_SECRETS_FILE"] = secrets_file
    if service:
        os.environ["OPENFUSED_KEYRING_SERVICE"] = service
    data = _load()
    return [{"name": k} for k in sorted(data) if not prefix or k.startswith(prefix)]

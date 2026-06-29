"""Test harness for the secrets-management UDFs.

The ``@udf`` decorator is injected by the fused exec runtime, so it is an
undefined name when a ``main.py`` is imported normally. ``load_udf`` execs the
module source in a namespace that stubs ``udf`` as an identity decorator.

The UDFs call ``keyring.{get,set,delete}_password`` against the active backend at
call time, so the autouse ``_fake_keyring`` fixture installs an in-memory backend
BEFORE any UDF is invoked — no OS keychain needed. ``load_udf`` is therefore called
inside each test body (after fixtures run), never at import time.
"""

import os
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


class _MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def _fake_keyring():
    prev = keyring.get_keyring()
    keyring.set_keyring(_MemoryKeyring())
    yield
    keyring.set_keyring(prev)


@pytest.fixture
def load_udf():
    def _load(script_name: str, func_name: str):
        path = SCRIPTS_DIR / script_name / "main.py"
        ns: dict = {"udf": lambda f: f, "__name__": f"udf_{script_name}"}
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
        return ns[func_name]

    return _load


@pytest.fixture(autouse=True)
def _restore_environ():
    """The UDFs set OPENFUSED_SECRETS_FILE / OPENFUSED_KEYRING_SERVICE from their
    params. pytest runs every test in one process, so snapshot and restore
    os.environ around each test to stop those overrides leaking between tests."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)

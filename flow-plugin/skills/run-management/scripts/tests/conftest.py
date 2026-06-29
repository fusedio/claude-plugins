"""Test harness for the run-management UDFs.

The ``@udf`` decorator is injected by the fused exec runtime, so it is an
undefined name when a ``main.py`` is imported normally. ``load_udf`` execs the
module source in a namespace that stubs ``udf`` as an identity decorator, then
returns the requested function — letting the UDFs be exercised in-process.
"""

import os
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


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
    """The UDFs set OPENFUSED_APP_DIR_STATE from their ``app_dir`` param. pytest
    runs every test in one process, so snapshot and restore os.environ around each
    test to stop that override leaking between tests."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)

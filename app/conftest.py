"""Shared pytest setup for all app tests.

`app/evaluation/harness/runner.py` loads `.env` into `os.environ` at import time (it is
also a CLI), and harness scenarios write DATA_DIR / HARNESS_MODE / DEMO_TODAY directly.
Under one pytest session that state leaked into later test modules (for example
DEMO_SNAPSHOT made b04/b07 boot from the demo snapshot). Every test now starts from the
environment the test run was launched with.
"""

import os

import pytest

_LAUNCH_ENV = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}


def _reset_environment() -> None:
    for key in list(os.environ):
        if key.startswith("PYTEST_"):
            continue  # managed by pytest itself
        if key not in _LAUNCH_ENV:
            del os.environ[key]
    for key, value in _LAUNCH_ENV.items():
        if os.environ.get(key) != value:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def _isolate_environment(request):
    _reset_environment()
    if "evaluation" in request.node.path.parts:
        # The reliability harness always runs with HARNESS_MODE=1 (set by runner.py for CLI runs).
        os.environ["HARNESS_MODE"] = "1"
    yield
    _reset_environment()

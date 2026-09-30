"""Hermetic git configuration for the Foundry tooling tests.

These tests drive real ``git`` in throwaway repositories and assert what the
tooling concludes, for example that ``safe_push`` refuses a push whose target
is rewritten by ``url.<base>.insteadOf``. git also reads configuration passed
through the environment (``GIT_CONFIG_COUNT`` with ``GIT_CONFIG_KEY_<n>`` and
``GIT_CONFIG_VALUE_<n>``, or ``GIT_CONFIG_PARAMETERS``). Hosted agent
sandboxes set these, for example to route git through a proxy, while CI
runners do not. The tooling then correctly refuses in the sandbox, and more
than a hundred tests fail there for a reason CI never sees.

Removing the environment-injected configuration makes every run see the
configuration each test sets up itself. The file- and system-level isolation
stays with the individual tests (``GIT_CONFIG_NOSYSTEM``, temporary ``HOME``).
"""

from __future__ import annotations

import os

import pytest

_INJECTED_GIT_CONFIG = ("GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS")
_INJECTED_GIT_CONFIG_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")


@pytest.fixture(autouse=True)
def _no_environment_injected_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name in _INJECTED_GIT_CONFIG or name.startswith(_INJECTED_GIT_CONFIG_PREFIXES):
            monkeypatch.delenv(name)

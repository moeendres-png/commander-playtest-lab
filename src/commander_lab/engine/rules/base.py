from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from commander_lab.models import (
    ActionProposal,
    GameState,
    LegalAction,
    RulesDeckHandle,
    RulesDeckInput,
    RulesEngineLog,
    RulesEngineProbe,
    RulesEngineResult,
    RulesGameRequest,
    RulesSession,
    TacticalScenario,
)


class RulesEngineError(RuntimeError):
    """Base failure raised by tactical or external rules-engine adapters."""


class RulesEngineUnavailable(RulesEngineError):
    """Raised when the configured external backend cannot be started."""


class RulesEngineProtocolError(RulesEngineError):
    """Raised when an external bridge violates the JSONL bridge contract."""


ENGINE_RUNTIME_DIRECTORY_ENV = "ENGINE_RUNTIME_DIRECTORY"
DEFAULT_ENGINE_RUNTIME_DIRECTORY = ".runtime/engine"


def resolve_engine_working_directory(cwd: str | Path | None) -> str | None:
    """Resolve the working directory an external engine process runs in.

    Both candidate engines resolve engine-internal state relative to the
    *process* working directory: XMage hardcodes its H2 card repository at
    ``jdbc:h2:file:./db/cards.h2`` (``DatabaseUtils.prepareH2Connection``), which
    materializes a multi-hundred-megabyte database on first use. Inheriting the
    caller's working directory therefore writes engine runtime state into the Git
    worktree, which dirties tracked state and trips the project's own
    stale-canonical-input guard for every subsequent run.

    Run the engine inside the already-ignored ``.runtime/engine`` state directory
    instead, which is the same default the engine log directory already uses
    (``process_manager`` reads ``ENGINE_LOG_DIRECTORY`` with a ``.runtime/engine``
    fallback). The directory is created on demand and a failure to create it
    fails closed rather than silently falling back to the worktree.

    An explicit ``cwd`` is always honoured: callers that deliberately place the
    engine somewhere else keep that authority.
    """
    if cwd is not None:
        return str(cwd)
    configured = os.environ.get(ENGINE_RUNTIME_DIRECTORY_ENV) or DEFAULT_ENGINE_RUNTIME_DIRECTORY
    # Resolve against the caller's directory once, here, and pin the absolute
    # result. A relative answer would keep the engine tied to whatever the
    # working directory happens to be at spawn time, which is exactly the
    # coupling being removed, and it would not be auditable after the fact.
    target = Path(configured).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RulesEngineUnavailable(
            f"unable to create the engine runtime state directory {target}: {exc}"
        ) from exc
    return str(target)


class RulesEngineAdapter(ABC):
    """Narrow authority boundary for tactical and external rules backends.

    The adapter is the only component allowed to create or mutate an authoritative
    tactical/rules-engine session. Agents receive legal actions and may submit an
    ``ActionProposal``; they never receive a mutable engine object.
    """

    @abstractmethod
    def probe(self) -> RulesEngineProbe:
        raise NotImplementedError

    @abstractmethod
    def load_deck(self, deck: RulesDeckInput) -> RulesDeckHandle:
        raise NotImplementedError

    @abstractmethod
    def start_commander_game(self, request: RulesGameRequest) -> RulesSession:
        raise NotImplementedError

    @abstractmethod
    def create_scenario(self, scenario: TacticalScenario) -> RulesSession:
        raise NotImplementedError

    @abstractmethod
    def get_state(self, session_id: str) -> GameState:
        raise NotImplementedError

    @abstractmethod
    def get_legal_actions(self, session_id: str) -> tuple[LegalAction, ...]:
        raise NotImplementedError

    @abstractmethod
    def submit_action(self, session_id: str, proposal: ActionProposal) -> GameState:
        raise NotImplementedError

    @abstractmethod
    def get_logs(self, session_id: str) -> RulesEngineLog:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, session_id: str) -> RulesEngineResult:
        raise NotImplementedError

    def close(self) -> None:
        """Release subprocesses or temporary resources."""
        return None


__all__ = [
    "DEFAULT_ENGINE_RUNTIME_DIRECTORY",
    "ENGINE_RUNTIME_DIRECTORY_ENV",
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineProtocolError",
    "RulesEngineUnavailable",
    "resolve_engine_working_directory",
]

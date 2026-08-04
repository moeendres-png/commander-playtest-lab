from __future__ import annotations

from abc import ABC, abstractmethod

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


__all__ = [
    "RulesEngineAdapter",
    "RulesEngineError",
    "RulesEngineProtocolError",
    "RulesEngineUnavailable",
]

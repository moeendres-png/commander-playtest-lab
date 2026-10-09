"""WS218 divergence taxonomy (fail-closed, machine-readable)."""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from functools import wraps

from commander_lab.engine.rules.failure_privacy import diagnostics_digest

REPLAY_DIVERGENCE_DETAIL_LIMIT = 500

# Only exact Lab-authored reasons may be persisted verbatim. A new reason not
# registered here still fails closed, with its diagnostic digest. Never infer
# trusted codes or public text from arbitrary engine/validation diagnostics.
_PUBLIC_REASONS = frozenset(
    {
        "concede interleave guard tripped",
        "creation mismatch",
        "decision lacks pilot_state",
        "deck hash mismatch",
        "deck import failed",
        "deck import gave no handle",
        "drain expected a pending decision",
        "game terminal before first decision",
        "handle count mismatch",
        "initial RNG calls differ",
        "initial checkpoint seed disagrees with manifest",
        "initial decision malformed",
        "joint numeric choices malformed",
        "joint numeric leg bound malformed",
        "joint numeric leg malformed",
        "joint numeric legs malformed",
        "joint numeric total band malformed",
        "legal_options malformed",
        "missing binding",
        "missing rules_seed_binding",
        "native decision malformed",
        "no initial decision",
        "no initial replay decision",
        "outcome not an object",
        "player count mismatch",
        "provider is not xmage",
        "record budget exhausted without terminal; no complete tape sealed",
        "replay consumed all steps but the game offers another decision",
        "replay ended but game is not terminal",
        "replay game terminal at start",
        "replay seed mismatch",
        "rng_contract root seed disagrees with manifest",
        "rules_seed mismatch",
        "seed mismatch",
        "seed not explicit",
        "seed not matching",
        "status is missing live rules_seed_binding.rules_random_calls",
        "status missing rules_seed_binding",
        "terminal outcomes malformed",
        "REPLAY_SHUTDOWN_NOT_GRACEFUL (record)",
        "REPLAY_SHUTDOWN_NOT_GRACEFUL (replay)",
    }
)
_DIAGNOSTIC_SITES = (
    "engine failed at start: ",
    "engine failed before first decision: ",
    "engine failure mid-game: ",
    "engine failure after submit: ",
    "engine failure while draining to terminal: ",
    "engine failed at replay start: ",
    "engine failure during replay: ",
    "engine failure after replay submit: ",
    "schema invalid: ",
    "REPLAY_EXECUTION_FAILED: ",
)
_STEP_PREFIX = re.compile(r"^(?:concede )?step [1-9][0-9]{0,9}: ")
# ENGINE_FAILURE is a fixed generic failure label, not an arbitrary token
# extraction rule. Uppercase private values must not be promoted to codes.
_ENGINE_FAILURE = re.compile(r"\bENGINE_FAILURE\b")


def _public_detail(detail: str) -> str:
    if detail in _PUBLIC_REASONS:
        return detail
    prefix = "replay diagnostics redacted"
    step = _STEP_PREFIX.match(detail)
    if step is not None:
        # Meta-qualification uses this structural prefix to locate a failure.
        prefix = step.group().rstrip() + " diagnostics redacted"
    else:
        for site in _DIAGNOSTIC_SITES:
            if detail.startswith(site):
                prefix = site.removesuffix(": ")
                break
    code = " [ENGINE_FAILURE]" if _ENGINE_FAILURE.search(detail) else ""
    summary = f"{prefix}{code} (diagnostics sha256:{diagnostics_digest((detail,))})"
    # Preserve the existing bounded-detail indication without publishing even
    # a truncated fragment of the original, potentially private diagnostics.
    return summary + ("..." if len(detail) > REPLAY_DIVERGENCE_DETAIL_LIMIT else "")


class DivergenceClass(StrEnum):
    SOURCE_LOCK_MISMATCH = "SOURCE_LOCK_MISMATCH"
    DOMAIN_LOCK_MISMATCH = "DOMAIN_LOCK_MISMATCH"
    INITIAL_STATE_MISMATCH = "INITIAL_STATE_MISMATCH"
    ACTOR_MISMATCH = "ACTOR_MISMATCH"
    DECISION_CLASS_MISMATCH = "DECISION_CLASS_MISMATCH"
    DECISION_REVISION_MISMATCH = "DECISION_REVISION_MISMATCH"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"
    LEGAL_SET_MISMATCH = "LEGAL_SET_MISMATCH"
    CHOSEN_OPTION_MISSING = "CHOSEN_OPTION_MISSING"
    CHOSEN_OPTION_AMBIGUOUS = "CHOSEN_OPTION_AMBIGUOUS"
    RULES_RNG_CALL_DRIFT = "RULES_RNG_CALL_DRIFT"
    RULES_RNG_RESULT_DRIFT = "RULES_RNG_RESULT_DRIFT"
    EVENT_DIGEST_MISMATCH = "EVENT_DIGEST_MISMATCH"
    STATE_DIGEST_MISMATCH = "STATE_DIGEST_MISMATCH"
    EARLY_TERMINATION = "EARLY_TERMINATION"
    EXTRA_DECISION = "EXTRA_DECISION"
    TERMINAL_OUTCOME_MISMATCH = "TERMINAL_OUTCOME_MISMATCH"
    MALFORMED_TAPE = "MALFORMED_TAPE"


class ReplayDivergence(RuntimeError):
    """Fail-closed replay divergence (no WARN_AND_CONTINUE)."""

    def __init__(self, divergence: DivergenceClass, detail: str) -> None:
        self.detail = _public_detail(detail)
        self.public_message = f"{divergence.value}: {self.detail}"
        super().__init__(self.public_message)
        self.divergence = divergence


def public_replay_errors[**P, T](operation: Callable[P, T]) -> Callable[P, T]:
    """Keep raw transport/parse/pilot errors out of public replay failures.

    Transport exceptions can already carry an unsafe 'public_message' from
    another boundary. Do not trust it or retain a raw chained traceback.
    """

    @wraps(operation)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return operation(*args, **kwargs)
        except ReplayDivergence as exc:
            raise exc from None
        except Exception as exc:
            raise ReplayDivergence(
                DivergenceClass.EARLY_TERMINATION,
                f"REPLAY_EXECUTION_FAILED: {exc}",
            ) from None

    return guarded


__all__ = ["DivergenceClass", "ReplayDivergence", "public_replay_errors"]

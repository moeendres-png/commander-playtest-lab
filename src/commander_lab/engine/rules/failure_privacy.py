"""Redaction of full-game failure diagnostics before they leave the process.

A failed full game can carry anything the engine or the bridge printed: raw
protocol lines, engine exception text, stderr of the JVM. Those can contain
hidden information (cards in a hand or library, face-down identities) and local
environment details. None of that may reach an exception message, a batch
record or an evidence file.

What survives is structural and safe:

* a stable failure code chosen by the Lab (``BRIDGE_TIMEOUT`` ...);
* exact audited machine codes from a fixed public vocabulary; uppercase
  spelling alone does not make an engine or pilot diagnostic public;
* a short digest of the raw diagnostics, so an operator holding the local log
  can correlate a record with it without the record carrying the text.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_MACHINE_CODE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_MAX_CODES = 8

# Lab transport sites and the full-game Player/DecisionController failure sites.
# New unregistered bridge failures still fail closed, retaining their digest.
PUBLIC_FAILURE_CODES = frozenset(
    {
        "BRIDGE_CLOSED",
        "BRIDGE_ERROR",
        "BRIDGE_EXITED",
        "BRIDGE_NOT_WRITABLE",
        "BRIDGE_PROTOCOL_ERROR",
        "BRIDGE_START_FAILED",
        "BRIDGE_TIMEOUT",
        "DECISION_TIMEOUT",
        "ENGINE_FAILURE",
        "FULL_GAME_ALREADY_STARTED",
        "FULL_GAME_NOT_CREATED",
        "FULL_GAME_NOT_STARTED",
        "ILLEGAL_ACTION",
        "INVALID_RESPONSE",
        "NO_LEGAL_ACTION",
        "OUT_OF_SCOPE_DECISION",
        "PILOT_RESPONSE_INVALID",
        "PLAYER_LEFT_GAME",
        "PLAYER_LEFT_GAME_UNSUPPORTED_DECISION",
        "PROTOCOL_MISMATCH",
        "REQUEST_ID_MISMATCH",
        "XMAGE_ACTION_EXECUTION_FAILED",
        "XMAGE_FULL_GAME_FAILED",
    }
)
_EXCEPTION_TYPES = (ValueError, TypeError, OSError, RuntimeError, Exception, BaseException)
_EXCEPTION_LABELS = frozenset(cls.__name__ for cls in _EXCEPTION_TYPES)
_PUBLIC_CONFIGURATION_ERRORS = frozenset(
    {
        "smoke_decision_target must be positive",
        "stop_at_turn must be positive",
        "full-game bridge command must not be empty",
        "full-game bridge command must explicitly include the full-game subcommand",
        "full-game policy requires two to six pilot bindings",
    }
)

# Exact Lab-authored diagnostic sites. Dynamic suffixes are never published.
# Preserve useful public error classes without trusting a caller's message.
_FULL_GAME_SITES = (
    "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD is required for the semantic tape replay",
    "unsupported discretionary decision class",
    "full game shutdown not graceful",
    "full-game shutdown not graceful",
    "semantic tape replay",
    "full-game semantic tape replay",
    "bounded smoke shutdown not graceful",
    "semantic tape replay was not verified",
    "semantic tape replay requires",
    "actor-scoped hidden-information audit",
)
_ACTOR_SCOPE_SITE = re.compile(r"^hidden information not actor-scoped at decision [0-9]{1,10}:")
_PUBLIC_ERROR_REASONS = (
    "wrong vector length",
    "non-integer element",
    "non-integer",
    "outside authoritative domain",
    "outside authoritative band",
    "explicit boolean",
    "no productive option",
    "no authoritative decisions",
    "player-count/seed contract",
    "engine failed",
    "not configured",
    "turn boundary",
    "progress",
    "unknown",
)


def public_full_game_message(message: str, *, code: str | None = None) -> str:
    """Render a public full-game error using only fixed sites and audited codes."""
    site = "full-game diagnostics redacted"
    actor_scope = _ACTOR_SCOPE_SITE.match(message)
    if actor_scope is not None:
        site = actor_scope.group().removesuffix(":")
    else:
        for candidate in _FULL_GAME_SITES:
            if message.startswith(candidate):
                site = candidate
                break
        if site == "full-game diagnostics redacted":
            for reason in _PUBLIC_ERROR_REASONS:
                if reason in message:
                    site = reason
                    break
    label = code if code in PUBLIC_FAILURE_CODES else "ENGINE_FAILURE"
    return f"{site}: {redacted_summary(label, (message,))}"


def machine_codes(texts: Iterable[str]) -> tuple[str, ...]:
    """Distinct audited public codes in first-seen order; raw tokens are untrusted."""
    seen: list[str] = []
    for text in texts:
        for code in _MACHINE_CODE.findall(text or ""):
            if code in PUBLIC_FAILURE_CODES and code not in seen:
                seen.append(code)
                if len(seen) == _MAX_CODES:
                    return tuple(seen)
    return tuple(seen)


def diagnostics_digest(texts: Iterable[str]) -> str:
    """First 16 hex digits of the SHA-256 over the raw diagnostics."""
    digest = hashlib.sha256()
    for text in texts:
        digest.update((text or "").encode("utf-8", errors="replace"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def redacted_summary(code: str, raw: Iterable[str]) -> str:
    """``code [codes=...] (diagnostics sha256:...)`` without any raw text."""
    raw = tuple(raw)
    codes = machine_codes(raw)
    summary = (
        code if code in PUBLIC_FAILURE_CODES or code in _EXCEPTION_LABELS else "ENGINE_FAILURE"
    )
    if codes:
        summary += " [" + ", ".join(codes) + "]"
    if raw:
        summary += f" (diagnostics sha256:{diagnostics_digest(raw)})"
    return summary


def _exception_diagnostics(exc: BaseException) -> str:
    try:
        return str(exc)
    except Exception:
        # Formatting is untrusted too; never propagate or stringify its error.
        return "exception diagnostics unavailable"


def public_full_game_exception_message(exc: BaseException, *, code: str | None = None) -> str:
    """Preserve finite public reasons without trusting exception metadata."""
    return public_full_game_message(_exception_diagnostics(exc), code=code)


def redacted_exception_message(exc: BaseException) -> str:
    """Persistable error; neither metadata nor a custom class name is authority."""
    label = public_exception_type(exc)
    raw = _exception_diagnostics(exc)
    summary = redacted_summary(label, (raw,))
    if raw in _PUBLIC_CONFIGURATION_ERRORS:
        summary = f"{raw}: {summary}"
    return summary


def public_exception_type(exc: BaseException) -> str:
    """A fixed standard classification, never an arbitrary subclass name."""
    return next(cls.__name__ for cls in _EXCEPTION_TYPES if isinstance(exc, cls))


def redacted_exception(exc: Exception) -> Exception:
    """Keep the standard failure family while dropping unsafe subclass metadata."""
    cls = next(cls for cls in _EXCEPTION_TYPES if isinstance(exc, cls))
    return cls(redacted_exception_message(exc))  # type: ignore[return-value]

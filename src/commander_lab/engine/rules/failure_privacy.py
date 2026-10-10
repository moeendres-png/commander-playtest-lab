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
* a short keyed correlation token of the raw diagnostics. Operators can
  recompute it only while the originating process/key is alive; saved raw logs
  alone cannot reproduce it after exit. The legacy ``diagnostics sha256:``
  marker denotes HMAC-SHA-256, not a publicly reproducible content hash.
"""

from __future__ import annotations

import hmac
import os
import re
import secrets
from collections.abc import Iterable

_MACHINE_CODE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_MAX_CODES = 8

# Diagnostic privacy entropy is separate from Rules RNG, seeds and replay.
# Never export/persist this key or derive it from any public game identity.
_DIAGNOSTIC_KEY: bytes | None = secrets.token_bytes(32)


def _reset_diagnostic_key() -> None:
    global _DIAGNOSTIC_KEY
    # Invalidate first: a child must fail closed if fresh entropy is unavailable.
    _DIAGNOSTIC_KEY = None
    _DIAGNOSTIC_KEY = secrets.token_bytes(32)


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_diagnostic_key)

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
    "hidden information not actor-scoped",
)
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
    message = _plain_diagnostic(message)
    for candidate in _FULL_GAME_SITES:
        if message.startswith(candidate):
            site = candidate
            break
    if site == "full-game diagnostics redacted":
        for reason in _PUBLIC_ERROR_REASONS:
            if reason in message:
                site = reason
                break
    label = code if type(code) is str and code in PUBLIC_FAILURE_CODES else "ENGINE_FAILURE"
    return f"{site}: {redacted_summary(label, (message,))}"


def machine_codes(texts: Iterable[str]) -> tuple[str, ...]:
    """Distinct audited public codes in first-seen order; raw tokens are untrusted."""
    seen: list[str] = []
    for text in texts:
        for code in _MACHINE_CODE.findall(_plain_diagnostic(text)):
            if code in PUBLIC_FAILURE_CODES and code not in seen:
                seen.append(code)
                if len(seen) == _MAX_CODES:
                    return tuple(seen)
    return tuple(seen)


def diagnostics_digest(texts: Iterable[str]) -> str:
    """Process-local 16-hex HMAC token; never an offline diagnostic oracle."""
    if _DIAGNOSTIC_KEY is None:
        raise RuntimeError("diagnostic correlation unavailable")
    digest = hmac.new(_DIAGNOSTIC_KEY, digestmod="sha256")
    for text in texts:
        digest.update(_plain_diagnostic(text).encode("utf-8", errors="replace"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def redacted_summary(code: str, raw: Iterable[str]) -> str:
    """Safe classification and keyed token, retaining the legacy wire marker."""
    raw = tuple(raw)
    codes = machine_codes(raw)
    summary = (
        code
        if type(code) is str and (code in PUBLIC_FAILURE_CODES or code in _EXCEPTION_LABELS)
        else "ENGINE_FAILURE"
    )
    if codes:
        summary += " [" + ", ".join(codes) + "]"
    if raw:
        summary += f" (diagnostics sha256:{diagnostics_digest(raw)})"
    return summary


def _plain_diagnostic(text: object) -> str:
    # str() can retain a hostile string subclass returned by __str__. Use the
    # built-in primitive conversion, never its hash/equality/encoding hooks.
    if issubclass(type(text), str):
        return str.__str__(text)
    return "exception diagnostics unavailable"


def _exception_diagnostics(exc: BaseException) -> str:
    try:
        return _plain_diagnostic(str(exc))
    except BaseException:
        # Formatting is untrusted too; never propagate or stringify its error.
        # This contains only formatter failures, not real operation interrupts.
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
    return next(cls.__name__ for cls in _EXCEPTION_TYPES if issubclass(type(exc), cls))


def redacted_exception(exc: Exception) -> Exception:
    """Keep the standard failure family while dropping unsafe subclass metadata."""
    cls = next(cls for cls in _EXCEPTION_TYPES if issubclass(type(exc), cls))
    return cls(redacted_exception_message(exc))  # type: ignore[return-value]

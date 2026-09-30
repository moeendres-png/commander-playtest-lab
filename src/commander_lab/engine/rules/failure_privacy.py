"""Redaction of full-game failure diagnostics before they leave the process.

A failed full game can carry anything the engine or the bridge printed: raw
protocol lines, engine exception text, stderr of the JVM. Those can contain
hidden information (cards in a hand or library, face-down identities) and local
environment details. None of that may reach an exception message, a batch
record or an evidence file.

What survives is structural and safe:

* a stable failure code chosen by the Lab (``BRIDGE_TIMEOUT`` ...);
* the machine codes already embedded in the raw text (upper-case identifiers
  with an underscore such as ``PLAYER_LEFT_GAME_UNSUPPORTED_DECISION``), which
  name a failure class and never a card or a player;
* a short digest of the raw diagnostics, so an operator holding the local log
  can correlate a record with it without the record carrying the text.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

_MACHINE_CODE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_MAX_CODES = 8


def machine_codes(texts: Iterable[str]) -> tuple[str, ...]:
    """Distinct machine codes found in ``texts``, in first-seen order."""
    seen: list[str] = []
    for text in texts:
        for code in _MACHINE_CODE.findall(text or ""):
            if code not in seen:
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
    summary = code
    if codes:
        summary += " [" + ", ".join(codes) + "]"
    if raw:
        summary += f" (diagnostics sha256:{diagnostics_digest(raw)})"
    return summary


def redacted_exception_message(exc: BaseException) -> str:
    """Persistable message for any exception: its public text if it has one.

    Exceptions that carry a vetted public message (``public_message``) keep it.
    Anything else is reduced to its type, the machine codes in its text and a
    digest, because arbitrary exception text is not known to be safe.
    """
    public = getattr(exc, "public_message", None)
    if isinstance(public, str) and public:
        return public
    return redacted_summary(type(exc).__name__, (str(exc),))

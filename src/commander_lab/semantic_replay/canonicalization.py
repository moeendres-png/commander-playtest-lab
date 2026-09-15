"""WS218 canonical semantic encoding (engine-neutral).

Versioned contract: ``semantic-canonical-1.0.0``.

Rules:
- UTF-8 bytes of JSON with stable object-key ordering (sort_keys), compact
  separators, ``ensure_ascii=False`` (Unicode preserved, UTF-8 encoded).
- Stable scalar representation: JSON numbers/bools/strings/null only;
  NaN/Infinity forbidden (fail closed).
- Ordered semantic sequences stay ordered (stack, graveyard order,
  transcript order, damage rows are pre-sorted by caller where order is
  semantic). Unordered semantic sets are sorted by the caller via semantic
  fingerprint before hashing (see fingerprint module).
- Timestamps, wall-clock diagnostics, request ids, engine game UUIDs and
  other process-local identities are EXCLUDED by the projection functions
  (fingerprint/observation), never by silent generic stripping. This module
  provides only the byte encoding plus explicit UUID-redaction for free
  text (prompts/labels) where source inspection proved the redacted
  substring carries no Rules content (per-process engine UUIDs and GameLog
  short-id suffixes, matching the production ``_semantic_text`` /
  ``redactObjectIds`` / ``choiceText`` lineage).
- Canonicalization version is persisted in every tape/checkpoint digest
  input so a future encoding change cannot silently compare across
  versions.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

CANONICALIZATION_VERSION = "semantic-canonical-1.0.0"

_UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
_OBJECT_ID_ATTR_RE = re.compile(
    r"\s+object_id=(['\"])[^'\"]+\1", flags=re.IGNORECASE
)
_SHORT_ID_SUFFIX_RE = re.compile(r"(</font>)\s*\[[0-9a-fA-F]{3,8}\]")
_SHORT_ID_TAIL_RE = re.compile(r"\s*\[[0-9a-fA-F]{3,8}\](?=</div>|$)")
_CHOICE_SHORT_ID_RE = re.compile(r" \[[0-9a-z]{1,8}\]")


def redact_text(value: object) -> object:
    """Redact process-local identity from free text (prompts/labels).

    Provenance: mirrors the production twin-stable lineage
    (``XmageFullGameRunner._semantic_text``,
    ``XmageFullGameDecisionController.redactObjectIds``,
    ``XmageFullGamePlayer.choiceText``): per-game engine object identity
    (UUIDs, ``object_id='...'`` attributes, GameLog short-id suffixes)
    carries no Rules content and must not enter semantic digests.
    Rules text itself is untouched.
    """
    if not isinstance(value, str):
        return value
    text = _OBJECT_ID_ATTR_RE.sub("", value)
    text = _UUID_RE.sub("<engine-object>", text)
    text = _SHORT_ID_SUFFIX_RE.sub(r"\1", text)
    text = _SHORT_ID_TAIL_RE.sub("", text)
    return text


def redact_choice_text(value: object) -> object:
    """Choice-text redaction including the ``[xxx]`` short-id suffix."""
    redacted = redact_text(value)
    if not isinstance(redacted, str):
        return redacted
    return _CHOICE_SHORT_ID_RE.sub(" [#]", redacted)


def canonical_bytes(value: Any) -> bytes:
    """Encode a JSON-compatible value to canonical UTF-8 bytes."""
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"non-canonical value for semantic digest: {exc}") from exc
    return text.encode("utf-8")


def canonical_hash(value: Any) -> str:
    """SHA-256 hex of the canonical encoding."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = [
    "CANONICALIZATION_VERSION",
    "canonical_bytes",
    "canonical_hash",
    "redact_choice_text",
    "redact_text",
]

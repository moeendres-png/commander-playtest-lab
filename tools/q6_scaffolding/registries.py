"""Versioned, provenance-bearing grammar registries for Q6 scaffolding.

The registries replace brittle hand-maintained frozensets with explicit
data-driven tables. Every entry is generic by grammar construct (ability
verb, trigger mode, static/ability mode class); card names never appear as
keys. Unknown tokens stay observable: anything not in a registry is
reported exactly and routes to manual review — there is no catch-all
"supported" fallback and no silent coercion.

Registry files (JSON, committed under this package):

- ``verb_registry.json``: ability verb -> mechanical shape + narrow flags.
- ``trigger_mode_registry.json``: recognized trigger-mode values.
- ``static_mode_registry.json``: static/ability ``Mode$`` classes.
- ``unsupported_registry.json``: explicit unsupported constructs.

Shapes name mechanical structure only (``DAMAGE_SHAPE``, ``TOKEN_SHAPE``,
...). A shape never implies a Rules outcome. Flags name narrow,
pre-declared consequences (``COPY_CONTROL``, ``RANDOMNESS``,
``REPLACEMENT``, ``TRIGGER``, ``COMBAT``, ``HIDDEN``,
``LAYER_ADJUDICATION``, ``PREVENTION_ADJUDICATION``, ``MANUAL_REVIEW``).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

REGISTRY_DIR = Path(__file__).resolve().parent

SCHEMA_VERB_REGISTRY_V1 = "q6.verb-registry.v1"
SCHEMA_TRIGGER_MODE_REGISTRY_V1 = "q6.trigger-mode-registry.v1"
SCHEMA_STATIC_MODE_REGISTRY_V1 = "q6.static-mode-registry.v1"
SCHEMA_UNSUPPORTED_REGISTRY_V1 = "q6.unsupported-registry.v1"

# Closed flag vocabulary. The parser maps shapes to consequences through
# SHAPE_SIGNALS below; registry-level flags add only the listed narrow
# consequences. No flag authorizes behavior verdicts, legality, or credit.
KNOWN_FLAGS = frozenset(
    {
        "COPY_CONTROL",
        "RANDOMNESS",
        "REPLACEMENT",
        "TRIGGER",
        "COMBAT",
        "HIDDEN",
        "LAYER_ADJUDICATION",
        "PREVENTION_ADJUDICATION",
        "MANUAL_REVIEW",
    }
)

# Shape -> parser-signal mapping (generic, documented, no card names).
# Signals feed existing boolean features / families / adjudication
# questions; they never encode Rules semantics.
SHAPE_SIGNALS: dict[str, tuple[str, ...]] = {
    "COPY_CONTROL_SHAPE": ("COPY_CONTROL",),
    "RANDOM_SHAPE": ("RANDOMNESS",),
    "TRIGGER_SHAPE": ("TRIGGER",),
    "REPLACEMENT_SHAPE": ("REPLACEMENT",),
    "HIDDEN_SHAPE": ("HIDDEN",),
    "SHUFFLE_SHAPE": ("SHUFFLE",),
    "COMBAT_SHAPE": ("COMBAT",),
}


def _load(name: str) -> dict:
    path = REGISTRY_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load Q6 registry {name}: {exc}") from exc


@cache
def verb_registry() -> dict:
    """Load and minimally validate the verb registry (cached, deterministic)."""
    doc = _load("verb_registry.json")
    if doc.get("schema") != SCHEMA_VERB_REGISTRY_V1:
        raise ValueError(f"verb registry schema mismatch: {doc.get('schema')}")
    if not doc.get("registry_version"):
        raise ValueError("verb registry carries no version")
    if not doc.get("provenance"):
        raise ValueError("verb registry carries no provenance")
    verbs = doc.get("verbs", {})
    for verb, entry in verbs.items():
        if not entry.get("shape"):
            raise ValueError(f"verb {verb} has no mechanical shape")
        for flag in entry.get("flags", []):
            if flag not in KNOWN_FLAGS:
                raise ValueError(f"verb {verb} carries unknown flag {flag!r}")
    return doc


@cache
def trigger_mode_registry() -> dict:
    """Load and minimally validate the trigger-mode registry."""
    doc = _load("trigger_mode_registry.json")
    if doc.get("schema") != SCHEMA_TRIGGER_MODE_REGISTRY_V1:
        raise ValueError(f"trigger-mode registry schema mismatch: {doc.get('schema')}")
    if not doc.get("registry_version"):
        raise ValueError("trigger-mode registry carries no version")
    if not doc.get("provenance"):
        raise ValueError("trigger-mode registry carries no provenance")
    return doc


@cache
def static_mode_registry() -> dict:
    """Load and minimally validate the static/ability-mode registry."""
    doc = _load("static_mode_registry.json")
    if doc.get("schema") != SCHEMA_STATIC_MODE_REGISTRY_V1:
        raise ValueError(f"static-mode registry schema mismatch: {doc.get('schema')}")
    if not doc.get("registry_version"):
        raise ValueError("static-mode registry carries no version")
    if not doc.get("provenance"):
        raise ValueError("static-mode registry carries no provenance")
    return doc


@cache
def unsupported_registry() -> dict:
    """Load and minimally validate the unsupported-construct registry."""
    doc = _load("unsupported_registry.json")
    if doc.get("schema") != SCHEMA_UNSUPPORTED_REGISTRY_V1:
        raise ValueError(f"unsupported registry schema mismatch: {doc.get('schema')}")
    if not doc.get("registry_version"):
        raise ValueError("unsupported registry carries no version")
    required = (
        "construct_id",
        "pattern",
        "first_examples",
        "mechanical_reason",
        "owning_subsystem",
        "safely_scaffolding_implementable",
        "rules_adjudication_required",
        "runtime_qualification_required",
    )
    for entry in doc.get("constructs", []):
        for key in required:
            if key not in entry:
                raise ValueError(
                    f"unsupported construct {entry.get('construct_id')} "
                    f"missing required field {key!r}"
                )
    return doc


def verb_shape(verb: str) -> tuple[str | None, list[str]]:
    """Return (shape, flags) for a verb, or (None, []) when unknown.

    Unknown is a first-class answer: callers must report it exactly and
    route it to review, never coerce it.
    """
    entry = verb_registry().get("verbs", {}).get(verb)
    if entry is None:
        return None, []
    shape = entry["shape"]
    flags = list(dict.fromkeys(list(SHAPE_SIGNALS.get(shape, ())) + list(entry.get("flags", []))))
    return shape, flags


def is_known_trigger_mode(mode: str) -> bool:
    """Return True iff a T-line Mode$ value is a registered trigger mode."""
    return mode in trigger_mode_registry().get("modes", {})


def static_mode_class(line_kind: str, mode: str) -> str | None:
    """Classify an S-line Mode$ value, or None when unregistered."""
    entry = static_mode_registry().get("static_modes", {}).get(mode)
    if entry is None:
        return None
    _ = line_kind
    return entry.get("class")


def ability_mode_class(mode: str) -> str | None:
    """Classify an A-line Mode$ value, or None when unregistered."""
    entry = static_mode_registry().get("ability_modes", {}).get(mode)
    if entry is None:
        return None
    return entry.get("class")

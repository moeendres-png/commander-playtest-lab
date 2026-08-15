from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

AUDIT_PATH = Path("data/enrichment/ORACLE_FACT_COMPLETENESS_CLOSURE_2026-08-15.json")
ORACLE_TEXT_LEGITIMATELY_EMPTY = "oracle_text_legitimately_empty"


class OracleFactVerificationError(RuntimeError):
    """Fail closed when verified Oracle facts drift from current project facts."""


def _normalized_colors(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        # The derived audit uses C for colorless; Commander color identity has no C color.
        return tuple(sorted(symbol for symbol in value if symbol in "WUBRG"))
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(sorted(str(symbol) for symbol in value if str(symbol) in "WUBRG"))
    return ()


def _normalized_number(value: object) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def validate_verified_empty_fact(
    oracle_name: str,
    verification: Mapping[str, object],
    current_fact: Mapping[str, object] | None,
) -> None:
    """Reject stale or contradictory verified-empty Oracle evidence.

    The audit may establish that a card legitimately has no functional Oracle rules text, but it
    may never override newer current project facts. Any material disagreement therefore blocks
    the knowledge pipeline instead of silently preferring one source.
    """
    problems: list[str] = []
    if str(verification.get("oracle_name", "")).strip() != oracle_name:
        problems.append("verification_identity_mismatch")
    if verification.get("oracle_text_classification") != ORACLE_TEXT_LEGITIMATELY_EMPTY:
        problems.append("verification_not_legitimately_empty")
    if str(verification.get("oracle_rules_text", "") or "").strip():
        problems.append("verification_rules_text_not_empty")
    if not str(verification.get("canonical_verification_status", "")).casefold().startswith(
        "verified_"
    ):
        problems.append("verification_status_not_verified")
    if "scryfall" not in str(verification.get("canonical_source_id", "")).casefold():
        problems.append("verification_source_not_scryfall_backed")

    if current_fact is None:
        problems.append("current_fact_missing")
    else:
        current_name = str(current_fact.get("oracle_name", oracle_name)).strip()
        if current_name and current_name != oracle_name:
            problems.append("current_identity_mismatch")
        if str(current_fact.get("oracle_text", "") or "").strip():
            problems.append("current_rules_text_is_now_nonempty")

        current_cost = str(current_fact.get("mana_cost", "") or "")
        verified_cost = str(verification.get("mana_cost", "") or "")
        if current_cost != verified_cost:
            problems.append(f"mana_cost:{current_cost!r}!={verified_cost!r}")

        current_mv = _normalized_number(current_fact.get("mana_value"))
        verified_mv = _normalized_number(verification.get("mana_value"))
        if current_mv is None or verified_mv is None or current_mv != verified_mv:
            problems.append(f"mana_value:{current_mv!r}!={verified_mv!r}")

        current_type = str(
            current_fact.get("type_line", "") or current_fact.get("card_type", "") or ""
        ).strip()
        verified_type = str(verification.get("type_line", "") or "").strip()
        if not current_type or current_type != verified_type:
            problems.append(f"type_line:{current_type!r}!={verified_type!r}")

        current_colors = _normalized_colors(current_fact.get("color_identity"))
        verified_colors = _normalized_colors(verification.get("color_identity"))
        if current_colors != verified_colors:
            problems.append(f"color_identity:{current_colors!r}!={verified_colors!r}")

    if problems:
        raise OracleFactVerificationError(
            f"Oracle verification conflict for {oracle_name}: " + "; ".join(problems)
        )


def load_verified_empty_oracle_audit(root: str | Path) -> dict[str, dict[str, object]]:
    path = Path(root).resolve() / AUDIT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OracleFactVerificationError(f"cannot read Oracle fact audit: {path}") from exc
    rows = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise OracleFactVerificationError("Oracle fact audit cards must be a list")
    declared_count = payload.get("card_count")
    if not isinstance(declared_count, int) or declared_count != len(rows):
        raise OracleFactVerificationError("Oracle fact audit card_count does not match rows")

    result: dict[str, dict[str, object]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise OracleFactVerificationError("Oracle fact audit row must be an object")
        name = str(raw.get("oracle_name", "")).strip()
        if not name or name in result:
            raise OracleFactVerificationError(f"invalid or duplicate Oracle identity: {name!r}")
        result[name] = dict(raw)
    return result


def verified_empty_oracle_names(
    root: str | Path,
    current_facts: Mapping[str, Mapping[str, object]],
) -> frozenset[str]:
    """Return verified no-rules-text identities after current-fact conflict validation."""
    audit = load_verified_empty_oracle_audit(root)
    for name, verification in audit.items():
        validate_verified_empty_fact(name, verification, current_facts.get(name))
    return frozenset(audit)

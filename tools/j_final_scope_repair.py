from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}: got {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_service() -> None:
    path = ROOT / "src/commander_lab/tools/service.py"
    replace_once(
        path,
        '    ACTIVE_OWN_DECK_IDS = ("korvold/current", "rogshai/current")\n'
        '    FROZEN_OPPONENT_ONLY_DECK_IDS = frozenset({"kaervek/current"})\n',
        '    ACTIVE_OWN_DECK_IDS = ("rogshai/current",)\n'
        '    HISTORICAL_OWN_DECK_IDS = ("korvold/current",)\n'
        '    FROZEN_OPPONENT_ONLY_DECK_IDS = frozenset({"kaervek/current"})\n',
    )
    replace_once(
        path,
        '                for deck_id in ("korvold/current", "rogshai/current"):\n',
        '                for deck_id in self.ACTIVE_OWN_DECK_IDS:\n',
    )


def patch_candidates() -> None:
    path = ROOT / "src/commander_lab/tools/candidates.py"
    old = '''def load_current_optimization_availability(root: str | Path) -> dict[str, int]:
    path = Path(root) / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(name): int(quantity) for name, quantity in payload.get("cards", {}).items()}


def load_current_candidate_eligibility(root: str | Path) -> dict[str, set[str]]:
'''
    new = '''def load_current_candidate_availability(
    root: str | Path,
    deck_id: str = "rogshai/current",
) -> dict[str, int]:
    path = Path(root) / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    eligible = payload.get("eligible_by_deck", {})
    if not isinstance(eligible, dict):
        return {}
    rows = eligible.get(deck_id, {})
    if isinstance(rows, dict):
        quantities: dict[str, int] = {}
        for name, metadata in rows.items():
            quantity = 1
            if isinstance(metadata, dict):
                quantity = _as_int(metadata.get("physical_available_quantity", 0))
            if quantity > 0:
                quantities[str(name)] = quantity
        return quantities
    if isinstance(rows, list):
        return {str(name): 1 for name in rows}
    return {}


def load_current_optimization_availability(root: str | Path) -> dict[str, int]:
    # Current RogShai eligibility is the active-scope availability projection. It already
    # incorporates physical ownership and opponent reservations without reserving inactive
    # historical Korvold cards. The old J-P5 two-deck projection is fallback provenance only.
    current = load_current_candidate_availability(root, "rogshai/current")
    if current:
        return current
    path = Path(root) / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(name): int(quantity) for name, quantity in payload.get("cards", {}).items()}


def load_current_candidate_eligibility(root: str | Path) -> dict[str, set[str]]:
'''
    replace_once(path, old, new)

    append = '''

UNMODELED_DISCOVERY_MARKER = "UNMODELED_DISCOVERY_ONLY"


def _unmodeled_discovery_profile(identity: CardIdentity) -> StructuralCardProfile:
    baseline = build_default_profile(identity)
    return baseline.model_copy(
        update={
            "source_quality": DataQuality.PROJECT_INFERRED,
            "notes": (
                f"{UNMODELED_DISCOVERY_MARKER}: legal/physical Fresh-Rebuild candidate remains "
                "discoverable but requires explicit mechanistic profiling before model-dependent "
                "comparison or recommendation."
            ),
        }
    )


def load_fresh_rebuild_candidate_profiles(
    root: str | Path,
    deck_id: str = "rogshai/current",
) -> dict[str, CandidateProfile]:
    """Return the complete current legal/physical discovery universe for one Fresh Rebuild.

    Historical deck membership and allocation are not quality priors. Current-deck cards, former
    Korvold cards, basics, partially modeled cards, and structurally unmodeled cards remain
    discoverable. Unmodeled cards are explicitly marked and must be profiled before model-dependent
    evaluation.
    """

    root_path = Path(root)
    eligible = load_current_candidate_eligibility(root_path).get(deck_id, set())
    if not eligible:
        return {}
    curated_by_name = {
        candidate.card.oracle_name: candidate for candidate in _load_curated(root_path)
    }
    candidates: dict[str, CandidateProfile] = {}
    seen_names: set[str] = set()

    for row in _inventory_rows(root_path):
        name = str(row.get("oracle_name", ""))
        if not name or name not in eligible:
            continue
        if not row.get("currently_owned") or _as_int(row.get("quantity", 0)) <= 0:
            continue
        if str(row.get("commander_legality", "")).casefold() != "legal":
            continue
        identity = _identity_from_inventory(row)
        if deck_id not in _allowed_decks(identity):
            continue
        curated_candidate = curated_by_name.get(name)
        if curated_candidate is not None:
            candidate = curated_candidate.model_copy(
                update={
                    "allowed_deck_ids": (deck_id,),
                    "physical_status": "canonical_inventory_verified_owned",
                    "notes": (curated_candidate.notes or "")
                    + " Fresh-Rebuild discovery ignores historical deck membership/allocation priors.",
                }
            )
        else:
            profile = _inferred_profile(identity)
            if profile is None:
                profile = _unmodeled_discovery_profile(identity)
            candidate = CandidateProfile(
                candidate_id=f"fresh/{_slug(name)}",
                card=profile,
                allowed_deck_ids=(deck_id,),
                physical_status="canonical_inventory_verified_owned",
                notes=(
                    "Current legal/physical Fresh-Rebuild discovery candidate; historical deck "
                    "membership and inactive Korvold allocation are not selection priors."
                ),
            )
        candidates[candidate.candidate_id] = candidate
        seen_names.add(name)

    missing = sorted(eligible - seen_names)
    if missing:
        raise ValueError(
            "current Fresh-Rebuild eligibility contains cards missing from the repo inventory "
            f"projection: {missing[:12]}" + (" ..." if len(missing) > 12 else "")
        )
    return candidates
'''
    text = path.read_text(encoding="utf-8")
    if "UNMODELED_DISCOVERY_MARKER" in text:
        raise SystemExit("fresh discovery helpers already present")
    path.write_text(text.rstrip() + append + "\n", encoding="utf-8")


def main() -> None:
    patch_service()
    patch_candidates()


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.meta import MetaKnowledgeBase
from commander_lab.models import CardRole, FormatBand, StructuralDeckProfile
from commander_lab.models.packages import (
    ArchetypeName,
    ArchetypeProfile,
    ArchetypeWeight,
    ExtractionMethod,
    PackageDefinition,
    PackageEvaluation,
    PackageRegistry,
    PackageStatus,
    PackageVersionComparison,
)
from commander_lab.storage.hashing import sha256_value

COMMANDER_LABELS = {
    "korvold/current": "Korvold, Fae-Cursed King",
    "rogshai/current": "Ishai, Ojutai Dragonspeaker / Rograkh, Son of Rohgahh",
}


class PackageExtractionError(ValueError):
    pass


class ArchetypePackageExtractor:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.registry_path = self.root / "data/packages/package_registry.json"
        self.registry = PackageRegistry.model_validate_json(
            self.registry_path.read_text(encoding="utf-8")
        )
        self.decks = load_project_structural_decks(
            self.root, include_synthetic_fixtures=True, include_current_opponents=True
        )

    def deck(self, deck_id: str) -> StructuralDeckProfile:
        try:
            return self.decks[deck_id]
        except KeyError as exc:
            raise PackageExtractionError(f"unknown deck_id: {deck_id}") from exc

    @staticmethod
    def commander_label(deck: StructuralDeckProfile) -> str:
        if deck.deck_id in COMMANDER_LABELS:
            return COMMANDER_LABELS[deck.deck_id]
        return " / ".join(deck.commander_names)

    def extract_archetypes(self, deck_id: str) -> ArchetypeProfile:
        deck = self.deck(deck_id)
        counts: Counter[ArchetypeName] = Counter()
        for card in deck.cards:
            roles = card.roles
            if CardRole.SACRIFICE_OUTLET in roles or CardRole.TOKEN_SOURCE in roles:
                counts[ArchetypeName.SACRIFICE] += 2
            if CardRole.LAND_SYNERGY in roles:
                counts[ArchetypeName.LAND_ENGINE] += 2
            if CardRole.RECURSION in roles:
                counts[ArchetypeName.GRAVEYARD_RECURSION] += 2
            if card.commander_synergy >= 1.0 or CardRole.ENGINE in roles:
                counts[ArchetypeName.COMMANDER_VALUE] += 1
            if CardRole.COMBAT_PAYOFF in roles:
                counts[ArchetypeName.VOLTRON] += 2
            if CardRole.COUNTER in roles or CardRole.SELECTION in roles:
                counts[ArchetypeName.TEMPO] += 1
            if CardRole.COUNTER in roles or CardRole.REMOVAL in roles or CardRole.WIPE in roles:
                counts[ArchetypeName.CONTROL] += 1
            if CardRole.SELECTION in roles or CardRole.DRAW in roles:
                counts[ArchetypeName.SPELLSLINGER] += 1
            if any(
                token in card.oracle_name.lower()
                for token in ("manufactor", "clue", "treasure", "food", "artifact")
            ):
                counts[ArchetypeName.ARTIFACT_ENGINE] += 1
            if CardRole.TOKEN_SOURCE in roles:
                counts[ArchetypeName.GO_WIDE] += 1
            if card.multiplayer_scaling >= 0.7 or any(
                token in card.oracle_name.lower()
                for token in ("bats", "gutter", "massacre", "exsanguinate", "mayhem")
            ):
                counts[ArchetypeName.PUNISHER] += 1
            if CardRole.FINISHER in roles and card.immediate_impact >= 0.8:
                counts[ArchetypeName.COMBO] += 1
            if CardRole.PROTECTION in roles or CardRole.REMOVAL in roles:
                counts[ArchetypeName.MIDRANGE] += 1
            if CardRole.RAMP in roles and card.mana_value <= 1:
                counts[ArchetypeName.TURBO] += 1
        total = max(1, sum(counts.values()))
        ranked = counts.most_common()
        # Retain explainable multi-archetype weights; cap at seven nonzero axes.
        weights = tuple(
            ArchetypeWeight(
                archetype=archetype,
                weight=round(count / total, 6),
                evidence=(ExtractionMethod.RULE_ROLES,),
            )
            for archetype, count in ranked[:7]
        )
        selected_total = sum(item.weight for item in weights)
        if selected_total > 0:
            weights = tuple(
                item.model_copy(update={"weight": item.weight / selected_total}) for item in weights
            )
        return ArchetypeProfile(
            profile_id=f"{deck.deck_id.replace('/', '-')}-{deck.deck_hash[:12]}",
            commander=self.commander_label(deck),
            deck_hash=deck.deck_hash,
            weights=weights,
            sample_size=1,
            small_sample=True,
            source_ids=("local-project-meta-2026-08-05", "structural-role-profiles"),
            confidence=0.72,
        )

    def packages_for_deck(
        self, deck_id: str, *, include_machine_candidates: bool = True
    ) -> dict[str, Any]:
        deck = self.deck(deck_id)
        commander = self.commander_label(deck)
        curated = list(self.registry.by_commander(commander))
        machine, machine_rejections = (
            self._machine_candidates(commander) if include_machine_candidates else ([], [])
        )
        evaluations = [self.evaluate(deck_id, p.package_id, version=p.version) for p in curated]
        return {
            "deck_id": deck_id,
            "deck_hash": deck.deck_hash,
            "commander": commander,
            "archetype_profile": self.extract_archetypes(deck_id).model_dump(mode="json"),
            "curated_packages": [p.model_dump(mode="json") for p in curated],
            "machine_candidates": [p.model_dump(mode="json") for p in machine],
            "machine_rejections": machine_rejections,
            "evaluations": [e.model_dump(mode="json") for e in evaluations],
            "machine_candidates_are_confirmed": False,
            "automatic_deck_application": False,
        }

    def _machine_candidates(
        self, commander: str
    ) -> tuple[list[PackageDefinition], list[dict[str, Any]]]:
        try:
            snapshot = MetaKnowledgeBase(self.root).load_snapshot()
        except (FileNotFoundError, ValueError):
            return [], [{"reason": "meta snapshot unavailable"}]
        groups: dict[FormatBand, list[Any]] = {}
        for deck in snapshot.deck_snapshots:
            if deck.commander == commander:
                groups.setdefault(deck.format_band, []).append(deck)
        candidates: list[PackageDefinition] = []
        rejections: list[dict[str, Any]] = []
        package_cards = {card for package in snapshot.packages for card in package.cards}
        for format_band, decks in sorted(groups.items(), key=lambda item: str(item[0])):
            if len(decks) < 3:
                rejections.append(
                    {
                        "format_band": str(format_band),
                        "sample_size": len(decks),
                        "reason": "sample below minimum of 3 same-format deck snapshots",
                    }
                )
                continue
            pair_counts: Counter[tuple[str, str]] = Counter()
            for deck in decks:
                relevant = sorted(set(deck.decklist) & package_cards)
                for i, left in enumerate(relevant):
                    for right in relevant[i + 1 :]:
                        pair_counts[(left, right)] += 1
            threshold = max(2, round(len(decks) * 0.6))
            for (left, right), count in pair_counts.most_common(5):
                if count < threshold:
                    continue
                pid = f"machine-{sha256_value((commander, str(format_band), left, right))[:16]}"
                candidates.append(
                    PackageDefinition(
                        package_id=pid,
                        version="0.1.0",
                        name=f"Machine co-occurrence: {left} + {right}",
                        commander=commander,
                        archetype=ArchetypeName.MIDRANGE,
                        core_cards=(left, right),
                        minimum_density=2,
                        redundancy=1,
                        source_ids=tuple(sorted({deck.source_id for deck in decks})),
                        confidence=min(0.69, count / len(decks)),
                        format_band=format_band,
                        status=PackageStatus.MACHINE_EXTRACTED,
                        extraction_methods=(
                            ExtractionMethod.CO_OCCURRENCE,
                            ExtractionMethod.CARD_FREQUENCY,
                        ),
                        sample_size=len(decks),
                        failure_modes=(
                            "co-occurrence does not prove synergy",
                            "manual domain review required",
                        ),
                        notes="Candidate only; manual domain review is required before curated status.",
                    )
                )
        return candidates, rejections

    def inspect(self, package_id: str, version: str | None = None) -> PackageDefinition:
        if version is None:
            return self.registry.latest(package_id)
        for package in self.registry.packages:
            if package.package_id == package_id and package.version == version:
                return package
        raise PackageExtractionError(f"unknown package version: {package_id}@{version}")

    def evaluate(
        self, deck_id: str, package_id: str, *, version: str | None = None
    ) -> PackageEvaluation:
        deck = self.deck(deck_id)
        package = self.inspect(package_id, version)
        commander = self.commander_label(deck)
        if package.commander != commander:
            raise PackageExtractionError(
                f"package commander mismatch: {package.commander!r} cannot be evaluated for {commander!r}"
            )
        names = {card.oracle_name for card in deck.cards}
        present = tuple(card for card in package.all_cards if card in names)
        missing_core = tuple(card for card in package.core_cards if card not in names)
        density = len(present)
        completeness = density / len(package.all_cards)
        enablers_present = tuple(card for card in package.enablers if card in names)
        payoffs_present = tuple(card for card in package.payoffs if card in names)
        support_present = tuple(card for card in package.support_cards if card in names)
        dead_support = support_present if not payoffs_present else ()
        payoffs_without = payoffs_present if package.enablers and not enablers_present else ()
        redundancy_present = max(
            len(enablers_present), len(payoffs_present), len(set(present) & set(package.core_cards))
        )
        key_card = (
            missing_core[0]
            if missing_core
            else (package.core_cards[0] if package.core_cards else None)
        )
        fragile_card = None
        if len(enablers_present) == 1:
            fragile_card = enablers_present[0]
        elif len(payoffs_present) == 1:
            fragile_card = payoffs_present[0]
        excess = max(0, density - package.minimum_density)
        marginal = min(1.0, excess / max(1, len(package.all_cards) - package.minimum_density))
        warnings: list[str] = []
        failures: list[str] = []
        if missing_core:
            failures.append("missing core cards")
        if density < package.minimum_density:
            failures.append("minimum density not met")
        if redundancy_present < package.redundancy:
            failures.append("redundancy below target")
        if dead_support:
            failures.append("support cards present without payoff")
        if payoffs_without:
            failures.append("payoffs present without enabler")
        if package.supported_deck_hashes and deck.deck_hash not in package.supported_deck_hashes:
            warnings.append("deck version is outside curated supported_deck_hashes")
        if package.sample_size < 5:
            warnings.append("small evidence sample")
        return PackageEvaluation(
            package_id=package.package_id,
            package_version=package.version,
            deck_hash=deck.deck_hash,
            commander=commander,
            present_cards=present,
            missing_core_cards=missing_core,
            package_completeness=round(completeness, 6),
            density=density,
            minimum_density=package.minimum_density,
            minimum_density_met=density >= package.minimum_density and not missing_core,
            redundancy_present=redundancy_present,
            redundancy_required=package.redundancy,
            redundancy_met=redundancy_present >= package.redundancy,
            key_card=key_card,
            fragile_card=fragile_card,
            dead_support_cards=dead_support,
            payoffs_without_enabler=payoffs_without,
            diminishing_marginal_utility=round(marginal, 6),
            failure_modes_triggered=tuple(failures),
            context_compatible=package.commander == commander,
            warnings=tuple(warnings),
        )

    def compare_versions(
        self, package_id: str, older_version: str, newer_version: str
    ) -> PackageVersionComparison:
        old = self.inspect(package_id, older_version)
        new = self.inspect(package_id, newer_version)
        return PackageVersionComparison(
            package_id=package_id,
            older_version=older_version,
            newer_version=newer_version,
            added_core_cards=tuple(sorted(set(new.core_cards) - set(old.core_cards))),
            removed_core_cards=tuple(sorted(set(old.core_cards) - set(new.core_cards))),
            added_support_cards=tuple(sorted(set(new.support_cards) - set(old.support_cards))),
            removed_support_cards=tuple(sorted(set(old.support_cards) - set(new.support_cards))),
            minimum_density_delta=new.minimum_density - old.minimum_density,
            redundancy_delta=new.redundancy - old.redundancy,
            status_changed=new.status != old.status,
            confidence_delta=round(new.confidence - old.confidence, 6),
        )

    def detect_orphans(self, deck_id: str) -> dict[str, Any]:
        deck = self.deck(deck_id)
        commander = self.commander_label(deck)
        evaluations = [
            self.evaluate(deck_id, pkg.package_id, version=pkg.version)
            for pkg in self.registry.by_commander(commander)
        ]
        support = sorted({card for item in evaluations for card in item.dead_support_cards})
        payoff = sorted({card for item in evaluations for card in item.payoffs_without_enabler})
        incomplete = sorted(item.package_id for item in evaluations if not item.minimum_density_met)
        return {
            "deck_id": deck_id,
            "deck_hash": deck.deck_hash,
            "orphaned_support_cards": support,
            "payoffs_without_enabler": payoff,
            "incomplete_packages": incomplete,
            "automatic_deck_application": False,
        }

    def package_cards_for_ablation(self, deck_id: str, package_id: str) -> tuple[str, ...]:
        deck = self.deck(deck_id)
        evaluation = self.evaluate(deck_id, package_id)
        removable = tuple(
            card for card in evaluation.present_cards if card not in deck.commander_names
        )
        if not removable:
            raise PackageExtractionError("package has no removable present cards to ablate")
        return removable

    def generate_report(self, deck_id: str) -> str:
        result = self.packages_for_deck(deck_id)
        lines = [
            "# Archetype and Package Report",
            "",
            f"Deck: `{deck_id}`",
            f"Deck hash: `{result['deck_hash']}`",
            f"Commander: {result['commander']}",
            "",
            "All results are structural/reference diagnostics. No package is automatically added to the deck.",
            "",
            "## Archetypes",
        ]
        for row in result["archetype_profile"]["weights"]:
            lines.append(f"- {row['archetype']}: {row['weight']:.3f}")
        lines.extend(["", "## Curated packages"])
        for package, evaluation in zip(
            result["curated_packages"], result["evaluations"], strict=True
        ):
            lines.append(
                f"- `{package['package_id']}` — status={package['status']}, density={evaluation['density']}/{evaluation['minimum_density']}, "
                f"completeness={evaluation['package_completeness']:.2f}, failures={', '.join(evaluation['failure_modes_triggered']) or 'none'}"
            )
        lines.extend(["", "## Machine candidates"])
        if result["machine_candidates"]:
            for package in result["machine_candidates"]:
                lines.append(
                    f"- `{package['package_id']}` — candidate only; confidence={package['confidence']:.2f}"
                )
        else:
            lines.append(
                "- None passed the conservative same-format sample/co-occurrence threshold."
            )
        if result.get("machine_rejections"):
            lines.extend(["", "## Rejected machine clusters"])
            for row in result["machine_rejections"]:
                lines.append(
                    f"- {row.get('format_band', 'unknown')}: sample={row.get('sample_size', 0)} — {row['reason']}"
                )
        return "\n".join(lines) + "\n"

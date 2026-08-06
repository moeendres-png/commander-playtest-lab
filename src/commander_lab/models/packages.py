from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from .common import FrozenModel, MutableModel
from .meta import FormatBand

PACKAGE_SCHEMA_VERSION = "1.0.0"


class ArchetypeName(StrEnum):
    SACRIFICE = "sacrifice"
    LAND_ENGINE = "land_engine"
    GRAVEYARD_RECURSION = "graveyard_recursion"
    COMMANDER_VALUE = "commander_value"
    VOLTRON = "voltron"
    TEMPO = "tempo"
    CONTROL = "control"
    SPELLSLINGER = "spellslinger"
    ARTIFACT_ENGINE = "artifact_engine"
    GO_WIDE = "go_wide"
    PUNISHER = "punisher"
    COMBO = "combo"
    STAX = "stax"
    MIDRANGE = "midrange"
    TURBO = "turbo"


class PackageStatus(StrEnum):
    CANDIDATE = "candidate"
    MACHINE_EXTRACTED = "machine_extracted"
    CURATED = "curated"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ExtractionMethod(StrEnum):
    RULE_ROLES = "rule_roles"
    CARD_FREQUENCY = "card_frequency"
    CO_OCCURRENCE = "co_occurrence"
    PRIMER_HINT = "primer_hint"
    KNOWN_SYNERGY = "known_synergy"
    MANUAL_CURRATION = "manual_curation"


class ArchetypeWeight(FrozenModel):
    archetype: ArchetypeName
    weight: float = Field(ge=0.0, le=1.0)
    evidence: tuple[ExtractionMethod, ...] = ()
    notes: str | None = None


class ArchetypeProfile(FrozenModel):
    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    commander: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    weights: tuple[ArchetypeWeight, ...]
    sample_size: int = Field(default=1, ge=1)
    small_sample: bool = True
    source_ids: tuple[str, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    automatic_deck_application: bool = False

    @model_validator(mode="after")
    def validate_weights(self) -> "ArchetypeProfile":
        if not self.weights:
            raise ValueError("at least one archetype weight is required")
        total = sum(item.weight for item in self.weights)
        if total <= 0 or total > 1.000001:
            raise ValueError("archetype weights must sum to a value in (0, 1]")
        return self


class PackageDefinition(FrozenModel):
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{2,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str
    commander: str
    archetype: ArchetypeName
    core_cards: tuple[str, ...]
    support_cards: tuple[str, ...] = ()
    optional_cards: tuple[str, ...] = ()
    minimum_density: int = Field(ge=1)
    redundancy: int = Field(default=1, ge=1)
    enablers: tuple[str, ...] = ()
    payoffs: tuple[str, ...] = ()
    finishers: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    source_ids: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    format_band: FormatBand
    status: PackageStatus
    extraction_methods: tuple[ExtractionMethod, ...]
    supported_deck_hashes: tuple[str, ...] = ()
    sample_size: int = Field(default=1, ge=1)
    notes: str | None = None
    automatic_deck_application: bool = False

    @field_validator("core_cards", "support_cards", "optional_cards", "enablers", "payoffs", "finishers")
    @classmethod
    def normalize_cards(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(" ".join(card.split()) for card in value if card.strip()))
        if len(normalized) != len(value):
            raise ValueError("package card lists must contain unique nonblank names")
        return normalized

    @model_validator(mode="after")
    def validate_package(self) -> "PackageDefinition":
        if not self.core_cards:
            raise ValueError("core_cards may not be empty")
        available = set(self.core_cards) | set(self.support_cards) | set(self.optional_cards) | set(self.enablers) | set(self.payoffs) | set(self.finishers)
        if self.minimum_density > len(available):
            raise ValueError("minimum_density exceeds package card count")
        if self.status in {PackageStatus.CURATED, PackageStatus.VALIDATED} and ExtractionMethod.MANUAL_CURRATION not in self.extraction_methods:
            raise ValueError("curated or validated packages require manual_curation evidence")
        return self

    @property
    def all_cards(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.core_cards, *self.support_cards, *self.optional_cards, *self.enablers, *self.payoffs, *self.finishers)))


class PackageEvaluation(FrozenModel):
    package_id: str
    package_version: str
    deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    commander: str
    present_cards: tuple[str, ...]
    missing_core_cards: tuple[str, ...]
    package_completeness: float = Field(ge=0.0, le=1.0)
    density: int = Field(ge=0)
    minimum_density: int = Field(ge=1)
    minimum_density_met: bool
    redundancy_present: int = Field(ge=0)
    redundancy_required: int = Field(ge=1)
    redundancy_met: bool
    key_card: str | None = None
    fragile_card: str | None = None
    dead_support_cards: tuple[str, ...] = ()
    payoffs_without_enabler: tuple[str, ...] = ()
    diminishing_marginal_utility: float = Field(ge=0.0, le=1.0)
    failure_modes_triggered: tuple[str, ...] = ()
    context_compatible: bool
    warnings: tuple[str, ...] = ()
    automatic_deck_application: bool = False


class PackageVersionComparison(FrozenModel):
    package_id: str
    older_version: str
    newer_version: str
    added_core_cards: tuple[str, ...] = ()
    removed_core_cards: tuple[str, ...] = ()
    added_support_cards: tuple[str, ...] = ()
    removed_support_cards: tuple[str, ...] = ()
    minimum_density_delta: int = 0
    redundancy_delta: int = 0
    status_changed: bool = False
    confidence_delta: float = 0.0


class PackageRegistry(MutableModel):
    schema_version: str = PACKAGE_SCHEMA_VERSION
    generated_at: str
    packages: tuple[PackageDefinition, ...]
    archetype_catalog: tuple[ArchetypeName, ...] = tuple(ArchetypeName)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_versions(self) -> "PackageRegistry":
        keys = [(item.package_id, item.version) for item in self.packages]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate package_id/version in registry")
        return self

    def latest(self, package_id: str) -> PackageDefinition:
        matches = [p for p in self.packages if p.package_id == package_id]
        if not matches:
            raise KeyError(package_id)
        return sorted(matches, key=lambda p: tuple(int(x) for x in p.version.split(".")))[-1]

    def by_commander(self, commander: str) -> tuple[PackageDefinition, ...]:
        latest: dict[str, PackageDefinition] = {}
        for package in self.packages:
            if package.commander != commander or package.status == PackageStatus.REJECTED:
                continue
            previous = latest.get(package.package_id)
            key = tuple(int(part) for part in package.version.split("."))
            if previous is None or key > tuple(int(part) for part in previous.version.split(".")):
                latest[package.package_id] = package
        return tuple(latest[key] for key in sorted(latest))

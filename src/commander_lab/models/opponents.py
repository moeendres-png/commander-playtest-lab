from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .cards import CommanderConfiguration, Deck, DeckEntry
from .common import DataQuality, MutableModel, NumericRange, SourceRef


class OpponentEvidenceKind(StrEnum):
    VERIFIED_FULL_DECK = "verified_full_deck"
    OFFICIAL_PRECON = "official_precon"
    DIRECTLY_OBSERVED = "directly_observed"
    REPORTED = "reported"
    PARTIALLY_OBSERVED = "partially_observed"
    INFERRED = "inferred"
    SYNTHETIC_COMPLETION = "synthetic_completion"
    UNKNOWN = "unknown"


class OpponentListStatus(StrEnum):
    VERIFIED_COMPLETE = "verified_complete"
    OFFICIAL_PRECON = "official_precon"
    PARTIALLY_KNOWN = "partially_known"
    SYNTHETIC_COMPLETION = "synthetic_completion"
    ROLE_PROFILE_ONLY = "role_profile_only"


class UncertaintyModel(MutableModel):
    confidence: float = Field(default=0.5, ge=0, le=1)
    known_card_count: int = Field(default=0, ge=0, le=100)
    synthetic_card_count: int = Field(default=0, ge=0, le=100)
    speed_turn_range: NumericRange | None = None
    interaction_density_range: NumericRange | None = None
    boardwipe_count_range: NumericRange | None = None
    role_density_ranges: dict[str, NumericRange] = Field(default_factory=dict)
    plausible_variants: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def known_and_synthetic_fit_deck(self) -> UncertaintyModel:
        if self.known_card_count + self.synthetic_card_count > 100:
            raise ValueError("known plus synthetic cards cannot exceed 100")
        return self


class OpponentProfile(MutableModel):
    profile_id: str
    name: str
    commander: CommanderConfiguration
    list_status: OpponentListStatus
    deck: Deck | None = None
    known_cards: list[DeckEntry] = Field(default_factory=list)
    archetypes: set[str] = Field(default_factory=set)
    strategic_roles: dict[str, float] = Field(default_factory=dict)
    pilot_style: str = "generic"
    uncertainty: UncertaintyModel = Field(default_factory=UncertaintyModel)
    sources: list[SourceRef] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.UNKNOWN
    notes: str | None = None

    @model_validator(mode="after")
    def verified_profiles_need_deck(self) -> OpponentProfile:
        if (
            self.list_status
            in {
                OpponentListStatus.VERIFIED_COMPLETE,
                OpponentListStatus.OFFICIAL_PRECON,
            }
            and self.deck is None
        ):
            raise ValueError("complete or official-precon profiles require a concrete deck")
        return self

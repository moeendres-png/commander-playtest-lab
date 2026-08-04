from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from .common import MutableModel


class PlaytestParticipant(MutableModel):
    player_id: str
    player_name: str | None = None
    deck_name: str
    commander_names: list[str] = Field(default_factory=list)
    seat: int = Field(ge=0)
    placement: int | None = Field(default=None, ge=1)
    final_life: int | None = None
    mulligans: int | None = Field(default=None, ge=0)
    notes: str | None = None


class RealPlaytest(MutableModel):
    game_id: str
    played_on: date | None = None
    pod_size: int = Field(ge=2, le=10)
    participants: list[PlaytestParticipant]
    turns: int | None = Field(default=None, ge=0)
    winner_player_ids: list[str] = Field(default_factory=list)
    end_reason: str | None = None
    starting_player_id: str | None = None
    freeform_log: str | None = None
    source_file: str | None = None
    validated: bool = False

    @model_validator(mode="after")
    def participants_match_pod(self) -> RealPlaytest:
        if len(self.participants) != self.pod_size:
            raise ValueError("participant count must equal pod_size")
        ids = {p.player_id for p in self.participants}
        if len(ids) != len(self.participants):
            raise ValueError("participant ids must be unique")
        if not set(self.winner_player_ids).issubset(ids):
            raise ValueError("winner ids must reference participants")
        return self

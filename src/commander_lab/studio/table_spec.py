"""The table setting shared by SIMULATE and PLAY (``TableSpec``, B2, #1658).

One versioned JSON object says who sits at the table and how the games are seated: the number
of seats, the opponents (repository precons or any Studio deck state, E15 Q6), how opponents are
chosen, which seats the tested deck takes and the pilot profile. Its SHA-256 (``table_hash``,
over canonical JSON) is written into every plan and result. This module is the only place the
table is defined; the pool (S1) and PLAY (P1) build on it.

Rules: the seat count is checked against the released maximum (``launch.MAX_RELEASED_SEATS``,
today four; five and six stay locked until the Owner releases them); an unknown deck is an error,
never replaced; there is no ``seed_step`` (consecutive seeds, so the starting seat
``seed % seats`` rotates). Opponent rotation and draw are part of the model but not yet run:
asking for them is an explicit error until the follow-up package.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .launch import MAX_SEATS, MIN_SEATS, validate_released_seat_count

SCHEMA = "studio-table-spec-1"
DEFAULT_STYLE = 0.5
STRENGTH = "near_optimal_heuristic"
#: Opponent modes of the model; only ``fixed`` runs in B2a (#1658, comment of the builder).
OPPONENT_MODES = ("fixed", "rotation", "draw")
RUNNABLE_OPPONENT_MODES = ("fixed",)


class PilotProfile(BaseModel):
    """The pilot of every seat; the fingerprint is filled in when a plan is resolved."""

    model_config = ConfigDict(extra="forbid")

    style: float = Field(default=DEFAULT_STYLE, ge=0.0, le=1.0)
    strength: Literal["near_optimal_heuristic"] = STRENGTH


class TableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["studio-table-spec-1"] = Field(default=SCHEMA, alias="schema")
    seats: int = Field(ge=MIN_SEATS, le=MAX_SEATS)
    opponent_mode: Literal["fixed", "rotation", "draw"] = "fixed"
    #: ``fixed``: the opponents in seat order after the tested deck (precon id or deck state).
    opponents: list[str] = Field(default_factory=list, max_length=MAX_SEATS - 1)
    #: ``rotation``: several fixed tables, balanced per block (modelled, not yet run).
    opponent_tables: list[list[str]] | None = None
    #: ``draw``: opponents drawn from this pool with ``draw_seed`` (modelled, not yet run).
    draw_pool: list[str] | None = None
    draw_seed: int | None = None
    #: ``rotate``: the tested deck takes every seat in turn; ``fixed``: seat 0 only.
    seat_policy: Literal["rotate", "fixed"] = "rotate"
    pilot: PilotProfile = Field(default_factory=PilotProfile)

    @model_validator(mode="after")
    def _check(self) -> TableSpec:
        validate_released_seat_count(self.seats - 1)
        if self.opponent_mode == "fixed":
            if len(self.opponents) != self.seats - 1:
                raise ValueError(
                    f"ein Tisch mit {self.seats} Sitzen braucht {self.seats - 1} Gegner, "
                    f"angegeben sind {len(self.opponents)}"
                )
            cleaned = [o.strip() for o in self.opponents]
            if any(not o for o in cleaned):
                raise ValueError("leere Gegner-Kennung")
            if len(set(cleaned)) != len(cleaned):
                raise ValueError("Gegner-Decks dürfen nicht doppelt vorkommen")
        return self

    def ensure_runnable(self) -> None:
        """Refuse what the model holds but B2a cannot play yet (explicit, never a fallback)."""
        if self.opponent_mode not in RUNNABLE_OPPONENT_MODES:
            raise ValueError(
                f"Gegner-Modus {self.opponent_mode!r} ist modelliert, aber noch nicht umgesetzt "
                "(Folgepaket zu #1658); heute läuft nur 'fixed'"
            )
        if self.pilot.style != DEFAULT_STYLE:
            raise ValueError(
                f"gepaarte Serien spielen heute mit Stil {DEFAULT_STYLE}; ein anderer Stil ist "
                "noch nicht umgesetzt"
            )

    def tested_seats(self) -> list[int]:
        return list(range(self.seats)) if self.seat_policy == "rotate" else [0]

    def canonical(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, mode="json")


def canonical_json(value: object) -> bytes:
    """The one serialization every hash of B2 is taken over."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_of(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def table_hash(resolved_table: dict[str, object]) -> str:
    """SHA-256 of a resolved table (the spec with deck hashes and pilot fingerprint)."""
    return sha256_of(resolved_table)

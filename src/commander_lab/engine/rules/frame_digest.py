"""Normalized digest of every decision request a full game's pilots were shown.

The semantic transcript hash of a game (``XmageFullGameRunner.semantic_transcript``) covers what
the pilots chose, not what they saw. This module adds the missing half: a running SHA-256 over
every decision request the policy receives, in order, after a deterministic normalization, so two
bridge builds can be shown to present the same observations. It only observes: the pilots get the
unchanged request and play is untouched.

Normalization of one request (documented here because it is the proof obligation):

* Dropped, the complete list of transport fields (top level of the request only):
  ``timeout_millis`` (a request deadline, not an observation), ``protocol_version`` and
  ``protocol_identity`` (version strings of the wire protocol; the handshake checks them).
  Nothing else is dropped, and only a number for ``timeout_millis`` and a text for the two
  version fields: the same key with another type stays in the digest.
* Run identity becomes ``id#<n>``, numbered by first appearance within the game, so "the same
  object twice" stays visible and only the arbitrary value disappears:
  UUID-shaped text anywhere (the same pattern the transcript normalization uses), and the values
  of ``option_id``, ``decision_id``, ``public_state_reference`` and
  ``private_actor_state_reference`` when they are 64-hex hashes (the bridge derives these over
  the UUID-bearing views, so they differ in every run); any other value is digested as text.
* Text leaves then go through ``XmageFullGameRunner._semantic_text``, the transcript
  normalization itself: it drops the engine's appended short ids (``Name [3a4]``) and the
  ``object_id=`` attributes of prompt markup.
* ``pilot_state.commander_status`` is an unordered collection: the bridge builds it from a map
  keyed by UUID, so its entry order follows the run's UUIDs. Its entries are sorted by their
  normalized text with unnumbered UUIDs masked, then numbered in that order.
* ``pilot_state.players[].exile`` is unordered among equal cards: the bridge sorts a player's
  exiled cards by name and zone-change counter and breaks ties by UUID, so two such cards (two
  copies of one card) change places from run to run on the same build. It is sorted the same
  way; the exile zone has no order in the rules and the pilots only test membership.
  Every other list keeps its order (battlefield, hand, options, stack ...).

Everything else is digested as it is.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import RulesDeckInput

from .full_game import FullGamePilotBinding, XmageFullGameRunner
from .full_game_pilot import ExternalPilotDecisionPolicy

Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]

#: Transport fields that are not observation content (top level of a request only).
EXCLUDED_TRANSPORT_FIELDS: frozenset[str] = frozenset(
    {"timeout_millis", "protocol_version", "protocol_identity"}
)
#: Keys whose string value is a bridge-derived hash over run identity.
DERIVED_ID_KEYS: frozenset[str] = frozenset(
    {"option_id", "decision_id", "public_state_reference", "private_actor_state_reference"}
)
#: Lists (path from the request root) whose order depends on the run's UUIDs (see module text).
UNORDERED_LISTS: frozenset[tuple[str, ...]] = frozenset(
    {("pilot_state", "commander_status"), ("pilot_state", "players", "exile")}
)

# The pattern of ``XmageFullGameRunner._semantic_text`` for engine object ids; a test pins that
# both agree.
_UUID_RE = re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


# A bridge-derived hash, optionally with the view prefix the state references carry.
_DERIVED_HASH_RE = re.compile(r"(?P<prefix>(?:public-view:|actor-view:)?)(?P<hash>[0-9a-f]{64})")


def _dump(value: Json) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class _Normalizer:
    """Maps run identity to ``id#<n>``; one instance per game."""

    def __init__(self, ids: dict[str, str] | None = None, *, mask: bool = False) -> None:
        self.ids: dict[str, str] = {} if ids is None else ids
        # In mask mode ids already numbered keep their placeholder and unseen ones become a
        # constant, so the text does not depend on the order it is produced in (sort keys).
        self._mask = mask

    def _ident(self, raw: str) -> str:
        key = raw.lower()
        if self._mask:
            return self.ids.get(key, "<id>")
        placeholder = self.ids.get(key)
        if placeholder is None:
            placeholder = f"id#{len(self.ids)}"
            self.ids[key] = placeholder
        return placeholder

    def _text(self, raw: str) -> str:
        # Cheap guards: a text without these characters cannot match the patterns below.
        mapped = _UUID_RE.sub(lambda match: self._ident(match.group(0)), raw) if "-" in raw else raw
        if "[" not in mapped and "object_id" not in mapped.lower():
            return mapped
        return str(XmageFullGameRunner._semantic_text(mapped))

    def value(self, value: object, path: tuple[str, ...] = ()) -> Json:
        if isinstance(value, str):
            return self._text(value)
        if isinstance(value, Mapping):
            # Unordered lists are numbered last, so their arbitrary order cannot decide numbers.
            keys = sorted(str(key) for key in value)
            keys.sort(key=lambda key: (*path, key) in UNORDERED_LISTS)
            out: dict[str, Json] = {}
            for key in keys:
                item = value[key]
                derived = _DERIVED_HASH_RE.fullmatch(item) if isinstance(item, str) else None
                if key in DERIVED_ID_KEYS and derived is not None:
                    out[self._text(key)] = derived["prefix"] + self._ident(derived["hash"])
                else:
                    out[self._text(key)] = self.value(item, (*path, key))
            return out
        if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
            if path in UNORDERED_LISTS:
                return self._ordered(value, path)
            return [self.value(item, path) for item in value]
        if value is None or isinstance(value, bool | int | float):
            return value
        return self._text(str(value))

    def _ordered(self, value: Sequence[object], path: tuple[str, ...]) -> list[Json]:
        """Entries of an unordered list, by their normalized text (ties are equal content)."""
        trial = _Normalizer(self.ids, mask=True)
        keyed = sorted(
            ((_dump(trial.value(item, path)), item) for item in value), key=lambda pair: pair[0]
        )
        return [self.value(item, path) for _, item in keyed]


def normalize_frame(request: Mapping[str, object]) -> dict[str, Json]:
    """The normalized form of one request, with a fresh identity numbering (for tests)."""
    return _normalize_request(_Normalizer(), request)


def _is_transport(key: str, item: object) -> bool:
    """A transport field of the expected type; the same key with another type is content."""
    if key == "timeout_millis":
        return isinstance(item, int | float) and not isinstance(item, bool)
    return key in EXCLUDED_TRANSPORT_FIELDS and isinstance(item, str)


def _normalize_request(norm: _Normalizer, request: Mapping[str, object]) -> dict[str, Json]:
    kept = {key: item for key, item in request.items() if not _is_transport(key, item)}
    return cast(dict[str, Json], norm.value(kept))


@dataclass(frozen=True)
class FrameDigestResult:
    """Digest of all frames of one game, per seat, and the frame count."""

    digest: str
    by_seat: dict[str, str]
    frames: int


@dataclass
class FrameDigest:
    """Running digest over the decision requests of one game, in the order received."""

    _norm: _Normalizer = field(default_factory=_Normalizer)
    _all: hashlib._Hash = field(default_factory=hashlib.sha256)
    _seats: dict[str, hashlib._Hash] = field(default_factory=dict)
    frames: int = 0

    def observe(self, request: Mapping[str, object]) -> None:
        text = _dump(_normalize_request(self._norm, request)).encode("ascii") + b"\n"
        seat = request.get("seat")
        label = str(seat) if type(seat) is int else "unknown"
        self._all.update(text)
        self._seats.setdefault(label, hashlib.sha256()).update(text)
        self.frames += 1

    def result(self) -> FrameDigestResult:
        by_seat = {
            seat: self._seats[seat].hexdigest()
            for seat in sorted(self._seats, key=lambda item: (len(item), item))
        }
        return FrameDigestResult(self._all.hexdigest(), by_seat, self.frames)


class _ObservingPolicy(ExternalPilotDecisionPolicy):
    """The production pilot policy; shows each request to ``digest`` first, then decides."""

    def __init__(self, base: ExternalPilotDecisionPolicy, digest: FrameDigest) -> None:
        super().__init__(
            tuple(base._pilots[seat] for seat in sorted(base._pilots)), base.scenario_seed
        )
        self._frame_digest = digest

    def decide(self, request: dict[str, object]) -> dict[str, object]:
        self._frame_digest.observe(request)
        return super().decide(request)


class FrameDigestRunner(XmageFullGameRunner):
    """The full-game runner with a frame digest per game; play is unchanged.

    ``digest_for(seed, decks)`` returns the digest of the last attempt at that game. A game is
    identified by its seed and deck ids, which is unique within one runner's batch.
    """

    def __init__(
        self,
        command: tuple[str, ...] | None = None,
        *,
        cwd: str | Path | None = None,
        request_timeout_seconds: float = 120.0,
        max_decisions: int = 50_000,
        private_card_repository: bool = False,
        shutdown_grace_seconds: float = 5.0,
    ) -> None:
        super().__init__(
            command,
            cwd=cwd,
            request_timeout_seconds=request_timeout_seconds,
            max_decisions=max_decisions,
            private_card_repository=private_card_repository,
            shutdown_grace_seconds=shutdown_grace_seconds,
        )
        self._digests: dict[tuple[int, tuple[str, ...]], FrameDigest] = {}

    @staticmethod
    def _game_key(seed: int, decks: Sequence[RulesDeckInput]) -> tuple[int, tuple[str, ...]]:
        return seed, tuple(deck.deck_id for deck in decks)

    def _validated_policy(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> ExternalPilotDecisionPolicy:
        base = super()._validated_policy(scenario, decks, pilots)
        digest = FrameDigest()
        self._digests[self._game_key(base.scenario_seed, decks)] = digest
        return _ObservingPolicy(base, digest)

    def digest_for(self, seed: int, decks: Sequence[RulesDeckInput]) -> FrameDigestResult | None:
        found = self._digests.get(self._game_key(seed, decks))
        return None if found is None else found.result()

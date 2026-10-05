"""Forge AF05: per-row hidden-information capability classification (#458).

The Forge provider is qualified against the same mandatory AF05 HIDDEN
denominator as XMage. This module classifies every HIDDEN row by what the
pinned Forge bridge can construct, execute and let a principal observe.

Two kinds of evidence go into each row:

* **Construction and execution gaps** come from the record itself, through the
  Forge scenario lane's own model (``forge_scenario_lane.model_requested_state``).
  No second translation of the record exists.
* **Observation channels** come from the pinned bridge source. Each channel
  is asserted by exact code fragments in a source blob at the bridge commit,
  matched on the code alone (comments stripped, whitespace collapsed). Absent
  tokens are checked after the asserted fragments are removed, and the
  bootstrap's JSON field reads must equal a closed set. A blob that loses a
  fragment, gains a token or reads a new field raises
  :class:`HiddenChannelDrift`, so no classification survives a source change
  without review.

Nothing here executes a row, writes a receipt or promotes credit. A row the
provider cannot construct is a ``PROVIDER_ADAPTER_GAP``, and its AF05 effect is
UNKNOWN: a missing capability is not a demonstrated leak (FAIL), and a
supporting native test never stands in for row execution (PASS). The Forge
Rules Core and bridge are read only; no Lab permission model is created.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import forge_scenario_lane as lane
from . import knowledge_projection
from .bridge_launcher import canonical_forge_authority

SCHEMA_VERSION = "commander-lab.forge-hidden-information/1.0.0"

PROVIDER_ADAPTER_GAP = "PROVIDER_ADAPTER_GAP"
LAB_ADAPTER_GAP = "LAB_ADAPTER_GAP"
AF05_EFFECT_UNKNOWN = "UNKNOWN"

CHANNEL_SUPPORTED = "SUPPORTED"
CHANNEL_ABSENT = "ABSENT"
# The channel exists and is principal-facing, but whether it honours a row's
# obligation is shown only by executing the row (a leak or sentinel scan of what
# it actually emits). A source assertion never stands in for that audit.
CHANNEL_UNAUDITED = "PRESENT_UNAUDITED"

# The bridge commit whose blobs this channel table was asserted against. A
# moved canonical pin invalidates every channel status until it is re-asserted.
ASSERTED_BRIDGE_COMMIT = "4ed8992de4bd7bd120c3920c0362533c7c65d822"

_BRIDGE_SOURCE = f"{lane.BRIDGE_MODULE}/src/main/java/forge/bridge"
SOURCES: dict[str, str] = {
    "bootstrap": f"{_BRIDGE_SOURCE}/ScenarioBootstrap.java",
    "engine": f"{_BRIDGE_SOURCE}/BridgeEngine.java",
    "projection": f"{_BRIDGE_SOURCE}/StateProjection.java",
    "controller": f"{_BRIDGE_SOURCE}/ExternalPlayerController.java",
    "main": f"{_BRIDGE_SOURCE}/BridgeMain.java",
}


class HiddenChannelDrift(RuntimeError):
    """The pinned bridge source no longer matches an asserted channel."""


@dataclass(frozen=True)
class Channel:
    """One principal-facing or construction capability of the pinned bridge."""

    name: str
    status: str
    source: str
    present: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    fields: frozenset[str] = frozenset()
    cases: frozenset[str] = frozenset()
    # Code between these two fragments (both required) is where ``keys`` and
    # ``prints`` are extracted; without a region the whole source is used.
    region: tuple[str, ...] = ()
    keys: frozenset[str] = frozenset()
    prints: frozenset[str] = frozenset()
    meaning: str = ""


# Every JSON field ScenarioBootstrap reads at the asserted commit. A construction
# channel is ABSENT only while this set is closed: any new field is drift.
BOOTSTRAP_FIELDS = frozenset(
    {
        "attached_to",
        "battlefield",
        "card",
        "commander_damage_taken",
        "continuous_effects_present",
        "controller",
        "counters",
        "decision_script",
        "hands",
        "id",
        "life",
        "owner",
        "players",
        "stack",
        "tapped",
    }
)
# Every message type the bridge dispatches at the asserted commit (its whole
# principal-facing request surface). A new or lost case label is drift.
MESSAGE_CASES = frozenset(
    {
        '"create_game"',
        '"get_event_log"',
        '"get_state"',
        '"shutdown"',
        "BridgeProtocol.ADD_PLAYER",
        "BridgeProtocol.CHOOSE_MODES",
        "BridgeProtocol.CONCEDE",
        "BridgeProtocol.CREATE_COMMANDER_GAME",
        "BridgeProtocol.EXPORT_EVENT_LOG",
        "BridgeProtocol.EXPORT_REPLAY",
        "BridgeProtocol.GET_CAPABILITIES",
        "BridgeProtocol.GET_CONSTRUCTED_STATE",
        "BridgeProtocol.GET_GAME_STATE",
        "BridgeProtocol.GET_LEGAL_ACTIONS",
        "BridgeProtocol.GET_PROVIDER_VERSION",
        "BridgeProtocol.IMPORT_DECK",
        "BridgeProtocol.ORDER_TRIGGERS",
        "BridgeProtocol.PASS_PRIORITY",
        "BridgeProtocol.RESOLVE_MULLIGAN",
        "BridgeProtocol.SELECT_TARGETS",
        "BridgeProtocol.SHUTDOWN_ENGINE",
        "BridgeProtocol.SHUTDOWN_GAME",
        "BridgeProtocol.START_ENGINE",
        "BridgeProtocol.START_GAME",
        "BridgeProtocol.SUBMIT_ACTION",
    }
)
# Every JSON key the projection writes into a decision frame summary, a legal
# action, its metadata and its object references at the asserted commit. A new
# or lost key is drift: each key is a pilot-facing field of the frame.
DECISION_FRAME_KEYS = frozenset(
    {
        "action_id",
        "action_type",
        "actor",
        "actor_id",
        "allowed_target_ids",
        "card_id",
        "choices_schema",
        "controller",
        "cost",
        "cost_order_indices",
        "decision_class",
        "decision_protocol_version",
        "decision_subtype",
        "divided_min_per_target",
        "divided_total",
        "divided_up_to",
        "event_offset",
        "frame_kind",
        "free_input",
        "hidden",
        "input_max",
        "input_min",
        "kind",
        "label",
        "legal_set_digest",
        "legal_set_size",
        "lifecycle",
        "max",
        "metadata",
        "min",
        "modes",
        "name",
        "object_refs",
        "options",
        "player_id",
        "principal_observation_digest",
        "public_state_digest",
        "reason",
        "revision",
        "rng_binding",
        "semantic_fingerprint",
        "semantic_key",
        "semantic_replay_version",
        "source_object_id",
        "status",
        "target_ids",
        "type",
        "zone",
    }
)
# Every JSON key get_constructed_state's keyed success path writes at the
# asserted commit (StateProjection.constructedState and zoneDigest). Each seat's
# library and hand leave only as library_and_hand_digest; the one name-valued
# key is a commander's public card_identity. A new or lost key is drift: a key
# that could carry a hidden card name is re-reviewed before it is certified.
CONSTRUCTED_STATE_KEYS = frozenset(
    {
        "active_player",
        "attachments",
        "battlefield_size",
        "card_identity",
        "commanders",
        "controller",
        "counters",
        "exile_size",
        "face_down",
        "graveyard_size",
        "hand_size",
        "left",
        "library_and_hand_digest",
        "library_shuffles",
        "library_size",
        "life",
        "lifecycle",
        "lost",
        "observation_scope",
        "owner",
        "phase",
        "player_id",
        "players",
        "poison",
        "prior_command_zone_cast_count",
        "priority_player",
        "schema",
        "seat",
        "stack_size",
        "tapped",
        "turn_number",
        "zone",
    }
)
# The honey-sentinel obligation's frame facets, each with the frame keys that
# carry it. Forge has no separate prompt or context field: the option label and
# the frame reason are the text a pilot reads. Every facet is PRESENT_UNAUDITED.
DECISION_FRAME_FACETS: dict[str, tuple[str, ...]] = {
    "prompt_and_context": ("label", "reason", "kind", "frame_kind"),
    "option_ids": ("action_id", "semantic_key", "semantic_fingerprint"),
    "labels": ("label",),
    "metadata": (
        "metadata",
        "revision",
        "decision_subtype",
        "cost_order_indices",
        "choices_schema",
        "object_refs",
    ),
    "object_references": ("card_id", "name", "zone", "controller", "player_id", "hidden"),
    "source": ("source_object_id",),
}
# Every stderr diagnostic BridgeMain itself writes at the asserted commit.
STDERR_PRINTS = frozenset(
    {
        '"[bridge] starting " + VersionInfo.BRIDGE_NAME + "/" + VersionInfo.BRIDGE_VERSION'
        ' + " protocol=" + BridgeProtocol.PROTOCOL_VERSION',
        '"[bridge] assets dir: " + HeadlessBridgeGui.resolveAssetsDir()',
        '"[bridge] engine initialization failed: " + e',
        '"[bridge] engine initialized in " + bootMillis + " ms"',
        '"[bridge] engine_commit=" + VersionInfo.engineCommit() + " source=" +'
        " VersionInfo.engineCommitSource()",
        '"[bridge] fatal io error: " + e',
        '"[bridge] exiting"',
        '"[bridge] dispatch failed: " + e',
    }
)
_WRITE_KEY = re.compile(r'(?:\.addProperty|\.add)\(\s*"([^"]+)"')
_STDERR_PRINT = re.compile(r"System\.err\.println\((.*?)\);")
_CASE_LABEL = re.compile(r'\bcase\s+("[^"]*"|[A-Za-z_][\w.]*)\s*:')
_FIELD_READ = re.compile(
    r'(?:\.has|\.get|\.getAsJsonObject|\.getAsJsonArray|\.getAsJsonPrimitive)\(\s*"([^"]+)"'
    r'|optString\(\s*\w+\s*,\s*"([^"]+)"'
)


# Each channel is decided by fragments that must be present, tokens that must
# not occur once those fragments are removed, and (for construction) the closed
# bootstrap field set. Fragments are code with whitespace collapsed.
CHANNELS: tuple[Channel, ...] = (
    Channel(
        "principal_scoped_state",
        CHANNEL_SUPPORTED,
        "projection",
        present=(
            "public static JsonObject gameState(BridgeSession session, String observerPlayerId)",
        ),
        meaning="get_game_state is projected for one observer principal",
    ),
    Channel(
        "face_down_redaction",
        CHANNEL_SUPPORTED,
        "projection",
        present=(
            "shown = view != null && view.canBeShownTo(observerView) "
            "&& view.canFaceDownBeShownTo(observerView);",
            'return faceDown ? "<face-down>" : "<hidden>";',
            "shown = observerView != null && view != null && view.canBeShownTo(observerView) "
            "&& view.canFaceDownBeShownTo(observerView);",
        ),
        meaning=(
            "a face-down card or stack source is named only to a principal both "
            "CardView.canBeShownTo and CardView.canFaceDownBeShownTo admit"
        ),
    ),
    Channel(
        "library_contents",
        CHANNEL_ABSENT,
        "projection",
        present=('zones.add("library", new JsonArray());', 'zones.add("library_size",'),
        absent=('zones.add("library', 'add("library'),
        meaning=(
            "every library projects as an empty list with library_size; no principal, "
            "entitled or not, can observe a library identity or its order"
        ),
    ),
    Channel(
        "event_log",
        CHANNEL_ABSENT,
        "engine",
        present=(
            "BridgeErrors.EVENT_LOG_UNSUPPORTED",
            'caps.addProperty("event_log_supported", false);',
        ),
        absent=('"event_log_supported"',),
        meaning=(
            "export_event_log and get_event_log fail closed; no engine event can be "
            "observed, so permission timing cannot be tied to the real event"
        ),
    ),
    Channel(
        "reveal_look_audience",
        CHANNEL_ABSENT,
        "controller",
        present=(
            "public void reveal(CardCollectionView cards, ZoneType zone, Player owner, "
            "String messagePrefix, boolean addMsgSuffix) { "
            "auditReveal(cards == null ? 0 : cards.size(), zone); }",
            "public void reveal(List<CardView> cards, ZoneType zone, PlayerView owner, "
            "String messagePrefix, boolean addMsgSuffix) { "
            "auditReveal(cards == null ? 0 : cards.size(), zone); }",
            "private void auditReveal(int count, ZoneType zone) { "
            "final Map<String, String> details = new LinkedHashMap<>(); "
            'details.put("actor", actorId()); '
            'details.put("count", Integer.toString(count)); '
            'details.put("zone", zone == null ? "?" : zone.name()); '
            'session.audit("cards_revealed", details); }',
        ),
        absent=("void reveal(", "auditReveal("),
        meaning=(
            "a reveal or look is recorded only in the bridge's internal audit, which is "
            "never pilot-visible; no principal has a revealed or looked-at log"
        ),
    ),
    Channel(
        "reveal_look_projection",
        CHANNEL_ABSENT,
        "projection",
        absent=('"revealed', '"looked', '"reveal', '"look_'),
        meaning=(
            "the state projection carries no revealed or looked-at zone; with the "
            "controller's audit-only reveal this is the whole reveal/look evidence"
        ),
    ),
    Channel(
        "replay_transcript",
        CHANNEL_ABSENT,
        "engine",
        present=(
            "export_replay is not supported: deterministic replay is not claimed",
            'caps.addProperty("replay_supported", false);',
        ),
        absent=('"replay_supported"',),
        meaning="no replay or transcript export exists to audit",
    ),
    Channel(
        "face_down_construction",
        CHANNEL_ABSENT,
        "bootstrap",
        absent=("face_down", "FaceDown", "faceDown", "manifest"),
        fields=BOOTSTRAP_FIELDS,
        meaning="the scenario bootstrap has no face-down field (MANIFESTED, CLOAKED, ...)",
    ),
    Channel(
        "library_construction",
        CHANNEL_ABSENT,
        "bootstrap",
        absent=('"library', '"libraries"'),
        fields=BOOTSTRAP_FIELDS,
        meaning="the scenario bootstrap cannot place a library in a requested order",
    ),
    Channel(
        "knowledge_construction",
        CHANNEL_ABSENT,
        "bootstrap",
        absent=("knowledge", "permission"),
        fields=BOOTSTRAP_FIELDS,
        meaning="the scenario bootstrap has no knowledge or permission field",
    ),
    Channel(
        "cost_state_construction",
        CHANNEL_ABSENT,
        "bootstrap",
        absent=('"action_cost_state"', '"cost', '"payment', '"mana_pool"'),
        fields=BOOTSTRAP_FIELDS,
        meaning="the scenario bootstrap has no mid-cast cost or payment state field",
    ),
    Channel(
        "message_surface",
        CHANNEL_UNAUDITED,
        "engine",
        present=(
            '"unknown message type: " + type',
            'case "get_state": return getGameState(request);',
        ),
        cases=MESSAGE_CASES,
        meaning=(
            "the bridge's whole request surface is this closed set of message types; an "
            "unknown type is refused with UNKNOWN_MESSAGE and the legacy get_state alias "
            "is the observer-scoped projection. Whether every message refuses an "
            "omniscient read, and what its errors and diagnostics carry, is shown only by "
            "the row's runtime refusal probes and channel scan, which were not run"
        ),
    ),
    Channel(
        "orchestration_constructed_state",
        CHANNEL_SUPPORTED,
        "engine",
        present=(
            "case BridgeProtocol.GET_CONSTRUCTED_STATE: return getConstructedState(request);",
            "if (!OrchestrationKey.enabled()) { final String problem = OrchestrationKey.problem(); "
            "return BridgeProtocol.error(request.requestId, "
            "BridgeErrors.ORCHESTRATION_CHANNEL_NOT_ENABLED,",
        ),
        meaning=(
            "get_constructed_state (forge#25, forge#28, the Lab's generic-lane construction proof, #441 "
            "(c)) is an orchestration channel, not a principal observation: every launch "
            "without COMMANDER_LAB_ORCHESTRATION_KEY refuses it with "
            "orchestration_channel_not_enabled. No principal-facing launch carries the key; "
            "the keyed success path is orchestration_constructed_state_payload"
        ),
    ),
    Channel(
        "orchestration_constructed_state_payload",
        CHANNEL_SUPPORTED,
        "projection",
        present=(
            'state.addProperty("observation_scope", "orchestration_keyed_digests");',
            'entry.addProperty("library_and_hand_digest", '
            'zoneDigest(seatId, "library_and_hand", libraryAndHand));',
            "return OrchestrationKey.digest(tokens);",
        ),
        region=(
            "public static JsonObject constructedState(BridgeSession session)",
            "public static JsonObject bridgeMeta(BridgeSession session, String observerPlayerId)",
        ),
        keys=CONSTRUCTED_STATE_KEYS,
        meaning=(
            "the keyed success path of get_constructed_state writes exactly the closed key set "
            "CONSTRUCTED_STATE_KEYS: public seat facts, sizes, shuffle counts and each "
            "commander's public identity, owner, zone, cast count and native controller, counters, face-down, tapped and attachment state (schema /3). Each seat's library and "
            "hand go only into zoneDigest, an HMAC under the launch key "
            "(OrchestrationKey.digest) over the name multiset, so no hidden card name leaves "
            "and nobody without the key can test a guess. A new key, or a lost digest "
            "construction, is drift"
        ),
    ),
    Channel(
        "decision_frames",
        CHANNEL_UNAUDITED,
        "projection",
        present=(
            'action.addProperty("source_object_id", option.sourceCardName);',
            'metadata.addProperty("label", option.label);',
            'action.getAsJsonObject("metadata").add("object_refs", refs);',
            'summary.addProperty("reason", frame.reason);',
        ),
        region=(
            "public static JsonObject decisionSummary(DecisionFrame frame)",
            "private static JsonObject playerState(",
        ),
        keys=DECISION_FRAME_KEYS,
        meaning=(
            "a decision frame reaches its actor as a summary and legal actions whose "
            "every key is the closed set DECISION_FRAME_KEYS: prompt and context (label, "
            "reason, kind), option ids (action_id, semantic_key, semantic_fingerprint), "
            "labels, metadata, object references and source (source_object_id, built "
            "from the source card name). Whether any of them carries a face-down or "
            "sentinel identity to a principal not entitled to it is shown only by the "
            "row's sentinel scan, which was not run"
        ),
    ),
    Channel(
        "transport_diagnostics",
        CHANNEL_UNAUDITED,
        "main",
        present=(
            "System.setOut(System.err);",
            "protocolOut.println(response);",
            'return BridgeProtocol.error("", BridgeErrors.MALFORMED_REQUEST, e.getMessage(), 0);',
            "return BridgeProtocol.error(request.requestId, BridgeErrors.INTERNAL_ERROR, "
            '"internal bridge error", 0);',
        ),
        absent=("protocolOut.print",),
        prints=STDERR_PRINTS,
        meaning=(
            "BridgeMain, the JSONL process the Lab launches, writes exactly one response "
            "per line to stdout; a malformed request echoes the parser's message and an "
            "internal failure returns a fixed text. Its own stderr diagnostics are the "
            "closed set STDERR_PRINTS (exception texts and stack traces included), and "
            "every engine System.out print is redirected to stderr. What the engine prints "
            "there is not bounded by bridge source, so whether stderr carries a hidden "
            "identity is shown only by the row's channel scan, which was not run; the Lab "
            "does not yet retain stderr for that scan (LAB_CAPTURE_GAPS)"
        ),
    ),
)
CHANNELS_BY_NAME: dict[str, Channel] = {channel.name: channel for channel in CHANNELS}

# Every row's verifier first scans everything the principal received
# (knowledge_projection._scan_principal: prompt, context, options, source and
# ability metadata, state, events, the transcript and the process log), so every
# row needs the whole principal-facing surface before its obligation-specific
# channels.
UNIVERSAL_PRINCIPAL_SURFACE: tuple[str, ...] = (
    "principal_scoped_state",
    "decision_frames",
    "message_surface",
    "transport_diagnostics",
    "event_log",
    "replay_transcript",
)

# The principal-facing channels each AF05 obligation needs, beyond construction
# and beyond UNIVERSAL_PRINCIPAL_SURFACE (required_channels joins the two).
# Kinds are knowledge_projection.ROWS's, so both providers share one row set.
OBSERVATION_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "opponent_hand": ("principal_scoped_state",),
    "opponent_library": ("principal_scoped_state",),
    "public_exile": ("principal_scoped_state",),
    "face_down_controller": ("principal_scoped_state", "face_down_redaction"),
    "no_omniscient_api": ("principal_scoped_state", "message_surface", "transport_diagnostics"),
    # Prompt, context, option ids, labels, metadata and source (decision frames),
    # errors and logs (message surface), state, transcript and the event log.
    "honey_sentinel": (
        "principal_scoped_state",
        "decision_frames",
        "message_surface",
        "transport_diagnostics",
        "event_log",
        "replay_transcript",
    ),
    "reveal_audience": (
        "principal_scoped_state",
        "reveal_look_audience",
        "reveal_look_projection",
        "event_log",
    ),
    "look_audience": (
        "principal_scoped_state",
        "reveal_look_audience",
        "reveal_look_projection",
        "event_log",
    ),
    "search_inspection": ("principal_scoped_state", "library_contents", "event_log"),
    "scry_knowledge": ("principal_scoped_state", "library_contents", "event_log"),
    "pile_metadata": ("principal_scoped_state", "decision_frames", "library_contents", "event_log"),
    "shuffle_invalidates_order": ("principal_scoped_state", "library_contents", "event_log"),
    "exile_permission_persists": ("principal_scoped_state", "face_down_redaction", "event_log"),
    "exile_permission_invalidates": ("principal_scoped_state", "face_down_redaction", "event_log"),
    "target_metadata": ("principal_scoped_state", "face_down_redaction", "decision_frames"),
    "source_metadata": ("principal_scoped_state", "face_down_redaction", "decision_frames"),
    "ability_metadata": ("principal_scoped_state", "face_down_redaction", "decision_frames"),
    "copy_face_down": ("principal_scoped_state", "face_down_redaction"),
    "transcript_privacy": ("principal_scoped_state", "replay_transcript", "event_log"),
    "controlled_player_authority": ("principal_scoped_state", "event_log"),
}

# Lane dimensions the provider itself cannot represent, by construction channel.
_PROVIDER_DIMENSIONS: dict[str, str] = {
    "semantic_objects.face_down": "face_down_construction",
    "temporal_checkpoint.exact_hand_after_draw": "library_construction",
    "knowledge_state": "knowledge_construction",
    # The lane's own finding: "mid-cast cost/payment state has no bootstrap field".
    "action_cost_state": "cost_state_construction",
}
# Lab-side lane dimensions: the provider offers the engine's own frames, but the
# Lab's Forge lane implements no selector execution for them.
_LAB_DIMENSION_PREFIXES = ("decision_execution.",)

# Principal-facing channels the provider emits but the Lab does not retain for a
# row's channel scan. Each claim is bound to the Lab's own launcher source by
# LAB_CAPTURE_ASSERTIONS, so a launcher that starts retaining the channel fails
# the assertion and the gap is re-reviewed instead of silently staying listed.
LAB_CAPTURE_GAPS: dict[str, str] = {
    "transport_diagnostics": (
        "bridge_launcher.launch pipes the bridge's stderr, but BridgeProcess.close "
        "discards it; only a 2000-character tail is read, and only when stdout closes "
        "during a request, so a row's sentinel scan cannot read normal diagnostics"
    ),
}
_LAB_LAUNCHER = Path(__file__).with_name("bridge_launcher.py")
LAB_CAPTURE_ASSERTIONS: dict[str, tuple[tuple[str, int], ...]] = {
    # (fragment, exact occurrence count) in the Lab launcher's code
    "transport_diagnostics": (
        ("stderr=subprocess.PIPE,", 1),
        ("self.popen.stderr.read()[-2000:]", 1),
        (".stderr.read", 1),
        ("for stream in (self.popen.stdout, self.popen.stderr):", 1),
    ),
}


def assert_lab_capture(launcher_text: str | None = None) -> None:
    """Each LAB_CAPTURE_GAPS claim must still describe the Lab launcher's code."""
    code = code_text(
        _LAB_LAUNCHER.read_text(encoding="utf-8") if launcher_text is None else launcher_text
    )
    for channel, fragments in LAB_CAPTURE_ASSERTIONS.items():
        wrong = [
            (fragment, count) for fragment, count in fragments if code.count(fragment) != count
        ]
        if wrong:
            raise HiddenChannelDrift(
                f"Lab capture gap {channel!r} no longer matches bridge_launcher.py: {wrong}"
            )


@dataclass
class HiddenRowClassification:
    fixture_id: str
    obligation_kind: str
    provider_gaps: list[dict[str, Any]] = field(default_factory=list)
    lab_gaps: list[dict[str, Any]] = field(default_factory=list)
    unobservable: list[dict[str, Any]] = field(default_factory=list)
    other_unsupported: list[dict[str, Any]] = field(default_factory=list)
    missing_channels: list[str] = field(default_factory=list)
    unaudited_channels: list[str] = field(default_factory=list)

    @property
    def classification(self) -> str:
        if self.other_unsupported:
            raise ValueError(
                f"{self.fixture_id}: unclassified lane dimensions "
                f"{[gap['dimension'] for gap in self.other_unsupported]}"
            )
        if self.provider_gaps or self.missing_channels:
            return PROVIDER_ADAPTER_GAP
        if self.lab_gaps:
            return LAB_ADAPTER_GAP
        raise ValueError(f"{self.fixture_id}: no gap found; a row without a gap needs execution")

    def reason(self) -> str:
        parts = [f"Forge AF05 {self.classification} ({self.obligation_kind})"]
        if self.provider_gaps:
            parts.append(
                "provider cannot construct: "
                + "; ".join(f"{gap['dimension']} ({gap['channel']})" for gap in self.provider_gaps)
            )
        if self.missing_channels:
            parts.append("principal channel absent: " + ", ".join(self.missing_channels))
        if self.unaudited_channels:
            parts.append(
                "principal channel present but unaudited (needs row execution): "
                + ", ".join(self.unaudited_channels)
            )
        if self.lab_gaps:
            parts.append(
                "Lab Forge lane has no execution for: "
                + ", ".join(gap["dimension"] for gap in self.lab_gaps)
            )
        if self.unobservable:
            parts.append(
                "readback cannot prove: " + ", ".join(gap["dimension"] for gap in self.unobservable)
            )
        parts.append(
            "no row execution, no receipt; AF05 effect UNKNOWN (a capability gap is not a "
            "demonstrated leak)"
        )
        return ". ".join(parts) + "."

    def to_document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "obligation_kind": self.obligation_kind,
            "classification": self.classification,
            "af05_effect": AF05_EFFECT_UNKNOWN,
            "provider_construction_gaps": self.provider_gaps,
            "missing_principal_channels": self.missing_channels,
            "unaudited_principal_channels": self.unaudited_channels,
            "lab_execution_gaps": self.lab_gaps,
            "unobservable_checkpoint_dimensions": self.unobservable,
            "other_unsupported_dimensions": self.other_unsupported,
            "reason": self.reason(),
        }


def required_channels(kind: str) -> tuple[str, ...]:
    """The universal principal surface, then the obligation's own channels."""
    return tuple(dict.fromkeys((*UNIVERSAL_PRINCIPAL_SURFACE, *OBSERVATION_REQUIREMENTS[kind])))


def classify_row(record: dict[str, Any]) -> HiddenRowClassification:
    """Classify one HIDDEN record by the Forge lane's model and the channel table."""
    fixture_id = str(record.get("fixture_id"))
    kind = knowledge_projection.ROWS.get(fixture_id)
    if kind is None:
        raise ValueError(f"{fixture_id} is not a mandatory AF05 HIDDEN row")
    model = lane.model_requested_state(record)
    row = HiddenRowClassification(fixture_id=fixture_id, obligation_kind=kind)
    for finding in model.hard_unsupported:
        document = finding.to_document()
        channel = _PROVIDER_DIMENSIONS.get(finding.dimension)
        if channel is not None:
            row.provider_gaps.append({**document, "channel": channel})
        elif finding.dimension.startswith(_LAB_DIMENSION_PREFIXES):
            row.lab_gaps.append(document)
        else:
            row.other_unsupported.append(document)
    if row.other_unsupported:
        raise ValueError(
            f"{fixture_id}: lane dimensions with no channel or Lab mapping: "
            f"{[gap['dimension'] for gap in row.other_unsupported]}"
        )
    row.unobservable = [finding.to_document() for finding in model.unobservable]
    required = required_channels(kind)
    row.missing_channels = [
        name for name in required if CHANNELS_BY_NAME[name].status == CHANNEL_ABSENT
    ]
    row.unaudited_channels = [
        name for name in required if CHANNELS_BY_NAME[name].status == CHANNEL_UNAUDITED
    ]
    for name in required:
        if name in LAB_CAPTURE_GAPS:
            row.lab_gaps.append(
                {"dimension": f"lab_capture.{name}", "detail": LAB_CAPTURE_GAPS[name]}
            )
    return row


def assert_bridge_pin(bridge_commit: str) -> None:
    """The channel table holds only for the bridge commit it was asserted against."""
    if bridge_commit != ASSERTED_BRIDGE_COMMIT:
        raise HiddenChannelDrift(
            f"channel table asserted against {ASSERTED_BRIDGE_COMMIT}, canonical Forge "
            f"bridge is {bridge_commit}: re-assert the channels before classifying"
        )


def row_reason(record: dict[str, Any]) -> str:
    """The exact runner reason for a Forge HIDDEN row, bound to the canonical pin."""
    assert_bridge_pin(canonical_forge_authority()["bridge_commit"])
    return classify_row(record).reason()


_COMMENT_OR_STRING = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.DOTALL
)


def code_text(source: str) -> str:
    """Java source with comments removed and whitespace collapsed (literals kept)."""

    def keep_literals(match: re.Match[str]) -> str:
        token = match.group(0)
        return " " if token.startswith("/") else token

    return " ".join(_COMMENT_OR_STRING.sub(keep_literals, source).split())


def bootstrap_fields(code: str) -> frozenset[str]:
    """Every JSON field name the bootstrap code reads."""
    return frozenset(a or b for a, b in _FIELD_READ.findall(code))


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        ).stdout
    except subprocess.CalledProcessError as error:
        raise HiddenChannelDrift(f"git {' '.join(args)} failed: {error.stderr.strip()}") from error


def _blob(root: Path, commit: str, relative: str) -> str:
    return _git(root, "show", f"{commit}:{relative}")


def channel_document(channel: Channel) -> dict[str, Any]:
    """The matrix entry of one asserted channel."""
    return {
        "channel": channel.name,
        "status": channel.status,
        "source": SOURCES[channel.source],
        "present_fragments": list(channel.present),
        "absent_tokens": list(channel.absent),
        "closed_bootstrap_fields": sorted(channel.fields),
        "closed_message_types": sorted(channel.cases),
        "closed_frame_keys": sorted(channel.keys),
        # The honey-sentinel facets describe decision frames only; another
        # closed key set (the keyed constructed-state payload) has none.
        "frame_key_facets": (
            {facet: list(keys) for facet, keys in DECISION_FRAME_FACETS.items()}
            if channel.keys == DECISION_FRAME_KEYS
            else {}
        ),
        "closed_stderr_prints": sorted(channel.prints),
        "meaning": channel.meaning,
    }


def assert_channels(texts: dict[str, str]) -> list[dict[str, Any]]:
    """Check every channel against its source code; drift raises."""
    asserted = []
    codes = {key: code_text(text) for key, text in texts.items()}
    for channel in CHANNELS:
        code = codes[channel.source]
        missing = [fragment for fragment in channel.present if fragment not in code]
        remainder = code
        for fragment in channel.present:
            remainder = remainder.replace(fragment, " ")
        found = [token for token in channel.absent if token in remainder]
        fields = bootstrap_fields(code) if channel.fields else frozenset()
        new_fields = sorted(fields - channel.fields)
        lost_fields = sorted(channel.fields - fields)
        cases = frozenset(_CASE_LABEL.findall(code)) if channel.cases else frozenset()
        new_cases = sorted(cases - channel.cases)
        lost_cases = sorted(channel.cases - cases)
        region = code
        if channel.region:
            start, end = channel.region
            if start not in code or end not in code or code.index(start) > code.index(end):
                raise HiddenChannelDrift(
                    f"channel {channel.name!r}: region {channel.region} not found in "
                    f"{SOURCES[channel.source]}"
                )
            region = code[code.index(start) : code.index(end)]
        keys = frozenset(_WRITE_KEY.findall(region)) if channel.keys else frozenset()
        prints = frozenset(_STDERR_PRINT.findall(region)) if channel.prints else frozenset()
        changed = {
            "new keys": sorted(keys - channel.keys),
            "lost keys": sorted(channel.keys - keys),
            "new stderr prints": sorted(prints - channel.prints),
            "lost stderr prints": sorted(channel.prints - prints),
        }
        if (
            missing
            or found
            or new_fields
            or lost_fields
            or new_cases
            or lost_cases
            or any(changed.values())
        ):
            raise HiddenChannelDrift(
                f"channel {channel.name!r} no longer matches {SOURCES[channel.source]}: "
                f"missing {missing}, unexpectedly present {found}, "
                f"new fields {new_fields}, lost fields {lost_fields}, "
                f"new messages {new_cases}, lost messages {lost_cases}, "
                + ", ".join(f"{label} {value}" for label, value in changed.items())
            )
        asserted.append(channel_document(channel))
    return asserted


def build_matrix(
    records: dict[str, dict[str, Any]], forge_root: Path, bridge_commit: str
) -> dict[str, Any]:
    """The full Forge AF05 matrix, bound to the pinned bridge source blobs."""
    assert_bridge_pin(bridge_commit)
    assert_lab_capture()
    texts = {key: _blob(forge_root, bridge_commit, path) for key, path in SOURCES.items()}
    blob_ids = {
        path: _git(forge_root, "rev-parse", f"{bridge_commit}:{path}").strip()
        for path in SOURCES.values()
    }
    channels = assert_channels(texts)
    hidden = sorted(fixture for fixture in records if fixture in knowledge_projection.ROWS)
    missing_rows = sorted(set(knowledge_projection.ROWS) - set(hidden))
    if missing_rows:
        raise ValueError(f"effective denominator lacks HIDDEN rows {missing_rows}")
    rows = [classify_row(records[fixture]).to_document() for fixture in hidden]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": "forge",
        "bridge_commit": bridge_commit,
        "sources": dict(SOURCES),
        "source_blobs": blob_ids,
        "channels": channels,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "classifications": counts,
            "pass": 0,
            "af05_forge": AF05_EFFECT_UNKNOWN,
        },
        "note": (
            "classification only: no row was executed and no receipt exists. A row "
            "becomes PASS only through a current source-bound execution receipt."
        ),
    }

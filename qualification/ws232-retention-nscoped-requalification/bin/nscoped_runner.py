#!/usr/bin/env python3
"""WS232 N-scoped runner (test-only orchestration, no production changes).

Drives ONE fresh-process XMage Commander game per invocation through the
exact production lane (`_RawFullGameClient` + `ExternalPilotDecisionPolicy`)
and records a PUBLIC-ONLY run log:

- per decision: offset, class, seat, option-type census, selected types,
  numeric bounds/choice, stack flag, turn/phase, life vector, zone
  name-multisets (battlefield/graveyard/command are board-public),
  hand/library/exile COUNTS only, rng calls.
- NEVER persisted: hands, libraries, labels, prompts, metadata contents,
  UUIDs, option IDs. Experiment-public card names (the focus card or the
  published Lions list) may appear as match booleans/counts only.

Spotlight pilot (focus seat only, own-principal options only): re-ranks the
engine-offered actions to prefer the focus card. This is ordinary pilot
discretion among authorized alternatives (what a themed-deck pilot does);
legality stays entirely in the engine; outcomes are never injected.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from commander_lab.agents import GenericCommanderPilot  # noqa: E402
from commander_lab.agents.pilots import PilotDecision, PilotStateView  # noqa: E402
from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    ExternalPilotDecisionPolicy,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
    _RawFullGameClient,
    _RuntimePilot,
    build_pilot,
)
from commander_lab.models import (  # noqa: E402
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    RulesDeckInput,
)
from commander_lab.semantic_replay.tape_helpers import deck_content_digest  # noqa: E402

XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
BRIDGE_VERSION = "xmage-engine-bridge-0.1.0-SNAPSHOT"
CMD = ("java", "-jar", "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar", "full-game")
POLICY_VERSION = "xmage-full-game-policy-1.0.0"


class SpotlightPilot(GenericCommanderPilot):
    """Prefer engine-offered actions naming the focus card (own seat only).

    Only re-ranks OFFERED PilotActionViews; never fabricates, never selects
    unoffered actions (the policy layer re-validates offered membership and
    fails closed otherwise). All other decisions delegate to the generic pilot.
    """

    pilot_name = "WS232SpotlightPilot"

    def __init__(self, config, focus_names: tuple[str, ...],
                 focus_is_commander: bool = False,
                 focus_halves: tuple[str, ...] = ()):
        super().__init__(config)
        self._focus = tuple(n.casefold() for n in focus_names)
        import re as _re
        self._half_pats = tuple(
            _re.compile(r"\b" + _re.escape(h.casefold()) + r"\b") for h in focus_halves)
        # When the focus IS the commander it never appears in hands; skip
        # hand-shaping (mulligan/bottom) and only prefer its casts.
        self._focus_is_commander = focus_is_commander

    def _is_focus_view(self, card_name: str | None) -> bool:
        if not card_name:
            return False
        low = card_name.casefold()
        if any(f in low for f in self._focus):
            return True
        return any(p.search(low) for p in self._half_pats)

    def should_keep_opening_hand(self, cards, *, mulligans, free_first,
                                 commander_names, rng):
        # Themed-table mulligan: keep the focus card (with at least one land
        # so the keep can develop); otherwise look for it while the cap
        # allows. The engine cap (forced keep at 3) still binds.
        # Commander-focus: the focus is never in hand; delegate entirely.
        if self._focus_is_commander:
            return super().should_keep_opening_hand(
                cards, mulligans=mulligans, free_first=free_first,
                commander_names=commander_names, rng=rng)
        if mulligans < 3 and self._focus:
            names = [getattr(c, "card_name", "") or "" for c in cards]
            has_focus = any(self._is_focus_view(n) for n in names)
            lands = sum(1 for c in cards if (c.metadata or {}).get("is_land"))
            # Keep focus hands that can develop (2+ lands); mulligan slow
            # focus hands and focus-less hands while the cap allows.
            if has_focus and lands >= 2:
                return True, 9.9
            if not has_focus or lands < 2:
                return False, 0.0
        return super().should_keep_opening_hand(
            cards, mulligans=mulligans, free_first=free_first,
            commander_names=commander_names, rng=rng)

    def choose_bottom_cards(self, cards, count, *, commander_names):
        # Never bottom the focus card while any other bottom candidate exists.
        # Commander-focus: delegate entirely (focus never in hand).
        if self._focus_is_commander:
            return super().choose_bottom_cards(
                cards, count, commander_names=commander_names)
        if count > 0 and self._focus:
            ordered = sorted(
                list(cards),
                key=lambda c: (
                    self._is_focus_view(getattr(c, "card_name", "") or ""),
                    self.opening_card_value(c, commander_names),
                    -getattr(c, "mana_cost", 0.0),
                    getattr(c, "action_id", ""),
                ),
            )
            return tuple(c.action_id for c in ordered[:count])
        return super().choose_bottom_cards(
            cards, count, commander_names=commander_names)

    _BASICS = ("plains", "island", "swamp", "mountain", "forest", "wastes")

    def _is_land_play(self, view) -> bool:
        # PilotActionView.card_name is the bare source name ('Mountain');
        # the ' — Play ...' suffix lives only in the wire label.
        return (view.card_name or "").strip().casefold() in self._BASICS

    def _is_mana_tap(self, view) -> bool:
        meta = view.metadata or {}
        return meta.get("xmage_option_type") == "mana_ability"

    # Resolution-bounded X discipline (WS232 U5): paid-X choices (announce
    # for X-spells, divide companions) must remain payable in test mana
    # bases or the engine correctly refuses activation and the effect never
    # resolves. Capping lawful choices at a small affordable constant is
    # ordinary pilot discretion (the mirror of the deterministic benefit
    # extreme): the VALUE is pilot input, the divide/damage/draw mechanics
    # and their resolution are engine output. Cap 4 exercises multi-point
    # divides and X>=1 resolutions while staying payable. Unpaid numeric
    # paths (pure amount choices like Damnations) are unaffected in
    # practice (any in-domain value resolves). Always in-domain, never
    # clamped outside [min, max].
    RESOLUTION_X_CAP = 4

    def choose_number(self, state, domain, rng):
        try:
            lo = int(domain.get("min"))
            hi = int(domain.get("max"))
        except (TypeError, ValueError):
            return super().choose_number(state, domain, rng)
        if hi - lo > self.RESOLUTION_X_CAP:
            return max(lo, min(hi, lo + self.RESOLUTION_X_CAP))
        return super().choose_number(state, domain, rng)

    def choose_numbers(self, state, domain, rng):
        try:
            legs = list(domain.get("legs") or [])
        except TypeError:
            return super().choose_numbers(state, domain, rng)
        if not legs:
            return super().choose_numbers(state, domain, rng)
        out = []
        for leg in legs:
            try:
                lo = int(leg.get("min"))
                hi = int(leg.get("max"))
            except (TypeError, ValueError):
                return super().choose_numbers(state, domain, rng)
            out.append(max(lo, min(hi, lo + self.RESOLUTION_X_CAP)))
        return out

    def choose_action(self, state: PilotStateView, actions, rng) -> PilotDecision:
        offered = list(actions)

        def is_cancel(v) -> bool:
            return v.action_kind == "pass" and "cancel" in (v.card_name or "").casefold()

        def is_priority_pass(v) -> bool:
            return v.action_kind == "pass" and (v.card_name or "") == "Pass priority"

        # Mana lane (real payment): pool/ability/cancel views — full
        # discretion to the generic pilot; never hide a productive tap or
        # the cancel, or lawful casts fizzle.
        if any(is_cancel(v) for v in offered):
            return super().choose_action(state, offered, rng)
        # Non-priority lanes (targets/attacks/blocks/modes): never interfere.
        if not any(is_priority_pass(v) for v in offered):
            return super().choose_action(state, offered, rng)
        # Priority lane only from here.
        candidates = [a for a in offered if not self._is_mana_tap(a)]
        # The lane auto-pays cast costs through mana_payment decisions;
        # idle manual taps only drain at phase end, so they are not taken
        # at priority (the generic pilot's tap-happiness starves 2-mana
        # casts of untapped sources).
        focused = [
            a for a in candidates
            if a.action_kind == "card"
            and any(f in (a.card_name or "").casefold() for f in self._focus)
        ]
        pool = focused
        if not pool:
            # Mana development is basic pilot competence: play lands while
            # no focus action is offered (still only ever offered options).
            lands = [a for a in candidates
                     if a.action_kind == "card" and self._is_land_play(a)]
            pool = lands
        if pool:
            scored = [(a, self.evaluate_action(state, a)) for a in pool]
            scored.sort(key=lambda item: (item[1].total_utility, item[0].action_id), reverse=True)
            best, breakdown = scored[0]
            return PilotDecision(
                pilot_name=self.pilot_name,
                strength=self.config.strength,
                mode=self.config.mode,
                selected_action_id=best.action_id,
                selected_utility=breakdown.total_utility,
                candidates=tuple((a.action_id, b.total_utility) for a, b in scored),
                selected_breakdown=breakdown,
            )
        # Priority lane with no focus/land offer: pass without idle taps so
        # untapped sources accumulate for real casts (taps excluded).
        return super().choose_action(state, candidates, rng)


def make_binding(seat: int, deck: RulesDeckInput,
                 mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC) -> FullGamePilotBinding:
    cfg = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                      mode=mode)
    return FullGamePilotBinding(
        seat=seat, deck_id=deck.deck_id, strategy="generic",
        commander_names=tuple(deck.commander_names), config=cfg,
        pilot_identity="GenericCommanderPilot", pilot_version="1.0.0",
        decision_policy_version=POLICY_VERSION)


def make_deck(deck_id: str, commander: str, mainboard: tuple[str, ...]) -> RulesDeckInput:
    digest = deck_content_digest(deck_id=deck_id, commander_names=(commander,), mainboard=mainboard)
    return RulesDeckInput(deck_id=deck_id, name=deck_id, commander_names=(commander,),
                          mainboard=mainboard, deck_hash=digest)


def make_scenario(scenario_id: str, player_count: int, seed: int, decks) -> FutureXmageScenario:
    assert decks[0].deck_hash is not None
    return FutureXmageScenario(
        candidate_id=decks[0].deck_id, deck_hash=decks[0].deck_hash,
        opponent_deck_ids=tuple(d.deck_id for d in decks[1:]),
        player_count=player_count, seat=1, scenario_id=scenario_id, seed=seed,
        xmage_commit=XMAGE_COMMIT, bridge_version=BRIDGE_VERSION,
        pilot_identity="GenericCommanderPilot", pilot_version="1.0.0",
        decision_policy_version=POLICY_VERSION)


def _zone_names(items) -> dict:
    if not isinstance(items, list):
        return {}
    return dict(sorted(Counter(
        str(it.get("name", "?")) for it in items if isinstance(it, dict)
    ).items()))


def _battlefield_details(items) -> dict:
    # Board-public physical characteristics (power/toughness/tapped/counters)
    # for continuous-effect/layers evidence. Absent fields stay absent.
    if not isinstance(items, list):
        return {}
    out = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        nm = str(it.get("name", "?"))
        out.setdefault(nm, []).append(
            {"power": it.get("power"), "toughness": it.get("toughness"),
             "tapped": it.get("tapped", "absent"),
             "counters": it.get("counters", "absent")})
    return out


def _public_snapshot(pilot_state: dict) -> dict:
    """Board-public projection of one actor-scoped state. No hands, no libraries,
    no UUIDs, no labels. Battlefield/graveyard/command names are public zones."""
    players = []
    for raw in (pilot_state.get("players") or []):
        if not isinstance(raw, dict):
            continue
        players.append({
            "seat": raw.get("seat"),
            "life": raw.get("life"),
            "hand_count": raw.get("hand_count"),
            "library_count": raw.get("library_count"),
            "graveyard_count": raw.get("graveyard_count"),
            "exile_count": raw.get("exile_count"),
            "has_lost": bool(raw.get("has_lost")),
            "has_won": bool(raw.get("has_won")),
            "battlefield": _zone_names(raw.get("battlefield")),
            "battlefield_detail": _battlefield_details(raw.get("battlefield")),
            "graveyard": _zone_names(raw.get("graveyard")),
            "command": _zone_names(raw.get("command")),
        })
    return {
        "turn": pilot_state.get("turn_number"),
        "phase": pilot_state.get("phase"),
        "step": pilot_state.get("step"),
        "players": players,
    }


@dataclass
class DecisionLog:
    offset: int
    decision_class: str
    seat: int
    n_options: int
    option_types: dict
    selected_types: list
    numeric_min: object = None
    numeric_max: object = None
    numeric_choice: object = None
    numeric_choices: object = None
    joint_legs: object = None
    joint_total: object = None
    stack_nonempty: bool = False
    turn: object = None
    life: list = field(default_factory=list)
    # runtime-only match signals, persisted as booleans/counts for
    # experiment-public names only:
    focus_offered: bool = False
    focus_selected: bool = False
    snapshot: dict = field(default_factory=dict)


def drive_game(scenario, decks, pilots, *, focus_names=(), focus_seats=None,
               focus_halves=(), focus_is_commander=False, max_decisions=150,
               request_timeout=120.0) -> dict:
    """Drive one fresh-process game. Returns the public run record.

    focus_seats defaults to ALL seats (symmetric themed table) when
    focus_names is set; pass an explicit subset to spotlight fewer seats.
    """
    runner = XmageFullGameRunner(command=CMD, cwd=str(REPO_ROOT),
                                 request_timeout_seconds=request_timeout,
                                 max_decisions=max_decisions + 10)
    runner._validate_inputs(scenario, decks, pilots)
    runtimes = []
    if focus_names and focus_seats is None:
        focus_seats = {b.seat for b in pilots}
    else:
        focus_seats = set(focus_seats or ())
    for binding in sorted(pilots, key=lambda b: b.seat):
        pilot = build_pilot(binding.config, strategy=binding.strategy)
        if binding.seat in focus_seats and focus_names:
            pilot = SpotlightPilot(binding.config, tuple(focus_names),
                                   focus_is_commander=focus_is_commander,
                                   focus_halves=tuple(focus_halves))
        runtimes.append(_RuntimePilot(binding=binding, pilot=pilot))
    policy = ExternalPilotDecisionPolicy(tuple(runtimes), scenario.seed)

    focus_cf = tuple(n.casefold() for n in focus_names)
    focus_whole = tuple(n.casefold() for n in focus_halves)
    import re as _re
    whole_pats = tuple(_re.compile(r"\b" + _re.escape(h) + r"\b") for h in focus_whole)

    def _matches(blob_cf: str) -> bool:
        if focus_cf and any(f in blob_cf for f in focus_cf):
            return True
        return any(p.search(blob_cf) for p in whole_pats)
    t0 = time.monotonic()
    logs: list[DecisionLog] = []
    provider: dict = {}
    terminal = False
    failure: str | None = None
    bounded_stop = False
    final_outcomes: list = []
    final_turn = None
    rules_calls_last = None
    rules_calls_first = None

    def text_in_option(opt: dict) -> str:
        parts = [str(opt.get("label") or "")]
        meta = opt.get("metadata")
        if isinstance(meta, dict):
            for key in ("source_name", "card_name", "name"):
                if meta.get(key):
                    parts.append(str(meta[key]))
        return "\n".join(parts)

    try:
        with _RawFullGameClient(CMD, cwd=str(REPO_ROOT),
                                request_timeout_seconds=request_timeout) as client:
            provider = runner._open_game(client, scenario, decks)
            status = client.request("start_full_game")
            count = 0
            while True:
                fail = status.get("failure")
                if isinstance(fail, dict):
                    failure = json.dumps(fail, sort_keys=True)[:500]
                    break
                decision = status.get("decision")
                if isinstance(decision, dict):
                    count += 1
                    if count > max_decisions:
                        bounded_stop = True
                        break  # bounded stop, not terminal; caller records budget status
                    dclass = str(decision.get("decision_class", "?"))
                    pstate = decision.get("pilot_state") or {}
                    seat = int(pstate.get("seat", -1)) + 1
                    options = decision.get("legal_options") or []
                    type_census = dict(sorted(Counter(
                        str(o.get("option_type", "?")) for o in options
                        if isinstance(o, dict)).items()))
                    ctx = decision.get("context") or {}
                    snap = _public_snapshot(pstate)
                    life = [p.get("life") for p in snap["players"]]
                    offered = False
                    if focus_cf and dclass == "priority":
                        for o in options:
                            if not isinstance(o, dict):
                                continue
                            # Any priority offer naming the focus except
                            # passes and mana taps: cast offers arrive as
                            # activated_ability/cast/play/cast_ability/choice
                            # depending on the card/zone path; the engine's
                            # act of offering IS the legality proof.
                            if str(o.get("option_type")) in (
                                    "pass_priority", "mana_ability"):
                                continue
                            blob = text_in_option(o).casefold()
                            if _matches(blob):
                                offered = True
                                break
                    response = policy.decide(decision)
                    sel_ids = set(response.get("selected_option_ids") or [])
                    sel_types = []
                    selected_focus = False
                    for o in options:
                        if isinstance(o, dict) and str(o.get("option_id")) in sel_ids:
                            sel_types.append(str(o.get("option_type", "?")))
                            if _matches(text_in_option(o).casefold()):
                                selected_focus = True
                    stack_flag = False
                    try:
                        actor = policy._actor(pstate)
                        stack_flag = bool(actor.get("stack"))
                    except Exception:
                        stack_flag = False
                    # Joint legs persist as min/max only: leg prompts embed
                    # per-process UUIDs and card text (never persisted).
                    raw_legs = ctx.get("numeric_legs")
                    clean_legs = None
                    if isinstance(raw_legs, list):
                        clean_legs = [
                            {"min": leg.get("min"), "max": leg.get("max")}
                            for leg in raw_legs if isinstance(leg, dict)]
                    logs.append(DecisionLog(
                        offset=count, decision_class=dclass, seat=seat,
                        n_options=len(options), option_types=type_census,
                        selected_types=sel_types,
                        numeric_min=ctx.get("numeric_min"), numeric_max=ctx.get("numeric_max"),
                        numeric_choice=(response.get("numeric_choice")
                                        if "numeric_choice" in response else None),
                        numeric_choices=(list(response.get("numeric_choices"))
                                         if isinstance(response.get("numeric_choices"), list)
                                         else None),
                        joint_legs=clean_legs,
                        joint_total=(ctx.get("numeric_total_min"),
                                     ctx.get("numeric_total_max")),
                        stack_nonempty=stack_flag, turn=snap["turn"], life=life,
                        focus_offered=offered, focus_selected=selected_focus,
                        snapshot=snap))
                    status = client.request("submit_full_game_decision", {"response": response})
                    outcomes = status.get("outcomes")
                    if isinstance(outcomes, list):
                        final_outcomes = [
                            {"seat": o.get("seat"), "life": o.get("life"),
                             "won": bool(o.get("won")), "lost": bool(o.get("lost")),
                             "left": bool(o.get("left"))} for o in outcomes
                            if isinstance(o, dict)]
                    if status.get("turn_number") is not None:
                        final_turn = status.get("turn_number")
                    rsb = status.get("rules_seed_binding")
                    if isinstance(rsb, dict) and rsb.get("rules_random_calls") is not None:
                        rules_calls_last = rsb.get("rules_random_calls")
                        if rules_calls_first is None:
                            rules_calls_first = rsb.get("rules_random_calls")
                    continue
                if bool(status.get("terminal")):
                    terminal = True
                    outcomes = status.get("outcomes")
                    if isinstance(outcomes, list):
                        final_outcomes = [
                            {"seat": o.get("seat"), "life": o.get("life"),
                             "won": bool(o.get("won")), "lost": bool(o.get("lost")),
                             "left": bool(o.get("left"))} for o in outcomes
                            if isinstance(o, dict)]
                    break
                status = client.request("get_full_game_decision")
    except (FullGameConformanceError, FullGameProtocolError) as exc:
        failure = f"{type(exc).__name__}: {exc}"[:800]

    elapsed = round(time.monotonic() - t0, 1)
    classes = dict(sorted(Counter(entry.decision_class for entry in logs).items()))
    return {
        "engine_version": str(provider.get("engine_version", "unknown")),
        "engine_commit": str(provider.get("engine_commit", XMAGE_COMMIT)),
        "protocol_version": str(provider.get("protocol_version", "unknown")),
        "player_count": scenario.player_count,
        "seed": scenario.seed,
        "scenario_id": scenario.scenario_id,
        "deck_ids": [d.deck_id for d in decks],
        "deck_digests": [d.deck_hash for d in decks],
        "focus_names": list(focus_names),
        "elapsed_seconds": elapsed,
        "decisions": len(logs),
        "terminal": terminal,
        "failure": failure,
        "budget_exhausted": bounded_stop,
        "observed_classes": classes,
        "final_outcomes": final_outcomes,
        "final_turn": final_turn,
        "rules_random_calls_first": rules_calls_first,
        "rules_random_calls_last": rules_calls_last,
        "log": [entry.__dict__ for entry in logs],
    }


def summarize_zones(run: dict) -> dict:
    """Board-public zone arrivals/departures per seat across the run."""
    out: dict[str, dict] = {}
    prev = None
    for entry in run["log"]:
        snap = entry["snapshot"]
        if prev is not None:
            for p, q in zip(prev["players"], snap["players"], strict=True):
                seat = str(q.get("seat"))
                for zone in ("battlefield", "graveyard", "command"):
                    before = Counter(p.get(zone) or {})
                    after = Counter(q.get(zone) or {})
                    for name in set(before) | set(after):
                        d = after.get(name, 0) - before.get(name, 0)
                        if d:
                            out.setdefault(seat, {}).setdefault(zone, {}).setdefault(
                                name, {"arrived": 0, "departed": 0})
                            if d > 0:
                                out[seat][zone][name]["arrived"] += d
                            else:
                                out[seat][zone][name]["departed"] += -d
        prev = snap
    return out

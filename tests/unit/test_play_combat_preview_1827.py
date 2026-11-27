"""PLAY (#1827): Oracle's-Eye combat outcome preview and honest uncertainty checks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "src" / "commander_lab" / "studio" / "static"


def _node_json(script: str) -> object:
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=STATIC_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_combat_preview_deterministic_unblocked_and_single_blocker_math() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        const frame = {
          turn: 4,
          phase: 'combat',
          step: 'declare_blockers',
          active_seat: 0,
          seat: 1,
          players: [
            {
              seat: 0,
              player_id: 'p0',
              life: 30,
              hand_count: 0,
              battlefield: [
                { object_id: 'atk-big', name: 'Ghalta', power: 6, toughness: 6, tapped: true, oracle_text: 'Trample' },
                { object_id: 'atk-fs', name: 'Knight', power: 3, toughness: 2, tapped: true, oracle_text: 'First strike' },
                { object_id: 'atk-ll', name: 'Vampire', power: 3, toughness: 3, tapped: true, oracle_text: 'Lifelink' },
                { object_id: 'atk-ds', name: 'Fencing Ace', power: 2, toughness: 2, tapped: true, oracle_text: 'Double strike, trample' }
              ]
            },
            {
              seat: 1,
              player_id: 'p1',
              life: 10,
              hand_count: 0,
              battlefield: [
                { object_id: 'blk-1', name: 'Grizzly Bears', power: 2, toughness: 2, tapped: false },
                { object_id: 'blk-2', name: 'Hill Giant', power: 3, toughness: 3, tapped: false },
                { object_id: 'blk-3', name: 'Elvish Mystic', power: 1, toughness: 1, tapped: false },
                { object_id: 'blk-4', name: 'Runeclaw Bear', power: 2, toughness: 2, tapped: false }
              ]
            }
          ],
          combat: {
            attacks: [
              { attacker_id: 'atk-big', attacker: 'Ghalta', target: 'Sitz 2' },
              { attacker_id: 'atk-fs', attacker: 'Knight', target: 'Sitz 2' },
              { attacker_id: 'atk-ll', attacker: 'Vampire', target: 'Sitz 2' },
              { attacker_id: 'atk-ds', attacker: 'Fencing Ace', target: 'Sitz 2' }
            ],
            blocks: [
              { attacker_id: 'atk-big', attacker: 'Ghalta', blocker_id: 'blk-1', blocker: 'Grizzly Bears' },
              { attacker_id: 'atk-fs', attacker: 'Knight', blocker_id: 'blk-2', blocker: 'Hill Giant' },
              { attacker_id: 'atk-ll', attacker: 'Vampire', blocker_id: 'blk-3', blocker: 'Elvish Mystic' },
              { attacker_id: 'atk-ds', attacker: 'Fencing Ace', blocker_id: 'blk-4', blocker: 'Runeclaw Bear' }
            ]
          }
        };
        const pv = CP.evaluateCombatPreview(frame, null, { seatName: (s) => `Sitz ${s + 1}` });
        console.log(JSON.stringify(pv));
        """
    )
    assert out["visible"] is True
    assert out["certainty"] == "certain"
    assert out["uncertaintyReasons"] == []
    # Trample 6 vs 2/2 => 4 trample; DS+Trample 2/2 vs 2/2 => kills in FS, 2 DS trample => total 6 to Seat 2!
    assert out["seatEffects"]["1"]["incomingDamage"] == 6
    assert out["seatEffects"]["1"]["newLife"] == 4
    # Vampire 3/3 lifelink dealt 3 damage => Seat 0 gains +3 life (30 -> 33)
    assert out["seatEffects"]["0"]["lifelinkGain"] == 3
    assert out["seatEffects"]["0"]["newLife"] == 33
    # First striker 3/2 kills Hill Giant 3/3 before taking damage
    assert out["creatureOutcomes"]["atk-fs"]["outcome"] == "survives"
    assert out["creatureOutcomes"]["blk-2"]["outcome"] == "dies"
    assert out["creatureOutcomes"]["blk-1"]["outcome"] == "dies"
    assert out["creatureOutcomes"]["blk-4"]["outcome"] == "dies"
    assert out["creatureOutcomes"]["atk-ds"]["outcome"] == "survives"


def test_combat_preview_deathtouch_indestructible_and_trade() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        const dtVsInd = CP.simulateOneVsOne(
          { name: 'Questing', power: 5, toughness: 5, oracle_text: 'Deathtouch, trample' },
          { name: 'Darksteel', power: 5, toughness: 5, oracle_text: 'Indestructible' }
        );
        const trade = CP.simulateOneVsOne(
          { name: 'Bear A', power: 3, toughness: 3 },
          { name: 'Bear B', power: 3, toughness: 3 }
        );
        const preHurt = CP.simulateOneVsOne(
          { name: 'Piker', power: 2, toughness: 1 },
          { name: 'Wall', power: 0, toughness: 4, damage: 2 }
        );
        console.log(JSON.stringify({ dtVsInd, trade, preHurt }));
        """
    )
    # Deathtouch assigns 1 lethal even to indestructible; 4 tramples over; both survive (5 dmg != indestructible death, 5 == 5 kills attacker!)
    assert out["dtVsInd"]["trampleDamage"] == 4
    assert out["dtVsInd"]["blockerDies"] is False
    assert out["dtVsInd"]["attackerDies"] is True
    assert out["trade"]["attackerDies"] is True
    assert out["trade"]["blockerDies"] is True
    assert out["preHurt"]["blockerDies"] is True


def test_combat_preview_live_precommit_blocker_toggle_and_drag_hover() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        const frame = {
          turn: 3,
          phase: 'combat',
          step: 'declare_blockers',
          active_seat: 1,
          seat: 0,
          players: [
            {
              seat: 0,
              player_id: 'p0',
              life: 6,
              hand_count: 0,
              battlefield: [
                { object_id: 'my-blk', name: 'Wall of Omens', power: 2, toughness: 4, tapped: false }
              ]
            },
            {
              seat: 1,
              player_id: 'p1',
              life: 20,
              hand_count: 0,
              battlefield: [
                { object_id: 'opp-atk', name: 'Beast Token', power: 6, toughness: 2, tapped: true }
              ]
            }
          ],
          combat: {
            attacks: [{ attacker_id: 'opp-atk', attacker: 'Beast Token', target: 'Sitz 1' }],
            blocks: []
          }
        };
        const pendingBlk = {
          decision_id: 'blk-live',
          decision_class: 'declare_blocker',
          seat: 0,
          metadata: { blocker_id: 'my-blk' },
          legal_options: [{ option_id: 'opp-atk', option_type: 'declare_blocker', metadata: { attacker_id: 'opp-atk', blocker_id: 'my-blk' }, label: 'Block Beast Token' }]
        };
        const unblocked = CP.evaluateCombatPreview(frame, pendingBlk, { selectedOptions: [] });
        const staged = CP.evaluateCombatPreview(frame, pendingBlk, { selectedOptions: ['opp-atk'] });
        const hovered = CP.evaluateCombatPreview(frame, pendingBlk, {
          selectedOptions: [],
          drag: { kind: 'blocker', objectId: 'my-blk', name: 'Wall of Omens' },
          hoveredTarget: { type: 'object', id: 'opp-atk' }
        });
        console.log(JSON.stringify({ unblocked, staged, hovered }));
        """
    )
    assert out["unblocked"]["seatEffects"]["0"]["newLife"] == 0
    assert out["unblocked"]["seatEffects"]["0"]["lethal"] is True
    assert out["staged"]["seatEffects"].get("0", {}).get("incomingDamage", 0) == 0
    assert out["staged"]["creatureOutcomes"]["opp-atk"]["outcome"] == "dies"
    assert out["staged"]["creatureOutcomes"]["my-blk"]["outcome"] == "dies"
    assert out["hovered"]["creatureOutcomes"]["opp-atk"]["outcome"] == "dies"


def test_combat_preview_honest_uncertainty_for_tricks_multiblock_complex_and_facedown() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        const trickFrame = {
          turn: 5,
          phase: 'combat',
          step: 'declare_attackers',
          active_seat: 0,
          seat: 0,
          players: [
            { seat: 0, player_id: 'p0', life: 40, hand_count: 2, battlefield: [{ object_id: 'a1', name: 'Bear', power: 2, toughness: 2, tapped: false }] },
            { seat: 1, player_id: 'p1', life: 20, hand_count: 3, battlefield: [{ object_id: 'l1', name: 'Forest', tapped: false, types: ['Land'] }] }
          ]
        };
        const pendingAtk = {
          decision_id: 'atk-1',
          decision_class: 'declare_attacker',
          seat: 0,
          legal_options: [{ option_id: 'opt-1', option_type: 'declare_attacker', metadata: { object_id: 'a1', defender_id: 'p1' }, label: 'Attack Seat 2' }]
        };
        const withTrickRisk = CP.evaluateCombatPreview(trickFrame, pendingAtk, { selectedOptions: ['opt-1'] });

        const multiAndComplexFrame = {
          turn: 6,
          phase: 'combat',
          step: 'declare_blockers',
          active_seat: 0,
          seat: 1,
          players: [
            {
              seat: 0,
              player_id: 'p0',
              life: 40,
              hand_count: 0,
              battlefield: [
                { object_id: 'a2', name: 'Attacker', power: 5, toughness: 5, tapped: true },
                { object_id: 'a3', name: 'TriggerGuy', power: 3, toughness: 3, tapped: true, oracle_text: 'Whenever TriggerGuy attacks, draw a card.' }
              ]
            },
            {
              seat: 1,
              player_id: 'p1',
              life: 20,
              hand_count: 0,
              battlefield: [
                { object_id: 'b1', name: 'Morph', face_down: true },
                { object_id: 'b2', name: 'Soldier', power: 2, toughness: 2, tapped: false }
              ]
            }
          ],
          combat: {
            attacks: [
              { attacker_id: 'a2', attacker: 'Attacker', target: 'Sitz 2' },
              { attacker_id: 'a3', attacker: 'TriggerGuy', target: 'Sitz 2' }
            ],
            blocks: [
              { attacker_id: 'a2', attacker: 'Attacker', blocker_id: 'b1', blocker: 'Morph' },
              { attacker_id: 'a2', attacker: 'Attacker', blocker_id: 'b2', blocker: 'Soldier' }
            ]
          }
        };
        const complexOut = CP.evaluateCombatPreview(multiAndComplexFrame, null, {});
        console.log(JSON.stringify({ withTrickRisk, complexOut }));
        """
    )
    assert out["withTrickRisk"]["trickRisk"]["risk"] is True
    assert out["withTrickRisk"]["certainty"] == "uncertain"
    assert any("Tricks" in r for r in out["withTrickRisk"]["uncertaintyReasons"])

    assert out["complexOut"]["certainty"] == "uncertain"
    assert out["complexOut"]["creatureOutcomes"]["a2"]["outcome"] == "uncertain"
    assert out["complexOut"]["creatureOutcomes"]["b1"]["outcome"] == "uncertain"
    assert out["complexOut"]["creatureOutcomes"]["a3"]["outcome"] == "uncertain"
    reasons_blob = " ".join(out["complexOut"]["uncertaintyReasons"])
    assert "Mehrfachblock" in reasons_blob
    assert "Verdeckte Kreatur" in reasons_blob
    assert "Trigger" in reasons_blob


def test_combat_preview_static_wiring_and_security_hygiene() -> None:
    html = (STATIC_DIR / "partie.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "partie.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "partie.js").read_text(encoding="utf-8")
    module_js = (STATIC_DIR / "combat_preview_ux.js").read_text(encoding="utf-8")

    assert 'id="combat-preview"' in html
    assert '<script src="combat_preview_ux.js"></script>' in html
    assert html.index("combat_preview_ux.js") < html.index("partie.js")
    for token in (
        ".combat-preview",
        ".combat-preview.uncertain",
        ".seat-life-preview",
        ".badge.preview-dies",
    ):
        assert token in css
    for token in ("computeCurrentCombatPreview", "renderCombatPreview", "refreshCombatPreviewLive"):
        assert token in js
    for forbidden in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "document.",
        "window.",
    ):
        assert forbidden not in module_js


def test_combat_preview_enriches_stripped_frame_from_pilot_state_and_facts() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        // Shape matching pilotStateToFrame(): no player_id, no oracle_text, no types, no frame.combat
        const strippedFrame = {
          turn: 5,
          phase: 'combat',
          step: 'declare_blockers',
          active_seat: 1,
          seat: 0,
          players: [
            {
              seat: 0,
              life: 10,
              hand_count: 0,
              battlefield: [
                { object_id: 'blk-1', name: 'Serra Angel', power: 4, toughness: 4, damage: 0, tapped: false },
                { object_id: 'hid-1', name: '(verdeckt)', power: 2, toughness: 2, damage: 0, tapped: false }
              ]
            },
            {
              seat: 1,
              life: 18,
              hand_count: 2,
              battlefield: [
                { object_id: 'atk-1', name: 'Ghalta, Primal Hunger', power: 6, toughness: 3, damage: 0, tapped: true },
                { object_id: 'l-1', name: 'Forest', tapped: false }
              ]
            }
          ]
        };
        const pendingBlk = {
          decision_id: 'blk-s',
          decision_class: 'declare_blocker',
          seat: 0,
          legal_options: [
            { option_id: 'atk-1', option_type: 'declare_blocker', metadata: { attacker_id: 'atk-1', blocker_id: 'blk-1' }, label: 'Serra Angel blocks Ghalta' }
          ],
          pilot_state: {
            players: [
              { seat: 0, player_id: 'uuid-p0', battlefield: [{ object_id: 'blk-1', name: 'Serra Angel' }, { object_id: 'hid-1', name: 'Secret Morph', face_down: true }] },
              { seat: 1, player_id: 'uuid-p1', battlefield: [{ object_id: 'atk-1', name: 'Ghalta, Primal Hunger' }, { object_id: 'l-1', name: 'Forest', types: ['Land'] }] }
            ],
            combat: {
              attacks: [{ attacker_id: 'atk-1', attacker: 'Ghalta, Primal Hunger', target: 'uuid-p0' }],
              blocks: []
            }
          }
        };
        const pendingAtk = {
          decision_id: 'atk-s',
          decision_class: 'declare_attacker',
          seat: 0,
          legal_options: [
            { option_id: 'opt-uuid', option_type: 'declare_attacker', metadata: { object_id: 'blk-1', defender_id: 'uuid-p1' }, label: 'Serra Angel attacks' }
          ],
          pilot_state: { players: pendingBlk.pilot_state.players }
        };
        const facts = {
          'Ghalta, Primal Hunger': { oracle_text: 'Trample', type_line: 'Legendary Creature' },
          'Serra Angel': { oracle_text: 'Flying, vigilance', type_line: 'Creature' },
          'Forest': { type_line: 'Basic Land — Forest' }
        };
        const tramplePv = CP.evaluateCombatPreview(strippedFrame, pendingBlk, { selectedOptions: ['atk-1'], facts });
        const uuidDefPv = CP.evaluateCombatPreview(
          { turn: 5, phase: 'combat', step: 'declare_attackers', active_seat: 0, seat: 0, players: strippedFrame.players },
          pendingAtk,
          { selectedOptions: ['opt-uuid'], facts }
        );
        const faceDownPv = CP.evaluateCombatPreview(strippedFrame, {
          decision_id: 'blk-f',
          decision_class: 'declare_blocker',
          seat: 0,
          legal_options: [{ option_id: 'atk-1', option_type: 'declare_blocker', metadata: { attacker_id: 'atk-1', blocker_id: 'hid-1' } }],
          pilot_state: pendingBlk.pilot_state
        }, { selectedOptions: ['atk-1'], facts });
        console.log(JSON.stringify({ tramplePv, uuidDefPv, faceDownPv }));
        """
    )
    assert out["tramplePv"]["seatEffects"]["0"]["incomingDamage"] == 2
    assert out["tramplePv"]["seatEffects"]["0"]["newLife"] == 8
    assert out["uuidDefPv"]["seatEffects"]["1"]["incomingDamage"] == 4
    assert out["uuidDefPv"]["trickRisk"]["risk"] is True
    assert out["uuidDefPv"]["certainty"] == "uncertain"
    assert out["uuidDefPv"]["creatureOutcomes"]["blk-1"]["outcome"] == "uncertain"
    assert out["faceDownPv"]["creatureOutcomes"]["hid-1"]["outcome"] == "uncertain"
    assert any("Verdeckte Kreatur" in r for r in out["faceDownPv"]["uncertaintyReasons"])


def test_combat_preview_xmage_redactor_real_payloads_and_review_regressions() -> None:
    out = _node_json(
        """
        const CP = require('./combat_preview_ux.js');
        const P1a = require('./play_p1a.js');

        // 1. P1 #1: masked op-1 player_id vs real UUID defender_id + Full Game Seat N option label + ownCombat ledger
        const redactorFrame = {
          turn: 4, phase: 'combat', step: 'declare_attackers', active_seat: 0, seat: 0,
          players: [
            { seat: 0, life: 40, hand_count: 0, battlefield: [{ object_id: 'atk-chulane', name: 'Chulane', power: 2, toughness: 4, tapped: false }] },
            { seat: 1, life: 15, hand_count: 0, battlefield: [] }
          ]
        };
        const redactorAtkDec = {
          decision_id: 'atk-real',
          decision_class: 'declare_attacker',
          seat: 0,
          legal_options: [{
            option_id: 'opt-real-1',
            option_type: 'declare_attacker',
            label: 'Chulane attacks Full Game Seat 2',
            metadata: { object_id: 'atk-chulane', name: 'Chulane', defender_id: 'de61be79-real-uuid' }
          }],
          pilot_state: {
            turn_number: 4,
            step: 'declare_attackers',
            players: [
              { seat: 0, player_id: 'you' },
              { seat: 1, player_id: 'op-1' }
            ]
          }
        };
        const stagedReal = CP.evaluateCombatPreview(redactorFrame, redactorAtkDec, { selectedOptions: ['opt-real-1'] });
        const ledgerAfterReal = P1a.recordOwnCombatAnswer(P1a.emptyCombatLedger(), redactorAtkDec, ['opt-real-1']);
        const ledgerPv = CP.evaluateCombatPreview(
          { turn: 4, phase: 'combat', step: 'declare_blockers', active_seat: 0, seat: 1, players: redactorFrame.players },
          null,
          { ownCombat: ledgerAfterReal }
        );

        // 2. P1 #2 + P2 #4 + P3 #10/#12: declare_blocker without combat field reconstructs unblocked attackers,
        // checks attacking opponent's tricks (Treasure + hand_count: null with hand array), ignores own hand
        const blkNoCombatFrame = {
          turn: 5, phase: 'combat', step: 'declare_blockers', active_seat: 1, seat: 0,
          players: [
            { seat: 0, life: 12, hand_count: 4, battlefield: [
              { object_id: 'my-blk', name: 'Wall', power: 1, toughness: 4, tapped: false },
              { object_id: 'my-land', name: 'Island', tapped: false, types: ['Land'] }
            ] },
            { seat: 1, life: 30, hand_count: null, hand: ['Secret Card'], battlefield: [
              { object_id: 'opp-atk', name: 'Beast', power: 5, toughness: 3, tapped: true },
              { object_id: 'treasure-1', name: 'Treasure Token', tapped: false, oracle_text: '{T}, Sacrifice this artifact: Add one mana of any color.' }
            ] }
          ]
        };
        const blkNoCombatDec = {
          decision_id: 'blk-no-combat',
          decision_class: 'declare_blocker',
          seat: 0,
          maximum_selections: 1,
          metadata: { blocker_id: 'my-blk' },
          legal_options: [{
            option_id: 'opp-atk',
            option_type: 'declare_blocker',
            label: 'Wall blocks Beast',
            metadata: { attacker_id: 'opp-atk', blocker_id: 'my-blk' }
          }]
        };
        const blkPreSelect = CP.evaluateCombatPreview(blkNoCombatFrame, blkNoCombatDec, { selectedOptions: [] });
        const blkFallbackNoTrick = CP.evaluateCombatPreview(
          {
            turn: 5, phase: 'combat', step: 'declare_blockers', active_seat: 1, seat: 0,
            players: [
              blkNoCombatFrame.players[0],
              { seat: 1, life: 30, hand_count: 0, battlefield: [{ object_id: 'opp-atk', name: 'Beast', power: 5, toughness: 3, tapped: true }] }
            ]
          },
          blkNoCombatDec,
          { selectedOptions: [] }
        );
        // With defending Planeswalker and no fallbackCombat, reconstructed target warns uncertainty
        const pwReconstructFrame = {
          turn: 5, phase: 'combat', step: 'declare_blockers', active_seat: 1, seat: 0,
          players: [
            { seat: 0, life: 12, hand_count: 0, battlefield: [
              { object_id: 'my-blk', name: 'Wall', power: 1, toughness: 4, tapped: false },
              { object_id: 'my-pw', name: 'Jace', type_line: 'Legendary Planeswalker — Jace' }
            ] },
            { seat: 1, life: 30, hand_count: 0, battlefield: [{ object_id: 'opp-atk', name: 'Beast', power: 5, toughness: 3, tapped: true }] }
          ]
        };
        const blkWithPwUncertain = CP.evaluateCombatPreview(pwReconstructFrame, blkNoCombatDec, { selectedOptions: [] });

        // 3. P1 #3: Deathtouch does NOT kill via pre-existing damage when 0 deathtouch combat damage was dealt
        const dtZero = CP.simulateOneVsOne(
          { name: 'ZeroDT', power: 0, toughness: 4, oracle_text: 'Deathtouch' },
          { name: 'Injured', power: 2, toughness: 4, damage: 2 }
        );
        const dtVsFirstStrike = CP.simulateOneVsOne(
          { name: 'BearDT', power: 2, toughness: 2, oracle_text: 'Deathtouch' },
          { name: 'KnightFS', power: 2, toughness: 4, damage: 1, oracle_text: 'First strike' }
        );

        // 4. P2 #5: card.abilities, non-self keyword rejection, and double-damage instead pattern
        const nonSelfKw = CP.extractKeywords({
          name: 'Elvish Archdruid', power: 2, toughness: 2,
          oracle_text: 'Other Elves you control have deathtouch and trample.\\nCreatures blocking this lose indestructible.',
          abilities: ['First strike']
        });
        const doublerCheck = CP.detectComplexCombatText({
          name: 'Furnace Fiend', power: 4, toughness: 4,
          oracle_text: 'If a source would deal damage, it deals double that damage instead.'
        });

        // 5. P2 #6: Duplicate card names disambiguated by active_seat
        const dupFrame = {
          turn: 3, phase: 'combat', step: 'declare_blockers', active_seat: 1, seat: 0,
          players: [
            { seat: 0, life: 20, hand_count: 0, battlefield: [{ object_id: 'b-p0', name: 'Grizzly Bears', power: 2, toughness: 2, tapped: false }] },
            { seat: 1, life: 20, hand_count: 0, battlefield: [{ object_id: 'b-p1', name: 'Grizzly Bears', power: 4, toughness: 4, tapped: true }] }
          ],
          combat: { attacks: [{ attacker: 'Grizzly Bears', target: 'Sitz 1' }], blocks: [] }
        };
        const dupPv = CP.evaluateCombatPreview(dupFrame, null, {});

        // 6. P2 #8: Planeswalker defender_id + object hover in declare_attacker
        const pwAtkFrame = {
          turn: 4, phase: 'combat', step: 'declare_attackers', active_seat: 0, seat: 0,
          players: [
            { seat: 0, life: 40, hand_count: 0, battlefield: [{ object_id: 'a-pw', name: 'Bear', power: 3, toughness: 3, tapped: false }] },
            { seat: 1, life: 20, hand_count: 0, battlefield: [{ object_id: 'pw-uuid-1', name: 'Nissa, Who Shakes', type_line: 'Planeswalker' }] }
          ]
        };
        const pwAtkDec = {
          decision_id: 'atk-pw', decision_class: 'declare_attacker', seat: 0,
          legal_options: [{ option_id: 'opt-pw', option_type: 'declare_attacker', label: 'Bear attacks Nissa', metadata: { object_id: 'a-pw', defender_id: 'pw-uuid-1' } }]
        };
        const pwHoverPv = CP.evaluateCombatPreview(pwAtkFrame, pwAtkDec, {
          selectedOptions: [],
          drag: { kind: 'attacker', objectId: 'a-pw', name: 'Bear' },
          hoveredTarget: { type: 'object', id: 'pw-uuid-1' }
        });
        const pwFrameNamedPv = CP.evaluateCombatPreview(
          {
            turn: 4, phase: 'combat', step: 'declare_blockers', active_seat: 0, seat: 1,
            players: pwAtkFrame.players,
            combat: { attacks: [{ attacker: 'Bear', target: 'Nissa, Who Shakes' }], blocks: [] }
          },
          null,
          {}
        );

        // 7. P3 #13 & #14: post-damage replay step doesn't re-subtract life; maxSel=1 hover replaces staged block
        const postDmgPv = CP.evaluateCombatPreview(
          {
            turn: 5, phase: 'combat', step: 'combat_damage', active_seat: 0, seat: 1,
            players: [
              { seat: 0, life: 20, hand_count: 0, battlefield: [{ object_id: 'a1', name: 'Wurm', power: 6, toughness: 6, tapped: true }] },
              { seat: 1, life: 14, hand_count: 0, battlefield: [] }
            ],
            combat: { attacks: [{ attacker_id: 'a1', attacker: 'Wurm', target: 'Sitz 2' }], blocks: [] }
          },
          null,
          {}
        );
        const hoverReplaceDec = {
          decision_id: 'blk-rep', decision_class: 'declare_blocker', seat: 0, maximum_selections: 1,
          legal_options: [
            { option_id: 'atk-a', option_type: 'declare_blocker', metadata: { attacker_id: 'atk-a', blocker_id: 'my-b' } },
            { option_id: 'atk-b', option_type: 'declare_blocker', metadata: { attacker_id: 'atk-b', blocker_id: 'my-b' } }
          ]
        };
        const hoverReplacePv = CP.evaluateCombatPreview(
          {
            turn: 5, phase: 'combat', step: 'declare_blockers', active_seat: 1, seat: 0,
            players: [
              { seat: 0, life: 20, hand_count: 0, battlefield: [{ object_id: 'my-b', name: 'Wall', power: 2, toughness: 5, tapped: false }] },
              { seat: 1, life: 20, hand_count: 0, battlefield: [{ object_id: 'atk-a', name: 'Bear', power: 2, toughness: 2, tapped: true }, { object_id: 'atk-b', name: 'Ogre', power: 4, toughness: 4, tapped: true }] }
            ],
            combat: {
              attacks: [
                { attacker_id: 'atk-a', attacker: 'Bear', target: 'Sitz 1' },
                { attacker_id: 'atk-b', attacker: 'Ogre', target: 'Sitz 1' }
              ],
              blocks: []
            }
          },
          hoverReplaceDec,
          {
            selectedOptions: ['atk-a'],
            drag: { kind: 'blocker', objectId: 'my-b', name: 'Wall' },
            hoveredTarget: { type: 'object', id: 'atk-b' }
          }
        );

        console.log(JSON.stringify({
          stagedReal, ledgerPv, blkPreSelect, blkFallbackNoTrick, blkWithPwUncertain,
          dtZero, dtVsFirstStrike, nonSelfKw, doublerCheck, dupPv, pwHoverPv, pwFrameNamedPv, postDmgPv, hoverReplacePv
        }));
        """
    )
    # P1 #1
    assert out["stagedReal"]["seatEffects"]["1"]["incomingDamage"] == 2
    assert out["stagedReal"]["clashes"][0]["defenderLabel"] == "Sitz 2"
    assert out["ledgerPv"]["seatEffects"]["1"]["incomingDamage"] == 2
    # P1 #2 + P2 #4 + P3 #10/#12
    assert out["blkPreSelect"]["visible"] is True
    assert out["blkPreSelect"]["trickRisk"]["risk"] is True
    assert out["blkPreSelect"]["trickRisk"]["seats"] == [1]
    assert out["blkPreSelect"]["seatEffects"]["0"]["newLife"] == 7
    assert out["blkFallbackNoTrick"]["trickRisk"]["risk"] is False
    assert out["blkWithPwUncertain"]["certainty"] == "uncertain"
    assert any("Planeswalker" in r for r in out["blkWithPwUncertain"]["uncertaintyReasons"])
    # P1 #3
    assert out["dtZero"]["blockerDies"] is False
    assert out["dtVsFirstStrike"]["blockerDies"] is False
    assert out["dtVsFirstStrike"]["attackerDies"] is True
    # P2 #5
    assert out["nonSelfKw"]["firstStrike"] is True
    assert out["nonSelfKw"]["deathtouch"] is False
    assert out["nonSelfKw"]["indestructible"] is False
    assert out["doublerCheck"]["complex"] is True
    # P2 #6
    assert out["dupPv"]["clashes"][0]["attackerSeat"] == 1
    assert out["dupPv"]["seatEffects"]["0"]["incomingDamage"] == 4
    # P2 #8
    pw_clash = out["pwHoverPv"]["clashes"][0]
    assert pw_clash["defenderLabel"] == "Nissa, Who Shakes"
    assert pw_clash["playerDamage"] == 0
    assert "Loyalit." in pw_clash["summaryText"]
    pw_named_clash = out["pwFrameNamedPv"]["clashes"][0]
    assert pw_named_clash["defenderLabel"] == "Nissa, Who Shakes"
    assert pw_named_clash["playerDamage"] == 0
    assert pw_named_clash["certainty"] == "uncertain"
    assert any("Planeswalker" in r for r in pw_named_clash["reasons"])
    # P3 #13 & #14
    assert out["postDmgPv"]["seatEffects"].get("1", {}).get("delta", 0) == 0
    assert out["postDmgPv"]["certainty"] == "uncertain"
    atk_a_clash = next(c for c in out["hoverReplacePv"]["clashes"] if c["attackerId"] == "atk-a")
    atk_b_clash = next(c for c in out["hoverReplacePv"]["clashes"] if c["attackerId"] == "atk-b")
    assert atk_a_clash["blockers"] == []
    assert len(atk_b_clash["blockers"]) == 1

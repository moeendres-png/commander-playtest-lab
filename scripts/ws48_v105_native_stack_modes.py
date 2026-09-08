#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

IMPORT_ANCHOR = 'import forge.game.GameState;\n'
IMPORTS = 'import forge.game.GameState;\nimport forge.game.ability.effects.CharmEffect;\nimport forge.game.spellability.AbilitySub;\n'

OLD_APPLY = '''    private static void applyStack(Game game) {
        stackAbilities.clear();
        List<String[]> ws40StackRows = rows("COMMANDER_LAB_WS40_STACK_SPECS_B64");
        java.util.Collections.reverse(ws40StackRows);
        for (String[] p : ws40StackRows) {
            if (p.length != 5) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_SPEC_ARITY:" + p.length);
            String sid = dec(p[0]);
            int ownerSeat = Integer.parseInt(p[1]);
            int controllerSeat = Integer.parseInt(p[2]);
            String name = dec(p[3]);
            String targetCsv = dec(p[4]);
            PaperCard pc = StaticData.instance().getCommonCards().getCard(name);
            if (pc == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_CARD_MISSING:" + name);
            Card host = Card.fromPaperCard(pc, player(game, ownerSeat));
            if (ownerSeat != controllerSeat) host.setController(player(game, controllerSeat), game.getNextTimestamp());
            SpellAbility sa = host.getFirstSpellAbility();
            if (sa == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_NO_SA:" + name);
            sa.setActivatingPlayer(player(game, controllerSeat));
            if (!targetCsv.isEmpty()) {
                for (String key : targetCsv.split(",")) sa.getTargets().add(target(game, key));
            }
            RestoredSpellCastHistory.restoreCompletedPaidSpell(game, sa);
            stackAbilities.put(sid, sa);
            semanticCards.put(sid, sa.getHostCard());
        }
    }
'''

NEW_APPLY = '''    private static String ws48SemanticMode(SpellAbility mode) {
        if (mode == null) return null;
        // Provider-neutral identity is normalized from Forge-native ability parameters.
        // Mode legality comes from CharmEffect native options; target legality remains
        // owned by RestoredSpellCastHistory / SpellAbility.canTarget.
        if ("Battlefield".equals(mode.getParam("Origin"))
                && "Library".equals(mode.getParam("Destination"))
                && "-1".equals(mode.getParam("LibraryPosition"))
                && mode.usesTargeting()) {
            return "put_creature_on_bottom_of_owners_library";
        }
        return null;
    }

    private static List<String> ws48RequestedModes(String encoded) {
        String raw = dec(encoded);
        if (raw.isEmpty()) return List.of();
        return java.util.Arrays.asList(raw.split("\\u001f", -1));
    }

    private static SpellAbility ws48RestoreModes(SpellAbility sa, List<String> requestedModes) {
        if (requestedModes.isEmpty()) return sa;
        if (!sa.hasParam("Choices")) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STACK_MODE_REQUEST_ON_NONMODAL_SPELL");
        }
        if (requestedModes.size() != 1) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STACK_MODE_CARDINALITY_UNSUPPORTED:" + requestedModes.size());
        }
        String requested = requestedModes.get(0);
        List<AbilitySub> matches = new ArrayList<>();
        for (AbilitySub option : CharmEffect.makePossibleOptions(sa)) {
            if (requested.equals(ws48SemanticMode(option))) matches.add(option);
        }
        if (matches.size() != 1) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STACK_MODE_NATIVE_MATCH_NONUNIQUE:" + requested + ":" + matches.size());
        }
        CharmEffect.chainAbilities(sa, matches);
        if (sa.getSubAbility() == null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STACK_MODE_NATIVE_CHAIN_MISSING:" + requested);
        }
        return sa.getSubAbility();
    }

    private static void applyStack(Game game) {
        stackAbilities.clear();
        List<String[]> ws40StackRows = rows("COMMANDER_LAB_WS40_STACK_SPECS_B64");
        java.util.Collections.reverse(ws40StackRows);
        for (String[] p : ws40StackRows) {
            if (p.length != 6) throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STATE_STACK_SPEC_ARITY:" + p.length);
            String sid = dec(p[0]);
            int ownerSeat = Integer.parseInt(p[1]);
            int controllerSeat = Integer.parseInt(p[2]);
            String name = dec(p[3]);
            String targetCsv = dec(p[4]);
            List<String> requestedModes = ws48RequestedModes(p[5]);
            PaperCard pc = StaticData.instance().getCommonCards().getCard(name);
            if (pc == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_CARD_MISSING:" + name);
            Card host = Card.fromPaperCard(pc, player(game, ownerSeat));
            if (ownerSeat != controllerSeat) host.setController(player(game, controllerSeat), game.getNextTimestamp());
            SpellAbility sa = host.getFirstSpellAbility();
            if (sa == null) throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STATE_STACK_NO_SA:" + name);
            sa.setActivatingPlayer(player(game, controllerSeat));
            SpellAbility targetAbility = ws48RestoreModes(sa, requestedModes);
            if (!targetCsv.isEmpty()) {
                for (String key : targetCsv.split(",")) targetAbility.getTargets().add(target(game, key));
            }
            RestoredSpellCastHistory.restoreCompletedPaidSpell(game, sa);
            stackAbilities.put(sid, sa);
            semanticCards.put(sid, sa.getHostCard());
        }
    }
'''

OLD_TARGETS = '''    private static String stackTargetsJson(Game game, SpellAbility sa) {
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (GameObject target : sa.getTargets()) {
            if (!first) b.append(',');
            first = false;
            b.append(Ws23ForgeVerticalProvider.esc(stackTargetSemantic(game, target)));
        }
        return b.append(']').toString();
    }
'''
NEW_TARGETS = '''    private static String stackTargetsJson(Game game, SpellAbility sa) {
        SpellAbility targetAbility = sa;
        if (sa.hasParam("Choices") && sa.getSubAbility() != null) targetAbility = sa.getSubAbility();
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (GameObject target : targetAbility.getTargets()) {
            if (!first) b.append(',');
            first = false;
            b.append(Ws23ForgeVerticalProvider.esc(stackTargetSemantic(game, target)));
        }
        return b.append(']').toString();
    }

    private static String stackModesJson(SpellAbility sa) {
        if (!sa.hasParam("Choices")) return "[]";
        List<String> modes = new ArrayList<>();
        for (SpellAbility sub = sa.getSubAbility(); sub != null; sub = sub.getSubAbility()) {
            String semantic = ws48SemanticMode(sub);
            if (semantic == null) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS48_STACK_MODE_NATIVE_READBACK_UNSUPPORTED:" + sub.getDescription());
            }
            modes.add(semantic);
        }
        StringBuilder b = new StringBuilder("[");
        for (int i = 0; i < modes.size(); i++) {
            if (i > 0) b.append(',');
            b.append(Ws23ForgeVerticalProvider.esc(modes.get(i)));
        }
        return b.append(']').toString();
    }
'''

OLD_STACK_JSON = '''            if (sa.getChosenList() != null && !sa.getChosenList().isEmpty()) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS40_STACK_MODE_OBSERVATION_UNSUPPORTED_NONEMPTY:" + e.getKey());
            }
            if (!first) b.append(','); first = false;
            b.append("{\\"source_semantic_id\\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))
                .append(",\\"native_stack_present\\":true")
                .append(",\\"cast_complete\\":").append(RestoredSpellCastHistory.isCastComplete(sa))
                .append(",\\"controller\\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,sa.getActivatingPlayer())))
                .append(",\\"costs_paid\\":").append(RestoredSpellCastHistory.areCostsPaid(sa))
                .append(",\\"modes\\":[]")
                .append(",\\"targets\\":").append(stackTargetsJson(game, sa))
'''
NEW_STACK_JSON = '''            if (!first) b.append(','); first = false;
            b.append("{\\"source_semantic_id\\":").append(Ws23ForgeVerticalProvider.esc(e.getKey()))
                .append(",\\"native_stack_present\\":true")
                .append(",\\"cast_complete\\":").append(RestoredSpellCastHistory.isCastComplete(sa))
                .append(",\\"controller\\":").append(Ws23ForgeVerticalProvider.esc(playerId(game,sa.getActivatingPlayer())))
                .append(",\\"costs_paid\\":").append(RestoredSpellCastHistory.areCostsPaid(sa))
                .append(",\\"modes\\":").append(stackModesJson(sa))
                .append(",\\"targets\\":").append(stackTargetsJson(game, sa))
'''

OLD_RUNNER = '''        out.append([enc(s["source_semantic_id"]),str(seat(o["owner"])),str(seat(s["controller"])),enc(o["card_identity"]),enc(",".join(s.get("targets") or []))])
'''
NEW_RUNNER = '''        out.append([enc(s["source_semantic_id"]),str(seat(o["owner"])),str(seat(s["controller"])),enc(o["card_identity"]),enc(",".join(s.get("targets") or [])),enc("\\u001f".join(s.get("modes") or []))])
'''

def replace_once(text, old, new, label):
    if new in text:
        return text, False
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 target, found {n}')
    return text.replace(old, new, 1), True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-java', type=Path, required=True)
    ap.add_argument('--runner', type=Path, required=True)
    a = ap.parse_args()
    s = a.state_java.read_text()
    changed = False
    if 'import forge.game.ability.effects.CharmEffect;' not in s:
        s, n = replace_once(s, IMPORT_ANCHOR, IMPORTS, 'imports'); changed |= n
    s, n = replace_once(s, OLD_APPLY, NEW_APPLY, 'applyStack'); changed |= n
    s, n = replace_once(s, OLD_TARGETS, NEW_TARGETS, 'stackTargetsJson'); changed |= n
    s, n = replace_once(s, OLD_STACK_JSON, NEW_STACK_JSON, 'stackJson'); changed |= n
    required = ['CharmEffect.makePossibleOptions(sa)', 'CharmEffect.chainAbilities(sa, matches)', 'RestoredSpellCastHistory.restoreCompletedPaidSpell(game, sa)', 'stackModesJson(sa)', 'WS48_STACK_MODE_NATIVE_MATCH_NONUNIQUE']
    if not all(x in s for x in required):
        raise SystemExit('WS48 stack mode Java patch incomplete')
    a.state_java.write_text(s)
    r = a.runner.read_text()
    r, n = replace_once(r, OLD_RUNNER, NEW_RUNNER, 'runner stack_rows'); changed |= n
    if 'enc("\\u001f".join(s.get("modes") or []))' not in r:
        raise SystemExit('WS48 runner mode transport incomplete')
    a.runner.write_text(r)
    print('WS48_V105_NATIVE_STACK_MODES=' + ('PASS' if changed else 'ALREADY_APPLIED'))

if __name__ == '__main__':
    main()

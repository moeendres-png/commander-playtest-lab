#!/usr/bin/env python3
"""WS55 mandatory decision-breadth provider overlay v1 (WS55-owned, qualification-only).

Chained patch applied AFTER candidate-qualification/ws53-forge-convergence-native-progression/
ws53_provider_overlay.py onto the ephemeral generated GPL-side provider
(Ws23ForgeVerticalProvider.java). Never touches pinned Forge source, shared
scripts, WS48/WS53-owned files, or another workstream's files.

Rules-Core authority is preserved throughout: every new discretionary branch
enumerates ONLY Forge-native options and returns the harness-selected OPAQUE
option id with exact native binding. Zero/ambiguous/stale cases fail closed.
Singleton/non-discretionary cases mirror the native Human controller exactly
(recordAutomatic, no external frame).

Additions (all systemic, no card-name hacks, no per-card branches):
 J1. chooseOptionalCosts: sequential multi-select over the engine-provided
     OptionalCostValue list (GameActionUtil.getOptionalCostValues); DONE
     always offered (native Human allows 0..size); exact OptionalCostValue
     binding; broker kind "optional_costs"; labels WS55:OPTCOST.
 J2. orderCosts: exact mirror of PlayerControllerHuman (auto-return unless
     FullControlFlag.ChooseCostOrder AND >=2 parts, with recordAutomatic);
     otherwise permutation frames over the engine-provided CostPart list
     (n<=5 bound, exact multiset binding); broker kind "order_costs".
 J3. orderBlockers / orderBlocker / orderAttackers: permutation/insertion
     frames over the engine-provided CardCollection (n<=5 bound, exact
     positional binding of the SAME Card objects); 0/1 fast path mirrors the
     Combat.java caller gate (recordAutomatic, no external frame); broker
     kind "order_combat"; labels WS55:ORDERBLOCKERS/ORDERBLOCKER/ORDERATTACKERS.
 J4. chooseModeForAbility multi: sequential externalization WITHIN the single
     native call (engine-remaining-modes + DONE iff >= min; min/num/
     allowRepeat enforced provider-side as bounds only, legality stays in
     the engine-supplied possible list); exact AbilitySub binding; mutable
     ArrayList return preserved; broker kind "choose_mode" (same as single).
 J5. orderSimultaneousSa N>2: general permutation frames (n<=5 bound, exact
     SpellAbility binding, multiset validated); 0/1 auto + exactly-2 binary
     path byte-identical (WS53-proven replay compatibility); broker kind
     "trigger_order" (same).
 J6. Deck-list env generalization (fixture syntax only): when
     COMMANDER_LAB_FORGE_DECK_MAIN / COMMANDER_LAB_FORGE_DECK_COMMANDER are
     absent, the legacy Mountain/Rograkh canonical path runs byte-identical.
     When present, PaperCards resolve via the native StaticData CardDb
     (getAllCards first print; UNKNOWN-print native precedent fallback), same forCommander registration, same natural
     shuffle/startup. Setup classification stays NATURAL_GAME_START.
 J7. Order-combatants fixture config: COMMANDER_LAB_FORGE_ORDER_COMBATANTS=1
     sets GameRules.setOrderCombatants(true) at session construction (same
     class as player-count/Commander-variant config); absent preserving the
     legacy default (false). The engine then natively enters (or skips) the
     orderBlockers/orderAttackers path; journaled per run.
 J8. Ranged integer choice (announceRequirements / chooseNumber int
     overload): when the engine-supplied [min,max] width exceeds 64, emit
     ONE WS55:NUMRANGE descriptor (engine bounds verbatim) and accept the
     external integer by VALUE in SUBMIT_DECISION, validated natively
     (parse + min<=v<=max; missing/malformed/out-of-range fail closed).
     Human integer-dialog mirror; no legality reconstructed. Width<=64
     keeps exact NUM enumeration; min==max keeps the automatic record.
 J9. Optional-trigger confirmation + choiceless trigger execution:
     confirmTrigger(WrappedAbility) offers an external YES/NO over the
     engine-identified trigger (host + trigger text projected; Human asks
     unless auto-yield/cost-trigger, both absent headless: cost-triggers
     mirror Human with recordAutomatic + true). playTrigger /
     playSaFromPlayEffect mirror Human exactly (native
     playSpellAbilityNoStack / playSpellAbility execution; nested
     discretionary choices re-enter the controller). Broker kind
     "confirm" (same CONFIRM grammar as confirmAction).

Explicitly NOT changed (remain fail-closed, recorded as gaps):
 - chooseCombatDamage / chooseAmountDistribution (already present via the
   ws40 base generator: Core-view enumeration, exact selection binding).
 - confirmTrigger / playTrigger / playSaFromPlayEffect / vote /
   chooseCardsPile / choosePermanentsToSacrifice-Destroy / chooseCardName /
   chooseSomeType / specifyManaCombo / divideShield / sideboard et al.
 - Broker.choose SUBMIT verification (actor/kind binding enforced
   harness-side in the WS55 runner; engine-side hole documented in Q9).
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS55_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- J1: optional costs
OPTIONAL_COSTS_OLD = """        public List<OptionalCostValue> chooseOptionalCosts(SpellAbility choosen, List<OptionalCostValue> optionalCostValues) {
            throw failClosed("chooseOptionalCosts");
        }"""

OPTIONAL_COSTS_NEW = """        @Override
        public List<OptionalCostValue> chooseOptionalCosts(SpellAbility choosen, List<OptionalCostValue> optionalCostValues) {
            ws48Milestone("chooseOptionalCosts:ENTERED");
            if (optionalCostValues == null) throw failClosed("chooseOptionalCosts:NULL");
            if (optionalCostValues.isEmpty()) {
                broker.recordAutomatic("chooseOptionalCosts:EMPTY");
                return new java.util.ArrayList<>();
            }
            java.util.List<OptionalCostValue> remaining = new java.util.ArrayList<>(optionalCostValues);
            java.util.List<OptionalCostValue> chosen = new java.util.ArrayList<>();
            int guard = 0;
            while (true) {
                if (++guard > 16) throw failClosed("chooseOptionalCosts:GUARD");
                java.util.List<OptionalCostValue> rest = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                labels.add("WS55:OPT:DONE");
                for (OptionalCostValue o : remaining) {
                    rest.add(o);
                    labels.add("WS55:OPTCOST:desc=" + ws48Enc(ws48Clip(String.valueOf(o), 200)));
                }
                if (rest.isEmpty()) break;
                int idx = ws48Choose("optional_costs", this.player, labels);
                if (idx == 0) break;
                OptionalCostValue pick = rest.get(idx - 1);
                if (!remaining.remove(pick)) throw failClosed("WS55_OPTIONAL_COST_STALE");
                chosen.add(pick);
            }
            return chosen;
        }"""

# ---------------------------------------------------------------- J2: order costs
ORDER_COSTS_OLD = """        public List<CostPart> orderCosts(List<CostPart> costs) {
            throw failClosed("orderCosts");
        }"""

ORDER_COSTS_NEW = """        @Override
        public List<CostPart> orderCosts(List<CostPart> costs) {
            ws48Milestone("orderCosts:ENTERED");
            if (costs == null) throw failClosed("orderCosts:NULL");
            if (!isFullControl(FullControlFlag.ChooseCostOrder) || costs.size() < 2) {
                broker.recordAutomatic("orderCosts:NATIVE_AUTO");
                return costs;
            }
            if (costs.size() > 5) throw failClosed("orderCosts:PERMUTATION_BOUND:" + costs.size());
            java.util.List<java.util.List<Integer>> perms = ws55Permutations(costs.size());
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (java.util.List<Integer> perm : perms) {
                StringBuilder sb = new StringBuilder("WS55:COSTORDER:order=");
                for (int k = 0; k < perm.size(); k++) {
                    if (k > 0) sb.append(',');
                    sb.append(perm.get(k));
                }
                sb.append(":parts=");
                for (int k = 0; k < perm.size(); k++) {
                    if (k > 0) sb.append('|');
                    sb.append(ws48Enc(ws48Clip(String.valueOf(costs.get(perm.get(k))), 80)));
                }
                labels.add(sb.toString());
            }
            java.util.List<Integer> pick = perms.get(ws48Choose("order_costs", this.player, labels));
            java.util.List<CostPart> out = new java.util.ArrayList<>();
            for (int i : pick) out.add(costs.get(i));
            return out;
        }"""

# ---------------------------------------------------------------- J3: combat ordering
ORDER_BLOCKERS_OLD = """        public CardCollection orderBlockers(Card attacker, CardCollection blockers) {
            throw failClosed("orderBlockers");
        }

        @Override
        public CardCollection orderBlocker(final Card attacker, final Card blocker, final CardCollection oldBlockers) {
            throw failClosed("orderBlocker");
        }

        @Override
        public CardCollection orderAttackers(Card blocker, CardCollection attackers) {
            throw failClosed("orderAttackers");
        }"""

ORDER_BLOCKERS_NEW = """        @Override
        public CardCollection orderBlockers(Card attacker, CardCollection blockers) {
            ws48Milestone("orderBlockers:ENTERED");
            if (blockers == null || blockers.isEmpty()) throw failClosed("orderBlockers:EMPTY");
            if (blockers.size() == 1) {
                broker.recordAutomatic("orderBlockers:SINGLETON");
                CardCollection ws55Single = new CardCollection();
                for (Card ws55c : blockers) ws55Single.add(ws55c);
                return ws55Single;
            }
            if (blockers.size() > 5) throw failClosed("orderBlockers:PERMUTATION_BOUND:" + blockers.size());
            java.util.List<Card> nativeOrder = new java.util.ArrayList<>(blockers);
            java.util.List<java.util.List<Integer>> perms = ws55Permutations(nativeOrder.size());
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (java.util.List<Integer> perm : perms) {
                StringBuilder sb = new StringBuilder("WS55:ORDERBLOCKERS:attacker=");
                sb.append(ws48Enc(ws48CardRef(attacker))).append(":order=");
                for (int k = 0; k < perm.size(); k++) {
                    if (k > 0) sb.append(',');
                    sb.append(ws48Enc(ws48CardRef(nativeOrder.get(perm.get(k)))));
                }
                labels.add(sb.toString());
            }
            java.util.List<Integer> pick = perms.get(ws48Choose("order_combat", this.player, labels));
            CardCollection out = new CardCollection();
            boolean[] seen = new boolean[nativeOrder.size()];
            for (int i : pick) {
                if (i < 0 || i >= nativeOrder.size() || seen[i]) throw failClosed("WS55_ORDERBLOCKERS_BAD_PERMUTATION");
                seen[i] = true;
                out.add(nativeOrder.get(i));
            }
            return out;
        }

        @Override
        public CardCollection orderBlocker(final Card attacker, final Card blocker, final CardCollection oldBlockers) {
            ws48Milestone("orderBlocker:ENTERED");
            if (oldBlockers == null || blocker == null) throw failClosed("orderBlocker:NULL");
            if (oldBlockers.size() + 1 > 6) throw failClosed("orderBlocker:PERMUTATION_BOUND:" + oldBlockers.size());
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (int pos = 0; pos <= oldBlockers.size(); pos++) {
                labels.add("WS55:ORDERBLOCKER:attacker=" + ws48Enc(ws48CardRef(attacker))
                    + ":blocker=" + ws48Enc(ws48CardRef(blocker)) + ":pos=" + pos);
            }
            int pos = ws48Choose("order_combat", this.player, labels);
            CardCollection out = new CardCollection();
            int i = 0;
            for (Card c : oldBlockers) {
                if (i == pos) out.add(blocker);
                out.add(c);
                i++;
            }
            if (i == pos) out.add(blocker);
            if (out.size() != oldBlockers.size() + 1) throw failClosed("WS55_ORDERBLOCKER_SIZE");
            return out;
        }

        @Override
        public CardCollection orderAttackers(Card blocker, CardCollection attackers) {
            ws48Milestone("orderAttackers:ENTERED");
            if (attackers == null || attackers.isEmpty()) throw failClosed("orderAttackers:EMPTY");
            if (attackers.size() == 1) {
                broker.recordAutomatic("orderAttackers:SINGLETON");
                CardCollection ws55Single = new CardCollection();
                for (Card ws55c : attackers) ws55Single.add(ws55c);
                return ws55Single;
            }
            if (attackers.size() > 5) throw failClosed("orderAttackers:PERMUTATION_BOUND:" + attackers.size());
            java.util.List<Card> nativeOrder = new java.util.ArrayList<>(attackers);
            java.util.List<java.util.List<Integer>> perms = ws55Permutations(nativeOrder.size());
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (java.util.List<Integer> perm : perms) {
                StringBuilder sb = new StringBuilder("WS55:ORDERATTACKERS:blocker=");
                sb.append(ws48Enc(ws48CardRef(blocker))).append(":order=");
                for (int k = 0; k < perm.size(); k++) {
                    if (k > 0) sb.append(',');
                    sb.append(ws48Enc(ws48CardRef(nativeOrder.get(perm.get(k)))));
                }
                labels.add(sb.toString());
            }
            java.util.List<Integer> pick = perms.get(ws48Choose("order_combat", this.player, labels));
            CardCollection out = new CardCollection();
            boolean[] seen = new boolean[nativeOrder.size()];
            for (int i : pick) {
                if (i < 0 || i >= nativeOrder.size() || seen[i]) throw failClosed("WS55_ORDERATTACKERS_BAD_PERMUTATION");
                seen[i] = true;
                out.add(nativeOrder.get(i));
            }
            return out;
        }"""

# ---------------------------------------------------------------- J4: multi-mode
MODE_MULTI_OLD = """            throw failClosed("chooseModeForAbility:DEPENDENT_MULTI_CHOICE");"""

MODE_MULTI_NEW = """            ws48Milestone("chooseModeForAbility:MULTI");
            java.util.List<AbilitySub> ws55Chosen = new java.util.ArrayList<>();
            int ws55Guard = 0;
            while (true) {
                if (++ws55Guard > 16) throw failClosed("chooseModeForAbility:GUARD");
                if (ws55Chosen.size() >= num) break;
                java.util.List<AbilitySub> ws55Rest = new java.util.ArrayList<>();
                java.util.List<String> ws55Labels = new java.util.ArrayList<>();
                if (ws55Chosen.size() >= min) ws55Labels.add("WS48:MODE:DONE");
                for (AbilitySub o : possible) {
                    if (!allowRepeat && ws55Chosen.contains(o)) continue;
                    ws55Rest.add(o);
                    ws55Labels.add("WS48:MODE:api=" + ws48Enc(String.valueOf(o.getApi()))
                        + ":desc=" + ws48Enc(ws48Clip(o.getDescription(), 200)));
                }
                if (ws55Rest.isEmpty()) break;
                int ws55Offset = (ws55Chosen.size() >= min) ? 1 : 0;
                int ws55Idx = ws48Choose("choose_mode", this.player, ws55Labels);
                if (ws55Offset == 1 && ws55Idx == 0) break;
                AbilitySub ws55Pick = ws55Rest.get(ws55Idx - ws55Offset);
                if (!allowRepeat && ws55Chosen.contains(ws55Pick)) throw failClosed("WS55_MODE_REPEAT_FORBIDDEN");
                ws55Chosen.add(ws55Pick);
            }
            if (ws55Chosen.size() < min || ws55Chosen.size() > num) throw failClosed("chooseModeForAbility:BOUNDS");
            return new java.util.ArrayList<>(ws55Chosen);"""

# ---------------------------------------------------------------- J5: trigger N
TRIGGER_N_OLD = """            if (activePlayerSAs.size() != 2) throw failClosed("orderSimultaneousSa:MORE_THAN_TWO");
            java.util.List<String> identities = new java.util.ArrayList<>();
            for (SpellAbility o : activePlayerSAs) {
                identities.add(ws48CardName(o.getHostCard()) + ":" + ws48Clip(String.valueOf(o), 120));
            }
            java.util.List<String> labels = java.util.List.of(
                "WS48:ORDER:order=0,1:first=" + ws48Enc(identities.get(0)) + ":second=" + ws48Enc(identities.get(1)),
                "WS48:ORDER:order=1,0:first=" + ws48Enc(identities.get(1)) + ":second=" + ws48Enc(identities.get(0)));
            int idx = ws48Choose("trigger_order", this.player, labels);
            if (idx == 0) return java.util.List.of(activePlayerSAs.get(0), activePlayerSAs.get(1));
            return java.util.List.of(activePlayerSAs.get(1), activePlayerSAs.get(0));"""

TRIGGER_N_NEW = """            if (activePlayerSAs.size() == 2) {
                java.util.List<String> identities = new java.util.ArrayList<>();
                java.util.List<String> hidIds = new java.util.ArrayList<>();
                for (SpellAbility o : activePlayerSAs) {
                    identities.add(ws48CardName(o.getHostCard()) + ":" + ws48Clip(String.valueOf(o), 120));
                    hidIds.add(ws48CardRef(o.getHostCard()));
                }
                java.util.List<String> labels = java.util.List.of(
                    "WS48:ORDER:order=0,1:first=" + ws48Enc(identities.get(0)) + ":hidfirst=" + ws48Enc(hidIds.get(0)) + ":second=" + ws48Enc(identities.get(1)) + ":hidsecond=" + ws48Enc(hidIds.get(1)),
                    "WS48:ORDER:order=1,0:first=" + ws48Enc(identities.get(1)) + ":hidfirst=" + ws48Enc(hidIds.get(1)) + ":second=" + ws48Enc(identities.get(0)) + ":hidsecond=" + ws48Enc(hidIds.get(0)));
                int idx = ws48Choose("trigger_order", this.player, labels);
                if (idx == 0) return java.util.List.of(activePlayerSAs.get(0), activePlayerSAs.get(1));
                return java.util.List.of(activePlayerSAs.get(1), activePlayerSAs.get(0));
            }
            if (activePlayerSAs.size() > 5) throw failClosed("orderSimultaneousSa:PERMUTATION_BOUND:" + activePlayerSAs.size());
            ws48Milestone("orderSimultaneousSa:N:" + activePlayerSAs.size());
            java.util.List<java.util.List<Integer>> ws55Perms = ws55Permutations(activePlayerSAs.size());
            java.util.List<String> ws55Labels = new java.util.ArrayList<>();
            for (java.util.List<Integer> perm : ws55Perms) {
                StringBuilder ws55Sb = new StringBuilder("WS48:ORDER:order=");
                for (int k = 0; k < perm.size(); k++) {
                    if (k > 0) ws55Sb.append(',');
                    ws55Sb.append(perm.get(k));
                }
                for (int k = 0; k < perm.size(); k++) {
                    SpellAbility o = activePlayerSAs.get(perm.get(k));
                    ws55Sb.append(":m").append(k).append('=')
                        .append(ws48Enc(ws48CardName(o.getHostCard()) + ":" + ws48Clip(String.valueOf(o), 120)))
                        .append(":h").append(k).append('=')
                        .append(ws48Enc(ws48CardRef(o.getHostCard())));
                }
                ws55Labels.add(ws55Sb.toString());
            }
            java.util.List<Integer> ws55Pick = ws55Perms.get(ws48Choose("trigger_order", this.player, ws55Labels));
            java.util.List<SpellAbility> ws55Out = new java.util.ArrayList<>();
            boolean[] ws55Seen = new boolean[activePlayerSAs.size()];
            for (int i : ws55Pick) {
                if (i < 0 || i >= activePlayerSAs.size() || ws55Seen[i]) throw failClosed("WS55_TRIGGER_BAD_PERMUTATION");
                ws55Seen[i] = true;
                ws55Out.add(activePlayerSAs.get(i));
            }
            return ws55Out;"""

# ---------------------------------------------------------------- J6: deck env
DECK_OLD = """        forge.card.CardRules finalistMountainRules = finalistReader.attemptToLoadCard("Mountain");
        forge.card.CardRules finalistCommanderRules = finalistReader.attemptToLoadCard("Rograkh, Son of Rohgahh");
        if (finalistMountainRules == null || finalistCommanderRules == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_RULES_MISSING");
        for (int i = 1; i <= requestedPlayers; i++) {
            Deck deck = new Deck("FINALIST-SEAT-" + i);
            PaperCard mountain = new PaperCard(finalistMountainRules, "10E", forge.card.CardRarity.BasicLand);
            PaperCard commander = new PaperCard(finalistCommanderRules, "CMR", forge.card.CardRarity.Uncommon);
            deck.getMain().add(mountain, 99);
            deck.getOrCreate(forge.deck.DeckSection.Commander).add(commander, 1);"""

DECK_NEW = """        String ws55DeckMain = System.getenv("COMMANDER_LAB_FORGE_DECK_MAIN");
        String ws55DeckCommander = System.getenv("COMMANDER_LAB_FORGE_DECK_COMMANDER");
        boolean ws55CustomDeck = ws55DeckMain != null && !ws55DeckMain.isBlank()
            && ws55DeckCommander != null && !ws55DeckCommander.isBlank();
        java.util.List<forge.item.PaperCard> ws55MainCards = new java.util.ArrayList<>();
        forge.item.PaperCard ws55CommanderCard = null;
        forge.card.CardRules finalistMountainRules = null;
        forge.card.CardRules finalistCommanderRules = null;
        if (ws55CustomDeck) {
            for (String ws55Entry : ws55DeckMain.split(",")) {
                String[] ws55Kv = ws55Entry.trim().split("[*]", 2);
                if (ws55Kv.length != 2) throw new ControlledStop("WS55_DECK_SPEC_MALFORMED:" + ws55Entry);
                // Prefer a real native print from the loaded CardDb; fall back
                // to the native UNKNOWN-print precedent (CardDb: unassigned
                // cards get PaperCard(cr, UNKNOWN_CODE, Special)).
                forge.item.PaperCard ws55Pc = null;
                try {
                    java.util.List<forge.item.PaperCard> ws55Prints =
                        forge.StaticData.instance().getCommonCards().getAllCards(ws55Kv[0].trim());
                    if (ws55Prints != null && !ws55Prints.isEmpty()) ws55Pc = ws55Prints.get(0);
                } catch (Throwable ws55t) {
                    ws55Pc = null;
                }
                if (ws55Pc == null) {
                    forge.card.CardRules ws55Rules = finalistReader.attemptToLoadCard(ws55Kv[0].trim());
                    if (ws55Rules == null) throw new ControlledStop("WS55_DECK_CARD_MISSING:" + ws55Kv[0].trim());
                    ws55Pc = new forge.item.PaperCard(
                        ws55Rules, forge.card.CardEdition.UNKNOWN_CODE, forge.card.CardRarity.Special);
                }
                int ws55Count;
                try {
                    ws55Count = Integer.parseInt(ws55Kv[1].trim());
                } catch (NumberFormatException ws55n) {
                    throw new ControlledStop("WS55_DECK_COUNT_MALFORMED:" + ws55Entry);
                }
                if (ws55Count < 1 || ws55Count > 99) throw new ControlledStop("WS55_DECK_COUNT_OUT_OF_RANGE:" + ws55Entry);
                for (int ws55k = 0; ws55k < ws55Count; ws55k++) ws55MainCards.add(ws55Pc);
            }
            try {
                java.util.List<forge.item.PaperCard> ws55CmdPrints =
                    forge.StaticData.instance().getCommonCards().getAllCards(ws55DeckCommander.trim());
                if (ws55CmdPrints != null && !ws55CmdPrints.isEmpty())
                    ws55CommanderCard = ws55CmdPrints.get(0);
            } catch (Throwable ws55t) {
                ws55CommanderCard = null;
            }
            if (ws55CommanderCard == null) {
                try {
                    forge.card.CardRules ws55CmdRules =
                        finalistReader.attemptToLoadCard(ws55DeckCommander.trim());
                    if (ws55CmdRules != null) ws55CommanderCard = new forge.item.PaperCard(
                        ws55CmdRules, forge.card.CardEdition.UNKNOWN_CODE, forge.card.CardRarity.Special);
                } catch (Throwable ws55t) {
                    ws55CommanderCard = null;
                }
            }
            if (ws55CommanderCard == null) throw new ControlledStop("WS55_DECK_COMMANDER_MISSING:" + ws55DeckCommander);
        } else {
            finalistMountainRules = finalistReader.attemptToLoadCard("Mountain");
            finalistCommanderRules = finalistReader.attemptToLoadCard("Rograkh, Son of Rohgahh");
            if (finalistMountainRules == null || finalistCommanderRules == null) throw new ControlledStop("FINALIST_CANONICAL_DECK_RULES_MISSING");
        }
        for (int i = 1; i <= requestedPlayers; i++) {
            Deck deck = new Deck("FINALIST-SEAT-" + i);
            if (ws55CustomDeck) {
                for (forge.item.PaperCard ws55Pc : ws55MainCards) deck.getMain().add(ws55Pc);
                deck.getOrCreate(forge.deck.DeckSection.Commander).add(ws55CommanderCard);
            } else {
            PaperCard mountain = new PaperCard(finalistMountainRules, "10E", forge.card.CardRarity.BasicLand);
            PaperCard commander = new PaperCard(finalistCommanderRules, "CMR", forge.card.CardRarity.Uncommon);
            deck.getMain().add(mountain, 99);
            deck.getOrCreate(forge.deck.DeckSection.Commander).add(commander, 1);
            }"""

# ---------------------------------------------------------------- J7: order-combatants config
ORDER_COMBATANTS_OLD = """        GameRules rules = new GameRules(GameType.Constructed);
        rules.addAppliedVariant(GameType.Commander);"""

ORDER_COMBATANTS_NEW = """        GameRules rules = new GameRules(GameType.Constructed);
        rules.addAppliedVariant(GameType.Commander);
        String ws55OrderCombatants = System.getenv("COMMANDER_LAB_FORGE_ORDER_COMBATANTS");
        if ("1".equals(ws55OrderCombatants)) {
            rules.setOrderCombatants(true);
        }"""

# ---------------------------------------------------------------- J8: ranged ints
BROKER_RANGED_ANCHOR = """        boolean chooseBoolean(String kind, Player actor, String trueLabel, String falseLabel) {"""

BROKER_RANGED_ADD = """        int chooseRanged(String kind, Player actor, int min, int max, String announce) {
            long seq = ++decisionSeq;
            String did = "d" + seq;
            String label = "WS55:NUMRANGE:min=" + min + ":max=" + max
                + ":announce=" + ws48Enc(announce == null ? "" : announce);
            String ws55obs = "[]";
            String ws55state = "null";
            try {
                Game ws55game = actor.getGame();
                if (ws55game != null) {
                    ws55obs = ws50AllObservations(ws55game);
                    ws55state = sessionSnapshot(ws55game);
                }
            } catch (Throwable ws55t) {
                ws55obs = "[{\\"viewer\\":\\"PX\\",\\"fingerprint\\":\\"UNAVAILABLE\\",\\"view\\":\\"\\"}]";
            }
            java.util.List<String> ws55one = java.util.List.of(label);
            out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"DECISION_FRAME\\""
                + ",\\"request_id\\":" + esc(did)
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"actor_id\\":" + esc(actor.getName())
                + ",\\"state_revision\\":" + revision
                + ",\\"payload\\":{\\"decision_id\\":" + esc(did)
                + ",\\"decision_kind\\":" + esc(kind)
                + ",\\"frame_seq\\":" + seq
                + ",\\"cancel_offered\\":" + ws50CancelOffered(ws55one)
                + ",\\"rng\\":" + ws50RngIdentity()
                + ",\\"state_snapshot\\":" + esc(ws55state)
                + ",\\"state_fingerprint\\":" + esc(ws50Sha(ws55state))
                + ",\\"observations\\":" + ws55obs
                + ",\\"options_digest\\":" + esc(digest(java.util.List.of("o0")))
                + ",\\"options\\":[{\\"option_id\\":\\"o0\\",\\"kind\\":" + esc(label) + "}]}}");
            out.flush();
            try {
                String answer = in.readLine();
                if (answer == null) throw new ControlledStop("WS55_EXTERNAL_EOF:" + kind);
                if (!"SUBMIT_DECISION".equals(field(answer, "message_type"))) {
                    throw new ControlledStop("WS23_EXPECTED_SUBMIT_DECISION");
                }
                if (!did.equals(field(answer, "decision_id"))) {
                    throw new ControlledStop("WS23_STALE_OR_WRONG_DECISION_ID");
                }
                if (!"o0".equals(field(answer, "option_id"))) {
                    throw new ControlledStop("WS23_OPTION_NOT_OFFERED");
                }
                String vstr = field(answer, "value");
                if (vstr == null) throw new ControlledStop("WS55_RANGED_VALUE_MISSING");
                int v;
                try {
                    v = Integer.parseInt(vstr.trim());
                } catch (Exception e) {
                    throw new ControlledStop("WS55_RANGED_VALUE_MALFORMED");
                }
                if (v < min || v > max) throw new ControlledStop("WS55_RANGED_VALUE_OUT_OF_RANGE");
                revision++;
                return v;
            } catch (java.io.IOException e) {
                throw new RuntimeException(e);
            }
        }

""" + BROKER_RANGED_ANCHOR

ANNOUNCE_RANGED_OLD = """            if ((long) max - (long) min > 64) throw failClosed("announceRequirements:RANGE_TOO_WIDE");"""

ANNOUNCE_RANGED_NEW = """            if ((long) max - (long) min > 64) {
                ws48Milestone("announceRequirements:RANGED");
                return broker.chooseRanged("announce_x", this.player, min, max, announce);
            }"""

NUMBER_RANGED_OLD = """            if ((long) max - (long) min > 64) throw failClosed("chooseNumber:RANGE_TOO_WIDE");"""

NUMBER_RANGED_NEW = """            if ((long) max - (long) min > 64) {
                ws48Milestone("chooseNumber:RANGED");
                return broker.chooseRanged("announce_x", this.player, min, max, title);
            }"""

# ---------------------------------------------------------------- J9: trigger confirm/exec
CONFIRM_TRIGGER_OLD = """        public boolean confirmTrigger(WrappedAbility sa) {
            throw failClosed("confirmTrigger");
        }"""

PLAY_TRIGGER_OLD = """        public boolean playTrigger(Card host, WrappedAbility wrapperAbility, boolean isMandatory) {
            throw failClosed("playTrigger");
        }"""

PLAY_SA_OLD = """        public boolean playSaFromPlayEffect(SpellAbility tgtSA) {
            throw failClosed("playSaFromPlayEffect");
        }"""

CONFIRM_TRIGGER_NEW = """        @Override
        public boolean confirmTrigger(WrappedAbility sa) {
            ws48Milestone("confirmTrigger:ENTERED");
            if (sa == null || sa.getWrappedAbility() == null) throw failClosed("confirmTrigger:NULL");
            SpellAbility inner = sa.getWrappedAbility();
            if (inner.hasParam("Cost") && !inner.getParam("Cost").equals("0")) {
                broker.recordAutomatic("confirmTrigger:COST_TRIGGER_NATIVE_TRUE");
                return true;
            }
            String host = sa.getHostCard() == null ? "null" : ws48CardRef(sa.getHostCard());
            String trig = ws48Clip(String.valueOf(sa.getTrigger()), 200);
            return "o0".equals(broker.choose("confirm", player, java.util.List.of(
                "WS48:CONFIRM:opt=YES:host=" + ws48Enc(host) + ":trig=" + ws48Enc(trig),
                "WS48:CONFIRM:opt=NO:host=" + ws48Enc(host) + ":trig=" + ws48Enc(trig))));
        }"""

PLAY_TRIGGER_NEW = """        @Override
        public boolean playTrigger(Card host, WrappedAbility wrapperAbility, boolean isMandatory) {
            ws48Milestone("playTrigger:ENTERED");
            return PlaySpellAbility.playSpellAbilityNoStack(this, player, wrapperAbility, false);
        }"""

PLAY_SA_NEW = """        @Override
        public boolean playSaFromPlayEffect(SpellAbility tgtSA) {
            ws48Milestone("playSaFromPlayEffect:ENTERED");
            return PlaySpellAbility.playSpellAbility(this, player, tgtSA);
        }"""

# ---------------------------------------------------------------- J11: zone-move ordering
ZONE_ORDER_OLD = """        public CardCollectionView orderMoveToZoneList(CardCollectionView cards, ZoneType destinationZone, SpellAbility source) {
            throw failClosed("orderMoveToZoneList");
        }"""

ZONE_ORDER_NEW = """        @Override
        public CardCollectionView orderMoveToZoneList(CardCollectionView cards, ZoneType destinationZone, SpellAbility source) {
            ws48Milestone("orderMoveToZoneList:ENTERED");
            if (cards == null) throw failClosed("orderMoveToZoneList:NULL");
            java.util.List<Card> nativeOrder = new java.util.ArrayList<>();
            for (Card c : cards) nativeOrder.add(c);
            if (nativeOrder.size() <= 1) {
                broker.recordAutomatic("orderMoveToZoneList:ZERO_OR_ONE");
                return cards;
            }
            if (nativeOrder.size() > 24) throw failClosed("orderMoveToZoneList:FRAME_BOUND:" + nativeOrder.size());
            java.util.List<Card> built = new java.util.ArrayList<>();
            for (Card c : nativeOrder) {
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (int pos = 0; pos <= built.size(); pos++) {
                    labels.add("WS55:ZONEORDER:card=" + ws48Enc(ws48CardRef(c))
                        + ":pos=" + pos + ":of=" + built.size()
                        + ":dest=" + ws48Enc(String.valueOf(destinationZone)));
                }
                int pos = ws48Choose("order_zone", this.player, labels);
                if (pos < 0 || pos > built.size()) throw failClosed("WS55_ZONEORDER_STALE");
                built.add(pos, c);
            }
            CardCollection out = new CardCollection();
            for (Card c : built) out.add(c);
            if (out.size() != nativeOrder.size()) throw failClosed("WS55_ZONEORDER_SIZE");
            return out;
        }"""

# ---------------------------------------------------------------- J10: replacement call audit
REPL_AUDIT_OLD = """        public ReplacementEffect chooseSingleReplacementEffect(List<ReplacementEffect> possibleReplacers) {
            if (possibleReplacers == null || possibleReplacers.isEmpty())
                throw failClosed("chooseSingleReplacementEffect:EMPTY");"""

REPL_AUDIT_NEW = """        public ReplacementEffect chooseSingleReplacementEffect(List<ReplacementEffect> possibleReplacers) {
            ws48Milestone("chooseSingleReplacementEffect:CALLED:n=" + (possibleReplacers == null ? -1 : possibleReplacers.size()));
            if (possibleReplacers == null || possibleReplacers.isEmpty())
                throw failClosed("chooseSingleReplacementEffect:EMPTY");"""

# ---------------------------------------------------------------- static helper
STATIC_ANCHOR = "    static String ws48Enc(String v) {"

STATIC_ADD = """    static java.util.List<java.util.List<Integer>> ws55Permutations(int n) {
            java.util.List<java.util.List<Integer>> out = new java.util.ArrayList<>();
            int[] idx = new int[n];
            for (int i = 0; i < n; i++) idx[i] = i;
            ws55PermuteInto(idx, 0, out);
            return out;
        }

        static void ws55PermuteInto(int[] idx, int from, java.util.List<java.util.List<Integer>> out) {
            if (from == idx.length) {
                java.util.List<Integer> one = new java.util.ArrayList<>(idx.length);
                for (int v : idx) one.add(v);
                out.add(one);
                return;
            }
            for (int i = from; i < idx.length; i++) {
                int t = idx[from];
                idx[from] = idx[i];
                idx[i] = t;
                ws55PermuteInto(idx, from + 1, out);
                t = idx[from];
                idx[from] = idx[i];
                idx[i] = t;
            }
        }

""" + STATIC_ANCHOR


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    # Prereqs: converged WS53 provider (repaired WS48 overlay + WS53 overlay).
    for marker in ("WS48:ATTACK:attacker=", "ws50AllObservations",
                   "chooseCardsToDiscardToMaximumHandSize:ENTERED",
                   "chooseCombatDamage", "AmountDistributionSelection"):
        if marker not in p:
            raise SystemExit(f"WS55_OVERLAY_PREREQ_MISSING:{marker}")
    # WS53 Repair-01 supersession guard (same defense-in-depth as WS53).
    if "nativeOptions.add(sa);\n                            nativeOptions.add(sa);" in p:
        raise SystemExit("WS55_OVERLAY_REPAIR01_RESURRECTED")
    p = once(p, OPTIONAL_COSTS_OLD, OPTIONAL_COSTS_NEW, "chooseOptionalCosts")
    p = once(p, ORDER_COSTS_OLD, ORDER_COSTS_NEW, "orderCosts")
    p = once(p, ORDER_BLOCKERS_OLD, ORDER_BLOCKERS_NEW, "combat ordering trio")
    p = once(p, MODE_MULTI_OLD, MODE_MULTI_NEW, "multi-mode sequential")
    p = once(p, TRIGGER_N_OLD, TRIGGER_N_NEW, "trigger order N")
    p = once(p, DECK_OLD, DECK_NEW, "deck env generalization")
    p = once(p, ORDER_COMBATANTS_OLD, ORDER_COMBATANTS_NEW, "order combatants config")
    p = once(p, BROKER_RANGED_ANCHOR, BROKER_RANGED_ADD, "ranged broker method")
    p = once(p, ANNOUNCE_RANGED_OLD, ANNOUNCE_RANGED_NEW, "ranged announce")
    p = once(p, NUMBER_RANGED_OLD, NUMBER_RANGED_NEW, "ranged chooseNumber")
    p = once(p, CONFIRM_TRIGGER_OLD, CONFIRM_TRIGGER_NEW, "trigger confirm")
    p = once(p, PLAY_TRIGGER_OLD, PLAY_TRIGGER_NEW, "playTrigger mirror")
    p = once(p, PLAY_SA_OLD, PLAY_SA_NEW, "playSaFromPlayEffect mirror")
    p = once(p, REPL_AUDIT_OLD, REPL_AUDIT_NEW, "replacement call audit")
    p = once(p, ZONE_ORDER_OLD, ZONE_ORDER_NEW, "zone-move ordering")
    p = once(p, STATIC_ANCHOR, STATIC_ADD, "permutation helper")
    # Collapse doubled @Override from annotation-including replacements.
    while "        @Override\n        @Override\n" in p:
        p = p.replace("        @Override\n        @Override\n", "        @Override\n")
    args.provider.write_text(p, encoding="utf-8")
    required = ["WS55:OPTCOST:desc=", "WS55:COSTORDER:order=", "WS55:ORDERBLOCKERS:attacker=",
                "WS55:ORDERBLOCKER:attacker=", "WS55:ORDERATTACKERS:blocker=",
                "chooseModeForAbility:MULTI", "orderSimultaneousSa:N:",
                "COMMANDER_LAB_FORGE_DECK_MAIN", "ws55Permutations",
                "COMMANDER_LAB_FORGE_ORDER_COMBATANTS",
                "WS55:NUMRANGE:min=", "chooseRanged(",
                "WS55_RANGED_VALUE_OUT_OF_RANGE",
                "chooseSingleReplacementEffect:CALLED:n=",
                "WS55:ZONEORDER:card=",
                "orderMoveToZoneList:ENTERED",
                "orderCosts:NATIVE_AUTO", "orderBlockers:SINGLETON",
                "FULL_CONTROL_MIRROR" if False else "ChooseCostOrder"]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS55_OVERLAY_INCOMPLETE:{missing}")
    for gap in ("throw failClosed(\"chooseOptionalCosts\");",
                "throw failClosed(\"orderCosts\");",
                "throw failClosed(\"orderBlockers\");",
                "throw failClosed(\"orderBlocker\");",
                "throw failClosed(\"orderMoveToZoneList\");",
                "throw failClosed(\"orderAttackers\");",
                "throw failClosed(\"confirmTrigger\");",
                "throw failClosed(\"playTrigger\");",
                "throw failClosed(\"playSaFromPlayEffect\");",
                "RANGE_TOO_WIDE",
                "DEPENDENT_MULTI_CHOICE", "MORE_THAN_TWO"):
        if gap in p:
            raise SystemExit(f"WS55_OVERLAY_GAP_REMAINS:{gap}")
    print("WS55_DECISION_BREADTH_PROVIDER_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())

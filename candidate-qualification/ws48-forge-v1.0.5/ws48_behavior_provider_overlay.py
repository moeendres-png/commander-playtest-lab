#!/usr/bin/env python3
"""WS48 behavior provider overlay v1 (WS48-owned, qualification-only).

Patches ONLY the ephemeral generated GPL-side provider
(Ws23ForgeVerticalProvider.java) plus a minimal semantic accessor on the
ephemeral Ws40SuccessorState.java copy. Never touches pinned Forge source,
shared scripts, or another workstream's files.

Rules-Core authority is preserved: every discretionary branch enumerates ONLY
Forge-native options (getAllPossibleAbilities, TargetRestrictions candidates
filtered by SpellAbility.canTarget, CombatUtil legality, native mode/number/
color/cost surfaces). The overlay only projects stable semantic identities
(seat pids, requested semantic ids, native card names, literal ints/colors)
onto already-authorized options and returns the harness-selected OPAQUE
option id. Zero-option and ambiguous cases fail closed. Single-option
mandatory cases resolve automatically with an audit record (no discretion).

Label grammar: WS48:<kind>:<k>=<urlencoded>:...  (harness decodes values)
Kinds: PASS, ACT, TARGET, TARGETPAIR, OPT, MODE, NUM, COLOR, BOOL, CONFIRM,
       REPL, ORDER, MANA, ATTACK, BLOCK, SCRY, PILE, EVENT, MILESTONE.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS48_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


STATE_ACCESSOR_ANCHOR = "    private static String semanticOf(Card c) {"
STATE_ACCESSOR_ADD = """    public static String ws48SemanticOf(Card c) { return semanticOf(c); }

    public static String ws48CommanderOf(Card c) {
        for (Map.Entry<String, Card> e : commanderCards.entrySet()) if (e.getValue() == c) return e.getKey();
        return null;
    }

    public static String ws48SemanticOfSpell(SpellAbility sa) {
        if (sa == null || sa.getHostCard() == null) return null;
        return ws48SemanticOf(sa.getHostCard());
    }

    // WS48-PROVISIONAL (coordinator review pending): complete AttackingBand
    // blocked flags for loader-injected combat. Live Forge finalizes these in
    // Combat.fireTriggersForUnblockedAttackers after the declare-blockers
    // turn-based action; injected combat bypasses that pipeline, leaving null
    // flags that NPE Combat.assignAttackersDamage. This mirrors the engine's
    // flag computation WITHOUT firing triggers (trigger firing remains the
    // engine's job when the declare step runs). Snapshot-neutral: no emitted
    // combat snapshot field carries band flags (attackers/blockers/eligible
    // only), so construction/readback normalization equality is preserved.
    // Behavior-workflow only; shared sources untouched.
    public static void ws48FinalizeLoadedCombatBands(Game game) {
        forge.game.combat.Combat combat = game.getCombat();
        if (combat == null) return;
        for (forge.game.combat.AttackingBand band : combat.getAttackingBands()) {
            band.setBlocked(!combat.getBlockers(band).isEmpty());
        }
    }
"""

HELPERS_ANCHOR = "        RuntimeException failClosed(String method) {"
HELPERS_ADD = """        String ws48Pid(Player p) {
            int i = getGame().getPlayers().indexOf(p);
            if (i < 0) throw failClosed("ws48Pid:UNBOUND:" + p);
            return "P" + (i + 1);
        }

        String ws48EntityRef(GameEntity e) {
            if (e instanceof Player p) return "WS48:player:" + ws48Pid(p) + ":" + p.getName();
            if (e instanceof Card c) return ws48CardRef(c);
            return "WS48:entity:" + String.valueOf(e);
        }

        int ws48Choose(String kind, Player actor, java.util.List<String> labels) {
            String id = broker.choose(kind, actor, labels);
            int idx = Integer.parseInt(id.substring(1));
            if (idx < 0 || idx >= labels.size()) throw failClosed(kind + ":STALE_OPTION");
            return idx;
        }

        void ws48Milestone(String name) {
            // Diagnostic NATIVE_EVENT milestone: proves control reached this
            // provider point. Content-free by design (no game facts).
            broker.out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"NATIVE_EVENT\\""
                + ",\\"request_id\\":\\"ws48-milestone\\""
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"payload\\":{\\"event\\":" + esc("milestone:" + name)
                + ",\\"facts\\":\\"\\"}}");
            broker.out.flush();
        }

        RuntimeException failClosed(String method) {"""

PRIORITY_LABEL_ANCHOR = '                            labels.add("FORGE_LEGAL_ACTION");'
PRIORITY_LABEL_NEW = """                            nativeOptions.add(sa);
                            String ws48Host = Ws40SuccessorState.ws48SemanticOf(sa.getHostCard());
                            String ws48Cmd = Ws40SuccessorState.ws48CommanderOf(sa.getHostCard());
                            labels.add("WS48:ACT:host=" + ws48Enc(ws48Host == null ? ("MINTED-" + sa.getHostCard().getId()) : ws48Host)
                                + ":cmd=" + ws48Enc(String.valueOf(ws48Cmd))
                                + ":card=" + ws48Enc(ws48CardName(sa.getHostCard()))
                                + ":sa=" + ws48Enc(ws48Clip(String.valueOf(sa), 160)));"""

PROVIDER_STATIC_ANCHOR = "    static String esc(String s) {"
PROVIDER_STATIC_ADD = """    static String ws48Enc(String v) {
            try { return java.net.URLEncoder.encode(String.valueOf(v), java.nio.charset.StandardCharsets.UTF_8); }
            catch (Exception e) { throw new RuntimeException(e); }
        }

        static String ws48Clip(String v, int n) {
            String s = String.valueOf(v).replace('|', '/').replace('\\n', ' ').replace('\\r', ' ');
            return s.length() <= n ? s : s.substring(0, n);
        }

        static String ws48CardName(Card c) {
            if (c == null) return "null";
            return c.getPaperCard() == null ? c.getName() : c.getPaperCard().getName();
        }

        static String ws48CardRef(Card c) {
            if (c == null) return "WS48:null:null";
            String sid = Ws40SuccessorState.ws48SemanticOf(c);
            String id = sid == null ? ("MINTED-" + c.getId()) : sid;
            return "WS48:" + id + ":" + ws48CardName(c);
        }

        static String ws48StaticPid(Game game, Player p) {
            int i = game.getPlayers().indexOf(p);
            return i < 0 ? "PX" : ("P" + (i + 1));
        }

        static void ws48FinalizeDeclaredBands(Combat combat) {
            if (combat == null) return;
            for (forge.game.combat.AttackingBand band : combat.getAttackingBands()) {
                band.setBlocked(!combat.getBlockers(band).isEmpty());
            }
        }

""" + PROVIDER_STATIC_ANCHOR

ABILITY_TO_PLAY_NEW = """        @Override
        public SpellAbility getAbilityToPlay(Card hostCard, List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
            if (abilities == null || abilities.isEmpty()) throw failClosed("getAbilityToPlay:EMPTY");
            if (abilities.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:getAbilityToPlay");
                return abilities.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (SpellAbility o : abilities) {
                labels.add("WS48:ABILITY:host=" + ws48Enc(ws48CardRef(hostCard))
                    + ":sa=" + ws48Enc(ws48Clip(String.valueOf(o), 200)));
            }
            return abilities.get(ws48Choose("choose_ability", this.player, labels));
        }"""

TARGETS_FOR_NEW = """        @Override
        public boolean chooseTargetsFor(SpellAbility currentAbility) {
            TargetRestrictions restrictions = currentAbility.getTargetRestrictions();
            if (restrictions == null) {
                broker.recordAutomatic("chooseTargetsFor:NO_RESTRICTIONS");
                return true;
            }
            int guard = 0;
            while (true) {
                if (++guard > 32) throw failClosed("chooseTargetsFor:GUARD");
                if (currentAbility.getTargets().size() >= currentAbility.getMaxTargets()) return true;
                java.util.List<GameEntity> cands = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (GameEntity cand : restrictions.getAllCandidates(currentAbility)) {
                    if (!(cand instanceof GameObject)) continue;
                    if (!currentAbility.canTarget((GameObject) cand)) continue;
                    if (currentAbility.getTargets().contains(cand)) continue;
                    cands.add(cand);
                    labels.add("WS48:TARGET:tgt=" + ws48Enc(ws48EntityRef(cand)));
                }
                if (cands.isEmpty()) return currentAbility.getTargets().size() >= currentAbility.getMinTargets();
                if (currentAbility.getTargets().size() >= currentAbility.getMinTargets()) {
                    labels.add("WS48:TARGET:DONE");
                }
                int idx = ws48Choose("target", this.player, labels);
                if (idx == labels.size() - 1 && currentAbility.getTargets().size() >= currentAbility.getMinTargets()
                        && labels.get(idx).equals("WS48:TARGET:DONE")) {
                    return true;
                }
                if (!currentAbility.getTargets().add(cands.get(idx))) throw failClosed("chooseTargetsFor:ADD_REJECTED");
            }
        }"""

TARGET_NEW = """        @Override
        public Pair<SpellAbilityStackInstance, GameObject> chooseTarget(SpellAbility sa, List<Pair<SpellAbilityStackInstance, GameObject>> allTargets) {
            if (allTargets == null || allTargets.isEmpty()) throw failClosed("chooseTarget:EMPTY");
            if (allTargets.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseTarget");
                return allTargets.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (Pair<SpellAbilityStackInstance, GameObject> t : allTargets) {
                GameObject go = t.getRight();
                String ref = (go instanceof GameEntity ge) ? ws48EntityRef(ge) : ("WS48:object:" + String.valueOf(go));
                labels.add("WS48:TARGETPAIR:tgt=" + ws48Enc(ref));
            }
            return allTargets.get(ws48Choose("target", this.player, labels));
        }"""

ENTITY_GENERIC_NEW = """        @Override
        public <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal, SpellAbility sa, String title, boolean isOptional, Player relatedPlayer, Map<String, Object> params) {
            java.util.List<T> opts = new java.util.ArrayList<>();
            for (T o : optionList) opts.add(o);
            if (!isOptional) {
                if (opts.isEmpty()) throw new ControlledStop("FINALIST_ZERO_NATIVE_OPTIONS:chooseSingleEntityForEffect");
                if (opts.size() == 1) {
                    broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseSingleEntityForEffect");
                    return opts.get(0);
                }
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            if (isOptional) labels.add("WS48:OPT:NONE");
            for (T o : opts) labels.add("WS48:OPT:opt=" + ws48Enc(ws48EntityRef(o)));
            int idx = ws48Choose("choose_object", this.player, labels);
            if (isOptional) {
                if (idx == 0) return null;
                idx--;
            }
            return opts.get(idx);
        }

        @Override
        public <T extends GameEntity> List<T> chooseEntitiesForEffect(FCollectionView<T> optionList, int min, int max, DelayedReveal delayedReveal, SpellAbility sa, String title, Player relatedPlayer, Map<String, Object> params) {
            java.util.List<T> opts = new java.util.ArrayList<>();
            for (T o : optionList) opts.add(o);
            java.util.List<T> chosen = new java.util.ArrayList<>();
            int guard = 0;
            while (true) {
                if (++guard > 32) throw failClosed("chooseEntitiesForEffect:GUARD");
                if (chosen.size() >= max) break;
                java.util.List<T> rest = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (T o : opts) {
                    if (chosen.contains(o)) continue;
                    rest.add(o);
                    labels.add("WS48:OPT:opt=" + ws48Enc(ws48EntityRef(o)));
                }
                if (rest.isEmpty()) break;
                if (chosen.size() >= min) labels.add("WS48:OPT:DONE");
                int idx = ws48Choose("choose_object", this.player, labels);
                if (chosen.size() >= min && idx == labels.size() - 1 && labels.get(idx).equals("WS48:OPT:DONE")) break;
                chosen.add(rest.get(idx));
            }
            if (chosen.size() < min) throw failClosed("chooseEntitiesForEffect:UNDER_MIN");
            return chosen;
        }"""

CARDS_FOR_EFFECT_NEW = """        @Override
        public CardCollectionView chooseCardsForEffect(CardCollectionView sourceList, SpellAbility sa, String title, int min, int max, boolean isOptional, Map<String, Object> params) {
            java.util.List<Card> opts = new java.util.ArrayList<>();
            for (Card o : sourceList) opts.add(o);
            CardCollection chosen = new CardCollection();
            int guard = 0;
            while (true) {
                if (++guard > 64) throw failClosed("chooseCardsForEffect:GUARD");
                if (chosen.size() >= max) break;
                java.util.List<Card> rest = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                if (isOptional && chosen.isEmpty()) labels.add("WS48:OPT:NONE");
                for (Card o : opts) {
                    if (chosen.contains(o)) continue;
                    rest.add(o);
                    labels.add("WS48:OPT:opt=" + ws48Enc(ws48CardRef(o)));
                }
                if (rest.isEmpty()) break;
                if (!chosen.isEmpty() && chosen.size() >= min) labels.add("WS48:OPT:DONE");
                int offset = (isOptional && chosen.isEmpty()) ? 1 : 0;
                int idx = ws48Choose("choose_object", this.player, labels);
                if (isOptional && chosen.isEmpty() && idx == 0) return new CardCollection();
                if (!chosen.isEmpty() && chosen.size() >= min && idx == labels.size() - 1
                        && labels.get(idx).equals("WS48:OPT:DONE")) break;
                chosen.add(rest.get(idx - offset));
            }
            if (chosen.size() < min) throw failClosed("chooseCardsForEffect:UNDER_MIN");
            return chosen;
        }"""

SPELLS_ABILITIES_NEW = """        @Override
        public List<SpellAbility> chooseSpellAbilitiesForEffect(List<SpellAbility> spells, SpellAbility sa, String title, int num, Map<String, Object> params) {
            if (spells == null || spells.isEmpty()) throw failClosed("chooseSpellAbilitiesForEffect:EMPTY");
            java.util.List<SpellAbility> chosen = new java.util.ArrayList<>();
            int guard = 0;
            while (chosen.size() < num) {
                if (++guard > 32) throw failClosed("chooseSpellAbilitiesForEffect:GUARD");
                java.util.List<SpellAbility> rest = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (SpellAbility o : spells) {
                    if (chosen.contains(o)) continue;
                    rest.add(o);
                    labels.add("WS48:OPT:sa=" + ws48Enc(ws48Clip(String.valueOf(o), 160))
                        + ":host=" + ws48Enc(ws48CardRef(o.getHostCard())));
                }
                if (rest.isEmpty()) throw failClosed("chooseSpellAbilitiesForEffect:EXHAUSTED");
                chosen.add(rest.get(ws48Choose("choose_ability", this.player, labels)));
            }
            return chosen;
        }"""

SINGLE_SPELL_NEW = """        @Override
        public SpellAbility chooseSingleSpellForEffect(List<SpellAbility> spells, SpellAbility sa, String title, Map<String, Object> params) {
            if (spells == null || spells.isEmpty()) throw failClosed("chooseSingleSpellForEffect:EMPTY");
            if (spells.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseSingleSpellForEffect");
                return spells.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (SpellAbility o : spells) {
                labels.add("WS48:OPT:sa=" + ws48Enc(ws48Clip(String.valueOf(o), 160))
                    + ":host=" + ws48Enc(ws48CardRef(o.getHostCard())));
            }
            return spells.get(ws48Choose("choose_ability", this.player, labels));
        }"""

SINGLE_ZONE_NEW = """        @Override
        public Card chooseSingleCardForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, DelayedReveal delayedReveal, String selectPrompt, boolean isOptional, Player decider) {
            if (fetchList == null || fetchList.isEmpty()) {
                if (isOptional) return null;
                throw failClosed("chooseSingleCardForZoneChange:EMPTY");
            }
            if (!isOptional && fetchList.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseSingleCardForZoneChange");
                return fetchList.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            if (isOptional) labels.add("WS48:OPT:NONE");
            for (Card o : fetchList) labels.add("WS48:OPT:opt=" + ws48Enc(ws48CardRef(o)));
            int idx = ws48Choose("choose_object", decider == null ? this.player : decider, labels);
            if (isOptional) {
                if (idx == 0) return null;
                idx--;
            }
            return fetchList.get(idx);
        }"""

ZONE_LIST_NEW = """        @Override
        public List<Card> chooseCardsForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, int min, int max, DelayedReveal delayedReveal, String selectPrompt, Player decider) {
            java.util.List<Card> out = new java.util.ArrayList<>();
            int guard = 0;
            while (out.size() < max) {
                if (++guard > 32) throw failClosed("chooseCardsForZoneChange:GUARD");
                java.util.List<Card> rest = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (Card o : fetchList) {
                    if (out.contains(o)) continue;
                    rest.add(o);
                    labels.add("WS48:OPT:opt=" + ws48Enc(ws48CardRef(o)));
                }
                if (rest.isEmpty()) break;
                if (out.size() >= min) labels.add("WS48:OPT:DONE");
                int idx = ws48Choose("choose_object", decider == null ? this.player : decider, labels);
                if (out.size() >= min && idx == labels.size() - 1 && labels.get(idx).equals("WS48:OPT:DONE")) break;
                out.add(rest.get(idx));
            }
            if (out.size() < min) throw failClosed("chooseCardsForZoneChange:UNDER_MIN");
            return out;
        }"""

MODE_NEW = """        @Override
        public List<AbilitySub> chooseModeForAbility(SpellAbility sa, List<AbilitySub> possible, int min, int num, boolean allowRepeat) {
            if (possible == null || possible.isEmpty()) throw failClosed("chooseModeForAbility:EMPTY");
            if (possible.size() == 1 && min == 1 && num == 1 && !allowRepeat) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseModeForAbility");
                // Mutable container required: the engine sorts the returned
                // modes in place (CharmEffect.chainAbilities). Same element,
                // same order - only the container mutability matches the
                // native controller contract.
                return new java.util.ArrayList<>(java.util.List.of(possible.get(0)));
            }
            if (min == 1 && num == 1 && !allowRepeat) {
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (AbilitySub o : possible) {
                    labels.add("WS48:MODE:api=" + ws48Enc(String.valueOf(o.getApi()))
                        + ":desc=" + ws48Enc(ws48Clip(o.getDescription(), 200)));
                }
                return new java.util.ArrayList<>(java.util.List.of(possible.get(ws48Choose("choose_mode", this.player, labels))));
            }
            throw failClosed("chooseModeForAbility:DEPENDENT_MULTI_CHOICE");
        }"""

NUMBER_INT_NEW = """        @Override
        public int chooseNumber(SpellAbility sa, String title, int min, int max) {
            if (max < min) throw failClosed("chooseNumber:RANGE");
            if (min == max) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseNumber");
                return min;
            }
            if ((long) max - (long) min > 64) throw failClosed("chooseNumber:RANGE_TOO_WIDE");
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (int i = min; i <= max; i++) labels.add("WS48:NUM:n=" + i);
            int idx = ws48Choose("announce_x", this.player, labels);
            return min + idx;
        }"""

NUMBER_LIST_NEW = """        @Override
        public int chooseNumber(SpellAbility sa, String title, List<Integer> values, Player relatedPlayer) {
            if (values == null || values.isEmpty()) throw failClosed("chooseNumber:EMPTY_VALUES");
            if (values.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseNumberValues");
                return values.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (int v : values) labels.add("WS48:NUM:n=" + v);
            return values.get(ws48Choose("announce_x", this.player, labels));
        }"""

ANNOUNCE_NEW = """        @Override
        public Integer announceRequirements(SpellAbility ability, int min, int max, String announce) {
            if (max < min) throw failClosed("announceRequirements:RANGE");
            if (min == max) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:announceRequirements");
                return min;
            }
            if ((long) max - (long) min > 64) throw failClosed("announceRequirements:RANGE_TOO_WIDE");
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (int i = min; i <= max; i++) labels.add("WS48:NUM:n=" + i + ":announce=" + ws48Enc(ws48Clip(announce, 80)));
            return min + ws48Choose("announce_x", this.player, labels);
        }"""

BINARY_NEW = """        @Override
        public boolean chooseBinary(SpellAbility sa, String question, BinaryChoiceType kindOfChoice, Boolean defaultChoice) {
            return "o0".equals(broker.choose("choose_use", player, java.util.List.of(
                "WS48:BOOL:val=true:q=" + ws48Enc(ws48Clip(question, 160)),
                "WS48:BOOL:val=false:q=" + ws48Enc(ws48Clip(question, 160)))));
        }"""

COLOR_NEW = """        @Override
        public byte chooseColor(String message, SpellAbility sa, ColorSet colors) {
            if (colors == null || colors.countColors() == 0) throw failClosed("chooseColor:EMPTY");
            java.util.List<Byte> opts = new java.util.ArrayList<>();
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (forge.card.MagicColor.Color col : colors) {
                opts.add(col.getColorMask());
                labels.add("WS48:COLOR:color=" + ws48Enc(col.getShortName()));
            }
            if (opts.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseColor");
                return opts.get(0);
            }
            return opts.get(ws48Choose("choice", this.player, labels));
        }"""

REPL_SINGLE_NEW = """        @Override
        public ReplacementEffect chooseSingleReplacementEffect(List<ReplacementEffect> possibleReplacers) {
            if (possibleReplacers == null || possibleReplacers.isEmpty())
                throw failClosed("chooseSingleReplacementEffect:EMPTY");
            if (possibleReplacers.size() == 1) {
                broker.recordAutomatic("SINGLE_NATIVE_OPTION:chooseSingleReplacementEffect");
                return possibleReplacers.get(0);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            for (ReplacementEffect o : possibleReplacers) {
                labels.add("WS48:REPL:src=" + ws48Enc(ws48CardName(o.getHostCard()))
                    + ":desc=" + ws48Enc(ws48Clip(String.valueOf(o), 160)));
            }
            return possibleReplacers.get(ws48Choose("replacement_effect", this.player, labels));
        }"""

TRIGGER_ORDER_NEW = """        @Override
        public List<SpellAbility> orderSimultaneousSa(List<SpellAbility> activePlayerSAs) {
            if (activePlayerSAs == null || activePlayerSAs.size() <= 1) {
                broker.recordAutomatic("orderSimultaneousSa:ZERO_OR_ONE");
                return activePlayerSAs;
            }
            if (activePlayerSAs.size() != 2) throw failClosed("orderSimultaneousSa:MORE_THAN_TWO");
            java.util.List<String> identities = new java.util.ArrayList<>();
            for (SpellAbility o : activePlayerSAs) {
                identities.add(ws48CardName(o.getHostCard()) + ":" + ws48Clip(String.valueOf(o), 120));
            }
            java.util.List<String> labels = java.util.List.of(
                "WS48:ORDER:order=0,1:first=" + ws48Enc(identities.get(0)) + ":second=" + ws48Enc(identities.get(1)),
                "WS48:ORDER:order=1,0:first=" + ws48Enc(identities.get(1)) + ":second=" + ws48Enc(identities.get(0)));
            int idx = ws48Choose("trigger_order", this.player, labels);
            if (idx == 0) return java.util.List.of(activePlayerSAs.get(0), activePlayerSAs.get(1));
            return java.util.List.of(activePlayerSAs.get(1), activePlayerSAs.get(0));
        }

        @Override
        public void orderAndPlaySimultaneousSa(List<SpellAbility> activePlayerSAs) {
            if (activePlayerSAs == null || activePlayerSAs.isEmpty()) {
                broker.recordAutomatic("orderAndPlaySimultaneousSa:EMPTY");
                return;
            }
            java.util.List<SpellAbility> ordered = orderSimultaneousSa(activePlayerSAs);
            for (int i = ordered.size() - 1; i >= 0; i--) {
                SpellAbility next = ordered.get(i);
                if (!next.isTrigger() || next.isCopied())
                    throw failClosed("orderAndPlaySimultaneousSa:NON_NATIVE_TRIGGER");
                if (!PlaySpellAbility.playSpellAbility(this, this.player, next))
                    throw failClosed("orderAndPlaySimultaneousSa:FORGE_REJECTED_TRIGGER_PLAY");
            }
            broker.recordAutomatic("orderAndPlaySimultaneousSa:FORGE_CORE_TRIGGER_STACK");
        }"""

# Exact ICostVisitor<PaymentDecision> surface at Forge 66caae16 (40 methods).
# R1b audit (all citations Forge 66caae16, tree 40fc8f29):
# - CostPartMana: HumanCostDecision.visit returns new PaymentDecision(0)
#   unconditionally; CostPartMana.payAsDecided runs the interactive native
#   payment (payManaCost/applyManaToCost) ignoring decision content. AUTO.
# - CostTap: HumanCostDecision.visit returns PaymentDecision.number(1)
#   unconditionally - no prompt, no selection, no confirm. CostTap is a
#   no-arg part; CostTap.payAsDecided taps ability.getHostCard() directly and
#   ignores the decision content. Selective tapping is the separate
#   CostTapType part (stays fail-closed). AUTO.
# - CostAddMana: HumanCostDecision.visit returns
#   PaymentDecision.number(cost.getAbilityAmount(ability)) unconditionally -
#   no prompt, no selection, no confirm. payAsDecided adds exactly
#   decision.c mana of the native part type. The amount is engine-computed
#   native state (X resolved from ability-announced values via the separate
#   announceRequirements surface). AUTO as an exact native mirror.
# - CostPayLife: HumanCostDecision.visit pays WITHOUT asking only when
#   sa.getPayCosts().isMandatory(); the non-mandatory path offers a
#   confirm-or-cancel choice and cancelling aborts payment. Willingness to
#   pay is genuine discretion: only the exact native-mandatory branch is
#   mirrored, everything else fails closed (never auto-pay, never
#   auto-decline/filter-cancel).
# - All other parts involve native prompts/selections/confirms: FAIL_CLOSED
#   with exact part identity. Multi-part cost ordering stays fail-closed via
#   the generated orderCosts fail-closed stub (PlaySpellAbility activation
#   uses CostPayment.payCost, which calls orderCosts for >1 part).
COST_VISIT_PARTS = [
    "CostBehold", "CostBeholdExile", "CostGainControl", "CostChooseColor",
    "CostChooseCreatureType", "CostCollectEvidence", "CostDiscard",
    "CostDamage", "CostDraw", "CostExile", "CostExileFromStack",
    "CostExiledMoveToGrave", "CostExert", "CostEnlist", "CostFlipCoin",
    "CostForage", "CostRollDice", "CostMill",
    "CostPayEnergy", "CostGainLife",     "CostPromiseGift", "CostPutCardToLib",
    "CostSacrifice", "CostReturn", "CostReveal",
    "CostRevealChosen", "CostRemoveAnyCounter", "CostRemoveCounter",
    "CostPutCounter", "CostPutCounterYou", "CostUntapType", "CostUntap",
    "CostUnattach", "CostTapType", "CostPayShards", "CostBlight",
]


def cost_decision_java() -> str:
    visits = []
    for part in COST_VISIT_PARTS:
        visits.append(
            "                @Override\n"
            f"                public PaymentDecision visit({part} cost) {{\n"
            f'                    throw failClosed("costVisit:{part}");\n'
            "                }")
    return """        @Override
        public CostDecisionMakerBase getCostDecisionMaker(Player player, SpellAbility ability, boolean effect, String prompt) {
            ws48Milestone("getCostDecisionMaker:ENTERED");
            Card source = ability == null ? null : ability.getHostCard();
            return new CostDecisionMakerBase(player, effect, ability, source) {
                @Override
                public boolean paysRightAfterDecision() {
                    // Structural two-phase payment: decide all parts first,
                    // then CostPayment pays each once via payAsDecided.
                    // Returning true would double-pay mana parts.
                    return false;
                }

                @Override
                public PaymentDecision visit(CostPartMana cost) {
                    // The decision content is unused by
                    // CostPartMana.payAsDecided (whole payment runs through
                    // the native payManaCost/applyManaToCost path).
                    broker.recordAutomatic("costVisit:CostPartMana");
                    return new PaymentDecision(0);
                }

                @Override
                public PaymentDecision visit(CostTap cost) {
                    // R1b PROVEN NON-DISCRETIONARY, exact native mirror:
                    // HumanCostDecision.visit(CostTap) returns
                    // PaymentDecision.number(1) with no prompt/selection/
                    // confirm, and CostTap.payAsDecided taps
                    // ability.getHostCard() ignoring the decision content.
                    broker.recordAutomatic("costVisit:CostTap");
                    return PaymentDecision.number(1);
                }

                @Override
                public PaymentDecision visit(CostAddMana cost) {
                    // R1b PROVEN NON-DISCRETIONARY, exact native mirror:
                    // HumanCostDecision.visit(CostAddMana) returns
                    // PaymentDecision.number(cost.getAbilityAmount(ability))
                    // with no prompt/selection/confirm. payAsDecided adds
                    // exactly decision.c mana of the native part type.
                    broker.recordAutomatic("costVisit:CostAddMana");
                    return PaymentDecision.number(cost.getAbilityAmount(ability));
                }

                @Override
                public PaymentDecision visit(CostPayLife cost) {
                    // R1b CONDITIONAL mirror of the single native branch that
                    // pays without asking: HumanCostDecision.visit(CostPayLife)
                    // returns PaymentDecision.number(c) directly only when
                    // sa.getPayCosts().isMandatory(). The non-mandatory path
                    // offers confirm-or-cancel (cancel aborts payment), which
                    // is genuine discretion, so it fails closed with exact
                    // part identity - never auto-pay, never auto-decline.
                    if (ability.getPayCosts().isMandatory()) {
                        broker.recordAutomatic("costVisit:CostPayLife:MANDATORY");
                        return PaymentDecision.number(cost.getAbilityAmount(ability));
                    }
                    throw failClosed("costVisit:CostPayLife");
                }

""" + "\n".join(visits) + """
            };
        }"""


COST_DECISION_NEW = cost_decision_java()

MANA_NEW = """        @Override
        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            ws48Milestone("payManaCost:ENTERED");
            return PlaySpellAbility.payManaCost(this, toPay, costPartMana, sa, this.player, prompt, matrix, effect);
        }

        @Override
        public boolean applyManaToCost(ManaCostBeingPaid toPay, SpellAbility ability, String prompt, ManaConversionMatrix matrix, boolean effect) {
            ws48Milestone("applyManaToCost:ENTERED");
            int guard = 0;
            while (!toPay.isPaid()) {
                if (++guard > 24) throw failClosed("applyManaToCost:GUARD");
                java.util.List<SpellAbility> nativeMana = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                ZoneType[] zones = new ZoneType[] {ZoneType.Battlefield, ZoneType.Hand, ZoneType.Graveyard, ZoneType.Exile, ZoneType.Command};
                for (ZoneType zone : zones) {
                    for (Card card : this.player.getCardsIn(zone)) {
                        for (SpellAbility manaAbility : card.getAllPossibleAbilities(this.player, true)) {
                            if (!manaAbility.isManaAbility()) continue;
                            manaAbility.setActivatingPlayer(this.player);
                            nativeMana.add(manaAbility);
                            labels.add("WS48:MANA:src=" + ws48Enc(ws48CardRef(card))
                                + ":ability=" + ws48Enc(ws48Clip(String.valueOf(manaAbility), 120)));
                        }
                    }
                }
                if (nativeMana.isEmpty()) return false;
                SpellAbility chosen = nativeMana.get(ws48Choose("mana_payment", this.player, labels));
                if (!PlaySpellAbility.playSpellAbility(this, this.player, chosen)) return false;
                boolean restrictionsMet = true;
                for (AbilityManaPart manaPart : chosen.getAllManaParts()) {
                    if (!manaPart.meetsManaRestrictions(ability)) {
                        restrictionsMet = false;
                        break;
                    }
                }
                if (!restrictionsMet) return false;
                this.player.getManaPool().payManaFromAbility(ability, toPay, chosen);
            }
            return true;
        }"""

DECLARE_NEW = """        @Override
        public void declareAttackers(Player attacker, Combat combat) {
            ws48Milestone("declareAttackers:ENTERED");
            java.util.List<Card> cands = new java.util.ArrayList<>();
            for (Card c : attacker.getCardsIn(ZoneType.Battlefield)) {
                if (!c.isCreature()) continue;
                if (forge.game.combat.CombatUtil.canAttack(c)) cands.add(c);
            }
            for (Card c : cands) {
                java.util.List<GameEntity> defs = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (Player p : getGame().getPlayers()) {
                    if (p.equals(attacker)) continue;
                    if (forge.game.combat.CombatUtil.canAttack(c, p)) {
                        defs.add(p);
                        labels.add("WS48:ATTACK:attacker=" + ws48Enc(ws48CardRef(c))
                            + ":defender=" + ws48Enc(ws48EntityRef(p)));
                    }
                    for (Card pw : p.getCardsIn(ZoneType.Battlefield)) {
                        if (!pw.isPlaneswalker()) continue;
                        if (forge.game.combat.CombatUtil.canAttack(c, pw)) {
                            defs.add(pw);
                            labels.add("WS48:ATTACK:attacker=" + ws48Enc(ws48CardRef(c))
                                + ":defender=" + ws48Enc(ws48CardRef(pw)));
                        }
                    }
                }
                if (defs.isEmpty()) continue;
                labels.add("WS48:ATTACK:SKIP:" + ws48Enc(ws48CardRef(c)));
                int idx = ws48Choose("declare_attacker", attacker, labels);
                if (idx == labels.size() - 1) continue;
                combat.addAttacker(c, defs.get(idx));
            }
            ws48FinalizeDeclaredBands(combat);
            broker.recordAutomatic("declareAttackers:WS48_NATIVE_COMBAT");
        }

        @Override
        public void declareBlockers(Player defender, Combat combat) {
            ws48Milestone("declareBlockers:ENTERED");
            java.util.List<Card> cands = new java.util.ArrayList<>();
            for (Card c : defender.getCardsIn(ZoneType.Battlefield)) {
                if (!c.isCreature()) continue;
                if (forge.game.combat.CombatUtil.canBlock(c, combat)) cands.add(c);
            }
            java.util.List<Card> attackers = new java.util.ArrayList<>(combat.getAttackers());
            for (Card c : cands) {
                java.util.List<Card> foes = new java.util.ArrayList<>();
                java.util.List<String> labels = new java.util.ArrayList<>();
                for (Card a : attackers) {
                    if (!forge.game.combat.CombatUtil.canBlock(a, c, combat)) continue;
                    foes.add(a);
                    labels.add("WS48:BLOCK:blocker=" + ws48Enc(ws48CardRef(c))
                        + ":attacker=" + ws48Enc(ws48CardRef(a)));
                }
                if (foes.isEmpty()) continue;
                labels.add("WS48:BLOCK:SKIP:" + ws48Enc(ws48CardRef(c)));
                int idx = ws48Choose("declare_blocker", defender, labels);
                if (idx == labels.size() - 1) continue;
                combat.addBlocker(foes.get(idx), c);
                combat.setBlocked(foes.get(idx), true);
            }
            ws48FinalizeDeclaredBands(combat);
            broker.recordAutomatic("declareBlockers:WS48_NATIVE_COMBAT");
        }"""

SCRY_NEW = """        @Override
        public ImmutablePair<CardCollection, CardCollection> arrangeForScry(CardCollection topN) {
            if (topN == null || topN.isEmpty()) throw failClosed("arrangeForScry:EMPTY");
            if (topN.size() > 4) throw failClosed("arrangeForScry:TOO_MANY:" + topN.size());
            java.util.List<Card> cards = new java.util.ArrayList<>(topN);
            java.util.List<java.util.List<Integer>> splits = new java.util.ArrayList<>();
            int total = 1 << cards.size();
            for (int mask = 0; mask < total; mask++) {
                java.util.List<Integer> top = new java.util.ArrayList<>();
                java.util.List<Integer> bottom = new java.util.ArrayList<>();
                for (int i = 0; i < cards.size(); i++) {
                    if ((mask & (1 << i)) != 0) top.add(i); else bottom.add(i);
                }
                splits.add(top);
                splits.add(bottom);
            }
            java.util.List<String> labels = new java.util.ArrayList<>();
            java.util.List<CardCollection> tops = new java.util.ArrayList<>();
            java.util.List<CardCollection> bottoms = new java.util.ArrayList<>();
            for (int mask = 0; mask < total; mask++) {
                CardCollection t = new CardCollection();
                CardCollection b = new CardCollection();
                StringBuilder tl = new StringBuilder();
                StringBuilder bl = new StringBuilder();
                for (int i = 0; i < cards.size(); i++) {
                    String ref = ws48CardRef(cards.get(i));
                    if ((mask & (1 << i)) != 0) {
                        t.add(cards.get(i));
                        if (tl.length() > 0) tl.append(",");
                        tl.append(ref);
                    } else {
                        b.add(cards.get(i));
                        if (bl.length() > 0) bl.append(",");
                        bl.append(ref);
                    }
                }
                tops.add(t);
                bottoms.add(b);
                labels.add("WS48:SCRY:top=" + ws48Enc(tl.toString()) + ":bottom=" + ws48Enc(bl.toString()));
            }
            int idx = ws48Choose("choose_use", this.player, labels);
            return ImmutablePair.of(tops.get(idx), bottoms.get(idx));
        }"""

EOF_TYPED_ANCHOR = '                if (answer == null) throw new ControlledStop("WS23_EXTERNAL_EOF");'
EOF_TYPED_NEW = """                if (answer == null) throw new ControlledStop("WS48_UNSUPPORTED_DISCRETIONARY_DECISION:" + kind);"""
TRACE_ANCHOR = """        } catch (ControlledStop expected) {
            stopReason = expected.getMessage();
        } catch (UnsupportedOperationException unsupported) {
            stopReason = unsupported.getMessage();
        }"""
TRACE_NEW = """        } catch (ControlledStop expected) {
            stopReason = expected.getMessage();
            if (stopReason == null) stopReason = "WS48_NULL_CONTROLLED_STOP";
            expected.printStackTrace();
        } catch (UnsupportedOperationException unsupported) {
            stopReason = unsupported.getMessage();
            if (stopReason == null) stopReason = "WS48_BARE_UNSUPPORTED_OPERATION";
            unsupported.printStackTrace();
        }"""
EVENTS_ANCHOR = "        Game game = match.createGame();"
EVENTS_ADD = """        Game game = match.createGame();
        game.subscribeToEvents(new Ws48NativeEvents(broker, game));"""
EVENTS_CLASS_ANCHOR = "    static String singleCommanderName(Player player) {"
EVENTS_CLASS_ADD = """    static final class Ws48NativeEvents {
        final Broker broker;
        final Game game;

        Ws48NativeEvents(Broker broker, Game game) {
            this.broker = broker;
            this.game = game;
        }

        String pid(Player p) {
            int i = game.getPlayers().indexOf(p);
            return i < 0 ? "PX" : ("P" + (i + 1));
        }

        void emit(String name, String facts) {
            broker.out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"NATIVE_EVENT\\""
                + ",\\"request_id\\":\\"ws48-native-event\\""
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"payload\\":{\\"event\\":" + esc(name) + ",\\"facts\\":" + esc(facts) + "}}");
            broker.out.flush();
        }

        @com.google.common.eventbus.Subscribe
        public void onCast(forge.game.event.GameEventSpellAbilityCast event) {
            emit("spell_cast", String.valueOf(event.sa()) + "|" + String.valueOf(event.targetDescription()));
        }

        @com.google.common.eventbus.Subscribe
        public void onResolve(forge.game.event.GameEventSpellResolved event) {
            emit("spell_resolved", "fizzled=" + event.hasFizzled() + "|" + String.valueOf(event.stackDescription()));
        }

        @com.google.common.eventbus.Subscribe
        public void onAttackers(forge.game.event.GameEventAttackersDeclared event) {
            emit("attackers_declared", String.valueOf(event.attackersMap().size()));
        }

        @com.google.common.eventbus.Subscribe
        public void onBlockers(forge.game.event.GameEventBlockersDeclared event) {
            emit("blockers_declared", String.valueOf(event.blockers().size()));
        }

        @com.google.common.eventbus.Subscribe
        public void onMulligan(forge.game.event.GameEventMulligan event) {
            emit("mulligan", String.valueOf(event.player()));
        }

        @com.google.common.eventbus.Subscribe
        public void onScry(forge.game.event.GameEventScry event) {
            emit("scry", "toTop=" + event.toTop() + ":toBottom=" + event.toBottom());
        }

        @com.google.common.eventbus.Subscribe
        public void onShuffle(forge.game.event.GameEventShuffle event) {
            emit("shuffle", String.valueOf(event.player()));
        }

        @com.google.common.eventbus.Subscribe
        public void onTurnPhase(forge.game.event.GameEventTurnPhase event) {
            emit("turn_phase", String.valueOf(event.phase()));
        }

        @com.google.common.eventbus.Subscribe
        public void onPlayerDamaged(forge.game.event.GameEventPlayerDamaged event) {
            emit("player_damaged", "amount=" + event.amount() + ":combat=" + event.combat());
        }
    }

    static String singleCommanderName(Player player) {"""

TERMINATION_HELPERS_ANCHOR = "    static void runSession(BufferedReader in, PrintWriter out) throws Exception {"
TERMINATION_HELPERS_ADD = """    // R1c truthful terminal SESSION_RESULT. Exactly-once emission guarded by
    // ws48ResultEmitted: normal return, clean EOF/script exhaustion, and
    // controlled fail-closed stops emit synchronously with their real stop
    // reason; unexpected failures emit before propagating (real termination
    // class preserved, never translated into success); a shutdown hook
    // covers any remaining JVM-exit path with a truthful no-result marker.
    static final java.util.concurrent.atomic.AtomicBoolean ws48ResultEmitted =
        new java.util.concurrent.atomic.AtomicBoolean(false);
    static volatile String ws48TerminalClass = null;

    static void ws48EmitResult(PrintWriter out, Broker broker, Game game, String stopReason) {
        if (!ws48ResultEmitted.compareAndSet(false, true)) return;
        String snapshot;
        try {
            snapshot = sessionSnapshot(game);
        } catch (Throwable t) {
            snapshot = "{\\"snapshot_unavailable\\":" + esc(t.getClass().getName()) + "}";
        }
        out.println("{\\"protocol\\":" + esc(PROTOCOL)
            + ",\\"message_type\\":\\"SESSION_RESULT\\""
            + ",\\"request_id\\":\\"ws23-result\\""
            + ",\\"session_id\\":" + esc(SESSION_ID)
            + ",\\"state_revision\\":" + broker.revision
            + ",\\"payload\\":{\\"stop_reason\\":" + esc(stopReason)
            + ",\\"priority_decisions\\":" + broker.priorityDecisions
            + ",\\"snapshot\\":" + snapshot + "}}");
        out.flush();
    }

    static void runSession(BufferedReader in, PrintWriter out) throws Exception {"""

TERM_CATCH_OLD = """        } catch (ControlledStop expected) {
            stopReason = expected.getMessage();
            if (stopReason == null) stopReason = "WS48_NULL_CONTROLLED_STOP";
            expected.printStackTrace();
        } catch (UnsupportedOperationException unsupported) {
            stopReason = unsupported.getMessage();
            if (stopReason == null) stopReason = "WS48_BARE_UNSUPPORTED_OPERATION";
            unsupported.printStackTrace();
        }"""
TERM_CATCH_NEW = """        } catch (ControlledStop expected) {
            stopReason = expected.getMessage();
            if (stopReason == null) stopReason = "WS48_NULL_CONTROLLED_STOP";
            expected.printStackTrace();
        } catch (UnsupportedOperationException unsupported) {
            stopReason = unsupported.getMessage();
            if (stopReason == null) stopReason = "WS48_BARE_UNSUPPORTED_OPERATION";
            unsupported.printStackTrace();
        } catch (RuntimeException unexpected) {
            // R1c: unexpected failure - report terminally HERE before exit,
            // preserving the real termination class (never a success).
            // printStackTrace preserves the stderr diagnostic evidence.
            unexpected.printStackTrace();
            ws48TerminalClass = "UNEXPECTED:" + unexpected.getClass().getName()
                + ":" + ws48Clip(String.valueOf(unexpected.getMessage()), 200);
            ws48EmitResult(out, broker, game, ws48TerminalClass);
            throw unexpected;
        } catch (Error terminalError) {
            terminalError.printStackTrace();
            ws48TerminalClass = "UNEXPECTED_ERROR:" + terminalError.getClass().getName()
                + ":" + ws48Clip(String.valueOf(terminalError.getMessage()), 200);
            ws48EmitResult(out, broker, game, ws48TerminalClass);
            throw terminalError;
        }"""

TERM_EMIT_OLD = """        out.println("{\\"protocol\\":" + esc(PROTOCOL)
            + ",\\"message_type\\":\\"SESSION_RESULT\\""
            + ",\\"request_id\\":\\"ws23-result\\""
            + ",\\"session_id\\":" + esc(SESSION_ID)
            + ",\\"state_revision\\":" + broker.revision
            + ",\\"payload\\":{\\"stop_reason\\":" + esc(stopReason)
            + ",\\"priority_decisions\\":" + broker.priorityDecisions
            + ",\\"snapshot\\":" + sessionSnapshot(game) + "}}");
        out.flush();"""
TERM_EMIT_NEW = """        ws48TerminalClass = stopReason;
        ws48EmitResult(out, broker, game, stopReason);"""

TERM_HOOK_OLD = """        Game game = match.createGame();
        game.subscribeToEvents(new Ws48NativeEvents(broker, game));"""
TERM_HOOK_NEW = """        Game game = match.createGame();
        game.subscribeToEvents(new Ws48NativeEvents(broker, game));
        final Broker ws48HookBroker = broker;
        final Game ws48HookGame = game;
        final PrintWriter ws48HookOut = out;
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            String terminal = ws48TerminalClass == null
                ? "WS48_NO_RESULT_AT_SHUTDOWN"
                : ("WS48_NO_RESULT_AT_SHUTDOWN:lastKnown=" + ws48TerminalClass);
            ws48EmitResult(ws48HookOut, ws48HookBroker, ws48HookGame, terminal);
        }));"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()

    s = args.state_java.read_text(encoding="utf-8")
    s = once(s, STATE_ACCESSOR_ANCHOR, STATE_ACCESSOR_ADD + STATE_ACCESSOR_ANCHOR,
             "state semantic accessors")
    s = once(s, "        applyCombat(game);",
             "        applyCombat(game);\n        ws48FinalizeLoadedCombatBands(game);",
             "loaded combat band finalization")
    args.state_java.write_text(s, encoding="utf-8")

    p = args.provider.read_text(encoding="utf-8")
    p = once(p, HELPERS_ANCHOR, HELPERS_ADD, "controller helpers")
    p = once(p, PROVIDER_STATIC_ANCHOR, PROVIDER_STATIC_ADD, "static helpers")
    p = once(p, PRIORITY_LABEL_ANCHOR, PRIORITY_LABEL_NEW, "priority semantic labels")

    def rep(old: str, new: str, label: str) -> None:
        nonlocal p
        p = once(p, old, new, label)

    rep("""        public SpellAbility getAbilityToPlay(Card hostCard, List<SpellAbility> abilities, ITriggerEvent triggerEvent) {
            throw failClosed("getAbilityToPlay");
        }""", ABILITY_TO_PLAY_NEW, "getAbilityToPlay")
    rep("""        public boolean chooseTargetsFor(SpellAbility currentAbility) {
            throw failClosed("chooseTargetsFor");
        }""", TARGETS_FOR_NEW, "chooseTargetsFor")
    rep("""        public Pair<SpellAbilityStackInstance, GameObject> chooseTarget(SpellAbility sa, List<Pair<SpellAbilityStackInstance, GameObject>> allTargets) {
            throw failClosed("chooseTarget");
        }""", TARGET_NEW, "chooseTarget")
    rep("""        public <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal, SpellAbility sa, String title, boolean isOptional, Player relatedPlayer, Map<String, Object> params) {
            throw failClosed("chooseSingleEntityForEffect");
        }

        @Override
        public <T extends GameEntity> List<T> chooseEntitiesForEffect(FCollectionView<T> optionList, int min, int max, DelayedReveal delayedReveal, SpellAbility sa, String title, Player relatedPlayer, Map<String, Object> params) {
            throw failClosed("chooseEntitiesForEffect");
        }""", ENTITY_GENERIC_NEW, "entity generics")
    rep("""        public CardCollectionView chooseCardsForEffect(CardCollectionView sourceList, SpellAbility sa, String title, int min, int max, boolean isOptional, Map<String, Object> params) {
            throw failClosed("chooseCardsForEffect");
        }""", CARDS_FOR_EFFECT_NEW, "chooseCardsForEffect")
    rep("""        public List<SpellAbility> chooseSpellAbilitiesForEffect(List<SpellAbility> spells, SpellAbility sa, String title, int num, Map<String, Object> params) {
            throw failClosed("chooseSpellAbilitiesForEffect");
        }""", SPELLS_ABILITIES_NEW, "chooseSpellAbilitiesForEffect")
    rep("""        public SpellAbility chooseSingleSpellForEffect(List<SpellAbility> spells, SpellAbility sa, String title, Map<String, Object> params) {
            throw failClosed("chooseSingleSpellForEffect");
        }""", SINGLE_SPELL_NEW, "chooseSingleSpellForEffect")
    rep("""        public Card chooseSingleCardForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, DelayedReveal delayedReveal, String selectPrompt, boolean isOptional, Player decider) {
            throw failClosed("chooseSingleCardForZoneChange");
        }""", SINGLE_ZONE_NEW, "chooseSingleCardForZoneChange")
    rep("""        public List<Card> chooseCardsForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa, CardCollection fetchList, int min, int max, DelayedReveal delayedReveal, String selectPrompt, Player decider) {
            throw failClosed("chooseCardsForZoneChange");
        }""", ZONE_LIST_NEW, "chooseCardsForZoneChange")
    rep("""        public List<AbilitySub> chooseModeForAbility(SpellAbility sa, List<AbilitySub> possible, int min, int num, boolean allowRepeat) {
            if (possible == null || possible.isEmpty()) throw failClosed("chooseModeForAbility:EMPTY");
            if (min == 1 && num == 1 && !allowRepeat) {
                AbilitySub chosen = broker.chooseObject("chooseModeForAbility", player, possible, false);
                return java.util.List.of(chosen);
            }
            throw failClosed("chooseModeForAbility:DEPENDENT_MULTI_CHOICE");
        }""", MODE_NEW, "chooseModeForAbility")
    rep("""        public Integer announceRequirements(SpellAbility ability, int min, int max, String announce) {
            throw failClosed("announceRequirements");
        }""", ANNOUNCE_NEW, "announceRequirements")
    rep("""        public int chooseNumber(SpellAbility sa, String title, int min, int max) {
            throw failClosed("chooseNumber");
        }""", NUMBER_INT_NEW, "chooseNumber")
    rep("""        public int chooseNumber(SpellAbility sa, String title, List<Integer> values, Player relatedPlayer) {
            throw failClosed("chooseNumber");
        }

        @Override
        public boolean chooseBinary(SpellAbility sa, String question, BinaryChoiceType kindOfChoice, Boolean defaultChoice) {
            return broker.chooseBoolean("chooseBinary", player, "TRUE", "FALSE");
        }""", NUMBER_LIST_NEW + "\n" + BINARY_NEW, "chooseNumberValues+binary")
    rep("""        public byte chooseColor(String message, SpellAbility sa, ColorSet colors) {
            throw failClosed("chooseColor");
        }""", COLOR_NEW, "chooseColor")
    rep("""        public boolean confirmAction(SpellAbility sa, PlayerActionConfirmMode mode, String message, List<String> options, Card cardToShow, Map<String, Object> params) {
            return broker.chooseBoolean("confirmAction", player, "YES", "NO");
        }""", """        @Override
        public boolean confirmAction(SpellAbility sa, PlayerActionConfirmMode mode, String message, List<String> options, Card cardToShow, Map<String, Object> params) {
            java.util.List<String> labels = new java.util.ArrayList<>();
            if (options == null || options.isEmpty()) {
                labels.add("WS48:CONFIRM:opt=YES");
                labels.add("WS48:CONFIRM:opt=NO");
            } else {
                for (String o : options) labels.add("WS48:CONFIRM:opt=" + ws48Enc(ws48Clip(o, 120)));
            }
            int idx = ws48Choose("confirm", player, labels);
            if (options == null || options.isEmpty()) return idx == 0;
            String picked = options.get(idx);
            return !(picked.equalsIgnoreCase("NO") || picked.equalsIgnoreCase("DECLINE")
                || picked.equalsIgnoreCase("FALSE") || picked.equalsIgnoreCase("BOTTOM")
                || picked.equalsIgnoreCase("MULLIGAN"));
        }""", "confirmAction")
    rep("""        public boolean confirmPayment(CostPart costPart, String string, SpellAbility sa) {
            return broker.chooseBoolean("confirmPayment", player, "PAY", "DECLINE");
        }""", """        @Override
        public boolean confirmPayment(CostPart costPart, String string, SpellAbility sa) {
            return "o0".equals(broker.choose("confirm", player, java.util.List.of(
                "WS48:CONFIRM:opt=PAY:q=" + ws48Enc(ws48Clip(string, 160)),
                "WS48:CONFIRM:opt=DECLINE:q=" + ws48Enc(ws48Clip(string, 160)))));
        }""", "confirmPayment")
    rep("""        public boolean confirmReplacementEffect(ReplacementEffect replacementEffect, SpellAbility effectSA, GameEntity affected, String question) {
            throw failClosed("confirmReplacementEffect");
        }""", """        @Override
        public boolean confirmReplacementEffect(ReplacementEffect replacementEffect, SpellAbility effectSA, GameEntity affected, String question) {
            String src = replacementEffect == null ? "null"
                : ws48CardName(replacementEffect.getHostCard());
            return "o0".equals(broker.choose("replacement_effect", player, java.util.List.of(
                "WS48:REPL:apply=true:src=" + ws48Enc(src)
                    + ":affected=" + ws48Enc(affected == null ? "null" : ws48EntityRef(affected))
                    + ":q=" + ws48Enc(ws48Clip(question, 160)),
                "WS48:REPL:apply=false:src=" + ws48Enc(src)
                    + ":affected=" + ws48Enc(affected == null ? "null" : ws48EntityRef(affected))
                    + ":q=" + ws48Enc(ws48Clip(question, 160)))));
        }""", "confirmReplacementEffect")
    rep("""        public ReplacementEffect chooseSingleReplacementEffect(List<ReplacementEffect> possibleReplacers) {
            return broker.chooseObject("chooseSingleReplacementEffect", player, possibleReplacers, false);
        }""", REPL_SINGLE_NEW, "chooseSingleReplacementEffect")
    rep("""        public List<SpellAbility> orderSimultaneousSa(List<SpellAbility> activePlayerSAs) {
            if (activePlayerSAs == null || activePlayerSAs.size() <= 1) {
                broker.recordAutomatic("orderSimultaneousSa:ZERO_OR_ONE");
                return activePlayerSAs;
            }
            throw failClosed("orderSimultaneousSa:MULTI_ORDER");
        }

        @Override
        public void orderAndPlaySimultaneousSa(List<SpellAbility> activePlayerSAs) {
            if (activePlayerSAs == null || activePlayerSAs.isEmpty()) {
                broker.recordAutomatic("orderAndPlaySimultaneousSa:EMPTY");
                return;
            }
            throw failClosed("orderAndPlaySimultaneousSa");
        }""", TRIGGER_ORDER_NEW, "trigger order")
    rep("""        public boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect) {
            throw failClosed("payManaCost");
        }

        @Override
        public boolean applyManaToCost(ManaCostBeingPaid toPay, SpellAbility ability, String prompt, ManaConversionMatrix matrix, boolean effect) {
            throw failClosed("applyManaToCost");
        }""", MANA_NEW, "mana")
    rep("""        public void declareAttackers(Player attacker, Combat combat) {
            throw failClosed("declareAttackers");
        }

        @Override
        public void declareBlockers(Player defender, Combat combat) {
            throw failClosed("declareBlockers");
        }""", DECLARE_NEW, "declare")
    rep("""        public ImmutablePair<CardCollection, CardCollection> arrangeForScry(CardCollection topN) {
            throw failClosed("arrangeForScry");
        }""", SCRY_NEW, "scry")
    rep("""        public CostDecisionMakerBase getCostDecisionMaker(Player player, SpellAbility ability, boolean effect, String prompt) {
            throw failClosed("getCostDecisionMaker");
        }""", COST_DECISION_NEW, "getCostDecisionMaker")
    rep(TRACE_ANCHOR, TRACE_NEW, "fail-closed trace + null guard")
    rep(EVENTS_ANCHOR, EVENTS_ADD, "event subscription")
    rep(EVENTS_CLASS_ANCHOR, EVENTS_CLASS_ADD, "event recorder")
    rep(EOF_TYPED_ANCHOR, EOF_TYPED_NEW, "typed EOF fail-closed")
    rep(TERMINATION_HELPERS_ANCHOR, TERMINATION_HELPERS_ADD, "R1c terminal emitter")
    rep(TERM_CATCH_OLD, TERM_CATCH_NEW, "R1c unexpected-exception terminal report")
    rep(TERM_EMIT_OLD, TERM_EMIT_NEW, "R1c guarded terminal emission")
    rep(TERM_HOOK_OLD, TERM_HOOK_NEW, "R1c shutdown-hook last-resort report")
    # Collapse doubled @Override (original anchors exclude the annotation line
    # while replacement bodies include it).
    while "        @Override\n        @Override\n" in p:
        p = p.replace("        @Override\n        @Override\n", "        @Override\n")
    args.provider.write_text(p, encoding="utf-8")

    required_state = ["ws48SemanticOf", "ws48CommanderOf", "ws48SemanticOfSpell",
                      "ws48FinalizeLoadedCombatBands"]
    missing_state = [x for x in required_state if x not in s]
    if missing_state:
        raise SystemExit(f"WS48_OVERLAY_INCOMPLETE_STATE:{missing_state}")
    required = [
        "WS48:ACT:host=", "WS48:ABILITY:host=",
        "WS48:TARGET:tgt=", "WS48:MODE:api=", "WS48:NUM:n=",
        "WS48:COLOR:color=", "WS48:BOOL:val=", "WS48:REPL:apply=",
        "WS48:ORDER:order=", "WS48:MANA:src=", "WS48:ATTACK:attacker=",
        "WS48:BLOCK:blocker=",         "WS48:SCRY:top=", "Ws48NativeEvents",
        "announceRequirements", "CombatUtil.canAttack", "CombatUtil.canBlock",
        "costVisit:CostTap", "costVisit:CostAddMana", "costVisit:CostPayLife",
        "ws48EmitResult", "WS48_NO_RESULT_AT_SHUTDOWN",
    ]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS48_OVERLAY_INCOMPLETE:{missing}")
    print("WS48_BEHAVIOR_PROVIDER_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())

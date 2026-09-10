#!/usr/bin/env python3
"""WS50 decision-sequence provider overlay v1 (WS50-owned, qualification-only).

Chained patch applied AFTER candidate-qualification/ws48-forge-v1.0.5/
ws48_behavior_provider_overlay.py onto the ephemeral generated GPL-side
provider (Ws23ForgeVerticalProvider.java). Never touches pinned Forge source,
shared scripts, WS48-owned files, or another workstream's files.

Contents (all bounded adapter transport; Rules-Core authority preserved):
1. discard transport upgrade: chooseCardsToDiscardToMaximumHandSize currently
   offers NATIVE_OPTION labels with no stable identity, so no external pilot
   can strictly bind. Replace with per-card WS48:OPT labels projected from
   the engine's own hand (same pattern as the WS48 chooseCardsForEffect
   transport). Zero/ambiguous cases still fail closed harness-side.
2. per-frame decision metadata (additive DECISION_FRAME payload fields only;
   old drivers ignore unknown fields):
   - frame_seq: engine decision sequence number (Broker.decisionSeq)
   - cancel_offered: whether an engine-offered decline option (PASS / SKIP /
     DONE / NONE) is present in this frame's native option set
   - rng: {effective_seed} from COMMANDER_LAB_FORGE_RULES_SEED
   - state: sessionSnapshot at frame time (observable state fingerprint input)
   - observations: per-principal redacted views (own hand identities iff the
     native CardView marks them visible to that viewer; opponent hands and
     libraries as counts only; public zones with face-down protection) plus
     sha256 fingerprints per viewer.

Label grammar reuse: WS48:OPT:opt=<cardRef> (same as WS48 overlay).
"""
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"WS50_OVERLAY_ANCHOR:{label}:expected=1:found={n}")
    return text.replace(old, new, 1)


DISCARD_OLD = """        public CardCollectionView chooseCardsToDiscardToMaximumHandSize(int numDiscard) {
            int ws25Count = numDiscard;
            java.util.List<Card> ws25Remaining = new java.util.ArrayList<>(player.getCardsIn(ZoneType.Hand));
            if (ws25Count < 0 || ws25Count > ws25Remaining.size()) throw failClosed("discardToMaximumHandSize:COUNT_OUT_OF_RANGE");
            CardCollection ws25Chosen = new CardCollection();
            for (int ws25Index = 0; ws25Index < ws25Count; ws25Index++) {
                Card ws25Card = broker.chooseObject("discardToMaximumHandSize", player, ws25Remaining, false);
                if (!ws25Remaining.remove(ws25Card)) throw failClosed("WS25_CARD_SELECTION_STALE");
                ws25Chosen.add(ws25Card);
            }
            return ws25Chosen;
        }"""

DISCARD_NEW = """        public CardCollectionView chooseCardsToDiscardToMaximumHandSize(int numDiscard) {
            ws48Milestone("chooseCardsToDiscardToMaximumHandSize:ENTERED");
            java.util.List<Card> ws50Remaining = new java.util.ArrayList<>(player.getCardsIn(ZoneType.Hand));
            if (numDiscard < 0 || numDiscard > ws50Remaining.size()) throw failClosed("discardToMaximumHandSize:COUNT_OUT_OF_RANGE");
            CardCollection ws50Chosen = new CardCollection();
            for (int ws50Index = 0; ws50Index < numDiscard; ws50Index++) {
                java.util.List<String> ws50Labels = new java.util.ArrayList<>();
                for (Card ws50Card : ws50Remaining) ws50Labels.add("WS48:OPT:opt=" + ws48Enc(ws48CardRef(ws50Card)));
                Card ws50Card = ws50Remaining.get(ws48Choose("discardToMaximumHandSize", player, ws50Labels));
                if (!ws50Remaining.remove(ws50Card)) throw failClosed("WS50_CARD_SELECTION_STALE");
                ws50Chosen.add(ws50Card);
            }
            return ws50Chosen;
        }"""

STATIC_HELPERS_ANCHOR = "    static String esc(String s) {"

STATIC_HELPERS_ADD = """    static String ws50Sha(String v) {
            try {
                java.security.MessageDigest ws50md = java.security.MessageDigest.getInstance("SHA-256");
                byte[] ws50raw = ws50md.digest(v.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                StringBuilder ws50sb = new StringBuilder();
                for (byte ws50b : ws50raw) ws50sb.append(String.format(java.util.Locale.ROOT, "%02x", ws50b));
                return ws50sb.toString();
            } catch (Exception e) { throw new RuntimeException(e); }
        }

        static boolean ws50CardVisibleTo(Card c, Player viewer) {
            return c.getView().canBeShownTo(viewer.getView())
                    && c.getView().canFaceDownBeShownTo(viewer.getView());
        }

        static String ws50ZoneCards(Game game, Player viewer, ZoneType zone) {
            StringBuilder ws50b = new StringBuilder("[");
            boolean ws50first = true;
            for (Card ws50c : game.getCardsIn(zone)) {
                if (!ws50first) ws50b.append(',');
                ws50first = false;
                ws50b.append("{\\"id\\":").append(ws50c.getId())
                        .append(",\\"face_down\\":").append(ws50c.isFaceDown());
                if (ws50CardVisibleTo(ws50c, viewer)) {
                    ws50b.append(",\\"name\\":").append(esc(ws48CardName(ws50c)));
                }
                ws50b.append('}');
            }
            return ws50b.append(']').toString();
        }

        static String ws50Observation(Game game, Player viewer) {
            StringBuilder ws50hands = new StringBuilder("[");
            for (int ws50i = 0; ws50i < game.getPlayers().size(); ws50i++) {
                Player ws50owner = game.getPlayers().get(ws50i);
                if (ws50i > 0) ws50hands.append(',');
                ws50hands.append("{\\"owner\\":").append(esc(ws48StaticPid(game, ws50owner)))
                        .append(",\\"count\\":").append(ws50owner.getCardsIn(ZoneType.Hand).size())
                        .append(",\\"cards\\":[");
                boolean ws50first = true;
                for (Card ws50c : ws50owner.getCardsIn(ZoneType.Hand)) {
                    if (!ws50CardVisibleTo(ws50c, viewer)) continue;
                    if (!ws50first) ws50hands.append(',');
                    ws50first = false;
                    ws50hands.append("{\\"id\\":").append(ws50c.getId())
                            .append(",\\"name\\":").append(esc(ws48CardName(ws50c))).append('}');
                }
                ws50hands.append("]}");
            }
            ws50hands.append(']');
            StringBuilder ws50libs = new StringBuilder("[");
            for (int ws50i = 0; ws50i < game.getPlayers().size(); ws50i++) {
                Player ws50owner = game.getPlayers().get(ws50i);
                if (ws50i > 0) ws50libs.append(',');
                ws50libs.append("{\\"owner\\":").append(esc(ws48StaticPid(game, ws50owner)))
                        .append(",\\"count\\":").append(ws50owner.getCardsIn(ZoneType.Library).size()).append('}');
            }
            ws50libs.append(']');
            return "{\\"viewer\\":" + esc(ws48StaticPid(game, viewer))
                    + ",\\"hands\\":" + ws50hands
                    + ",\\"libraries\\":" + ws50libs
                    + ",\\"battlefield\\":" + ws50ZoneCards(game, viewer, ZoneType.Battlefield)
                    + ",\\"graveyard\\":" + ws50ZoneCards(game, viewer, ZoneType.Graveyard)
                    + ",\\"exile\\":" + ws50ZoneCards(game, viewer, ZoneType.Exile)
                    + ",\\"command\\":" + ws50ZoneCards(game, viewer, ZoneType.Command)
                    + ",\\"stack\\":" + ws50ZoneCards(game, viewer, ZoneType.Stack) + "}";
        }

        static String ws50AllObservations(Game game) {
            StringBuilder ws50b = new StringBuilder("[");
            for (int ws50i = 0; ws50i < game.getPlayers().size(); ws50i++) {
                Player ws50viewer = game.getPlayers().get(ws50i);
                if (ws50i > 0) ws50b.append(',');
                String ws50view = ws50Observation(game, ws50viewer);
                ws50b.append("{\\"viewer\\":").append(esc(ws48StaticPid(game, ws50viewer)))
                        .append(",\\"fingerprint\\":").append(esc(ws50Sha(ws50view)))
                        .append(",\\"view\\":").append(esc(ws50view)).append('}');
            }
            return ws50b.append(']').toString();
        }

        static String ws50RngIdentity() {
            String ws50seed = System.getenv("COMMANDER_LAB_FORGE_RULES_SEED");
            return "{\\"effective_seed\\":" + esc(ws50seed == null ? "" : ws50seed) + "}";
        }

        static boolean ws50CancelOffered(java.util.List<String> labels) {
            for (String ws50l : labels) {
                if (ws50l.equals("PASS") || ws50l.equals("WS48:OPT:NONE")
                        || ws50l.contains(":SKIP") || ws50l.endsWith(":DONE")
                        || ws50l.equals("WS48:TARGET:DONE") || ws50l.equals("WS48:OPT:DONE")) return true;
            }
            return false;
        }

""" + STATIC_HELPERS_ANCHOR

CHOOSE_OLD = """        String choose(String kind, Player actor, java.util.List<String> labels) {
            long seq = ++decisionSeq;
            String did = "d" + seq;"""

CHOOSE_NEW = """        String choose(String kind, Player actor, java.util.List<String> labels) {
            long seq = ++decisionSeq;
            String did = "d" + seq;
            String ws50obs = "[]";
            String ws50state = "null";
            try {
                Game ws50game = actor.getGame();
                if (ws50game != null) {
                    ws50obs = ws50AllObservations(ws50game);
                    ws50state = sessionSnapshot(ws50game);
                }
            } catch (Throwable ws50t) {
                ws50obs = "[{\\"viewer\\":\\"PX\\",\\"fingerprint\\":\\"UNAVAILABLE\\",\\"view\\":\\"\\"}]";
            }"""

OPTS_OLD = """            out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"DECISION_FRAME\\""
                + ",\\"request_id\\":" + esc(did)
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"actor_id\\":" + esc(actor.getName())
                + ",\\"state_revision\\":" + revision
                + ",\\"payload\\":{\\"decision_id\\":" + esc(did)
                + ",\\"decision_kind\\":" + esc(kind)
                + ",\\"options_digest\\":" + esc(digest(ids))
                + ",\\"options\\":[" + opts + "]}}");"""

OPTS_NEW = """            out.println("{\\"protocol\\":" + esc(PROTOCOL)
                + ",\\"message_type\\":\\"DECISION_FRAME\\""
                + ",\\"request_id\\":" + esc(did)
                + ",\\"session_id\\":" + esc(SESSION_ID)
                + ",\\"actor_id\\":" + esc(actor.getName())
                + ",\\"state_revision\\":" + revision
                + ",\\"payload\\":{\\"decision_id\\":" + esc(did)
                + ",\\"decision_kind\\":" + esc(kind)
                + ",\\"frame_seq\\":" + seq
                + ",\\"cancel_offered\\":" + ws50CancelOffered(labels)
                + ",\\"rng\\":" + ws50RngIdentity()
                + ",\\"state_snapshot\\":" + esc(ws50state)
                + ",\\"state_fingerprint\\":" + esc(ws50Sha(ws50state))
                + ",\\"observations\\":" + ws50obs
                + ",\\"options_digest\\":" + esc(digest(ids))
                + ",\\"options\\":[" + opts + "]}}");"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", type=Path, required=True)
    args = ap.parse_args()
    p = args.provider.read_text(encoding="utf-8")
    # Require the WS48 overlay first (chained patch, WS48 files untouched).
    for marker in ("WS48:ATTACK:attacker=", "ws48FinalizeDeclaredBands",
                   "WS48_UNSUPPORTED_DISCRETIONARY_DECISION",
                   "chooseCardsToDiscardToMaximumHandSize(int numDiscard)"):
        if marker not in p:
            raise SystemExit(f"WS50_OVERLAY_PREREQ_MISSING:{marker}")
    p = once(p, DISCARD_OLD, DISCARD_NEW, "discard labeled transport")
    p = once(p, STATIC_HELPERS_ANCHOR, STATIC_HELPERS_ADD, "ws50 static helpers")
    p = once(p, CHOOSE_OLD, CHOOSE_NEW, "ws50 frame capture")
    p = once(p, OPTS_OLD, OPTS_NEW, "ws50 frame payload")
    args.provider.write_text(p, encoding="utf-8")
    required = ["ws50AllObservations", "ws50RngIdentity", "ws50CancelOffered",
                "frame_seq", "cancel_offered", "observations", "state_fingerprint",
                "WS48:OPT:opt=", "chooseCardsToDiscardToMaximumHandSize:ENTERED"]
    missing = [x for x in required if x not in p]
    if missing:
        raise SystemExit(f"WS50_OVERLAY_INCOMPLETE:{missing}")
    print("WS50_DECISION_SEQUENCE_PROVIDER_OVERLAY_V1=PASS")


if __name__ == "__main__":
    raise SystemExit(main())

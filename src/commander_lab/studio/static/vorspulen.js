"use strict";
// Fast-forward ("Vorspulen") for a human seat. Owner decision 2026-11-17: while it is on, the page
// may answer a priority question of the human with exactly one thing, the pass option the engine
// itself offered (the option the opt-in auto-pass sends too). Every other decision of the human
// stops it and is never answered here. The page decides no rule: it reads only what the engine
// published (decision class, offered options, whose turn it is, the stack) and sends nothing but
// the engine's own pass option.
const StudioFastForward = (() => {
  function activeSeat(pilotState) {
    const players = Array.isArray(pilotState.players) ? pilotState.players : [];
    if (!pilotState.active_player_id) return null;
    const owner = players.find((player) => player.player_id === pilotState.active_player_id);
    return owner && Number.isInteger(owner.seat) ? owner.seat : null;
  }
  function stackName(item) { return item && item.face_down ? "verdeckt" : (item && item.name) || "?"; }

  // pending: the pending decision of the human as the server publishes it.
  // context: { startTurn, stopOnOpponentStack, labelOf } (labelOf names a decision class).
  // Returns { action: "pass", optionId } or { action: "stop", reason }.
  function verdict(pending, context) {
    const labelOf = (context && context.labelOf) || ((value) => value);
    if (!pending || pending.decision_class !== "priority") {
      const cls = pending ? labelOf(pending.decision_class || "choice") : "?";
      return { action: "stop", reason: `Entscheidung „${cls}“: die triffst du selbst` };
    }
    const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
    const pass = options.find((option) => option.option_type === "pass_priority");
    if (!pass) return { action: "stop", reason: "die Engine bietet keine Pass-Option an" };
    const state = pending.pilot_state || {};
    const active = activeSeat(state);
    if (active === null) return { action: "stop", reason: "der Zugbesitzer ist nicht bekannt" };
    const startTurn = context && Number.isInteger(context.startTurn) ? context.startTurn : null;
    if (active === pending.seat && (startTurn === null || state.turn_number !== startTurn)) {
      return { action: "stop", reason: "dein Zug beginnt" };
    }
    if (context && context.stopOnOpponentStack) {
      const stack = Array.isArray(state.stack) ? state.stack : [];
      const foreign = stack.find((item) => !item || item.controller_id !== pending.actor_id);
      if (foreign !== undefined) return { action: "stop", reason: `Gegner-Objekt auf dem Stack (${stackName(foreign)})` };
    }
    return { action: "pass", optionId: pass.option_id };
  }
  return { verdict };
})();
if (typeof module !== "undefined") module.exports = StudioFastForward;

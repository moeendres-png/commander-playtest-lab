"use strict";
// The one pass element ("Pass" / "Continue" / "To my turn") for a human seat (#1662). While a run
// is on, the page may answer a priority question of the human with exactly one thing, the
// pass_priority option the engine itself offered. Every other decision of the human stops the run
// and is never answered here. The page decides no rule: it reads only what the engine published
// (decision class, offered options, whose turn it is, the stack) and sends nothing but the
// engine's own pass option. Buttons and keys go through shortcutAction, so both take one path.
const StudioFastForward = (() => {
  function activeSeat(pilotState) {
    const players = Array.isArray(pilotState.players) ? pilotState.players : [];
    if (!pilotState.active_player_id) return null;
    const owner = players.find((player) => player.player_id === pilotState.active_player_id);
    return owner && Number.isInteger(owner.seat) ? owner.seat : null;
  }
  function stackName(item) { return item && item.face_down ? "verdeckt" : (item && item.name) || "?"; }

  // pending: the pending decision of the human as the server publishes it.
  // context: { startTurn, stopOnOpponentStack, labelOf }
  // One run ("continue" / "to my turn") passes only on priority questions and stops at: any
  // non-priority question, the start of my own turn, and (stopOnOpponentStack) an opponent object
  // on the stack. Returns { action: "pass", optionId } or { action: "stop", reason }; optionId is
  // always the pass_priority option the engine offered, never anything else.
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
    const stack = Array.isArray(state.stack) ? state.stack : [];
    if (active === pending.seat && (startTurn === null || state.turn_number !== startTurn)) {
      return { action: "stop", reason: "dein Zug beginnt" };
    }
    if (context && context.stopOnOpponentStack) {
      const foreign = stack.find((item) => !item || item.controller_id !== pending.actor_id);
      if (foreign !== undefined) return { action: "stop", reason: `Gegner-Objekt auf dem Stack (${stackName(foreign)})` };
    }
    return { action: "pass", optionId: pass.option_id };
  }

  // Pure keyboard-shortcut mapping for live human priority / fast-forward (no rules, no DOM).
  function shortcutAction(key, shiftKey) {
    if (key === " ") return { kind: "pass_once" };
    if (key === "Enter") {
      if (shiftKey) {
        return {
          kind: "fast_forward",
          stopOnOpponentStack: false,
          label: "To my turn"
        };
      }
      return {
        kind: "fast_forward",
        stopOnOpponentStack: true,
        label: "Continue"
      };
    }
    return null;
  }

  return { verdict, shortcutAction };
})();
if (typeof module !== "undefined") module.exports = StudioFastForward;

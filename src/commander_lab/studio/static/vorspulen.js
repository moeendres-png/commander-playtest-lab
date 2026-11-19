"use strict";
// Fast-forward ("Vorspulen") for a human seat. Owner decision 2026-11-17: while it is on, the page
// may answer a priority question of the human with exactly one thing, the pass option the engine
// itself offered (the option the opt-in auto-pass sends too). Every other decision of the human
// stops it and is never answered here. The page decides no rule: it reads only what the engine
// published (decision class, offered options, whose turn it is, the stack) and sends nothing but
// the engine's own pass option.
const StudioFastForward = (() => {
  const MODES = {
    until_my_turn: "Bis zu meinem Zug",
    until_end_of_turn: "Bis Zugende",
    until_stack_resolves: "Bis Stapel-Eintrag aufgelöst"
  };

  function activeSeat(pilotState) {
    const players = Array.isArray(pilotState.players) ? pilotState.players : [];
    if (!pilotState.active_player_id) return null;
    const owner = players.find((player) => player.player_id === pilotState.active_player_id);
    return owner && Number.isInteger(owner.seat) ? owner.seat : null;
  }
  function stackName(item) { return item && item.face_down ? "verdeckt" : (item && item.name) || "?"; }
  function modeLabel(mode) { return MODES[mode] || MODES.until_my_turn; }

  // pending: the pending decision of the human as the server publishes it.
  // context: { mode, startTurn, stopOnOpponentStack, watchStackObjectId, labelOf }
  //   mode: "until_my_turn" (default) | "until_end_of_turn" | "until_stack_resolves"
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
    const rawMode = context && context.mode !== undefined && context.mode !== null ? context.mode : "until_my_turn";
    if (!(rawMode in MODES)) return { action: "stop", reason: "unbekannter Vorspul-Modus" };
    const mode = rawMode;
    const startTurn = context && Number.isInteger(context.startTurn) ? context.startTurn : null;
    const stack = Array.isArray(state.stack) ? state.stack : [];

    if (mode === "until_end_of_turn") {
      if (startTurn === null || !Number.isInteger(state.turn_number)) {
        return { action: "stop", reason: "der aktuelle Zug ist nicht bekannt" };
      }
      if (state.turn_number !== startTurn) {
        return { action: "stop", reason: "der Zug hat gewechselt" };
      }
      if (context && context.stopOnOpponentStack) {
        const foreign = stack.find((item) => !item || item.controller_id !== pending.actor_id);
        if (foreign !== undefined) return { action: "stop", reason: `Gegner-Objekt auf dem Stack (${stackName(foreign)})` };
      }
      return { action: "pass", optionId: pass.option_id };
    }

    if (mode === "until_stack_resolves") {
      if (!stack.length) return { action: "stop", reason: "der Stapel ist leer" };
      const watchId = context && typeof context.watchStackObjectId === "string" && context.watchStackObjectId
        ? context.watchStackObjectId
        : null;
      if (watchId !== null) {
        const stillThere = stack.some((item) => item && item.object_id === watchId);
        if (!stillThere) return { action: "stop", reason: "beobachteter Stapel-Eintrag wurde aufgelöst" };
        const top = stack[0];
        if (!top || top.object_id !== watchId) {
          if (!top || top.controller_id !== pending.actor_id) {
            return { action: "stop", reason: `neues Gegner-Objekt auf dem Stack (${stackName(top)})` };
          }
        }
      } else if (context && context.stopOnOpponentStack) {
        const foreign = stack.find((item) => !item || item.controller_id !== pending.actor_id);
        if (foreign !== undefined) return { action: "stop", reason: `Gegner-Objekt auf dem Stack (${stackName(foreign)})` };
      }
      return { action: "pass", optionId: pass.option_id };
    }

    // Default: "until_my_turn"
    if (active === pending.seat && (startTurn === null || state.turn_number !== startTurn)) {
      return { action: "stop", reason: "dein Zug beginnt" };
    }
    if (context && context.stopOnOpponentStack) {
      const foreign = stack.find((item) => !item || item.controller_id !== pending.actor_id);
      if (foreign !== undefined) return { action: "stop", reason: `Gegner-Objekt auf dem Stack (${stackName(foreign)})` };
    }
    return { action: "pass", optionId: pass.option_id };
  }
  return { MODES, modeLabel, verdict };
})();
if (typeof module !== "undefined") module.exports = StudioFastForward;

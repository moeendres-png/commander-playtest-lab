"use strict";
// Board clicks for a human seat. The page lets the human answer an engine decision by clicking a
// card or a player field instead of a line of the option list. This file only maps what the rules
// engine published: it takes the pending decision (legal_options plus pilot_state) and says which
// board object belongs to which offered option. It decides no rule. A card or player is clickable
// only if an offered option points at it, a click yields exactly the option_id of an offered
// option, a click without one unique option yields a menu of the offered options or nothing, and
// nothing here ever answers a decision by itself.
//
// Shapes the engine publishes (engine-bridge, XmageFullGamePlayer):
//   priority / mana_payment  option.metadata.source_object_id = the card the action belongs to
//   target / choose_object / choice
//                            option_id = object id = metadata.object_id (a player has no zone)
//   declare_attacker         metadata.object_id = the attacker the engine asks about now,
//                            metadata.defender_id = player or planeswalker; hold_attacker = no attack
//   declare_blocker          metadata.blocker_id = the blocker asked about now,
//                            option_id = metadata.attacker_id
//   trigger_order            metadata.source_object_id = the source of the trigger
// Opponents are published as the alias op-<seat>, while their ids inside options are real
// ids. An opponent is therefore recognised only by the name the engine gave the player
// ("Full Game Seat N", N = seat + 1) in the option's own name or label, and only if the seat exists.
const StudioBoardClick = (() => {
  const SEAT_NAME = /^Full Game Seat (\d+)$/;
  const PLACED_ZONES = ["battlefield", "hand", "stack", "command", "graveyard", "exile"];
  const OBJECT_CLASSES = ["target", "choose_object", "choice"];
  const NO_OBJECT_TYPES = ["pass_priority", "hold_attacker", "cancel_mana_payment", "mana_pool"];

  const text = (value) => (typeof value === "string" && value ? value : null);
  const meta = (option) => (option && option.metadata && typeof option.metadata === "object" ? option.metadata : {});
  const optionsOf = (pending) => (pending && Array.isArray(pending.legal_options) ? pending.legal_options : []);
  const list = (value) => (Array.isArray(value) ? value : []);

  // object id -> { zone, seat } for everything the actor may see on the table.
  function indexObjects(pilotState) {
    const found = Object.create(null);
    const state = pilotState && typeof pilotState === "object" ? pilotState : {};
    const add = (items, zone, seat) => {
      for (const item of list(items)) {
        const id = item && text(item.object_id);
        if (id && !(id in found)) found[id] = { zone, seat };
      }
    };
    for (const player of list(state.players)) {
      if (!player || !Number.isInteger(player.seat)) continue;
      add(player.battlefield, "battlefield", player.seat);
      add(player.hand, "hand", player.seat);
      add(player.command, "command", player.seat);
      add(player.graveyard, "graveyard", player.seat);
      add(player.exile, "exile", player.seat);
    }
    add(state.stack, "stack", null);
    return found;
  }

  // The seat of a player named by an offered option, or null when that is not certain.
  function seatOfPlayer(pending, id, name) {
    const players = list(pending.pilot_state && pending.pilot_state.players);
    const known = (seat) => players.some((player) => player && player.seat === seat);
    if (id && id === text(pending.actor_id) && known(pending.seat)) return pending.seat;
    const named = SEAT_NAME.exec(name || "");
    if (!named) return null;
    const seat = Number(named[1]) - 1;
    return known(seat) ? seat : null;
  }

  function entryFor(map, key, role) {
    if (!map[key]) map[key] = { role, optionIds: [] };
    return map[key];
  }

  // Everything the page needs to draw and to answer clicks for one pending decision:
  //   kind     what sort of decision (priority, mana_payment, target, attacker, blocker, trigger_order)
  //            or "none" when the board has nothing to click (mulligan, yes/no, numbers, modes, ...)
  //   mode     immediate (a click answers at once), staged (clicks select, the page confirms),
  //            info (cards are only highlighted)
  //   objects  object id -> { role, zone, seat, optionIds }  (cards that are on the visible board)
  //   seats    seat -> { role, optionIds }  (player fields)
  //   asked    object id of the creature the engine asks about now (attack, block), else null
  //   listOnly option ids that have no place on the board; they stay in the option list
  //   loose    option_type "no object" actions (pass, do not attack, cancel payment): panel/bar buttons
  function build(pending) {
    const none = { kind: "none", mode: "info", decisionId: pending && typeof pending === "object" && pending.decision_id ? pending.decision_id : null, objects: Object.create(null), seats: Object.create(null), asked: null, listOnly: [], loose: [], byOption: Object.create(null) };
    if (!pending || typeof pending !== "object") return none;
    const options = optionsOf(pending);
    const cls = pending.decision_class;
    const ctx = pending.context && typeof pending.context === "object" ? pending.context : {};
    if (!options.length || list(ctx.numeric_legs).length || ctx.numeric_min !== undefined || ctx.numeric_max !== undefined) return none;
    const minSel = Number(pending.minimum_selections ?? 0);
    const maxSel = Number(pending.maximum_selections ?? 0);
    const index = indexObjects(pending.pilot_state);
    const model = Object.assign(none, { decisionId: pending.decision_id || null });
    const ordering = (cls === "trigger_order" || cls === "order") && !(minSel === 1 && maxSel === 1);
    model.mode = ordering ? "info" : (minSel === 1 && maxSel === 1 ? "immediate" : "staged");

    // Where one option belongs: { objectId } for a card, { seat } for a player, or null.
    const place = (option) => {
      const data = meta(option);
      const optionId = text(option.option_id);
      if (!optionId) return null;
      if (cls === "priority") {
        const source = text(data.source_object_id);
        return source ? { objectId: source, role: "action" } : null;
      }
      if (cls === "mana_payment") {
        const source = text(data.source_object_id) || text(data.object_id);
        return source ? { objectId: source, role: "action" } : null;
      }
      if (cls === "trigger_order" || cls === "order") {
        const source = text(data.source_object_id);
        return source ? { objectId: source, role: "source" } : null;
      }
      if (cls === "declare_attacker") {
        if (option.option_type === "hold_attacker") return null;
        const defender = text(data.defender_id);
        if (!defender) return null;
        if (defender in index && index[defender].zone === "battlefield") return { objectId: defender, role: "defender" };
        const label = text(option.label) || "";
        const attackerName = text(data.name) || "";
        const rest = attackerName && label.startsWith(`${attackerName} attacks `) ? label.slice(attackerName.length + " attacks ".length) : "";
        const seat = seatOfPlayer(pending, defender, rest);
        return seat === null ? null : { seat, role: "defender" };
      }
      if (cls === "declare_blocker") {
        const attacker = text(data.attacker_id);
        return attacker && attacker === optionId ? { objectId: attacker, role: "block-target" } : null;
      }
      if (OBJECT_CLASSES.includes(cls)) {
        const objectId = text(data.object_id);
        if (!objectId || objectId !== optionId) return null; // the click must send exactly this object
        if (objectId in index) return { objectId, role: "target" };
        if (!text(data.zone)) {
          const seat = seatOfPlayer(pending, objectId, text(data.name) || text(option.label));
          if (seat !== null) return { seat, role: "target" };
        }
        return null;
      }
      return null;
    };

    if (cls === "priority") model.kind = "priority";
    else if (cls === "mana_payment") model.kind = "mana_payment";
    else if (cls === "declare_attacker") model.kind = "attacker";
    else if (cls === "declare_blocker") model.kind = "blocker";
    else if (cls === "trigger_order" || cls === "order") model.kind = "trigger_order";
    else if (OBJECT_CLASSES.includes(cls)) model.kind = "target";
    else return none;

    // the creature the engine asks about now
    if (model.kind === "attacker") {
      const ids = new Set(options.map((option) => text(meta(option).object_id)));
      if (ids.size === 1) model.asked = [...ids][0];
    } else if (model.kind === "blocker") {
      const ids = new Set(options.map((option) => text(meta(option).blocker_id)));
      if (ids.size === 1) model.asked = [...ids][0];
    }
    if (model.asked !== null && !(model.asked in index && index[model.asked].zone === "battlefield")) model.asked = null;

    for (const option of options) {
      const optionId = text(option.option_id);
      if (!optionId) continue;
      const where = place(option);
      let placed = false;
      if (where && where.objectId !== undefined) {
        const found = index[where.objectId];
        if (found && PLACED_ZONES.includes(found.zone)) {
          const entry = entryFor(model.objects, where.objectId, where.role);
          entry.zone = found.zone; entry.seat = found.seat;
          entry.optionIds.push(optionId);
          placed = true;
        }
      } else if (where && where.seat !== undefined) {
        entryFor(model.seats, String(where.seat), where.role).optionIds.push(optionId);
        placed = true;
      }
      if (placed) model.byOption[optionId] = true;
      else if (NO_OBJECT_TYPES.includes(option.option_type)) model.loose.push(optionId);
      else model.listOnly.push(optionId);
    }

    if (model.kind === "attacker" || model.kind === "blocker") {
      // the asked creature: every option of the decision belongs to it (attack/hold, or the block list)
      if (model.asked !== null && model.kind === "attacker") {
        const entry = entryFor(model.objects, model.asked, "asked");
        entry.zone = "battlefield"; entry.seat = index[model.asked].seat;
        entry.optionIds = options.map((option) => text(option.option_id)).filter(Boolean);
      } else if (model.asked !== null) {
        const entry = entryFor(model.objects, model.asked, "asked");
        entry.zone = "battlefield"; entry.seat = index[model.asked].seat;
        entry.optionIds = [];
      }
    }
    return model;
  }

  const optionOf = (pending, optionId) => optionsOf(pending).find((option) => text(option.option_id) === optionId) || null;

  // The answer to a click. target: { type: "object", id } or { type: "seat", seat }.
  //   { action: "send", optionId }    answer the decision with this offered option
  //   { action: "toggle", optionId }  select / unselect this offered option (the page confirms)
  //   { action: "menu", options: [{ optionId, label }] }  several offered options belong here
  //   { action: "none" }              nothing clickable
  function resolve(pending, model, target) {
    const nothing = { action: "none" };
    if (!model || model.kind === "none" || model.mode === "info" || !target) return nothing;
    // a model built for another decision answers nothing, even if an option id is offered by both
    if (!pending || !model.decisionId || model.decisionId !== pending.decision_id) return nothing;
    const entry = target.type === "object" ? model.objects[target.id] : (target.type === "seat" ? model.seats[String(target.seat)] : null);
    if (!entry) return nothing;
    if (entry.role === "asked" && model.kind === "blocker") return nothing; // the blocker only shows who blocks
    // only ids that really are offered options of this very decision
    const offered = entry.optionIds.map((id) => optionOf(pending, id)).filter(Boolean);
    if (!offered.length || offered.length !== entry.optionIds.length) return nothing;
    if (offered.length === 1 && entry.role !== "asked") {
      return { action: model.mode === "immediate" ? "send" : "toggle", optionId: text(offered[0].option_id) };
    }
    return { action: "menu", mode: model.mode, options: offered.map((option) => ({ optionId: text(option.option_id), label: text(option.label) || text(option.option_id) })) };
  }

  // Every option id this model can ever emit (used by the tests and by the page as a last guard).
  function emittable(model) {
    const ids = new Set();
    for (const key of Object.keys(model.objects)) for (const id of model.objects[key].optionIds) ids.add(id);
    for (const key of Object.keys(model.seats)) for (const id of model.seats[key].optionIds) ids.add(id);
    for (const id of model.loose) ids.add(id);
    return [...ids];
  }

  return { build, resolve, emittable, indexObjects, seatOfPlayer };
})();
if (typeof module !== "undefined") module.exports = StudioBoardClick;

"use strict";
// Play P1a pure UI helpers: stack rail projection and own combat answer ledger.
// Strictly read-only projection of engine-published pilot_state and own submitted answers.
// Never computes any game rule, legality, combat damage, or commander tax.
const StudioPlayP1a = (() => {
  const OWN_COMBAT_LABEL =
    "Eigener Kampf-Zwischenstand (eigene Angaben, kein Engine-Kampfzustand)";
  const COMBAT_STEPS = new Set([
    "begin_combat", // XMage PhaseStep.BEGIN_COMBAT, lower-cased by the bridge
    "declare_attackers",
    "declare_blockers",
    "first_combat_damage",
    "combat_damage",
    "end_combat"
  ]);

  const text = (value) => (typeof value === "string" && value ? value : null);
  const list = (value) => (Array.isArray(value) ? value : []);

  function stripMarkup(raw) {
    return String(raw || "").replace(/<[^>]*>/g, "");
  }

  function indexPublished(pilotState, seatNameFn) {
    const players = new Map();
    const objects = new Map();
    const ps = pilotState && typeof pilotState === "object" ? pilotState : {};
    const addZone = (items) => {
      for (const item of list(items)) {
        const id = item && text(item.object_id);
        if (!id || objects.has(id)) continue;
        objects.set(id, item.face_down ? "verdeckt" : text(item.name) || "?");
      }
    };
    for (const player of list(ps.players)) {
      if (!player || typeof player !== "object") continue;
      const seat = Number.isInteger(player.seat) ? player.seat : null;
      const pid = text(player.player_id);
      if (pid && seat !== null) players.set(pid, seat);
      addZone(player.battlefield);
      addZone(player.hand);
      addZone(player.command);
      addZone(player.graveyard);
      addZone(player.exile);
    }
    addZone(ps.stack);
    const seatLabel = (seat) =>
      typeof seatNameFn === "function"
        ? seatNameFn(seat)
        : Number.isInteger(seat)
          ? `Sitz ${seat + 1}`
          : "?";
    const resolveId = (id) => {
      if (!id) return null;
      if (objects.has(id)) return objects.get(id);
      if (players.has(id)) return seatLabel(players.get(id));
      return id;
    };
    return { players, seatLabel, resolveId };
  }

  function extractPublishedTargets(item, lookup) {
    if (!item || typeof item !== "object") return [];
    const out = [];
    if (Array.isArray(item.target_names) && item.target_names.length) {
      for (const entry of item.target_names) {
        const name = text(entry);
        if (name) out.push(stripMarkup(name));
      }
      return out;
    }
    if (Array.isArray(item.targets) && item.targets.length) {
      for (const entry of item.targets) {
        if (typeof entry === "string" && entry) {
          out.push(stripMarkup(lookup.resolveId(entry) || entry));
        } else if (entry && typeof entry === "object") {
          if (entry.face_down) {
            out.push("verdeckt");
          } else {
            const direct = text(entry.name) || text(entry.label);
            const resolved =
              direct ||
              lookup.resolveId(text(entry.object_id) || text(entry.player_id) || text(entry.id));
            if (resolved) out.push(stripMarkup(resolved));
          }
        }
      }
      return out;
    }
    if (Array.isArray(item.target_ids) && item.target_ids.length) {
      for (const rawId of item.target_ids) {
        const id = text(rawId);
        if (id) out.push(stripMarkup(lookup.resolveId(id) || id));
      }
    }
    return out;
  }

  // Projects pilotState.stack in published order (index 0 = top of stack).
  // Uses only fields published in pilotState; never derives hidden or unstated targets.
  function buildStackRail(pilotState, seatNameFn) {
    const ps = pilotState && typeof pilotState === "object" ? pilotState : {};
    const stack = list(ps.stack);
    if (!stack.length) return [];
    const lookup = indexPublished(ps, seatNameFn);
    return stack.map((item, index) => {
      const obj = item && typeof item === "object" ? item : {};
      const faceDown = Boolean(obj.face_down);
      const rawName = faceDown ? "verdeckt" : text(obj.name) || "?";
      const isAbility = !faceDown && rawName.startsWith("stack ability");
      const displayName = isAbility
        ? stripMarkup(rawName.replace(/^stack ability \(/, "Fähigkeit: ").replace(/\)$/, ""))
        : stripMarkup(rawName);
      const controllerId = text(obj.controller_id);
      const controllerSeat =
        controllerId && lookup.players.has(controllerId) ? lookup.players.get(controllerId) : null;
      const controllerLabel =
        controllerSeat !== null
          ? lookup.seatLabel(controllerSeat)
          : controllerId
            ? "unbekannt"
            : null;
      const targets = extractPublishedTargets(obj, lookup);
      return {
        position: index + 1,
        isTop: index === 0,
        objectId: text(obj.object_id),
        faceDown,
        name: rawName,
        displayName,
        isAbility,
        controllerId,
        controllerSeat,
        controllerLabel,
        targets,
        targetsPublished: targets.length > 0
      };
    });
  }

  function emptyCombatLedger() {
    return { label: OWN_COMBAT_LABEL, turn: null, step: null, entries: [] };
  }

  function clearOwnCombatLedger(ledger, turnNumber, step) {
    if (!ledger || !Array.isArray(ledger.entries) || !ledger.entries.length) {
      return emptyCombatLedger();
    }
    const turn = Number.isInteger(turnNumber) ? turnNumber : null;
    const stepText = text(step);
    if (turn === null && stepText === null) return emptyCombatLedger();
    if (turn !== null && ledger.turn !== null && turn !== ledger.turn) {
      return emptyCombatLedger();
    }
    if (stepText !== null && !COMBAT_STEPS.has(stepText)) {
      return emptyCombatLedger();
    }
    return {
      label: OWN_COMBAT_LABEL,
      turn: turn !== null ? turn : ledger.turn,
      step: stepText !== null ? stepText : ledger.step,
      entries: ledger.entries.slice()
    };
  }

  // Records only the human's own answers already submitted for declare_attacker / declare_blocker.
  function recordOwnCombatAnswer(ledger, decision, chosenOptionIds, pilotState) {
    const ps =
      (pilotState && typeof pilotState === "object" ? pilotState : null) ||
      (decision && decision.pilot_state && typeof decision.pilot_state === "object"
        ? decision.pilot_state
        : {});
    const turn = Number.isInteger(ps.turn_number) ? ps.turn_number : null;
    const step = text(ps.step);
    const base = clearOwnCombatLedger(ledger, turn, step);
    if (!decision || typeof decision !== "object") return base;
    const cls = decision.decision_class;
    if (cls !== "declare_attacker" && cls !== "declare_blocker") return base;

    const decisionId = text(decision.decision_id);
    const legal = list(decision.legal_options);
    const byId = new Map();
    for (const option of legal) {
      const id = option && text(option.option_id);
      if (id) byId.set(id, option);
    }
    const chosenIds = list(chosenOptionIds)
      .map((id) => text(String(id)))
      .filter(Boolean);
    const matched = chosenIds.map((id) => byId.get(id)).filter(Boolean);

    const nextEntries = base.entries.filter(
      (entry) => !decisionId || entry.decisionId !== decisionId
    );
    if (cls === "declare_attacker") {
      if (!matched.length) {
        nextEntries.push({
          kind: "no_attack",
          decisionId,
          optionId: null,
          text: "greift nicht an"
        });
      } else {
        for (const option of matched) {
          nextEntries.push({
            kind: option.option_type === "hold_attacker" ? "hold_attacker" : "attacker",
            decisionId,
            optionId: text(option.option_id),
            text: stripMarkup(text(option.label) || text(option.option_id) || "?")
          });
        }
      }
    } else if (cls === "declare_blocker") {
      if (!matched.length) {
        const promptText = text(decision.prompt);
        nextEntries.push({
          kind: "no_block",
          decisionId,
          optionId: null,
          text: promptText ? `${stripMarkup(promptText)}: nicht geblockt` : "nicht geblockt"
        });
      } else {
        for (const option of matched) {
          nextEntries.push({
            kind: "blocker",
            decisionId,
            optionId: text(option.option_id),
            text: stripMarkup(text(option.label) || text(option.option_id) || "?")
          });
        }
      }
    }
    return {
      label: OWN_COMBAT_LABEL,
      turn,
      step,
      entries: nextEntries
    };
  }

  // What the own-combat box shows for the frame on screen. The ledger is cleaned up only at the
  // live end (the decision the engine is asking now): looking at an older frame (rewind) must not
  // delete the interim state for good, it only hides the box until the live end is shown again.
  function ownCombatView(ledger, frame, atLiveTail, interactive) {
    const current = ledger && Array.isArray(ledger.entries) ? ledger : emptyCombatLedger();
    if (!atLiveTail) return { ledger: current, visible: false };
    const next = clearOwnCombatLedger(
      current,
      frame && Number.isInteger(frame.turn) ? frame.turn : null,
      frame ? frame.step : null
    );
    return { ledger: next, visible: Boolean(interactive) && next.entries.length > 0 };
  }

  // Text of the auto-pass log line (the line itself is built by the page).
  function autoPassLine(pending, reasonText) {
    const seat = pending && Number.isInteger(pending.seat) ? pending.seat : 0;
    return { seat, tag: `S${seat + 1}`, text: `Auto-Pass (${stripMarkup(reasonText)}): Priorität abgegeben` };
  }

  // Sends one answer of the human and keeps the books about it. io carries the page side:
  //   getPendingDecision(), post(payload) (rejects when the engine refuses), getLedger(),
  //   setLedger(ledger), logAutoPass(line).
  // The decision answered is the one that was pending when the answer was sent (a poll may replace
  // the pending decision while the post is in flight). Ledger and auto-pass line are written only
  // after the post was accepted: a refused answer leaves no trace (the rejection propagates).
  // opts.autoPassReason marks an automatic pass and gets one log line after the accepted post.
  async function submitAnswer(io, payload, opts) {
    const submitted = io.getPendingDecision();
    if (!submitted) return null;
    await io.post(payload);
    io.setLedger(
      recordOwnCombatAnswer(
        io.getLedger(),
        submitted,
        payload && payload.selected_option_ids ? payload.selected_option_ids : [],
        submitted.pilot_state
      )
    );
    const reason = opts && text(opts.autoPassReason);
    if (reason) io.logAutoPass(autoPassLine(submitted, reason));
    return submitted;
  }

  return {
    OWN_COMBAT_LABEL,
    COMBAT_STEPS: [...COMBAT_STEPS],
    buildStackRail,
    emptyCombatLedger,
    recordOwnCombatAnswer,
    clearOwnCombatLedger,
    ownCombatView,
    autoPassLine,
    submitAnswer
  };
})();
if (typeof globalThis !== "undefined") globalThis.StudioPlayP1a = StudioPlayP1a;
if (typeof module !== "undefined") module.exports = StudioPlayP1a;

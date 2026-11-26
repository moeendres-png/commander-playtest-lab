"use strict";
// Always-visible Phase/Step timeline, persistent waiting-seat state,
// 3 named response profiles with fail-safe Interrupt-Table halt evaluation,
// and unified Decision Action Bar with "Nichts mehr zu tun" & Hold-to-Confirm (#1822, #1823).
// Strictly read-only UI projection over engine-published state and legal_options.

const StudioTurnBar = (() => {
  const PHASES = [
    {
      key: "beginning",
      label: "Beginn",
      steps: [
        { key: "untap", label: "Enttappen" },
        { key: "upkeep", label: "Versorgung" },
        { key: "draw", label: "Ziehen" }
      ]
    },
    {
      key: "precombat_main",
      label: "Haupt 1",
      steps: [{ key: "precombat_main", label: "Hauptphase 1" }]
    },
    {
      key: "combat",
      label: "Kampf",
      steps: [
        { key: "begin_combat", label: "Beginn" },
        { key: "declare_attackers", label: "Angreifer" },
        { key: "declare_blockers", label: "Blocker" },
        { key: "first_combat_damage", label: "Erstschlag" },
        { key: "combat_damage", label: "Schaden" },
        { key: "end_combat", label: "Ende" }
      ]
    },
    {
      key: "postcombat_main",
      label: "Haupt 2",
      steps: [{ key: "postcombat_main", label: "Hauptphase 2" }]
    },
    {
      key: "end",
      label: "Ende",
      steps: [
        { key: "end_turn", label: "Endsegment" },
        { key: "cleanup", label: "Aufräumen" }
      ]
    }
  ];

  const KNOWN_STEPS = new Set(PHASES.flatMap((p) => p.steps.map((s) => s.key)));

  const STEP_TO_PHASE = {};
  const STEP_LABELS = {};
  for (const p of PHASES) {
    for (const s of p.steps) {
      STEP_TO_PHASE[s.key] = p.key;
      STEP_LABELS[s.key] = s.label;
    }
  }

  const RESPONSE_PROFILES = {
    full_control: {
      id: "full_control",
      label: "Volle Kontrolle",
      shortHint: "Hält in jedem Prioritätsfenster an.",
      defaultHalts: {
        haltStackNonEmpty: true,
        haltCombat: true,
        haltOwnMain: true,
        haltOpponentEndStep: true,
        haltPlayableOptions: true
      }
    },
    big_moments: {
      id: "big_moments",
      label: "Große Momente halten",
      shortHint: "Hält bei Stapel/Auslösern, Kampf, eigener Hauptphase und gegnerischem Endsegment.",
      defaultHalts: {
        haltStackNonEmpty: true,
        haltCombat: true,
        haltOwnMain: true,
        haltOpponentEndStep: true,
        haltPlayableOptions: true
      }
    },
    auto_pass: {
      id: "auto_pass",
      label: "Auto-Pass",
      shortHint: "Passt Routine-Priorität, hält aber bei markierten Halt-Ereignissen & unbekannten Effekten.",
      defaultHalts: {
        haltStackNonEmpty: true,
        haltCombat: true,
        haltOwnMain: true,
        haltOpponentEndStep: false,
        haltPlayableOptions: true
      }
    }
  };

  function defaultHaltConfig(modeId) {
    const profile = RESPONSE_PROFILES[modeId] || RESPONSE_PROFILES.big_moments;
    return { ...profile.defaultHalts };
  }

  function normKey(raw) {
    return typeof raw === "string" ? raw.trim().toLowerCase() : "";
  }

  function activeSeatFromPilotState(ps) {
    if (!ps || typeof ps !== "object") return null;
    const players = Array.isArray(ps.players) ? ps.players : [];
    if (ps.active_player_id) {
      const found = players.find((p) => p && p.player_id === ps.active_player_id);
      if (found && Number.isInteger(found.seat)) return found.seat;
    }
    return Number.isInteger(ps.active_seat) ? ps.active_seat : null;
  }

  function buildPhaseTimeline(frame) {
    const rawStep = normKey(frame && frame.step);
    const rawPhase = normKey(frame && frame.phase);
    const activePhaseKey = STEP_TO_PHASE[rawStep] || (PHASES.some((p) => p.key === rawPhase) ? rawPhase : null);
    const activeIdx = activePhaseKey ? PHASES.findIndex((p) => p.key === activePhaseKey) : -1;

    const phases = PHASES.map((phase, idx) => {
      const state = activeIdx < 0 ? "upcoming" : idx < activeIdx ? "done" : idx === activeIdx ? "active" : "upcoming";
      return {
        key: phase.key,
        label: phase.label,
        state,
        steps: phase.steps.map((s) => ({
          key: s.key,
          label: s.label,
          active: s.key === rawStep
        }))
      };
    });

    const activeStepLabel = STEP_LABELS[rawStep] || (activeIdx >= 0 ? PHASES[activeIdx].label : "Spielbeginn");
    return {
      turn: frame && Number.isInteger(frame.turn) ? frame.turn : null,
      phaseKey: activePhaseKey,
      stepKey: rawStep || null,
      activeStepLabel,
      phases
    };
  }

  function buildWaitingInfo(frame, pendingDecision, options) {
    const opts = options && typeof options === "object" ? options : {};
    const seatName = typeof opts.seatName === "function" ? opts.seatName : (s) => (s === null || s === undefined ? "?" : `Sitz ${s + 1}`);
    const classLabelOf = typeof opts.classLabelOf === "function" ? opts.classLabelOf : (c) => c || "Entscheidung";
    const humanSeats = Array.isArray(opts.humanSeats) ? opts.humanSeats : [];
    const running = Boolean(opts.running);
    const interactive = Boolean(opts.interactive);

    if (interactive && running && pendingDecision) {
      const waitSeat = Number.isInteger(pendingDecision.seat) ? pendingDecision.seat : null;
      const isHuman = waitSeat !== null && humanSeats.includes(waitSeat);
      const clsLabel = classLabelOf(pendingDecision.decision_class);
      return {
        waitingSeat: waitSeat,
        activeSeat: activeSeatFromPilotState(pendingDecision.pilot_state) ?? (frame ? frame.active_seat : null),
        isHumanWaiting: isHuman,
        badgeLabel: isHuman ? "Du bist gefragt" : `Warten auf ${seatName(waitSeat)}`,
        bannerText: isHuman
          ? `Warten auf dich (${seatName(waitSeat)}) · ${clsLabel}`
          : `Warten auf ${seatName(waitSeat)} · ${clsLabel}`
      };
    }

    if (running && frame) {
      const waitSeat = Number.isInteger(frame.seat) ? frame.seat : frame.active_seat;
      return {
        waitingSeat: waitSeat,
        activeSeat: Number.isInteger(frame.active_seat) ? frame.active_seat : null,
        isHumanWaiting: false,
        badgeLabel: `Warten auf ${seatName(waitSeat)}`,
        bannerText: `Warten auf ${seatName(waitSeat)} · Zug ${frame.turn ?? "?"}`
      };
    }

    if (!running && frame) {
      return {
        waitingSeat: null,
        activeSeat: Number.isInteger(frame.active_seat) ? frame.active_seat : null,
        isHumanWaiting: false,
        badgeLabel: "Partie beendet",
        bannerText: "Aufgezeichnete Partie — Wiedergabe / Nachbetrachtung"
      };
    }

    return {
      waitingSeat: null,
      activeSeat: null,
      isHumanWaiting: false,
      badgeLabel: "Bereit",
      bannerText: "Wähle oder starte eine Partie."
    };
  }

  // Evaluates whether auto-pass MUST halt for `pending` under the selected response mode
  // and Interrupt-Table configuration. Fail-safe: non-priority, missing pilot_state, unknown step,
  // or any matching halt trigger returns `{ action: "stop", reason }`.
  function evaluateResponseProfile(pending, modeId, haltConfig) {
    if (!pending || typeof pending !== "object") {
      return { action: "stop", reason: "keine offene Entscheidung" };
    }
    const mode = modeId in RESPONSE_PROFILES ? modeId : "big_moments";
    if (mode === "full_control") {
      return { action: "stop", reason: "Volle Kontrolle aktiv — jeder Halt bleibt geöffnet" };
    }
    if (pending.decision_class !== "priority") {
      return { action: "stop", reason: "keine Prioritätsabfrage (Entscheidung bleibt beim Menschen)" };
    }
    const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
    const passOpt = options.find((opt) => opt && opt.option_type === "pass_priority");
    if (!passOpt || !passOpt.option_id) {
      return { action: "stop", reason: "keine Pass-Option von der Engine angeboten" };
    }
    const ps = pending.pilot_state;
    if (!ps || typeof ps !== "object") {
      return { action: "stop", reason: "Spielzustand fehlt (fail-safe Halt)" };
    }
    const step = normKey(ps.step);
    if (!step || !KNOWN_STEPS.has(step)) {
      return { action: "stop", reason: `unbekannter Spielschritt „${ps.step || "?"}“ (fail-safe Halt)` };
    }

    const activeSeat = activeSeatFromPilotState(ps);
    const stack = Array.isArray(ps.stack) ? ps.stack : [];
    const halts = Object.assign(defaultHaltConfig(mode), haltConfig && typeof haltConfig === "object" ? haltConfig : {});
    const isOwnTurn = activeSeat !== null && activeSeat === pending.seat;
    const otherOptions = options.filter((opt) => opt && opt.option_type !== "pass_priority");

    // 1. Triggers / spells on the stack (Interrupt-Table top rule)
    if (halts.haltStackNonEmpty && stack.length > 0) {
      const top = stack[0];
      const topName = top && !top.face_down && top.name ? top.name : "Stapel-Eintrag";
      return { action: "stop", reason: `Halt bei Stapel/Auslöser: ${topName}` };
    }

    // 2. Playable cards/abilities available in hand/board
    if (halts.haltPlayableOptions && otherOptions.length > 0) {
      return { action: "stop", reason: `${otherOptions.length} spielbare Aktionen verfügbar` };
    }

    // 3. Combat reaction windows
    if (halts.haltCombat && (step === "begin_combat" || step === "declare_attackers" || step === "declare_blockers" || step === "first_combat_damage" || step === "combat_damage")) {
      return { action: "stop", reason: `Halt im Kampf (${STEP_LABELS[step] || step})` };
    }

    // 4. Own main phase priority
    if (halts.haltOwnMain && isOwnTurn && (step === "precombat_main" || step === "postcombat_main")) {
      return { action: "stop", reason: `Halt in eigener ${STEP_LABELS[step] || "Hauptphase"}` };
    }

    // 5. Opponent End-of-Turn instant window
    if (halts.haltOpponentEndStep && !isOwnTurn && step === "end_turn") {
      return { action: "stop", reason: "Halt im gegnerischen Endsegment" };
    }

    // Mode guard: "big_moments" still waits on opponent spells / combat / playable cards even if
    // individual checkboxes weren't set, and passes ONLY routine empty upkeep/draw/opponent cleanup steps.
    if (mode === "big_moments" && isOwnTurn && stack.length === 0 && (step === "precombat_main" || step === "postcombat_main")) {
      return { action: "stop", reason: "Große Momente halten: eigene Hauptphase" };
    }

    return {
      action: "pass",
      optionId: String(passOpt.option_id),
      reason: RESPONSE_PROFILES[mode].label
    };
  }

  function isCriticalPassWindow(pending, frame) {
    if (!pending || pending.decision_class !== "priority") return false;
    const ps = pending.pilot_state || {};
    const stack = Array.isArray(ps.stack) ? ps.stack : (frame && Array.isArray(frame.stack) ? frame.stack : []);
    if (stack.length > 0) return true;
    const step = normKey(ps.step || (frame && frame.step));
    if (step === "begin_combat" || step === "declare_attackers" || step === "declare_blockers" || step === "combat_damage" || step === "first_combat_damage") {
      return true;
    }
    const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
    const otherCount = options.filter((o) => o && o.option_type !== "pass_priority").length;
    return otherCount > 0;
  }

  function buildPrimaryAction(pending, selectedOptions, frame, opts) {
    if (!pending || typeof pending !== "object") return null;
    const cfg = opts && typeof opts === "object" ? opts : {};
    const dc = String(pending.decision_class || "choice");
    const options = Array.isArray(pending.legal_options) ? pending.legal_options : [];
    const selected = Array.isArray(selectedOptions) ? selectedOptions : [];
    const minSel = Number(pending.minimum_selections ?? 0);
    const maxSel = Number(pending.maximum_selections ?? 0);
    const ps = pending.pilot_state || {};
    const step = normKey(ps.step || (frame && frame.step));
    const stack = Array.isArray(ps.stack) ? ps.stack : (frame && Array.isArray(frame.stack) ? frame.stack : []);
    const activeSeat = activeSeatFromPilotState(ps) ?? (frame ? frame.active_seat : null);
    const isOwnTurn = activeSeat !== null && activeSeat === pending.seat;
    const holdSetting = cfg.holdToConfirm !== false;

    if (dc === "priority") {
      const passOpt = options.find((o) => o && o.option_type === "pass_priority");
      if (!passOpt) return null;
      const otherCount = options.filter((o) => o && o.option_type !== "pass_priority").length;
      const nothingLeft = otherCount === 0;
      const isEndLike = isOwnTurn && stack.length === 0 && (step === "postcombat_main" || step === "end_turn");
      const baseVerb = nothingLeft
        ? (isEndLike ? "Nichts mehr zu tun — Zug beenden" : "Nichts mehr zu tun — Priorität abgeben")
        : (isEndLike ? "Zug weitergeben" : "Priorität abgeben");
      const critical = isCriticalPassWindow(pending, frame);
      return {
        kind: "pass_priority",
        optionId: String(passOpt.option_id),
        label: baseVerb,
        nothingLeft,
        critical,
        requireHold: Boolean(holdSetting && critical),
        disabled: false,
        hintText: holdSetting && critical
          ? "Kritisches Fenster: zum Passen gedrückt halten (oder Leertaste)."
          : nothingLeft
            ? "Keine sinnvolle Aktion mehr angeboten — Weiterklicken gibt Priorität ab."
            : `${otherCount} andere Möglichkeiten auf Hand/Brett verfügbar.`
      };
    }

    if (dc === "mulligan") {
      const keepOpt = options.find((o) => /keep/i.test(String(o.label || "")));
      if (keepOpt && options.length === 2 && minSel === 1 && maxSel === 1) {
        return {
          kind: "option",
          optionId: String(keepOpt.option_id),
          label: "Starthand behalten",
          nothingLeft: false,
          critical: false,
          requireHold: false,
          disabled: false,
          hintText: "Behält die aktuelle Starthand (oder wähle rechts Mulligan)."
        };
      }
    }

    if (dc === "declare_attacker") {
      return {
        kind: "confirm_selection",
        label: selected.length > 0 ? `Mit ${selected.length} Angreifer${selected.length === 1 ? "" : "n"} angreifen` : "Nicht angreifen (Weiter)",
        nothingLeft: selected.length === 0,
        critical: false,
        requireHold: false,
        disabled: selected.length < minSel || (maxSel > 0 && selected.length > maxSel),
        hintText: "Wähle angreifende Kreaturen/Ziele auf dem Brett oder bestätige 0 Angreifer."
      };
    }

    if (dc === "declare_blocker") {
      return {
        kind: "confirm_selection",
        label: selected.length > 0 ? `Blocker ansagen (${selected.length})` : "Nicht blocken (Weiter)",
        nothingLeft: selected.length === 0,
        critical: false,
        requireHold: false,
        disabled: selected.length < minSel || (maxSel > 0 && selected.length > maxSel),
        hintText: "Klicke auf Blocker und Angreifer oder bestätige ohne Block."
      };
    }

    if (dc === "trigger_order" || (dc === "order" && !(minSel === 1 && maxSel === 1))) {
      return {
        kind: "confirm_order",
        label: "Reihenfolge bestätigen",
        nothingLeft: false,
        critical: false,
        requireHold: false,
        disabled: false,
        hintText: "Sortiere die Auslöser rechts und bestätige die Reihenfolge."
      };
    }

    if (dc === "mana_payment") {
      return {
        kind: "info_only",
        label: "Mana-Quelle wählen oder abbrechen",
        nothingLeft: false,
        critical: false,
        requireHold: false,
        disabled: true,
        hintText: "Wähle eine Mana-Quelle auf dem Brett, im Pool oder nutze die Staging-Leiste."
      };
    }

    if (minSel === 1 && maxSel === 1 && options.length === 1) {
      return {
        kind: "option",
        optionId: String(options[0].option_id),
        label: "Einzige Möglichkeit bestätigen",
        nothingLeft: true,
        critical: false,
        requireHold: false,
        disabled: false,
        hintText: "Nur diese Option steht zur Wahl."
      };
    }

    if (minSel === 0 || maxSel > 1) {
      return {
        kind: "confirm_selection",
        label: selected.length > 0 ? `Auswahl bestätigen (${selected.length})` : "Auswahl bestätigen",
        nothingLeft: false,
        critical: false,
        requireHold: false,
        disabled: selected.length < minSel || (maxSel > 0 && selected.length > maxSel),
        hintText: `Wähle ${minSel}..${maxSel} Optionen und bestätige.`
      };
    }

    return {
      kind: "focus_panel",
      label: "Option in Liste/Brett wählen",
      nothingLeft: false,
      critical: false,
      requireHold: false,
      disabled: false,
      hintText: "Springt zur offenen Entscheidungsliste."
    };
  }

  return {
    PHASES,
    RESPONSE_PROFILES,
    defaultHaltConfig,
    buildPhaseTimeline,
    buildWaitingInfo,
    evaluateResponseProfile,
    isCriticalPassWindow,
    buildPrimaryAction
  };
})();
if (typeof globalThis !== "undefined") globalThis.StudioTurnBar = StudioTurnBar;
if (typeof module !== "undefined") module.exports = StudioTurnBar;

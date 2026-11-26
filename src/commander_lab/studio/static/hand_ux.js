"use strict";
// Fanned hand dock, unified card zoom helpers, engine-derived playability & block reasons,
// and mana-preview / Undo staging state (#1819, #1820).
// Read-only UI projection over engine-published pilot_state, legal_options, and public card facts:
// never computes game legality or substitutes for XMage's Rules Core.

const StudioHandUX = (() => {
  const BASIC_LAND_COLORS = {
    Plains: "W",
    Island: "U",
    Swamp: "B",
    Mountain: "R",
    Forest: "G",
    Wastes: "C"
  };
  const COLOR_ORDER = ["W", "U", "B", "R", "G", "C"];
  const POOL_KEY_TO_CODE = {
    white: "W",
    blue: "U",
    black: "B",
    red: "R",
    green: "G",
    colorless: "C"
  };

  function fanDensityClass(count) {
    const n = Number(count) || 0;
    if (n <= 4) return "fan-sparse";
    if (n <= 7) return "fan-normal";
    if (n <= 10) return "fan-compact";
    if (n <= 13) return "fan-dense";
    return "fan-ultra";
  }

  function parseManaCost(manaCost) {
    const colored = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
    let generic = 0;
    let xCount = 0;
    const tokens = [];
    const raw = typeof manaCost === "string" ? manaCost : "";
    const pattern = /\{([^}]+)\}/g;
    let match;
    while ((match = pattern.exec(raw)) !== null) {
      const sym = String(match[1] || "").trim().toUpperCase();
      if (!sym) continue;
      tokens.push(sym);
      if (/^\d+$/.test(sym)) {
        generic += Number(sym);
      } else if (sym === "X") {
        xCount += 1;
      } else if (sym in colored) {
        colored[sym] += 1;
      } else if (sym.includes("/")) {
        // Hybrid/Phyrexian symbols require one matching payment; track generic 1 conservatively only as total
        const parts = sym.split("/").filter((p) => p !== "P");
        if (parts.length === 1 && parts[0] in colored) {
          colored[parts[0]] += 1;
        } else {
          generic += 1;
        }
      }
    }
    const totalColored = COLOR_ORDER.reduce((acc, c) => acc + colored[c], 0);
    return { generic, colored, xCount, total: generic + totalColored, tokens };
  }

  function frontTypeLine(fact) {
    const tl = fact && typeof fact.type_line === "string" ? fact.type_line : "";
    return tl.split("//")[0].trim();
  }

  function isLandFact(name, fact) {
    const front = frontTypeLine(fact);
    if (front) return /\bLand\b/i.test(front);
    return name in BASIC_LAND_COLORS;
  }

  function hasFlashOrInstant(fact) {
    const front = frontTypeLine(fact);
    if (/\bInstant\b/i.test(front)) return true;
    const text = fact && typeof fact.oracle_text === "string" ? fact.oracle_text : "";
    return /\bFlash\b/i.test(text);
  }

  function optionSourceId(opt) {
    if (!opt || typeof opt !== "object") return null;
    const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : {};
    return opt.source_object_id || meta.source_object_id || opt.object_id || meta.object_id || null;
  }

  function resolveOptionKind(opt) {
    if (!opt || typeof opt !== "object") return "activated_ability";
    const ot = typeof opt.option_type === "string" ? opt.option_type : "";
    const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : null;
    const at = meta && typeof meta.ability_type === "string" ? meta.ability_type.toLowerCase() : "";
    if ((!ot || ot === "activated_ability") && at === "play_land") return "play_land";
    if ((!ot || ot === "activated_ability") && at === "spell") return "cast_spell";
    return ot || "activated_ability";
  }

  function cardProducedColors(name, fact) {
    const front = frontTypeLine(fact);
    const produced = new Set();
    for (const [word, code] of Object.entries(BASIC_LAND_COLORS)) {
      if (name === word || new RegExp(`\\b${word}\\b`, "i").test(front)) {
        produced.add(code);
      }
    }
    const oracle = fact && typeof fact.oracle_text === "string" ? fact.oracle_text : "";
    if (oracle) {
      if (/\bany color\b/i.test(oracle) || /\bone mana of any type\b/i.test(oracle)) {
        for (const code of ["W", "U", "B", "R", "G"]) produced.add(code);
      }
      const addMatches = oracle.match(/Add [^.\n]*/gi) || [];
      for (const line of addMatches) {
        const symRe = /\{([WUBRGC])\}/gi;
        let m;
        while ((m = symRe.exec(line)) !== null) {
          produced.add(m[1].toUpperCase());
        }
      }
    }
    if (!produced.size && /\bLand\b/i.test(front)) {
      // Unknown non-basic utility land still provides at least colorless preview credit
      produced.add("C");
    }
    return [...produced];
  }

  function isLikelyManaPermanent(card, fact) {
    if (!card || card.tapped) return false;
    const front = frontTypeLine(fact);
    if (/\bLand\b/i.test(front)) return true;
    const oracle = fact && typeof fact.oracle_text === "string" ? fact.oracle_text : "";
    if (/\{T\}\s*:\s*Add\b/i.test(oracle)) return true;
    return false;
  }

  function formatMissingTokens(missingGeneric, missingColored) {
    const parts = [];
    if (missingGeneric > 0) parts.push(`{${missingGeneric}}`);
    for (const code of COLOR_ORDER) {
      for (let i = 0; i < (missingColored[code] || 0); i += 1) {
        parts.push(`{${code}}`);
      }
    }
    return parts;
  }

  // Computes an honest, strictly read-only UI preview of untapped own mana sources + pool mana
  // needed for `cardName`. Never substitutes for engine legality.
  function buildManaPreview(cardName, cardFact, playerState, pendingDecision, factsMap) {
    const manaCostStr = cardFact && typeof cardFact.mana_cost === "string" ? cardFact.mana_cost : "";
    const parsed = parseManaCost(manaCostStr);
    const pool = playerState && playerState.mana_pool && typeof playerState.mana_pool === "object"
      ? playerState.mana_pool
      : {};
    const remainingPool = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
    for (const [k, v] of Object.entries(pool)) {
      const code = POOL_KEY_TO_CODE[String(k).toLowerCase()] || (k in remainingPool ? k : null);
      if (code) remainingPool[code] += Math.max(0, Number(v) || 0);
    }

    const battlefield = playerState && Array.isArray(playerState.battlefield) ? playerState.battlefield : [];
    const candidates = [];
    for (const perm of battlefield) {
      if (!perm || perm.tapped || !perm.name) continue;
      const pFact = factsMap && typeof factsMap === "object" ? factsMap[perm.name] : null;
      if (!isLikelyManaPermanent(perm, pFact)) continue;
      candidates.push({
        objectId: perm.object_id || null,
        name: perm.name,
        colors: cardProducedColors(perm.name, pFact)
      });
    }

    const usedIndices = new Set();
    const plannedSources = [];
    const poolUsed = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
    const missingColored = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };

    // Prefer mono-color sources over multi-color flexible sources when reserving colored pips
    const orderedIndices = candidates
      .map((_, idx) => idx)
      .sort((a, b) => candidates[a].colors.length - candidates[b].colors.length);

    for (const code of COLOR_ORDER) {
      let need = parsed.colored[code] || 0;
      while (need > 0 && remainingPool[code] > 0) {
        remainingPool[code] -= 1;
        poolUsed[code] += 1;
        need -= 1;
      }
      while (need > 0) {
        const pickIdx = orderedIndices.find(
          (idx) => !usedIndices.has(idx) && candidates[idx].colors.includes(code)
        );
        if (pickIdx === undefined) break;
        usedIndices.add(pickIdx);
        plannedSources.push({ ...candidates[pickIdx], assigned: code });
        need -= 1;
      }
      if (need > 0) missingColored[code] = need;
    }

    let needGeneric = parsed.generic;
    for (const code of COLOR_ORDER) {
      while (needGeneric > 0 && remainingPool[code] > 0) {
        remainingPool[code] -= 1;
        poolUsed[code] += 1;
        needGeneric -= 1;
      }
    }
    while (needGeneric > 0) {
      const pickIdx = orderedIndices.find((idx) => !usedIndices.has(idx));
      if (pickIdx === undefined) break;
      usedIndices.add(pickIdx);
      plannedSources.push({ ...candidates[pickIdx], assigned: "1" });
      needGeneric -= 1;
    }

    const missingTokens = formatMissingTokens(needGeneric, missingColored);
    const sourceObjectIds = plannedSources.map((s) => s.objectId).filter(Boolean);
    const poolChips = COLOR_ORDER.filter((c) => poolUsed[c] > 0).map((c) => `${poolUsed[c]}×{${c}}`);
    const engineCancel = findCancelManaOption(pendingDecision);

    return {
      cardName,
      manaCost: manaCostStr,
      hasCost: parsed.total > 0 || parsed.xCount > 0,
      plannedSources,
      sourceObjectIds,
      poolUsed,
      poolSummary: poolChips.join(" "),
      missingTokens,
      missingText: missingTokens.join(""),
      canCoverApprox: missingTokens.length === 0,
      cancelOptionId: engineCancel ? engineCancel.option_id : null
    };
  }

  function findCancelManaOption(pendingDecision) {
    if (!pendingDecision || pendingDecision.decision_class !== "mana_payment") return null;
    const options = Array.isArray(pendingDecision.legal_options) ? pendingDecision.legal_options : [];
    return options.find((opt) => opt && opt.option_type === "cancel_mana_payment") || null;
  }

  // Selects one engine-offered mana_payment option matching a single unambiguous planned source
  // or single advancing pool spend. Fails closed with null on ambiguity or no fit.
  function nextAutoPayOptionId(pendingDecision, plannedSourceIds) {
    if (!pendingDecision || pendingDecision.decision_class !== "mana_payment") return null;
    const options = Array.isArray(pendingDecision.legal_options) ? pendingDecision.legal_options : [];
    const poolOpts = options.filter((opt) => {
      if (!opt || opt.option_type !== "mana_pool") return false;
      const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : {};
      return meta.advances_payment !== false;
    });
    if (poolOpts.length === 1 && poolOpts[0].option_id) {
      return String(poolOpts[0].option_id);
    }
    if (poolOpts.length > 1) {
      return null;
    }

    const plannedList = Array.isArray(plannedSourceIds) ? plannedSourceIds.filter(Boolean) : [];
    for (const plannedId of plannedList) {
      const forSource = options.filter((opt) => {
        if (!opt || opt.option_type === "cancel_mana_payment" || opt.option_type === "mana_pool") return false;
        return optionSourceId(opt) === plannedId;
      });
      if (forSource.length === 1 && forSource[0].option_id) {
        return String(forSource[0].option_id);
      }
      if (forSource.length > 1) {
        return null;
      }
    }
    return null;
  }

  function matchOptionsForHandCard(cardName, objectId, legalOptions) {
    const out = [];
    for (const opt of legalOptions) {
      if (!opt || opt.option_type === "pass_priority") continue;
      const kind = resolveOptionKind(opt);
      const optSource = optionSourceId(opt);
      const meta = opt.metadata && typeof opt.metadata === "object" ? opt.metadata : {};
      if (objectId && optSource) {
        if (optSource === objectId) out.push({ opt, kind });
        continue;
      }
      if (meta.zone && String(meta.zone).toUpperCase() !== "HAND") continue;
      if (!optSource && (kind === "play_land" || kind === "cast_spell")) {
        const label = String(opt.label || "").trim();
        if (/\bfrom\s+(?:graveyard|exile|command zone)\b/i.test(label)) continue;
        let subject = label.includes(" — ") ? label.split(" — ")[0].trim() : label;
        subject = subject.replace(/^(?:Cast|Play)\s+/i, "").replace(/\s+from\s+hand.*$/i, "").trim();
        if (subject.toLowerCase() === String(cardName || "").toLowerCase()) {
          out.push({ opt, kind });
        }
      }
    }
    return out;
  }

  function buildBlockReason(cardName, fact, playerState, frame, factsMap, handSeat) {
    const isLand = isLandFact(cardName, fact);
    const step = frame && frame.step ? String(frame.step) : "";
    const phase = frame && frame.phase ? String(frame.phase) : "";
    const isOwnTurn = Boolean(frame && handSeat !== undefined && frame.active_seat === handSeat);
    const isOwnMainPhase =
      isOwnTurn &&
      (step === "precombat_main" ||
        step === "postcombat_main" ||
        phase === "precombat_main" ||
        phase === "postcombat_main");
    const stackEmpty = !frame || !Array.isArray(frame.stack) || frame.stack.length === 0;
    const instantSpeed = !isLand && hasFlashOrInstant(fact);

    if (isLand) {
      if (!isOwnMainPhase || !stackEmpty) {
        return {
          reasonClass: "phase",
          badgeIcon: "⏳",
          badgeLabel: "Phase",
          reasonText: "Länder können nur in der eigenen Hauptphase bei leerem Stapel gespielt werden."
        };
      }
      return {
        reasonClass: "land_drop",
        badgeIcon: "⛰",
        badgeLabel: "Land-Zug",
        reasonText: "Kein Land-Zug mehr frei (du hast in diesem Zug bereits ein Land gespielt)."
      };
    }

    if (!instantSpeed && (!isOwnMainPhase || !stackEmpty)) {
      return {
        reasonClass: "phase",
        badgeIcon: "⏳",
        badgeLabel: "Phase",
        reasonText: "Nur in eigener Hauptphase bei leerem Stapel (kein Spontanzauber/Aufblitzen)."
      };
    }

    const manaPreview = buildManaPreview(cardName, fact, playerState, null, factsMap);
    if (manaPreview.hasCost && !manaPreview.canCoverApprox && manaPreview.missingText) {
      return {
        reasonClass: "mana",
        badgeIcon: "💧",
        badgeLabel: "Mana fehlt",
        reasonText: `Noch Mana fehlt: ${manaPreview.missingText}`,
        manaPreview
      };
    }

    return {
      reasonClass: "target_or_condition",
      badgeIcon: "🎯",
      badgeLabel: "Bedingung",
      reasonText: "Kein legales Ziel oder Zauber-/Aktivierungsbedingung laut Engine nicht erfüllt.",
      manaPreview
    };
  }

  function classifyHandCards(handNames, handIds, ctx) {
    const names = Array.isArray(handNames) ? handNames : [];
    const ids = Array.isArray(handIds) ? handIds : [];
    const info = ctx && typeof ctx === "object" ? ctx : {};
    const frame = info.frame || null;
    const handSeat = info.handSeat;
    const humanSeats = Array.isArray(info.humanSeats) ? info.humanSeats : [];
    const facts = info.facts && typeof info.facts === "object" ? info.facts : {};
    const pending = info.pendingDecision || null;
    const snapshot = info.lastOwnPriority || null;
    const stagedObjectId = info.stagedObjectId || null;

    const players = frame && Array.isArray(frame.players) ? frame.players : [];
    const playerState = players.find((p) => p && p.seat === handSeat) || null;
    const activeSeat = frame ? frame.active_seat : null;
    const step = frame && frame.step ? String(frame.step) : "";
    const isOwnTurn = activeSeat === handSeat;
    const isOwnMain =
      isOwnTurn && (step === "precombat_main" || step === "postcombat_main" || frame.phase === "precombat_main" || frame.phase === "postcombat_main");

    const hasLiveOwnPriority = Boolean(
      pending &&
      pending.seat === handSeat &&
      pending.decision_class === "priority" &&
      Array.isArray(pending.legal_options)
    );
    const currentStackCount = frame && Array.isArray(frame.stack) ? frame.stack.length : 0;
    const hasSameWindowSnapshot = Boolean(
      !hasLiveOwnPriority &&
      isOwnTurn &&
      snapshot &&
      snapshot.seat === handSeat &&
      snapshot.turn === (frame ? frame.turn : null) &&
      snapshot.step === step &&
      (snapshot.stackCount ?? 0) === currentStackCount &&
      Array.isArray(snapshot.legal_options) &&
      snapshot.legal_options.length > 0
    );

    const effectiveOptions = hasLiveOwnPriority
      ? pending.legal_options
      : hasSameWindowSnapshot
        ? snapshot.legal_options
        : [];
    const engineEvaluatedHere = hasLiveOwnPriority || hasSameWindowSnapshot;

    return names.map((name, index) => {
      const objectId = ids[index] || null;
      const fact = facts[name] || null;
      const isHumanOwn = humanSeats.includes(handSeat);
      const isStaged = Boolean(stagedObjectId && objectId && stagedObjectId === objectId);

      if (!isHumanOwn && frame) {
        return {
          name,
          objectId,
          status: "waiting",
          actionKind: null,
          optionIds: [],
          primaryOptionId: null,
          badgeIcon: "👁",
          badgeLabel: "Ansicht",
          reasonClass: "waiting",
          reasonText: "Handkarte dieses Sitzes (reine Ansicht).",
          playableNow: false,
          manaPreview: buildManaPreview(name, fact, playerState, pending, facts)
        };
      }

      if (engineEvaluatedHere) {
        const matched = matchOptionsForHandCard(name, objectId, effectiveOptions);
        if (matched.length > 0) {
          const primary = matched[0];
          const isLandPlay = primary.kind === "play_land";
          const isCast = primary.kind === "cast_spell";
          const preview = buildManaPreview(name, fact, playerState, pending, facts);
          return {
            name,
            objectId,
            status: isStaged ? "staged" : "playable",
            actionKind: primary.kind,
            optionIds: matched.map((m) => String(m.opt.option_id)),
            primaryOptionId: String(primary.opt.option_id),
            badgeIcon: isStaged ? "💠" : isLandPlay ? "⛰" : isCast ? "✦" : "⚡",
            badgeLabel: isStaged ? "Vorgemerkt" : isLandPlay ? "Land spielen" : isCast ? "Spielbar" : "Fähigkeit",
            reasonClass: null,
            reasonText: hasLiveOwnPriority
              ? "Von der Regel-Engine jetzt als legal angeboten."
              : "Im aktuellen Hauptphasen-Fenster laut letzter Engine-Priorität spielbar.",
            playableNow: hasLiveOwnPriority,
            manaPreview: preview
          };
        }

        const block = buildBlockReason(name, fact, playerState, frame, facts, handSeat);
        return {
          name,
          objectId,
          status: isStaged ? "staged" : "blocked",
          actionKind: null,
          optionIds: [],
          primaryOptionId: null,
          badgeIcon: isStaged ? "💠" : block.badgeIcon,
          badgeLabel: isStaged ? "Vorgemerkt" : block.badgeLabel,
          reasonClass: block.reasonClass,
          reasonText: isStaged ? "Zauber im Staging — Zahlung läuft oder wurde zurückgenommen." : block.reasonText,
          playableNow: false,
          manaPreview: block.manaPreview || buildManaPreview(name, fact, playerState, pending, facts)
        };
      }

      // No live priority snapshot for this window yet: NEVER invent playability; display honest waiting/blocked hint.
      const manaPreview = buildManaPreview(name, fact, playerState, pending, facts);
      if (isOwnMain) {
        const block = buildBlockReason(name, fact, playerState, frame, facts, handSeat);
        if (block.reasonClass === "mana") {
          return {
            name,
            objectId,
            status: "blocked",
            actionKind: null,
            optionIds: [],
            primaryOptionId: null,
            badgeIcon: block.badgeIcon,
            badgeLabel: block.badgeLabel,
            reasonClass: "mana",
            reasonText: block.reasonText,
            playableNow: false,
            manaPreview
          };
        }
        return {
          name,
          objectId,
          status: isStaged ? "staged" : "waiting",
          actionKind: null,
          optionIds: [],
          primaryOptionId: null,
          badgeIcon: isStaged ? "💠" : "⏸",
          badgeLabel: isStaged ? "Vorgemerkt" : "Eigene Hauptphase",
          reasonClass: "waiting",
          reasonText: isStaged
            ? "Zauber vorgemerkt — Zahlung oder Zielauswahl läuft."
            : "Eigene Hauptphase — warte auf Prioritätsfenster der Engine.",
          playableNow: false,
          manaPreview
        };
      }

      return {
        name,
        objectId,
        status: isStaged ? "staged" : "waiting",
        actionKind: null,
        optionIds: [],
        primaryOptionId: null,
        badgeIcon: isStaged ? "💠" : "⏳",
        badgeLabel: isStaged ? "Vorgemerkt" : (isOwnTurn ? "Andere Phase" : "Gegner-Zug"),
        reasonClass: "phase",
        reasonText: isOwnTurn
          ? "Andere Phase oder offener Stapel — keine aktive Hauptphasen-Priorität."
          : "Gegnerischer Zug — warten auf eigene Priorität.",
        playableNow: false,
        manaPreview
      };
    });
  }

  return {
    CANCEL_PAYMENT_LABEL: "Zahlung zurücknehmen (Undo)",
    CANCEL_PAYMENT_HINT: "Zahlung zurückgenommen — Zauber bleibt im Staging; Quellen können neu gewählt werden.",
    fanDensityClass,
    parseManaCost,
    buildManaPreview,
    findCancelManaOption,
    nextAutoPayOptionId,
    classifyHandCards
  };
})();
if (typeof globalThis !== "undefined") globalThis.StudioHandUX = StudioHandUX;
if (typeof module !== "undefined") module.exports = StudioHandUX;

"use strict";
// Pure read-only UI projection helpers for the PLAY table, commander damage matrix,
// danger/casting states, ordered stack rail annotations, and Icon-Tile event log.
// Strictly visual projection of engine-published state: never computes game rules,
// legality, commander tax, or hidden information.

const StudioBoardUX = (() => {
  const MAX_SHORT_LOG_LEN = 68;
  const TRIGGER_COLLAPSE_THRESHOLD = 5;
  const CASTING_DECISION_CLASSES = new Set([
    "mana_payment",
    "pay_mana",
    "target",
    "mode",
    "announce_x",
    "target_amount",
    "replacement_effect",
  ]);

  function clampSeatCount(count) {
    const n = Number(count);
    if (!Number.isFinite(n) || n <= 1) return 1;
    return Math.max(2, Math.min(6, Math.trunc(n)));
  }

  function gridModeClass(seatCount, focusSeat) {
    const clamped = clampSeatCount(seatCount);
    const hasFocus =
      Number.isInteger(focusSeat) && focusSeat >= 0 && focusSeat < clamped;
    const classes = clamped === 1 ? ["one"] : [`seats-${clamped}`];
    if (hasFocus) classes.push("focus-mode");
    return classes;
  }

  // Never render negative life values on eliminated seats (#1824).
  function lifeStatus(player) {
    const lost = Boolean(player && player.lost);
    const raw = player && typeof player.life === "number" && Number.isFinite(player.life) ? player.life : null;
    if (lost) {
      return {
        displayLife: 0,
        rawLife: raw,
        dangerLevel: "eliminated",
        eliminated: true,
      };
    }
    if (raw === null) {
      return {
        displayLife: "?",
        rawLife: null,
        dangerLevel: "unknown",
        eliminated: false,
      };
    }
    let dangerLevel = "ok";
    if (raw <= 5) dangerLevel = "critical";
    else if (raw <= 10) dangerLevel = "warn";
    return {
      displayLife: raw,
      rawLife: raw,
      dangerLevel,
      eliminated: false,
    };
  }

  function commanderDamageLevel(total) {
    const n = Number(total);
    if (!Number.isFinite(n) || n <= 0) return "none";
    if (n >= 21) return "lethal";
    if (n >= 15) return "warn";
    return "normal";
  }

  function formatSeatName(seat, seatNameFn) {
    if (typeof seatNameFn === "function") return seatNameFn(seat);
    return Number.isInteger(seat) ? `Sitz ${seat + 1}` : "?";
  }

  // Pairwise engine-published commander damage (never summed across commanders, never derives tax).
  function buildCommanderMatrix(frame, seat, seatNameFn) {
    const commandersMap = frame && frame.commanders && typeof frame.commanders === "object"
      ? frame.commanders
      : null;
    if (!commandersMap) return null;
    const info = commandersMap[seat];
    if (!info || typeof info !== "object") return null;
    const owned = (Array.isArray(info.commanders) ? info.commanders : []).map((entry) => {
      const name = typeof entry.name === "string" && entry.name ? entry.name : "?";
      const casts = Number.isInteger(entry.casts) ? entry.casts : null;
      return {
        name,
        casts,
        castsLabel: casts === null ? "Casts unbekannt" : `${casts}× aus der Kommandozone`,
      };
    });
    const rows = (Array.isArray(info.received) ? info.received : [])
      .map((hit) => {
        const fromSeat = hit && Number.isInteger(hit.fromSeat) ? hit.fromSeat : null;
        const fromName = hit && typeof hit.fromName === "string" && hit.fromName ? hit.fromName : "?";
        const total = hit && Number.isFinite(hit.total) ? Number(hit.total) : 0;
        const level = commanderDamageLevel(total);
        const badgeText = level === "lethal" ? "☠ 21+ Tödlich" : level === "warn" ? "⚠ 15+" : "";
        return {
          fromSeat,
          fromName,
          seatLabel: formatSeatName(fromSeat, seatNameFn),
          total,
          level,
          badgeText,
        };
      })
      .sort((a, b) => b.total - a.total || (a.fromSeat ?? 99) - (b.fromSeat ?? 99));
    return { owned, rows };
  }

  function stripMarkupText(raw) {
    return String(raw || "")
      .replace(/<[^>]*>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function extractCardFromStackName(rawName, knownFacts) {
    const s = stripMarkupText(rawName);
    if (!s || s === "(verdeckt)" || s === "verdeckt") return null;
    let candidate = s;
    const abilityMatch = /^(?:stack ability|Fähigkeit:?)\s*\((.+)\)$/i.exec(s);
    if (abilityMatch) {
      candidate = abilityMatch[1];
    } else if (/^Fähigkeit:\s*/i.test(s)) {
      candidate = s.replace(/^Fähigkeit:\s*/i, "");
    } else if (!/^stack ability/i.test(s)) {
      return candidate;
    }
    if (knownFacts && typeof knownFacts === "object") {
      if (Object.prototype.hasOwnProperty.call(knownFacts, candidate)) return candidate;
      let best = null;
      for (const name of Object.keys(knownFacts)) {
        if (!name || name === "(verdeckt)") continue;
        if (
          (candidate === name || candidate.startsWith(`${name}:`) || candidate.startsWith(`${name} —`) || candidate.startsWith(`${name} (`)) &&
          (!best || name.length > best.length)
        ) {
          best = name;
        }
      }
      if (best) return best;
    }
    const colonIdx = candidate.indexOf(":");
    if (colonIdx > 0) {
      const head = candidate.slice(0, colonIdx).trim();
      if (head && head.length <= 64) return head;
    }
    return candidate.length <= 64 ? candidate : null;
  }

  // Identifies which seat is currently casting or owns the resolving stack top.
  function detectCastingSeat(frame, pendingDecision) {
    if (!frame || typeof frame !== "object") return null;
    const ps = pendingDecision && pendingDecision.pilot_state && typeof pendingDecision.pilot_state === "object"
      ? pendingDecision.pilot_state
      : null;
    const stackList = Array.isArray(frame.stack) ? frame.stack : [];
    const psStack = ps && Array.isArray(ps.stack) ? ps.stack : [];
    if (psStack.length > 0 || stackList.length > 0) {
      const topObj = psStack[0] && typeof psStack[0] === "object" ? psStack[0] : null;
      let controllerSeat = null;
      if (topObj && topObj.controller_id && Array.isArray(ps.players)) {
        const match = ps.players.find((p) => p && p.player_id === topObj.controller_id);
        if (match && Number.isInteger(match.seat)) controllerSeat = match.seat;
      }
      if (controllerSeat === null && Array.isArray(frame.stack_controllers) && Number.isInteger(frame.stack_controllers[0])) {
        controllerSeat = frame.stack_controllers[0];
      }
      const rawTopName = topObj
        ? (topObj.face_down ? "(verdeckt)" : topObj.name || "")
        : (stackList[0] || "");
      const cleanTop = rawTopName === "(verdeckt)" ? "Verdeckter Zauber" : stripMarkupText(rawTopName);
      if (controllerSeat !== null) {
        return {
          seat: controllerSeat,
          kind: "stack",
          sourceName: cleanTop || "Zauber/Fähigkeit",
          label: cleanTop ? `✨ Wirkt: ${cleanTop}` : "✨ Auf dem Stapel",
        };
      }
    }
    const activeDecision = pendingDecision && typeof pendingDecision === "object" ? pendingDecision : null;
    const decClass = activeDecision ? activeDecision.decision_class : frame.decision_class;
    const actorSeat = activeDecision && Number.isInteger(activeDecision.seat)
      ? activeDecision.seat
      : (Number.isInteger(frame.seat) ? frame.seat : null);
    if (actorSeat !== null && CASTING_DECISION_CLASSES.has(decClass)) {
      const src = frame.source && frame.source !== "(verdeckt)" ? stripMarkupText(frame.source) : "";
      return {
        seat: actorSeat,
        kind: "casting",
        sourceName: src || null,
        label: src ? `✨ Wirkt: ${src}` : "✨ Wirkt gerade",
      };
    }
    return null;
  }

  function annotateStackRail(rail, knownFacts) {
    const items = Array.isArray(rail) ? rail : [];
    return items.map((item, idx) => {
      const orderNumber = idx + 1;
      const orderLabel = idx === 0 ? "#1 · löst zuerst auf" : `#${orderNumber}`;
      const kindLabel = item.faceDown ? "Verdeckt" : item.isAbility ? "Fähigkeit" : "Zauber";
      const targetSummary =
        item.targetsPublished && Array.isArray(item.targets) && item.targets.length
          ? item.targets.join(", ")
          : "kein Ziel veröffentlicht";
      let zoomCardName = null;
      if (!item.faceDown) {
        if (!item.isAbility && item.name) {
          zoomCardName = extractCardFromStackName(item.name, knownFacts) || item.name;
        } else if (item.isAbility) {
          zoomCardName = extractCardFromStackName(item.name || item.displayName, knownFacts);
        }
      }
      return Object.assign({}, item, {
        orderNumber,
        orderLabel,
        kindLabel,
        targetSummary,
        zoomCardName,
      });
    });
  }

  function shortenRuleProse(raw) {
    let s = stripMarkupText(raw);
    if (!s) return "";
    // Remove verbose parenthetical reminder text
    s = s.replace(/\([^()]{20,}\)/g, "").replace(/\s+/g, " ").trim();
    // Collapse "Card — Ability prose..." or "Auslöser: Card: Ability prose..." into concise action
    const abilityMatch = /^(?:Fähigkeit:|Auslöser:|stack ability)\s*\(?([^:()]+):/i.exec(s);
    if (abilityMatch) {
      return `Auslöser: ${abilityMatch[1].trim()}`;
    }
    const dashParts = s.split(" — ");
    if (dashParts.length >= 2 && dashParts[1].length > 26) {
      s = `${dashParts[0].trim()} — ${dashParts[1].split(/[.;:]/)[0].trim()}`;
    }
    const colonIdx = s.indexOf(": ");
    if (colonIdx > 0 && colonIdx < 36 && s.length > MAX_SHORT_LOG_LEN) {
      const tail = s.slice(colonIdx + 2);
      if (tail.length > 36) {
        s = `${s.slice(0, colonIdx)}: ${tail.split(/[.;]/)[0].trim()}`;
      }
    }
    if (s.length > MAX_SHORT_LOG_LEN) {
      s = `${s.slice(0, MAX_SHORT_LOG_LEN - 1).trim()}…`;
    }
    return s;
  }

  function findKnownCardInText(text, knownFacts) {
    if (!text || !knownFacts || typeof knownFacts !== "object") return null;
    let best = null;
    for (const name of Object.keys(knownFacts)) {
      if (!name || name.length < 2 || name === "(verdeckt)") continue;
      if (text.includes(name) && (!best || name.length > best.length)) best = name;
    }
    return best;
  }

  function classifyLogEntry(frame, ansText, knownFacts) {
    const f = frame && typeof frame === "object" ? frame : {};
    const decClass = String(f.decision_class || "");
    const rawText = stripMarkupText(ansText || "");
    const privateHidden = Boolean(f.private_selection) || rawText.includes("verdeckt");
    let sourceCard = null;
    if (!privateHidden && f.source && f.source !== "(verdeckt)") {
      sourceCard = extractCardFromStackName(String(f.source), knownFacts);
    }
    if (!sourceCard && !privateHidden && Array.isArray(f.chosen) && f.chosen.length) {
      for (const ch of f.chosen) {
        const s = String(ch || "");
        const head = s.includes(" — ") ? s.split(" — ")[0].trim() : "";
        if (head && knownFacts && Object.prototype.hasOwnProperty.call(knownFacts, head)) {
          sourceCard = head;
          break;
        }
        const matched = findKnownCardInText(s, knownFacts);
        if (matched) {
          sourceCard = matched;
          break;
        }
      }
    }
    if (!sourceCard && !privateHidden) {
      sourceCard = findKnownCardInText(rawText, knownFacts);
    }

    const lower = rawText.toLowerCase();
    const isTrigger =
      decClass === "trigger_order" ||
      lower.includes("auslöser") ||
      lower.includes("ausgelöst") ||
      lower.includes("stack ability") ||
      (f.source && /^stack ability/i.test(String(f.source)));

    let icon = "📋";
    let kind = "action";
    if (isTrigger) {
      icon = "⚡";
      kind = "trigger";
    } else if (lower.includes("land spielen") || lower.startsWith("spiele ") && !lower.includes("zauber")) {
      icon = "🌱";
      kind = "land";
    } else if (lower.includes("zauber wirken") || lower.startsWith("wirke ")) {
      icon = "✨";
      kind = "cast";
    } else if (decClass === "declare_attacker" || lower.includes("greift ")) {
      icon = "⚔️";
      kind = "attack";
    } else if (decClass === "declare_blocker" || lower.includes("blockt")) {
      icon = "🛡️";
      kind = "block";
    } else if (decClass === "target" || decClass === "target_amount" || lower.startsWith("ziel")) {
      icon = "🎯";
      kind = "target";
    } else if (decClass === "mana_payment" || lower.includes("mana")) {
      icon = "💎";
      kind = "mana";
    } else if (decClass === "mulligan") {
      icon = "🃏";
      kind = "mulligan";
    } else if (decClass === "choose_use" || decClass === "mode" || decClass === "choice") {
      icon = "❓";
      kind = "choice";
    }

    const shortText = shortenRuleProse(rawText) || rawText;
    const hasExtraDetail = rawText.length > shortText.length + 2 || (f.prompt && stripMarkupText(f.prompt).length > 0 && !rawText.includes(stripMarkupText(f.prompt)));
    const collapseTarget = sourceCard || shortText;
    const collapseKey =
      kind === "trigger" || (kind === "mana" && decClass === "mana_payment")
        ? `s${f.seat ?? "?"}|${kind}|${collapseTarget.toLowerCase()}`
        : null;

    return {
      icon,
      kind,
      shortText,
      fullText: rawText,
      promptText: f.prompt ? stripMarkupText(f.prompt) : "",
      hasExtraDetail,
      cardName: sourceCard,
      collapseKey,
      collapseTitle: kind === "trigger"
        ? `Auslöser: ${sourceCard || shortText.replace(/^Auslöser:\s*/i, "")}`
        : shortText,
    };
  }

  return {
    TRIGGER_COLLAPSE_THRESHOLD,
    gridModeClass,
    lifeStatus,
    commanderDamageLevel,
    buildCommanderMatrix,
    extractCardFromStackName,
    detectCastingSeat,
    annotateStackRail,
    shortenRuleProse,
    classifyLogEntry,
  };
})();

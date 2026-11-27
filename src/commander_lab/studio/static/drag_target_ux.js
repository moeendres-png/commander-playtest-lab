"use strict";
// Read-only UI helpers for hand/permanent drag-and-drop and targeting arrows (#1821).
// Projects only engine-published pendingDecision + StudioBoardClick + StudioHandUX state:
// never computes game legality, targets, or combat outcomes itself.

const StudioDragTargetUX = (() => {
  const DRAG_THRESHOLD_PX = 8;

  function classifyHandDrag(info, pending, atLiveTail, submitting, ffOn) {
    if (!atLiveTail || submitting || ffOn || !pending || !info) {
      return { draggable: false };
    }
    if (!info.playableNow || !info.primaryOptionId) {
      return { draggable: false };
    }
    let arrowKind = "action";
    let dropHint = "⚡ Loslassen: Aktion ausführen";
    if (info.actionKind === "play_land") {
      arrowKind = "land";
      dropHint = "🌱 Loslassen: Land aufs Feld spielen";
    } else if (info.actionKind === "cast_spell") {
      arrowKind = "spell";
      dropHint = info.manaPreview && info.manaPreview.hasCost
        ? "✨ Loslassen: Mana-Vorschau / Wirken"
        : "✨ Loslassen: Zauber wirken";
    }
    return {
      draggable: true,
      kind: "hand",
      objectId: info.objectId || null,
      name: info.name || "Karte",
      actionKind: info.actionKind || "activated_ability",
      primaryOptionId: String(info.primaryOptionId),
      dropMode: "board",
      arrowKind,
      dropHint,
    };
  }

  function classifyPermanentDrag(objectId, name, pending, clickModel, atLiveTail, submitting, ffOn) {
    if (!atLiveTail || submitting || ffOn || !pending || !clickModel || !objectId) {
      return { draggable: false };
    }
    if (!clickModel.decisionId || clickModel.decisionId !== pending.decision_id) {
      return { draggable: false };
    }
    const cardName = name || "Karte";
    if (clickModel.kind === "attacker" && objectId === clickModel.asked) {
      return {
        draggable: true,
        kind: "attacker",
        objectId,
        name: cardName,
        dropMode: "targets",
        arrowKind: "attack",
        dropHint: "⚔️ Auf Gegner oder Planeswalker ziehen",
      };
    }
    if (clickModel.kind === "blocker" && objectId === clickModel.asked) {
      return {
        draggable: true,
        kind: "blocker",
        objectId,
        name: cardName,
        dropMode: "targets",
        arrowKind: "block",
        dropHint: "🛡️ Auf Angreifer ziehen (Staging)",
      };
    }
    const entry = clickModel.objects && clickModel.objects[objectId];
    if (clickModel.kind === "priority" && entry && entry.role === "action" && Array.isArray(entry.optionIds) && entry.optionIds.length > 0) {
      return {
        draggable: true,
        kind: "permanent_action",
        objectId,
        name: cardName,
        dropMode: "board",
        arrowKind: "action",
        dropHint: "⚡ Auf Spielfeld ziehen: Aktion wählen",
      };
    }
    return { draggable: false };
  }

  function isLegalDropTarget(dragState, candidateTarget, clickModel) {
    if (!dragState || !dragState.draggable || !candidateTarget) return false;
    if (dragState.dropMode === "board") {
      return candidateTarget.type === "board";
    }
    if (dragState.dropMode !== "targets" || !clickModel) return false;
    if (dragState.kind === "attacker") {
      if (candidateTarget.type === "seat") {
        const seatEntry = clickModel.seats && clickModel.seats[String(candidateTarget.seat)];
        return Boolean(seatEntry && seatEntry.role === "defender" && Array.isArray(seatEntry.optionIds) && seatEntry.optionIds.length > 0);
      }
      if (candidateTarget.type === "object") {
        const objEntry = clickModel.objects && clickModel.objects[candidateTarget.id];
        return Boolean(objEntry && objEntry.role === "defender" && Array.isArray(objEntry.optionIds) && objEntry.optionIds.length > 0);
      }
      return false;
    }
    if (dragState.kind === "blocker") {
      if (candidateTarget.type === "object") {
        const objEntry = clickModel.objects && clickModel.objects[candidateTarget.id];
        return Boolean(objEntry && objEntry.role === "block-target" && Array.isArray(objEntry.optionIds) && objEntry.optionIds.length > 0);
      }
      return false;
    }
    return false;
  }

  function resolveTargetMode(pending, clickModel, frame, dismissedDecisionId) {
    const empty = {
      active: false,
      paused: false,
      decisionId: pending && pending.decision_id ? String(pending.decision_id) : null,
      kind: "none",
      mode: "info",
      sourceName: null,
      sourceAnchor: { type: "bar" },
      targetCount: 0,
    };
    if (!pending || !clickModel || !clickModel.decisionId || clickModel.decisionId !== pending.decision_id) {
      return empty;
    }
    if (clickModel.kind !== "target") return empty;
    const objCount = Object.keys(clickModel.objects || {}).length;
    const seatCount = Object.keys(clickModel.seats || {}).length;
    const targetCount = objCount + seatCount;
    if (targetCount === 0) return empty;

    const decisionId = String(pending.decision_id);
    const paused = dismissedDecisionId === decisionId;
    const ps = pending.pilot_state && typeof pending.pilot_state === "object" ? pending.pilot_state : {};
    const ctx = pending.context && typeof pending.context === "object" ? pending.context : {};
    const srcObj = pending.source_object && typeof pending.source_object === "object" ? pending.source_object : {};
    const topStack = Array.isArray(ps.stack) && ps.stack.length && typeof ps.stack[0] === "object" ? ps.stack[0] : null;
    const sourceId = srcObj.object_id || ctx.source_object_id || (topStack && topStack.object_id) || null;
    const sourceName =
      (srcObj.name && !srcObj.face_down ? srcObj.name : null) ||
      (typeof pending.source === "string" && pending.source && pending.source !== "(verdeckt)" ? pending.source : null) ||
      (topStack && !topStack.face_down && topStack.name ? topStack.name : null) ||
      (frame && typeof frame.source === "string" && frame.source !== "(verdeckt)" ? frame.source : null);

    let sourceAnchor = { type: "bar" };
    if (sourceId) {
      sourceAnchor = { type: "object", id: String(sourceId) };
    } else if (frame && Array.isArray(frame.stack) && frame.stack.length > 0) {
      sourceAnchor = { type: "stack_top", index: 0 };
    }

    return {
      active: !paused,
      paused,
      decisionId,
      kind: clickModel.kind,
      mode: clickModel.mode || "immediate",
      sourceName,
      sourceAnchor,
      targetCount,
    };
  }

  function computeCurvedArrowPath(x1, y1, x2, y2) {
    const aX = Number(x1) || 0;
    const aY = Number(y1) || 0;
    const bX = Number(x2) || 0;
    const bY = Number(y2) || 0;
    const dx = bX - aX;
    const dy = bY - aY;
    const dist = Math.hypot(dx, dy);
    if (dist < 1) {
      return {
        d: `M ${Math.round(aX)} ${Math.round(aY)} L ${Math.round(bX)} ${Math.round(bY)}`,
        cx: aX,
        cy: aY,
        length: 0,
      };
    }
    const midX = (aX + bX) / 2;
    const midY = (aY + bY) / 2;
    const lift = Math.min(72, Math.max(18, dist * 0.2));
    // Perpendicular unit vector oriented upward/outward so cross-table arcs never flatten straight
    let nx = -dy / dist;
    let ny = dx / dist;
    if (ny > 0.2) {
      nx = -nx;
      ny = -ny;
    }
    const cx = midX + nx * lift;
    const cy = midY + ny * lift;
    return {
      d: `M ${Math.round(aX)} ${Math.round(aY)} Q ${Math.round(cx)} ${Math.round(cy)} ${Math.round(bX)} ${Math.round(bY)}`,
      cx: Math.round(cx),
      cy: Math.round(cy),
      length: Math.round(dist),
    };
  }

  return {
    DRAG_THRESHOLD_PX,
    classifyHandDrag,
    classifyPermanentDrag,
    isLegalDropTarget,
    resolveTargetMode,
    computeCurvedArrowPath,
  };
})();
if (typeof module !== "undefined") module.exports = StudioDragTargetUX;

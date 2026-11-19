"use strict";
// Pure replay navigation helpers for a finished game in Commander Studio (Issue #1530).
// Operates strictly on the frames already loaded in the page: no network calls, no DOM access,
// no rules computation. Available for finished games and for running AI-vs-AI games; never while
// a game with human seats is still running (the AI hands are hidden until it ends).
const StudioReplay = (() => {
  function isPass(frame) {
    return Boolean(
      frame &&
      frame.decision_class === "priority" &&
      Array.isArray(frame.chosen) &&
      frame.chosen.length === 1 &&
      frame.chosen[0] === "Pass priority"
    );
  }

  function isMinor(frame) {
    return Boolean(frame && (isPass(frame) || frame.decision_class === "mana_payment"));
  }

  function clampIndex(frames, index) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    const raw = Number.isFinite(index) ? Math.trunc(index) : 0;
    return Math.max(0, Math.min(frames.length - 1, raw));
  }

  // Replay controls need at least one loaded frame. A running game with human seats never offers
  // them (hidden information: the AI hands are revealed only once the game has ended). A running
  // AI-vs-AI game keeps them (nothing hidden). A finished game needs its result; one with human
  // seats additionally needs the server's reveal of the AI hands.
  function isReplayAvailable(state) {
    if (!state || typeof state !== "object") return false;
    if (!Array.isArray(state.frames) || state.frames.length === 0) return false;
    if (state.running) return !state.interactive;
    if (!state.result) return false;
    return state.interactive ? Boolean(state.handsRevealed) : true;
  }

  // Unique turn numbers in order of first appearance, each paired with its start frame index.
  function listTurns(frames) {
    if (!Array.isArray(frames) || frames.length === 0) return [];
    const seen = new Set();
    const turns = [];
    for (let i = 0; i < frames.length; i += 1) {
      const frame = frames[i];
      const turn = frame && Number.isInteger(frame.turn) ? frame.turn : null;
      if (turn === null || seen.has(turn)) continue;
      seen.add(turn);
      turns.push({ turn, index: i });
    }
    return turns;
  }

  function stepForward(frames, index, skipMinor = false) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    let next = clampIndex(frames, index) + 1;
    if (next >= frames.length) return frames.length - 1;
    if (skipMinor) {
      while (next < frames.length - 1 && isMinor(frames[next])) next += 1;
    }
    return clampIndex(frames, next);
  }

  function stepBackward(frames, index, skipMinor = false) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    let next = clampIndex(frames, index) - 1;
    if (next <= 0) return 0;
    if (skipMinor) {
      while (next > 0 && isMinor(frames[next])) next -= 1;
    }
    return clampIndex(frames, next);
  }

  // First frame index of turnNumber, or the closest valid turn start index if turnNumber is absent.
  function jumpToTurn(frames, turnNumber) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    const turns = listTurns(frames);
    if (turns.length === 0) return 0;
    const wanted = Number(turnNumber);
    if (!Number.isFinite(wanted)) return 0;
    const exact = turns.find((entry) => entry.turn === wanted);
    if (exact) return exact.index;
    let best = turns[0];
    let bestDiff = Math.abs(best.turn - wanted);
    for (let i = 1; i < turns.length; i += 1) {
      const diff = Math.abs(turns[i].turn - wanted);
      if (diff < bestDiff) {
        best = turns[i];
        bestDiff = diff;
      }
    }
    return best.index;
  }

  // Start frame index of the previous turn, or 0 when already in the first turn (or before it).
  function prevTurn(frames, index) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    const cur = clampIndex(frames, index);
    const turns = listTurns(frames);
    let pos = -1;
    for (let i = 0; i < turns.length; i += 1) {
      if (turns[i].index <= cur) pos = i;
      else break;
    }
    if (pos <= 0) return 0;
    return turns[pos - 1].index;
  }

  // Start frame index of the next turn, or the last frame index when already in the final turn.
  function nextTurn(frames, index) {
    if (!Array.isArray(frames) || frames.length === 0) return 0;
    const cur = clampIndex(frames, index);
    const turns = listTurns(frames);
    for (let i = 0; i < turns.length; i += 1) {
      if (turns[i].index > cur) return turns[i].index;
    }
    return frames.length - 1;
  }

  return {
    isPass,
    isMinor,
    isReplayAvailable,
    listTurns,
    stepForward,
    stepBackward,
    jumpToTurn,
    prevTurn,
    nextTurn,
  };
})();
if (typeof module !== "undefined") module.exports = StudioReplay;

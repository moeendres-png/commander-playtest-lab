"use strict";
// How the Partie page follows a running game (Issue #1593). Pure helpers: no network, no DOM,
// no rules. The server holds a state request open until the live game changed ("long poll"), so a
// new decision is shown as soon as the engine published it. If the server does not send a
// revision, or a request fails, the page keeps the fixed intervals it used before.
const StudioFollow = (() => {
  // Asked of the server; the server holds a request at most this long (its own cap may be lower).
  const LONG_POLL_WAIT_MS = 8000;
  // A held request that answers faster than this without a change is treated as a server that does
  // not hold requests: the page then falls back to the fixed intervals instead of spinning.
  const MIN_GAP_MS = 40;
  const WATCHING_AI_GAME_MS = 2000;

  // The fixed intervals of before: fast-forward 150 ms, an open decision 1.5 s, else 0.4 s.
  function legacyIntervalMs(interactive, fastForward, hasPendingDecision) {
    if (!interactive) return WATCHING_AI_GAME_MS;
    if (fastForward) return 150;
    return hasPendingDecision ? 1500 : 400;
  }

  // The revision counts the changes of a live game; null means the server did not report one.
  function parseRevision(page) {
    return page && Number.isInteger(page.revision) && page.revision >= 0 ? page.revision : null;
  }

  // Path of one state request. Only a request that asks for a change after a known revision is
  // held open; every other request (first load, after an own answer) is answered at once.
  function statePath(gameId, start, interactive, revision, hold) {
    const base = interactive ? "/api/play/" : "/api/games/";
    const path = `${base}${encodeURIComponent(gameId)}?start=${start}&count=1000`;
    if (!interactive || !hold || revision === null) return path;
    return `${path}&since=${revision}&wait_ms=${LONG_POLL_WAIT_MS}`;
  }

  // Pause before the next request. info: {interactive, fastForward, hasPendingDecision, revision
  // (null = unknown), failed, held (the last request was a held one), changed, elapsedMs}.
  function nextDelayMs(info) {
    const legacy = legacyIntervalMs(info.interactive, info.fastForward, info.hasPendingDecision);
    if (!info.interactive || info.failed || info.revision === null) return legacy;
    if (!info.held) return 0;
    if (!info.changed && info.elapsedMs < MIN_GAP_MS) return legacy;
    return Math.max(0, MIN_GAP_MS - info.elapsedMs);
  }

  // What the page shows, as one comparable value (#1578). The follow loop draws the table again only
  // when this differs from the value of the last drawing: an answer that brought nothing new (same
  // revision, same frames, same decision) leaves the board as it is. Everything a drawing reads to
  // decide what it shows (the open decision, fast-forward, a pass already sent) is part of it.
  // view: {gameId, revision, frames (count), index, running, interactive, pendingDecisionId,
  // handsRevealed, canConcede, resultStatus, fastForward, autoPassAttempt, submitting, playing}.
  function viewKey(view) {
    const v = view || {};
    const pick = (value) => (value === undefined ? null : value);
    return JSON.stringify([
      pick(v.gameId), pick(v.revision), pick(v.frames), pick(v.index), Boolean(v.running),
      Boolean(v.interactive), pick(v.pendingDecisionId), Boolean(v.handsRevealed), Boolean(v.canConcede),
      pick(v.resultStatus), Boolean(v.fastForward), pick(v.autoPassAttempt), Boolean(v.submitting),
      Boolean(v.playing)
    ]);
  }

  // The state an own answer brought back (POST /decision with start, #1578) replaces the next state
  // request only if it is the very page that request would ask for: the same game, frames from the
  // number the page holds, and not older than the revision the page already has. Anything else (or
  // nothing) and the page asks the server as before.
  function usableAnswerState(page, gameId, heldFrames, heldRevision) {
    if (!page || typeof page !== "object" || page.game_id !== gameId) return false;
    if (!Array.isArray(page.frames) || page.start !== heldFrames) return false;
    const revision = parseRevision(page);
    if (revision === null) return false;
    return heldRevision === null || revision >= heldRevision;
  }

  return { LONG_POLL_WAIT_MS, MIN_GAP_MS, legacyIntervalMs, parseRevision, statePath, nextDelayMs, viewKey, usableAnswerState };
})();
if (typeof module !== "undefined") module.exports = StudioFollow;

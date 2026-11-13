"use strict";
// Card search ranking of the deck builder: exact name, name prefix, word prefix, name contains,
// then text matches. Alphabetical inside a rank. A pure function, so it can be tested alone.

const StudioSearch = (() => {
  const fold = (text) => String(text || "").toLowerCase();
  // 0 exact name, 1 name starts with the query, 2 a word of the name starts with it,
  // 3 the name contains it, 4 type line or oracle text contains it, null no match.
  function rank(card, query) {
    const q = fold(query).trim();
    if (!q) return 0;
    const name = fold(card.name);
    if (name === q) return 0;
    if (name.startsWith(q)) return 1;
    const nameWords = name.split(/[\s,'/-]+/).filter(Boolean);
    if (nameWords.some((word) => word.startsWith(q))) return 2;
    // a multi-word query that starts at a word of the name ("sol r" in "Zealous Sol Ringer"),
    // or whose every word starts a word of the name, in any order
    const queryWords = q.split(/\s+/).filter(Boolean);
    if (queryWords.length > 1) {
      const at = nameWords.map((_, i) => nameWords.slice(i).join(" "));
      if (at.some((tail) => tail.startsWith(q))) return 2;
    }
    if (name.includes(q)) return 3;
    const hay = `${name}\n${fold(card.type_line)}\n${fold(card.text)}`;
    if (hay.includes(q)) return 4;
    // several words: every word must be found somewhere; all in the name beats the text
    const words = q.split(/\s+/).filter(Boolean);
    if (words.length > 1 && words.every((word) => hay.includes(word))) return words.every((word) => name.includes(word)) ? 3 : 4;
    return null;
  }
  function sortByRank(cards, query) {
    const scored = [];
    for (const card of cards) { const r = rank(card, query); if (r !== null) scored.push([r, card]); }
    scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name));
    return scored.map((item) => item[1]);
  }
  return { rank, sortByRank };
})();
if (typeof module !== "undefined") module.exports = StudioSearch;

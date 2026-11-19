"use strict";
// Wishlist (Zukauf) helpers and literal Oracle/Superfriends filters (Refs #1636, Refs #1187).
// Pure functions: objective collection counts and literal Oracle-text / type-line matching only.

const StudioWishlist = (() => {
  function lookupCard(poolMap, cardId) {
    if (!poolMap || !cardId) return null;
    if (typeof poolMap.get === "function") return poolMap.get(cardId) || null;
    return poolMap[cardId] || null;
  }

  function isUnowned(card) {
    if (!card) return true;
    return card.in_collection === false || Number(card.owned || 0) < 1;
  }

  function summarizeDeckOwnership(deckEntries, poolMap) {
    const byId = new Map();
    for (const entry of deckEntries || []) {
      if (!entry || !entry.card_id) continue;
      const quantity = Math.max(0, Number(entry.quantity || 0));
      if (!quantity) continue;
      const prev = byId.get(entry.card_id);
      if (prev) {
        prev.quantity += quantity;
      } else {
        byId.set(entry.card_id, {
          card_id: entry.card_id,
          quantity,
          name: entry.name || "",
        });
      }
    }
    let total = 0;
    let owned = 0;
    let missing = 0;
    const missingCards = [];
    for (const item of byId.values()) {
      const card = lookupCard(poolMap, item.card_id);
      const ownedCount =
        card && card.in_collection !== false ? Math.max(0, Number(card.owned || 0)) : 0;
      const have = Math.min(item.quantity, ownedCount);
      const need = Math.max(0, item.quantity - ownedCount);
      total += item.quantity;
      owned += have;
      missing += need;
      if (need > 0) {
        missingCards.push({
          card_id: item.card_id,
          name: (card && (card.name || card.oracle_name)) || item.name || item.card_id,
          quantity: item.quantity,
          owned: ownedCount,
          missing: need,
        });
      }
    }
    missingCards.sort((a, b) => a.name.localeCompare(b.name));
    return { total, owned, missing, missingCards };
  }

  function formatWishlistText(missingCards) {
    if (!Array.isArray(missingCards) || !missingCards.length) return "";
    const sorted = [...missingCards].sort((a, b) =>
      String(a.name || "").localeCompare(String(b.name || ""))
    );
    return sorted
      .filter((item) => Number(item.missing !== undefined ? item.missing : item.quantity || 0) > 0)
      .map((item) => {
        const count = Number(item.missing !== undefined ? item.missing : item.quantity || 1);
        return `${count} ${item.name}`;
      })
      .join("\n");
  }

  function matchesSuperfriendsFilter(card, kind) {
    if (!card || !kind) return true;
    if (kind === "planeswalker") {
      return /planeswalker/i.test(String(card.type_line || ""));
    }
    if (kind === "proliferate") {
      const oracle = String(card.oracle_text !== undefined ? card.oracle_text : card.text || "");
      return /proliferate/i.test(oracle);
    }
    if (kind === "missing") {
      return isUnowned(card);
    }
    return true;
  }

  return {
    isUnowned,
    summarizeDeckOwnership,
    formatWishlistText,
    matchesSuperfriendsFilter,
  };
})();
if (typeof module !== "undefined") module.exports = StudioWishlist;

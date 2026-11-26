"use strict";
// German game-sentence prompts, safe HTML stripping, and MTG mana-pip DOM rendering (#1826).
// Presentation-only layer over XMage bridge prompts and seat mana pools; computes no MTG rules.

const StudioPrompts = (() => {
  const POOL_ORDER = [
    { key: "white", symbol: "W", label: "Weiß" },
    { key: "blue", symbol: "U", label: "Blau" },
    { key: "black", symbol: "B", label: "Schwarz" },
    { key: "red", symbol: "R", label: "Rot" },
    { key: "green", symbol: "G", label: "Grün" },
    { key: "colorless", symbol: "C", label: "Farblos" },
  ];

  const ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&#x27;": "'",
  };

  function stripHtmlAndNormalize(raw) {
    if (raw === null || raw === undefined) return "";
    let text = String(raw);
    // XMage mana/ability hints embed Swing/HTML div and font markup.
    text = text.replace(/&(nbsp|amp|lt|gt|quot|#39|#x27);/gi, (match) => ENTITIES[match.toLowerCase()] || " ");
    text = text.replace(/<+\s*br\s*\/?\s*>+/gi, " ");
    for (let pass = 0; pass < 8 && /<+\s*\/?[a-zA-Z!][^<>]*>+/.test(text); pass += 1) {
      text = text.replace(/<+\s*\/?[a-zA-Z!][^<>]*>+/g, " ");
    }
    text = text.replace(/<+\s*\/?[a-zA-Z!][^<>]*$/g, " ");
    text = text.replace(/Full Game Seat (\d+)/g, "Sitz $1");
    return text.replace(/\s+/g, " ").trim();
  }

  function trimTrailingPunctuation(text) {
    return String(text || "").replace(/[.:!?]+$/, "").trim();
  }

  function cleanSubject(raw) {
    let s = stripHtmlAndNormalize(raw);
    // XMage puts redundant wrapper text inside cast/payment HTML blocks; drop pure noise fragments
    s = s.replace(/\(\s*\)/g, "").replace(/\s+/g, " ").trim();
    return trimTrailingPunctuation(s);
  }

  function isOwnActiveTurn(pending) {
    if (!pending || typeof pending !== "object") return false;
    const ps = pending.pilot_state;
    if (!ps || typeof ps !== "object") return false;
    if (pending.actor_id && ps.active_player_id) {
      return pending.actor_id === ps.active_player_id;
    }
    const players = Array.isArray(ps.players) ? ps.players : [];
    const active = players.find((p) => p && p.player_id === ps.active_player_id);
    return Boolean(active && Number.isInteger(pending.seat) && active.seat === pending.seat);
  }

  function translateSentenceBody(clean, decisionClass, ctx) {
    const lower = clean.toLowerCase();
    const minSel = ctx && ctx.minimum_selections !== undefined ? Number(ctx.minimum_selections) : null;
    const maxSel = ctx && ctx.maximum_selections !== undefined ? Number(ctx.maximum_selections) : null;

    if (lower === "choose priority action" || lower === "choose action") {
      return "Du hast Priorität — wähle eine Aktion oder gib ab.";
    }
    if (/^play spells and abilities/.test(lower)) {
      return "Du kannst jetzt Zauber wirken, ein Land spielen oder Priorität abgeben.";
    }

    const mulliganMatch = /^mulligan(?:\s*\((\d+)\))?/i.exec(clean);
    if (decisionClass === "mulligan" || mulliganMatch || /^keep hand\b/i.test(lower)) {
      return "Starthand behalten oder einen Mulligan nehmen?";
    }

    if (decisionClass === "mana_payment") {
      const unpaidRaw = ctx && typeof ctx.unpaid_mana === "string" ? stripHtmlAndNormalize(ctx.unpaid_mana) : "";
      const sym = "\\d+|[WUBRGCSX]|[WUBRGC2]\\/[WUBRGCP](?:\\/P)?";
      const singlePat = new RegExp(`\\{(${sym})\\}`, "gi");
      const leadingPat = new RegExp(`^\\s*((?:\\{(${sym})\\})+)`, "i");
      const groupPat = new RegExp(`((?:\\{(${sym})\\})+)`, "i");
      let tokenText = "";
      if (unpaidRaw) {
        const fromCtx = unpaidRaw.match(singlePat);
        tokenText = fromCtx ? fromCtx.join("") : "";
      } else {
        const leadingMatch = leadingPat.exec(clean);
        if (leadingMatch) {
          tokenText = leadingMatch[1];
        } else {
          const firstGroupMatch = groupPat.exec(clean);
          tokenText = firstGroupMatch ? firstGroupMatch[1] : "";
        }
      }
      if (tokenText) {
        return `Mana bezahlen — offen: ${tokenText}. Wähle eine Mana-Quelle oder Pool-Mana.`;
      }
      if (/^pay\b|^choose mana\b|^select mana\b/i.test(lower)) {
        const rest = clean.replace(/^(?:choose mana to pay|choose mana|select mana|pay)\s*:?\s*/i, "");
        return rest
          ? `Mana bezahlen (${rest}) — wähle eine Mana-Quelle oder Pool-Mana.`
          : "Mana bezahlen — wähle eine Mana-Quelle oder brich die Zahlung ab.";
      }
      return clean ? `Mana bezahlen: ${clean}` : "Mana bezahlen — wähle eine Mana-Quelle.";
    }

    if (/^select attackers?\b|^declare attackers?\b/i.test(lower)) {
      const attackerMatch = /(?:attack with|for)\s+(.+)$/i.exec(clean);
      return attackerMatch
        ? `Angreifer ansagen — wähle das Angriffsziel für ${trimTrailingPunctuation(attackerMatch[1])}.`
        : "Angreifer ansagen — wähle deine Angreifer und deren Ziele.";
    }

    if (/^select blockers?\b|^declare blockers?\b/i.test(lower)) {
      const blockerMatch = /(?:block with|for)\s+(.+)$/i.exec(clean);
      return blockerMatch
        ? `Blocker ansagen — wähle Angreifer, die ${trimTrailingPunctuation(blockerMatch[1])} blockt.`
        : "Blocker ansagen — wähle, welche Angreifer geblockt werden.";
    }

    const targetMatch = /^(?:select|choose)\s+target(?:\s+(.+))?$/i.exec(clean);
    if (targetMatch || decisionClass === "target") {
      const what = targetMatch && targetMatch[1] ? cleanSubject(targetMatch[1]) : cleanSubject(clean);
      if (!what || /^(?:select|choose)\s+target$/i.test(what)) return "Wähle ein legales Ziel für diesen Zauber oder diese Fähigkeit.";
      return `Wähle ein Ziel: ${what}`;
    }

    if (decisionClass === "target_amount") {
      return clean
        ? `Verteile die Menge auf die Ziele (${clean}).`
        : "Verteile Schaden oder Marken auf die gewählten Ziele.";
    }

    const discardMatch = /^discard\s+(?:a|an|(\d+))?\s*cards?\b(.*)$/i.exec(clean);
    if (discardMatch) {
      const countText = discardMatch[1] ? `${discardMatch[1]} Karten` : "eine Karte";
      const suffix = cleanSubject(discardMatch[2]);
      return suffix ? `Wirf ${countText} ab (${suffix}).` : `Wähle ${countText} zum Abwerfen.`;
    }

    const searchMatch = /^search (?:your )?library\b(.*)$/i.exec(clean);
    if (searchMatch) {
      const suffix = cleanSubject(searchMatch[1]);
      return suffix ? `Durchsuche deine Bibliothek${suffix.startsWith("for ") ? ` nach ${suffix.slice(4)}` : ` (${suffix})`}.` : "Durchsuche deine Bibliothek.";
    }

    const chooseColorMatch = /^choose a color\b(.*)$/i.exec(clean);
    if (chooseColorMatch) {
      return "Wähle eine Farbe für diesen Effekt.";
    }

    const chooseModeMatch = /^choose (?:a )?modes?\b(.*)$/i.exec(clean);
    if (chooseModeMatch || decisionClass === "mode") {
      return "Wähle den Modus, mit dem dieser Zauber oder diese Fähigkeit ausgeführt wird.";
    }

    if (decisionClass === "announce_x" || /^choose (?:value for )?x\b/i.test(lower)) {
      return "Lege den Wert für {X} fest.";
    }

    if (decisionClass === "amount" || decisionClass === "multi_amount" || /^choose (?:a )?number\b/i.test(lower)) {
      return "Lege die gewünschte Anzahl fest.";
    }

    if (decisionClass === "trigger_order" || decisionClass === "order" || /^order\b/i.test(lower)) {
      return "Lege die Reihenfolge fest (oberster Eintrag wird zuerst ausgeführt).";
    }

    if (decisionClass === "replacement_effect" || /^choose replacement/i.test(lower)) {
      return "Wähle, welcher Ersatzeffekt zuerst angewendet wird.";
    }

    if (decisionClass === "pile") {
      return "Wähle einen der angebotenen Stapel.";
    }

    if (decisionClass === "choose_use" || /^(?:do you want to|would you like to|use|may)\b/i.test(lower)) {
      if (lower.startsWith("put commander") || lower.includes("command zone")) {
        return "Soll dein Commander stattdessen in die Kommandozone zurückkehren?";
      }
      if (/^pay\s+(\{[^}]+\}|\d+)/i.test(lower)) {
        return `Möchtest du die Kosten bezahlen (${cleanSubject(clean)})?`;
      }
      return clean
        ? `Möchtest du diesen Effekt nutzen? (${cleanSubject(clean)})`
        : "Möchtest du diese Fähigkeit oder Option anwenden?";
    }

    const selectCardMatch = /^(?:select|choose)\s+(?:a|an|up to (\d+)|(\d+))?\s*(cards?|permanents?|creatures?|lands?|spells?|artifacts?|enchantments?|objects?)\b(.*)$/i.exec(clean);
    if (selectCardMatch) {
      const nounMap = {
        card: "Karte", cards: "Karten",
        permanent: "bleibende Karte", permanents: "bleibende Karten",
        creature: "Kreatur", creatures: "Kreaturen",
        land: "Land", lands: "Länder",
        spell: "Zauberspruch", spells: "Zaubersprüche",
        artifact: "Artefakt", artifacts: "Artefakte",
        enchantment: "Verzauberung", enchantments: "Verzauberungen",
        object: "Objekt", objects: "Objekte",
      };
      const noun = nounMap[selectCardMatch[3].toLowerCase()] || "Option";
      const upTo = selectCardMatch[1];
      const exactN = selectCardMatch[2];
      const countPrefix = upTo ? `bis zu ${upTo}× ` : exactN ? `${exactN}× ` : "";
      const tail = cleanSubject(selectCardMatch[4]);
      return tail ? `Wähle ${countPrefix}${noun} (${tail}).` : `Wähle ${countPrefix}${noun} aus.`;
    }

    if (decisionClass === "choose_object") {
      return clean ? `Wähle eine passende Karte oder Option (${cleanSubject(clean)}).` : "Wähle eines der angebotenen Objekte.";
    }

    if (minSel !== null && maxSel !== null && minSel === maxSel && minSel > 0) {
      return clean ? `Triff eine Auswahl (${cleanSubject(clean)}).` : `Wähle genau ${minSel} Option(en).`;
    }

    return clean ? `Auswahl erforderlich: ${clean}` : "Triff eine Entscheidung.";
  }

  function localizePrompt(pendingOrText, decisionClass, context) {
    const isObj = pendingOrText && typeof pendingOrText === "object";
    const pending = isObj ? pendingOrText : null;
    const dc = decisionClass || (pending && pending.decision_class) || "";
    const ctx = context || (pending && pending.context) || {};
    const rawPrompt = pending ? pending.prompt : pendingOrText;
    const clean = stripHtmlAndNormalize(rawPrompt);

    if (dc === "priority") {
      const ps = pending && pending.pilot_state;
      const stackLen = ps && Array.isArray(ps.stack) ? ps.stack.length : 0;
      if (isOwnActiveTurn(pending)) {
        return stackLen > 0
          ? "Du bist am Zug und ein Effekt liegt auf dem Stapel — reagieren oder abgeben?"
          : "Du bist am Zug — was möchtest du tun?";
      }
      if (pending) {
        return stackLen > 0
          ? "Du hast Priorität auf dem Stapel — möchtest du reagieren?"
          : "Du hast Priorität im gegnerischen Zug — reagieren oder passen?";
      }
    }

    const mergedCtx = pending
      ? Object.assign({}, ctx, {
          minimum_selections: pending.minimum_selections,
          maximum_selections: pending.maximum_selections,
        })
      : ctx;
    return translateSentenceBody(clean, dc, mergedCtx);
  }

  function localizeOptionLabel(text) {
    const clean = stripHtmlAndNormalize(text);
    if (!clean) return "";
    const lower = clean.toLowerCase();
    if (lower === "keep opening hand" || lower === "keep hand" || lower === "keep") return "Starthand behalten";
    if (lower === "take mulligan" || lower === "mulligan") return "Mulligan nehmen";
    if (lower === "yes") return "Ja";
    if (lower === "no") return "Nein";
    if (lower === "cancel" || lower === "cancel mana payment") return "Zahlung abbrechen";
    if (lower === "pass priority" || lower === "pass") return "Priorität abgeben";
    if (lower === "hold attacker" || lower === "no attackers") return "Nicht angreifen";
    if (lower === "done" || lower === "confirm") return "Bestätigen";
    if (lower === "skip") return "Überspringen";
    if (/^put on top$/i.test(lower)) return "Oben auf die Bibliothek legen";
    if (/^put on bottom$/i.test(lower)) return "Unten unter die Bibliothek legen";
    if (/^move to command zone$/i.test(lower)) return "In die Kommandozone legen";
    if (/^leave in (?:graveyard|exile)$/i.test(lower)) {
      return lower.includes("graveyard") ? "Im Friedhof lassen" : "Im Exil lassen";
    }
    return clean;
  }

  function pipMeta(rawToken) {
    const token = String(rawToken || "").trim().toUpperCase();
    const colorMap = {
      W: { cls: "mana-w", text: "W", title: "Weißes Mana" },
      U: { cls: "mana-u", text: "U", title: "Blaues Mana" },
      B: { cls: "mana-b", text: "B", title: "Schwarzes Mana" },
      R: { cls: "mana-r", text: "R", title: "Rotes Mana" },
      G: { cls: "mana-g", text: "G", title: "Grünes Mana" },
      C: { cls: "mana-c", text: "C", title: "Farbloses Mana" },
      S: { cls: "mana-c", text: "S", title: "Schnee-Mana" },
      X: { cls: "mana-generic", text: "X", title: "Variables Mana X" },
      T: { cls: "mana-tap", text: "⟳", title: "Tappen" },
      Q: { cls: "mana-tap", text: "↺", title: "Enttappen" },
    };
    if (colorMap[token]) return colorMap[token];
    if (/^\d+$/.test(token)) return { cls: "mana-generic", text: token, title: `${token} beliebiges Mana` };
    if (token.includes("/")) {
      const compact = token.replace(/\s+/g, "");
      const firstColor = compact.split("/")[0];
      const base = colorMap[firstColor];
      return {
        cls: base ? `${base.cls} mana-hybrid` : "mana-generic mana-hybrid",
        text: compact,
        title: `Hybrid-/Phyrexian-Mana (${compact})`,
      };
    }
    return { cls: "mana-generic", text: token, title: `Symbol ${token}` };
  }

  // Builds pure DOM nodes (text + styled .mana-pip spans) without innerHTML.
  function renderRichGameText(h, rawText) {
    const clean = stripHtmlAndNormalize(rawText);
    if (!clean) return [];
    const nodes = [];
    const pattern = /\{(\d+|[WUBRGCSXPTQ]|[WUBRGC2]\/[WUBRGCP](?:\/P)?)\}/gi;
    let cursor = 0;
    let match;
    while ((match = pattern.exec(clean)) !== null) {
      if (match.index > cursor) {
        nodes.push(clean.slice(cursor, match.index));
      }
      const meta = pipMeta(match[1]);
      nodes.push(h("span", {
        class: `mana-pip ${meta.cls}`,
        title: meta.title,
        "aria-label": meta.title,
      }, meta.text));
      cursor = pattern.lastIndex;
    }
    if (cursor < clean.length) {
      nodes.push(clean.slice(cursor));
    }
    return nodes;
  }

  function renderManaPoolPips(h, manaPool) {
    if (!manaPool || typeof manaPool !== "object") return null;
    const entries = POOL_ORDER.map((spec) => {
      const count = Number(manaPool[spec.key] ?? 0);
      return { ...spec, count: Number.isFinite(count) ? count : 0 };
    });
    const total = entries.reduce((sum, item) => sum + item.count, 0);
    return h("span", {
      class: `mana-pool-pips${total > 0 ? " has-mana" : ""}`,
      role: "group",
      "aria-label": total > 0
        ? `Mana-Pool: ${entries.filter((e) => e.count > 0).map((e) => `${e.count} ${e.label}`).join(", ")}`
        : "Mana-Pool leer",
    },
    entries.map((item) => h("span", {
      class: `mana-pool-chip${item.count > 0 ? " active" : " empty"}`,
      "data-mana-color": item.key,
      "data-mana-symbol": item.symbol,
      "data-mana-count": String(item.count),
      title: `${item.label}: ${item.count}`,
    },
    h("span", { class: `mana-pip mana-${item.symbol.toLowerCase()}`, "aria-hidden": "true" }, item.symbol),
    h("span", { class: "mana-pool-count" }, String(item.count)))));
  }

  return {
    POOL_ORDER,
    stripHtmlAndNormalize,
    localizePrompt,
    localizeOptionLabel,
    renderRichGameText,
    renderManaPoolPips,
  };
})();

"use strict";
// Card search ranking and structured field/operator query parser (#1451) for the Studio pool and
// tier list views. Plain freetext queries keep the exact ranking order (0 exact name, 1 name
// prefix, 2 word prefix, 3 name contains, 4 type line or oracle text contains; alphabetical
// inside a rank). Field/operator queries filter before ranking and surface syntax errors visibly
// instead of returning a silent empty list.

const StudioSearch = (() => {
  // Case-insensitive and sharp-s tolerant ("strasse" finds "Straße"), composed form.
  const fold = (text) => String(text || "").normalize("NFC").toLowerCase().replace(/ß/g, "ss");

  const FIELD_ALIASES = {
    t: "type",
    type: "type",
    typ: "type",
    o: "oracle",
    oracle: "oracle",
    text: "oracle",
    n: "name",
    name: "name",
    r: "role",
    role: "role",
    rolle: "role",
    fn: "role",
    l: "label",
    label: "label",
    tag: "label",
    marke: "label",
    c: "color",
    color: "color",
    colour: "color",
    farbe: "color",
    id: "identity",
    ci: "identity",
    identity: "identity",
    mv: "mv",
    cmc: "mv",
    manavalue: "mv",
    manawert: "mv",
    is: "is",
    has: "is",
  };

  const TYPE_ALIASES = {
    kreatur: "creature",
    kreaturen: "creature",
    spontanzauber: "instant",
    hexerei: "sorcery",
    artefakt: "artifact",
    verzauberung: "enchantment",
    land: "land",
    laender: "land",
    länder: "land",
    planeswalker: "planeswalker",
    schlacht: "battle",
    legende: "legendary",
    legendaer: "legendary",
    legendär: "legendary",
    standardland: "basic",
  };

  const COLOR_ALIASES = {
    c: { colorless: true, letters: "" },
    colorless: { colorless: true, letters: "" },
    farblos: { colorless: true, letters: "" },
    none: { colorless: true, letters: "" },
    w: { colorless: false, letters: "W" },
    white: { colorless: false, letters: "W" },
    weiss: { colorless: false, letters: "W" },
    weiß: { colorless: false, letters: "W" },
    u: { colorless: false, letters: "U" },
    blue: { colorless: false, letters: "U" },
    blau: { colorless: false, letters: "U" },
    b: { colorless: false, letters: "B" },
    black: { colorless: false, letters: "B" },
    schwarz: { colorless: false, letters: "B" },
    r: { colorless: false, letters: "R" },
    red: { colorless: false, letters: "R" },
    rot: { colorless: false, letters: "R" },
    g: { colorless: false, letters: "G" },
    green: { colorless: false, letters: "G" },
    gruen: { colorless: false, letters: "G" },
    grün: { colorless: false, letters: "G" },
    azorius: { colorless: false, letters: "WU" },
    dimir: { colorless: false, letters: "UB" },
    rakdos: { colorless: false, letters: "BR" },
    gruul: { colorless: false, letters: "RG" },
    selesnya: { colorless: false, letters: "GW" },
    orzhov: { colorless: false, letters: "WB" },
    izzet: { colorless: false, letters: "UR" },
    golgari: { colorless: false, letters: "BG" },
    boros: { colorless: false, letters: "RW" },
    simic: { colorless: false, letters: "UG" },
    bant: { colorless: false, letters: "GWU" },
    esper: { colorless: false, letters: "WUB" },
    grixis: { colorless: false, letters: "UBR" },
    jund: { colorless: false, letters: "BRG" },
    naya: { colorless: false, letters: "RGW" },
    abzan: { colorless: false, letters: "WBG" },
    jeskai: { colorless: false, letters: "URW" },
    sultai: { colorless: false, letters: "BGU" },
    mardu: { colorless: false, letters: "RWB" },
    temur: { colorless: false, letters: "GUR" },
  };

  const IS_VALUES = new Set([
    "legendary",
    "legende",
    "commander",
    "basic",
    "standardland",
    "gamechanger",
    "gc",
    "fav",
    "favorite",
    "favorit",
    "free",
    "frei",
    "excluded",
    "ausgeschlossen",
  ]);

  function parseColors(rawVal) {
    const clean = fold(rawVal).trim();
    if (!clean) return null;
    if (Object.prototype.hasOwnProperty.call(COLOR_ALIASES, clean)) {
      return COLOR_ALIASES[clean];
    }
    if (/^[wubrgc]+$/i.test(clean)) {
      const upper = clean.toUpperCase();
      if (upper === "C") return { colorless: true, letters: "" };
      const letters = ["W", "U", "B", "R", "G"].filter((ch) => upper.includes(ch)).join("");
      return { colorless: false, letters };
    }
    return null;
  }

  function tokenize(raw) {
    const tokens = [];
    let current = "";
    let inQuotes = false;
    let hadQuotes = false;
    let startedWithQuote = false;
    let endedWithQuote = false;

    for (let i = 0; i < raw.length; i += 1) {
      const ch = raw[i];
      if (ch === '"') {
        if (!inQuotes && current.length === 0) startedWithQuote = true;
        inQuotes = !inQuotes;
        hadQuotes = true;
        endedWithQuote = !inQuotes && (i + 1 === raw.length || /\s/.test(raw[i + 1]));
        current += ch;
      } else if (!inQuotes && /\s/.test(ch)) {
        if (current.length > 0) {
          tokens.push({
            text: current,
            hadQuotes,
            standaloneQuoted: startedWithQuote && endedWithQuote && current.startsWith('"') && current.endsWith('"'),
          });
          current = "";
          hadQuotes = false;
          startedWithQuote = false;
          endedWithQuote = false;
        }
      } else {
        current += ch;
        endedWithQuote = false;
      }
    }
    if (current.length > 0) {
      tokens.push({
        text: current,
        hadQuotes,
        standaloneQuoted: !inQuotes && startedWithQuote && current.startsWith('"') && current.endsWith('"'),
      });
    }
    return { tokens, unclosedQuote: inQuotes };
  }

  function stripQuotes(str) {
    const s = String(str || "").trim();
    if (s.length >= 2 && s.startsWith('"') && s.endsWith('"')) {
      return s.slice(1, -1);
    }
    return s;
  }

  function parseQuery(rawQuery) {
    const raw = String(rawQuery || "");
    const trimmed = raw.trim();
    if (!trimmed) {
      return { raw: "", isPlainFreetext: true, textQuery: "", clauses: [], errors: [] };
    }

    const { tokens, unclosedQuote } = tokenize(trimmed);
    const errors = [];
    const clauses = [];
    const positiveWords = [];

    if (unclosedQuote) {
      errors.push('Nicht geschlossenes Anführungszeichen (") in der Suchanfrage.');
    }

    for (const tok of tokens) {
      const t = tok.text;

      // Standalone quoted phrase: "Sol Ring" or "draw a card"
      if (tok.standaloneQuoted) {
        const inner = stripQuotes(t).trim();
        if (!inner) {
          errors.push('Leere Phrasensuche ("") — bitte Suchbegriff zwischen den Anführungszeichen angeben.');
        } else {
          clauses.push({ kind: "phrase", negated: false, value: fold(inner) });
          positiveWords.push(inner);
        }
        continue;
      }

      // Negated quoted phrase: -"Sol Ring"
      if (t.startsWith('-"') && t.endsWith('"') && t.length >= 3) {
        const inner = stripQuotes(t.slice(1)).trim();
        if (!inner) {
          errors.push('Leere negierte Phrasensuche (-"") — bitte Suchbegriff angeben.');
        } else {
          clauses.push({ kind: "phrase", negated: true, value: fold(inner) });
        }
        continue;
      }

      // Leading operator without field name (e.g. ":creature" or ">=3")
      const leadingOp = t.match(/^(-)?(:|!=|<=|>=|=|<|>)(.*)$/);
      if (leadingOp) {
        errors.push(`Ungültiger Operator am Wortanfang „${t}“ (Feldname vor „${leadingOp[2]}“ erwartet, z. B. mv${leadingOp[2]}2).`);
        continue;
      }

      // Field + operator expression: [-]<field>(:|!=|<=|>=|=|<|> value)
      const opMatch = t.match(/^(-)?([a-zA-Z_äöüÄÖÜ]+)(:|!=|<=|>=|=|<|>)(.*)$/);
      if (opMatch) {
        let negated = Boolean(opMatch[1]);
        const fieldNameRaw = opMatch[2];
        const fieldKey = fold(fieldNameRaw);
        const op = opMatch[3];
        const valPart = stripQuotes(opMatch[4]).trim();

        if (!Object.prototype.hasOwnProperty.call(FIELD_ALIASES, fieldKey)) {
          errors.push(`Unbekanntes Suchfeld „${fieldNameRaw}“ (erlaubt: t, o, r, c, id, mv, l, n, is).`);
          continue;
        }
        const canonical = FIELD_ALIASES[fieldKey];
        if (!valPart) {
          errors.push(`Fehlender Wert nach „${fieldNameRaw}${op}“.`);
          continue;
        }

        if (canonical === "mv") {
          const vFold = fold(valPart);
          if (vFold === "even" || vFold === "gerade" || vFold === "odd" || vFold === "ungerade") {
            if (op !== ":" && op !== "=" && op !== "!=") {
              errors.push(`Operator „${op}“ ist bei ${fieldNameRaw}:${valPart} nicht erlaubt (nutze : oder =).`);
              continue;
            }
            if (op === "!=") negated = !negated;
            const parity = vFold === "even" || vFold === "gerade" ? "even" : "odd";
            clauses.push({ kind: "mv_parity", negated, parity });
            continue;
          }
          const normalizedNum = valPart.replace(",", ".");
          if (!/^\d+(?:\.\d+)?$/.test(normalizedNum)) {
            errors.push(`Ungültiger Zahlenwert „${valPart}“ bei ${fieldNameRaw}${op} (Zahl oder even/odd erwartet).`);
            continue;
          }
          clauses.push({
            kind: "mv",
            negated,
            op: op === ":" ? "=" : op,
            number: Number(normalizedNum),
          });
          continue;
        }

        if (canonical === "color" || canonical === "identity") {
          const parsedCol = parseColors(valPart);
          if (!parsedCol) {
            errors.push(`Unbekannte Farbangabe „${valPart}“ bei ${fieldNameRaw}${op} (erlaubt: W, U, B, R, G, C).`);
            continue;
          }
          clauses.push({
            kind: canonical,
            negated,
            op,
            colorless: parsedCol.colorless,
            letters: parsedCol.letters,
          });
          continue;
        }

        // Text / categorical fields: only :, =, != allowed
        if (op !== ":" && op !== "=" && op !== "!=") {
          errors.push(`Operator „${op}“ wird für Feld „${fieldNameRaw}“ nicht unterstützt (nutze : oder =).`);
          continue;
        }
        if (op === "!=") negated = !negated;

        if (canonical === "is") {
          const isVal = fold(valPart);
          if (!IS_VALUES.has(isVal)) {
            errors.push(`Unbekannte Eigenschaft „${valPart}“ bei ${fieldNameRaw}${op} (erlaubt: legendary, basic, gamechanger, fav, free, excluded).`);
            continue;
          }
          clauses.push({ kind: "is", negated, value: isVal });
          continue;
        }

        if (canonical === "type") {
          const mapped = TYPE_ALIASES[fold(valPart)] || fold(valPart);
          clauses.push({ kind: "type", negated, value: mapped, rawValue: fold(valPart) });
          continue;
        }

        clauses.push({ kind: canonical, negated, value: fold(valPart) });
        continue;
      }

      // Negated freetext word: -island
      if (t.startsWith("-")) {
        const inner = stripQuotes(t.slice(1)).trim();
        if (!inner) {
          errors.push("Fehlender Suchbegriff nach „-“.");
        } else {
          clauses.push({ kind: "phrase", negated: true, value: fold(inner) });
        }
        continue;
      }

      // Plain freetext word
      positiveWords.push(stripQuotes(t));
    }

    const isPlainFreetext = clauses.length === 0 && errors.length === 0;
    return {
      raw: trimmed,
      isPlainFreetext,
      textQuery: positiveWords.join(" ").trim(),
      clauses,
      errors,
    };
  }

  function cardRolesList(card) {
    if (Array.isArray(card.roles)) {
      return card.roles.map((r) => fold(typeof r === "string" ? r : r && r.role ? r.role : ""));
    }
    if (card.layers && card.layers.fact && Array.isArray(card.layers.fact.roles)) {
      return card.layers.fact.roles.map((r) => fold(r && r.role ? r.role : ""));
    }
    return [];
  }

  function cardLabelsList(card) {
    if (Array.isArray(card.labels)) {
      return card.labels.map((l) => fold(l));
    }
    return [];
  }

  function cardColorsString(card) {
    const raw = card.colors !== undefined && card.colors !== null
      ? card.colors
      : (card.color_identity !== undefined && card.color_identity !== null
        ? card.color_identity
        : (card.layers && card.layers.fact && card.layers.fact.colors) || "");
    return String(raw || "").toUpperCase().replace(/[^WUBRG]/g, "");
  }

  function matchColorClause(cardColors, clause) {
    const cardSet = new Set([...cardColors]);
    const targetSet = new Set([...clause.letters]);
    const isSubset = (a, b) => [...a].every((x) => b.has(x));
    const isEqual = (a, b) => a.size === b.size && isSubset(a, b);

    if (clause.colorless) {
      if (clause.op === "!=") return cardSet.size !== 0;
      return cardSet.size === 0;
    }

    if (clause.op === "=") return isEqual(cardSet, targetSet);
    if (clause.op === "!=") return !isEqual(cardSet, targetSet);
    if (clause.op === "<=") return isSubset(cardSet, targetSet);
    if (clause.op === "<") return isSubset(cardSet, targetSet) && cardSet.size < targetSet.size;
    if (clause.op === ">=") return isSubset(targetSet, cardSet);
    if (clause.op === ">") return isSubset(targetSet, cardSet) && cardSet.size > targetSet.size;

    // Default ":" operator:
    // - For identity (id:/ci:), card's color identity must fit within targetSet (subset).
    // - For color (c:), card must contain all requested colors (superset).
    if (clause.kind === "identity") {
      return isSubset(cardSet, targetSet);
    }
    return isSubset(targetSet, cardSet);
  }

  function matchClause(card, clause) {
    const name = fold(card.name);
    const typeLine = fold(card.type_line);
    const group = fold(card.group);
    const text = fold(card.text !== undefined ? card.text : card.oracle_text);
    const german = Array.isArray(card.names_de) ? card.names_de.map(fold) : [];
    const hay = [name, typeLine, text, ...german].join("\n");

    let result = false;
    switch (clause.kind) {
      case "phrase":
        result = hay.includes(clause.value);
        break;
      case "name":
        result = name.includes(clause.value) || german.some((item) => item.includes(clause.value));
        break;
      case "type":
        result = typeLine.includes(clause.value)
          || group.includes(clause.value)
          || (clause.rawValue ? typeLine.includes(clause.rawValue) || group.includes(clause.rawValue) : false);
        break;
      case "oracle":
        result = text.includes(clause.value);
        break;
      case "role": {
        const roles = cardRolesList(card);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = roles.length === 0;
        } else {
          result = roles.some((r) => r === clause.value || r.includes(clause.value));
        }
        break;
      }
      case "label": {
        const labels = cardLabelsList(card);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = labels.length === 0;
        } else {
          result = labels.some((l) => l === clause.value || l.includes(clause.value));
        }
        break;
      }
      case "mv": {
        const mv = card.mana_value;
        if (mv === null || mv === undefined || Number.isNaN(Number(mv))) {
          result = false;
        } else {
          const n = Number(mv);
          if (clause.op === "=") result = n === clause.number;
          else if (clause.op === "!=") result = n !== clause.number;
          else if (clause.op === "<") result = n < clause.number;
          else if (clause.op === "<=") result = n <= clause.number;
          else if (clause.op === ">") result = n > clause.number;
          else if (clause.op === ">=") result = n >= clause.number;
        }
        break;
      }
      case "mv_parity": {
        const mv = card.mana_value;
        if (mv === null || mv === undefined || Number.isNaN(Number(mv))) {
          result = false;
        } else {
          const intMv = Math.round(Number(mv));
          result = clause.parity === "even" ? intMv % 2 === 0 : Math.abs(intMv % 2) === 1;
        }
        break;
      }
      case "color":
      case "identity":
        result = matchColorClause(cardColorsString(card), clause);
        break;
      case "is": {
        const v = clause.value;
        if (v === "legendary" || v === "legende" || v === "commander") {
          result = typeLine.includes("legendary");
        } else if (v === "basic" || v === "standardland") {
          result = Boolean(card.is_basic_land) || typeLine.includes("basic");
        } else if (v === "gamechanger" || v === "gc") {
          result = Boolean(card.game_changer);
        } else if (v === "fav" || v === "favorite" || v === "favorit") {
          result = Boolean(card.favorite);
        } else if (v === "free" || v === "frei") {
          result = Number(card.available || 0) > 0;
        } else if (v === "excluded" || v === "ausgeschlossen") {
          result = Boolean(card.excluded);
        }
        break;
      }
      default:
        result = false;
    }
    return clause.negated ? !result : result;
  }

  // 0 exact name, 1 name starts with the query, 2 a word of the name starts with it,
  // 3 the name contains it, 4 type line or oracle text contains it, null no match.
  function nameRank(name, q) {
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
    return null;
  }

  // The German printed names (card.names_de, #1553) rank like the Oracle name; the card
  // is shown under its Oracle name either way.
  function germanNameRank(card, q) {
    if (!Array.isArray(card.names_de)) return null;
    let best = null;
    for (const german of card.names_de) {
      const r = nameRank(fold(german), q);
      if (r !== null && (best === null || r < best)) best = r;
    }
    return best;
  }

  function baseRank(card, query) {
    const q = fold(query).trim();
    if (!q) return 0;
    const name = fold(card.name);
    const byName = nameRank(name, q);
    const byGerman = germanNameRank(card, q);
    if (byName !== null || byGerman !== null) return Math.min(byName ?? 99, byGerman ?? 99);
    const text = fold(card.text !== undefined ? card.text : card.oracle_text);
    const hay = `${name}\n${fold(card.type_line)}\n${text}`;
    if (hay.includes(q)) return 4;
    // several words: every word must be found somewhere; all in the name beats the text
    const words = q.split(/\s+/).filter(Boolean);
    if (words.length > 1 && words.every((word) => hay.includes(word))) {
      return words.every((word) => name.includes(word)) ? 3 : 4;
    }
    return null;
  }

  function rank(card, queryOrParsed) {
    const parsed = typeof queryOrParsed === "object" && queryOrParsed !== null && Array.isArray(queryOrParsed.clauses)
      ? queryOrParsed
      : parseQuery(queryOrParsed);
    if (parsed.errors.length > 0) return null;
    if (parsed.isPlainFreetext) {
      return baseRank(card, parsed.textQuery);
    }
    for (const clause of parsed.clauses) {
      if (!matchClause(card, clause)) return null;
    }
    if (parsed.textQuery) {
      return baseRank(card, parsed.textQuery);
    }
    return 0;
  }

  function sortByRank(cards, queryOrParsed) {
    const parsed = typeof queryOrParsed === "object" && queryOrParsed !== null && Array.isArray(queryOrParsed.clauses)
      ? queryOrParsed
      : parseQuery(queryOrParsed);
    if (parsed.errors.length > 0) return [];
    const scored = [];
    for (const card of cards) {
      const r = rank(card, parsed);
      if (r !== null) scored.push([r, card]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1].name.localeCompare(b[1].name));
    return scored.map((item) => item[1]);
  }

  const SYNTAX_EXAMPLES = [
    { op: "t:creature", label: "Kreaturen" },
    { op: "mv<=2", label: "Manawert ≤ 2" },
    { op: "r:ramp", label: "Rolle Ramp" },
    { op: "c:gu", label: "Farbe GU" },
    { op: "id<=gwu", label: "Identität Bant" },
    { op: "-t:land", label: "ohne Länder" },
    { op: 'o:"draw a card"', label: "Regeltext" },
    { op: "is:fav", label: "Favoriten" },
    { op: "is:free", label: "nur freie" },
  ];

  function appendOperator(currentQuery, operatorToken) {
    const base = String(currentQuery || "").trim();
    const token = String(operatorToken || "").trim();
    if (!token) return base;
    if (!base) return token;
    const parts = tokenize(base).tokens.map((item) => item.text);
    if (parts.includes(token)) return base;
    return `${base} ${token}`;
  }

  function attachSyntaxHelper(inputEl, onApply) {
    if (!inputEl || typeof document === "undefined" || inputEl.dataset.syntaxHelpAttached === "1") {
      return null;
    }
    inputEl.dataset.syntaxHelpAttached = "1";
    const wrap = document.createElement("span");
    wrap.className = "search-help-wrap";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip search-help-btn";
    btn.textContent = "?";
    btn.title = "Such-Operatoren einfügen (z. B. t:creature, mv<=2, r:ramp)";
    btn.setAttribute("aria-label", "Such-Operatoren anzeigen");
    btn.setAttribute("aria-expanded", "false");

    const pop = document.createElement("div");
    pop.className = "search-help-popover";
    pop.hidden = true;
    pop.setAttribute("role", "region");
    pop.setAttribute("aria-label", "Such-Operatoren");

    const head = document.createElement("div");
    head.className = "search-help-title";
    head.textContent = "Such-Operatoren (Klick fügt ein):";
    pop.appendChild(head);

    const chips = document.createElement("div");
    chips.className = "chips";
    for (const item of SYNTAX_EXAMPLES) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.title = item.label;
      chip.textContent = item.op;
      chip.addEventListener("click", () => {
        inputEl.value = appendOperator(inputEl.value, item.op);
        inputEl.focus();
        if (typeof onApply === "function") onApply(inputEl.value);
      });
      chips.appendChild(chip);
    }
    pop.appendChild(chips);

    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const next = pop.hidden;
      pop.hidden = !next;
      btn.setAttribute("aria-expanded", String(next));
    });
    document.addEventListener("click", (event) => {
      if (!pop.hidden && !wrap.contains(event.target)) {
        pop.hidden = true;
        btn.setAttribute("aria-expanded", "false");
      }
    });

    wrap.appendChild(btn);
    wrap.appendChild(pop);
    inputEl.insertAdjacentElement("afterend", wrap);
    return { wrap, button: btn, popover: pop };
  }

  return { rank, sortByRank, parseQuery, baseRank, SYNTAX_EXAMPLES, appendOperator, attachSyntaxHelper };
})();
if (typeof module !== "undefined") module.exports = StudioSearch;

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
    sub: "subtype",
    subtype: "subtype",
    untertyp: "subtype",
    super: "supertype",
    supertype: "supertype",
    uebertyp: "supertype",
    "übertyp": "supertype",
    o: "oracle",
    oracle: "oracle",
    text: "oracle",
    kw: "keyword",
    keyword: "keyword",
    keywords: "keyword",
    schluesselwort: "keyword",
    "schlüsselwort": "keyword",
    n: "name",
    name: "name",
    r: "role",
    role: "role",
    rolle: "role",
    fn: "role",
    otag: "otag",
    oracletag: "otag",
    cat: "otag",
    category: "otag",
    kategorie: "otag",
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

  const SUPERTYPES = new Set(["basic", "legendary", "ongoing", "snow", "world"]);

  const SUPERTYPE_ALIASES = {
    legende: "legendary",
    legendaer: "legendary",
    "legendär": "legendary",
    standard: "basic",
    standardland: "basic",
    schnee: "snow",
  };

  const SUBTYPE_ALIASES = {
    elfen: "elf",
    drache: "dragon",
    drachen: "dragon",
    mensch: "human",
    menschen: "human",
    engel: "angel",
    zauberer: "wizard",
    magier: "wizard",
    krieger: "warrior",
    soldat: "soldier",
    druide: "druid",
    druiden: "druid",
    bestie: "beast",
    bestien: "beast",
    vogel: "bird",
    "vögel": "bird",
    voegel: "bird",
    geist: "spirit",
    geister: "spirit",
    riese: "giant",
    riesen: "giant",
    daemon: "demon",
    "dämon": "demon",
    schlange: "snake",
    schlangen: "snake",
    vampir: "vampire",
    vampire: "vampire",
    goblin: "goblin",
    zombie: "zombie",
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

    const flushCurrent = () => {
      if (current.length === 0) return;
      const standaloneQuoted = !inQuotes && startedWithQuote && endedWithQuote && current.startsWith('"') && current.endsWith('"');
      const isOr = !hadQuotes && fold(current) === "or";
      tokens.push({
        type: isOr ? "OR" : "TERM",
        text: current,
        hadQuotes,
        standaloneQuoted,
      });
      current = "";
      hadQuotes = false;
      startedWithQuote = false;
      endedWithQuote = false;
    };

    for (let i = 0; i < raw.length; i += 1) {
      const ch = raw[i];
      if (ch === '"') {
        if (!inQuotes && current.length === 0) startedWithQuote = true;
        inQuotes = !inQuotes;
        hadQuotes = true;
        endedWithQuote = !inQuotes && (i + 1 === raw.length || /\s|\)/.test(raw[i + 1]));
        current += ch;
      } else if (!inQuotes && /\s/.test(ch)) {
        flushCurrent();
      } else if (!inQuotes && ch === "(") {
        if (current === "-" && !hadQuotes) {
          tokens.push({ type: "NOT_LPAREN", text: "-(", hadQuotes: false, standaloneQuoted: false });
          current = "";
          hadQuotes = false;
          startedWithQuote = false;
          endedWithQuote = false;
        } else {
          flushCurrent();
          tokens.push({ type: "LPAREN", text: "(", hadQuotes: false, standaloneQuoted: false });
        }
      } else if (!inQuotes && ch === ")") {
        flushCurrent();
        tokens.push({ type: "RPAREN", text: ")", hadQuotes: false, standaloneQuoted: false });
      } else {
        current += ch;
        endedWithQuote = false;
      }
    }
    if (current.length > 0) {
      const standaloneQuoted = !inQuotes && startedWithQuote && current.startsWith('"') && current.endsWith('"');
      const isOr = !hadQuotes && fold(current) === "or";
      tokens.push({
        type: isOr ? "OR" : "TERM",
        text: current,
        hadQuotes,
        standaloneQuoted,
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

  function parseTermToken(tok, errors, clauses, positiveWords) {
    const t = tok.text;

    if (!tok.hadQuotes && (t === "||" || t === "|" || t === "&&" || t === "&" || t === "!")) {
      const hint = t === "!" ? "Nutze „-“ vor einem Ausdruck oder einer Klammer (z. B. -t:land oder -(t:land or mv>=4))."
        : (t === "|" || t === "||") ? "Nutze „or“ statt „" + t + "“ (z. B. t:artifact or t:creature)."
        : "Leerzeichen verknüpfen automatisch mit UND; „" + t + "“ ist nicht nötig.";
      errors.push(`Nicht unterstützter Operator „${t}“. ${hint}`);
      return null;
    }

    // Standalone quoted phrase: "Sol Ring" or "draw a card"
    if (tok.standaloneQuoted) {
      const inner = stripQuotes(t).trim();
      if (!inner) {
        errors.push('Leere Phrasensuche ("") — bitte Suchbegriff zwischen den Anführungszeichen angeben.');
        return null;
      }
      const clause = { kind: "phrase", negated: false, value: fold(inner), rawValue: inner };
      clauses.push(clause);
      positiveWords.push(inner);
      return { type: "clause", clause };
    }

    // Negated quoted phrase: -"Sol Ring"
    if (t.startsWith('-"') && t.endsWith('"') && t.length >= 3) {
      const inner = stripQuotes(t.slice(1)).trim();
      if (!inner) {
        errors.push('Leere negierte Phrasensuche (-"") — bitte Suchbegriff angeben.');
        return null;
      }
      const clause = { kind: "phrase", negated: true, value: fold(inner), rawValue: inner };
      clauses.push(clause);
      return { type: "clause", clause };
    }

    // Unsupported "!field:..." prefix
    if (!tok.hadQuotes && /^!(?:[a-zA-Z_äöüÄÖÜ]+[:=<>]|\(|")/.test(t)) {
      errors.push(`Nicht unterstütztes Negationszeichen „!“ in „${t}“ (nutze „-“ statt „!“).`);
      return null;
    }

    // Leading operator without field name (e.g. ":creature" or ">=3")
    const leadingOp = t.match(/^(-)?(:|!=|<=|>=|=|<|>)(.*)$/);
    if (leadingOp) {
      errors.push(`Ungültiger Operator am Wortanfang „${t}“ (Feldname vor „${leadingOp[2]}“ erwartet, z. B. mv${leadingOp[2]}2).`);
      return null;
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
        errors.push(`Unbekanntes Suchfeld „${fieldNameRaw}“ (erlaubt: t, subtype, super, o, kw, r, otag, c, id, mv, l, n, is).`);
        return null;
      }
      const canonical = FIELD_ALIASES[fieldKey];
      if (!valPart) {
        errors.push(`Fehlender Wert nach „${fieldNameRaw}${op}“.`);
        return null;
      }

      if (canonical === "mv") {
        const vFold = fold(valPart);
        if (vFold === "even" || vFold === "gerade" || vFold === "odd" || vFold === "ungerade") {
          if (op !== ":" && op !== "=" && op !== "!=") {
            errors.push(`Operator „${op}“ ist bei ${fieldNameRaw}:${valPart} nicht erlaubt (nutze : oder =).`);
            return null;
          }
          if (op === "!=") negated = !negated;
          const parity = vFold === "even" || vFold === "gerade" ? "even" : "odd";
          const clause = { kind: "mv_parity", negated, parity };
          clauses.push(clause);
          return { type: "clause", clause };
        }
        const normalizedNum = valPart.replace(",", ".");
        if (!/^\d+(?:\.\d+)?$/.test(normalizedNum)) {
          errors.push(`Ungültiger Zahlenwert „${valPart}“ bei ${fieldNameRaw}${op} (Zahl oder even/odd erwartet).`);
          return null;
        }
        const clause = {
          kind: "mv",
          negated,
          op: op === ":" ? "=" : op,
          number: Number(normalizedNum),
        };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      if (canonical === "color" || canonical === "identity") {
        const parsedCol = parseColors(valPart);
        if (!parsedCol) {
          errors.push(`Unbekannte Farbangabe „${valPart}“ bei ${fieldNameRaw}${op} (erlaubt: W, U, B, R, G, C).`);
          return null;
        }
        const clause = {
          kind: canonical,
          negated,
          op,
          colorless: parsedCol.colorless,
          letters: parsedCol.letters,
        };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      // Text / categorical fields: only :, =, != allowed
      if (op !== ":" && op !== "=" && op !== "!=") {
        errors.push(`Operator „${op}“ wird für Feld „${fieldNameRaw}“ nicht unterstützt (nutze : oder =).`);
        return null;
      }
      if (op === "!=") negated = !negated;

      if (canonical === "is") {
        const isVal = fold(valPart);
        if (!IS_VALUES.has(isVal)) {
          errors.push(`Unbekannte Eigenschaft „${valPart}“ bei ${fieldNameRaw}${op} (erlaubt: legendary, basic, gamechanger, fav, free, excluded).`);
          return null;
        }
        const clause = { kind: "is", negated, value: isVal };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      if (canonical === "type") {
        const mapped = TYPE_ALIASES[fold(valPart)] || fold(valPart);
        const clause = { kind: "type", negated, value: mapped, rawValue: fold(valPart) };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      if (canonical === "subtype") {
        const mapped = SUBTYPE_ALIASES[fold(valPart)] || fold(valPart);
        const clause = { kind: "subtype", negated, value: mapped, rawValue: fold(valPart) };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      if (canonical === "supertype") {
        const rawSub = fold(valPart);
        const mapped = SUPERTYPE_ALIASES[rawSub] || rawSub;
        const clause = { kind: "supertype", negated, value: mapped, rawValue: rawSub };
        clauses.push(clause);
        return { type: "clause", clause };
      }

      const clause = { kind: canonical, negated, value: fold(valPart) };
      clauses.push(clause);
      return { type: "clause", clause };
    }

    // Negated freetext word: -island
    if (t.startsWith("-")) {
      const inner = stripQuotes(t.slice(1)).trim();
      if (!inner) {
        errors.push("Fehlender Suchbegriff nach „-“.");
        return null;
      }
      const clause = { kind: "phrase", negated: true, value: fold(inner) };
      clauses.push(clause);
      return { type: "clause", clause };
    }

    // Plain freetext word
    const wordRaw = stripQuotes(t);
    positiveWords.push(wordRaw);
    return { type: "word", value: fold(wordRaw), rawValue: wordRaw };
  }

  function parseQuery(rawQuery) {
    const raw = String(rawQuery || "");
    const trimmed = raw.trim();
    if (!trimmed) {
      return { raw: "", isPlainFreetext: true, textQuery: "", clauses: [], ast: null, errors: [] };
    }

    const { tokens, unclosedQuote } = tokenize(trimmed);
    const errors = [];
    const clauses = [];
    const positiveWords = [];
    let hasBooleanSyntax = false;

    if (unclosedQuote) {
      errors.push('Nicht geschlossenes Anführungszeichen (") in der Suchanfrage.');
    }

    let pos = 0;
    const peek = () => tokens[pos] || null;
    const next = () => {
      const tok = tokens[pos] || null;
      pos += 1;
      return tok;
    };

    function parseOr() {
      const first = parseAnd();
      if (!first) return null;
      const branches = [first];
      while (peek() && peek().type === "OR") {
        hasBooleanSyntax = true;
        next();
        if (!peek()) {
          errors.push("Fehlendes Suchkriterium nach „or“.");
          break;
        }
        if (peek().type === "OR") {
          errors.push("Unerwartetes „or“ direkt nach „or“.");
          next();
          continue;
        }
        if (peek().type === "RPAREN") {
          errors.push("Fehlendes Suchkriterium vor „)“ nach „or“.");
          break;
        }
        const right = parseAnd();
        if (right) branches.push(right);
      }
      return branches.length === 1 ? branches[0] : { type: "or", children: branches };
    }

    function parseAnd() {
      const factors = [];
      while (peek() && peek().type !== "OR" && peek().type !== "RPAREN") {
        const item = parsePrimary();
        if (item) factors.push(item);
      }
      if (!factors.length) return null;
      return factors.length === 1 ? factors[0] : { type: "and", children: factors };
    }

    function parsePrimary() {
      const tok = peek();
      if (!tok) return null;
      if (tok.type === "OR") {
        hasBooleanSyntax = true;
        errors.push("Unerwartetes „or“ ohne linken Suchausdruck.");
        next();
        return null;
      }
      if (tok.type === "NOT_LPAREN" || tok.type === "LPAREN") {
        hasBooleanSyntax = true;
        const negatedGroup = tok.type === "NOT_LPAREN";
        next();
        if (peek() && peek().type === "RPAREN") {
          next();
          errors.push(negatedGroup ? "Leere negierte Klammergruppe „-()“ ist nicht erlaubt." : "Leere Klammergruppe „()“ ist nicht erlaubt.");
          return null;
        }
        if (peek() && peek().type === "OR") {
          errors.push("Unerwartetes „or“ direkt nach öffnender Klammer „(“.");
          next();
        }
        const inner = parseOr();
        if (!peek() || peek().type !== "RPAREN") {
          errors.push("Fehlende schließende Klammer „)“ in der Suchanfrage.");
          return inner;
        }
        next();
        if (!inner) return null;
        return negatedGroup ? { type: "not", child: inner } : inner;
      }
      if (tok.type === "RPAREN") {
        hasBooleanSyntax = true;
        errors.push("Unerwartete schließende Klammer „)“ ohne öffnende Klammer.");
        next();
        return null;
      }
      next();
      return parseTermToken(tok, errors, clauses, positiveWords);
    }

    const branches = [];
    while (peek()) {
      if (peek().type === "OR") {
        hasBooleanSyntax = true;
        errors.push("Unerwartetes „or“ ohne linken Suchausdruck.");
        next();
        continue;
      }
      if (peek().type === "RPAREN") {
        hasBooleanSyntax = true;
        errors.push("Unerwartete schließende Klammer „)“ ohne öffnende Klammer.");
        next();
        continue;
      }
      const expr = parseOr();
      if (expr) branches.push(expr);
    }

    const ast = branches.length === 0 ? null : branches.length === 1 ? branches[0] : { type: "and", children: branches };
    const isPlainFreetext = clauses.length === 0 && !hasBooleanSyntax && errors.length === 0;
    return {
      raw: trimmed,
      isPlainFreetext,
      textQuery: positiveWords.join(" ").trim(),
      clauses,
      ast,
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

  function cardKeywordsList(card) {
    if (Array.isArray(card.keywords)) {
      return card.keywords.map((k) => fold(k)).filter(Boolean);
    }
    if (typeof card.keywords === "string") {
      const raw = card.keywords.trim();
      if (!raw) return [];
      if (raw.startsWith("[")) {
        try {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) return parsed.map((k) => fold(k)).filter(Boolean);
        } catch (error) {
          // ignore malformed JSON string and fall back to comma split
        }
      }
      return raw.split(",").map((k) => fold(k.trim())).filter(Boolean);
    }
    return [];
  }

  function cardOtagList(card) {
    const out = [...cardRolesList(card)];
    if (card.layers && card.layers.fact && Array.isArray(card.layers.fact.roles)) {
      for (const r of card.layers.fact.roles) {
        if (r && r.original_tag) out.push(fold(r.original_tag));
      }
    }
    if (Array.isArray(card.oracle_tags)) {
      for (const t of card.oracle_tags) out.push(fold(t));
    }
    if (Array.isArray(card.categories)) {
      for (const c of card.categories) out.push(fold(c));
    }
    return out.filter(Boolean);
  }

  function cardTypeParts(typeLine) {
    const folded = fold(typeLine);
    const faces = folded.split(/\s*\/\/\s*/);
    const supertypes = [];
    const subtypes = [];
    for (const face of faces) {
      const parts = face.split(/\s*[—–]\s*|\s+-\s+/);
      if (parts[0]) {
        for (const word of parts[0].trim().split(/\s+/).filter(Boolean)) {
          if (SUPERTYPES.has(word)) supertypes.push(word);
        }
      }
      for (let i = 1; i < parts.length; i += 1) {
        subtypes.push(...parts[i].trim().split(/\s+/).filter(Boolean));
      }
    }
    return { supertypes, subtypes };
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
      case "subtype": {
        const { subtypes } = cardTypeParts(typeLine);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = subtypes.length === 0;
        } else {
          result = subtypes.some((st) => st === clause.value || st.includes(clause.value)
            || (clause.rawValue && (st === clause.rawValue || st.includes(clause.rawValue))));
        }
        break;
      }
      case "supertype": {
        const { supertypes } = cardTypeParts(typeLine);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = supertypes.length === 0;
        } else {
          result = supertypes.some((sup) => sup === clause.value
            || (clause.rawValue && sup === clause.rawValue));
        }
        break;
      }
      case "keyword": {
        const keywords = cardKeywordsList(card);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = keywords.length === 0;
        } else {
          result = keywords.some((kw) => kw === clause.value || kw.includes(clause.value));
        }
        break;
      }
      case "otag": {
        const otags = cardOtagList(card);
        if (clause.value === "none" || clause.value === "keine" || clause.value === "-") {
          result = otags.length === 0;
        } else {
          const normTarget = clause.value.replace(/[-_]+/g, " ");
          result = otags.some((tag) => tag === clause.value || tag.includes(clause.value)
            || tag.replace(/[-_]+/g, " ").includes(normTarget));
        }
        break;
      }
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

  function evalAstRank(card, node) {
    if (!node) return 0;
    if (node.type === "word") {
      return baseRank(card, node.rawValue);
    }
    if (node.type === "clause") {
      if (!matchClause(card, node.clause)) return null;
      if (node.clause.kind === "phrase" && !node.clause.negated) {
        const r = baseRank(card, node.clause.rawValue || node.clause.value);
        return r !== null ? r : 4;
      }
      return 0;
    }
    if (node.type === "not") {
      return evalAstRank(card, node.child) === null ? 0 : null;
    }
    if (node.type === "or") {
      let best = null;
      for (const child of node.children) {
        const r = evalAstRank(card, child);
        if (r !== null && (best === null || r < best)) best = r;
      }
      return best;
    }
    if (node.type === "and") {
      const wordParts = [];
      let nonWordBest = 0;
      let hasNonWord = false;
      for (const child of node.children) {
        if (child.type === "word") {
          wordParts.push(child.rawValue);
          if (baseRank(card, child.rawValue) === null) return null;
        } else {
          const r = evalAstRank(card, child);
          if (r === null) return null;
          hasNonWord = true;
          if (r > nonWordBest) nonWordBest = r;
        }
      }
      if (wordParts.length > 0) {
        const combinedRank = baseRank(card, wordParts.join(" "));
        const wordRank = combinedRank !== null
          ? combinedRank
          : Math.max(...wordParts.map((w) => baseRank(card, w) ?? 4));
        return hasNonWord ? Math.max(wordRank, nonWordBest) : wordRank;
      }
      return nonWordBest;
    }
    return null;
  }

  function rank(card, queryOrParsed) {
    const parsed = typeof queryOrParsed === "object" && queryOrParsed !== null && Array.isArray(queryOrParsed.clauses)
      ? queryOrParsed
      : parseQuery(queryOrParsed);
    if (parsed.errors && parsed.errors.length > 0) return null;
    if (parsed.isPlainFreetext) {
      return baseRank(card, parsed.textQuery);
    }
    if (parsed.ast) {
      return evalAstRank(card, parsed.ast);
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
    if (parsed.errors && parsed.errors.length > 0) return [];
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
    { op: "subtype:elf", label: "Untertyp Elf" },
    { op: "super:legendary", label: "Legendär" },
    { op: "kw:flying", label: "Schlüsselwort Fliegend" },
    { op: "otag:ramp", label: "Kategorie / Rolle Ramp" },
    { op: "mv<=2", label: "Manawert ≤ 2" },
    { op: "r:ramp", label: "Rolle Ramp" },
    { op: "c:gu", label: "Farbe GU" },
    { op: "id<=gwu", label: "Identität Bant" },
    { op: "t:artifact or t:enchantment", label: "ODER-Verknüpfung" },
    { op: "-(t:land or mv>=4)", label: "Gruppen-Negation" },
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

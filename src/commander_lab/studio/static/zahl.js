"use strict";
// The number contract (B3, #1659): one component for every figure a builder route sends as
// {id, bezeichnung, wert, einheit, n, N, bezug, intervall, klasse, kohorte, quelle, stand_datum,
//  stand_hash, basis_hash, pilot, piloten, data_class, hinweise}. Twin of number_contract.py; same
// rules and the same messages:
//   EXAKT      computed from the list (hypergeometry, castability, list counts)
//   GEZÄHLT    counted in a cohort: always N and a cohort
//   SIMULIERT  SIMULATED_RESULT: always N, the deck state (stand_hash, null = unknown) and the
//              pilot origin (card outcomes: the pilot fingerprint of the stratum, #1687;
//              elsewhere still the constant "Konstante")
//   URTEIL     a model judgement; never in the same column as GEZÄHLT
// VORSCHLAG is no number class and is refused. A missing wert is "unbekannt", never 0; n without
// N is refused; every N names what n and N count (bezug: "Paare (abgeschlossen / geplant)"); a share
// lies in 0..1; a figure that breaks a rule is never shown as a number. Origin (Quelle, Kohorte,
// SIMULATED_RESULT, Stand, Pilot) and the source's notes are visible text, not only a tooltip. DOM only through h(),
// numbers only through StudioUI (read at call time, so the node tests use the real ui.js helpers).
// Compact cells (WP-6, opt-in through zelle(..., { kompakt: true })): for a long table column whose figures share
// one origin, the caller shows that origin ONCE as visible text above the column; each cell keeps the value, the
// class badge and the caller's visible extras, and carries its own full origin and notes in the tooltip. Without
// the option every cell is unchanged.
const StudioZahl = (() => {
  const KLASSEN = ["EXAKT", "GEZÄHLT", "SIMULIERT", "URTEIL"];
  const EINHEITEN = ["Anteil", "pp", "Anzahl", "Punkte"]; // Punkte: the score of a judgement (Q1-b5), no count
  const KEYS = ["id", "bezeichnung", "wert", "einheit", "n", "N", "bezug", "intervall", "klasse", "kohorte", "quelle",
    "stand_datum", "stand_hash", "basis_hash", "pilot", "piloten", "data_class", "hinweise"];
  const LABEL = { EXAKT: "exakt", "GEZÄHLT": "gezählt", SIMULIERT: "simuliert", URTEIL: "Modellurteil" };
  const CSS = { EXAKT: "zahl-exakt", "GEZÄHLT": "zahl-gezaehlt", SIMULIERT: "zahl-simuliert", URTEIL: "zahl-urteil" };
  const UNKNOWN = "unbekannt";

  const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const isCount = (value) => Number.isInteger(value) && value >= 0;
  const isText = (value) => typeof value === "string" && value.trim() !== "";
  const has = (zahl, key) => Object.prototype.hasOwnProperty.call(zahl, key);
  const ui = () => (typeof StudioUI !== "undefined" ? StudioUI : null);

  // Every rule the object breaks (empty array = a valid contract).
  function pruefe(zahl) {
    if (!zahl || typeof zahl !== "object" || Array.isArray(zahl)) return ["keine Zahl-Struktur"];
    const errors = [];
    const foreign = Object.keys(zahl).filter((key) => !KEYS.includes(key)).sort();
    if (foreign.length) errors.push(`unbekannte Felder: ${foreign.join(", ")}`);
    const klasse = zahl.klasse;
    if (klasse === "VORSCHLAG") errors.push("VORSCHLAG ist keine Zahl-Klasse");
    else if (!KLASSEN.includes(klasse)) errors.push("Zahl ohne gültige Klasse");
    if (!isText(zahl.id)) errors.push("id fehlt");
    if (!isText(zahl.bezeichnung)) errors.push("bezeichnung fehlt");
    if (!EINHEITEN.includes(zahl.einheit)) errors.push("einheit fehlt oder unbekannt");
    if (!isText(zahl.quelle)) errors.push("quelle fehlt");
    const wert = zahl.wert === undefined ? null : zahl.wert;
    if (wert !== null && !isNumber(wert)) errors.push("wert ist keine endliche Zahl");
    const n = zahl.n === undefined ? null : zahl.n;
    const total = zahl.N === undefined ? null : zahl.N;
    if (n !== null && !isCount(n)) errors.push("n ist keine Anzahl");
    if (total !== null && !isCount(total)) errors.push("N ist keine Anzahl");
    if (n !== null && total === null) errors.push("n ohne N");
    if (Number.isInteger(n) && Number.isInteger(total) && n > total) errors.push("n größer als N");
    if (total !== null && !isText(zahl.bezug)) errors.push("N ohne Bezug");
    const ci = zahl.intervall === undefined ? null : zahl.intervall;
    const ciOk = Array.isArray(ci) && ci.length === 2 && ci.every(isNumber) && ci[0] <= ci[1];
    if (ci !== null && !ciOk) errors.push("intervall ist kein [unten, oben]");
    if (zahl.einheit === "Anteil") {
      const values = [...(isNumber(wert) ? [wert] : []), ...(ciOk ? ci : [])];
      if (values.some((value) => value < 0 || value > 1)) errors.push("Anteil außerhalb 0..1");
    }
    for (const key of ["kohorte", "bezug", "stand_datum", "stand_hash", "basis_hash", "pilot"]) {
      if (zahl[key] !== undefined && zahl[key] !== null && !isText(zahl[key])) errors.push(`${key} ist kein Text`);
    }
    for (const key of ["piloten", "hinweise"]) {
      if (zahl[key] !== undefined && zahl[key] !== null && !(Array.isArray(zahl[key]) && zahl[key].every(isText))) errors.push(`${key} ist keine Textliste`);
    }
    if (klasse === "GEZÄHLT" || klasse === "SIMULIERT") {
      if (total === null) errors.push(`${klasse} ohne N`);
      if (wert !== null && n === null) errors.push(`${klasse} ohne n`);
    }
    if (klasse === "GEZÄHLT" && !isText(zahl.kohorte)) errors.push("GEZÄHLT ohne Kohorte");
    if (klasse === "SIMULIERT") {
      if (zahl.data_class !== "SIMULATED_RESULT") errors.push("SIMULIERT ohne data_class SIMULATED_RESULT");
      if (!has(zahl, "stand_hash")) errors.push("SIMULIERT ohne Stand-Hash (leer = unbekannt)");
      if (!isText(zahl.pilot)) errors.push("SIMULIERT ohne Pilot-Herkunft");
    } else if (zahl.data_class !== undefined && zahl.data_class !== null) {
      errors.push("data_class nur bei SIMULIERT");
    }
    return errors;
  }

  function wertText(zahl) {
    const helpers = ui();
    const wert = zahl.wert;
    if (!helpers || wert === null || wert === undefined) return UNKNOWN;
    if (zahl.einheit === "Anteil") return helpers.pct(wert, 1);
    if (zahl.einheit === "pp") return `${wert > 0 ? "+" : ""}${helpers.num(wert, 1)} pp`;
    // Punkte (a judgement score) unrounded: the mean of two ratings is a multiple of 2,5 (Owner decision E19)
    if (zahl.einheit === "Punkte") return helpers.numFlex(wert, 1);
    return helpers.num(wert, 0);
  }

  function intervallText(zahl) {
    const helpers = ui();
    const ci = zahl.intervall;
    if (!helpers || !Array.isArray(ci)) return null;
    if (zahl.einheit === "Anteil") return `[${helpers.pct(ci[0], 1)}; ${helpers.pct(ci[1], 1)}]`;
    if (zahl.einheit === "pp") return `[${helpers.num(ci[0], 1)}; ${helpers.num(ci[1], 1)}] pp`;
    return `[${helpers.num(ci[0], 0)}; ${helpers.num(ci[1], 0)}]`;
  }

  function nNText(zahl) {
    const helpers = ui();
    if (!helpers || zahl.N === null || zahl.N === undefined) return null;
    const n = zahl.n === null || zahl.n === undefined ? UNKNOWN : helpers.num(zahl.n, 0);
    return `${n} / ${helpers.num(zahl.N, 0)} ${zahl.bezug}`;
  }

  // Deck state and pilot of a simulated figure: always shown, unknown stays "unbekannt".
  function standText(zahl) {
    if (zahl.klasse !== "SIMULIERT") return null;
    const short = (hash) => (isText(hash) ? hash.slice(0, 12) : UNKNOWN);
    const stand = `Stand ${short(zahl.stand_hash)}${has(zahl, "basis_hash") ? ` gegen ${short(zahl.basis_hash)}` : ""}`;
    const names = Array.isArray(zahl.piloten) && zahl.piloten.length ? ` (${zahl.piloten.join(", ")})` : "";
    return `SIMULATED_RESULT · ${stand} · Pilot: ${zahl.pilot}${names}`;
  }

  function herkunftText(zahl) {
    const parts = [`Quelle: ${zahl.quelle}`];
    if (isText(zahl.kohorte)) parts.push(`Kohorte: ${zahl.kohorte}`);
    if (isText(zahl.stand_datum)) parts.push(`Datenstand: ${zahl.stand_datum}`);
    return parts.join(" · ");
  }
  const hinweisText = (zahl) => (Array.isArray(zahl.hinweise) && zahl.hinweise.length ? `Hinweise: ${zahl.hinweise.join(" · ")}` : null);

  // Pure view model: everything a cell shows, as text. An invalid figure shows no number.
  function modell(zahl) {
    const fehler = pruefe(zahl);
    if (fehler.length) return { ok: false, fehler, wert: "ungültige Zahl", klasse: null, klasseText: null, nN: null, intervall: null, stand: null, herkunft: fehler.join("; "), hinweise: null };
    return {
      ok: true,
      fehler: [],
      wert: wertText(zahl),
      klasse: zahl.klasse,
      klasseText: LABEL[zahl.klasse],
      nN: nNText(zahl),
      intervall: intervallText(zahl),
      stand: standText(zahl),
      herkunft: herkunftText(zahl),
      hinweise: hinweisText(zahl),
    };
  }

  // A column holds one class. Any figure of another class (URTEIL in a GEZÄHLT column) makes
  // the whole column invalid: classes are never mixed in one column.
  function spalte(klasse, zahlen) {
    if (!KLASSEN.includes(klasse)) return { ok: false, fehler: ["Spalte ohne gültige Klasse"] };
    const fehler = [];
    for (const zahl of zahlen) {
      if (zahl === null || zahl === undefined) continue; // an empty cell, no figure
      if (!zahl || zahl.klasse !== klasse) fehler.push(`${zahl && zahl.id ? zahl.id : "?"}: Klasse ${zahl && zahl.klasse ? zahl.klasse : "fehlt"} in Spalte ${klasse}`);
    }
    return { ok: fehler.length === 0, fehler };
  }

  function knoten(h, zahl) {
    const m = modell(zahl);
    if (!m.ok) return h("span", { class: "zahl zahl-ungueltig", title: m.herkunft }, m.wert);
    const title = [m.herkunft, m.stand, m.hinweise].filter(Boolean).join(" · ");
    return h("span", { class: "zahl", title },
      h("span", { class: "zahl-wert" }, m.wert),
      m.intervall ? h("span", { class: "zahl-ci" }, ` ${m.intervall}`) : null,
      " ", h("span", { class: `zahl-klasse ${CSS[m.klasse]}` }, m.klasseText),
      m.nN ? h("span", { class: "zahl-nn" }, `n/N ${m.nN}`) : null,
      h("span", { class: "zahl-herkunft" }, m.herkunft),
      m.stand ? h("span", { class: "zahl-stand" }, m.stand) : null,
      m.hinweise ? h("span", { class: "zahl-hinweise" }, m.hinweise) : null);
  }

  // Compact form of knoten (see the head comment): value, interval, class badge and the caller's extra nodes
  // visible; origin, deck state and notes of this figure in the tooltip. An invalid figure still shows no number.
  function kompakt(h, zahl, zusatz) {
    const m = modell(zahl);
    if (!m.ok) return h("span", { class: "zahl zahl-ungueltig", title: m.herkunft }, m.wert);
    const title = [m.herkunft, m.nN ? `n/N ${m.nN}` : null, m.stand, m.hinweise].filter(Boolean).join(" · ");
    return h("span", { class: "zahl zahl-kompakt", title },
      h("span", { class: "zahl-wert" }, m.wert),
      m.intervall ? h("span", { class: "zahl-ci" }, ` ${m.intervall}`) : null,
      ...(Array.isArray(zusatz) ? zusatz : []),
      " ", h("span", { class: `zahl-klasse ${CSS[m.klasse]}` }, m.klasseText));
  }

  // One table cell of a column of class `klasse`: a figure of another class shows no number.
  // optionen.kompakt: compact cell (the caller shows the shared origin above the column); optionen.zusatz: extra
  // visible nodes after the value (only in the compact cell).
  function zelle(h, zahl, klasse, props, optionen) {
    const check = spalte(klasse, [zahl]);
    const attrs = props || {};
    if (!check.ok) return h("td", attrs, h("span", { class: "zahl zahl-ungueltig", title: check.fehler.join("; ") }, "Klasse passt nicht zur Spalte"));
    if (zahl === null || zahl === undefined) return h("td", attrs, UNKNOWN);
    const compact = Boolean(optionen && optionen.kompakt);
    return h("td", attrs, compact ? kompakt(h, zahl, optionen.zusatz) : knoten(h, zahl));
  }

  // id -> figure for the valid figures of an answer; invalid ones are left out (never shown).
  function index(zahlen) {
    const found = new Map();
    for (const zahl of Array.isArray(zahlen) ? zahlen : []) if (!pruefe(zahl).length) found.set(zahl.id, zahl);
    return found;
  }

  return { KLASSEN, LABEL, pruefe, modell, spalte, knoten, kompakt, zelle, index };
})();
if (typeof module !== "undefined") module.exports = StudioZahl;

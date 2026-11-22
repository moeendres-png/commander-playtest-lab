"use strict";
// "Kartenverständnis (Modellurteil)" in the card window (WP-6, T2; tier list and deck builder): the single ratings of
// one card from GET /api/cards/{id}/understanding. All seven criteria E, F, T, R, K, D, H as number contracts of class
// URTEIL (zahl.js), the rater's note per criterion, reason, rules claims, the audit doubt, the land scale, the spread
// of one rating and the coverage n of N per criterion. H is the mean of the two ratings (Owner decision E19) with both
// raw values and their run; the other six criteria, notes, reason and claims are from the first run. A card the data set does not list shows "unbekannt" for every
// criterion, never 0. For every commander but the data set's the server says anzeigen: false and nothing is shown
// (no TAM, no other commander). A model judgement from the rules text: no strength in play, no tier, no rank.
const StudioKartenverstaendnis = (() => {
  const NAME = "Kartenverständnis (Modellurteil)";
  const UNKNOWN = "unbekannt";
  const CONFIDENCE = { high: "hoch", medium: "mittel", low: "niedrig" };
  // fallback wording when an older answer carries no heading or note of its own
  const CLAIMS_HEADING = "Regelclaims des Raters (Modellurteil, keine Regelaussage; Regelautorität XMage/CR)";
  const CLAIMS_NOTE = "Zitate nicht einzeln geprüft";
  const num = (value) => (typeof StudioUI !== "undefined" ? StudioUI.num(value, 0) : String(value));
  // a score unrounded (the mean of two ratings is a multiple of 2,5): 42,5 and 40
  const score = (value) => (typeof StudioUI !== "undefined" ? StudioUI.numFlex(value, 1) : String(value));
  const RUN_SHORT = { mittel: "Mittel aus 2 Bewertungen", nur_erstbewertung: "1 Bewertung, nur erste", nur_lauf_1: "nur Lauf 1" };
  const DEVIATION_LABEL = "Bewertungen weichen stark ab";

  // The shown H and how it comes about (Owner decision E19): the number of ratings, both raw values with their run and
  // n/N per run, the deviation mark at |ΔH| >= 15, and that only H is averaged. "unbekannt" never reads as 0.
  function ratingNodes(h, ratings) {
    if (!ratings) return [h("p", { class: "understanding-ratings unknown" }, "Zahl der Bewertungen von H: unbekannt.")];
    const card = ratings.karte;
    const runs = Array.isArray(ratings.laeufe) ? ratings.laeufe : [];
    const nN = (run) => `n/N ${run && Number.isInteger(run.n) ? num(run.n) : UNKNOWN} / ${run && Number.isInteger(run.N) ? num(run.N) : UNKNOWN}`;
    const out = [];
    if (card) {
      out.push(h("p", { class: "understanding-ratings" }, h("b", {}, `H angezeigt: ${score(card.wert)}`), ` · ${RUN_SHORT[card.art] || card.kurz}`, card.grund ? ` (${card.grund})` : ""));
      const second = card.h_r2 === null || card.h_r2 === undefined ? (card.art === "nur_lauf_1" ? `${UNKNOWN} (nicht gelesen)` : `fehlt (${card.grund || "keine gültige zweite Bewertung"})`) : score(card.h_r2);
      out.push(h("ul", { class: "understanding-runs" },
        h("li", { "data-lauf": "F1" }, `${(runs[0] && runs[0].lauf) || "Lauf 1 (F1)"}: H ${score(card.h_f1)} · ${nN(runs[0])}`),
        h("li", { "data-lauf": "R2" }, `${(runs[1] && runs[1].lauf) || "Lauf 2 (R2)"}: H ${second} · ${nN(runs[1])}${card.quelle_r2 ? ` · Quelle ${card.quelle_r2}` : ""}`)));
      if (card.abweichung === true && typeof card.h_r2 === "number") {
        out.push(h("p", { class: "bewertungen-abweichung-detail" }, h("span", { class: "badge warn bewertungen-abweichung" }, `${DEVIATION_LABEL} (Δ ${score(Math.abs(card.h_r2 - card.h_f1))})`), ` ${card.marke || ""}`));
      }
    }
    if (ratings.verfuegbar !== true) out.push(h("p", { class: "muted" }, `Mittel der zwei Bewertungen nicht verfügbar: ${ratings.grund || "kein Grund geliefert"}; gezeigt wird H aus Lauf 1 (F1).`));
    out.push(h("p", { class: "understanding-note ratings-note" }, [ratings.text, ratings.andere_kriterien, ratings.standardfehler_hinweis].filter(Boolean).join(". ") + (ratings.quelle ? `. Quelle: ${ratings.quelle}.` : ".")));
    return out;
  }

  function coverageText(entry) {
    return entry && Number.isInteger(entry.n) && Number.isInteger(entry.N) ? `${num(entry.n)} / ${num(entry.N)}` : UNKNOWN;
  }

  function spreadNodes(h, spread, gate) {
    if (!spread) return [h("p", { class: "understanding-spread" }, "Streuung: unbekannt.")];
    return [
      h("p", { class: "understanding-spread" }, `Streuung von ${spread.kriterium || "H"}: ${spread.text} (${spread.art}).`),
      gate && typeof gate.punkte === "number" ? h("p", { class: "understanding-gate" }, `${gate.text} (${gate.quelle}).`) : null,
      h("ul", { class: "understanding-bands" }, (spread.baender || []).map((b) => h("li", {}, `H ${num(b.ab)} bis ${num(b.bis)}: ${b.text} (${b.quelle})`))),
      h("ul", { class: "understanding-sources" }, (spread.quellen || []).map((q) => h("li", {}, `${q.name}: ${q.kennzahl} · ${q.gemessen === false ? "Schätzung" : "gemessen"} · n/N ${num(q.n)} / ${num(q.N)} ${q.bezug} · ${q.datei}`))),
    ];
  }

  function claimNodes(h, claims, findings) {
    if (!Array.isArray(claims) || !claims.length) return [h("p", { class: "muted" }, "Keine Regelclaims im Datensatz für diese Karte.")];
    const byIndex = new Map((Array.isArray(findings) ? findings : []).map((f) => [f.index, f]));
    return [h("ol", { class: "understanding-claims" }, claims.map((claim, index) => h("li", {},
      byIndex.has(index) ? h("div", { class: "regelclaim-befund-detail" }, h("span", { class: "badge warn regelclaim-befund" }, byIndex.get(index).kurz), ` ${byIndex.get(index).korrektur} (${byIndex.get(index).quelle})`) : null,
      claim.quote ? h("div", {}, h("b", {}, "Zitat laut Rater: "), `„${claim.quote}“`) : null,
      claim.interaction ? h("div", {}, h("b", {}, "Zusammenspiel: "), String(claim.interaction)) : null,
      claim.claim ? h("div", {}, h("b", {}, "Aussage des Raters: "), String(claim.claim)) : null,
      claim.basis ? h("div", { class: "muted" }, h("b", {}, "Grundlage: "), String(claim.basis)) : null)))];
  }

  // The box for one answer; null when nothing may be shown (another commander).
  function box(h, detail) {
    if (!detail || detail.anzeigen === false) return null;
    const out = h("div", { class: "layer understanding-detail" }, h("h3", {}, NAME, " ", h("span", { class: "zahl-klasse zahl-urteil" }, "Modellurteil")));
    out.append(h("p", { class: "understanding-note" }, `${detail.hinweis || "Modellurteil, keine Spielstärke"}.`));
    if (detail.verfuegbar !== true) { out.append(h("p", {}, `${NAME} nicht verfügbar: ${detail.grund || "kein Grund geliefert"}.`)); return out; }
    const origin = detail.herkunft || {};
    const tier = origin.rater_tier ? `, Modell-Rater Stufe ${origin.rater_tier}, ${origin.raters === 1 ? "1 Bewerter" : `${num(origin.raters)} Bewerter`}${detail.bewertungen ? ", Lauf 1 (F1)" : ""}` : "";
    out.append(h("p", { class: "understanding-origin" }, `Quelle: Rubrik ${origin.version || UNKNOWN} (${origin.rubric || UNKNOWN})${tier} · Kohorte: ${detail.kohorte || UNKNOWN}`));
    if (detail.bewertet !== true) out.append(h("p", { class: "understanding-unrated" }, "Diese Karte ist im Datensatz nicht bewertet: alle sieben Kriterien sind unbekannt, nicht 0."));
    else out.append(...ratingNodes(h, detail.bewertungen));
    if (detail.pruefer_zweifel) {
      const d = detail.pruefer_zweifel;
      out.append(h("p", { class: "pruefer-zweifel-detail" }, h("span", { class: d.unter_rauschgate === true ? "badge pruefer-zweifel unter-rauschgate" : "badge warn pruefer-zweifel" }, d.kurz || "Prüfer-Modell-Zweifel"), ` ${d.text}. ${d.grund}`));
    }
    if (detail.pruefer_audit && detail.pruefer_audit.pruefbasis) out.append(h("p", { class: "understanding-note pruefbasis" }, `${detail.pruefer_audit.pruefbasis.text}.`));
    if (Array.isArray(detail.regelclaim_befunde) && detail.regelclaim_befunde.length) out.append(h("p", { class: "regelclaim-befund-head" }, ...detail.regelclaim_befunde.map((f) => h("span", { class: "badge warn regelclaim-befund" }, `${f.kurz} (Claim ${num(f.index + 1)})`))));
    if (!detail.pruefer_zweifel && detail.pruefer_audit && detail.pruefer_audit.verfuegbar === false) {
      out.append(h("p", { class: "muted" }, `Prüfer-Audit nicht verfügbar: ${detail.pruefer_audit.grund || "kein Grund geliefert"}.`));
    }
    if (detail.laender_skala) out.append(h("p", { class: "laender-skala-detail" }, h("span", { class: "badge laender-skala" }, "Länder-Skala"), ` ${detail.laender_skala.text} (${detail.laender_skala.quelle}).`));
    const coverage = detail.abdeckung || {};
    const rows = (detail.kriterien || []).map((entry) => h("tr", { "data-kriterium": entry.kriterium },
      h("th", { scope: "row" }, `${entry.kriterium} ${entry.name}`),
      StudioZahl.zelle(h, entry.zahl || null, "URTEIL", { class: "num" }, { kompakt: true }),
      h("td", { class: entry.notiz ? "" : "unknown" }, entry.notiz || UNKNOWN),
      h("td", { class: "num nowrap", title: (coverage[entry.kriterium] || {}).bezug || "" }, coverageText(coverage[entry.kriterium]))));
    const firstCoverage = Object.values(coverage)[0];
    const coverageBezug = firstCoverage && firstCoverage.bezug ? firstCoverage.bezug : "";
    out.append(h("div", { class: "table-wrap" }, h("table", { class: "understanding-criteria" },
      h("thead", {}, h("tr", {}, h("th", {}, "Kriterium (0 bis 100)"), h("th", {}, "Wert"), h("th", {}, "Notiz des Raters"), h("th", { title: coverageBezug }, "Abdeckung n/N"))),
      h("tbody", {}, rows))));
    if (coverageBezug) out.append(h("p", { class: "understanding-note" }, `Abdeckung n/N: ${coverageBezug}.`));
    out.append(...spreadNodes(h, detail.streuung, detail.rauschgate).filter(Boolean));
    if (detail.vertrauen) out.append(h("p", {}, `Rater-Vertrauen (Selbstauskunft): ${CONFIDENCE[detail.vertrauen] || detail.vertrauen}.`));
    const reasonNotes = (Array.isArray(detail.regelclaim_befunde) ? detail.regelclaim_befunde : []).map((f) => f.begruendung_hinweis).filter(Boolean);
    out.append(h("h4", {}, "Begründung des Raters"),
      ...reasonNotes.map((note) => h("p", { class: "regelclaim-befund-detail begruendung-befund" }, h("span", { class: "badge warn regelclaim-befund" }, "Begründung laut Audit D betroffen"), ` ${note}.`)),
      h("p", { class: detail.begruendung ? "" : "unknown" }, detail.begruendung || UNKNOWN));
    out.append(h("h4", {}, detail.regelclaims_titel || CLAIMS_HEADING),
      h("p", { class: "understanding-note claims-note" }, `${detail.regelclaims_hinweis || CLAIMS_NOTE}.`),
      ...claimNodes(h, detail.regelclaims, detail.regelclaim_befunde));
    return out;
  }

  // Loads the answer into `into`; on another commander `into` stays empty, on an error it says so.
  async function fill(into, h, api, cardId, commander) {
    try {
      const detail = await api(`/api/cards/${encodeURIComponent(cardId)}/understanding?commander=${encodeURIComponent(commander)}`);
      const node = box(h, detail);
      into.replaceChildren(...(node ? [node] : []));
    } catch (error) {
      into.replaceChildren(h("p", { class: "muted" }, `${NAME} nicht ladbar: ${typeof StudioUI !== "undefined" ? StudioUI.germanError(error) : String(error)}`));
    }
  }

  return { box, fill };
})();
if (typeof module !== "undefined") module.exports = StudioKartenverstaendnis;

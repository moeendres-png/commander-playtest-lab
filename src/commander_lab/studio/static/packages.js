"use strict";
// Guided 6-step Build Plan (#1404 op. 5), Synergy/Shell Packages (#1404 op. 7),
// Role Coverage (#1413), and Descriptive Upgrade Path (B-2).
// DOM creation uses only h() and textContent; no innerHTML, no mark bias.

async function renderBuildPlanTab(body, deps) {
  const { h, api, entries, fail, roleName, openCard, add, poolCardById, cohort, cohortName, token, isCurrent } = deps;
  const myToken = token();
  body.append(h("h3", {}, `Bauplan (${cohortName(cohort())})`), h("p", { class: "muted" }, "6-Schritte-Bauplan wird berechnet …"));
  let data;
  try {
    data = await api("/api/build-plan", "POST", {
      commander: deps.commander,
      cards: entries(),
      cohort: cohort(),
    });
  } catch (error) {
    if (!isCurrent(myToken)) return;
    body.replaceChildren(h("p", { class: "muted" }, "Bauplan nicht lesbar: " + fail(error, true)));
    return;
  }
  if (!isCurrent(myToken)) return;
  const nodes = [
    h("h3", {}, `Bauplan · ${cohortName(data.cohort)}`),
    h("p", { class: "note" },
      `Vergleichsgruppe: ${StudioUI.num(data.cohort_decks, 0)} Quelldecks · Pool mit bekannter Tagger-Rolle: ${StudioUI.num(data.pool_tagged, 0)}/${StudioUI.num(data.pool_total, 0)}`,
      data.small_sample ? h("span", { class: "pill low ml-1" }, `Kleine Stichprobe (< ${StudioUI.num(data.small_denominator, 0)} Decks)`) : null),
  ];

  const spanText = (span) => span ? `${StudioUI.num(span.median, 1)} (${StudioUI.num(span.p25, 1)}–${StudioUI.num(span.p75, 1)})` : "unbekannt";
  for (const step of data.steps || []) {
    const statusLabel = step.status === "COMPLETE" ? ["vollständig", "good"]
      : step.status === "IN_SPAN" ? ["in mittlerer Hälfte", "good"]
      : step.status === "OPEN" ? ["offen", "warn"]
      : ["prüfen", "low"];
    const stepBox = h("div", { class: "plan-step card-box" },
      h("div", { class: "actions" }, h("strong", {}, step.title), h("span", { class: `pill ${statusLabel[1]}` }, statusLabel[0])),
      h("p", { class: "note" }, step.description));

    if (step.metrics && step.metrics.length) {
      stepBox.append(h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {},
          h("th", {}, "Kennzahl / Rolle"),
          h("th", { class: "num" }, "Im Deck"),
          h("th", { class: "num" }, "Vergleich (p25–p75)"),
          h("th", { class: "num" }, "Im Pool belegt"))),
        h("tbody", {}, step.metrics.map((m) => h("tr", {},
          h("td", {}, m.role ? roleName(m.role) : m.label),
          h("td", { class: "num" }, m.deck === null || m.deck === undefined ? "unbekannt" : StudioUI.num(m.deck, Number.isInteger(m.deck) ? 0 : 2)),
          h("td", { class: "num" }, m.span ? spanText(m.span) : (m.target !== null && m.target !== undefined ? StudioUI.num(m.target, Number.isInteger(m.target) ? 0 : 2) : "unbekannt")),
          h("td", { class: "num" }, m.pool_total ? `${StudioUI.num(m.pool_tagged, 0)}/${StudioUI.num(m.pool_total, 0)}` : "–")))))));
    }
    const cands = step.free_pool_candidates || [];
    if (cands.length) {
      stepBox.append(h("details", {},
        h("summary", {}, `Freie Pool-Kandidaten (${StudioUI.num(cands.length, 0)} gezeigt)`),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", { class: "num" }, "MW"), h("th", { class: "num" }, "Decks (n/N)"), h("th", { class: "num" }, "frei"), h("th", {}, ""))),
          h("tbody", {}, cands.map((cand) => {
            const pCard = poolCardById(cand.card_id);
            return h("tr", {},
              h("td", { class: pCard ? "name" : "", onclick: () => { if (pCard) openCard(pCard); } }, cand.name),
              h("td", { class: "num" }, cand.mana_value === null ? "–" : StudioUI.numFlex(cand.mana_value, 2)),
              h("td", { class: "num" }, cand.decks !== null && cand.of ? `${StudioUI.num(cand.decks, 0)}/${StudioUI.num(cand.of, 0)} (${StudioUI.num(100 * cand.share, 0)} %)` : "unbekannt"),
              h("td", { class: "num" }, StudioUI.num(cand.available, 0)),
              h("td", {}, pCard ? h("button", { type: "button", class: "small", onclick: () => add(pCard) }, "+") : null));
          }))))));
    }
    nodes.push(stepBox);
  }

  if (data.role_coverage && data.role_coverage.length) {
    nodes.push(h("details", {},
      h("summary", {}, `Rollen-Belegung im Pool (${StudioUI.num(data.pool_tagged, 0)}/${StudioUI.num(data.pool_total, 0)} Karten belegt)`),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Rolle"), h("th", { class: "num" }, "Im Deck"), h("th", { class: "num" }, "Im Pool (n/N)"), h("th", { class: "num" }, "Vergleich (p25–p75)"))),
        h("tbody", {}, data.role_coverage.map((row) => h("tr", {},
          h("td", {}, roleName(row.role)),
          h("td", { class: "num" }, StudioUI.num(row.deck_count, 0)),
          h("td", { class: "num" }, `${StudioUI.num(row.pool_tagged, 0)}/${StudioUI.num(row.pool_total, 0)}`),
          h("td", { class: "num" }, spanText(row.cohort_span)))))))));
  }
  nodes.push(h("p", { class: "note" }, data.meaning));
  body.replaceChildren(...nodes);
}

async function renderPackagesUpgradeTab(body, deps) {
  const { h, api, entries, fail, roleName, openCard, add, remove, poolCardById, cohort, cohortName, token, isCurrent } = deps;
  const myToken = token();
  body.append(h("h3", {}, `Pakete & Upgrade-Pfad (${cohortName(cohort())})`), h("p", { class: "muted" }, "Lädt Synergie-Pakete und Vergleichskandidaten …"));
  let pkgData, upgData;
  try {
    [pkgData, upgData] = await Promise.all([
      api("/api/packages", "POST", { commander: deps.commander, cards: entries(), cohort: cohort() }),
      api("/api/upgrade-path", "POST", { commander: deps.commander, cards: entries(), cohort: cohort() }),
    ]);
  } catch (error) {
    if (!isCurrent(myToken)) return;
    body.replaceChildren(h("p", { class: "muted" }, "Pakete nicht lesbar: " + fail(error, true)));
    return;
  }
  if (!isCurrent(myToken)) return;

  const nodes = [
    h("h3", {}, `Kombo- & Synergie-Pakete (${cohortName(pkgData.cohort)})`),
    h("p", { class: "note" }, pkgData.meaning),
  ];

  const shells = pkgData.shell_packages || [];
  if (shells.length) {
    nodes.push(h("h4", {}, `Berührte Spellbook-Shells (${StudioUI.num(shells.length, 0)})`),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Shell"), h("th", {}, "Im Deck"), h("th", {}, "Fehlend / frei im Pool"), h("th", {}, "Ergebnis"))),
        h("tbody", {}, shells.map((sh) => {
          const missNodes = (sh.missing_from_deck || []).map((name) => {
            const info = (sh.available_missing || {})[name];
            const pCard = info && info.card_id ? poolCardById(info.card_id) : null;
            return h("span", { class: "inline-item mr-2" },
              name,
              pCard && info.available > 0 ? h("button", { type: "button", class: "small ml-1", onclick: () => add(pCard) }, "+") : null);
          });
          return h("tr", {},
            h("td", {}, `#${sh.shell_id}`),
            h("td", {}, (sh.in_deck || []).join(", ")),
            h("td", {}, sh.complete_in_deck ? h("span", { class: "pill good" }, "vollständig") : missNodes),
            h("td", {}, (sh.produces || []).slice(0, 3).join("; ") || "–"));
        })))));
  }

  const syn = pkgData.synergy_packages || [];
  if (syn.length) {
    nodes.push(h("h4", {}, `Korpus-Synergie-Pakete (${StudioUI.num(syn.length, 0)} Anker im Deck, Lift ≥ 1,5)`));
    for (const pkg of syn) {
      const anc = pkg.anchor;
      const ancCard = poolCardById(anc.card_id);
      const pBox = h("div", { class: "card-box" },
        h("p", {},
          h("strong", { class: ancCard ? "name" : "", onclick: () => { if (ancCard) openCard(ancCard); } }, anc.name),
          ` · ${StudioUI.num(anc.decks, 0)}/${StudioUI.num(anc.of, 0)} Decks`,
          anc.small_sample ? h("span", { class: "pill low ml-1" }, `< ${StudioUI.num(pkgData.small_denominator, 0)} Decks`) : null));
      if (pkg.in_deck_partners && pkg.in_deck_partners.length) {
        pBox.append(h("p", { class: "note" }, "Bereits im Deck gekoppelt: " + pkg.in_deck_partners.map((p) => `${p.name} (Lift ${StudioUI.num(p.lift, 3)})`).join(" · ")));
      }
      if (pkg.free_pool_partners && pkg.free_pool_partners.length) {
        pBox.append(h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Freie Pool-Partner"), h("th", { class: "num" }, "gemeinsam (n/N)"), h("th", { class: "num" }, "Lift"), h("th", {}, "Kombo"), h("th", {}, ""))),
          h("tbody", {}, pkg.free_pool_partners.map((partner) => {
            const pCard = poolCardById(partner.card_id);
            return h("tr", {},
              h("td", { class: pCard ? "name" : "", onclick: () => { if (pCard) openCard(pCard); } }, partner.name),
              h("td", { class: "num" }, `${StudioUI.num(partner.both_hits, 0)}/${StudioUI.num(partner.anchor_decks, 0)}`),
              h("td", { class: "num" }, StudioUI.num(partner.lift, 3)),
              h("td", {}, partner.combo_partner ? "ja" : "–"),
              h("td", {}, pCard ? h("button", { type: "button", class: "small", onclick: () => add(pCard) }, "+") : null));
          })))));
      }
      nodes.push(pBox);
    }
  } else {
    nodes.push(h("p", { class: "muted" }, "Keine Synergie-Pakete ab Lift 1,5 für die aktuelle Vergleichsgruppe gefunden."));
  }

  nodes.push(h("h3", {}, `Upgrade-Pfad (beschreibender Rollen-Vergleich · ${cohortName(upgData.cohort)})`),
    h("p", { class: "note" }, upgData.meaning));
  if (upgData.small_sample) {
    nodes.push(h("p", { class: "pill low" }, `Kleine Stichprobe (${StudioUI.num(upgData.cohort_decks, 0)} < ${StudioUI.num(upgData.small_denominator, 0)} Decks)`));
  }
  const swaps = upgData.swap_suggestions || [];
  if (swaps.length) {
    nodes.push(h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {},
        h("th", {}, "Im Deck (niedrigere Quelldeck-Quote)"),
        h("th", { class: "num" }, "Decks (n/N)"),
        h("th", {}, "Freie Pool-Alternative (gleiche Rolle, höhere Quote)"),
        h("th", { class: "num" }, "Alt. (n/N)"),
        h("th", { class: "num" }, "Δ MW"),
        h("th", {}, ""))),
      h("tbody", {}, swaps.map((entry) => {
        const cut = entry.cut;
        const alt = entry.alternatives[0];
        const cutCard = poolCardById(cut.card_id);
        const altCard = poolCardById(alt.card_id);
        const mvDelta = Number(alt.mv_delta);
        const mvDeltaStr = mvDelta > 0 ? `+${StudioUI.numFlex(mvDelta, 2)}` : StudioUI.numFlex(mvDelta, 2);
        return h("tr", {},
          h("td", { class: cutCard ? "name" : "", onclick: () => { if (cutCard) openCard(cutCard); } }, cut.name),
          h("td", { class: "num" }, `${StudioUI.num(cut.decks, 0)}/${StudioUI.num(cut.of, 0)} (${StudioUI.num(100 * cut.share, 0)} %)`),
          h("td", { class: altCard ? "name" : "", onclick: () => { if (altCard) openCard(altCard); } },
            alt.name,
            h("div", { class: "muted" }, `Rollen: ${(alt.shared_roles || []).map(roleName).join(", ")}`)),
          h("td", { class: "num" }, `${StudioUI.num(alt.decks, 0)}/${StudioUI.num(alt.of, 0)} (${StudioUI.num(100 * alt.share, 0)} %)`),
          h("td", { class: "num" }, mvDeltaStr),
          h("td", {}, cutCard && altCard ? h("button", {
            type: "button", class: "small",
            onclick: () => { remove(cutCard); add(altCard); },
          }, "Tauschen") : null));
      })))));
  } else {
    nodes.push(h("p", { class: "muted" }, "Keine Tauschpaare mit höherer Quelldeck-Quote im freien Pool."));
  }

  const staples = upgData.missing_staples || [];
  if (staples.length) {
    nodes.push(h("h4", {}, `Häufige freie Pool-Karten nicht im Deck (${StudioUI.num(staples.length, 0)})`),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Karte"), h("th", {}, "Rollen"), h("th", { class: "num" }, "Decks (n/N)"), h("th", { class: "num" }, "frei"), h("th", {}, ""))),
        h("tbody", {}, staples.map((st) => {
          const pCard = poolCardById(st.card_id);
          return h("tr", {},
            h("td", { class: pCard ? "name" : "", onclick: () => { if (pCard) openCard(pCard); } }, st.name),
            h("td", {}, (st.roles || []).map(roleName).join(", ") || "–"),
            h("td", { class: "num" }, `${StudioUI.num(st.decks, 0)}/${StudioUI.num(st.of, 0)} (${StudioUI.num(100 * st.share, 0)} %)`),
            h("td", { class: "num" }, StudioUI.num(st.available, 0)),
            h("td", {}, pCard ? h("button", { type: "button", class: "small", onclick: () => add(pCard) }, "+") : null));
        })))));
  }
  const unknown = upgData.unknown_corpus_cards || [];
  if (unknown.length) {
    nodes.push(h("details", {},
      h("summary", {}, `Karten ohne Korpus-Treffer (${StudioUI.num(unknown.length, 0)} — unbekannt, nie als 0 gewertet)`),
      h("p", { class: "note" }, unknown.map((item) => item.name).join(", "))));
  }
  body.replaceChildren(...nodes);
}

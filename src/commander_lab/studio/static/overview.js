"use strict";
// Single-page deck state overview (#1404 option 9): curve vs cohort, lands & sources vs
// colour pips & castability, role coverage on both sides, bracket check, data gaps,
// data freshness, and simulator readiness — strictly descriptive counts with denominators
// and provenance, zero total score, zero verdict, CSP-safe DOM creation via h().

function _ovPct(value) {
  return value === null || value === undefined ? "unbekannt" : `${StudioUI.num(100 * value, 1)} %`;
}

function _ovSpan(entry, digits = 1) {
  if (!entry || entry.median === undefined || entry.median === null) return "unbekannt";
  return `${StudioUI.num(entry.median, digits)} (${StudioUI.num(entry.p25, digits)}–${StudioUI.num(entry.p75, digits)})`;
}

function _buildOverviewNodes(data, deps, options = {}) {
  const { h, cohortName, roleName, openCard, openModalWide } = deps;
  const {
    shape, reference, deckCards, commanderCards, deckRoles, pool, small, cohort,
    combos, issues, dirty, landData, castData, factsData, layersData, deckTotal, qty, bars,
  } = data;

  const isWide = Boolean(options.wide);
  const deckCounted = reference && reference.decks_counted ? reference.decks_counted : 0;
  const smallCohort = deckCounted > 0 && deckCounted < small;

  const headerCard = h("div", { class: "card-box overview-head" },
    h("h4", {},
      h("span", {}, `Deck-Zustand auf einer Seite · ${cohortName(cohort)}`),
      h("span", { class: "chips" },
        h("span", { class: "pill " + (deckTotal === 100 ? "good" : deckTotal > 100 ? "bad" : "warn") }, `${deckTotal} / 100 Karten`),
        dirty ? h("span", { class: "pill warn" }, "ungespeicherter Entwurf") : h("span", { class: "pill good" }, "Stand gespeichert"),
        smallCohort ? h("span", { class: "pill warn" }, `kleine Gruppe (${deckCounted} < ${small})`) : null,
        !isWide && openModalWide ? h("button", { type: "button", class: "small", onclick: () => openModalWide(data) }, "Großansicht") : null)),
    h("p", { class: "note" }, "Alle Angaben sind gemessene Zählungen und Wahrscheinlichkeiten mit Nenner und Herkunft — keine Gesamtnote, keine Wertung."));

  // A: Grundstruktur & Manakurve vs. Vergleichsgruppe
  const kpiRow = h("div", { class: "kpi-row" },
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Länder"),
      h("div", { class: "kpi-value" }, shape ? shape.lands : 0),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.lands, 1)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Kreaturen"),
      h("div", { class: "kpi-value" }, shape && shape.types ? (shape.types.Creature || 0) : 0),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.creatures, 1)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Ø Manawert (ohne Länder)"),
      h("div", { class: "kpi-value" }, shape && shape.mana_value !== null && shape.mana_value !== undefined ? StudioUI.num(shape.mana_value, 2) : "unbekannt"),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.mana_value, 2)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Quelldecks (Nenner)"),
      h("div", { class: "kpi-value" }, deckCounted),
      h("div", { class: "kpi-sub" }, reference && reference.decks ? `von ${reference.decks} in Gruppe` : "keine Vergleichsdaten")));

  const curveVals = shape && shape.curve ? [0, 1, 2, 3, 4, 5, 6, 7].map((k) => shape.curve[String(k)] || 0) : [0, 0, 0, 0, 0, 0, 0, 0];
  const dp = shape && shape.draw_probabilities && shape.draw_probabilities.opening_7 ? shape.draw_probabilities : null;
  const drawNote = dp
    ? `Starthand (7 Karten, ohne Mulligan): ≥ 2 Länder ${_ovPct(dp.opening_7.at_least_2_lands)} · 3–4 Länder ${_ovPct(dp.opening_7.between_3_and_4_lands)} · Zug 3 ≥ 3 Länder ${_ovPct(dp.turn_3_draw_9 && dp.turn_3_draw_9.at_least_3_lands)}`
    : "Land-Ziehwahrscheinlichkeiten werden erst bei gültigem Maindeck berechnet.";

  const secCurve = h("div", { class: "card-box" },
    h("h4", {}, h("span", {}, "1. Kurve & Grundgerüst"), h("span", { class: "muted" }, "Deck vs. Median (p25–p75)")),
    kpiRow,
    ...bars(curveVals, ["0", "1", "2", "3", "4", "5", "6", "7+"]),
    h("p", { class: "note" }, drawNote));

  // B: Länder + Quellen vs. Farbsymbole & Farbwahrscheinlichkeit auf Kurve
  const manaChildren = [h("h4", {}, h("span", {}, "2. Manabasis & Farben auf Kurve"), h("span", { class: "muted" }, "Länder / Quellen / Karsten 2022"))];
  if (landData && landData.deck) {
    const group = (landData.groups || []).find((g) => g.cohort === cohort);
    const colourRows = (landData.deck.colours || []).map((entry) => {
      const grpCol = group && group.colours ? group.colours[entry.colour] : null;
      const pipCmp = grpCol ? `${entry.pips} (Vgl. ${StudioUI.num(grpCol.pips.median, 1)})` : String(entry.pips);
      const landCmp = grpCol ? `${entry.land_sources} (Vgl. ${StudioUI.num(grpCol.land_sources.median, 1)})` : String(entry.land_sources);
      return h("tr", {},
        h("td", {}, h("span", { class: `ms ms-${entry.colour}` }, entry.colour)),
        h("td", { class: "num" }, pipCmp),
        h("td", { class: "num" }, landCmp),
        h("td", { class: "num" }, String(entry.other_sources) + (entry.modal_sources ? ` (+${entry.modal_sources})` : "")));
    });
    if (colourRows.length) {
      manaChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Symbole"), h("th", { class: "num" }, "Länder"), h("th", { class: "num" }, "Andere"))),
          h("tbody", {}, colourRows))));
    } else {
      manaChildren.push(h("p", { class: "muted" }, "Keine Farbsymbole oder Farbquellen gezählt."));
    }
    if (landData.deck.lands_unknown_colours) {
      manaChildren.push(h("p", { class: "note" }, `${landData.deck.lands_unknown_colours} Länder ohne Farbdaten (unbekannt, nie als 0 gezählt).`));
    }
  } else {
    manaChildren.push(h("p", { class: "muted" }, "Land-Analyse wird geladen oder ist nicht verfügbar …"));
  }

  if (castData && castData.opening_hand) {
    const hand = castData.opening_hand;
    manaChildren.push(h("p", { class: "note" }, `Spielbare Starthand (${hand.rule}): ${_ovPct(hand.p_keepable)} (${hand.lands} Länder, ${hand.early_actions} frühe Aktionen).`));
    const reqs = (castData.requirements || []).slice(0, 8);
    if (reqs.length) {
      manaChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Kosten"), h("th", { class: "num" }, "Quellen"), h("th", { class: "num" }, "Land-Drops"), h("th", { class: "num" }, "Farben*"))),
          h("tbody", {}, reqs.map((item) => h("tr", {},
            h("td", { class: "nowrap" }, item.label, ` Z${item.turn}`),
            h("td", { class: "num" }, Object.entries(item.sources || {}).map(([c, n]) => `${c} ${n}`).join(" · ")),
            h("td", { class: "num" }, _ovPct(item.p_land_drops)),
            h("td", { class: "num" }, _ovPct(item.p_colours_given_lands))))))));
    }
    if (castData.cards_unknown_mana_value || castData.lands_unknown_colours) {
      manaChildren.push(h("p", { class: "note" }, `Unbekannte Eingaben: ${castData.cards_unknown_mana_value || 0} Karten ohne Manawert, ${castData.lands_unknown_colours || 0} Länder ohne Farbdaten.`));
    }
  }
  const secMana = h("div", { class: "card-box" }, ...manaChildren);

  // C: Rollen-Abdeckung auf beiden Seiten (Deck + Vergleich + Pool)
  const ownNonlandCards = deckCards.filter((card) => card.group !== "Land");
  const ownNonlandTotal = ownNonlandCards.reduce((sum, card) => sum + qty(card.card_id), 0);
  const ownWithRole = ownNonlandCards.filter((card) => card.roles && card.roles.length).reduce((sum, card) => sum + qty(card.card_id), 0);
  const poolWithRole = pool.filter((card) => card.roles && card.roles.length).length;
  const poolTotal = pool.length;
  const poolRoleCounts = {};
  for (const card of pool) {
    for (const r of (card.roles || [])) poolRoleCounts[r] = (poolRoleCounts[r] || 0) + 1;
  }
  const refRoles = (reference && reference.roles) || {};
  const coreOrder = ["ramp", "mana_dork", "mana_rock", "land_ramp", "card_draw", "card_advantage", "tutor", "removal", "board_wipe", "counterspell", "protection", "recursion"];
  const allRoleKeys = Array.from(new Set([...coreOrder, ...Object.keys(deckRoles || {}), ...Object.keys(refRoles)])).filter(
    (r) => (deckRoles[r] || 0) > 0 || (refRoles[r] && refRoles[r].median > 0) || coreOrder.includes(r)
  );
  allRoleKeys.sort((a, b) => {
    const da = (refRoles[a] && refRoles[a].median) || 0;
    const db = (refRoles[b] && refRoles[b].median) || 0;
    if (db !== da) return db - da;
    return (deckRoles[b] || 0) - (deckRoles[a] || 0) || roleName(a).localeCompare(roleName(b));
  });
  const topRoles = allRoleKeys.slice(0, 14);
  const roleChildren = [
    h("h4", {}, h("span", {}, "3. Rollen-Abdeckung (beide Seiten)"), h("span", { class: "muted" }, "Deck vs. Gruppe & Pool")),
    h("p", { class: "note" }, `Deck: ${ownWithRole} / ${ownNonlandTotal} Nicht-Land-Karten mit Tagger-Rolle · Gruppe: Median ${reference && reference.role_coverage_median !== undefined && reference.role_coverage_median !== null ? reference.role_coverage_median : "unbekannt"} · Pool: ${poolWithRole} / ${poolTotal} Karten belegt.`),
  ];
  if (topRoles.length) {
    roleChildren.push(h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Rolle"), h("th", { class: "num" }, "Deck"), h("th", { class: "num" }, "Vergleich"), h("th", { class: "num" }, "Pool (n/N)"))),
        h("tbody", {}, topRoles.map((role) => h("tr", {},
          h("td", {}, roleName(role)),
          h("td", { class: "num" }, deckRoles[role] || 0),
          h("td", { class: "num" }, _ovSpan(refRoles[role], 1)),
          h("td", { class: "num" }, `${poolRoleCounts[role] || 0}/${poolTotal}`)))))));
  } else {
    roleChildren.push(h("p", { class: "muted" }, "Keine Rollen-Daten geladen."));
  }
  const secRoles = h("div", { class: "card-box" }, ...roleChildren);

  // D: Bracket-Check & Kombos
  const bracketChildren = [h("h4", {}, h("span", {}, "4. Bracket-Check & Kombos"), h("span", { class: "muted" }, "Fakten, keine Einstufung"))];
  if (factsData && factsData.bracket) {
    const br = factsData.bracket;
    const gc = br.game_changers;
    const tut = br.tutors;
    const two = br.two_card_combos;
    const limitBadges = (gc.limits || []).map((item) => {
      const cls = item.status === "passt" ? "badge good" : item.status === "über der Grenze" ? "badge status-MISSING" : "badge warn";
      return h("span", { class: cls, title: `Bracket ${item.bracket}: ${item.status}` }, `B${item.bracket}: ${item.status}`);
    });
    const twoText = two.count === null ? "unbekannt (keine Liste)" : `${two.count} / ${two.listed}`;
    bracketChildren.push(
      h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Merkmal"), h("th", { class: "num" }, "Anzahl (n/N)"), h("th", {}, "Hinweis / Namen"))),
          h("tbody", {},
            h("tr", {},
              h("td", {}, "Game Changer"),
              h("td", { class: "num" }, `${gc.count} / ${gc.of}` + (gc.unknown ? ` (+${gc.unknown} ?)` : "")),
              h("td", {}, (gc.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Extrazüge"),
              h("td", { class: "num" }, `${br.extra_turns.count} / ${br.extra_turns.of}`),
              h("td", {}, (br.extra_turns.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Massen-Landzerstörung"),
              h("td", { class: "num" }, `${br.mass_land_denial.count} / ${br.mass_land_denial.of}`),
              h("td", {}, (br.mass_land_denial.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Tutoren (Tagger)"),
              h("td", { class: "num" }, `${tut.count} / ${tut.of}`),
              h("td", {}, tut.land_search ? `davon ${tut.land_search} Land-Suche` : "–")),
            h("tr", {},
              h("td", {}, "2-Karten-Kombos"),
              h("td", { class: "num" }, twoText),
              h("td", {}, (two.combos || []).map((c) => (c.cards || []).join(" + ")).join(" · ") || "–"))))),
      h("p", { class: "chips mt-2" }, ...limitBadges));
  } else {
    bracketChildren.push(h("p", { class: "muted" }, "Bracket-Fakten werden geladen …"));
  }
  if (combos && combos.listed) {
    bracketChildren.push(h("p", { class: "note" },
      `Alle Commander-Spellbook-Kombos: ${(combos.complete || []).length} von ${combos.listed} vollständig im Deck · ${(combos.one_missing || []).length} mit genau 1 fehlenden Karte · Pool-Shells: ${(combos.pool_shells || []).length}.`));
  }
  const secBracket = h("div", { class: "card-box" }, ...bracketChildren);

  // E: Datenlücken, Datenfrische & Simulator-Bereitschaft
  const allUnique = [...commanderCards, ...deckCards];
  const simUnknown = allUnique.filter((c) => c.sim_status && c.sim_status !== "OK");
  const simUnknownExplicit = allUnique.filter((c) => !c.sim_status);
  const simReadyCount = allUnique.length - simUnknown.length - simUnknownExplicit.length;

  const gapsChildren = [h("h4", {}, h("span", {}, "5. Datenlücken, Frische & Simulator"), h("span", { class: "muted" }, "unbekannt ≠ 0"))];
  if (factsData && factsData.data_gaps) {
    const dg = factsData.data_gaps;
    const labels = dg.reason_labels || {};
    const nonzeroReasons = Object.entries(dg.by_reason || {}).filter(([, val]) => val && val.count > 0);
    gapsChildren.push(h("p", { class: "note" }, `Datenlücken (ohne Commander): ${dg.cards_with_gaps} von ${dg.cards_checked} Karten mit mindestens einer Lücke.`));
    if (nonzeroReasons.length) {
      gapsChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Fehlende Angabe"), h("th", { class: "num" }, "Karten (n/N)"))),
          h("tbody", {}, nonzeroReasons.map(([key, val]) => h("tr", {}, h("td", {}, labels[key] || key), h("td", { class: "num" }, `${val.count} / ${val.of}`)))))));
    }
  } else {
    gapsChildren.push(h("p", { class: "muted" }, "Datenlücken werden geladen …"));
  }

  const simPillClass = simUnknown.length === 0 && simUnknownExplicit.length === 0 ? "pill good" : "pill warn";
  gapsChildren.push(h("p", { class: "mt-2" },
    h("span", { class: simPillClass }, `Simulator-Bereitschaft: ${simReadyCount} / ${allUnique.length} eindeutige Karten OK`),
    simUnknown.length ? ` · nicht bereit: ${simUnknown.slice(0, 5).map((c) => `${c.name} (${StudioUI.simStatusLabel(c.sim_status)})`).join(", ")}${simUnknown.length > 5 ? " …" : ""}` : null));

  if (issues && issues.length) {
    gapsChildren.push(h("p", { class: "note" }, `Datenprüfung: ${issues.length} Befund(e) — siehe Tab „Prüfung“.`));
  }
  if (layersData && Array.isArray(layersData.layers)) {
    const missingLayers = layersData.layers.filter((l) => l.status === "MISSING");
    const presentCount = layersData.layers.filter((l) => l.status !== "MISSING" && l.status !== "NOT_PROVIDED").length;
    gapsChildren.push(h("p", { class: "note" },
      `Datenebenen im Store: ${presentCount} von ${layersData.layers.length} vorhanden` +
      (missingLayers.length ? ` (fehlend: ${missingLayers.slice(0, 6).map((l) => l.layer || l.key).join(", ")}${missingLayers.length > 6 ? " …" : ""})` : " (keine Pflichtschicht leer).")));
  }
  if (combos && combos.sources && combos.sources.length) {
    const src = combos.sources[0];
    gapsChildren.push(h("p", { class: "note" }, `Kombo-Snapshot: ${src.snapshot_date || (src.imported_at || "").slice(0, 10)} (${src.title}).`));
  }

  // Clickable names hint for cards with gaps if in wide view
  if (isWide && factsData && factsData.data_gaps && factsData.data_gaps.gaps && factsData.data_gaps.gaps.length) {
    const dg = factsData.data_gaps;
    const labels = dg.reason_labels || {};
    gapsChildren.push(h("details", { class: "mt-2" },
      h("summary", {}, `Karten mit Datenlücken (${dg.gaps.length})`),
      h("ul", { class: "note" }, dg.gaps.slice(0, 20).map((item) => h("li", {},
        h("a", { href: "#", class: "nm", onclick: (ev) => { ev.preventDefault(); openCard(item.card_id); } }, item.name),
        ": ", (item.reasons || []).map((k) => labels[k] || k).join(" · "))))));
  }
  const secGaps = h("div", { class: "card-box" }, ...gapsChildren);

  const grid = h("div", { class: isWide ? "overview-grid wide" : "overview-grid" }, secCurve, secMana, secRoles, secBracket, secGaps);
  return [headerCard, grid];
}

async function renderDeckOverview(body, deps) {
  const { h, api, entries, fail, token, isCurrent } = deps;
  const myToken = token();
  const root = h("div", { id: "deck-overview" });
  body.append(root);

  const openModalWide = (snapshotData) => {
    const modalBox = document.getElementById("modal-box");
    const modal = document.getElementById("modal");
    if (!modalBox || !modal) return;
    modalBox.className = "plain wide";
    modalBox.replaceChildren(
      ..._buildOverviewNodes(snapshotData, deps, { wide: true }),
      h("div", { class: "actions" }, h("button", { type: "button", onclick: () => { modal.hidden = true; } }, "Schließen"))
    );
    modal.hidden = false;
  };

  const cacheKey = `${deps.deckId || ""}|${deps.branch || ""}|${deps.changeSeq}|${deps.cohort}`;
  const getCached = (slot) => (slot && slot.key === cacheKey ? slot.data : null);

  let landData = getCached(deps.getLandAdvisor());
  let castData = getCached(deps.getCastability());
  let factsData = getCached(deps.getDeckFacts());
  let layersData = deps.getLayers();

  const buildSnapshot = () => ({
    shape: deps.shape,
    reference: deps.reference,
    deckCards: deps.deckCards(),
    commanderCards: deps.commanderCards(),
    deckRoles: deps.deckRoles,
    pool: deps.pool,
    small: deps.small,
    cohort: deps.cohort,
    combos: deps.combos,
    issues: deps.issues,
    dirty: deps.dirty,
    deckTotal: deps.deckTotal(),
    qty: deps.qty,
    bars: deps.bars,
    landData,
    castData,
    factsData,
    layersData,
  });

  const paint = () => {
    if (!isCurrent(myToken)) return;
    root.replaceChildren(..._buildOverviewNodes(buildSnapshot(), { ...deps, openModalWide }, { wide: false }));
  };

  paint();

  const payload = { cards: entries() };
  const tasks = [];
  if (!landData) {
    tasks.push(
      api("/api/land-advisor", "POST", { cards: payload.cards, owned_only: true, cohort: deps.cohort, min_share: 0.20 })
        .then((res) => { landData = res; deps.setLandAdvisor({ key: cacheKey, seq: deps.changeSeq, cohort: deps.cohort, data: res }); })
        .catch(() => null)
    );
  }
  if (!castData) {
    tasks.push(
      api("/api/castability", "POST", payload)
        .then((res) => { castData = res; deps.setCastability({ key: cacheKey, data: res }); })
        .catch(() => null)
    );
  }
  if (!factsData) {
    tasks.push(
      api("/api/deck-facts", "POST", payload)
        .then((res) => { factsData = res; deps.setDeckFacts({ key: cacheKey, data: res }); })
        .catch((err) => { fail(err); return null; })
    );
  }
  if (!layersData && deps.commander) {
    tasks.push(
      api(`/api/layers?commander=${encodeURIComponent(deps.commander)}`)
        .then((res) => { layersData = res; deps.setLayers(res); })
        .catch(() => null)
    );
  }
  if (tasks.length) {
    await Promise.all(tasks);
    paint();
  }
}

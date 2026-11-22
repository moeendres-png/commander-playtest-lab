"use strict";
// Single-page deck state overview (#1404 option 9): curve vs cohort, lands & sources vs
// colour pips & castability (with the tapped land classes, WP-4), role coverage on both sides, bracket check, data gaps,
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
        h("span", { class: "pill " + (deckTotal === 100 ? "good" : deckTotal > 100 ? "bad" : "warn") }, `${StudioUI.num(deckTotal, 0)} / 100 Karten`),
        dirty ? h("span", { class: "pill warn" }, "ungespeicherter Entwurf") : h("span", { class: "pill good" }, "Stand gespeichert"),
        smallCohort ? h("span", { class: "pill warn" }, `kleine Gruppe (${StudioUI.num(deckCounted, 0)} < ${StudioUI.num(small, 0)})`) : null,
        !isWide && openModalWide ? h("button", { type: "button", class: "small", onclick: () => openModalWide(data) }, "Großansicht") : null)),
    h("p", { class: "note" }, "Alle Angaben sind gemessene Zählungen und Wahrscheinlichkeiten mit Nenner und Herkunft — keine Gesamtnote, keine Wertung."));

  // A: Grundstruktur & Manakurve vs. Vergleichsgruppe
  const kpiRow = h("div", { class: "kpi-row" },
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Länder"),
      h("div", { class: "kpi-value" }, StudioUI.num(shape ? shape.lands : 0, 0)),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.lands, 1)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Kreaturen"),
      h("div", { class: "kpi-value" }, StudioUI.num(shape && shape.types ? (shape.types.Creature || 0) : 0, 0)),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.creatures, 1)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Ø Manawert (ohne Länder)"),
      h("div", { class: "kpi-value" }, shape && shape.mana_value !== null && shape.mana_value !== undefined ? StudioUI.num(shape.mana_value, 2) : "unbekannt"),
      h("div", { class: "kpi-sub" }, `Vergleich: ${_ovSpan(reference && reference.mana_value, 2)}`)),
    h("div", { class: "kpi-card" },
      h("div", { class: "kpi-label" }, "Quelldecks (Nenner)"),
      h("div", { class: "kpi-value" }, StudioUI.num(deckCounted, 0)),
      h("div", { class: "kpi-sub" }, reference && reference.decks ? `von ${StudioUI.num(reference.decks, 0)} in Gruppe` : "keine Vergleichsdaten")));

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
      const pipCmp = grpCol ? `${StudioUI.num(entry.pips, 0)} (Vgl. ${StudioUI.num(grpCol.pips.median, 1)})` : StudioUI.num(entry.pips, 0);
      const viaSearch = entry.search_sources ? ` +${StudioUI.num(entry.search_sources, 0)} Suchland` : "";
      const landCmp = (grpCol ? `${StudioUI.num(entry.land_sources, 0)} (Vgl. ${StudioUI.num(grpCol.land_sources.median, 1)})` : StudioUI.num(entry.land_sources, 0)) + viaSearch;
      return h("tr", {},
        h("td", {}, h("span", { class: `ms ms-${entry.colour}` }, entry.colour)),
        h("td", { class: "num" }, pipCmp),
        h("td", { class: "num" }, landCmp),
        h("td", { class: "num" }, StudioUI.num(entry.other_sources, 0) + (entry.modal_sources ? ` (+${StudioUI.num(entry.modal_sources, 0)})` : "")));
    });
    if (colourRows.length) {
      manaChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Farbe"), h("th", { class: "num" }, "Symbole"), h("th", { class: "num", title: "Länder mit eigener Farbe (Vergleich: gleiche Zählung in der Gruppe); +n: Suchländer, die die Farbe im Deck finden (Rechenannahme, nicht im Vergleich)" }, "Länder"), h("th", { class: "num" }, "Andere"))),
          h("tbody", {}, colourRows))));
      if (landData.deck.lands_search) manaChildren.push(h("p", { class: "note" }, `+n Suchland: ${StudioUI.num(landData.deck.lands_search, 0)} Suchländer, als Quelle jeder Farbe gezählt, die ein passendes Land im Deck erzeugt (Rechenannahme, kein Regelurteil; der Gruppenvergleich zählt nur direkte Quellen).`));
    } else {
      manaChildren.push(h("p", { class: "muted" }, "Keine Farbsymbole oder Farbquellen gezählt."));
    }
    if (landData.deck.lands_unknown_colours) {
      manaChildren.push(h("p", { class: "note" }, `${StudioUI.num(landData.deck.lands_unknown_colours, 0)} Länder ohne Farbdaten (unbekannt, nie als 0 gezählt).`));
    }
  } else {
    manaChildren.push(h("p", { class: "muted" }, "Land-Analyse wird geladen oder ist nicht verfügbar …"));
  }

  if (castData && castData.opening_hand) {
    const hand = castData.opening_hand;
    manaChildren.push(h("p", { class: "note" }, `Spielbare Starthand (${hand.rule}): ${_ovPct(hand.p_keepable)} (${StudioUI.num(hand.lands, 0)} Länder, ${StudioUI.num(hand.early_actions, 0)} frühe Aktionen).`));
    (castData.commander || []).forEach((cmd) => {
      manaChildren.push(h("p", { class: "note overview-commander-curve" }, cmd.known
        ? `Commander ${cmd.name} (${cmd.mana_cost}) auf Kurve Zug ${StudioUI.num(cmd.turn, 0)}: ${_ovPct(cmd.p_on_curve)} direkt (Land-Drops ${_ovPct(cmd.p_land_drops)} × Farben ${_ovPct(cmd.p_colours_given_lands)}), mit Suchland ${_ovPct(cmd.with_search && cmd.with_search.p_on_curve)}; aus der Kommandozone, ohne Commander-Steuer.`
        : `Commander ${cmd.name}: auf Kurve unbekannt (${cmd.reason}).`));
    });
    if (castData.tapped && castData.tapped.of) {
      const tc = castData.tapped.counts || {};
      const of = StudioUI.num(castData.tapped.of, 0);
      manaChildren.push(h("p", { class: "note overview-tapped" }, `Getappte Länder (laut Regeltext): immer ${StudioUI.num(tc.immer_getappt || 0, 0)} von ${of}, bedingt ${StudioUI.num(tc.bedingt_getappt || 0, 0)} von ${of}, Klasse unbekannt ${StudioUI.num(tc.unbekannt || 0, 0)} von ${of}; Zitate und Farbzugriff Zug 1/2 im Tab Zahlen.`));
    }
    const reqs = (castData.requirements || []).slice(0, 8);
    if (reqs.length) {
      manaChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Kosten"), h("th", { class: "num" }, "Quellen"), h("th", { class: "num" }, "Land-Drops"), h("th", { class: "num" }, "Farben direkt*"), h("th", { class: "num", title: "Suchländer als Quelle (Rechenannahme, siehe Tab Zahlen)" }, "mit Suchland*"))),
          h("tbody", {}, reqs.map((item) => h("tr", {},
            h("td", { class: "nowrap" }, item.label, ` Z${item.turn}`),
            h("td", { class: "num" }, Object.entries(item.sources || {}).map(([c, n]) => `${c} ${StudioUI.num(n, 0)}`).join(" · ")),
            h("td", { class: "num" }, _ovPct(item.p_land_drops)),
            h("td", { class: "num" }, _ovPct(item.p_colours_given_lands)),
            h("td", { class: "num" }, _ovPct(item.with_search && item.with_search.p_colours_given_lands))))))));
    }
    if (castData.cards_unknown_mana_value || castData.lands_unknown_colours) {
      manaChildren.push(h("p", { class: "note" }, `Unbekannte Eingaben: ${StudioUI.num(castData.cards_unknown_mana_value || 0, 0)} Karten ohne Manawert, ${StudioUI.num(castData.lands_unknown_colours || 0, 0)} Länder ohne Farbdaten.`));
    }
  }
  const secMana = h("div", { class: "card-box" }, ...manaChildren);

  // C: Rollen-Abdeckung auf beiden Seiten (Deck + Vergleich + Pool)
  const ownNonlandCards = deckCards.filter((card) => card.group !== "Land");
  const ownNonlandTotal = ownNonlandCards.reduce((sum, card) => sum + qty(card.card_id), 0);
  const ownWithRole = ownNonlandCards.filter((card) => card.roles && card.roles.length).reduce((sum, card) => sum + qty(card.card_id), 0);
  // The Bauplan counts the collection only; this view counts what the pool shows, so it names it.
  const poolBasis = deps.includeUnowned ? "Pool (Sammlung + fehlende Karten, Schalter an)" : "Pool (Sammlung)";
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
    h("p", { class: "note" }, `Deck: ${StudioUI.num(ownWithRole, 0)} / ${StudioUI.num(ownNonlandTotal, 0)} Nicht-Land-Karten mit Tagger-Rolle · Gruppe: Median ${reference && reference.role_coverage_median !== undefined && reference.role_coverage_median !== null ? StudioUI.numFlex(reference.role_coverage_median, 1) : "unbekannt"} · ${poolBasis}: ${StudioUI.num(poolWithRole, 0)} / ${StudioUI.num(poolTotal, 0)} Karten mit Rolle belegt.`),
  ];
  if (topRoles.length) {
    roleChildren.push(h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Rolle"), h("th", { class: "num" }, "Deck"), h("th", { class: "num" }, "Vergleich"), h("th", { class: "num" }, "Pool (n/N)"))),
        h("tbody", {}, topRoles.map((role) => h("tr", {},
          h("td", {}, roleName(role)),
          h("td", { class: "num" }, StudioUI.num(deckRoles[role] || 0, 0)),
          h("td", { class: "num" }, _ovSpan(refRoles[role], 1)),
          h("td", { class: "num" }, `${StudioUI.num(poolRoleCounts[role] || 0, 0)}/${StudioUI.num(poolTotal, 0)}`)))))));
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
    const twoText = two.count === null ? "unbekannt (keine Liste)" : `${StudioUI.num(two.count, 0)} / ${StudioUI.num(two.listed, 0)}`;
    bracketChildren.push(
      h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Merkmal"), h("th", { class: "num" }, "Anzahl (n/N)"), h("th", {}, "Hinweis / Namen"))),
          h("tbody", {},
            h("tr", {},
              h("td", {}, "Game Changer"),
              h("td", { class: "num" }, `${StudioUI.num(gc.count, 0)} / ${StudioUI.num(gc.of, 0)}` + (gc.unknown ? ` (+${StudioUI.num(gc.unknown, 0)} ?)` : "")),
              h("td", {}, (gc.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Extrazüge"),
              h("td", { class: "num" }, `${StudioUI.num(br.extra_turns.count, 0)} / ${StudioUI.num(br.extra_turns.of, 0)}`),
              h("td", {}, (br.extra_turns.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Massen-Landzerstörung"),
              h("td", { class: "num" }, `${StudioUI.num(br.mass_land_denial.count, 0)} / ${StudioUI.num(br.mass_land_denial.of, 0)}`),
              h("td", {}, (br.mass_land_denial.cards || []).map((c) => c.name).join(", ") || "–")),
            h("tr", {},
              h("td", {}, "Tutoren (Tagger)"),
              h("td", { class: "num" }, `${StudioUI.num(tut.count, 0)} / ${StudioUI.num(tut.of, 0)}`),
              h("td", {}, tut.land_search ? `davon ${StudioUI.num(tut.land_search, 0)} Land-Suche` : "–")),
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
      `Alle Commander-Spellbook-Kombos: ${StudioUI.num((combos.complete || []).length, 0)} von ${StudioUI.num(combos.listed, 0)} vollständig im Deck · ${StudioUI.num((combos.one_missing || []).length, 0)} mit genau 1 fehlenden Karte · Pool-Shells: ${StudioUI.num((combos.pool_shells || []).length, 0)}.`));
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
    gapsChildren.push(h("p", { class: "note" }, `Datenlücken (ohne Commander): ${StudioUI.num(dg.cards_with_gaps, 0)} von ${StudioUI.num(dg.cards_checked, 0)} Karten mit mindestens einer Lücke.`));
    if (nonzeroReasons.length) {
      gapsChildren.push(h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Fehlende Angabe"), h("th", { class: "num" }, "Karten (n/N)"))),
          h("tbody", {}, nonzeroReasons.map(([key, val]) => h("tr", {}, h("td", {}, labels[key] || key), h("td", { class: "num" }, `${StudioUI.num(val.count, 0)} / ${StudioUI.num(val.of, 0)}`)))))));
    }
  } else {
    gapsChildren.push(h("p", { class: "muted" }, "Datenlücken werden geladen …"));
  }

  const simPillClass = simUnknown.length === 0 && simUnknownExplicit.length === 0 ? "pill good" : "pill warn";
  gapsChildren.push(h("p", { class: "mt-2" },
    h("span", { class: simPillClass }, `Simulator-Bereitschaft: ${StudioUI.num(simReadyCount, 0)} / ${StudioUI.num(allUnique.length, 0)} eindeutige Karten OK`),
    simUnknown.length ? ` · nicht bereit: ${simUnknown.slice(0, 5).map((c) => `${c.name} (${StudioUI.simStatusLabel(c.sim_status)})`).join(", ")}${simUnknown.length > 5 ? " …" : ""}` : null));

  if (issues && issues.length) {
    gapsChildren.push(h("p", { class: "note" }, `Datenprüfung: ${StudioUI.num(issues.length, 0)} Befund(e) — siehe Tab „Prüfung“.`));
  }
  if (layersData && Array.isArray(layersData.layers)) {
    const missingLayers = layersData.layers.filter((l) => l.status === "MISSING");
    const presentCount = layersData.layers.filter((l) => l.status !== "MISSING" && l.status !== "NOT_PROVIDED").length;
    gapsChildren.push(h("p", { class: "note" },
      `Datenebenen im Store: ${StudioUI.num(presentCount, 0)} von ${StudioUI.num(layersData.layers.length, 0)} vorhanden` +
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
      h("summary", {}, `Karten mit Datenlücken (${StudioUI.num(dg.gaps.length, 0)})`),
      h("ul", { class: "note" }, dg.gaps.slice(0, 20).map((item) => h("li", {},
        h("a", { href: "#", class: "nm", onclick: (ev) => { ev.preventDefault(); openCard(item.card_id); } }, item.name),
        ": ", (item.reasons || []).map((k) => labels[k] || k).join(" · "))))));
  }
  const secGaps = h("div", { class: "card-box" }, ...gapsChildren);

  // F: Lücken-Ausgleich (unter p25 / über p75) aus freiem Pool
  const doctorData = data.doctorData;
  const docChildren = [h("h4", {}, h("span", {}, "6. Lücken-Ausgleich (p25–p75)"), h("span", { class: "muted" }, "Freier Pool · n/N"))];
  if (!doctorData) {
    docChildren.push(h("p", { class: "muted" }, "Abweichungen werden geprüft …"));
  } else if (!doctorData.remedies || !doctorData.remedies.length) {
    docChildren.push(h("p", { class: "note" }, "Keine geprüfte Kennzahl liegt unter p25 oder über p75 der Vergleichsgruppe."));
  } else {
    docChildren.push(h("p", { class: "note" }, doctorData.meaning));
    for (const rem of doctorData.remedies) {
      const remTitle = rem.role ? `Rolle ${roleName(rem.role)} unterhalb p25` : rem.label;
      const valDigits = rem.kind === "mana_value_above_p75" ? 2 : 0;
      const spanDigits = rem.kind === "mana_value_above_p75" ? 2 : 1;
      const cands = rem.candidates || [];
      docChildren.push(
        h("div", { class: "mt-2" },
          h("strong", {}, remTitle),
          h("span", { class: "muted ml-1" }, `Deck: ${StudioUI.num(rem.deck_value, valDigits)} · Vergleich: ${_ovSpan(rem.span, spanDigits)}`),
          cands.length
            ? h("div", { class: "table-wrap" },
              h("table", {},
                h("thead", {}, h("tr", {}, h("th", {}, "Freie Pool-Karte"), h("th", { class: "num" }, "MW"), h("th", { class: "num" }, "Quelldecks (n/N)"), h("th", {}, ""))),
                h("tbody", {}, cands.map((cand) => {
                  const pCard = deps.poolCardById ? deps.poolCardById(cand.card_id) : null;
                  return h("tr", {},
                    h("td", { class: pCard ? "name" : "", onclick: () => openCard(cand.card_id) }, cand.name),
                    h("td", { class: "num" }, cand.mana_value === null || cand.mana_value === undefined ? "–" : StudioUI.numFlex(cand.mana_value, 2)),
                    h("td", { class: "num" }, cand.decks !== null && cand.of ? `${StudioUI.num(cand.decks, 0)}/${StudioUI.num(cand.of, 0)}` : "unbekannt"),
                    h("td", {}, pCard && deps.add ? h("button", { type: "button", class: "small", onclick: () => deps.add(pCard) }, "+") : null));
                }))))
            : h("p", { class: "muted" }, "Keine passende freie Karte im Pool."))
      );
    }
  }
  const secDoctor = h("div", { class: "card-box" }, ...docChildren);

  const grid = h("div", { class: isWide ? "overview-grid wide" : "overview-grid" }, secCurve, secMana, secRoles, secBracket, secGaps, secDoctor);
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
  let doctorData = deps.getDeckDoctor ? getCached(deps.getDeckDoctor()) : null;
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
    doctorData,
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
  if (!doctorData) {
    tasks.push(
      api("/api/deck-doctor", "POST", { commander: deps.commander, cards: payload.cards, cohort: deps.cohort, limit: 5 })
        .then((res) => { doctorData = res; if (deps.setDeckDoctor) deps.setDeckDoctor({ key: cacheKey, data: res }); })
        .catch(() => null)
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

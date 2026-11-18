"use strict";
// Paired overnight A-vs-B comparison series (#1404 op. 6) and C-3 simulator readiness audit.
// DOM creation uses only h() and textContent; zero innerHTML, zero eval, zero inline styles.

// Measured for batch series only (#1251: 6 workers, 8 games per JVM). A paired series plays one
// game after the other in a fresh JVM each: its throughput is unmeasured (paired_series.py).
const PAIRED_ESTIMATED_GAMES_PER_HOUR = 540.0;
// Planning constants of the engine lane (full_game_comparison.py: DIFFERENCE_Z95,
// DIFFERENCE_Z80, PLANNED_PAIR_SD) and the assumed seat-rotation block correlation of
// power_table; mirrored in paired_series.planned_detectable_difference_pp.
const PLAN_Z95 = 1.96;
const PLAN_Z80 = 0.8416;
const PLAN_PAIR_SD = 0.63;
const PLAN_BLOCK_CORRELATION = 0.25;
const PLAN_REFERENCE_EFFECT_PP = 5;

function estimatePairedText(budgetPairs) {
  const pairs = Math.max(0, Number(budgetPairs) || 0);
  const maxGames = pairs * 2;
  const seconds = Math.round(maxGames * (3600.0 / PAIRED_ESTIMATED_GAMES_PER_HOUR));
  const minutes = StudioUI.num(seconds / 60.0, 1);
  return `Dauer: mindestens ~${minutes} min für bis zu ${StudioUI.num(maxGames, 0)} Partien, gerechnet mit ${StudioUI.num(PAIRED_ESTIMATED_GAMES_PER_HOUR, 0)} Partien/h. Dieser Durchsatz ist nur für Batch-Serien gemessen (6 Worker, 8 Partien je JVM); für gepaarte Serien ist er ungemessen (sie laufen nacheinander, eine frische JVM je Partie) und vermutlich deutlich niedriger. Früher Stopp je nach Look möglich.`;
}

// What a budget can detect before a game is played: (z95 + z80) * sd / sqrt(n), with the seat
// rotations of one seed as design effect 1 + (m - 1) * 0.25 at the upper end. A plan, not a
// measurement: the pairing correlation is unmeasured, so the sd is not lowered for it.
function planPairedLines(budgetPairs, rotateSeats) {
  const pairs = Math.max(1, Number(budgetPairs) || 1);
  const seatsPerSeed = rotateSeats ? 4 : 1;
  const designEffect = 1 + (seatsPerSeed - 1) * PLAN_BLOCK_CORRELATION;
  const low = (PLAN_Z95 + PLAN_Z80) * PLAN_PAIR_SD / Math.sqrt(pairs) * 100;
  const high = low * Math.sqrt(designEffect);
  const needed = Math.ceil(((PLAN_Z95 + PLAN_Z80) * PLAN_PAIR_SD / (PLAN_REFERENCE_EFFECT_PP / 100)) ** 2);
  const neededHigh = Math.ceil(needed * designEffect);
  const range = (a, b, digits) => (a === b ? StudioUI.num(a, digits) : `${StudioUI.num(a, digits)} bis ${StudioUI.num(b, digits)}`);
  return [
    `Nachweisbar mit ${StudioUI.num(pairs, 0)} Paaren: erst Unterschiede ab etwa ${range(Math.round(low * 10) / 10, Math.round(high * 10) / 10, 1)} Prozentpunkten (95 %, Power 80 %). Kleinere Effekte bleiben „kein Unterschied nachweisbar“ – das heißt nie, dass eine Karte egal ist.`,
    `Für ${StudioUI.num(PLAN_REFERENCE_EFFECT_PP, 0)} pp bräuchte es etwa ${range(needed, neededHigh, 0)} Paare. Referenz: ein einzelner Siegrate-Anteil braucht bei 25 % rund 800 Partien für ±3 pp.`,
    `Annahmen: Paar-Streuung 0,63 wie bei unabhängigen Partien mit 25 % Siegrate (gepaart: Korrelation ungemessen)${rotateSeats ? "; Sitzrotation eines Seeds mit Design-Effekt bis 1,75 (Blockkorrelation 0,25 angenommen)" : ""}; Zwischenblicke nicht eingerechnet. Ein Plan, keine Messung.`,
  ];
}

function notDecidedText(res) {
  const n = StudioUI.num(res.pairs_completed ?? 0, 0);
  const mde = res.detectable_difference_pp;
  const mdeText = mde === null || mde === undefined
    ? "die nachweisbare Differenz ist unbekannt"
    : `nachweisbar wären mindestens ${StudioUI.num(mde, 1)} pp (95 %, Power 80 %, aus der gemessenen Paar-Streuung)`;
  return `Kein Unterschied nachweisbar bei n = ${n} Paaren; ${mdeText}. Das heißt nicht, dass die Karte egal ist.`;
}

function fmtShare(val) {
  return val === null || val === undefined ? "unbekannt" : StudioUI.num(Number(val), 2);
}

function pairedVerdictInfo(res) {
  if (!res) return null;
  if (res.status === "DECIDED" && res.answer === "ABOVE") {
    return ["good", "Entschieden: Variante B übertrifft Basis A"];
  }
  if (res.status === "DECIDED" && res.answer === "NOT_ABOVE") {
    return ["bad", "Entschieden: Variante B liegt nicht über Basis A"];
  }
  if (res.status === "NOT_DECIDED") {
    return ["warn", "Budget erschöpft: kein eindeutiger Unterschied"];
  }
  return ["warn", "Keine auswertbaren Paare"];
}

function fmtPp(val) {
  if (val === null || val === undefined) return "–";
  const num = Number(val);
  return `${num >= 0 ? "+" : ""}${StudioUI.num(num, 1)} pp`;
}

function fmtCiPp(ci) {
  if (!Array.isArray(ci) || ci.length !== 2) return "–";
  return `[${fmtPp(ci[0])}; ${fmtPp(ci[1])}]`;
}

function fmtRatePct(rate) {
  if (rate === null || rate === undefined) return "–";
  return `${StudioUI.num(100 * Number(rate), 1)} %`;
}

async function loadPairedOptions(deps) {
  const options = [];
  try {
    const baseResp = await deps.api(`/api/diff-baselines?${deps.commanderQuery}`);
    for (const item of baseResp.baselines || []) {
      options.push({ ref: item.revision_id, label: item.label });
    }
  } catch (error) { /* optional repo baseline */ }
  for (const deck of deps.decks() || []) {
    for (const br of deck.branches || []) {
      options.push({
        ref: br.revision_id,
        label: `${deck.name || deck.deck_id} · ${br.branch} (${StudioUI.num(br.cards, 0)} K.)`,
      });
    }
  }
  const curDeckId = deps.currentDeckId();
  if (curDeckId) {
    try {
      const hist = await deps.api(`/api/decks/${encodeURIComponent(curDeckId)}/history`);
      for (const row of (hist || []).slice(0, 12)) {
        const ts = row.created_at ? row.created_at.slice(0, 16).replace("T", " ") : "";
        options.push({
          ref: row.revision_id,
          label: `Verlauf ${row.branch || "main"} ${ts}${row.note ? " – " + row.note : ""}`,
        });
      }
    } catch (error) { /* optional history */ }
  }
  const seen = new Set();
  return options.filter((opt) => opt.ref && !seen.has(opt.ref) && seen.add(opt.ref));
}

function renderPairedMonitor(h, job, deps) {
  const isRunning = job.status === "running" || job.status === "pending";
  const statusText = isRunning
    ? "Läuft..."
    : job.status === "completed"
      ? "Abgeschlossen"
      : job.status === "cancelled"
        ? "Abgebrochen"
        : `Fehler: ${job.error || "Unbekannt"}`;
  const maxPairs = Math.max(1, Number(job.budget_pairs) || 1);
  const donePairs = Number(job.pairs_attempted) || 0;
  const pct = Math.min(100, Math.round((donePairs / maxPairs) * 100));

  const monitor = h("div", { class: "sim-monitor" },
    h("div", { class: "sim-monitor-head" },
      h("b", {}, `Paar-Serie „${job.pod}“ (${job.series_id}): ${StudioUI.num(donePairs, 0)} / ${StudioUI.num(maxPairs, 0)} Paare (${StudioUI.num(pct, 0)} %)`),
      h("span", { class: "pill " + (isRunning ? "warn" : job.status === "completed" ? "good" : "bad") }, statusText)),
    h("progress", { value: donePairs, max: maxPairs }),
    h("p", { class: "note note-compact" }, `Basis (A): ${job.base_ref} · Variante (B): ${job.variant_ref}`));

  const qualStates = job.bridge_qualification_states || (job.bridge_qualification && job.bridge_qualification.status ? [job.bridge_qualification.status] : []);
  if (qualStates.includes("BRIDGE_AHEAD_OF_QUALIFICATION")) {
    monitor.append(h("div", { class: "mt-2" },
      h("span", {
        class: "pill warn pill-inline",
        title: ["Rohcode: BRIDGE_AHEAD_OF_QUALIFICATION", job.bridge_qualification && job.bridge_qualification.reason].filter(Boolean).join(" · "),
      }, "Bridge: Engine-Stand noch nicht qualifiziert · nicht durch versiegelte Epoche abgedeckt")));
  }

  if (isRunning) {
    const cancelBtn = h("button", {
      type: "button",
      class: "danger mt-2",
      onclick: async () => {
        cancelBtn.disabled = true;
        try {
          const updated = await deps.api(`/api/simulations/paired/${encodeURIComponent(job.series_id)}/cancel`, "POST");
          deps.setActivePaired(updated);
          deps.pollPaired(job.series_id);
        } catch (err) {
          deps.fail(err);
          cancelBtn.disabled = false;
        }
      },
    }, "Nachtlauf abbrechen");
    monitor.append(cancelBtn);
  }

  const res = job.result;
  if (res) {
    const vInfo = pairedVerdictInfo(res);
    const bridgeSha = (res.bridge_jar_sha256s && res.bridge_jar_sha256s[0]) || job.bridge_jar_sha256 || null;
    const epochLabel = res.covered_by_sealed_epoch ? "versiegelt" : ((res.bridge_qualification_states || qualStates).join(", ") || "nicht versiegelt");
    const pVal = res.sign_test_p_value !== null && res.sign_test_p_value !== undefined
      ? StudioUI.num(res.sign_test_p_value, 4)
      : "–";
    const sumBox = h("div", { class: "sim-summary" },
      h("div", { class: "sim-monitor-head" },
        h("h4", { class: "mt-0" }, "Sequentielles Paar-Ergebnis"),
        vInfo ? h("span", { class: `pill ${vInfo[0]}` }, vInfo[1]) : null),
      h("p", { class: "note" }, res.stop_reason || ""),
      res.stop_reason === "BUDGET_EXHAUSTED" ? h("p", { class: "note", id: "paired-not-decided" }, notDecidedText(res)) : null,
      h("div", { class: "sim-grid" },
        h("div", {}, h("span", { class: "muted" }, "Basis-Siegrate (A): "), h("b", {}, fmtRatePct(res.base_rate))),
        h("div", {}, h("span", { class: "muted" }, "Varianten-Siegrate (B): "), h("b", {}, fmtRatePct(res.variant_rate))),
        h("div", {}, h("span", { class: "muted" }, "Differenz (B − A): "), h("b", {}, fmtPp(res.difference_pp))),
        h("div", {}, h("span", { class: "muted" }, "95 %-CI (Cluster): "), h("b", {}, fmtCiPp(res.difference_ci95_pp))),
        h("div", {}, h("span", { class: "muted" }, `Look-CI (${res.decision_level_pct !== null && res.decision_level_pct !== undefined ? StudioUI.numFlex(res.decision_level_pct, 2) : "–"} %): `), h("b", {}, fmtCiPp(res.decision_ci_pp))),
        h("div", {}, h("span", { class: "muted" }, "Sign-Test p / Diskordant: "), h("b", {}, `${pVal} (${StudioUI.num(res.variant_only_wins, 0)}B : ${StudioUI.num(res.baseline_only_wins, 0)}A · ${StudioUI.num(res.tied_pairs, 0)} gleich)`)),
        h("div", {}, h("span", { class: "muted" }, "Paare fertig / zensiert: "), h("b", {}, `${StudioUI.num(res.pairs_completed, 0)} / ${StudioUI.num(res.pairs_censored, 0)}`)),
        h("div", { title: "Paarung spart Partien nur, wenn der gemessene Anteil deutlich unter dem Wert unabhängiger Partien liegt." }, h("span", { class: "muted" }, "Diskordante Paare (gemessen / unabhängig erwartet): "), h("b", {}, `${StudioUI.num((res.variant_only_wins ?? 0) + (res.baseline_only_wins ?? 0), 0)}/${StudioUI.num(res.pairs_completed ?? 0, 0)} = ${fmtShare(res.discordant_share)} / ${fmtShare(res.discordant_share_if_independent)}`)),
        h("div", {}, h("span", { class: "muted" }, "Bibliotheksplätze: "), h("b", {}, job.slot_alignment ? `an Basis ausgerichtet (${StudioUI.num(job.slot_alignment.swapped_slots, 0)} getauscht)` : "nicht ausgerichtet (ältere Serie)")),
        h("div", {}, h("span", { class: "muted" }, "Seeds: "), h("b", {}, job.seed_plan && job.seed_plan.first_seed !== null && job.seed_plan.first_seed !== undefined ? `${job.seed_plan.first_seed} bis ${job.seed_plan.last_seed} (fortlaufend)` : "unbekannt")),
        h("div", {}, h("span", { class: "muted" }, "Bridge-JAR: "), h("code", { title: bridgeSha || "" }, bridgeSha ? String(bridgeSha).slice(0, 12) : "–")),
        h("div", {}, h("span", { class: "muted" }, "Epoche: "), h("b", {}, epochLabel))),
      ...(res.warnings && res.warnings.length
        ? [h("ul", { class: "note" }, res.warnings.map((w) => h("li", {}, w)))]
        : []),
      h("p", { class: "note note-compact" }, "SIMULATED_RESULT: gleiche Seeds, Sitze und Gegner-Tisch. Simulationsergebnisse fließen nie in die Tierliste ein (Gewicht 0)."));
    monitor.append(sumBox);
  }
  return monitor;
}

function renderReadinessAuditBox(h, deps) {
  const box = h("div", { class: "sim-box", id: "readiness-audit-box" },
    h("h3", { class: "mt-0" }, "Simulator-Bereitschafts-Audit (C-3: Deck & freie Tier-S/A-Kandidaten)"),
    h("p", { class: "note" }, "Prüft explizit mit Zähler/Nenner gegen XMage-Card-Facts und Piloten-Wissen. Fehlende Kataloge melden strikt UNKNOWN, niemals ein Schein-PASS."));

  const resultBox = h("div", { id: "readiness-audit-result" });
  const renderAudit = (audit) => {
    if (!audit) {
      resultBox.replaceChildren(h("p", { class: "muted" }, "Noch nicht geprüft."));
      return;
    }
    const badgeInfo = audit.status === "OK"
      ? ["good", "OK · vollständig simulator-bereit"]
      : audit.status === "GAPS_FOUND"
        ? ["bad", "Lücken gefunden"]
        : ["warn", "UNKNOWN · Kartendaten nicht lesbar"];
    const nodes = [
      h("div", { class: "actions" }, h("span", { class: `pill ${badgeInfo[0]}` }, badgeInfo[1])),
    ];
    if (!audit.available) {
      nodes.push(h("p", { class: "note" }, audit.reason || "Kartendaten nicht verfügbar."));
      resultBox.replaceChildren(...nodes);
      return;
    }
    const d = audit.deck || {};
    const f = audit.free_top_candidates || {};
    nodes.push(
      h("div", { class: "sim-grid" },
        h("div", {}, h("span", { class: "muted" }, "Deck-Karten: "), h("b", {}, `${StudioUI.num(d.ready ?? 0, 0)} / ${StudioUI.num(d.total ?? 0, 0)} OK`)),
        h("div", {}, h("span", { class: "muted" }, `Freie Tier-${(f.tiers || ["S", "A"]).join("/")}-Kandidaten: `), h("b", {}, `${StudioUI.num(f.ready ?? 0, 0)} / ${StudioUI.num(f.total ?? 0, 0)} OK`)))
    );

    const allIssues = [
      ...(d.issues || []).map((item) => ({ scope: "Deck", ...item })),
      ...(f.issues || []).map((item) => ({ scope: `Tier ${item.tier}`, ...item })),
    ];
    if (allIssues.length) {
      nodes.push(
        h("h4", { class: "mt-2" }, `Offene Simulator-Lücken (${StudioUI.num(allIssues.length, 0)})`),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Bereich"), h("th", {}, "Karte"), h("th", {}, "XMage"), h("th", {}, "Pilot-Wissen"))),
          h("tbody", {}, allIssues.slice(0, 40).map((item) => {
            const poolCard = item.card_id ? deps.poolCardById(item.card_id) : null;
            return h("tr", {},
              h("td", {}, item.scope),
              h("td", { class: poolCard ? "name" : "", onclick: () => { if (poolCard) deps.openCard(poolCard); } }, item.name),
              h("td", { title: item.sim_status || "" }, StudioUI.simStatusLabel(item.sim_status)),
              h("td", {}, item.pilot_known ? "OK" : "FEHLT"));
          }))))
      );
    } else {
      nodes.push(h("p", { class: "note mt-2" }, "Alle geprüften Deckkarten und freien Tier-S/A-Kandidaten sind im XMage-Regelkern und Piloten-Wissen hinterlegt."));
    }
    resultBox.replaceChildren(...nodes);
  };

  const runBtn = h("button", {
    type: "button",
    id: "readiness-audit-run",
    onclick: async () => {
      runBtn.disabled = true;
      resultBox.replaceChildren(h("p", { class: "muted" }, "Audit läuft …"));
      try {
        const audit = await deps.api("/api/simulations/readiness-audit", "POST", {
          commander: deps.commander,
          cards: deps.entries(),
          tiers: ["S", "A"],
        });
        deps.setReadinessAudit(audit);
        renderAudit(audit);
      } catch (err) {
        resultBox.replaceChildren(h("p", { class: "muted" }, "Audit-Fehler: " + deps.fail(err, true)));
      } finally {
        runBtn.disabled = false;
      }
    },
  }, "Simulator-Bereitschaft jetzt auditieren");

  box.append(h("div", { class: "actions" }, runBtn), resultBox);
  renderAudit(deps.readinessAudit());
  return box;
}

function refreshPairedSlots(deps) {
  const { h } = deps;
  const monSlot = document.getElementById("paired-monitor-slot");
  if (monSlot) {
    const active = deps.activePaired();
    monSlot.replaceChildren(...(active ? [renderPairedMonitor(h, active, deps)] : []));
  }
  const histSlot = document.getElementById("paired-history-slot");
  if (histSlot) {
    const historyList = deps.pairedHistory() || [];
    if (!historyList.length) {
      histSlot.replaceChildren();
    } else {
      histSlot.replaceChildren(
        h("h4", { class: "mt-2" }, "Gespeicherte Nachtlauf-Serien"),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Serie"), h("th", {}, "Status"), h("th", {}, "Ergebnis"), h("th", { class: "num" }, "Differenz"), h("th", {}, ""))),
          h("tbody", {}, historyList.slice(0, 10).map((item) => {
            const r = item.result || null;
            const v = pairedVerdictInfo(r);
            return h("tr", {},
              h("td", {}, h("code", {}, item.series_id)),
              h("td", {}, item.status),
              h("td", {}, v ? v[1] : `${StudioUI.num(item.pairs_attempted ?? 0, 0)}/${item.budget_pairs !== null && item.budget_pairs !== undefined ? StudioUI.num(item.budget_pairs, 0) : "?"} Paare`),
              h("td", { class: "num" }, r ? fmtPp(r.difference_pp) : "–"),
              h("td", {}, h("button", {
                type: "button",
                class: "small",
                onclick: () => {
                  deps.setActivePaired(item);
                  refreshPairedSlots(deps);
                },
              }, "Details")));
          }))))
      );
    }
  }
}

function renderPairedComparisonSection(body, deps) {
  const { h } = deps;
  const pBox = h("div", { class: "sim-box", id: "paired-series-box" },
    h("h3", { class: "mt-0" }, "Nachtlauf-Vergleichsserie (A vs. B · gleiche Seeds & Sitze)"),
    h("p", { class: "note" }, "Vergleicht Basis (A) gegen Variante (B) auf identischen Seeds, Sitzen und Gegner-Tischen. Sequentielle Looks nach O'Brien-Fleming beenden den Lauf automatisch bei eindeutigem Abstand; abgebrochene Spiele zensieren das Paar ohne Verlustwertung.")
  );

  const curRev = deps.currentRevision() || "";
  const baseSelect = h("select", { id: "paired-base-select" }, h("option", { value: "" }, "Stände laden …"));
  const varSelect = h("select", { id: "paired-variant-select" },
    curRev ? h("option", { value: curRev }, curRev) : h("option", { value: "" }, "Stände laden …"));
  const podSelect = h("select", { id: "paired-pod-select" },
    h("option", { value: "precon" }, "Precon (Lorehold, Animated Army, Token Triumph)"),
    h("option", { value: "mixed" }, "Mixed (Kaervek, Animated Army, Lorehold)"),
    h("option", { value: "optimized" }, "Optimized (Eldrazi, Kaervek, Hosts of Mordor)")
  );
  const budgetSelect = h("select", { id: "paired-budget-select" },
    h("option", { value: "20" }, "20 Paare (bis 40 Partien)"),
    h("option", { value: "40", selected: true }, "40 Paare (bis 80 Partien · 10 Seeds)"),
    h("option", { value: "60" }, "60 Paare (bis 120 Partien)"),
    h("option", { value: "100" }, "100 Paare (bis 200 Partien)"),
    h("option", { value: "200" }, "200 Paare (bis 400 Partien)")
  );
  const lookSelect = h("select", { id: "paired-look-select" },
    h("option", { value: "4", selected: true }, "alle 4 Paare"),
    h("option", { value: "5" }, "alle 5 Paare"),
    h("option", { value: "10" }, "alle 10 Paare"),
    h("option", { value: "20" }, "alle 20 Paare")
  );
  const seedInput = h("input", { type: "number", value: "1000", class: "seed-input", id: "paired-seed-input" });
  const thresholdInput = h("input", { type: "number", value: "0", step: "0.5", class: "seed-input", id: "paired-threshold-input" });
  const rotateCheck = h("input", { type: "checkbox", checked: true, id: "paired-rotate-check" });

  const estLine = h("p", { class: "note", id: "paired-estimate" }, estimatePairedText(budgetSelect.value));
  const planBox = h("div", { class: "note", id: "paired-plan" });
  const refreshPlan = () => {
    estLine.textContent = estimatePairedText(budgetSelect.value);
    planBox.replaceChildren(...planPairedLines(budgetSelect.value, rotateCheck.checked).map((line) => h("p", { class: "note note-compact" }, line)));
  };
  budgetSelect.addEventListener("change", refreshPlan);
  rotateCheck.addEventListener("change", refreshPlan);
  refreshPlan();

  const startBtn = h("button", { type: "submit", class: "primary", id: "paired-start-btn" }, "Nachtlauf starten");
  const form = h("form", {
    class: "sim-form",
    onsubmit: async (e) => {
      e.preventDefault();
      if (!baseSelect.value || !varSelect.value) {
        deps.toast("Bitte Basis (A) und Variante (B) wählen.");
        return;
      }
      if (baseSelect.value === varSelect.value) {
        deps.toast("Basis (A) und Variante (B) müssen verschiedene Stände sein.");
        return;
      }
      startBtn.disabled = true;
      try {
        const res = await deps.api("/api/simulations/paired", "POST", {
          base_revision_id: baseSelect.value,
          variant_revision_id: varSelect.value,
          pod: podSelect.value,
          budget_pairs: parseInt(budgetSelect.value, 10),
          look_every_pairs: parseInt(lookSelect.value, 10),
          base_seed: parseInt(seedInput.value, 10),
          rotate_seats: rotateCheck.checked,
          threshold_pp: parseFloat(thresholdInput.value) || 0.0,
        });
        deps.setActivePaired(res);
        refreshPairedSlots(deps);
        deps.pollPaired(res.series_id);
      } catch (err) {
        deps.fail(err);
      } finally {
        startBtn.disabled = false;
      }
    },
  },
    h("label", {}, "Basis (A)", baseSelect),
    h("label", {}, "Variante (B)", varSelect),
    h("label", {}, "Gegnertisch", podSelect),
    h("label", {}, "Budget", budgetSelect),
    h("label", {}, "Sequential-Look", lookSelect),
    h("label", {}, "Schwelle (pp)", thresholdInput),
    h("label", {}, "Basis-Seed", seedInput),
    h("label", { class: "paired-check" }, rotateCheck, "Sitze 1–4 rotieren"),
    startBtn
  );

  const monSlot = h("div", { id: "paired-monitor-slot" });
  const histSlot = h("div", { id: "paired-history-slot" });
  pBox.append(form, estLine, planBox, monSlot, histSlot);

  body.append(pBox, renderReadinessAuditBox(h, deps));
  refreshPairedSlots(deps);

  const tok = deps.token();
  loadPairedOptions(deps).then((opts) => {
    if (!deps.isCurrent(tok) || !opts.length) return;
    const defaultVar = (curRev && opts.some((o) => o.ref === curRev)) ? curRev : opts[0].ref;
    const defaultBase = (opts.find((o) => o.ref.startsWith("repo:")) || opts.find((o) => o.ref !== defaultVar) || opts[0]).ref;
    baseSelect.replaceChildren(...opts.map((o) => h("option", { value: o.ref, selected: o.ref === defaultBase }, o.label)));
    varSelect.replaceChildren(...opts.map((o) => h("option", { value: o.ref, selected: o.ref === defaultVar }, o.label)));
  }).catch(() => {});
}

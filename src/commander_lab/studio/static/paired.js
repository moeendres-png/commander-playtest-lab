"use strict";
// Paired overnight A-vs-B comparison series (#1404 op. 6) and C-3 simulator readiness audit.
// DOM creation uses only h() and textContent; zero innerHTML, zero eval, zero inline styles.

// The one measured rate (#1251): 541 games/hour for a WHOLE batch series with 6 workers. The time
// at that rate is shown as a floor ("mindestens"), never as a maximum; paired series throughput is
// unmeasured. #1513's 540/h per worker is an unmeasured assumption and not used for the duration
// (paired_series.MEASURED_BATCH_GAMES_PER_HOUR, assumed_games_per_hour_unmeasured).
const PAIRED_MEASURED_BATCH_GAMES_PER_HOUR = 541.2;
const PAIRED_MEASURED_BATCH_WORKERS = 6;
// The table size of a series (#1702) is a setting of the dialog. Which sizes may start comes from
// the server (GET /api/simulations/paired-tables, launch.MAX_RELEASED_SEATS): this file holds no
// lock of its own. Before the server answers, or when it cannot, only this size is offered.
const PAIRED_DEFAULT_TABLE_SEATS = 4;
// Budgets of the dialog; at four seats this list is offered unchanged. At other sizes each budget
// is rounded up to whole rotation blocks (N seeds x N seats = N^2 pairs per arm, 25 at five and
// 36 at six seats), so a rotation is never cut off by the dialog.
const PAIRED_BUDGETS = [20, 40, 60, 100, 200];
const PAIRED_DEFAULT_BUDGET = 40;
const PAIRED_POD_TITLES = { precon: "Precon", mixed: "Mixed", optimized: "Optimized" };

function estimatePairedText(budgetPairs, workers = 4, seats = PAIRED_DEFAULT_TABLE_SEATS) {
  const pairs = Math.max(0, Number(budgetPairs) || 0);
  const usedWorkers = Math.max(1, Math.min(16, Math.round(Number(workers) || 1)));
  const tableSeats = Math.round(Number(seats) || PAIRED_DEFAULT_TABLE_SEATS);
  const maxGames = pairs * 2;
  const seconds = Math.round(maxGames * (3600.0 / PAIRED_MEASURED_BATCH_GAMES_PER_HOUR));
  const minutes = StudioUI.num(seconds / 60.0, 1);
  const floorNote = usedWorkers > PAIRED_MEASURED_BATCH_WORKERS ? " Mit mehr als 6 Workern ist das keine sichere Untergrenze." : "";
  if (tableSeats < 4) {
    // smaller tables play shorter games: the four-seat rate is no floor there
    return `Dauer: unbekannt (UNKNOWN) für bis zu ${StudioUI.num(maxGames, 0)} Partien: gemessen sind nur 541 Partien/h für eine ganze Batch-Serie mit 6 Workern an Vierertischen (#1251). Bei ${StudioUI.num(tableSeats, 0)} Sitzen sind Partien kürzer, die Rate ist dort keine Untergrenze. Früher Stopp je nach Look möglich.`;
  }
  if (tableSeats > 4) {
    return `Dauer: mindestens ~${minutes} min für bis zu ${StudioUI.num(maxGames, 0)} Partien, gerechnet mit den 541 Partien/h, die nur für eine ganze Batch-Serie mit 6 Workern an Vierertischen gemessen sind (#1251). Bei ${StudioUI.num(tableSeats, 0)} Sitzen ist der Durchsatz ungemessen (UNKNOWN); Partien mit mehr Sitzen dauern länger (ein Messpunkt: 6 Sitze brauchten das 3,2-Fache der Zeit von 4 Sitzen, n = 1, Qualifikationsplan 5/6), daher bleibt das nur eine Untergrenze.${floorNote} Früher Stopp je nach Look möglich.`;
  }
  return `Dauer: mindestens ~${minutes} min für bis zu ${StudioUI.num(maxGames, 0)} Partien, gerechnet mit den 541 Partien/h, die nur für eine ganze Batch-Serie mit 6 Workern gemessen sind (#1251). Für gepaarte Serien ist der Durchsatz ungemessen; die Dauer ist vermutlich deutlich länger.${floorNote} Früher Stopp je nach Look möglich.`;
}

// Budget choices at a table size: [{value, label, selected}]. Seeds are ceil(pairs / N) with
// rotation (each seed plays every seat), else one per pair.
function pairedBudgetOptions(seats, rotate) {
  const n = Math.max(1, Math.round(Number(seats) || PAIRED_DEFAULT_TABLE_SEATS));
  const block = rotate ? n * n : 1;
  const values = n === 4 || !rotate
    ? PAIRED_BUDGETS.slice()
    : [...new Set(PAIRED_BUDGETS.map((v) => Math.ceil(v / block) * block))];
  const preferred = values.find((v) => v >= PAIRED_DEFAULT_BUDGET) ?? values[values.length - 1];
  return values.map((value) => {
    const seeds = rotate ? Math.ceil(value / n) : value;
    return {
      value,
      label: `${StudioUI.num(value, 0)} Paare (bis ${StudioUI.num(2 * value, 0)} Partien · ${StudioUI.num(seeds, 0)} Seeds)`,
      selected: value === preferred,
    };
  });
}

// What a series of `budget` pairs at N seats covers: whole rotation blocks or an honest note
// that the last block is incomplete.
function pairedBlockText(seats, rotate, budget) {
  const n = Math.max(1, Math.round(Number(seats) || PAIRED_DEFAULT_TABLE_SEATS));
  const pairs = Math.max(0, Math.round(Number(budget) || 0));
  if (!rotate) {
    return `Ohne Rotation sitzt das getestete Deck immer auf Sitz 1 eines Tischs mit ${StudioUI.num(n, 0)} Sitzen; der Sitzvorteil ist nicht ausgeglichen.`;
  }
  const block = n * n;
  const full = Math.floor(pairs / block);
  const head = `Rotationsblock bei ${StudioUI.num(n, 0)} Sitzen: ${StudioUI.num(n, 0)} Seeds × ${StudioUI.num(n, 0)} Sitze = ${StudioUI.num(block, 0)} Paare je Arm (${StudioUI.num(2 * block, 0)} Partien je Block, beide Arme). Startsitz ist Seed mod ${StudioUI.num(n, 0)}.`;
  if (pairs % block === 0) {
    return `${head} ${StudioUI.num(pairs, 0)} Paare sind ${StudioUI.num(full, 0)} ${full === 1 ? "voller Block" : "volle Blöcke"}: jede Kombination aus Startsitz und getestetem Sitz kommt gleich oft vor.`;
  }
  return `${head} ${StudioUI.num(pairs, 0)} Paare sind kein Vielfaches von ${StudioUI.num(block, 0)}: ${StudioUI.num(full, 0)} ${full === 1 ? "voller Block" : "volle Blöcke"}, der letzte Block ist unvollständig (nicht jede Kombination aus Startsitz und getestetem Sitz kommt gleich oft vor).`;
}

// Table sizes for the select: [{value, label, disabled, selected}]. Without server info only the
// default size; sizes above the released maximum are shown greyed out, never startable.
function pairedTableSizeOptions(info, selectedSeats) {
  if (!info || !Array.isArray(info.sizes)) {
    return [{ value: PAIRED_DEFAULT_TABLE_SEATS, label: `${PAIRED_DEFAULT_TABLE_SEATS} Sitze`, disabled: false, selected: true }];
  }
  const want = Number(selectedSeats) || Number(info.default_seats) || PAIRED_DEFAULT_TABLE_SEATS;
  return info.sizes.map((size) => {
    const released = size.released === true;
    return {
      value: size.seats,
      label: released ? `${size.seats} Sitze` : `${size.seats} Sitze (nicht freigegeben)`,
      disabled: !released,
      selected: released && size.seats === want,
    };
  });
}

function pairedTableNote(info) {
  if (!info || !Array.isArray(info.sizes)) {
    return "Tischgrößen nicht geladen: angeboten sind nur 4 Sitze.";
  }
  const locked = info.sizes.filter((size) => size.released !== true).map((size) => String(size.seats));
  const lockText = locked.length
    ? `${locked.join(" und ")} Sitze sind nicht freigegeben: Qualifikation und Owner-Entscheid stehen aus, der Server lehnt sie ab. `
    : "";
  return `${lockText}Die Tischgröße ist eine eigene Schicht der Auswertung; Serien verschiedener Tischgrößen werden nie zusammengezählt.`;
}

// Opponent presets of one table size: [{value, label}], empty when the size has none (then the
// dialog cannot start: no other preset or size takes its place).
function pairedPodOptions(info, seats) {
  const size = info && Array.isArray(info.sizes) ? info.sizes.find((s) => s.seats === Number(seats)) : null;
  if (!size || !size.pods) return [];
  return Object.entries(size.pods).map(([pod, decks]) => ({
    value: pod,
    label: `${PAIRED_POD_TITLES[pod] || pod} (${(decks || []).map((d) => d.name || d.deck_id).join(", ")})`,
  }));
}

// The pre-run plan comes from the backend (paired_series.planned_detectable_difference_pp via
// GET /api/simulations/paired-plan): one computation, with the Student-t quantiles at
// (seeds - 1) degrees of freedom that the evaluation uses. This only formats it.
function planPairedLines(plan, thresholdPp) {
  const range = (a, b, digits) => (a === b ? StudioUI.num(a, digits) : `${StudioUI.num(a, digits)} bis ${StudioUI.num(b, digits)}`);
  const a = plan.assumptions || {};
  const threshold = Number(thresholdPp) || 0;
  const unknown = plan.detectable_pp_low === null || plan.detectable_pp_low === undefined;
  const first = unknown
    ? `Nachweisbare Differenz mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren: unbekannt (nur ein Seed: keine Streuung zwischen Seeds, die Auswertung gibt dann kein Intervall).`
    : threshold === 0
    ? `Nachweisbar mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren: erst Unterschiede ab etwa ${range(plan.detectable_pp_low, plan.detectable_pp_high, 1)} Prozentpunkten (95 %, Power 80 %). Kleinere Effekte bleiben „kein Unterschied nachweisbar“ – das heißt nie, dass eine Karte egal ist.`
    : `Mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren entscheidbar: erst Abstände zur Schwelle von ${StudioUI.num(threshold, 1)} pp ab etwa ${range(plan.detectable_pp_low, plan.detectable_pp_high, 1)} Prozentpunkten (95 %, Power 80 %).`;
  return [
    first,
    `Für ${StudioUI.num(plan.reference_effect_pp, 0)} pp bräuchte es etwa ${range(plan.pairs_needed_low, plan.pairs_needed_high, 0)} Paare. Referenz: ein einzelner Siegrate-Anteil braucht bei 25 % rund 800 Partien für ±3 pp.`,
    `Annahmen: Paar-Streuung ${StudioUI.num(a.pair_sd, 2)} als vorsichtiger Planungswert (exakt ${StudioUI.num(a.pair_sd_independent_exact, 3)} für unabhängige Partien mit 25 % Siegrate; gepaart: Korrelation ungemessen); Student-t mit ${StudioUI.num(a.degrees_of_freedom, 0)} Freiheitsgraden (Seeds − 1) wie in der Auswertung${a.seats_per_seed > 1 ? `; Sitzrotation mit ${StudioUI.num(a.seats_per_seed, 0)} Sitzen je Seed bis Design-Effekt ${StudioUI.num(a.design_effect, 2)} (Blockkorrelation ${StudioUI.num(a.block_correlation_assumed, 2)} angenommen)` : ""}; Zwischenblicke nicht eingerechnet. Ein Plan, keine Messung.`,
  ];
}

// Ask the backend for the plan and format it; the dialog only shows what this returns.
async function loadPairedPlanLines(api, budgetPairs, seatsPerSeed, thresholdPp) {
  const plan = await api(`/api/simulations/paired-plan?budget_pairs=${encodeURIComponent(budgetPairs)}&seats_per_seed=${encodeURIComponent(seatsPerSeed)}`);
  return planPairedLines(plan, thresholdPp);
}

function notDecidedText(res) {
  const n = StudioUI.num(res.pairs_completed ?? 0, 0);
  const mde = res.detectable_difference_pp;
  const threshold = Number(res.question && res.question.threshold_pp) || 0;
  const mdeText = mde === null || mde === undefined
    ? "die nachweisbare Differenz ist unbekannt"
    : `nachweisbar wären mindestens ${StudioUI.num(mde, 1)} pp (95 %, Power 80 %, aus der gemessenen Paar-Streuung)`;
  if (threshold !== 0) {
    return `Frage „größer als ${StudioUI.num(threshold, 1)} pp?“ nicht entschieden bei n = ${n} Paaren; ${mdeText}.`;
  }
  return `Kein Unterschied nachweisbar bei n = ${n} Paaren; ${mdeText}. Das heißt nicht, dass die Karte egal ist.`;
}

function fmtShare(val) {
  return val === null || val === undefined ? "unbekannt" : StudioUI.num(Number(val), 2);
}

// Library slots of the variant (slot_alignment of the series). A series without the field was
// played before the alignment existed: not aligned, never pooled with aligned series.
function pairedAlignmentText(sa) {
  if (!sa) return "nicht ausgerichtet (ältere Serie)";
  const extra = (Number(sa.appended) || 0) + (Number(sa.dropped) || 0);
  const text = `an Basis ausgerichtet: ${StudioUI.num(sa.swapped_slots, 0)} getauscht, ${StudioUI.num(sa.appended, 0)} angehängt, ${StudioUI.num(sa.dropped, 0)} entfallen`;
  return extra > 0 ? `${text} – nicht deckungsgleich (Kartenzahl verschieden)` : text;
}

function pairedAlignmentShort(sa) {
  if (!sa) return "nicht ausgerichtet (älter)";
  return (Number(sa.appended) || 0) + (Number(sa.dropped) || 0) > 0 ? "nicht deckungsgleich" : "ausgerichtet";
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

// Progress per game, as far as the backend knows it. "gespielt" means the engine has played the game
// to its end; the result of a game only exists once the engine process has ended ("abgeschlossen").
// A record without the figure (an older series) says "unbekannt", never 0; a planned maximum is
// worded as a maximum, because a paired series may stop early.
function seriesPlayedText(played, planned, closed, atMost, running) {
  const known = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
  if (!known(played)) return "Gespielt: unbekannt (ältere Serie ohne Zählung je Partie).";
  const of = known(planned) ? `${atMost ? "von höchstens" : "von"} ${StudioUI.num(planned, 0)}` : "von unbekannt vielen";
  const tail = known(closed) ? ` · abgeschlossen: ${StudioUI.num(closed, 0)}` : "";
  const note = running ? " Das Ergebnis folgt, wenn der Engine-Prozess endet." : "";
  return `Gespielt: ${StudioUI.num(played, 0)} ${of} Partien${tail}.${note}`;
}

function renderPairedMonitor(h, job, deps) {
  const isRunning = job.status === "running" || job.status === "pending";
  const isInterrupted = job.status === "interrupted";
  const statusText = isRunning
    ? "Läuft..."
    : isInterrupted
      ? "Unterbrochen"
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
      h("b", {}, `Paar-Serie „${job.pod}“${job.seed_plan && job.seed_plan.player_count ? ` · ${StudioUI.num(job.seed_plan.player_count, 0)} Sitze` : ""} (${job.series_id}): ${StudioUI.num(donePairs, 0)} / ${StudioUI.num(maxPairs, 0)} Paare (${StudioUI.num(pct, 0)} %)`),
      h("span", { class: "pill " + (isRunning || isInterrupted ? "warn" : job.status === "completed" ? "good" : "bad") }, statusText)),
    h("progress", { value: donePairs, max: maxPairs }),
    h("p", { class: "note note-compact" }, seriesPlayedText(job.games_played, job.games_planned_max, null, true, isRunning)),
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
  } else if (isInterrupted || job.status === "cancelled" || job.status === "failed") {
    const resumeBtn = h("button", {
      type: "button",
      class: "primary mt-2",
      onclick: async () => {
        resumeBtn.disabled = true;
        try {
          const resumed = await deps.api(`/api/simulations/paired/${encodeURIComponent(job.series_id)}/resume`, "POST");
          deps.setActivePaired(resumed);
          deps.pollPaired(job.series_id);
        } catch (err) {
          deps.fail(err);
          resumeBtn.disabled = false;
        }
      },
    }, "Serie fortsetzen");
    monitor.append(resumeBtn);
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
        h("div", {}, h("span", { class: "muted" }, "Bibliotheksplätze: "), h("b", {}, pairedAlignmentText(job.slot_alignment))),
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
          h("thead", {}, h("tr", {}, h("th", {}, "Serie"), h("th", {}, "Status"), h("th", {}, "Ergebnis"), h("th", { class: "num" }, "Differenz"), h("th", {}, "Plätze"), h("th", {}, ""))),
          h("tbody", {}, historyList.slice(0, 10).map((item) => {
            const r = item.result || null;
            const v = pairedVerdictInfo(r);
            const canResume = item.resumable !== undefined
              ? Boolean(item.resumable)
              : (item.status === "interrupted" || item.status === "cancelled" || item.status === "failed");
            let histResumeBtn = null;
            if (canResume) {
              histResumeBtn = h("button", {
                type: "button",
                class: "small primary",
                onclick: async () => {
                  histResumeBtn.disabled = true;
                  try {
                    const resumed = await deps.api(`/api/simulations/paired/${encodeURIComponent(item.series_id)}/resume`, "POST");
                    deps.setActivePaired(resumed);
                    deps.pollPaired(item.series_id);
                  } catch (err) {
                    deps.fail(err);
                    histResumeBtn.disabled = false;
                  }
                },
              }, "Fortsetzen");
            }
            return h("tr", {},
              h("td", {}, h("code", {}, item.series_id)),
              h("td", {}, item.status === "interrupted" ? "unterbrochen" : item.status),
              h("td", {}, v ? v[1] : `${StudioUI.num(item.pairs_attempted ?? 0, 0)}/${item.budget_pairs !== null && item.budget_pairs !== undefined ? StudioUI.num(item.budget_pairs, 0) : "?"} Paare`),
              h("td", { class: "num" }, r ? fmtPp(r.difference_pp) : "–"),
              h("td", { title: pairedAlignmentText(item.slot_alignment) }, pairedAlignmentShort(item.slot_alignment)),
              h("td", {}, h("div", { class: "actions" },
                h("button", {
                  type: "button",
                  class: "small",
                  onclick: () => {
                    deps.setActivePaired(item);
                    refreshPairedSlots(deps);
                  },
                }, "Details"),
                histResumeBtn)));
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
  const tableSelect = h("select", { id: "paired-table-select" },
    ...pairedTableSizeOptions(null).map((o) => h("option", { value: String(o.value), selected: o.selected, disabled: o.disabled }, o.label)));
  const tableNote = h("p", { class: "note note-compact", id: "paired-table-note" }, pairedTableNote(null));
  const blockLine = h("p", { class: "note note-compact", id: "paired-block" });
  const budgetSelect = h("select", { id: "paired-budget-select" },
    ...pairedBudgetOptions(PAIRED_DEFAULT_TABLE_SEATS, true).map((o) => h("option", { value: String(o.value), selected: o.selected }, o.label)));
  const lookSelect = h("select", { id: "paired-look-select" },
    h("option", { value: "4", selected: true }, "alle 4 Paare"),
    h("option", { value: "5" }, "alle 5 Paare"),
    h("option", { value: "10" }, "alle 10 Paare"),
    h("option", { value: "20" }, "alle 20 Paare")
  );
  const seedInput = h("input", { type: "number", value: "1000", class: "seed-input", id: "paired-seed-input" });
  const thresholdInput = h("input", { type: "number", value: "0", step: "0.5", class: "seed-input", id: "paired-threshold-input" });
  const workersInput = h("input", { type: "number", value: "4", min: "1", max: "16", class: "seed-input", id: "paired-workers-input" });
  const gamesPerJvmInput = h("input", { type: "number", value: "16", min: "1", max: "24", class: "seed-input", id: "paired-games-per-jvm-input" });
  const rotateCheck = h("input", { type: "checkbox", checked: true, id: "paired-rotate-check" });
  const rotateText = h("span", { id: "paired-rotate-text" }, `Sitze 1–${PAIRED_DEFAULT_TABLE_SEATS} rotieren`);
  let tableInfo = null;
  const tableSeats = () => Math.round(Number(tableSelect.value) || PAIRED_DEFAULT_TABLE_SEATS);

  const estLine = h("p", { class: "note", id: "paired-estimate" }, estimatePairedText(budgetSelect.value, workersInput.value, tableSeats()));
  const planBox = h("div", { class: "note", id: "paired-plan" });
  const updateEstimate = () => {
    estLine.textContent = estimatePairedText(budgetSelect.value, workersInput.value, tableSeats());
    blockLine.textContent = pairedBlockText(tableSeats(), rotateCheck.checked, budgetSelect.value);
  };
  let planRequest = 0;
  const refreshPlan = async () => {
    const mine = ++planRequest;
    const seats = rotateCheck.checked ? tableSeats() : 1;
    try {
      const lines = await loadPairedPlanLines(deps.api, budgetSelect.value, seats, thresholdInput.value);
      if (mine !== planRequest) return;
      planBox.replaceChildren(...lines.map((line) => h("p", { class: "note note-compact" }, line)));
    } catch (error) {
      if (mine === planRequest) planBox.replaceChildren(h("p", { class: "note note-compact" }, "Planung nicht verfügbar (unbekannt)."));
    }
  };
  const startBtn = h("button", { type: "submit", class: "primary", id: "paired-start-btn" }, "Nachtlauf starten");
  // Rebuild what depends on the table size: budgets (whole blocks), presets, rotation text.
  const applyTableSize = () => {
    const seats = tableSeats();
    const keepPod = podSelect.value;
    budgetSelect.replaceChildren(...pairedBudgetOptions(seats, rotateCheck.checked).map((o) => h("option", { value: String(o.value), selected: o.selected }, o.label)));
    const chosenBudget = pairedBudgetOptions(seats, rotateCheck.checked).find((o) => o.selected);
    if (chosenBudget) budgetSelect.value = String(chosenBudget.value);
    if (tableInfo) {
      const pods = pairedPodOptions(tableInfo, seats);
      if (pods.length) {
        const keep = pods.some((o) => o.value === keepPod) ? keepPod : pods[0].value;
        podSelect.replaceChildren(...pods.map((o) => h("option", { value: o.value, selected: o.value === keep }, o.label)));
        podSelect.value = keep;
        podSelect.disabled = false;
        startBtn.disabled = false;
      } else {
        podSelect.replaceChildren(h("option", { value: "" }, `kein Preset für ${seats} Sitze`));
        podSelect.value = "";
        podSelect.disabled = true;
        startBtn.disabled = true;
      }
    }
    rotateText.textContent = `Sitze 1–${seats} rotieren`;
    updateEstimate();
    refreshPlan();
  };
  tableSelect.addEventListener("change", applyTableSize);
  budgetSelect.addEventListener("change", () => { updateEstimate(); refreshPlan(); });
  rotateCheck.addEventListener("change", applyTableSize);
  thresholdInput.addEventListener("change", refreshPlan);
  workersInput.addEventListener("change", updateEstimate);
  workersInput.addEventListener("input", updateEstimate);
  updateEstimate();
  refreshPlan();

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
      if (!podSelect.value) {
        deps.toast(`Für ${tableSeats()} Sitze gibt es keinen Gegnertisch.`);
        return;
      }
      startBtn.disabled = true;
      try {
        const res = await deps.api("/api/simulations/paired", "POST", {
          base_revision_id: baseSelect.value,
          variant_revision_id: varSelect.value,
          pod: podSelect.value,
          table_seats: tableSeats(),
          budget_pairs: parseInt(budgetSelect.value, 10),
          look_every_pairs: parseInt(lookSelect.value, 10),
          base_seed: parseInt(seedInput.value, 10),
          rotate_seats: rotateCheck.checked,
          threshold_pp: parseFloat(thresholdInput.value) || 0.0,
          workers: Math.max(1, Math.min(16, parseInt(workersInput.value, 10) || 4)),
          games_per_jvm: Math.max(1, Math.min(24, parseInt(gamesPerJvmInput.value, 10) || 16)),
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
    h("label", {}, "Tischgröße", tableSelect),
    h("label", {}, "Gegnertisch", podSelect),
    h("label", {}, "Budget", budgetSelect),
    h("label", {}, "Sequential-Look", lookSelect),
    h("label", {}, "Schwelle (pp)", thresholdInput),
    h("label", {}, "Basis-Seed", seedInput),
    h("label", {}, "Worker", workersInput),
    h("label", {}, "Partien / JVM", gamesPerJvmInput),
    h("label", { class: "paired-check" }, rotateCheck, rotateText),
    startBtn
  );

  const monSlot = h("div", { id: "paired-monitor-slot" });
  const histSlot = h("div", { id: "paired-history-slot" });
  pBox.append(form, tableNote, blockLine, estLine, planBox, monSlot, histSlot);

  body.append(pBox, renderReadinessAuditBox(h, deps));
  refreshPairedSlots(deps);

  const tok = deps.token();
  deps.api("/api/simulations/paired-tables").then((info) => {
    if (!deps.isCurrent(tok) || !info || !Array.isArray(info.sizes)) return;
    tableInfo = info;
    const options = pairedTableSizeOptions(info, tableSeats());
    tableSelect.replaceChildren(...options.map((o) => h("option", { value: String(o.value), selected: o.selected, disabled: o.disabled }, o.label)));
    const chosen = options.find((o) => o.selected);
    tableSelect.value = String(chosen ? chosen.value : PAIRED_DEFAULT_TABLE_SEATS);
    tableNote.textContent = pairedTableNote(info);
    applyTableSize();
  }).catch(() => {});
  loadPairedOptions(deps).then((opts) => {
    if (!deps.isCurrent(tok) || !opts.length) return;
    const defaultVar = (curRev && opts.some((o) => o.ref === curRev)) ? curRev : opts[0].ref;
    const defaultBase = (opts.find((o) => o.ref.startsWith("repo:")) || opts.find((o) => o.ref !== defaultVar) || opts[0]).ref;
    baseSelect.replaceChildren(...opts.map((o) => h("option", { value: o.ref, selected: o.ref === defaultBase }, o.label)));
    varSelect.replaceChildren(...opts.map((o) => h("option", { value: o.ref, selected: o.ref === defaultVar }, o.label)));
  }).catch(() => {});
}

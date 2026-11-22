"use strict";
// Paired overnight A-vs-B comparison series (#1404 op. 6) and C-3 simulator readiness audit.
// DOM creation uses only h() and textContent; zero innerHTML, zero eval, zero inline styles.

// The one measured rate (#1251): 541 games/hour for a WHOLE batch series with 6 workers. The time
// at that rate is shown as a floor ("mindestens"), never as a maximum; paired series throughput is
// unmeasured. #1513's 540/h per worker is an unmeasured assumption and not used for the duration
// (paired_series.MEASURED_BATCH_GAMES_PER_HOUR, assumed_games_per_hour_unmeasured).
const PAIRED_MEASURED_BATCH_GAMES_PER_HOUR = 541.2;
const PAIRED_MEASURED_BATCH_WORKERS = 6;
// Table sizes of a series (#1702): two to six seats. The seat lock (launch.MAX_RELEASED_SEATS) lets the
// Studio start two to four; five and six can be planned here but not started, and the server refuses
// them too. Freigabe nur per Owner-Entscheid: raise PAIRED_RELEASED_SEATS (and partie.js) only then.
const PAIRED_MIN_SEATS = 2;
const PAIRED_MAX_SEATS = 6;
const PAIRED_RELEASED_SEATS = 4;
const PAIRED_DEFAULT_SEATS = 4;
// The one table size the rate above was measured at; for any other size the duration is UNKNOWN.
const PAIRED_MEASURED_TABLE_SEATS = 4;
const PAIRED_LEGACY_BUDGETS = [20, 40, 60, 100, 200];

function pairedTableOptions() {
  const sizes = [];
  for (let seats = PAIRED_MIN_SEATS; seats <= PAIRED_MAX_SEATS; seats += 1) {
    sizes.push({ seats, locked: seats > PAIRED_RELEASED_SEATS, label: `${seats} Sitze${seats > PAIRED_RELEASED_SEATS ? " (nicht freigegeben)" : ""}` });
  }
  return sizes;
}

function pairedLockNote() {
  return `${PAIRED_RELEASED_SEATS + 1} und ${PAIRED_MAX_SEATS} Sitze sind nicht freigegeben (Owner-Entscheid, E15 Q5): Sie lassen sich hier planen, aber nicht starten; der Server lehnt sie ab.`;
}

// Pairs of one block: every combination of starting seat (seed mod seats) and tested seat once.
function pairedBlockPairs(seats, rotate) {
  return rotate ? seats * seats : seats;
}

// The budgets offered at a table size: the usual ones plus whole blocks (complete rotations).
function pairedBudgetOptions(seats, rotate) {
  const block = pairedBlockPairs(seats, rotate);
  const values = new Set(PAIRED_LEGACY_BUDGETS);
  for (const k of [1, 2, 4]) values.add(k * block);
  return [...values].sort((a, b) => a - b).map((pairs) => {
    const blocks = pairs % block === 0 ? pairs / block : null;
    const tail = blocks === null ? "" : ` · ${StudioUI.num(blocks, 0)} ${blocks === 1 ? "Block" : "Blöcke"}, vollständige Rotation`;
    return { value: pairs, label: `${StudioUI.num(pairs, 0)} Paare (bis ${StudioUI.num(2 * pairs, 0)} Partien${tail})` };
  });
}

// The default budget: the long-standing 40 at four seats, else one whole block.
function pairedDefaultBudget(seats, rotate) {
  return seats === PAIRED_DEFAULT_SEATS ? 40 : pairedBlockPairs(seats, rotate);
}

// What the backend plan (paired_series.table_plan) says about the table, in words. The page
// computes none of it: counts, rotation and the lock come from the server.
function pairedTableLines(table) {
  const n = StudioUI.num;
  const lines = [];
  const tested = (table.tested_seats || []).length;
  lines.push(`Tisch mit ${n(table.table_size, 0)} Sitzen: ${n(table.seeds_planned, 0)} Seeds mal ${n(tested, 0)} getestete(r) Sitz(e). Ein Block sind ${n(table.pairs_per_block, 0)} Paare, also ${n(table.games_per_arm_per_block, 0)} Partien je Arm: jede Kombination aus Startsitz (Seed mod ${n(table.table_size, 0)}) und getestetem Sitz einmal.`);
  if (table.rotation_complete) {
    lines.push(`Rotation vollständig: ${n(table.full_blocks, 0)} ${table.full_blocks === 1 ? "Block" : "Blöcke"}, jede Kombination ${n(table.cells_min_pairs, 0)}-mal.`);
  } else {
    lines.push(`Rotation unvollständig: ${n(table.full_blocks, 0)} volle Blöcke plus ${n(table.remainder_pairs, 0)} Paare; ${n(table.cells_missing, 0)} von ${n(table.cells_total, 0)} Kombinationen kommen nie vor, die übrigen ${n(table.cells_min_pairs, 0)} bis ${n(table.cells_max_pairs, 0)}-mal. Ein Vielfaches von ${n(table.pairs_per_block, 0)} Paaren schließt die Rotation.`);
  }
  lines.push(`Aufwand: bis zu ${n(table.max_games, 0)} Partien (${n(table.games_per_arm, 0)} je Arm).`);
  if (Array.isArray(table.opponent_ids) && table.opponent_ids.length) {
    lines.push(`Gegner (Sitz 2 bis ${n(table.table_size, 0)}): ${table.opponent_ids.join(", ")}.`);
  }
  if (table.locked_text) lines.push(table.locked_text);
  return lines;
}

// Five and six seats (#1661, part B, F6): the four-seat rate divided by the measured wall ratio of
// one game (table A, seeds 1-10, one JVM per game, n = 10/10 games per seat count). A median
// ratio is no floor: the text says "geschätzt (abgeleitet)", never "mindestens". The pool series of
// part B is a reference with its own n/N, not the figure (paired_series.WALL_RATIO_VS_FOUR_SEATS,
// POOL_REFERENCE_PART_B; a test holds them equal).
const PAIRED_WALL_RATIO_VS_FOUR_SEATS = { 5: 1.56, 6: 2.22 };
const PAIRED_POOL_REFERENCE_PART_B = { 5: [607.3, 50, 50], 6: [379.2, 72, 72] };

function estimatePairedText(budgetPairs, workers = 4, tableSeats = PAIRED_MEASURED_TABLE_SEATS) {
  const pairs = Math.max(0, Number(budgetPairs) || 0);
  const ratio = PAIRED_WALL_RATIO_VS_FOUR_SEATS[Number(tableSeats)];
  if (ratio !== undefined) {
    const games = pairs * 2;
    const rate = PAIRED_MEASURED_BATCH_GAMES_PER_HOUR / ratio;
    const seconds = Math.round(games * (3600.0 / rate));
    const [poolRate, poolN, poolPlanned] = PAIRED_POOL_REFERENCE_PART_B[Number(tableSeats)];
    return `Dauer: geschätzt ~${StudioUI.num(seconds / 60.0, 1)} min für bis zu ${StudioUI.num(games, 0)} Partien (abgeleitet, keine Untergrenze): die 541 Partien/h des Vierertischs (#1251) geteilt durch das gemessene Wandzeit-Verhältnis ${StudioUI.num(ratio, 2)} je Partie bei ${StudioUI.num(tableSeats, 0)} Sitzen (#1661 Teil B: Tisch A, Seeds 1–10, n = 10/10 Partien je Sitzzahl), also etwa ${StudioUI.num(rate, 0)} Partien/h. Zum Vergleich gemessen: gepaarte Serie im Pool mit 3 Workern ${StudioUI.num(poolRate, 0)} Partien/h (n = ${StudioUI.num(poolN, 0)}/${StudioUI.num(poolPlanned, 0)} Partien), ein anderer Weg. Früher Stopp je nach Look möglich.`;
  }
  if (Number(tableSeats) !== PAIRED_MEASURED_TABLE_SEATS) {
    return `Dauer: unbekannt (UNKNOWN). Für einen Tisch mit ${StudioUI.num(tableSeats, 0)} Sitzen ist kein Durchsatz gemessen (n = 0 Partien); gemessen sind nur Vierertische (541 Partien/h, ganze Batch-Serie mit 6 Workern, #1251; die Zahl der Partien dieser Messung ist im Repository nicht belegt) und das Wandzeit-Verhältnis für 5 und 6 Sitze (#1661 Teil B). Aufwand: bis zu ${StudioUI.num(pairs * 2, 0)} Partien (${StudioUI.num(pairs, 0)} je Arm).`;
  }
  const usedWorkers = Math.max(1, Math.min(16, Math.round(Number(workers) || 1)));
  const maxGames = pairs * 2;
  const seconds = Math.round(maxGames * (3600.0 / PAIRED_MEASURED_BATCH_GAMES_PER_HOUR));
  const minutes = StudioUI.num(seconds / 60.0, 1);
  const floorNote = usedWorkers > PAIRED_MEASURED_BATCH_WORKERS ? " Mit mehr als 6 Workern ist das keine sichere Untergrenze." : "";
  return `Dauer: mindestens ~${minutes} min für bis zu ${StudioUI.num(maxGames, 0)} Partien, gerechnet mit den 541 Partien/h, die nur für eine ganze Batch-Serie mit 6 Workern gemessen sind (#1251). Für gepaarte Serien ist der Durchsatz ungemessen; die Dauer ist vermutlich deutlich länger.${floorNote} Früher Stopp je nach Look möglich.`;
}

// The pre-run plan comes from the backend (paired_series.planned_detectable_difference_pp via
// GET /api/simulations/paired-plan): one computation, with the Student-t quantiles at
// (seeds - 1) degrees of freedom that the evaluation uses. This only formats it.
// The reference sentence of the plan (#1661): at five and six seats the server's base win rate 1/N
// and the games a single win share needs for +-20 % (Wilson); at two to four seats the long-standing
// reference at 25 %. Nothing is computed here.
function planPairedReference(plan) {
  const b = plan.baseline;
  if (!b || !b.applies_to_plan) return "Referenz: ein einzelner Siegrate-Anteil braucht bei 25 % rund 800 Partien für ±3 pp.";
  const pct = (v) => StudioUI.num(v, Number.isInteger(v) ? 0 : 1);
  return `Referenz: Zufallsbasis 1/${StudioUI.num(b.table_size, 0)} = ${pct(b.win_rate_pct)} % bei ${StudioUI.num(b.table_size, 0)} gleich starken Plätzen; ein einzelner Siegrate-Anteil braucht ${StudioUI.num(b.games_needed_wilson, 0)} Partien für ±${pct(b.half_width_pp)} pp (±20 % relativ, 95-%-Wilson-Intervall).`;
}

function planPairedLines(plan, thresholdPp) {
  const range = (a, b, digits) => (a === b ? StudioUI.num(a, digits) : `${StudioUI.num(a, digits)} bis ${StudioUI.num(b, digits)}`);
  const a = plan.assumptions || {};
  const sdRate = a.pair_sd_win_rate_pct === undefined || a.pair_sd_win_rate_pct === null ? 25 : Number(a.pair_sd_win_rate_pct);
  const sdBase = plan.baseline && plan.baseline.applies_to_plan ? ` = Zufallsbasis 1/${StudioUI.num(plan.baseline.table_size, 0)}` : "";
  const threshold = Number(thresholdPp) || 0;
  const unknown = plan.detectable_pp_low === null || plan.detectable_pp_low === undefined;
  const first = unknown
    ? `Nachweisbare Differenz mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren: unbekannt (nur ein Seed: keine Streuung zwischen Seeds, die Auswertung gibt dann kein Intervall).`
    : threshold === 0
    ? `Nachweisbar mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren: erst Unterschiede ab etwa ${range(plan.detectable_pp_low, plan.detectable_pp_high, 1)} Prozentpunkten (95 %, Power 80 %). Kleinere Effekte bleiben „kein Unterschied nachweisbar“ – das heißt nie, dass eine Karte egal ist.`
    : `Mit ${StudioUI.num(plan.budget_pairs, 0)} Paaren entscheidbar: erst Abstände zur Schwelle von ${StudioUI.num(threshold, 1)} pp ab etwa ${range(plan.detectable_pp_low, plan.detectable_pp_high, 1)} Prozentpunkten (95 %, Power 80 %).`;
  return [
    first,
    `Für ${StudioUI.num(plan.reference_effect_pp, 0)} pp bräuchte es etwa ${range(plan.pairs_needed_low, plan.pairs_needed_high, 0)} Paare. ${planPairedReference(plan)}`,
    `Annahmen: Paar-Streuung ${StudioUI.num(a.pair_sd, 2)} als vorsichtiger Planungswert (exakt ${StudioUI.num(a.pair_sd_independent_exact, 3)} für unabhängige Partien mit ${StudioUI.num(sdRate, Number.isInteger(sdRate) ? 0 : 1)} % Siegrate${sdBase}; gepaart: Korrelation ungemessen); Student-t mit ${StudioUI.num(a.degrees_of_freedom, 0)} Freiheitsgraden (Seeds − 1) wie in der Auswertung${a.seats_per_seed > 1 ? `; Sitzrotation mit ${StudioUI.num(a.seats_per_seed, 0)} Sitzen je Seed bis Design-Effekt ${StudioUI.num(a.design_effect, 2)} (Blockkorrelation ${StudioUI.num(a.block_correlation_assumed, 2)} angenommen)` : ""}; Zwischenblicke nicht eingerechnet. Ein Plan, keine Messung.`,
  ];
}

// The plan of a table (also a locked one): the usual plan lines and the table block of the backend.
// A refusal (a preset with too few decks) is not caught here: the dialog shows its text.
async function loadPairedTablePlan(api, budgetPairs, table, thresholdPp) {
  const query = [`budget_pairs=${encodeURIComponent(budgetPairs)}`, `table_size=${encodeURIComponent(table.seats)}`, `rotate_seats=${table.rotate ? "true" : "false"}`];
  if (table.pod) query.push(`pod=${encodeURIComponent(table.pod)}`);
  const plan = await api(`/api/simulations/paired-plan?${query.join("&")}`);
  return { lines: planPairedLines(plan, thresholdPp), table: plan.table || null };
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

// The table of a recorded series: its seat count from the seed plan, "unbekannt" for an older record.
function pairedMonitorTableText(job) {
  const seats = job.seed_plan ? job.seed_plan.player_count : null;
  const known = seats !== null && seats !== undefined && Number.isFinite(Number(seats));
  const tested = Array.isArray(job.tested_seats) ? job.tested_seats.length : null;
  return known
    ? `Tisch: ${StudioUI.num(seats, 0)} Sitze, getestete Sitze: ${tested === null ? "unbekannt" : StudioUI.num(tested, 0)}.`
    : "Tisch: Sitzzahl unbekannt (ältere Serie).";
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
      h("b", {}, `Paar-Serie „${job.pod}“ (${job.series_id}): ${StudioUI.num(donePairs, 0)} / ${StudioUI.num(maxPairs, 0)} Paare (${StudioUI.num(pct, 0)} %)`),
      h("span", { class: "pill " + (isRunning || isInterrupted ? "warn" : job.status === "completed" ? "good" : "bad") }, statusText)),
    h("progress", { value: donePairs, max: maxPairs }),
    h("p", { class: "note note-compact" }, seriesPlayedText(job.games_played, job.games_planned_max, null, true, isRunning)),
    h("p", { class: "note note-compact" }, `Basis (A): ${job.base_ref} · Variante (B): ${job.variant_ref}`),
    h("p", { class: "note note-compact", id: "paired-monitor-table" }, pairedMonitorTableText(job)));

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
    h("option", { value: "precon" }, "Precon (Lorehold, Animated Army, Token Triumph, …)"),
    h("option", { value: "mixed" }, "Mixed (Kaervek, Animated Army, Lorehold, …)"),
    h("option", { value: "optimized" }, "Optimized (Eldrazi, Kaervek, Hosts of Mordor, …)")
  );
  const tableSelect = h("select", { id: "paired-table-size-select" },
    pairedTableOptions().map((opt) => h("option", { value: String(opt.seats), selected: opt.seats === PAIRED_DEFAULT_SEATS }, opt.label)));
  tableSelect.value = String(PAIRED_DEFAULT_SEATS);
  const budgetSelect = h("select", { id: "paired-budget-select" });
  const fillBudgets = (seats, rotate) => {
    const keep = pairedDefaultBudget(seats, rotate);
    budgetSelect.replaceChildren(...pairedBudgetOptions(seats, rotate).map((opt) => h("option", { value: String(opt.value), selected: opt.value === keep }, opt.label)));
    budgetSelect.value = String(keep);
  };
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
  const rotateText = h("span", { id: "paired-rotate-text" }, `Sitze 1–${PAIRED_DEFAULT_SEATS} rotieren`);
  const tableNote = h("p", { class: "note note-compact", id: "paired-table-note" }, pairedLockNote());
  const startBtn = h("button", { type: "submit", class: "primary", id: "paired-start-btn" }, "Nachtlauf starten");

  const tableSeats = () => Math.max(PAIRED_MIN_SEATS, Math.min(PAIRED_MAX_SEATS, parseInt(tableSelect.value, 10) || PAIRED_DEFAULT_SEATS));
  const tableLocked = () => tableSeats() > PAIRED_RELEASED_SEATS;
  fillBudgets(PAIRED_DEFAULT_SEATS, true);
  const estLine = h("p", { class: "note", id: "paired-estimate" }, estimatePairedText(budgetSelect.value, workersInput.value, tableSeats()));
  const planBox = h("div", { class: "note", id: "paired-plan" });
  const updateEstimate = () => {
    estLine.textContent = estimatePairedText(budgetSelect.value, workersInput.value, tableSeats());
  };
  const updateTable = () => {
    rotateText.textContent = `Sitze 1–${tableSeats()} rotieren`;
    startBtn.disabled = tableLocked();
  };
  let planRequest = 0;
  const refreshPlan = async () => {
    const mine = ++planRequest;
    try {
      const planned = await loadPairedTablePlan(deps.api, budgetSelect.value, { seats: tableSeats(), rotate: rotateCheck.checked, pod: podSelect.value }, thresholdInput.value);
      if (mine !== planRequest) return;
      const lines = [...(planned.table ? pairedTableLines(planned.table) : []), ...planned.lines];
      planBox.replaceChildren(...lines.map((line) => h("p", { class: "note note-compact" }, line)));
    } catch (error) {
      if (mine === planRequest) planBox.replaceChildren(h("p", { class: "note note-compact" }, `Planung nicht verfügbar (unbekannt): ${deps.fail(error, true)}`));
    }
  };
  tableSelect.addEventListener("change", () => { fillBudgets(tableSeats(), rotateCheck.checked); updateTable(); updateEstimate(); refreshPlan(); });
  podSelect.addEventListener("change", refreshPlan);
  budgetSelect.addEventListener("change", () => { updateEstimate(); refreshPlan(); });
  rotateCheck.addEventListener("change", () => { fillBudgets(tableSeats(), rotateCheck.checked); updateEstimate(); refreshPlan(); });
  thresholdInput.addEventListener("change", refreshPlan);
  workersInput.addEventListener("change", updateEstimate);
  workersInput.addEventListener("input", updateEstimate);
  updateTable();
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
      if (tableLocked()) {
        deps.toast(pairedLockNote());
        return;
      }
      startBtn.disabled = true;
      try {
        const res = await deps.api("/api/simulations/paired", "POST", {
          base_revision_id: baseSelect.value,
          variant_revision_id: varSelect.value,
          pod: podSelect.value,
          // the usual four-seat table is named by its pod as before; another size is sent explicitly
          ...(tableSeats() === PAIRED_DEFAULT_SEATS ? {} : { table_size: tableSeats() }),
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
        startBtn.disabled = tableLocked();
      }
    },
  },
    h("label", {}, "Basis (A)", baseSelect),
    h("label", {}, "Variante (B)", varSelect),
    h("label", {}, "Gegnertisch", podSelect),
    h("label", {}, "Tischgröße", tableSelect),
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
  pBox.append(form, tableNote, estLine, planBox, monSlot, histSlot);

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

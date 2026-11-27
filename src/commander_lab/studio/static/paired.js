"use strict";
// Paired overnight A-vs-B comparison series (#1404 op. 6) and C-3 simulator readiness audit.
// DOM creation uses only h() and textContent; zero innerHTML, zero eval, zero inline styles.

// The one measured rate (#1251): 541 games/hour for a WHOLE batch series with 6 workers. The time
// at that rate is shown as a floor ("mindestens"), never as a maximum; paired series throughput is
// unmeasured. #1513's 540/h per worker is an unmeasured assumption and not used for the duration
// (paired_series.MEASURED_BATCH_GAMES_PER_HOUR, assumed_games_per_hour_unmeasured).
const PAIRED_MEASURED_BATCH_GAMES_PER_HOUR = 541.2;
const PAIRED_MEASURED_BATCH_WORKERS = 6;
// Table sizes of a series (#1702, #1672): two to eight seats. PAIRED_RELEASED_SEATS mirrors the SIMULATE
// seat lock (launch.MAX_RELEASED_SEATS, now eight: E18, seven and eight seats for simulations only); a size
// above it can be planned here but not started, and the server refuses it too. PLAY has its own lock
// (launch.MAX_RELEASED_PLAY_SEATS, six, partie.js), not this one.
const PAIRED_MIN_SEATS = 2;
const PAIRED_MAX_SEATS = 8;
const PAIRED_RELEASED_SEATS = 8;
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
  if (PAIRED_RELEASED_SEATS >= PAIRED_MAX_SEATS) return "";
  if (PAIRED_RELEASED_SEATS + 1 === PAIRED_MAX_SEATS) return `${PAIRED_MAX_SEATS} Sitze sind nicht freigegeben (Owner-Entscheid, E15 Q5): Sie lassen sich hier planen, aber nicht starten; der Server lehnt sie ab.`;
  return `${PAIRED_RELEASED_SEATS + 1} ${PAIRED_RELEASED_SEATS + 2 === PAIRED_MAX_SEATS ? "und" : "bis"} ${PAIRED_MAX_SEATS} Sitze sind nicht freigegeben (Owner-Entscheid, E15 Q5): Sie lassen sich hier planen, aber nicht starten; der Server lehnt sie ab.`;
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

// Five and six seats (#1661, part B, F6): the four-seat batch rate divided by the ratio of the
// wall-time medians of table A only (seeds 1-10, one JVM per game, n = 10/10 games per seat count).
// A ratio of one table's medians is neither floor nor forecast: the text says "grobe Orientierung aus
// Tisch A", never "mindestens", and names the spread (seed-pair median, table B) and the measured pool
// series of part B with its own n/N (paired_series.WALL_RATIO_VS_FOUR_SEATS,
// WALL_RATIO_SEED_PAIR_MEDIAN, WALL_RATIO_TABLE_B_VS_A4, POOL_REFERENCE_PART_B; a test holds them equal).
const PAIRED_WALL_RATIO_VS_FOUR_SEATS = { 5: 1.56, 6: 2.23 }; // 20,18 / 12,91 and 28,73 / 12,91 = 2,2254
const PAIRED_WALL_RATIO_SPREAD = { 5: [1.63, 1.43], 6: [2.63, 1.68] };
const PAIRED_POOL_REFERENCE_PART_B = { 5: [607.3, 50, 50], 6: [379.2, 72, 72] };
// Seven and eight seats (#1672): no Owner-PC throughput, the duration stays UNKNOWN. The warning names
// one game per JVM in the container of the feasibility run (paired_series.SINGLE_GAME_REFERENCE_7_8; a
// test holds them equal): [median wall s, min s, max s, RSS median MiB, RSS max MiB, decisions median,
// games, planned, second median s, second max s, second games, second planned, RSS of a JVM with 8 games (two runs)].
// Memory at 16 games per JVM is unknown (n = 0).
const PAIRED_SINGLE_GAME_REFERENCE_7_8 = { 7: [87.0, 46.1, 102.3, 955, 1343, 9760, 6, 6, 114.4, 140.9, 8, 8, 1231, 883], 8: [98.8, 65.7, 121.9, 945, 1006, 10314, 6, 6, 143.8, 189.0, 8, 8, 1255, 1255] };

function pairedSingleGameReferenceText(tableSeats) {
  const ref = PAIRED_SINGLE_GAME_REFERENCE_7_8[Number(tableSeats)];
  if (ref === undefined) return "";
  const [wall, low, high, rss, rssMax, decisions, games, planned, secondWall, secondMax, secondGames, secondPlanned, batchA, batchB] = ref;
  return ` Hinweis ${StudioUI.num(tableSeats, 0)} Sitze: eine Partie dauerte im Median ${StudioUI.num(wall, 1)} s (${StudioUI.num(low, 1)} bis ${StudioUI.num(high, 1)} s) bei etwa ${StudioUI.num(decisions, 0)} Entscheidungen, Spitzen-Speicher der Engine (RSS) im Median ${StudioUI.num(rss, 0)} MiB, höchstens ${StudioUI.num(rssMax, 0)} MiB (n = ${StudioUI.num(games, 0)}/${StudioUI.num(planned, 0)} Partien; Machbarkeitsversuch #1672 im Cloud-Container, eine JVM je Partie, SIMULATED_RESULT, kein Owner-PC-Wert). Zweite Messung (Gates #1672, zwei Tische parallel, Fremdlast): Median ${StudioUI.num(secondWall, 1)} s, bis ${StudioUI.num(secondMax, 1)} s (n = ${StudioUI.num(secondGames, 0)}/${StudioUI.num(secondPlanned, 0)} Partien); Spitzen-Speicher einer JVM mit 8 Partien ${StudioUI.num(batchA, 0)} und ${StudioUI.num(batchB, 0)} MiB (2 Läufe). Bei 16 Partien je JVM (Studio-Standard) ist der Speicher unbekannt (n = 0): wenige Worker wählen und den freien Arbeitsspeicher prüfen (je Worker eine JVM mit bis zu 3 GB Heap).`;
}

function estimatePairedText(budgetPairs, workers = 4, tableSeats = PAIRED_MEASURED_TABLE_SEATS) {
  const pairs = Math.max(0, Number(budgetPairs) || 0);
  const ratio = PAIRED_WALL_RATIO_VS_FOUR_SEATS[Number(tableSeats)];
  if (ratio !== undefined) {
    const games = pairs * 2;
    const rate = PAIRED_MEASURED_BATCH_GAMES_PER_HOUR / ratio;
    const seconds = Math.round(games * (3600.0 / rate));
    const [poolRate, poolN, poolPlanned] = PAIRED_POOL_REFERENCE_PART_B[Number(tableSeats)];
    const [seedPair, tableB] = PAIRED_WALL_RATIO_SPREAD[Number(tableSeats)];
    return `Dauer: grobe Orientierung ~${StudioUI.num(seconds / 60.0, 1)} min für bis zu ${StudioUI.num(games, 0)} Partien, aus Tisch A (weder Untergrenze noch Prognose): die Batch-Rate des Vierertischs von 541 Partien/h (ganze Batch-Serie, 6 Worker, 8 Partien je JVM, #1251) geteilt durch das Verhältnis der Wandzeit-Mediane ${StudioUI.num(ratio, 2)} bei ${StudioUI.num(tableSeats, 0)} Sitzen (#1661 Teil B: nur Tisch A, Seeds 1–10, n = 10/10 Partien je Sitzzahl), also etwa ${StudioUI.num(rate, 0)} Partien/h. Das Verhältnis streut: Median der Seed-Paar-Verhältnisse ${StudioUI.num(seedPair, 2)}, Tisch B gegen Tisch A mit 4 Sitzen etwa ${StudioUI.num(tableB, 2)}. Gemessen ist die gepaarte Serie im Pool mit 3 Workern mit ${StudioUI.num(poolRate, 0)} Partien/h (n = ${StudioUI.num(poolN, 0)}/${StudioUI.num(poolPlanned, 0)} Partien), ${poolRate > rate ? "schneller" : "langsamer"} als dieser Wert: die Dauer kann deutlich kürzer oder länger sein. Früher Stopp je nach Look möglich.`;
  }
  if (Number(tableSeats) !== PAIRED_MEASURED_TABLE_SEATS) {
    return `Dauer: unbekannt (UNKNOWN). Für einen Tisch mit ${StudioUI.num(tableSeats, 0)} Sitzen ist kein Durchsatz gemessen (n = 0 Partien); gemessen sind nur Vierertische (541 Partien/h, ganze Batch-Serie mit 6 Workern, #1251; die Zahl der Partien dieser Messung ist im Repository nicht belegt) und das Wandzeit-Verhältnis für 5 und 6 Sitze (#1661 Teil B). Aufwand: bis zu ${StudioUI.num(pairs * 2, 0)} Partien (${StudioUI.num(pairs, 0)} je Arm).${pairedSingleGameReferenceText(tableSeats)}`;
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
// The reference sentence of the plan (#1661, #1757): at two, three, and five to eight seats the
// server's base win rate 1/N and the games a single win share needs for +-20 % (Wilson); at four
// seats the long-standing reference at 25 %. Nothing is computed here.
function planPairedReference(plan) {
  const b = plan.baseline;
  if (!b || !b.applies_to_plan) return "Referenz: ein einzelner Siegrate-Anteil braucht bei 25 % rund 800 Partien für ±3 pp.";
  const pct = (v) => StudioUI.num(v, Number.isInteger(v) ? 0 : Math.abs(v * 10 - Math.round(v * 10)) < 1e-9 ? 1 : 2);
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
  const lines = [
    first,
    `Für ${StudioUI.num(plan.reference_effect_pp, 0)} pp bräuchte es etwa ${range(plan.pairs_needed_low, plan.pairs_needed_high, 0)} Paare. ${planPairedReference(plan)}`,
    `Annahmen: Paar-Streuung ${StudioUI.num(a.pair_sd, 2)} als vorsichtiger Planungswert (exakt ${StudioUI.num(a.pair_sd_independent_exact, 3)} für unabhängige Partien mit ${StudioUI.num(sdRate, Number.isInteger(sdRate) ? 0 : 1)} % Siegrate${sdBase}; gepaart: Korrelation ungemessen); Student-t mit ${StudioUI.num(a.degrees_of_freedom, 0)} Freiheitsgraden (Seeds − 1) wie in der Auswertung${a.seats_per_seed > 1 ? `; Sitzrotation mit ${StudioUI.num(a.seats_per_seed, 0)} Sitzen je Seed bis Design-Effekt ${StudioUI.num(a.design_effect, 2)} (Blockkorrelation ${StudioUI.num(a.block_correlation_assumed, 2)} angenommen)` : ""}; Zwischenblicke nicht eingerechnet. Ein Plan, keine Messung.`,
  ];
  const band = plan.measured_spread_band;
  if (band && band.available) {
    const samples = Array.isArray(band.samples) ? band.samples : [];
    const detKnown = band.detectable_pp_min !== null && band.detectable_pp_min !== undefined && band.detectable_pp_max !== null && band.detectable_pp_max !== undefined;
    const detText = detKnown
      ? `ab etwa ${range(band.detectable_pp_min, band.detectable_pp_max, 1)} pp`
      : "unbekannt (nur ein Seed)";
    const sdText = band.sd_pair_min === band.sd_pair_max
      ? StudioUI.num(band.sd_pair_min, 4)
      : `${StudioUI.num(band.sd_pair_min, 4)}–${StudioUI.num(band.sd_pair_max, 4)}`;
    const sampleDesc = samples.map((s) => {
      const clusterPart = s.clusters === null || s.clusters === undefined ? "ungeclustert" : `k = ${StudioUI.num(s.clusters, 0)} Seed-Cluster`;
      return `${s.label} (${s.source}, n = ${StudioUI.num(s.pairs, 0)}/${StudioUI.num(s.planned, 0)}, ${clusterPart}, DEFF ${StudioUI.num(s.deff, 3)})`;
    }).join("; ");
    lines.push(
      `Gemessene Paar-Streuung (SIMULATED_RESULT, Bandbreite aus ${StudioUI.num(samples.length, 0)} ${samples.length === 1 ? "Stichprobe" : "Stichproben"}): nachweisbar ${detText}, für ${StudioUI.num(plan.reference_effect_pp, 0)} pp etwa ${range(band.pairs_needed_min, band.pairs_needed_max, 0)} Paare (sd_pair ${sdText}${sampleDesc ? `; ${sampleDesc}` : ""}); kein Garantiewert, ersetzt nicht den konservativen Planungswert.`
    );
  } else if (band && !band.available) {
    lines.push("Gemessene Paar-Streuung: unbekannt (n = 0 Paare für diese Tischgröße).");
  }
  return lines;
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

// The threshold of the question ("is B greater than A by more than x pp?"); 0 when the result
// carries none. A result with a threshold other than 0 answers that question, not "B beats A".
function pairedThresholdPp(res) {
  const raw = res && (res.question ? res.question.threshold_pp : res.threshold_pp);
  return raw !== null && raw !== undefined && raw !== "" && Number.isFinite(Number(raw)) ? Number(raw) : 0;
}

function pairedVerdictInfo(res) {
  if (!res) return null;
  const threshold = pairedThresholdPp(res);
  const question = `„größer als ${StudioUI.num(threshold, 1)} pp?“`;
  if (res.status === "DECIDED" && res.answer === "ABOVE") {
    return ["good", threshold === 0 ? "Entschieden: Variante B übertrifft Basis A" : `Entschieden: Frage ${question} mit ja beantwortet`];
  }
  if (res.status === "DECIDED" && res.answer === "NOT_ABOVE") {
    return ["bad", threshold === 0 ? "Entschieden: Variante B liegt nicht über Basis A" : `Entschieden: Frage ${question} mit nein beantwortet`];
  }
  if (res.status === "NOT_DECIDED") {
    return ["warn", threshold === 0 ? "Budget erschöpft: kein eindeutiger Unterschied" : `Budget erschöpft: Frage ${question} nicht entschieden`];
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
  // Both batch and paired series now show a descriptive interim summary below while running (#1828).
  const note = !running ? ""
    : atMost ? " Der vorläufige Zwischenstand der abgeschlossenen Paare steht darunter (kein Entscheid)."
      : " Der Zwischenstand der abgeschlossenen Partien steht darunter.";
  return `Gespielt: ${StudioUI.num(played, 0)} ${of} Partien${tail}.${note}`;
}

function pairedDurationText(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return "unbekannt";
  const minutes = Math.round(Number(seconds) / 60);
  if (minutes < 1) return "weniger als 1 Minute";
  if (minutes < 60) return `etwa ${StudioUI.num(minutes, 0)} Min.`;
  return `etwa ${StudioUI.num(Math.floor(minutes / 60), 0)} Std. ${StudioUI.num(minutes % 60, 0)} Min.`;
}

function pairedPaceEta(job) {
  const none = { perHour: null, etaSeconds: null, done: null, seconds: null };
  if (!job || !job.run_started_at || !job.observed_at) return none;
  const known = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
  if (!known(job.games_played) || !known(job.games_played_at_run_start) || !known(job.games_planned_max)) return none;
  const seconds = (Date.parse(job.observed_at) - Date.parse(job.run_started_at)) / 1000;
  const done = Number(job.games_played) - Number(job.games_played_at_run_start);
  if (!Number.isFinite(seconds) || seconds < 10 || !(done >= 1)) return none;
  const perSecond = done / seconds;
  const left = Math.max(0, Number(job.games_planned_max) - Number(job.games_played));
  return { perHour: perSecond * 3600, etaSeconds: left / perSecond, done, seconds };
}

function pairedTruthBadge(summary, isPartial) {
  if (isPartial || !summary || !summary.status) {
    const n = summary && Number.isFinite(Number(summary.pairs_completed)) ? Number(summary.pairs_completed) : 0;
    return [
      "warn",
      n > 0 ? `Vorläufiger Zwischenstand (kein Entscheid · ${StudioUI.num(n, 0)} Paare)` : "Vorläufig (noch kein Paar abgeschlossen)",
    ];
  }
  if (summary.status === "NO_PAIRS") {
    return ["warn", "Keine auswertbaren Paare (0 Paare · keine Aussage möglich)"];
  }
  if (summary.status === "DECIDED" && summary.answer === "ABOVE") {
    const threshold = pairedThresholdPp(summary);
    return threshold === 0
      ? ["good", "Hinweis auf echten Unterschied (B > A · Look-Intervall schließt Schwelle aus)"]
      : ["good", `Frage „größer als ${StudioUI.num(threshold, 1)} pp?“ mit ja beantwortet (Look-Intervall ganz über der Schwelle, nicht „B > A“)`];
  }
  if (summary.status === "DECIDED" && summary.answer === "NOT_ABOVE") {
    const threshold = pairedThresholdPp(summary);
    return threshold === 0
      ? ["bad", "Kein ausreichender Vorteil für B (B nicht über A · Look-Intervall)"]
      : ["bad", `Kein ausreichender Vorteil für B (Frage „größer als ${StudioUI.num(threshold, 1)} pp?“ mit nein beantwortet · Look-Intervall nicht über der Schwelle)`];
  }
  return ["warn", pairedThresholdPp(summary) === 0
    ? "Zufall nicht ausgeschlossen (Look-Intervall umfasst Schwelle · kein eindeutiger Unterschied)"
    : "Frage nicht entschieden (Look-Intervall umfasst die Schwelle)"];
}

// BEGIN paired-interim
// The interim of a running paired series, its partial result after a stop and the seed pair table
// (#1828). Pure text and count helpers: the server computes every figure (paired_series.
// look_interim_view from the last planned look, paired_comparison.run_comparison_series), nothing is
// recomputed here. A look is a planned interim at the level the series spent for it: never a
// 95 % interval that shrinks with every pair, never a decision. A figure the server does not send
// stays text ("unbekannt"), never 0.
const PAIRED_SEED_PAIR_ROWS_SHOWN = 60;

function pairedKnown(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

function pairedNum(value, digits = 0) {
  return pairedKnown(value) ? StudioUI.num(value, digits) : "unbekannt";
}

function pairedPpText(value) {
  return pairedKnown(value) ? fmtPp(value) : "unbekannt";
}

// The level one look spent: "Look-Niveau 99,9 % (α = 0,0001 für diesen Look)". The level is that of
// the look's own interval, not the 95 % of a single look; α is the share of the overall error budget.
function pairedLevelText(view) {
  const alphaRaw = pairedKnown(view.look_alpha) ? view.look_alpha : view.decision_alpha;
  let level = pairedKnown(view.decision_level_pct) ? StudioUI.numFlex(view.decision_level_pct, 4) : null;
  if (level === null && pairedKnown(alphaRaw)) level = StudioUI.numFlex((1 - Number(alphaRaw)) * 100, 4);
  let alpha = "unbekannt";
  if (pairedKnown(alphaRaw)) {
    alpha = Number(alphaRaw) < 0.000001 ? "weniger als 0,000001" : StudioUI.numFlex(alphaRaw, 6);
  }
  return `Look-Niveau ${level === null ? "unbekannt" : `${level} %`} (α = ${alpha} für diesen Look)`;
}

function pairedLookTitle(view) {
  const look = pairedKnown(view.look_index) && pairedKnown(view.looks_planned)
    ? `Look ${StudioUI.num(view.look_index, 0)} von ${StudioUI.num(view.looks_planned, 0)}`
    : "Look unbekannt";
  return `Zwischenstand (${look}, kein Entscheid)`;
}

// "Teilergebnis: k von N Paaren": k = pairs evaluated at the last look, N = the planned budget.
function pairedPartialTitle(view) {
  return `Teilergebnis: ${pairedNum(view.pairs_completed)} von ${pairedNum(view.pairs_budget)} Paaren, ungeplanter Stopp: nur beschreibend`;
}

// Delta B - A with the interval of the look at its stated level. No interval (no spread between the
// seeds, or fewer than two seeds): the text says so; "kein Intervall" is not an interval [0; 0].
function pairedLookDeltaText(view) {
  if (!pairedKnown(view.pairs_completed) || Number(view.pairs_completed) < 1) {
    return "Delta (B − A): unbekannt (noch kein Paar abgeschlossen).";
  }
  const ci = view.decision_ci_pp;
  const interval = Array.isArray(ci) && ci.length === 2 && pairedKnown(ci[0]) && pairedKnown(ci[1])
    ? `Look-Intervall [${fmtPp(ci[0])}; ${fmtPp(ci[1])}] bei ${pairedLevelText(view)}`
    : `kein Look-Intervall (zu wenige Seeds oder keine Streuung zwischen den Seeds: dann entscheidet bei ${pairedLevelText(view)} nur der Vorzeichentest über die Seeds)`;
  return `Delta (B − A): ${pairedPpText(view.difference_pp)} · ${interval}`;
}

function pairedLookCountsText(view) {
  const n = pairedNum(view.pairs_completed);
  const budget = pairedNum(view.pairs_budget);
  const attempted = pairedNum(view.pairs_attempted);
  const censored = pairedNum(view.pairs_censored);
  return `Paare: ${n}/${budget} ausgewertet · zensiert: ${censored} von ${attempted} gespielten Paaren (ein zensiertes Paar zählt nie als Niederlage).`;
}

function pairedLookSignText(view) {
  const b = view.variant_only_wins;
  const a = view.baseline_only_wins;
  const discordant = pairedKnown(b) && pairedKnown(a) ? Number(b) + Number(a) : null;
  return `Vorzeichentest: B besser in ${pairedNum(b)}, A besser in ${pairedNum(a)}, gleich in ${pairedNum(view.tied_pairs)} Paaren; diskordante Paare ${pairedNum(discordant)}/${pairedNum(view.pairs_completed)}; exaktes p = ${pairedKnown(view.sign_test_p_value) ? StudioUI.numFlex(view.sign_test_p_value, 6) : "unbekannt"}.`;
}

const PAIRED_BLOCKER_WORDS = {
  CENSORING_LIMIT: "zu viele zensierte Paare",
  ASYMMETRIC_CENSORING: "einseitig zensierte Paare zwischen den beiden Armen",
};

// What the look means for the stop rule. Never "entschieden": the series result decides.
function pairedLookRuleText(view, stopped) {
  if (stopped && view.look_decides !== true && !view.censoring_blocker) {
    return "Dieser Look hat nicht entschieden; die Serie wurde danach vor dem nächsten Look gestoppt (ungeplant).";
  }
  if (view.censoring_blocker) {
    const why = PAIRED_BLOCKER_WORDS[view.censoring_blocker] || String(view.censoring_blocker);
    return `Die Stoppregel ist an diesem Look durch Zensierung gesperrt (${why}); die Serie entscheidet hier nicht.`;
  }
  if (view.look_decides === true) {
    return "Dieser Look erfüllt die Stoppregel; die Serie endet mit ihrem Ergebnis, dieser Zwischenstand ist nicht das Ergebnis.";
  }
  if (view.look_decides === false) {
    return "Dieser Look entscheidet nicht; die Serie läuft bis zum nächsten Look oder zum Budget.";
  }
  return "Ob dieser Look die Stoppregel erfüllt: unbekannt.";
}

// The line "echt vs. Zufall". Only the finished series answers it: a look is no decision and an
// unplanned stop is descriptive. "nicht unterscheidbar von Zufall" is said for an exhausted budget
// only (a series that ended on censoring says "nicht beurteilbar"), and never means the card is
// irrelevant. kind: "interim" (running), "partial" (stopped), "final" (series result).
function pairedChanceLine(res, kind) {
  const label = "Echt vs. Zufall: ";
  if (kind === "interim") {
    return `${label}offen; erst das Ergebnis der Serie beantwortet das, ein Zwischenstand sagt dazu nichts.`;
  }
  if (kind === "partial") {
    return `${label}keine Aussage; ein ungeplanter Stopp ist nur beschreibend und kein Ergebnis der Serie.`;
  }
  if (!res || res.status === "NO_PAIRS" || !res.status) {
    return `${label}keine Aussage möglich (keine auswertbaren Paare).`;
  }
  const level = pairedLevelText(res);
  const threshold = pairedThresholdPp(res);
  const stopCensoring = res.status === "NOT_DECIDED" && res.stop_reason !== "BUDGET_EXHAUSTED";
  if (stopCensoring) {
    const why = PAIRED_BLOCKER_WORDS[res.stop_reason] || String(res.stop_reason || "unbekannt");
    return `${label}nicht beurteilbar: die Serie endete ohne Entscheid wegen Zensierung (${why}), nicht mit einem ausgeschöpften Budget.`;
  }
  if (threshold !== 0) {
    // The question was "B greater than A by more than x pp": no statement about chance versus 0.
    const t = StudioUI.num(threshold, 1);
    const head = `${label}gilt nur für die Schwelle 0 pp; diese Serie fragte „größer als ${t} pp?“: `;
    if (res.status === "DECIDED" && res.answer === "ABOVE") {
      return `${head}ja, das Look-Intervall liegt ganz über der Schwelle (${level}); das sagt nichts darüber, ob B von A abweicht, wenn die Schwelle 0 pp wäre.`;
    }
    if (res.status === "DECIDED" && res.answer === "NOT_ABOVE") {
      return `${head}nein, das Look-Intervall liegt bei oder unter der Schwelle (${level}).`;
    }
    return `${head}nicht entschieden, das Look-Intervall umfasst die Schwelle.`;
  }
  if (res.status === "DECIDED" && res.answer === "ABOVE") {
    return `${label}Hinweis auf einen echten Unterschied: das Look-Intervall liegt ganz über 0 pp, mit Zufall allein bei ${level} nicht erklärbar (diese Piloten, dieser Tisch, SIMULATED_RESULT).`;
  }
  if (res.status === "DECIDED" && res.answer === "NOT_ABOVE") {
    return `${label}B liegt nicht über A (Look-Intervall bei oder unter 0 pp, ${level}); das heißt nicht, dass B schlechter ist.`;
  }
  return `${label}nicht unterscheidbar von Zufall bei dieser Stichprobe (heißt nicht, dass die Karte egal ist). ${pairedVerdictInfo(res)[1]}; die nachweisbare Differenz steht darunter.`;
}

// PairRecord (0-based seat) of a stored result as a table row (1-based seat).
function pairedPairRows(pairs) {
  if (!Array.isArray(pairs)) return [];
  return pairs.map((p) => ({ ...p, seat: typeof p.seat === "number" ? p.seat + 1 : p.seat, status: "paired" }));
}

// n/N over ALL rows, also those the table does not show. Censored pairs have no PairRecord, so a
// stored result lists none of them: their number comes from the series (pairs_censored), never 0.
// ctx: {pairs_censored, pairs_attempted} of the series, when the caller has them.
function pairedSeedPairCounts(rows, ctx) {
  const out = { total: rows.length, withDiff: 0, bBetter: 0, aBetter: 0, same: 0, censoredRows: 0, open: 0 };
  for (const row of rows) {
    if (row.status === "censored") { out.censoredRows += 1; continue; }
    if (!pairedKnown(row.difference)) { out.open += 1; continue; }
    out.withDiff += 1;
    const d = Number(row.difference);
    if (d > 0) out.bBetter += 1; else if (d < 0) out.aBetter += 1; else out.same += 1;
  }
  const c = ctx || {};
  out.censored = pairedKnown(c.pairs_censored) ? Number(c.pairs_censored) : (out.censoredRows > 0 ? out.censoredRows : null);
  out.attempted = pairedKnown(c.pairs_attempted) && Number(c.pairs_attempted) >= rows.length ? Number(c.pairs_attempted) : rows.length;
  return out;
}

function pairedSeedPairSummaryText(rows, shown, ctx) {
  const c = pairedSeedPairCounts(rows, ctx);
  const more = rows.length - shown;
  const window = more > 0
    ? `${StudioUI.num(shown, 0)} von ${StudioUI.num(rows.length, 0)} Paaren angezeigt, ${StudioUI.num(more, 0)} weitere nicht`
    : `${StudioUI.num(rows.length, 0)} Paare`;
  const censored = c.censored === null
    ? "zensiert: unbekannt (zensierte Paare stehen nicht in der Tabelle)"
    : c.censoredRows === 0 && c.censored > 0
      ? `zensiert ${StudioUI.num(c.censored, 0)} von ${StudioUI.num(c.attempted, 0)} gespielten Paaren (zensierte Paare haben keine Differenz und stehen nicht in der Tabelle)`
      : `zensiert ${StudioUI.num(c.censored, 0)} von ${StudioUI.num(c.attempted, 0)} gespielten Paaren`;
  return {
    summary: `Seed-Paartabelle (${window} · Einzelspiel-Drilldown ins Replay)`,
    counts: `Differenz bekannt in ${StudioUI.num(c.withDiff, 0)}/${StudioUI.num(c.attempted, 0)} gespielten Paaren: B besser ${StudioUI.num(c.bBetter, 0)}, A besser ${StudioUI.num(c.aBetter, 0)}, gleich ${StudioUI.num(c.same, 0)}; ${censored}; offen ${StudioUI.num(c.open, 0)}.`,
    more: more > 0 ? `${StudioUI.num(more, 0)} weitere Paare nicht angezeigt (angezeigt ${StudioUI.num(shown, 0)}/${StudioUI.num(rows.length, 0)}).` : null,
  };
}
// END paired-interim

// The determinism guard of a series that was played on the worker pool (S1 Rest, #1660), in words.
// "unbewacht n/N": n of the N finished games have no transcript hash or no game key, so the guard
// could not compare them. "vergleichbar": the number of game keys with two or more games, the only
// ones it can compare at all; a normal A/B series plays every key once, so that is 0 and nothing was
// compared. No journal, no finished game or an answer without the figures is "unbekannt", never 0.
function pairedGuardParts(guard) {
  const known = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
  if (guard === null || guard === undefined || typeof guard !== "object") {
    return { short: "unbekannt", text: "Determinismus-Wächter: unbekannt (kein Journal: nicht auf dem Pool-Weg gespielt oder noch nichts gespielt)." };
  }
  if (guard.error) {
    return { short: "nicht prüfbar", text: `Determinismus-Wächter: nicht prüfbar (${guard.error}).` };
  }
  if (guard.violation) {
    return { short: "DETERMINISM_VIOLATION", text: "Determinismus-Wächter: DETERMINISM_VIOLATION, ein Spielschlüssel hat zwei verschiedene Transkripte; die Serie hat kein Ergebnis." };
  }
  if (!known(guard.unguarded) || !known(guard.finished)) {
    return { short: "unbekannt", text: "Determinismus-Wächter: unbekannt (noch keine abgeschlossene Partie im Journal)." };
  }
  const short = `unbewacht ${StudioUI.num(guard.unguarded, 0)}/${StudioUI.num(guard.finished, 0)}`;
  const comparable = known(guard.comparable_keys)
    ? `${StudioUI.num(guard.comparable_keys, 0)} Schlüssel mit mindestens 2 Partien`
    : "unbekannt viele Schlüssel";
  return {
    short,
    text: `Determinismus-Wächter: ${short} abgeschlossene Partien ohne Transkript-Hash oder Schlüssel; vergleichbar: ${comparable} (verglichen wird nur, was zweimal gespielt wurde).`,
  };
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

function renderValidityBlock(h, vb) {
  if (!vb) return null;
  const sc = vb.seat_curve || {};
  const seats = Array.isArray(sc.seats) ? sc.seats : [];
  const om = vb.pilot_omissions || {};
  const omText = om.status === "measured" && om.display ? om.display : "unbekannt";
  const seatTable = seats.length
    ? h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {},
        h("th", {}, "Sitz"),
        h("th", { class: "num" }, "Siege/Spiele (n/N)"),
        h("th", { class: "num" }, "Siegrate"),
        h("th", { class: "num" }, "95 %-Wilson-CI"),
        h("th", { class: "num" }, "Playgroup-Referenz (4 Sitze)"))),
      h("tbody", {}, seats.map((s) => h("tr", {},
        h("td", {}, `Sitz ${StudioUI.num(s.seat, 0)}`),
        h("td", { class: "num" }, s.n_of_N || "unbekannt"),
        h("td", { class: "num" }, s.win_rate_pct !== null && s.win_rate_pct !== undefined ? `${StudioUI.num(s.win_rate_pct, 1)} %` : "unbekannt"),
        h("td", { class: "num" }, Array.isArray(s.ci95_pct) && s.ci95_pct.length === 2
          ? `[${StudioUI.num(s.ci95_pct[0], 1)} %; ${StudioUI.num(s.ci95_pct[1], 1)} %]`
          : "unbekannt"),
        h("td", { class: "num" }, sc.reference_comparable && s.reference_win_rate_pct !== null && s.reference_win_rate_pct !== undefined
          ? `${StudioUI.num(s.reference_win_rate_pct, 1)} %`
          : "nur für 4 Sitze"))))))
    : h("p", { class: "muted" }, "Sitzkurve: unbekannt (keine abgeschlossenen Partien oder Tischgröße unbekannt).");
  return h("div", { class: "validity-block", id: "paired-validity-block" },
    h("h5", {}, "Gültigkeitsblock (SIMULATED_RESULT)"),
    h("p", { class: "note note-compact" }, vb.validity_statement || "unbekannt"),
    h("p", { class: "note note-compact" }, `Pilot-Auslassungen: ${omText}`),
    seatTable,
    sc.reference_note ? h("p", { class: "note note-compact" }, sc.reference_note) : null);
}

function renderConsistencyTable(h, ct) {
  if (!ct || !Array.isArray(ct.rows) || !ct.rows.length) return null;
  const classes = Array.isArray(ct.origin_classes) ? ct.origin_classes : [];
  const byClass = ct.by_origin_class || {};
  const bodyRows = [];
  for (const cls of classes) {
    const items = Array.isArray(byClass[cls.key]) ? byClass[cls.key] : [];
    for (const item of items) {
      bodyRows.push(h("tr", {},
        h("td", {}, cls.label || item.origin_label || item.origin_class),
        h("td", {}, item.label || item.metric_id),
        h("td", { class: "num" }, item.n_of_N || "unbekannt"),
        h("td", {}, item.display || "unbekannt")));
    }
  }
  if (!bodyRows.length) return null;
  return h("div", { class: "consistency-block", id: "paired-consistency-table" },
    h("h5", {}, "Konsistenztabelle (3 Herkunftsklassen)"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {},
        h("th", {}, "Herkunftsklasse"),
        h("th", {}, "Kennzahl"),
        h("th", { class: "num" }, "n/N"),
        h("th", {}, "Wert / Status"))),
      h("tbody", {}, bodyRows))));
}

// The seed pair table (one row per pair, its seed, the outcome of A and of B, the difference), built
// from the PairRecords of a result or the live rows; long tables show the first rows and say how many
// more there are (n/N over all rows in the line above the table).
function renderPairedSeedPairs(h, rows, ctx) {
  if (!Array.isArray(rows) || !rows.length) return null;
  const gameLink = (gid, label) => gid
    ? h("a", { href: `partie.html?partie=${encodeURIComponent(gid)}` }, `${label} →`)
    : h("span", { class: "muted" }, "–");
  const fmtSide = (credit, err, gid, sideLabel) => {
    if (err) return h("span", { class: "muted" }, `Fehler (${err})`);
    if (credit === null || credit === undefined) return h("span", { class: "muted" }, "läuft / offen");
    const label = credit >= 1 ? "Sieg" : credit > 0 ? `Split (${StudioUI.num(credit, 2)})` : "Niederlage";
    return h("span", {}, `${label} · `, gameLink(gid, `Replay ${sideLabel}`));
  };
  const fmtDelta = (row) => {
    if (row.status === "censored") return h("span", { class: "pill warn" }, "zensiert");
    if (row.difference === null || row.difference === undefined) return h("span", { class: "muted" }, "–");
    const d = Number(row.difference);
    const cls = d > 0 ? "seed-delta pos" : d < 0 ? "seed-delta neg" : "seed-delta zero";
    const txt = d > 0 ? `+${StudioUI.numFlex(d, 2)} B` : d < 0 ? `${StudioUI.numFlex(d, 2)} A` : "0 Gleich";
    return h("span", { class: cls }, txt);
  };
  const shownRows = rows.slice(0, PAIRED_SEED_PAIR_ROWS_SHOWN);
  const text = pairedSeedPairSummaryText(rows, shownRows.length, ctx);
  return h("details", { class: "paired-seed-pairs mt-2", id: "paired-seed-pairs", open: rows.length <= 20 },
    h("summary", {}, text.summary),
    h("p", { class: "note note-compact", id: "paired-seed-pairs-counts" }, text.counts),
    h("div", { class: "table-wrap mt-2" }, h("table", {},
      h("thead", {}, h("tr", {},
        h("th", { class: "num" }, "Seed"),
        h("th", { class: "num" }, "Sitz"),
        h("th", {}, "Basis (A)"),
        h("th", {}, "Variante (B)"),
        h("th", {}, "Paar-Delta"))),
      h("tbody", {}, shownRows.map((row) => h("tr", {},
        h("td", { class: "num" }, row.seed !== null && row.seed !== undefined ? StudioUI.num(row.seed, 0) : "–"),
        h("td", { class: "num" }, row.seat !== null && row.seat !== undefined ? `Sitz ${StudioUI.num(row.seat, 0)}` : "–"),
        h("td", {}, fmtSide(row.base_credit, row.base_error, row.base_game_id, "A")),
        h("td", {}, fmtSide(row.variant_credit, row.variant_error, row.variant_game_id, "B")),
        h("td", {}, fmtDelta(row))))))),
    text.more ? h("p", { class: "note note-compact", id: "paired-seed-pairs-more" }, text.more) : null);
}

// The interim card of one look (a running series) or the partial result of a stopped one: the same
// look figures, a different title and chance line. view: paired_series.look_interim_view or a partial.
function renderPairedLookCard(h, view, kind, extraLines, seedRows) {
  const stopped = kind === "partial";
  const badge = stopped
    ? ["warn", "ungeplanter Stopp · nur beschreibend · kein Ergebnis der Serie"]
    : ["warn", "Zwischenstand · kein Entscheid"];
  return h("div", { class: "sim-summary sim-interim paired-ab-card", id: stopped ? "paired-partial" : "paired-look-interim" },
    h("div", { class: "sim-monitor-head" },
      h("h4", { class: "mt-0", id: stopped ? "paired-partial-title" : "paired-look-title" }, stopped ? pairedPartialTitle(view) : pairedLookTitle(view)),
      h("span", { class: `pill ${badge[0]}` }, badge[1])),
    stopped ? h("p", { class: "note note-compact" }, pairedLookTitle(view) + ": letzter geplanter Look dieser Serie.") : null,
    h("p", { id: "paired-look-delta" }, pairedLookDeltaText(view)),
    h("p", { class: "note note-compact", id: "paired-look-counts" }, pairedLookCountsText(view)),
    h("p", { class: "note note-compact", id: "paired-look-sign" }, pairedLookSignText(view)),
    h("p", { class: "note note-compact", id: "paired-look-rule" }, pairedLookRuleText(view, stopped)),
    h("p", { class: "note note-compact", id: "paired-chance-line" }, pairedChanceLine(null, kind)),
    ...(extraLines || []).map((line) => h("p", { class: "note note-compact" }, line)),
    renderPairedSeedPairs(h, seedRows, view),
    h("p", { class: "note note-compact" }, "SIMULATED_RESULT (Zwischenstand, nicht zusammengezählt mit anderen Serien oder Deck-Ständen): der Stopp ist vorab durch Looks mit geplantem α-Verbrauch festgelegt; ein früherer Stopp ist nur beschreibend. Simulationsergebnisse fließen nie in die Tierliste ein (Gewicht 0)."));
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
          : "Fehlgeschlagen";
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
    h("p", { class: "note note-compact", id: "paired-monitor-table" }, pairedMonitorTableText(job)),
    h("p", { class: "note note-compact", id: "paired-monitor-guard" }, pairedGuardParts(job.determinism_guard).text));

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
    if (job.status === "failed") {
      monitor.append(StudioUI.renderErrorCard(
        StudioUI.classifyError({ error: job.error || "Serie fehlgeschlagen", failure_class: job.failure_class }, { context: "batch" }),
        {
          retry: () => resumeBtn.click(),
          build: () => { if (typeof deps.goBuild === "function") deps.goBuild(); },
        }
      ));
    }
    monitor.append(resumeBtn);
  }

  const stopped = job.status === "cancelled" || job.status === "interrupted";
  const failed = job.status === "failed";
  // The card of a look belongs to a running series only; a failed one has no interim to show.
  const look = isRunning && job.interim && typeof job.interim === "object" && !job.result ? job.interim : null;
  const partial = stopped && !job.result && job.result_partial && typeof job.result_partial === "object" ? job.result_partial : null;
  const interim = job.interim_comparison;
  const hasDescriptive = Boolean(interim && typeof interim === "object" && !job.result);
  // The look interval is the only interval shown as the series' own; it comes from the last planned
  // look. A stopped series keeps that look as a partial result, flagged, never as a finished series.
  if (partial) {
    const later = pairedKnown(job.pairs_attempted) && pairedKnown(partial.pairs_attempted)
      ? Number(job.pairs_attempted) - Number(partial.pairs_attempted)
      : null;
    const laterText = later === null
      ? "Wie viele Paare nach diesem Look noch gespielt wurden: unbekannt."
      : later > 0
        ? `Nach diesem Look wurden noch ${StudioUI.num(later, 0)} Paare gespielt; sie sind in diesem Teilergebnis nicht eingerechnet.`
        : "Nach diesem Look wurde kein weiteres Paar abgeschlossen.";
    monitor.append(renderPairedLookCard(h, partial, "partial", [laterText], pairedPairRows(partial.pairs)));
  } else if (look) {
    monitor.append(renderPairedLookCard(h, look, "interim", [], null));
  } else if (stopped && !job.result) {
    monitor.append(h("p", { class: "note", id: "paired-partial-none" },
      `Kein Teilergebnis (vor dem ersten Look gestoppt, ungeplanter Stopp): unbekannt, nicht 0. Ein Teilergebnis ist der letzte geplante Look; er liegt nur im Speicher und wird nicht in die Serien-Datei geschrieben (nach einem Neustart des Servers fehlt er ebenfalls).${hasDescriptive ? " Was bis zum Stopp gespielt wurde, steht darunter (beschreibend, ungeplant)." : ""} Das ist keine Aussage über die Karten.`));
  }
  if (hasDescriptive) {
    const pairsDone = interim.pairs_completed;
    const pairsBudget = pairedKnown(interim.pairs_budget) ? interim.pairs_budget : job.budget_pairs;
    const truth = pairedTruthBadge(interim, true);
    const pace = pairedPaceEta(job);
    const ended = stopped || failed;
    const tempoText = ended
      ? `Bis zum ${failed ? "Fehler" : "Stopp"} gespielt: ${pairedNum(pairsDone)} von ${pairedNum(pairsBudget)} Paaren (ungeplant: nur beschreibend, kein Teilergebnis im Sinn eines Looks, nicht als abgeschlossene Serie gewertet).`
      : pace.perHour === null
        ? "Tempo: unbekannt (noch zu wenige Partien oder keine Zeitangabe) · Restzeit: unbekannt"
        : `Tempo: ${StudioUI.num(pace.perHour, 1)} Partien/Std. · Restzeit: ${pairedDurationText(pace.etaSeconds)} (Schätzung)`;
    const fmtRateCi = (rate, ci) => {
      if (rate === null || rate === undefined) return "unbekannt";
      const ciStr = Array.isArray(ci) && ci.length === 2 ? ` [${StudioUI.num(ci[0], 1)} %; ${StudioUI.num(ci[1], 1)} %]` : "";
      return `${fmtRatePct(rate)}${ciStr}`;
    };
    const descriptiveTitle = ended
      ? `Beschreibend, alle bis zum ${failed ? "Fehler" : "Stopp"} gespielten Paare (ungeplant): ${pairedNum(pairsDone)} / ${pairedNum(pairsBudget)} Paare`
      : "A/B-Zwischenstand (live, alle bisher fertigen Paare, beschreibend)";
    const abInterim = h("div", { class: "sim-summary sim-interim paired-ab-card", id: "paired-interim" },
      h("div", { class: "sim-monitor-head" },
        h("h4", { class: "mt-0" }, descriptiveTitle),
        h("span", { class: `pill ${truth[0]}`, id: "paired-truth-flag" }, truth[1])),
      h("div", { class: "sim-grid" },
        h("div", {}, h("span", { class: "muted" }, "Basis-Siegrate (A, 95 %-Wilson-CI je Rate): "), h("b", {}, fmtRateCi(interim.base_rate, interim.base_ci95_pp))),
        h("div", {}, h("span", { class: "muted" }, "Varianten-Siegrate (B, 95 %-Wilson-CI je Rate): "), h("b", {}, fmtRateCi(interim.variant_rate, interim.variant_ci95_pp))),
        h("div", {}, h("span", { class: "muted" }, "Delta (B − A): "), h("b", {}, pairedPpText(interim.difference_pp))),
        h("div", { title: "Ein Intervall zu 95 %, das mit jedem Paar schmaler wird: ein Blick bei jedem Paar beweist nichts (Peeking). Das Intervall zum Look-Niveau steht im Block „Zwischenstand (Look k von K)“." }, h("span", { class: "muted" }, "95 %-Cluster-CI (Delta, unadjustiert, nur beschreibend): "), h("b", {}, fmtCiPp(interim.difference_ci95_pp))),
        h("div", {}, h("span", { class: "muted" }, "Diskordante Paare: "), h("b", {}, `${pairedNum(interim.variant_only_wins)}B : ${pairedNum(interim.baseline_only_wins)}A · ${pairedNum(interim.tied_pairs)} gleich (${pairedNum(interim.pairs_censored)} zensiert)`))),
      h("p", { class: "note note-compact", id: "paired-interim-pace" }, tempoText),
      partial ? null : renderPairedSeedPairs(h, job.seed_pairs, { pairs_censored: interim.pairs_censored }),
      h("p", { class: "note note-compact" }, "SIMULATED_RESULT (Teilstand): kein Entscheid vor Erreichen der geplanten Looks. Simulationsergebnisse fließen nie in die Tierliste ein (Gewicht 0)."));
    monitor.append(abInterim);
  }

  const res = job.result;
  if (res) {
    const vInfo = pairedVerdictInfo(res);
    const truthFlag = pairedTruthBadge(res, Boolean(job.summary_partial));
    const bridgeSha = (res.bridge_jar_sha256s && res.bridge_jar_sha256s[0]) || job.bridge_jar_sha256 || null;
    const epochLabel = res.covered_by_sealed_epoch ? "versiegelt" : ((res.bridge_qualification_states || qualStates).join(", ") || "nicht versiegelt");
    const pVal = res.sign_test_p_value !== null && res.sign_test_p_value !== undefined
      ? StudioUI.num(res.sign_test_p_value, 4)
      : "–";
    const sumBox = h("div", { class: "sim-summary paired-ab-card", id: "paired-ab-card" },
      h("div", { class: "sim-monitor-head" },
        h("h4", { class: "mt-0" }, "Sequentielles Paar-Ergebnis (A vs. B)"),
        vInfo ? h("span", { class: `pill ${vInfo[0]}` }, vInfo[1]) : null,
        h("span", { class: `pill ${truthFlag[0]}`, id: "paired-truth-flag" }, truthFlag[1])),
      h("p", { class: "note" }, res.stop_reason || ""),
      h("p", { class: "note", id: "paired-chance-line" }, pairedChanceLine(res, "final")),
      res.stop_reason === "BUDGET_EXHAUSTED" ? h("p", { class: "note", id: "paired-not-decided" }, notDecidedText(res)) : null,
      h("div", { class: "sim-grid" },
        h("div", {}, h("span", { class: "muted" }, "Basis-Siegrate (A): "), h("b", {}, fmtRatePct(res.base_rate))),
        h("div", {}, h("span", { class: "muted" }, "Varianten-Siegrate (B): "), h("b", {}, fmtRatePct(res.variant_rate))),
        h("div", {}, h("span", { class: "muted" }, "Differenz (B − A): "), h("b", {}, fmtPp(res.difference_pp))),
        h("div", {}, h("span", { class: "muted" }, "95 %-CI (Cluster): "), h("b", {}, fmtCiPp(res.difference_ci95_pp))),
        h("div", {}, h("span", { class: "muted" }, `Look-CI (${res.decision_level_pct !== null && res.decision_level_pct !== undefined ? StudioUI.numFlex(res.decision_level_pct, 4) : "–"} %): `), h("b", {}, fmtCiPp(res.decision_ci_pp))),
        h("div", {}, h("span", { class: "muted" }, "Sign-Test p / Diskordant: "), h("b", {}, `${pVal} (${StudioUI.num(res.variant_only_wins, 0)}B : ${StudioUI.num(res.baseline_only_wins, 0)}A · ${StudioUI.num(res.tied_pairs, 0)} gleich)`)),
        h("div", {}, h("span", { class: "muted" }, "Paare fertig / zensiert: "), h("b", {}, `${StudioUI.num(res.pairs_completed, 0)} / ${StudioUI.num(res.pairs_censored, 0)}`)),
        res.baseline_reuse && res.baseline_reuse.reused_count > 0
          ? h("div", {}, h("span", { class: "muted" }, "Basis-Wiederverwendung (#1589): "), h("b", {}, `${StudioUI.num(res.baseline_reuse.reused_count, 0)} / ${StudioUI.num(res.baseline_reuse.total_base_games, 0)} übernommen · Gegenprobe ${StudioUI.num(res.baseline_reuse.spot_checks_verified, 0)} / ${StudioUI.num(res.baseline_reuse.spot_checks_planned ?? res.baseline_reuse.spot_checks_verified, 0)} identisch`))
          : null,
        h("div", { title: "Paarung spart Partien nur, wenn der gemessene Anteil deutlich unter dem Wert unabhängiger Partien liegt." }, h("span", { class: "muted" }, "Diskordante Paare (gemessen / unabhängig erwartet): "), h("b", {}, `${StudioUI.num((res.variant_only_wins ?? 0) + (res.baseline_only_wins ?? 0), 0)}/${StudioUI.num(res.pairs_completed ?? 0, 0)} = ${fmtShare(res.discordant_share)} / ${fmtShare(res.discordant_share_if_independent)}`)),
        h("div", {}, h("span", { class: "muted" }, "Bibliotheksplätze: "), h("b", {}, pairedAlignmentText(job.slot_alignment))),
        h("div", {}, h("span", { class: "muted" }, "Seeds: "), h("b", {}, job.seed_plan && job.seed_plan.first_seed !== null && job.seed_plan.first_seed !== undefined ? `${job.seed_plan.first_seed} bis ${job.seed_plan.last_seed} (fortlaufend)` : "unbekannt")),
        h("div", {}, h("span", { class: "muted" }, "Bridge-JAR: "), h("code", { title: bridgeSha || "" }, bridgeSha ? String(bridgeSha).slice(0, 12) : "–")),
        h("div", {}, h("span", { class: "muted" }, "Epoche: "), h("b", {}, epochLabel))),
      ...(res.warnings && res.warnings.length
        ? [h("ul", { class: "note" }, res.warnings.map((w) => h("li", {}, w)))]
        : []),
      renderValidityBlock(h, res.validity_block || job.validity_block),
      renderConsistencyTable(h, res.consistency_table || job.consistency_table),
      renderPairedSeedPairs(h, Array.isArray(job.seed_pairs) ? job.seed_pairs : pairedPairRows(res.pairs), { pairs_censored: res.pairs_censored, pairs_attempted: res.pairs_played }),
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
          h("thead", {}, h("tr", {}, h("th", {}, "Serie"), h("th", {}, "Status"), h("th", {}, "Ergebnis"), h("th", { class: "num" }, "Differenz"), h("th", {}, "Plätze"), h("th", {}, "Wächter"), h("th", {}, ""))),
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
              h("td", { class: "paired-guard", title: pairedGuardParts(item.determinism_guard).text }, pairedGuardParts(item.determinism_guard).short),
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
  const tableNote = pairedLockNote() ? h("p", { class: "note note-compact", id: "paired-table-note" }, pairedLockNote()) : null;
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
  pBox.append(form, ...(tableNote ? [tableNote] : []), estLine, planBox, monSlot, histSlot);

  body.append(pBox, renderReadinessAuditBox(h, deps));
  refreshPairedSlots(deps);

  const tok = deps.token();
  loadPairedOptions(deps).then((opts) => {
    if (!deps.isCurrent(tok) || !opts.length) return;
    const preset = deps.pairedPreset ? deps.pairedPreset() : null;
    if (preset && deps.clearPairedPreset) deps.clearPairedPreset();
    const list = opts.slice();
    if (preset && preset.baseRef && !list.some((o) => o.ref === preset.baseRef)) {
      list.push({ ref: preset.baseRef, label: `Stand ${preset.baseRef.slice(0, 20)}` });
    }
    if (preset && preset.variantRef && !list.some((o) => o.ref === preset.variantRef)) {
      list.push({ ref: preset.variantRef, label: `Stand ${preset.variantRef.slice(0, 20)}` });
    }
    const defaultVar = (preset && preset.variantRef && list.some((o) => o.ref === preset.variantRef))
      ? preset.variantRef
      : ((curRev && list.some((o) => o.ref === curRev)) ? curRev : list[0].ref);
    const defaultBase = (preset && preset.baseRef && list.some((o) => o.ref === preset.baseRef))
      ? preset.baseRef
      : (list.find((o) => o.ref.startsWith("repo:")) || list.find((o) => o.ref !== defaultVar) || list[0]).ref;
    baseSelect.replaceChildren(...list.map((o) => h("option", { value: o.ref, selected: o.ref === defaultBase }, o.label)));
    varSelect.replaceChildren(...list.map((o) => h("option", { value: o.ref, selected: o.ref === defaultVar }, o.label)));
  }).catch(() => {});
}

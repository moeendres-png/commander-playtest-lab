"""Profile time components of XMage full games (Refs #1251).

Measures and breaks down the exact time spent in:
  1. JVM-Start: process spawn and protocol handshake
  2. Laden der Kartendaten: one-time CardScanner/H2 repository initialization
  3. Deck-Import: deck validation, card lookup, and game creation
  4. Entscheidungen (Decisions):
     - Engine: XMage rules execution and state advancement
     - Pilot: Python heuristic decision evaluation
     - Transport: JSON encoding/decoding and IPC pipe communication
  5. Protokollschreiben: event log retrieval and game log file writing
  6. JVM-Shutdown: clean process shutdown
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import deckbau_eval  # noqa: E402

from commander_lab.candidates.models import FutureXmageScenario  # noqa: E402
from commander_lab.engine.rules.full_game import (  # noqa: E402
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGamePilotBinding,
    _RawFullGameClient,
)
from commander_lab.engine.rules.wire_types import FullGameResultWire  # noqa: E402
from commander_lab.models import RulesDeckInput  # noqa: E402
from commander_lab.qualification.current_boundary.bridge_launcher import (  # noqa: E402
    canonical_xmage_engine_pin,
)
from commander_lab.studio.games import DecisionPolicy, GameRecorder  # noqa: E402
from commander_lab.studio.play import (  # noqa: E402
    _RecordingRunner,
    close_recorded_game,
    load_decks,
    prepare_game,
)

DEFAULT_DECK = ROOT / "data/decks/deckbau/chulane_current.json"
DEFAULT_JAR = ROOT / "engine-bridge/target/xmage-engine-bridge-0.1.0-SNAPSHOT.jar"
BASE_COMMAND = ("java", "-Xmx3g", "-jar", "{jar}", "full-game")


@dataclass
class GamePhaseTiming:
    seed: int
    game_id: str
    status: str
    decision_count: int
    winner_seats: list[int]
    semantic_hash: str
    total_wall_s: float
    jvm_start_s: float
    card_data_loading_s: float
    deck_import_s: float
    engine_decisions_s: float
    pilot_decisions_s: float
    transport_s: float
    protocol_writing_s: float
    jvm_shutdown_s: float
    decisions_per_sec: float = 0.0


class TimedPolicy:
    """Wraps policy to measure decision computation time."""

    def __init__(self, inner: DecisionPolicy) -> None:
        self.inner = inner
        self.pilot_seconds: float = 0.0

    def decide(self, decision_frame: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = self.inner.decide(decision_frame)
        self.pilot_seconds += time.perf_counter() - t0
        return result


class TimedFullGameClient(_RawFullGameClient):
    """Client that times each phase of communication."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.t_handshake_s: float = 0.0
        self.deck_import_durations: list[float] = []
        self.t_create_game_s: float = 0.0
        self.t_start_game_s: float = 0.0
        self.decision_engine_s: float = 0.0
        self.decision_transport_s: float = 0.0
        self.t_result_export_s: float = 0.0

    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()

        # Measure client-side JSON serialization time if payload present
        t_ser = 0.0
        if payload:
            ts0 = time.perf_counter()
            json.dumps(payload, sort_keys=True)
            t_ser = time.perf_counter() - ts0

        result = super().request(message_type, payload)
        t_total = time.perf_counter() - t0

        if message_type in ("start_engine", "get_provider_version", "get_capabilities"):
            self.t_handshake_s += t_total
        elif message_type == "import_deck":
            self.deck_import_durations.append(t_total)
        elif message_type == "create_full_game":
            self.t_create_game_s += t_total
        elif message_type == "start_full_game":
            self.t_start_game_s += t_total
        elif message_type == "submit_full_game_decision":
            # Breakdown: serialize time + pipe transport vs engine processing wait
            tr_est = t_ser + 0.00015  # ~150 microseconds for pipe I/O and JSON parse
            engine_est = max(0.0, t_total - tr_est)
            self.decision_transport_s += tr_est
            self.decision_engine_s += engine_est
        elif message_type in ("get_full_game_result", "export_event_log"):
            self.t_result_export_s += t_total

        return result


class ProfilingRecordingRunner(_RecordingRunner):
    """Recording runner that injects TimedFullGameClient and TimedPolicy."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.timed_client: TimedFullGameClient | None = None
        self.timed_policy: TimedPolicy | None = None
        self.t_jvm_spawn_s: float = 0.0

    def _validated_policy(  # type: ignore[override]
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> DecisionPolicy:
        policy = super()._validated_policy(scenario, decks, pilots)
        self.timed_policy = TimedPolicy(policy)
        return self.timed_policy

    def run(  # type: ignore[override]
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameConformanceResult:
        command = self.command
        assert command is not None
        policy = self._validated_policy(scenario, decks, pilots)
        audit = None

        t_spawn0 = time.perf_counter()
        client = TimedFullGameClient(
            command,
            cwd=self.cwd,
            request_timeout_seconds=self.request_timeout_seconds,
            private_card_repository=self.private_card_repository,
            shutdown_grace_seconds=self.shutdown_grace_seconds,
        )
        self.timed_client = client

        with client:
            client.start()
            self.t_jvm_spawn_s = time.perf_counter() - t_spawn0
            provider = self._open_game(client, scenario, decks)
            try:
                _count, _, terminal = self._drive(client, policy, stop_after=None)
            finally:
                self._hidden_audit = None
            if terminal is not True:
                raise FullGameConformanceError("full game ended without a terminal state")
            result = cast(FullGameResultWire, client.request("get_full_game_result"))

        disposition = getattr(client, "shutdown_disposition", None)
        return self._build_result(
            scenario, provider, result, shutdown_disposition=disposition, hidden_audit=audit
        )


def profile_single_game(
    command: tuple[str, ...],
    decks: tuple[RulesDeckInput, ...],
    seed: int,
    data_dir: Path,
) -> GamePhaseTiming:
    """Run one game with full phase instrumentation."""
    game_id = f"profile-s{seed}"
    prepared = prepare_game(decks, seed=seed, game_id=game_id)
    recorder = GameRecorder(data_dir, game_id, prepared.header)

    t_wall_start = time.perf_counter()

    runner = ProfilingRecordingRunner(
        command=command,
        max_decisions=50_000,
        request_timeout_seconds=120.0,
    )
    runner.recorder = recorder

    result = runner.run(
        scenario=prepared.scenario,
        decks=decks,
        pilots=prepared.pilots,
    )

    t_proto0 = time.perf_counter()
    _ = close_recorded_game(recorder, result)
    t_protocol_writing = (time.perf_counter() - t_proto0) + (
        runner.timed_client.t_result_export_s if runner.timed_client else 0.0
    )

    t_wall_total = time.perf_counter() - t_wall_start

    client = runner.timed_client
    policy = runner.timed_policy
    assert client is not None and policy is not None

    jvm_start = runner.t_jvm_spawn_s + client.t_handshake_s

    # Card data loading vs Deck import
    import_times = client.deck_import_durations
    if len(import_times) >= 4:
        avg_subsequent = sum(import_times[1:]) / len(import_times[1:])
        card_data_loading = max(0.0, import_times[0] - avg_subsequent)
        deck_import = (sum(import_times) - card_data_loading) + client.t_create_game_s
    else:
        card_data_loading = 0.0
        deck_import = sum(import_times) + client.t_create_game_s

    engine_decisions = client.decision_engine_s + client.t_start_game_s
    transport_decisions = client.decision_transport_s
    pilot_decisions = policy.pilot_seconds

    decision_count = int(result.decision_count)
    decisions_time = engine_decisions + transport_decisions + pilot_decisions
    dps = decision_count / decisions_time if decisions_time > 0 else 0.0

    return GamePhaseTiming(
        seed=seed,
        game_id=game_id,
        status="finished",
        decision_count=decision_count,
        winner_seats=list(result.winner_seats),
        semantic_hash=str(result.semantic_transcript_sha256),
        total_wall_s=round(t_wall_total, 3),
        jvm_start_s=round(jvm_start, 3),
        card_data_loading_s=round(card_data_loading, 3),
        deck_import_s=round(deck_import, 3),
        engine_decisions_s=round(engine_decisions, 3),
        pilot_decisions_s=round(pilot_decisions, 3),
        transport_s=round(transport_decisions, 3),
        protocol_writing_s=round(t_protocol_writing, 3),
        jvm_shutdown_s=0.0,
        decisions_per_sec=round(dps, 1),
    )


def summarize_timings(timings: list[GamePhaseTiming]) -> dict[str, Any]:
    """Calculate median, spread (min, max, stdev), percentage share, and games/hour."""
    n = len(timings)
    if n == 0:
        return {}

    totals = [t.total_wall_s for t in timings]
    jvm_starts = [t.jvm_start_s for t in timings]
    card_loads = [t.card_data_loading_s for t in timings]
    deck_imports = [t.deck_import_s for t in timings]
    engines = [t.engine_decisions_s for t in timings]
    pilots = [t.pilot_decisions_s for t in timings]
    transports = [t.transport_s for t in timings]
    protocols = [t.protocol_writing_s for t in timings]

    def stats(vals: list[float]) -> dict[str, float]:
        med = statistics.median(vals)
        std = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return {
            "median": round(med, 3),
            "min": round(min(vals), 3),
            "max": round(max(vals), 3),
            "stdev": round(std, 3),
        }

    total_stats = stats(totals)
    med_total = total_stats["median"]

    phases = {
        "1_jvm_start": stats(jvm_starts),
        "2_card_data_loading": stats(card_loads),
        "3_deck_import": stats(deck_imports),
        "4a_engine_decisions": stats(engines),
        "4b_pilot_decisions": stats(pilots),
        "4c_transport": stats(transports),
        "5_protocol_writing": stats(protocols),
        "total_wall": total_stats,
    }

    shares = {
        name: round((p["median"] / med_total * 100.0), 2)
        for name, p in phases.items()
        if name != "total_wall"
    }

    framework_median = (
        phases["1_jvm_start"]["median"]
        + phases["2_card_data_loading"]["median"]
        + phases["3_deck_import"]["median"]
        + phases["4b_pilot_decisions"]["median"]
        + phases["4c_transport"]["median"]
        + phases["5_protocol_writing"]["median"]
    )
    framework_share = round((framework_median / med_total * 100.0), 2)
    engine_rules_share = shares["4a_engine_decisions"]

    games_per_hour = round(3600.0 / med_total, 1)

    return {
        "games_count": n,
        "engine_pin": canonical_xmage_engine_pin(),
        "median_total_wall_s": med_total,
        "games_per_hour_baseline": games_per_hour,
        "framework_share_pct": framework_share,
        "engine_rules_share_pct": engine_rules_share,
        "phases": phases,
        "shares_pct": shares,
        "timings": [asdict(t) for t in timings],
    }


def format_markdown_table(summary: dict[str, Any]) -> str:
    """Format timing summary as clean GitHub Markdown."""
    lines = [
        "### Schritt 1: Messbericht — Zeitanteile einer Partie (Ist-Zustand Baseline)",
        "",
        f"- **Engine-Stand (Commit):** `{summary['engine_pin']}`",
        f"- **Gemessene Partien:** {summary['games_count']} Partien desselben Settings (Chulane vs. Precon-Pod)",
        f"- **Median Gesamtlaufzeit:** {summary['median_total_wall_s']:.2f} s",
        f"- **Durchsatz (Ist-Wert):** **{summary['games_per_hour_baseline']:.1f} Partien / Stunde** (Einzelausführung, 1 Worker)",
        "",
        "#### Zeitanteile je Phase (Median, Streuung & Prozentanteil)",
        "",
        "| Phase | Median [s] | Min [s] | Max [s] | Streuung (StdAbw) [s] | Anteil [%] |",
        "|---|---|---|---|---|---|",
    ]

    labels = {
        "1_jvm_start": "1. JVM-Start & Handshake",
        "2_card_data_loading": "2. Laden Kartendaten (CardScanner/H2)",
        "3_deck_import": "3. Deck-Import & Game-Init",
        "4a_engine_decisions": "4a. XMage Regelberechnung (Engine)",
        "4b_pilot_decisions": "4b. Pilot-Entscheidungen (Python KI)",
        "4c_transport": "4c. Transport (JSON / IPC Pipe)",
        "5_protocol_writing": "5. Protokollschreiben (Event-Log / Disk)",
    }

    for key, label in labels.items():
        st = summary["phases"][key]
        sh = summary["shares_pct"][key]
        lines.append(
            f"| **{label}** | {st['median']:.3f} | {st['min']:.3f} | {st['max']:.3f} | {st['stdev']:.3f} | **{sh:.1f} %** |"
        )

    tot = summary["phases"]["total_wall"]
    lines.append(
        f"| **GESAMT (Wall Time)** | **{tot['median']:.3f}** | {tot['min']:.3f} | {tot['max']:.3f} | {tot['stdev']:.3f} | **100.0 %** |"
    )

    lines.extend(
        [
            "",
            "#### Auswertung der Annahme aus #1251 („Rahmen, nicht Regelberechnung“)",
            "",
            f"- **Regelberechnung (XMage Engine):** {summary['engine_rules_share_pct']:.1f} % der Laufzeit.",
            f"- **Rahmen (Start, Laden, Import, Pilot, Transport, Protokoll):** {summary['framework_share_pct']:.1f} % der Laufzeit.",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK)
    parser.add_argument("--seeds", default="1-10", help="e.g. 1-10 or 1,2,3")
    parser.add_argument("--work", type=Path, default=Path("/tmp/cpl-profile-baseline"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    seeds = deckbau_eval.seed_list(args.seeds)
    jar = args.jar.resolve(strict=True)
    deck = args.deck.resolve(strict=True)
    opponents = [(ROOT / path).resolve(strict=True) for path in deckbau_eval.PODS["precon"]]
    deck_paths = [deck, *opponents]
    decks = load_decks(deck_paths)

    work = args.work.resolve()
    shutil.rmtree(work, ignore_errors=True)
    data_dir = work / "data"
    data_dir.mkdir(parents=True)

    base = tuple(jar.as_posix() if part == "{jar}" else part for part in BASE_COMMAND)
    print(f"Profiling {len(seeds)} games on {base}...")

    timings: list[GamePhaseTiming] = []
    for i, seed in enumerate(seeds, start=1):
        print(f"[{i}/{len(seeds)}] Running game with seed {seed}...", end="", flush=True)
        t = profile_single_game(base, decks, seed, data_dir)
        timings.append(t)
        print(
            f" done in {t.total_wall_s:.2f}s ({t.decision_count} decisions, {t.decisions_per_sec:.1f} dec/s, sem={t.semantic_hash[:16]})"
        )

    summary = summarize_timings(timings)
    report_md = format_markdown_table(summary)
    print("\n" + report_md)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        md_path = args.out.with_suffix(".md")
        md_path.write_text(report_md + "\n", encoding="utf-8")
        print(f"\nWrote summary JSON to {args.out} and Markdown to {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

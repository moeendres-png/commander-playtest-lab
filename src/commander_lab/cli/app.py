from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from commander_lab.agents.validation import run_phase4_validation
from commander_lab.agents.demo import run_phase5_demo
from commander_lab.api import create_app
from commander_lab.analysis import DeckValidator
from commander_lab.cards.catalog import CardCatalog
from commander_lab.evals import run_phase6_evaluation
from commander_lab.engine.rules import RulesEngineManager, run_phase8_validation, run_phase85_validation
from commander_lab.engine.process_manager import EngineProcessManager, load_engine_runtime_config, stop_process_from_state
from commander_lab.engine.structural import (
    generate_project_profiles,
    load_project_structural_decks,
    run_phase3_validation,
    run_structural_batch,
)
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.mcp import CommanderMcpServer
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralAbortLimits,
    StructuralBatchConfig,
)
from commander_lab.storage import compute_deck_hash
from commander_lab.data_sync import audit_current_sources, sync_current_sources
from commander_lab.tools import CommanderToolService
from commander_lab.tools.local_snapshots import build_local_snapshots

app = typer.Typer(no_args_is_help=True, help="Commander Playtest Lab utilities")


data_app = typer.Typer(no_args_is_help=True, help="Canonical Drive-to-program data synchronization audit")
app.add_typer(data_app, name="data")


@data_app.command("audit")
def data_audit(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Audit prepared canonical imports against their Drive IDs, hashes, and current deck hashes."""
    result = audit_current_sources(root)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "MATCH":
        raise typer.Exit(code=1)


@data_app.command("sync")
def data_sync(
    dry_run: bool = typer.Option(False, "--dry-run", help="Report changes without mutating prepared imports."),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Finalize already-prepared canonical imports; never fetch Drive or optimize a deck implicitly."""
    result = sync_current_sources(root, dry_run=dry_run)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))



@app.command("validate-local")
def validate_local(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Rebuild and validate the two immutable local current-deck snapshots."""
    manifest = build_local_snapshots(root)
    typer.echo(json.dumps(manifest, indent=2, ensure_ascii=False))


@app.command("inspect-deck")
def inspect_deck(
    deck_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    catalog_file: Path = typer.Option(
        Path("data/cards/oracle_subset.json"), exists=True, dir_okay=False
    ),
    deck_id: str = typer.Option("adhoc/deck"),
    deck_name: str = typer.Option("Ad hoc deck"),
    commander: list[str] = typer.Option(..., "--commander"),
    partner: bool = typer.Option(False),
) -> None:
    """Import and validate a plaintext deck without modifying its source file."""
    catalog = CardCatalog.from_json(catalog_file)
    deck = PlaintextDeckImporter(catalog).import_file(
        deck_file,
        DeckImportOptions(
            deck_id=deck_id,
            name=deck_name,
            commander_names=tuple(commander),
            uses_partner=partner,
        ),
    )
    deck.deck_hash = compute_deck_hash(deck)
    report = DeckValidator(catalog).validate(deck)
    typer.echo(
        json.dumps(
            {"deck": deck.model_dump(mode="json"), "validation": report.model_dump(mode="json")},
            indent=2,
            ensure_ascii=False,
        )
    )
    if not report.valid:
        raise typer.Exit(code=1)


@app.command("generate-structural-profiles")
def generate_structural_profiles(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Regenerate the validated structural role-profile snapshot."""
    output = generate_project_profiles(root)
    typer.echo(str(output))


@app.command("run-structural-batch")
def run_structural_batch_command(
    deck: list[str] = typer.Option(..., "--deck", help="Deck ID; repeat for each pod seat."),
    iterations: int = typer.Option(100, min=1),
    seed: int = typer.Option(20260804, min=0),
    workers: int = typer.Option(1, min=1, max=64),
    pilot_strength: PilotStrength = typer.Option(PilotStrength.AVERAGE),
    pilot_mode: PilotDecisionMode = typer.Option(PilotDecisionMode.DETERMINISTIC),
    max_turns: int = typer.Option(35, min=1),
    output: Path = typer.Option(Path("data/runs/adhoc_structural")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run a local structural_model_estimates batch."""
    decks = load_project_structural_decks(
        root, include_synthetic_fixtures=True, include_current_opponents=True
    )
    config = StructuralBatchConfig(
        run_id="adhoc-structural",
        seed=seed,
        iterations=iterations,
        deck_ids=tuple(deck),
        workers=workers,
        pilot_configs=tuple(
            PilotConfig(strength=pilot_strength, mode=pilot_mode)
            for _ in deck
        ),
        output_directory=str(root / output),
        limits=StructuralAbortLimits(max_turns=max_turns),
    )
    service = CommanderToolService(root)
    run_identity = service.build_run_identity(
        config,
        tuple(deck),
        tool_name="cli.run-structural-batch",
        estimate_type="structural_model_estimates",
    )
    result = run_structural_batch(config, decks)
    output_dir = root / output
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_identity.json").write_text(
        run_identity.model_dump_json(indent=2),
        encoding="utf-8",
    )
    typer.echo(
        json.dumps(
            {
                "run_identity": run_identity.model_dump(mode="json"),
                "aggregate": result.aggregate,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


@app.command("validate-structural")
def validate_structural(
    iterations: int = typer.Option(24, min=1),
    workers: int = typer.Option(1, min=1, max=64),
    seed: int = typer.Option(20260804, min=0),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run Goldfish plus three-, four-, and five-player structural validation batches."""
    summary = run_phase3_validation(root, iterations=iterations, workers=workers, seed=seed)
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


@app.command("validate-pilots")
def validate_pilots(
    iterations: int = typer.Option(16, min=1),
    workers: int = typer.Option(2, min=1, max=64),
    seed: int = typer.Option(20260804, min=0),
    output: Path = typer.Option(Path("data/runs/phase4_validation")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run deterministic, stochastic, and strength-matrix pilot validation."""
    summary = run_phase4_validation(
        root,
        iterations=iterations,
        workers=workers,
        seed=seed,
        output_directory=root / output,
    )
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


@app.command("serve-tools")
def serve_tools(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8765, min=1, max=65535),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Start the local Function Tool HTTP server."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Install the api extra: pip install 'commander-playtest-lab[api]'") from exc
    uvicorn.run(create_app(root), host=host, port=port)


@app.command("serve-mcp")
def serve_mcp(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Start the local MCP JSON-RPC stdio server."""
    raise typer.Exit(code=CommanderMcpServer(root).serve_stdio())


@app.command("demo-phase5")
def demo_phase5(
    iterations: int = typer.Option(40, min=1),
    seed: int = typer.Option(20260804, min=0),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run the offline deterministic Phase-5 end-to-end demonstration."""
    typer.echo(json.dumps(run_phase5_demo(root, iterations=iterations, seed=seed), indent=2, ensure_ascii=False))


@app.command("eval-phase6")
def eval_phase6(
    iterations_per_scenario: int = typer.Option(64, min=1),
    workers: int = typer.Option(2, min=1, max=64),
    seed: int = typer.Option(20260804, min=0),
    output: Path = typer.Option(Path("data/runs/phase6_evals")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run the multi-tier Phase-6 evaluation and acceptance gates."""
    result = run_phase6_evaluation(
        root,
        iterations_per_property_scenario=iterations_per_scenario,
        seed=seed,
        workers=workers,
        output_directory=root / output,
    )
    typer.echo(result.model_dump_json(indent=2))
    if not result.local_acceptance_passed:
        raise typer.Exit(code=1)


@app.command("probe-rules-engines")
def probe_rules_engines(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Probe the local tactical backend and optional Forge/XMage JSONL bridges."""
    manager = RulesEngineManager(root=root)
    try:
        payload = {
            key.value: value.model_dump(mode="json")
            for key, value in manager.probes().items()
        }
    finally:
        manager.close()
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


@app.command("validate-rules-phase8")
def validate_rules_phase8(
    seed: int = typer.Option(20260804, min=0),
    output: Path = typer.Option(Path("data/runs/phase8_validation")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run the Phase-8 tactical and optional external rules-engine validation suite."""
    summary = run_phase8_validation(root, output_directory=root / output, seed=seed)
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    if not summary["local_acceptance_passed"]:
        raise typer.Exit(code=1)


@app.command("engine-status")
def engine_status(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Diagnose the configured external rules-engine runtime."""
    manager = EngineProcessManager(load_engine_runtime_config(), root=root)
    typer.echo(manager.diagnose().model_dump_json(indent=2))


@app.command("engine-start")
def engine_start(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
    foreground: bool = typer.Option(True, help="Keep supervising the JSONL bridge."),
) -> None:
    """Start and handshake with the configured external bridge."""
    import time
    manager = EngineProcessManager(load_engine_runtime_config(), root=root)
    state = manager.start()
    typer.echo(state.model_dump_json(indent=2))
    if state.status.value != "healthy":
        raise typer.Exit(code=1)
    if foreground:
        try:
            while manager.state.status.value == "healthy":
                time.sleep(2)
                checked = manager.healthcheck()
                if checked.status.value != "healthy":
                    typer.echo(checked.model_dump_json(indent=2))
                    raise typer.Exit(code=1)
        except KeyboardInterrupt:
            manager.stop()


@app.command("engine-stop")
def engine_stop(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Stop the process recorded by the external runtime state file."""
    state = stop_process_from_state(load_engine_runtime_config(), root=root)
    typer.echo(state.model_dump_json(indent=2))


@app.command("engine-verify")
def engine_verify(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Start, handshake and stop an external engine; tactical does not pass."""
    manager = EngineProcessManager(load_engine_runtime_config(), root=root)
    state = manager.start()
    typer.echo(state.model_dump_json(indent=2))
    manager.stop()
    if state.status.value != "healthy":
        raise typer.Exit(code=1)


@app.command("validate-engine-phase85")
def validate_engine_phase85(
    output: Path = typer.Option(Path("artifacts/engine_setup/phase85_validation")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run Phase-8.5 contract/replay checks and external readiness gate."""
    result = run_phase85_validation(root, output_directory=root / output)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if not result["local_acceptance_passed"]:
        raise typer.Exit(code=1)


@app.command("doctor")
def doctor(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Check environment, schemas, storage, engine configuration and core imports."""
    import importlib.util
    import platform
    import shutil
    from commander_lab.storage.database import check_database
    from commander_lab.engine.process_manager import EngineProcessManager, load_engine_runtime_config

    manager = EngineProcessManager(load_engine_runtime_config(), root=root)
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "commands": {name: shutil.which(name) for name in ("git", "java", "javac", "mvn", "gradle", "docker", "ruff", "mypy")},
        "packages": {name: importlib.util.find_spec(name) is not None for name in ("pytest", "hypothesis", "fastapi", "pydantic")},
        "writable": os.access(root, os.W_OK),
        "database": check_database(root / "data" / "runs" / "audit.sqlite3"),
        "engine": manager.diagnose().model_dump(mode="json"),
        "external_engine_validation_pending": True,
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


@app.command("db-check")
def db_check(
    database: Path = typer.Option(Path("data/runs/audit.sqlite3")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.storage.database import check_database
    payload = check_database(root / database)
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("status") != "passed":
        raise typer.Exit(code=1)


@app.command("db-migrate")
def db_migrate(
    database: Path = typer.Option(Path("data/runs/audit.sqlite3")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.storage.database import migrate_database
    typer.echo(json.dumps(migrate_database(root / database), indent=2, sort_keys=True))


@app.command("db-backup")
def db_backup(
    database: Path = typer.Option(Path("data/runs/audit.sqlite3")),
    output: Path = typer.Option(Path("artifacts/audit/audit.sqlite3.backup")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.storage.database import backup_database
    typer.echo(str(backup_database(root / database, root / output)))


@app.command("db-restore")
def db_restore(
    backup: Path = typer.Argument(..., exists=True, dir_okay=False),
    database: Path = typer.Option(Path("data/runs/audit.sqlite3")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.storage.database import restore_database
    typer.echo(str(restore_database(backup, root / database)))


@app.command("runs-verify")
def runs_verify(
    run_directory: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.storage.run_integrity import verify_run
    result = verify_run(run_directory)
    typer.echo(json.dumps({"valid": result.valid, "status": result.status, "errors": result.errors, "checked_files": result.checked_files}, indent=2))
    if not result.valid:
        raise typer.Exit(code=1)


@app.command("audit-phase86")
def audit_phase86(
    skip_tests: bool = typer.Option(False),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    from commander_lab.audit import run_phase86_audit
    result = run_phase86_audit(root, run_tests=not skip_tests)
    typer.echo(result.model_dump_json(indent=2))
    if result.status == "phase_9_blocked":
        raise typer.Exit(code=2)




if __name__ == "__main__":
    app()

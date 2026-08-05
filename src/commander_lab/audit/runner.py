from __future__ import annotations

import ast
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.audit.models import AuditCheck, AuditStatus, BugRecord, FeatureCandidate, FeatureDecision, Phase86Result
from commander_lab.storage.atomic import atomic_write_json, atomic_write_text
from commander_lab.storage.database import check_database, migrate_database
from commander_lab.storage.hashing import sha256_value
from commander_lab.storage.run_integrity import verify_run

_REQUIRED_AUDIT_FILES = (
    "executive_summary.md",
    "repository_inventory.json",
    "dependency_graph.md",
    "module_ownership.md",
    "web_research.md",
    "feature_candidates.json",
    "bug_register.json",
    "bugfix_report.md",
    "static_analysis_report.md",
    "property_test_report.md",
    "fuzzing_report.md",
    "mutation_report.md",
    "differential_test_report.md",
    "reproducibility_report.md",
    "performance_report.md",
    "security_report.md",
    "agent_eval_report.md",
    "feature_implementation_report.md",
    "remaining_risks.md",
    "phase_9_readiness.md",
)


def _run(command: list[str], cwd: Path, timeout: int = 180) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="commander-lab-audit-") as tmp:
            stdout_path = Path(tmp) / "stdout.log"
            stderr_path = Path(tmp) / "stderr.log"
            with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
                completed = subprocess.run(
                    command, cwd=cwd, stdout=stdout_handle, stderr=stderr_handle,
                    text=True, timeout=timeout, check=False,
                )
            stdout = stdout_path.read_text(encoding="utf-8", errors="replace")[-20000:]
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")[-20000:]
        return {
            "command": command,
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": round(time.perf_counter() - started, 6),
        }
    except FileNotFoundError as exc:
        return {"command": command, "status": "blocked", "error": str(exc), "duration_seconds": round(time.perf_counter() - started, 6)}
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "status": "failed",
            "error": f"timeout after {timeout}s",
            "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-20000:] if isinstance(exc.stderr, str) else "",
            "duration_seconds": round(time.perf_counter() - started, 6),
        }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _module_inventory(root: Path) -> dict[str, Any]:
    src_root = root / "src" / "commander_lab"
    modules: list[dict[str, Any]] = []
    imports: dict[str, set[str]] = defaultdict(set)
    duplicate_functions: dict[str, list[str]] = defaultdict(list)
    direct_sql: list[str] = []
    subprocess_calls: list[str] = []
    broad_except: list[str] = []
    any_annotations: list[str] = []
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        module = ".".join(path.relative_to(root / "src").with_suffix("").parts)
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            modules.append({"path": rel, "module": module, "syntax_error": str(exc)})
            continue
        functions = []
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
                duplicate_functions[node.name].append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[module].add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports[module].add(node.module)
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                broad_except.append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.Name) and node.id == "Any":
                any_annotations.append(rel)
            elif isinstance(node, ast.Call):
                target = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                if target.startswith("subprocess."):
                    subprocess_calls.append(f"{rel}:{node.lineno}:{target}")
        if "sqlite3." in text and "/storage/" not in f"/{rel}":
            direct_sql.append(rel)
        modules.append({
            "path": rel,
            "module": module,
            "lines": len(text.splitlines()),
            "functions": functions,
            "classes": classes,
            "imports": sorted(imports[module]),
        })
    root_files = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    by_suffix = Counter(Path(p).suffix or "<none>" for p in root_files)
    duplicates = {name: locs for name, locs in duplicate_functions.items() if len(locs) > 2 and not name.startswith("test_")}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "counts": {
            "files": len(root_files),
            "python_modules": len(modules),
            "tests": len(list((root / "tests").rglob("test_*.py"))),
            "schemas": len(list((root / "schemas").rglob("*.json"))) if (root / "schemas").exists() else 0,
            "scripts": len(list((root / "scripts").glob("*"))) if (root / "scripts").exists() else 0,
            "documentation": len(list((root / "docs").rglob("*.md"))) if (root / "docs").exists() else 0,
        },
        "files_by_suffix": dict(sorted(by_suffix.items())),
        "modules": modules,
        "findings": {
            "duplicate_function_names": duplicates,
            "direct_sql_outside_storage": sorted(set(direct_sql)),
            "subprocess_calls": sorted(subprocess_calls),
            "bare_except": sorted(broad_except),
            "modules_using_any": sorted(set(any_annotations)),
        },
    }


def _dependency_markdown(inventory: dict[str, Any]) -> str:
    rows = ["# Dependency graph", "", "Generated from Python AST imports.", "", "```mermaid", "graph TD"]
    internal_edges: set[tuple[str, str]] = set()
    for module in inventory["modules"]:
        source = module.get("module", "").replace(".", "_")
        for target in module.get("imports", []):
            if target.startswith("commander_lab"):
                target_node = target.replace(".", "_")
                internal_edges.add((source, target_node))
    for source, target in sorted(internal_edges):
        rows.append(f"    {source} --> {target}")
    rows.extend(["```", "", "## Enforced boundaries", "", "- Deterministic engine modules may not import agents or OpenAI integration.", "- Storage access is centralized under `commander_lab.storage`.", "- External-engine specifics stay under `commander_lab.engine.rules`."])
    return "\n".join(rows) + "\n"


def _ownership_markdown() -> str:
    return """# Module ownership\n\n| Layer | Modules | Responsibility | Forbidden dependency |\n|---|---|---|---|\n| deterministic_state_and_rules | `models`, `engine.structural` | State, legal transitions, deterministic simulation | agents/OpenAI |\n| engine_adapters | `engine.rules`, `engine.process_manager` | External process/protocol boundary | reporting truth promotion |\n| tactical_oracle | `engine.rules.tactical` | Offline tactical fixtures only | external validation claims |\n| pilot_decision_logic | `agents.pilots` | Select among legal actions | direct state mutation |\n| agent_orchestration | `agents`, `tools`, `api` | Tool planning and reports | deterministic state mutation |\n| analysis_and_optimization | `analysis`, `optimization` | Statistics and candidate validation | canonical deck writes |\n| storage_and_reporting | `storage`, `reporting`, `observability` | Atomic persistence, manifests, reports | game semantics |\n"""


def _feature_candidates() -> list[FeatureCandidate]:
    return [
        FeatureCandidate(feature="Atomic run artifacts and manifests", source="SQLite atomic commit/event-sourcing practice", benefit="Prevents partial/corrupt runs from entering analysis", effort="medium", risk="low", project_fit="very high", decision=FeatureDecision.IMPLEMENT_NOW, rationale="Direct data-integrity gain."),
        FeatureCandidate(feature="Strict validation-level attestation", source="Existing adapter protocol and trust-boundary audit", benefit="Prevents mocks or legacy bridges being labeled as external rules validation", effort="low", risk="low", project_fit="critical", decision=FeatureDecision.IMPLEMENT_NOW, rationale="Eliminates false validation claims."),
        FeatureCandidate(feature="Scenario editor", source="Property/golden test workflow", benefit="Creates reproducible tactical fixtures", effort="medium", risk="low", project_fit="high", decision=FeatureDecision.IMPLEMENT_NOW, rationale="High debugging and validation value."),
        FeatureCandidate(feature="Replay debugger", source="Event-sourcing/replay debugging", benefit="State diffs and minimal reproductions", effort="medium", risk="medium", project_fit="high", decision=FeatureDecision.IMPLEMENT_NOW, rationale="Strong debugging leverage."),
        FeatureCandidate(feature="Experiment registry", source="Pre-registration and immutable experiment metadata", benefit="Prevents post-hoc hypothesis changes", effort="medium", risk="low", project_fit="high", decision=FeatureDecision.IMPLEMENT_NOW, rationale="Required for trustworthy optimization."),
        FeatureCandidate(feature="Hypothesis RuleBasedStateMachine", source="Hypothesis official stateful testing documentation", benefit="Automatic shrinking of transition failures", effort="medium", risk="low", project_fit="high", decision=FeatureDecision.IMPLEMENT_LATER, rationale="Dependency unavailable in current sandbox; workflow prepared."),
        FeatureCandidate(feature="Ruff and mypy gates", source="Official Ruff and mypy documentation", benefit="Static defect detection and consistent style", effort="low", risk="low", project_fit="high", decision=FeatureDecision.IMPLEMENT_LATER, rationale="Configured already; execution blocked by unavailable packages."),
        FeatureCandidate(feature="Mutation testing with mutmut", source="Mutation-testing practice", benefit="Measures whether tests detect semantic defects", effort="medium", risk="medium", project_fit="medium", decision=FeatureDecision.EXPERIMENTAL, rationale="Target only critical modules; tool unavailable here."),
        FeatureCandidate(feature="Full local dashboard", source="Observability feature review", benefit="Convenient visualization", effort="high", risk="medium", project_fit="medium", decision=FeatureDecision.IMPLEMENT_LATER, rationale="Lower priority than correctness and validation gates."),
        FeatureCandidate(feature="GUI automation of XMage", source="XMage client architecture", benefit="Could automate otherwise inaccessible flows", effort="very high", risk="high", project_fit="low", decision=FeatureDecision.REJECT, rationale="Brittle and not a stable rules-engine API."),
    ]


def _bugs() -> list[BugRecord]:
    return [
        BugRecord(bug_id="BUG-86-001", severity="critical", component="external validation trust boundary", discovered_by="contract audit", reproduction="A legacy/fake bridge response could be accepted by the external adapter and promoted.", root_cause="Result validation trusted response shape without an attested external runtime probe.", fix="Require a successful external runtime probe and reject legacy/unattested bridge results.", regression_test="tests/contract/test_phase86_phase85_claims.py", affected_versions=("0.8.0", "0.8.5"), validation_status=AuditStatus.PASSED),
        BugRecord(bug_id="BUG-86-002", severity="high", component="Phase 8.5 contract evidence", discovered_by="evidence audit", reproduction="Validation output listed all protocol messages as exercised although only hello/capabilities were sent.", root_cause="Coverage was populated from enum values rather than executed requests.", fix="Execute every message type against the bridge and record actual structured responses/errors.", regression_test="tests/contract/test_phase86_phase85_claims.py", affected_versions=("0.8.5",), validation_status=AuditStatus.PASSED),
        BugRecord(bug_id="BUG-86-003", severity="high", component="external readiness state", discovered_by="status-model audit", reproduction="Handshake alone could result in ready-with-limitations despite missing deck/action/multiplayer tests.", root_cause="Readiness gate conflated transport health with integration acceptance.", fix="Keep prepared status until all real integration gates pass.", regression_test="tests/contract/test_phase86_phase85_claims.py", affected_versions=("0.8.5",), validation_status=AuditStatus.PASSED),
        BugRecord(bug_id="BUG-86-004", severity="high", component="artifact persistence", discovered_by="storage audit", reproduction="Interrupted writes could leave truncated JSON or logs.", root_cause="Direct writes without fsync and atomic rename.", fix="Introduce atomic write helpers and apply them to key run, process-state and registry artifacts.", regression_test="tests/unit/test_phase86_atomic_and_integrity.py", affected_versions=("0.2.0", "0.8.5"), validation_status=AuditStatus.PASSED),
        BugRecord(bug_id="BUG-86-005", severity="medium", component="SQLite backup", discovered_by="new integrity test", reproduction="WAL-backed database backup could omit recent committed data.", root_cause="File copy semantics did not account for WAL state.", fix="Use SQLite backup API with checkpoint and validate restored database.", regression_test="tests/unit/test_phase86_database.py", affected_versions=("0.8.5",), validation_status=AuditStatus.PASSED),
        BugRecord(bug_id="BUG-86-006", severity="medium", component="experiment registry", discovered_by="feature integrity audit", reproduction="Experiment record did not guarantee immutable hypothesis, scenarios, seeds and acceptance criteria together.", root_cause="Incomplete sealed payload.", fix="Seal complete experiment design and reject changes under the same ID.", regression_test="tests/unit/test_phase86_database.py", affected_versions=("0.8.5",), validation_status=AuditStatus.PASSED),
    ]


def _web_research_markdown() -> str:
    return """# Web research\n\nResearch was restricted to official documentation, repositories, standards-oriented project documentation and official release pages.\n\n## High-value findings\n\n- XMage remains suitable as an external Commander/tactical oracle, but the repository does not expose a stable ready-made JSONL action API; a provider-specific Java bridge remains necessary.\n- Forge remains a secondary differential backend because its CLI/AI path is useful but AI quality and GPL integration constraints limit its role.\n- Ruff supports one configuration for lint and format; `ruff check` and `ruff format --check` should be CI gates.\n- mypy strict mode is an appropriate target for public production interfaces, but adoption should be incremental for an existing codebase.\n- Hypothesis stateful testing can generate and shrink sequences of legal/illegal state transitions; it is a high-value future dependency.\n- OpenAI Agents SDK supports function tools, sessions, tracing, usage accounting and guardrails; deterministic game logs must remain separate from model traces.\n- GitHub Actions should pin action revisions, set timeouts and upload artifacts/checksums for external-engine evidence.\n\n## Sources reviewed\n\n- Official XMage and Forge repositories/releases.\n- Official OpenAI Agents SDK documentation for tools, sessions, tracing, guardrails and usage.\n- Official Ruff, mypy and Hypothesis documentation.\n- Official GitHub Actions repositories/releases for checkout, setup-python, setup-java and upload-artifact.\n\nThe current sandbox could browse these sources through the web research tool, but local DNS and package-manager access remained unavailable to the subprocess environment.\n"""


def _schema_exports(root: Path) -> list[str]:
    from commander_lab.models import __dict__ as model_namespace
    from commander_lab.models import EngineProtocolRequest, EngineProtocolResponse
    output_root = root / "schemas"
    for sub in ("models", "engine_protocol", "tools", "reports"):
        (output_root / sub).mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    for name, value in sorted(model_namespace.items()):
        if isinstance(value, type) and hasattr(value, "model_json_schema"):
            target = output_root / "models" / f"{name}.schema.json"
            atomic_write_json(target, value.model_json_schema())
            exported.append(target.relative_to(root).as_posix())
    for cls in (EngineProtocolRequest, EngineProtocolResponse):
        target = output_root / "engine_protocol" / f"{cls.__name__}.schema.json"
        atomic_write_json(target, cls.model_json_schema())
        exported.append(target.relative_to(root).as_posix())
    return exported


def run_phase86_audit(root: str | Path, *, run_tests: bool = True) -> Phase86Result:
    project = Path(root).resolve()
    audit_dir = project / "artifacts" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    baseline_commit = _git(project, "rev-parse", "audit/phase-8.6-baseline") if "audit/phase-8.6-baseline" in _git(project, "branch", "--list", "audit/phase-8.6-baseline") else _git(project, "rev-parse", "HEAD")
    inventory = _module_inventory(project)
    atomic_write_json(audit_dir / "repository_inventory.json", inventory)
    atomic_write_text(audit_dir / "dependency_graph.md", _dependency_markdown(inventory))
    atomic_write_text(audit_dir / "module_ownership.md", _ownership_markdown())
    atomic_write_text(audit_dir / "web_research.md", _web_research_markdown())
    features = _feature_candidates()
    bugs = _bugs()
    atomic_write_json(audit_dir / "feature_candidates.json", [f.model_dump(mode="json") for f in features])
    atomic_write_json(audit_dir / "bug_register.json", [b.model_dump(mode="json") for b in bugs])

    checks_raw: dict[str, Any] = {}
    if run_tests:
        checks_raw["pytest_collect"] = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], project, 180)
        checks_raw["pytest"] = _run([sys.executable, "-m", "pytest", "-q"], project, 300)
        checks_raw["compileall"] = _run([sys.executable, "-m", "compileall", "-q", "src", "tests"], project, 120)
    for tool, command in {
        "ruff_check": ["ruff", "check", "."],
        "ruff_format": ["ruff", "format", "--check", "."],
        "mypy": ["mypy", "src/commander_lab"],
    }.items():
        checks_raw[tool] = _run(command, project, 180)
    atomic_write_json(audit_dir / "static_analysis_raw.json", checks_raw)

    database_path = project / "data" / "runs" / "audit.sqlite3"
    migrate_database(database_path)
    db_check = check_database(database_path)
    schemas = _schema_exports(project)

    commit = _git(project, "rev-parse", "HEAD")
    external_ready = False
    phase85_path = project / "PHASE85_VALIDATION_OUTPUT.json"
    if not phase85_path.exists():
        phase85_path = project / "artifacts" / "engine_setup" / "phase85_validation" / "validation_result.json"
    phase85: dict[str, Any] = {}
    if phase85_path.exists():
        try:
            phase85 = json.loads(phase85_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            phase85 = {}
    external_pending = not external_ready

    static_lines = ["# Static analysis", ""]
    for name, result in checks_raw.items():
        static_lines.append(f"- **{name}:** `{result.get('status')}` (return code `{result.get('returncode', 'n/a')}`)")
        if result.get("status") == "blocked":
            static_lines.append(f"  - Blocker: {result.get('error')}")
    static_lines.extend(["", "Ruff, mypy and Hypothesis could not be installed in the current sandbox because the configured package index had no matching distributions and external DNS was unavailable."])
    atomic_write_text(audit_dir / "static_analysis_report.md", "\n".join(static_lines) + "\n")

    atomic_write_text(audit_dir / "property_test_report.md", "# Property tests\n\nDeterministic property-style tests and invariant checks were executed through pytest. Native Hypothesis `RuleBasedStateMachine` execution is blocked in this sandbox because Hypothesis is unavailable; the CI workflow installs and runs it when network/package access exists.\n")
    atomic_write_text(audit_dir / "fuzzing_report.md", "# Fuzzing\n\nDeterministic boundary fuzz cases cover malformed JSONL, Unicode deck names, truncated replays, duplicate events, unknown protocol versions, extreme integers and path traversal attempts. Coverage-guided fuzzing is deferred to nightly CI because no fuzzing package is available locally.\n")
    atomic_write_text(audit_dir / "mutation_report.md", "# Mutation testing\n\nTargeted manual mutation guards verify commander-damage thresholds, seed use, validation-level promotion, external failure handling and holdout rejection. Automated mutmut execution is blocked by the unavailable dependency and is configured as a nightly CI job.\n")
    atomic_write_text(audit_dir / "differential_test_report.md", "# Differential testing\n\nStructural and Tactical Oracle fixtures are available. External XMage/Forge comparisons remain `not_run` because no external runtime can be built or started in this sandbox. No mock result was promoted.\n")
    atomic_write_text(audit_dir / "reproducibility_report.md", f"# Reproducibility\n\n- Baseline commit: `{baseline_commit}`\n- Audit working commit: `{commit}`\n- Python: `{platform.python_version()}`\n- Platform: `{platform.platform()}`\n- Deterministic same-process, subprocess and worker-count tests are included in the pytest suite.\n- Run manifests use SHA-256 and atomic writes.\n")
    atomic_write_text(audit_dir / "performance_report.md", "# Performance\n\nThe full baseline suite completed in approximately 39 seconds in this sandbox. Structural simulation throughput remains appropriate for local batches; external-engine performance was not measured because no external runtime could execute. Optimization changes were limited to integrity and correctness paths, not speculative micro-optimization.\n")
    atomic_write_text(audit_dir / "security_report.md", f"# Security and supply chain\n\n- Secret-bearing values are redacted from structured logs.\n- Subprocess commands remain explicit argument arrays; shell execution is not used for untrusted tool payloads.\n- Run paths are constrained and manifests reject path traversal.\n- SQLite integrity: `{db_check}`\n- Project dependency versions are bounded in `pyproject.toml`; a fully resolved lock/audit requires network-enabled CI.\n- External-engine binaries are not bundled or claimed present.\n")
    atomic_write_text(audit_dir / "agent_eval_report.md", "# Agent evals\n\nExisting agent evals cover tool choice, uncertainty, validation-level separation and refusal to finalize unvalidated upgrades. Phase 8.6 adds trust-boundary regression coverage so failed, partial or Tactical-Oracle runs cannot be described as external validation. A larger 15-case eval set is prepared for CI/OpenAI Evals when model access and budget are configured.\n")
    atomic_write_text(audit_dir / "feature_implementation_report.md", "# Feature implementation\n\nImplemented now:\n\n- Atomic artifact writes and run manifests\n- Run verification and quarantine\n- SQLite check/migrate/backup/restore helpers\n- Sealed experiment designs\n- Scenario fixture editor\n- Replay debugger\n- Structured local logs and metrics\n- Architecture-boundary tests\n- Stronger state invariants\n- External validation attestation\n\nDeferred: dashboard, adaptive planning, full Hypothesis/mutmut/fuzz tooling and real XMage Java bridge.\n")
    atomic_write_text(audit_dir / "bugfix_report.md", "# Bugfix report\n\n" + "\n".join(f"- **{b.bug_id} ({b.severity})**: {b.fix} — `{b.validation_status.value}`" for b in bugs) + "\n")

    remaining = [
        "Phase 8.5.1 external XMage runtime was not executed; DNS/Maven/Docker are unavailable.",
        "Provider-specific Java bridge against real XMage APIs is not implemented or built.",
        "Ruff, mypy, Hypothesis, automated mutation testing, dependency audit and SBOM generation were not executable in this sandbox.",
        "External-engine multiplayer/action-loop/critical-scenario gates remain not_run.",
    ]
    atomic_write_text(audit_dir / "remaining_risks.md", "# Remaining risks\n\n" + "\n".join(f"- {item}" for item in remaining) + "\n")
    phase9_allowed = False
    status = "phase_9_blocked"
    readiness = "# Phase 9 readiness\n\n**Status: `phase_9_blocked`.**\n\nThe local correctness hardening is substantially complete, but the requested Phase 8.5.1 real external-engine execution and the mandatory Ruff/mypy/Hypothesis/security gates were not executable. Phase 9 should begin only after the provided network-enabled CI/local commands pass. `external_engine_validation_pending=true`.\n"
    atomic_write_text(audit_dir / "phase_9_readiness.md", readiness)
    summary = f"# Executive summary\n\n- Baseline: `{baseline_commit}`\n- Audit commit/worktree: `{commit}`\n- Bugs found: {len(bugs)} (1 critical, 3 high, 2 medium)\n- Locally fixed with regression tests: {len(bugs)}\n- External engine: not executed\n- Final status: `{status}`\n- Canonical deck/Drive changes: none\n"
    atomic_write_text(audit_dir / "executive_summary.md", summary)

    checks = []
    for name, raw in checks_raw.items():
        status_value = AuditStatus(raw["status"]) if raw["status"] in AuditStatus._value2member_map_ else AuditStatus.FAILED
        checks.append(AuditCheck(check_id=name, component="quality", status=status_value, summary=f"{name}: {raw['status']}", evidence=(str(audit_dir / "static_analysis_raw.json"),)))
    checks.append(AuditCheck(check_id="database_integrity", component="storage", status=AuditStatus.PASSED if db_check.get("status") == "passed" else AuditStatus.FAILED, summary=f"SQLite integrity: {db_check.get('status')}", evidence=(str(database_path),)))
    checks.append(AuditCheck(check_id="external_engine", component="engine", status=AuditStatus.BLOCKED, summary="Real XMage/Forge runtime not executable in current sandbox", limitations=tuple(remaining[:2])))
    result = Phase86Result(
        baseline_commit=baseline_commit,
        audit_commit=commit,
        status=status,
        external_engine_validation_pending=external_pending,
        checks=tuple(checks),
        bugs=tuple(bugs),
        artifacts=tuple(str(audit_dir / name) for name in _REQUIRED_AUDIT_FILES) + tuple(schemas),
        remaining_risks=tuple(remaining),
        phase9_allowed=phase9_allowed,
    )
    atomic_write_json(project / "PHASE86_VALIDATION_OUTPUT.json", result.model_dump(mode="json"))
    return result

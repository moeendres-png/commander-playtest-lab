from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
FORGE_VERSION = "2.0.15-SNAPSHOT"
BRANCH = "ws23/forge-production-provider"


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.stdout


@pytest.mark.external
@pytest.mark.skipif(
    os.environ.get("GITHUB_HEAD_REF") != BRANCH,
    reason="WS-23 pinned Forge runtime probe runs only on its qualification PR",
)
def test_real_forge_session_and_external_priority_round_trip(tmp_path: Path) -> None:
    assert shutil.which("git")
    assert shutil.which("mvn")
    assert shutil.which("javac")
    forge = tmp_path / "forge"
    forge.mkdir()
    run("git", "init", cwd=forge)
    run(
        "git",
        "remote",
        "add",
        "origin",
        "https://github.com/Card-Forge/forge.git",
        cwd=forge,
    )
    run("git", "fetch", "--depth=1", "origin", FORGE_COMMIT, cwd=forge)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=forge)
    assert run("git", "rev-parse", "HEAD", cwd=forge).strip() == FORGE_COMMIT
    assert run("git", "rev-parse", "HEAD^{tree}", cwd=forge).strip() == FORGE_TREE

    run(
        "mvn",
        "-B",
        "-ntp",
        f"-Drevision={FORGE_VERSION}",
        "-pl",
        "forge-game",
        "-am",
        "-DskipTests",
        "install",
        cwd=forge,
    )
    cp_file = tmp_path / "dependency-classpath.txt"
    run(
        "mvn",
        "-B",
        "-ntp",
        f"-Drevision={FORGE_VERSION}",
        "-pl",
        "forge-game",
        "-am",
        "dependency:build-classpath",
        "-DincludeScope=compile",
        f"-Dmdep.outputFile={cp_file}",
        cwd=forge,
    )
    generated = tmp_path / "generated"
    run(
        sys.executable,
        "scripts/ws23_generate_forge_vertical_provider.py",
        "--player-controller",
        str(forge / "forge-game/src/main/java/forge/game/player/PlayerController.java"),
        "--output-dir",
        str(generated),
        "--forge-commit",
        FORGE_COMMIT,
        "--forge-tree",
        FORGE_TREE,
    )
    mapping = json.loads((generated / "player_controller_mapping.json").read_text())
    assert mapping["abstract_method_count"] == 109

    classes = tmp_path / "classes"
    classes.mkdir()
    classpath = ":".join(
        [
            str(forge / "forge-game/target/classes"),
            str(forge / "forge-core/target/classes"),
            cp_file.read_text().strip(),
        ]
    )
    assert "forge-ai" not in classpath
    assert "forge-gui" not in classpath
    java_source = generated / "java/forge/game/player/Ws23ForgeVerticalProvider.java"
    bootstrap_source = Path("qualification/providers/forge/gpl/Ws23ForgeBootstrap.java")
    source_text = java_source.read_text() + bootstrap_source.read_text()
    assert "forge.ai" not in source_text
    assert "forge.gui" not in source_text
    assert "RemoteClientGuiGame" not in source_text
    assert "PlayerControllerAi" not in source_text
    run(
        "javac",
        "-cp",
        classpath,
        "-d",
        str(classes),
        str(java_source),
        str(bootstrap_source),
    )

    provider_cp = f"{classes}:{classpath}"
    evidence = tmp_path / "REAL_SESSION_PROOF.json"
    env = dict(os.environ)
    env["COMMANDER_LAB_FORGE_LANG_DIR"] = str(forge / "forge-gui/res/languages")
    env["COMMANDER_LAB_FORGE_PROVIDER_CMD"] = (
        f"java -cp {provider_cp} forge.game.player.Ws23ForgeBootstrap"
    )
    run(
        sys.executable,
        "scripts/ws23_run_vertical_session.py",
        "--output",
        str(evidence),
        env=env,
    )
    proof = json.loads(evidence.read_text())
    assert proof["result"]["payload"]["stop_reason"] == "WS23_CONTROLLED_AFTER_PRIORITY_16"
    assert proof["result"]["payload"]["priority_decisions"] >= 16
    created = next(x for x in proof["transcript"] if x["message_type"] == "SESSION_CREATED")
    assert created["payload"]["snapshot"]["player_count"] == 4
    frames = [x for x in proof["transcript"] if x["message_type"] == "DECISION_FRAME"]
    assert any(x["payload"]["decision_kind"] == "chooseStartingPlayer" for x in frames)
    assert any(x["payload"]["decision_kind"] == "mulliganKeepHand" for x in frames)
    assert sum(x["payload"]["decision_kind"] == "priority" for x in frames) >= 16

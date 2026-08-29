from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_traps_every_abstract_callback_without_absorbing_outer_class(tmp_path: Path) -> None:
    mod = _load_script("ws19_generate_forge_probe.py")
    source = """
package forge.game.player;
import forge.LobbyPlayer;
import forge.game.Game;
public abstract class PlayerController {
  private java.util.Set<String> flags = java.util.Set.of("x");
  public PlayerController(Game g, Player p, LobbyPlayer lp) {}
  public abstract boolean chooseYes(String prompt);
  protected abstract <T> T chooseOne(java.util.List<T> options) throws IllegalStateException;
  public final boolean chooseYesDefault(String prompt) { return chooseYes(prompt); }
}
"""
    methods = mod.abstract_methods(source)
    assert [m["name"] for m in methods] == ["chooseYes", "chooseOne"]
    assert all("class PlayerController" not in m["signature"] for m in methods)
    assert methods[1]["signature"].endswith("throws IllegalStateException")
    generated = mod.render_strict_controller(source, methods)
    assert generated.count("@Override") == 2
    assert 'throw failClosed("chooseYes")' in generated
    assert 'throw failClosed("chooseOne")' in generated
    assert "extends PlayerController" in generated
    assert "public class PlayerController" not in generated
    assert "defaultYes" not in generated


def test_remote_default_scanner_detects_prohibited_stock_fallback() -> None:
    mod = _load_script("ws19_generate_forge_probe.py")
    source = """
Object f() { return result != null ? result : defaultOption; }
boolean g() { return result != null ? result : defaultYes; }
"""
    findings = mod.remote_defaults(source)
    assert [x["fallback"] for x in findings] == ["defaultOption", "defaultYes"]


def test_proprietary_launcher_round_trips_without_legality_translation(tmp_path: Path) -> None:
    fake = tmp_path / "fake_provider.py"
    fake.write_text(
        """import json,sys\nr=json.loads(sys.stdin.read())\nprint(json.dumps({'protocol':r['protocol'],'message_type':'RUN_FIXTURE_RESULT','request_id':r['request_id'],'payload':{'verdict':'UNSUPPORTED','evidence_class':'RUNTIME_VERIFIED','reason':'fake'}}))\n""",
        encoding="utf-8",
    )
    request = {
        "protocol": "commander-lab.rules-service/1.1.0",
        "message_type": "RUN_FIXTURE",
        "request_id": "t1",
        "payload": {"fixture": {"fixture_id": "X"}},
    }
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PROVIDER_CMD"] = f"{sys.executable} {fake}"
    cp = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ws19_run_forge_provider.py")],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    response = json.loads(cp.stdout)
    assert response["request_id"] == "t1"
    assert response["payload"]["verdict"] == "UNSUPPORTED"


def test_proprietary_launcher_fails_closed_when_provider_missing() -> None:
    env = os.environ.copy()
    env.pop("COMMANDER_LAB_FORGE_PROVIDER_CMD", None)
    cp = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ws19_run_forge_provider.py")],
        input=json.dumps(
            {
                "protocol": "commander-lab.rules-service/1.1.0",
                "message_type": "RUN_FIXTURE",
                "request_id": "t2",
                "payload": {},
            }
        )
        + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert cp.returncode != 0
    assert "fails closed" in cp.stderr

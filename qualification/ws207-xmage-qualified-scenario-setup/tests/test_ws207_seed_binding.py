"""WS207 WS208/WS212 impact regression tests (no JVM required).

Guards the seed-authority boundary in repository source:

- production XmageFullGameSession must remain RandomUtil-only (no Rules-seed
  binding there; that change belongs to WS213, never WS207);
- every WS207 qualification-only setup path must bind the per-game Rules RNG
  explicitly (setRulesSeed + setRequireExplicitSeed before start/init) and
  fail closed when the binding is unobservable;
- WS207 must never use TestPlayer coin/die fallbacks (WS214 NOT_APPLICABLE);
- the orchestrator must route setup evidence exclusively through the bound
  driver and the opening_rs_ provenance prefix.
"""

import sys
from pathlib import Path

WS207_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = WS207_ROOT.parent.parent
sys.path.insert(0, str(WS207_ROOT))

DRIVER_JAVA = WS207_ROOT / "driver-java/org/commanderlab/xmage/Ws207SetupDriver.java"
PROBE_JAVA = WS207_ROOT / "driver-java/org/commanderlab/xmage/Ws207OpeningHandProbe.java"
PRODUCTION_SESSION = (
    REPO_ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
)
ORCHESTRATOR = WS207_ROOT / "ws207_setup.py"


def test_production_session_binds_rules_seed_natively():
    # WS213 SUCCESSOR REVISION (supersedes the WS207 RandomUtil-only guard,
    # which explicitly deferred this change to WS213): the production session
    # now binds the explicit orchestration seed to the native per-game Rules
    # RNG before start/init; RandomUtil is retired as Rules authority.
    # Recorded in qualification/ws213 / IMPACT_ADJUDICATION; WS207 sealed
    # evidence itself is untouched.
    text = PRODUCTION_SESSION.read_text()
    assert "setRulesSeed(seed)" in text
    assert "setRequireExplicitSeed(true)" in text
    assert "import mage.util.RandomUtil" not in text
    assert "RandomUtil." not in text


def test_setup_driver_binds_rules_seed_before_start():
    text = DRIVER_JAVA.read_text()
    assert "setRulesSeed(seed)" in text
    assert "setRequireExplicitSeed(true)" in text
    assert "WS207_RULES_SEED_BINDING_FAILED" in text
    construct = text.find("new XmageFullGameSession(")
    bind = text.find("setRulesSeed(seed)")
    start = text.find("session.start()", bind)
    assert 0 <= construct < bind < start


def test_probe_binds_rules_seed_before_start():
    text = PROBE_JAVA.read_text()
    assert "setRulesSeed(seed)" in text
    assert "setRequireExplicitSeed(true)" in text
    assert "WS207_RULES_SEED_BINDING_FAILED" in text
    construct = text.find("new XmageFullGameSession(")
    bind = text.find("setRulesSeed(seed)")
    start = text.find("session.start()", bind)
    assert 0 <= construct < bind < start


def test_setup_driver_records_binding_provenance():
    text = DRIVER_JAVA.read_text()
    for field in (
        '"rules_seed"',
        '"rules_seed_bound_before_start"',
        '"rules_seed_explicit"',
        '"seed_binding_model"',
    ):
        assert field in text


def test_no_testplayer_in_ws207_surface():
    roots = [WS207_ROOT / "driver-java", WS207_ROOT / "ws207_decks.py", WS207_ROOT / "ws207_setup.py"]
    paths: list[Path] = []
    for root in roots:
        if root.is_dir():
            paths.extend(list(root.rglob("*.java")))
        else:
            paths.append(root)
    assert paths
    for path in paths:
        assert "TestPlayer" not in path.read_text(), str(path)


def test_orchestrator_routes_only_through_bound_driver():
    text = ORCHESTRATOR.read_text()
    assert "org.commanderlab.xmage.Ws207SetupDriver" in text
    assert "org.commanderlab.xmage.Ws205FirstWaveDriver" not in text
    assert "opening_rs_seed_" in text
    assert "opening_rs_scan.json" in text
    assert "rules_seed_explicit" in text
    assert "SUPERSEDED" in text

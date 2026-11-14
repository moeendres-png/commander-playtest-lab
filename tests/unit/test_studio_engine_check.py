"""The binding engine check of the deck builder ("Prüfung durch die Engine").

All data here is synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, engine_check
from commander_lab.studio.web import create_app

COMMANDER = "Chulane, Teller of Tales"


def _rows(
    commanders: list[str], main: list[tuple[str, int]], *, pad: bool = True
) -> list[dict[str, object]]:
    """Deck rows; the runner's deck model wants exactly 100 cards, so basics fill up."""
    main = list(main)
    if pad:
        main.append(("Forest", 99 - sum(quantity for _, quantity in main)))
    rows: list[dict[str, object]] = [
        {"oracle_name": name, "engine_name": name, "zone": "commander", "quantity": 1}
        for name in commanders
    ]
    rows += [
        {"oracle_name": name, "engine_name": name, "zone": "main", "quantity": quantity}
        for name, quantity in main
    ]
    return rows


LEGAL = [("Island", 29), ("Plains", 28), ("Sol Ring", 1), ("Cultivate", 1)]


def _fake_jar(folder: Path) -> None:
    jar = folder / "engine" / "xmage-engine-bridge.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"not a real jar")


def test_the_real_validation_passes_a_legal_deck(tmp_path: Path) -> None:
    result = engine_check.construction_check(_rows([COMMANDER], LEGAL))
    assert result["status"] == "PASS"


def test_the_real_validation_refuses_a_colour_identity_violation(tmp_path: Path) -> None:
    result = engine_check.construction_check(_rows([COMMANDER], [*LEGAL, ("Lightning Bolt", 1)]))
    assert result["status"] == "FAIL"
    assert result["code"] == "deck_color_identity_violation"
    assert "Farbidentität" in str(result["text"])


def test_the_real_validation_refuses_a_duplicate_non_basic(tmp_path: Path) -> None:
    result = engine_check.construction_check(_rows([COMMANDER], [("Sol Ring", 2), ("Forest", 5)]))
    assert result["status"] == "FAIL"
    assert result["code"] == "deck_duplicate_card"


def test_the_real_validation_refuses_a_card_without_known_identity(tmp_path: Path) -> None:
    result = engine_check.construction_check(
        _rows([COMMANDER], [("A Card Nobody Printed", 1), ("Forest", 5)])
    )
    assert result["status"] == "FAIL"
    assert result["code"] == "deck_color_identity_unknown"


def test_a_deck_that_is_not_100_cards_cannot_be_validated_and_is_unknown(
    tmp_path: Path,
) -> None:
    rows = _rows([COMMANDER], [("Forest", 5)], pad=False)
    assert engine_check.construction_check(rows)["status"] == "NOT_CHECKED"
    result = engine_check.check_rows(rows, tmp_path)
    assert result["status"] == "UNKNOWN"


def test_without_the_engine_a_clean_deck_is_unknown_never_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_env(monkeypatch)
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)
    assert result["engine_ready"] is False
    assert result["status"] == "UNKNOWN"
    assert result["headline"] == "nicht geprüft: Engine nicht bereitgestellt"
    assert result["construction"]["status"] == "PASS"


def test_a_found_failure_is_reported_even_without_the_engine(tmp_path: Path) -> None:
    result = engine_check.check_rows(_rows([COMMANDER], [*LEGAL, ("Lightning Bolt", 1)]), tmp_path)
    assert result["status"] == "FAIL"
    assert result["construction"]["status"] == "FAIL"


@pytest.fixture
def provisioned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A command that really exists: an executable file and a jar file, named by the env var."""
    from commander_lab.studio import launch

    program = tmp_path / "fake-java"
    program.write_text("#!/bin/sh\n", encoding="utf-8")
    program.chmod(0o755)
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"not a real jar")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"{program} -jar {jar} full-game")
    return tmp_path


def _no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from commander_lab.studio import launch

    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)


def test_a_clean_complete_deck_with_a_real_engine_passes(provisioned: Path) -> None:
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), provisioned)
    assert result["engine_ready"] is True
    assert (result["status"], result["construction"]["status"]) == ("PASS", "PASS")  # type: ignore[index]
    assert result["cards_consulted"] is True


@pytest.mark.parametrize(
    ("label", "rows", "needle"),
    [
        ("five cards", _rows([COMMANDER], [("Forest", 4)], pad=False), "5"),
        ("no commander", _rows([], [("Forest", 100)], pad=False), "Commander"),
        ("empty", [], "0"),
    ],
)
def test_an_unchecked_construction_is_never_a_pass_even_with_an_engine(
    provisioned: Path, label: str, rows: list[dict[str, object]], needle: str
) -> None:
    result = engine_check.check_rows(rows, provisioned)
    assert result["engine_ready"] is True
    assert result["status"] == "UNKNOWN", label
    assert str(result["headline"]).startswith("nicht geprüft")
    failures = result["precondition_failures"]
    assert isinstance(failures, list) and failures
    assert any(needle in str(text) for text in failures)


def test_precondition_texts_are_plain() -> None:
    five = engine_check.preconditions(_rows([COMMANDER], [("Forest", 4)], pad=False))
    assert five == ["Das Deck hat 5 statt 100 Karten."]
    none = engine_check.preconditions(_rows([], [("Forest", 100)], pad=False))
    assert none == ["Das Deck hat keinen Commander."]
    assert engine_check.preconditions(_rows([COMMANDER], LEGAL)) == []


def test_a_nonexistent_command_is_not_provisioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "/nonexistent/x")
    ready, reason = engine_check.engine_readiness(tmp_path)
    assert ready is False and "/nonexistent/x" in reason
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)
    assert result["status"] == "UNKNOWN"
    assert result["headline"] == "nicht geprüft: Engine nicht bereitgestellt"
    assert result["engine_reason"]


def test_a_command_whose_jar_is_missing_is_not_provisioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    program = tmp_path / "fake-java"
    program.write_text("#!/bin/sh\n", encoding="utf-8")
    program.chmod(0o755)
    monkeypatch.setenv(
        launch.ENGINE_COMMAND_ENV, f"{program} -jar {tmp_path}/missing.jar full-game"
    )
    ready, reason = engine_check.engine_readiness(tmp_path)
    assert ready is False and "missing.jar" in reason
    (tmp_path / "missing.jar").mkdir()  # a directory is not a jar file
    assert engine_check.engine_readiness(tmp_path)[0] is False


def test_a_fake_existing_command_and_jar_are_provisioned(provisioned: Path) -> None:
    assert engine_check.engine_readiness(provisioned) == (True, "")


def test_the_java_probe_runs_at_most_once_for_repeated_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    _no_env(monkeypatch)
    _fake_jar(tmp_path)
    java = tmp_path / "java"
    java.write_text("#!/bin/sh\n", encoding="utf-8")
    java.chmod(0o755)
    calls: list[str] = []

    def probe(path: str) -> int:
        calls.append(path)
        return 21

    engine_check._JAVA_MAJOR_CACHE.clear()
    monkeypatch.setattr(launch, "_java_executable", lambda: str(java))
    monkeypatch.setattr(launch, "_java_major", probe)
    for _ in range(3):
        assert engine_check.engine_readiness(tmp_path) == (True, "")
    assert len(calls) == 1
    java.write_text("#!/bin/sh\n# changed\n", encoding="utf-8")  # a replaced JDK is probed again
    import os

    os.utime(java, ns=(1, 1))
    engine_check.engine_readiness(tmp_path)
    assert len(calls) == 2


def test_an_old_or_unreadable_java_is_not_provisioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    _no_env(monkeypatch)
    _fake_jar(tmp_path)
    java = tmp_path / "java"
    java.write_text("", encoding="utf-8")
    monkeypatch.setattr(launch, "_java_executable", lambda: str(java))
    for major in (11, None):
        engine_check._JAVA_MAJOR_CACHE.clear()
        monkeypatch.setattr(launch, "_java_major", lambda path, m=major: m)
        assert engine_check.engine_readiness(tmp_path)[0] is False


def test_cards_the_engine_cannot_load_fail_the_check(
    provisioned: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    monkeypatch.setattr(
        launch, "cards_unsupported_by_engine", lambda snapshot: ["Missing In Engine"]
    )
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), provisioned)
    assert result["status"] == "FAIL"
    assert result["unsupported_by_engine"] == ["Missing In Engine"]


def test_an_unreadable_card_list_is_unknown_not_a_pass(
    provisioned: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import builder

    monkeypatch.setattr(builder, "sim_readiness_available", lambda: False)
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), provisioned)
    assert result["cards_consulted"] is False
    assert result["status"] == "UNKNOWN"


def test_the_page_names_each_state() -> None:
    from commander_lab.studio.web import STATIC

    script = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "precondition_failures" in script
    assert "Voraussetzung nicht erfüllt" in script
    assert "engine_reason" in script


def test_the_route_reports_unknown_without_a_provisioned_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_env(monkeypatch)
    from tests.unit.test_studio_builder import _deck, _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    body = client.post("/api/engine-check", json={"cards": [c.__dict__ for c in _deck()]})
    assert body.status_code == 200
    payload = body.json()
    assert payload["status"] in {"UNKNOWN", "FAIL"}
    assert payload["status"] != "PASS"
    assert payload["engine_ready"] is False
    assert payload["label"] == "Prüfung durch die Engine"

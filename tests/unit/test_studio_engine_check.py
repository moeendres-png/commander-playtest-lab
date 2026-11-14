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


def _rows(commanders: list[str], main: list[tuple[str, int]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"oracle_name": name, "engine_name": name, "zone": "commander", "quantity": 1}
        for name in commanders
    ]
    rows += [
        {"oracle_name": name, "engine_name": name, "zone": "main", "quantity": quantity}
        for name, quantity in main
    ]
    return rows


LEGAL = [("Forest", 30), ("Island", 20), ("Plains", 20), ("Sol Ring", 1), ("Cultivate", 1)]


def _fake_jar(folder: Path) -> None:
    jar = folder / "engine" / "xmage-engine-bridge.jar"
    jar.parent.mkdir(parents=True)
    jar.write_bytes(b"not a real jar")


def test_the_real_validation_passes_a_legal_deck(tmp_path: Path) -> None:
    result = engine_check.construction_check(_rows([COMMANDER], LEGAL))
    assert result == {"status": "PASS", "code": None, "message": ""}


def test_the_real_validation_refuses_a_colour_identity_violation(tmp_path: Path) -> None:
    result = engine_check.construction_check(_rows([COMMANDER], [*LEGAL, ("Lightning Bolt", 1)]))
    assert result["status"] == "FAIL"
    assert result["code"] == "deck_color_identity_violation"
    assert "Lightning Bolt" in str(result["message"])


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


def test_without_the_engine_a_clean_deck_is_unknown_never_green(tmp_path: Path) -> None:
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)
    assert result["engine_ready"] is False
    assert result["status"] == "UNKNOWN"
    assert result["headline"] == "nicht geprüft: Engine nicht bereitgestellt"
    assert result["construction"]["status"] == "PASS"


def test_a_found_failure_is_reported_even_without_the_engine(tmp_path: Path) -> None:
    result = engine_check.check_rows(
        _rows([COMMANDER], [*LEGAL, ("Lightning Bolt", 1)]), tmp_path
    )
    assert result["status"] == "FAIL"
    assert result["construction"]["status"] == "FAIL"


def test_a_missing_java_or_jar_is_not_ready_and_a_present_jar_is_ready_when_java_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    _fake_jar(tmp_path)
    monkeypatch.setattr(launch, "engine_command", lambda folder: ("java", "-jar", "x", "full-game"))
    ready = engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)
    assert ready["engine_ready"] is True
    assert ready["status"] == "PASS"
    monkeypatch.setattr(launch, "engine_command", lambda folder: None)
    assert engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)["status"] == "UNKNOWN"


def test_cards_the_engine_cannot_load_fail_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    monkeypatch.setattr(launch, "engine_command", lambda folder: ("java",))
    monkeypatch.setattr(
        launch, "cards_unsupported_by_engine", lambda snapshot: ["Missing In Engine"]
    )
    result = engine_check.check_rows(_rows([COMMANDER], LEGAL), tmp_path)
    assert result["status"] == "FAIL"
    assert result["unsupported_by_engine"] == ["Missing In Engine"]


def test_the_route_reports_unknown_without_a_provisioned_engine(tmp_path: Path) -> None:
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

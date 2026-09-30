"""E2: receipts record behaviour-relevant environment facts without raw values.

``environment_identity()`` used to persist up to 200 raw characters of
``MAVEN_OPTS``, ``JAVA_HOME`` and the bridge command variables into every
native-suite receipt. A credential passed as a ``-D`` property or a local path
therefore landed in committed evidence. The receipt now keeps option names,
command shape, validated scalars and a digest.
"""

from __future__ import annotations

import json

import pytest

from commander_lab.qualification.current_boundary import receipts

SECRET = "s3cr3t-sentinel-0d9f"
HOME = "/home/private-user-4411"


@pytest.fixture
def leaky_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAVA_HOME", f"{HOME}/jdks/temurin-17")
    monkeypatch.setenv(
        "MAVEN_OPTS", f"-Xmx2g -Dmaven.repo.local={HOME}/.m2 -Dgithub.token={SECRET}"
    )
    monkeypatch.setenv(
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD",
        f"java -Dauth={SECRET} -jar {HOME}/lab/engine-bridge/target/bridge.jar full-game",
    )
    monkeypatch.setenv("COMMANDER_LAB_FORGE_BRIDGE_CMD", f"'{HOME}/forge run' --token {SECRET}")
    monkeypatch.setenv("FORGE_ENGINE_SHA", "ef958ee91ac6c9ce0152189f2654bf6e05abf273")
    monkeypatch.setenv("PYTHONHASHSEED", "0")


@pytest.mark.usefixtures("leaky_env")
def test_no_raw_value_reaches_the_identity() -> None:
    identity = receipts.environment_identity()
    encoded = json.dumps(identity)
    assert SECRET not in encoded
    assert HOME not in encoded
    assert "private-user" not in encoded


@pytest.mark.usefixtures("leaky_env")
def test_structure_that_matters_is_kept() -> None:
    identity = receipts.environment_identity()
    assert identity["MAVEN_OPTS.option_names"] == "-Dgithub.token,-Dmaven.repo.local,-Xmx"
    assert identity["JAVA_HOME.basename"] == "temurin-17"
    assert (
        identity["COMMANDER_LAB_XMAGE_BRIDGE_CMD.shape"] == "java -Dauth -jar bridge.jar full-game"
    )
    assert identity["FORGE_ENGINE_SHA"] == "ef958ee91ac6c9ce0152189f2654bf6e05abf273"
    assert identity["PYTHONHASHSEED"] == "0"
    for key in (
        "JAVA_HOME.sha256_16",
        "MAVEN_OPTS.sha256_16",
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD.sha256_16",
        "COMMANDER_LAB_FORGE_BRIDGE_CMD.sha256_16",
    ):
        assert len(identity[key]) == 16


def test_digest_distinguishes_values_without_revealing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAVEN_OPTS", f"-Dtoken={SECRET}")
    first = receipts.environment_identity()
    monkeypatch.setenv("MAVEN_OPTS", "-Dtoken=other")
    second = receipts.environment_identity()
    assert first["MAVEN_OPTS.option_names"] == second["MAVEN_OPTS.option_names"]
    assert first["MAVEN_OPTS.sha256_16"] != second["MAVEN_OPTS.sha256_16"]


def test_malformed_scalars_are_not_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORGE_ENGINE_SHA", f"main {SECRET}")
    monkeypatch.setenv("PYTHONHASHSEED", SECRET)
    identity = receipts.environment_identity()
    assert identity["FORGE_ENGINE_SHA"] == "<invalid>"
    assert identity["PYTHONHASHSEED"] == "<invalid>"


def test_unset_variables_are_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "JAVA_HOME",
        "MAVEN_OPTS",
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD",
        "COMMANDER_LAB_FORGE_BRIDGE_CMD",
        "FORGE_ENGINE_SHA",
        "PYTHONHASHSEED",
    ):
        monkeypatch.delenv(key, raising=False)
    assert set(receipts.environment_identity()) == {"python"}


def test_positional_and_flag_values_become_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "COMMANDER_LAB_XMAGE_BRIDGE_CMD", f"bridge-cli {SECRET} --key {SECRET} full-game"
    )
    shape = receipts.environment_identity()["COMMANDER_LAB_XMAGE_BRIDGE_CMD.shape"]
    assert shape == "bridge-cli <arg> --key <arg> full-game"

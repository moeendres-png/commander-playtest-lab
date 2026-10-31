"""Java dependency report: version order, statuses, jar reading, exit codes, the shipped table."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    name = "report_java_dependencies"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts/report_java_dependencies.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rjd = _module()

TABLE: dict[str, Any] = {
    "schema_version": 1,
    "checked_on": "2026-10-31",
    "advisories": [
        {
            "id": "GHSA-test-guava",
            "component": "com.google.guava:guava",
            "severity": "HIGH",
            "fixed_in": "33.7.2",
            "summary": "test finding",
            "reachability": "not reachable in the test",
        },
        {
            "id": "GHSA-test-jsoup-a",
            "component": "org.jsoup:jsoup",
            "severity": "MODERATE",
            "fixed_in": "1.23.1",
        },
        {
            "id": "GHSA-test-jsoup-b",
            "component": "org.jsoup:jsoup",
            "severity": "HIGH",
            "fixed_in": "1.23.2",
        },
    ],
    "checked_without_advisory": ["com.google.code.gson:gson", "org.slf4j:slf4j-api"],
    "jar_facts": {"h2_auto_server": "AUTO_SERVER text from the table"},
}


def _pom(group: str, artifact: str, version: str) -> tuple[str, bytes]:
    body = f"#x\nversion={version}\ngroupId={group}\nartifactId={artifact}\n"
    return f"META-INF/maven/{group}/{artifact}/pom.properties", body.encode()


def _jar(
    tmp_path: Path,
    poms: list[tuple[str, str, str]],
    extra: dict[str, bytes] | None = None,
    name: str = "bridge.jar",
) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        for group, artifact, version in poms:
            entry, body = _pom(group, artifact, version)
            archive.writestr(entry, body)
        for entry, body in (extra or {}).items():
            archive.writestr(entry, body)
    return path


def _table(tmp_path: Path, table: dict[str, Any] | None = None) -> Path:
    path = tmp_path / "advisories.json"
    path.write_text(json.dumps(table or TABLE), encoding="utf-8")
    return path


def _status(reports: list[Any]) -> dict[str, str]:
    return {report.key: report.status for report in reports}


def _classify(tmp_path: Path, poms: list[tuple[str, str, str]]) -> list[Any]:
    components, _ = rjd.read_components(_jar(tmp_path, poms))
    return rjd.classify(components, rjd.load_table(_table(tmp_path)))


def test_version_order_reads_maven_suffixes_and_missing_digits() -> None:
    assert rjd._below("33.4.8-jre", "33.7.2") is True
    assert rjd._below("33.7.2-jre", "33.7.2") is False
    assert rjd._below("1.21.2", "1.23.1") is True
    assert rjd._below("2.0", "2.0.0") is False
    assert rjd._below("2", "2.0.1") is True
    assert rjd._below("9999.0-empty-to-avoid-conflict-with-guava", "33.7.2") is False
    assert rjd._below("unknown", "33.7.2") is None
    assert rjd._below("1.0", "next") is None


def test_open_clean_and_unknown_are_told_apart(tmp_path: Path) -> None:
    reports = _classify(
        tmp_path,
        [
            ("com.google.guava", "guava", "33.4.8-jre"),
            ("com.google.code.gson", "gson", "2.14.0"),
            ("com.example", "mystery", "1.0.0"),
        ],
    )
    assert _status(reports) == {
        "com.google.guava:guava": "ADVISORY_OPEN",
        "com.google.code.gson:gson": "CHECKED_CLEAN",
        "com.example:mystery": "UNKNOWN",
    }


def test_status_follows_the_version_not_the_name(tmp_path: Path) -> None:
    open_report = _classify(tmp_path, [("com.google.guava", "guava", "33.4.8-jre")])
    fixed_report = _classify(tmp_path, [("com.google.guava", "guava", "33.7.2-jre")])
    assert open_report[0].status == "ADVISORY_OPEN"
    # Fixed version of a library the table has an advisory for but no clean entry: not clean.
    assert fixed_report[0].status == "UNKNOWN"
    assert fixed_report[0].advisories == []


def test_two_advisories_sort_by_severity_and_each_needs_its_own_fix(tmp_path: Path) -> None:
    both = _classify(tmp_path, [("org.jsoup", "jsoup", "1.21.2")])[0]
    assert [hit.advisory_id for hit in both.advisories] == [
        "GHSA-test-jsoup-b",
        "GHSA-test-jsoup-a",
    ]
    only_high = _classify(tmp_path, [("org.jsoup", "jsoup", "1.23.1")])[0]
    assert [hit.advisory_id for hit in only_high.advisories] == ["GHSA-test-jsoup-b"]


def test_own_libraries_are_not_reported(tmp_path: Path) -> None:
    reports = _classify(
        tmp_path,
        [("org.mage", "mage", "1.4.62"), ("org.commanderlab", "xmage-engine-bridge", "0.1")],
    )
    assert reports == []


def test_h2_version_is_the_highest_literal_and_missing_literal_is_unknown(tmp_path: Path) -> None:
    both = _jar(
        tmp_path,
        [],
        {"org/h2/engine/Constants.class": b"\x01\x00\x071.4.197\x0c\x01\x00\x071.4.196\x0c"},
        "both.jar",
    )
    components, _ = rjd.read_components(both)
    assert [(c.key, c.version) for c in components] == [("com.h2database:h2", "1.4.197")]
    none = _jar(tmp_path, [], {"org/h2/engine/Constants.class": b"\x00\x01nothing"}, "none.jar")
    components, _ = rjd.read_components(none)
    assert components[0].version == "unknown"
    assert _status(rjd.classify(components, rjd.load_table(_table(tmp_path)))) == {
        "com.h2database:h2": "UNKNOWN"
    }


def test_unversioned_protobuf_is_listed_as_unknown(tmp_path: Path) -> None:
    jar = _jar(tmp_path, [], {"com/google/protobuf/Message.class": b"x"})
    components, _ = rjd.read_components(jar)
    assert [(c.key, c.version) for c in components] == [
        ("com.google.protobuf:protobuf-java", "unknown")
    ]


@pytest.mark.parametrize(
    ("content", "expected"),
    [(b"jdbc:h2:file:./db/%s;AUTO_SERVER=TRUE", "present"), (b"jdbc:h2:file:./db/%s", "not found")],
)
def test_auto_server_marker_is_read_from_the_class(
    tmp_path: Path, content: bytes, expected: str
) -> None:
    jar = _jar(tmp_path, [], {"mage/cards/repository/DatabaseUtils.class": content})
    assert rjd.read_components(jar)[1]["h2_auto_server"] == expected


def test_missing_database_class_is_not_determined_rather_than_absent(tmp_path: Path) -> None:
    facts = rjd.read_components(_jar(tmp_path, []))[1]
    assert facts["h2_auto_server"].startswith("class not in jar")


def test_report_exit_code_and_strict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    table = str(_table(tmp_path))
    open_jar = str(_jar(tmp_path, [("com.google.guava", "guava", "33.4.8-jre")], name="open.jar"))
    clean_jar = str(_jar(tmp_path, [("com.google.code.gson", "gson", "2.14.0")], name="clean.jar"))
    unknown_jar = str(_jar(tmp_path, [("com.example", "mystery", "1.0")], name="unknown.jar"))
    base = ["--table", table, "--today", "2026-10-31"]
    assert rjd.main(["--jar", open_jar, *base]) == 0
    assert rjd.main(["--jar", open_jar, *base, "--strict"]) == 1
    assert rjd.main(["--jar", unknown_jar, *base, "--strict"]) == 1
    assert rjd.main(["--jar", clean_jar, *base, "--strict"]) == 0
    out = capsys.readouterr().out
    assert "ADVISORY_OPEN  com.google.guava:guava 33.4.8-jre" in out
    assert "HIGH GHSA-test-guava fixed in 33.7.2: test finding" in out
    assert "UNKNOWN is not a pass" in out


def test_old_table_is_called_old_and_json_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    jar = str(_jar(tmp_path, [("com.google.code.gson", "gson", "2.14.0")]))
    out_json = tmp_path / "out.json"
    argv = ["--jar", jar, "--table", str(_table(tmp_path)), "--json", str(out_json)]
    assert rjd.main([*argv, "--today", "2026-10-31"]) == 0
    assert "WARNING" not in capsys.readouterr().out
    assert rjd.main([*argv, "--today", "2026-12-15"]) == 0
    text = capsys.readouterr().out
    assert "(45 days old)" in text and "WARNING: the table is older than 30 days" in text
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["table_age_days"] == 45
    assert payload["components"][0]["status"] == "CHECKED_CLEAN"


def test_h2_fact_text_comes_from_the_table_only_when_the_marker_is_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    table = str(_table(tmp_path))
    marked = _jar(
        tmp_path, [], {"mage/cards/repository/DatabaseUtils.class": b";AUTO_SERVER=TRUE"}, "m.jar"
    )
    plain = _jar(tmp_path, [], {"mage/cards/repository/DatabaseUtils.class": b"x"}, "p.jar")
    rjd.main(["--jar", str(marked), "--table", table, "--today", "2026-10-31"])
    assert "AUTO_SERVER text from the table" in capsys.readouterr().out
    rjd.main(["--jar", str(plain), "--table", table, "--today", "2026-10-31"])
    assert "AUTO_SERVER text from the table" not in capsys.readouterr().out


def test_shipped_table_is_well_formed() -> None:
    path = ROOT / "data/security/java_dependency_advisories.json"
    table = rjd.load_table(path)
    assert table.advisories
    for advisory in table.advisories:
        assert rjd._version_key(advisory.fixed_in) is not None, advisory.advisory_id
        assert advisory.severity in rjd.SEVERITY_ORDER, advisory.advisory_id
        assert advisory.component not in table.checked_clean, advisory.advisory_id
    assert len({advisory.advisory_id for advisory in table.advisories}) == len(table.advisories)
    assert "h2_auto_server" in table.jar_facts

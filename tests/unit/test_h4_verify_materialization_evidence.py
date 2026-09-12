"""WS-A1D-H4 verifier logic tests (no Docker required).

These tests validate the non-Docker logic of
``scripts/h4_verify_materialization_evidence.py``: handshake emission from
manifest authority and fail-closed adjudication of captured evidence files.

No pins are restated here: positive fixtures are derived at test time from
``config/rules_engines.json`` (the sole authority) and every mismatch case
mutates one field. Nothing here executes Docker, starts a container, or
substitutes for runtime evidence.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MANIFEST_REL = "config/rules_engines.json"
_METHODS = (
    "start_engine",
    "get_provider_version",
    "get_capabilities",
    "shutdown_engine",
)


def _load(name: str, relative: str):
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve string annotations,
    # mirroring what the normal import system guarantees.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier():
    return _load(
        "h4_verify_materialization_evidence", "scripts/h4_verify_materialization_evidence.py"
    )


@pytest.fixture(scope="module")
def resolver():
    return _load("docker_resolve_engine_pin", "scripts/docker_resolve_engine_pin.py")


@pytest.fixture(scope="module")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def manifest_path(repo_root) -> Path:
    return repo_root / _MANIFEST_REL


def _expected(resolver, manifest_path, provider: str):
    manifest = resolver.load_manifest(str(manifest_path))
    return resolver.resolve(provider, manifest)


def _emit(verifier, manifest_path, provider: str, tmp_path: Path, tag: str):
    requests_file = tmp_path / f"{tag}-requests.jsonl"
    rc = verifier.main(
        [
            "emit-handshake",
            "--provider",
            provider,
            "--manifest",
            str(manifest_path),
            "--out-requests",
            str(requests_file),
        ]
    )
    assert rc == 0
    requests = [
        json.loads(line)
        for line in requests_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return requests


def _responses(provider: str, protocol: str, commit: str, requests: list) -> list:
    payloads = [
        {"engine": provider, "started": True, "phase": "B4D_EVENT_LOG_LIFECYCLE"},
        {
            "engine": provider,
            "engine_version": "test-version",
            "engine_commit": commit,
            "protocol_version": protocol,
        },
        {
            "capabilities": {
                "commander_supported": True,
                "multiplayer_supported": True,
                "deck_import_supported": True,
                "legal_actions_supported": False,
                "action_submission_supported": False,
                "event_log_supported": True,
                "runtime_kind": "external_rules_engine",
            }
        },
        {"engine": provider, "shutdown": True},
    ]
    return [
        {
            "protocol_version": protocol,
            "request_id": request["request_id"],
            "success": True,
            "status": "ok",
            "payload": payload,
            "engine_event_offset": 0,
        }
        for request, payload in zip(requests, payloads, strict=True)
    ]


def _write(tmp_path: Path, name: str, payload) -> Path:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _provenance(provider: str, pin) -> dict:
    return {
        "provider": provider,
        "repository": pin.repository,
        "commit": pin.commit,
        "protocol_version": pin.protocol_version,
    }


def _verify_args(manifest_path, provider: str, tmp_path: Path, pin, **overrides) -> list:
    provenance = _write(tmp_path, "provenance.json", _provenance(provider, pin))
    head = _write(tmp_path, "head.txt", pin.commit + "\n")
    args = [
        "verify",
        "--provider",
        provider,
        "--manifest",
        str(manifest_path),
        "--provenance",
        str(provenance),
        "--source-head",
        str(head),
        "--image-id",
        "sha256:" + "0" * 64,
        "--image-tag",
        f"h4-test-{provider}:test",
        "--build-exit-code",
        "0",
        "--out",
        str(tmp_path / "verdict.json"),
    ]
    for key, value in overrides.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    return args


@pytest.mark.parametrize("provider", ["xmage", "forge"])
def test_emit_handshake_uses_manifest_protocol(
    verifier, resolver, manifest_path, tmp_path, provider, capsys
):
    pin = _expected(resolver, manifest_path, provider)
    requests_file = tmp_path / "requests.jsonl"
    rc = verifier.main(
        [
            "emit-handshake",
            "--provider",
            provider,
            "--manifest",
            str(manifest_path),
            "--out-requests",
            str(requests_file),
        ]
    )
    assert rc == 0
    stdout_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    file_lines = [
        line for line in requests_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert stdout_lines == file_lines
    requests = [json.loads(line) for line in file_lines]
    assert [r["message_type"] for r in requests] == list(_METHODS)
    assert len({r["request_id"] for r in requests}) == 4
    assert all(r["protocol_version"] == pin.protocol_version for r in requests)


def test_emit_unknown_provider_fails(verifier, manifest_path, tmp_path, capsys):
    with pytest.raises(SystemExit) as excinfo:
        verifier.parse_args(
            ["emit-handshake", "--provider", "unknown", "--manifest", str(manifest_path)]
        )
    assert excinfo.value.code == 2


def test_emit_missing_manifest_fails_closed(verifier, tmp_path):
    rc = verifier.main(
        ["emit-handshake", "--provider", "xmage", "--manifest", str(tmp_path / "absent.json")]
    )
    assert rc == 3


def test_verify_complete_xmage_evidence(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "xmage")
    responses = _responses("xmage", pin.protocol_version, pin.commit, requests)
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    requests_file = tmp_path / "xmage-requests.jsonl"
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        ["--handshake-requests", str(requests_file), "--handshake-transcript", str(transcript)]
    )
    rc = verifier.main(args)
    assert rc == 0
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["overall"] == "EVIDENCE_COMPLETE"
    decisive = {k: v for k, v in verdict["boundaries"].items() if k != "engine_verify"}
    assert all(v["status"] == "PASS" for v in decisive.values())
    assert verdict["boundaries"]["bridge_handshake"]["observed"]["engine_commit"] == pin.commit


def _forge_responses(protocol: str, commit: str, requests: list) -> list:
    """Forge H4F qualified handshake shape: status strings, same rigor otherwise."""
    payloads = [
        {"engine": "forge", "protocol_version": protocol, "status": "started"},
        {
            "engine": "forge",
            "engine_version": "test-version",
            "engine_commit": commit,
            "protocol_version": protocol,
        },
        {
            "capabilities": {
                "commander_supported": True,
                "multiplayer_supported": True,
                "deck_import_supported": True,
                "legal_actions_supported": False,
                "action_submission_supported": False,
                "event_log_supported": False,
                "runtime_kind": "external_rules_engine",
            }
        },
        {"engine": "forge", "protocol_version": protocol, "status": "engine_shut_down"},
    ]
    return [
        {
            "protocol_version": protocol,
            "request_id": request["request_id"],
            "success": True,
            "status": "ok",
            "payload": payload,
            "engine_event_offset": 0,
        }
        for request, payload in zip(requests, payloads, strict=True)
    ]


def _forge_provenance(pin, bridge: dict) -> dict:
    return {
        "provider": "forge",
        "repository": pin.repository,
        "commit": pin.commit,
        "protocol_version": pin.protocol_version,
        "bridge_repository": bridge["repository"],
        "bridge_commit": bridge["commit"],
        "rules_core_base_commit": bridge["rules_core_base_commit"],
    }


def _linkage_files(tmp_path: Path, diff_lines: list | None = None):
    merge_exit = tmp_path / "linkage-merge-base-exit.txt"
    merge_exit.write_text("0\n", encoding="utf-8")
    diff_names = tmp_path / "linkage-diff-names.txt"
    if diff_lines is None:
        diff_lines = [
            "forge-protocol2-bridge/src/main/java/forge/bridge/BridgeMain.java",
            "pom.xml",
        ]
    diff_names.write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
    return merge_exit, diff_names


def _forge_verify_args(
    manifest_path,
    tmp_path: Path,
    pin,
    bridge: dict,
    merge_exit: Path,
    diff_names: Path,
    **overrides,
) -> list:
    provenance = _write(tmp_path, "provenance.json", _forge_provenance(pin, bridge))
    head = _write(tmp_path, "head.txt", bridge["commit"] + "\n")
    args = [
        "verify",
        "--provider",
        "forge",
        "--manifest",
        str(manifest_path),
        "--provenance",
        str(provenance),
        "--source-head",
        str(head),
        "--image-id",
        "sha256:" + "0" * 64,
        "--image-tag",
        "h4-test-forge:test",
        "--build-exit-code",
        "0",
        "--linkage-merge-base-exit",
        merge_exit.read_text(encoding="utf-8").strip(),
        "--linkage-diff-names",
        str(diff_names),
        "--out",
        str(tmp_path / "verdict.json"),
    ]
    for key, value in overrides.items():
        args.extend([f"--{key.replace('_', '-')}", str(value)])
    return args


def _bridge_dict(resolver, manifest_path) -> dict:
    manifest = resolver.load_manifest(str(manifest_path))
    return dict(manifest["secondary_engine"]["bridge_source"])


def test_verify_forge_complete_with_handshake_and_linkage(
    verifier, resolver, manifest_path, tmp_path
):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    assert bridge["rules_core_base_commit"] == pin.commit
    assert bridge["commit"] != pin.commit
    merge_exit, diff_names = _linkage_files(tmp_path)
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    requests = _emit(verifier, manifest_path, "forge", tmp_path, "forge-full")
    responses = _forge_responses(pin.protocol_version, pin.commit, requests)
    transcript = _write(
        tmp_path,
        "forge-transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "forge-full-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    rc = verifier.main(args)
    assert rc == 0
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["overall"] == "EVIDENCE_COMPLETE"
    decisive = {k: v for k, v in verdict["boundaries"].items() if k != "engine_verify"}
    assert all(v["status"] == "PASS" for v in decisive.values()), decisive
    handshake = verdict["boundaries"]["bridge_handshake"]
    assert handshake["observed"]["engine_commit"] == pin.commit
    caps = handshake["observed"]["capabilities"]
    assert caps["legal_actions_supported"] is False
    assert caps["action_submission_supported"] is False
    assert caps["event_log_supported"] is False
    assert caps["runtime_kind"] == "external_rules_engine"
    assert verdict["boundaries"]["materialization_match"]["status"] == "PASS"
    assert verdict["boundaries"]["rules_linkage"]["status"] == "PASS"
    assert verdict["boundaries"]["source_head_match"]["status"] == "PASS"


def test_verify_forge_partial_without_handshake(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    merge_exit, diff_names = _linkage_files(tmp_path)
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    rc = verifier.main(args)
    assert rc == 0
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["overall"] == "EVIDENCE_PARTIAL"
    assert verdict["boundaries"]["bridge_handshake"]["status"] == "NOT_RUN"
    assert "H4 PASS" in verdict["h4_note"]


def test_verify_forge_missing_linkage_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    provenance = _write(tmp_path, "provenance.json", _forge_provenance(pin, bridge))
    head = _write(tmp_path, "head.txt", bridge["commit"] + "\n")
    rc = verifier.main(
        [
            "verify",
            "--provider",
            "forge",
            "--manifest",
            str(manifest_path),
            "--provenance",
            str(provenance),
            "--source-head",
            str(head),
            "--image-id",
            "sha256:" + "4" * 64,
            "--image-tag",
            "h4-test-forge:test",
            "--build-exit-code",
            "0",
            "--out",
            str(tmp_path / "verdict.json"),
        ]
    )
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["overall"] == "EVIDENCE_MISMATCH"
    assert verdict["boundaries"]["rules_linkage"]["status"] == "FAIL"


def test_verify_forge_wrong_bridge_commit_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    bad = _forge_provenance(pin, bridge)
    bad["bridge_commit"] = "f" * 40
    provenance = _write(tmp_path, "provenance.json", bad)
    head = _write(tmp_path, "head.txt", bridge["commit"] + "\n")
    merge_exit, diff_names = _linkage_files(tmp_path)
    rc = verifier.main(
        [
            "verify",
            "--provider",
            "forge",
            "--manifest",
            str(manifest_path),
            "--provenance",
            str(provenance),
            "--source-head",
            str(head),
            "--image-id",
            "sha256:" + "5" * 64,
            "--image-tag",
            "h4-test-forge:test",
            "--build-exit-code",
            "0",
            "--linkage-merge-base-exit",
            merge_exit.read_text(encoding="utf-8").strip(),
            "--linkage-diff-names",
            str(diff_names),
            "--out",
            str(tmp_path / "verdict.json"),
        ]
    )
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["materialization_match"]["status"] == "FAIL"


def test_verify_forge_source_head_must_be_bridge_commit(
    verifier, resolver, manifest_path, tmp_path
):
    # The image source HEAD is the materialization commit, never the Rules pin:
    # presenting the Rules commit as the source HEAD fails closed.
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    merge_exit, diff_names = _linkage_files(tmp_path)
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    head_path = tmp_path / "head.txt"
    head_path.write_text(pin.commit + "\n", encoding="utf-8")
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["source_head_match"]["status"] == "FAIL"


def test_verify_forge_linkage_drift_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    merge_exit, diff_names = _linkage_files(
        tmp_path, ["forge-protocol2-bridge/BridgeMain.java", "forge-game/Game.java", "pom.xml"]
    )
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["rules_linkage"]["status"] == "FAIL"


def test_verify_forge_linkage_ancestor_failure_fails_closed(
    verifier, resolver, manifest_path, tmp_path
):
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    merge_exit, diff_names = _linkage_files(tmp_path)
    merge_exit.write_text("1\n", encoding="utf-8")
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["rules_linkage"]["status"] == "FAIL"


def test_verify_forge_handshake_must_attest_rules_commit(
    verifier, resolver, manifest_path, tmp_path
):
    # The bridge handshake engine_commit must be the Rules-Core pin (a37), never
    # the bridge materialization SHA: presenting the bridge SHA fails closed.
    pin = _expected(resolver, manifest_path, "forge")
    bridge = _bridge_dict(resolver, manifest_path)
    merge_exit, diff_names = _linkage_files(tmp_path)
    args = _forge_verify_args(manifest_path, tmp_path, pin, bridge, merge_exit, diff_names)
    requests = _emit(verifier, manifest_path, "forge", tmp_path, "forge-badcommit")
    responses = _forge_responses(pin.protocol_version, bridge["commit"], requests)
    transcript = _write(
        tmp_path,
        "forge-badcommit-transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "forge-badcommit-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["bridge_handshake"]["status"] == "FAIL"


def test_verify_provenance_mismatch_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    bad = _provenance("xmage", pin)
    bad["commit"] = "0" * 40
    provenance = _write(tmp_path, "provenance.json", bad)
    head = _write(tmp_path, "head.txt", pin.commit + "\n")
    rc = verifier.main(
        [
            "verify",
            "--provider",
            "xmage",
            "--manifest",
            str(manifest_path),
            "--provenance",
            str(provenance),
            "--source-head",
            str(head),
            "--image-id",
            "sha256:" + "1" * 64,
            "--image-tag",
            "h4-test-xmage:test",
            "--build-exit-code",
            "0",
            "--out",
            str(tmp_path / "verdict.json"),
        ]
    )
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["overall"] == "EVIDENCE_MISMATCH"
    assert verdict["boundaries"]["provenance_match"]["status"] == "FAIL"


def test_verify_source_head_mismatch_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "forge")
    args = _verify_args(manifest_path, "forge", tmp_path, pin)
    head_path = tmp_path / "head.txt"
    head_path.write_text("f" * 40 + "\n", encoding="utf-8")
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["source_head_match"]["status"] == "FAIL"


def test_verify_build_failure_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args[args.index("--build-exit-code") + 1] = "1"
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["image_build"]["status"] == "FAIL"


def test_verify_wrong_protocol_in_transcript_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "badproto")
    responses = _responses("xmage", "9.9.9", pin.commit, requests)
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "badproto-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    rc = verifier.main(args)
    assert rc == 3
    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["boundaries"]["bridge_handshake"]["status"] == "FAIL"


def test_verify_wrong_engine_identity_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "badengine")
    responses = _responses("forge", pin.protocol_version, pin.commit, requests)
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "badengine-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    rc = verifier.main(args)
    assert rc == 3


def test_verify_request_id_mismatch_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "badrid")
    responses = _responses("xmage", pin.protocol_version, pin.commit, requests)
    responses[2]["request_id"] = "00000000-0000-0000-0000-000000000000"
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "badrid-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    assert verifier.main(args) == 3


def test_verify_engine_commit_mismatch_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "badcommit")
    responses = _responses("xmage", pin.protocol_version, "0" * 40, requests)
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "badcommit-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    assert verifier.main(args) == 3


def test_verify_non_external_runtime_kind_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests = _emit(verifier, manifest_path, "xmage", tmp_path, "badkind")
    responses = _responses("xmage", pin.protocol_version, pin.commit, requests)
    responses[2]["payload"]["capabilities"]["runtime_kind"] = "tactical_oracle"
    transcript = _write(
        tmp_path,
        "transcript.jsonl",
        "\n".join(json.dumps(r, sort_keys=True) for r in responses) + "\n",
    )
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(
        [
            "--handshake-requests",
            str(tmp_path / "badkind-requests.jsonl"),
            "--handshake-transcript",
            str(transcript),
        ]
    )
    assert verifier.main(args) == 3


def test_verify_half_handshake_evidence_fails(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    requests_file = tmp_path / "half-requests.jsonl"
    requests_file.write_text('{"request_id": "x"}\n', encoding="utf-8")
    args = _verify_args(manifest_path, "xmage", tmp_path, pin)
    args.extend(["--handshake-requests", str(requests_file)])
    assert verifier.main(args) == 3


def test_verify_missing_provenance_fails_closed(verifier, resolver, manifest_path, tmp_path):
    pin = _expected(resolver, manifest_path, "xmage")
    head = _write(tmp_path, "head.txt", pin.commit + "\n")
    rc = verifier.main(
        [
            "verify",
            "--provider",
            "xmage",
            "--manifest",
            str(manifest_path),
            "--provenance",
            str(tmp_path / "absent.json"),
            "--source-head",
            str(head),
            "--image-id",
            "sha256:" + "2" * 64,
            "--image-tag",
            "h4-test-xmage:test",
            "--build-exit-code",
            "0",
            "--out",
            str(tmp_path / "verdict.json"),
        ]
    )
    assert rc == 3


def test_verify_missing_manifest_fails_closed(verifier, tmp_path):
    provenance = _write(tmp_path, "provenance.json", {"provider": "xmage"})
    head = _write(tmp_path, "head.txt", "0" * 40 + "\n")
    rc = verifier.main(
        [
            "verify",
            "--provider",
            "xmage",
            "--manifest",
            str(tmp_path / "absent.json"),
            "--provenance",
            str(provenance),
            "--source-head",
            str(head),
            "--image-id",
            "sha256:" + "3" * 64,
            "--image-tag",
            "h4-test-xmage:test",
            "--build-exit-code",
            "0",
            "--out",
            str(tmp_path / "verdict.json"),
        ]
    )
    assert rc == 3

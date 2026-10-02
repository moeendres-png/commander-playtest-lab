import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def j(p):
    return json.loads((ROOT / p).read_text())


def test_schemas_are_valid_and_manifest_validates():
    for p in [
        "qualification/protocol/ws10r/rules_service_protocol_v1.schema.json",
        "qualification/protocol/ws10r/rsp_semantics_v1.schema.json",
        "qualification/protocol/ws10r/architecture_freeze_contract_v1.schema.json",
        "qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json",
        "qualification/evidence/normalized_evidence_v1.schema.json",
        "qualification/evidence/candidate_result_v1.schema.json",
    ]:
        Draft202012Validator.check_schema(j(p))
    Draft202012Validator(
        j("qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json")
    ).validate(j("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"))


def test_common_fixture_minimum_and_29_cards():
    m = j("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    ids = {x["fixture_id"] for x in m["fixtures"]}
    for pc in [2, 3, 4, 5]:
        assert f"PLAYER_COUNT_{pc}P" in ids
    assert len([x for x in m["fixtures"] if x["category"] == "actual_card"]) == 29
    for req in [
        "WS05-MP-PRIO-3",
        "WS05-MP-PRIO-5",
        "WS05-MP-TRIG-3",
        "WS05-MP-TRIG-5",
        "WS05-CMD-PARTNER-TAX",
        "WS05-CMD-ZONE-GY-YES",
        "WS05-CMD-ZONE-HAND-YES",
    ]:
        assert req in ids


def test_missing_provider_is_not_run_and_blocks_admission(tmp_path):
    out = tmp_path / "results.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "qualification/harness.py"),
            "run",
            "--candidate",
            "none",
            "--source-lock",
            str(ROOT / "qualification/WS17_SOURCE_LOCK.json"),
            "--manifest",
            str(ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"),
            "--output",
            str(out),
        ],
        check=True,
    )
    r = json.loads(out.read_text())
    assert all(x["verdict"] == "NOT_RUN" for x in r["fixture_results"])
    adm = tmp_path / "adm.json"
    md = tmp_path / "adm.md"
    sha = "a" * 40
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "qualification/harness.py"),
            "aggregate",
            "--manifest",
            str(ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"),
            "--results",
            str(out),
            "--admitted-main-sha",
            sha,
            "--actual-sha",
            sha,
            "--output",
            str(adm),
            "--md-output",
            str(md),
        ],
        check=True,
    )
    assert json.loads(adm.read_text())["production_admission"] == "FAIL"


def test_exact_main_mismatch_blocks_admission(tmp_path):
    adm = tmp_path / "adm.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "qualification/harness.py"),
            "aggregate",
            "--manifest",
            str(ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"),
            "--results",
            str(ROOT / "qualification/evidence/BASELINE_COMMON_RESULTS.json"),
            "--admitted-main-sha",
            "a" * 40,
            "--actual-sha",
            "b" * 40,
            "--output",
            str(adm),
        ],
        check=True,
    )
    assert json.loads(adm.read_text())["production_admission"] == "FAIL"
    assert json.loads(adm.read_text())["blocking_results"][0]["fixture_id"] == "EXACT_MAIN_SHA"


def test_no_required_obligation_accepts_unknown_partial_not_run():
    c = j("qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json")
    for o in c["obligations"]:
        if o["required"]:
            assert "UNKNOWN" not in o["satisfying_verdicts"]
            assert "PARTIAL" not in o["satisfying_verdicts"]
            assert "NOT_RUN" not in o["satisfying_verdicts"]


def test_production_admission_md_is_generated_shape():
    assert (
        "generated from `PRODUCTION_ADMISSION.json`"
        in (ROOT / "qualification/aggregate/PRODUCTION_ADMISSION.md").read_text()
    )


def test_candidate_reports_account_for_every_common_fixture():
    manifest = j("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    expected = {x["fixture_id"] for x in manifest["fixtures"]}
    schema = j("qualification/evidence/candidate_result_v1.schema.json")
    for name in ["xmage", "forge", "phase_rs", "argentum"]:
        report = j(f"qualification/evidence/candidates/{name}.json")
        Draft202012Validator(schema).validate(report)
        results = report["fixture_results"]
        assert {x["fixture_id"] for x in results} == expected
        assert len(results) == len(expected)
        assert all(x["verdict"] == "NOT_RUN" for x in results)
        assert all(
            x["omission_reason_code"] in {"PROTOCOL_ADAPTER_MISSING", "REMEDIATION_REQUIRED"}
            for x in results
        )


def test_active_deck_denominators_are_exact():
    d = j("qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json")
    assert len(d["current_rogshai_unique_identity_list"]) == 87
    assert len(d["current_kaervek_unique_identity_list"]) == 77
    assert len(d["rogshai_kaervek_shared_identity_list"]) == 10
    assert (
        d["active_deck_source_locks"]["rogshai"]["git_blob"]
        == "4db4174011e6ea0b07196e68165aa4549cff1971"
    )
    assert (
        d["active_deck_source_locks"]["kaervek"]["git_blob"]
        == "beebc3cf50e32b29db5c1e594821f754da69249d"
    )


def _verify_sha256_manifest(manifest_path: Path, base: Path):
    entries = []
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        digest, rel = raw.split("  ", 1)
        target = base / rel
        assert target.is_file(), rel
        import hashlib

        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, rel
        entries.append(rel)
    return entries


def test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts():
    root_entries = set(_verify_sha256_manifest(ROOT / "WS17_SHA256SUMS", ROOT))
    expected = {
        "pyproject.toml",
        ".github/workflows/production-qualification.yml",
        "tests/qualification/test_ws17_qualification.py",
    }
    expected |= {
        str(p.relative_to(ROOT))
        for p in (ROOT / "qualification").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert root_entries == expected
    q_entries = set(
        _verify_sha256_manifest(ROOT / "qualification/SHA256SUMS", ROOT / "qualification")
    )
    expected_q = {
        str(p.relative_to(ROOT / "qualification"))
        for p in (ROOT / "qualification").rglob("*")
        if p.is_file() and p.name != "SHA256SUMS" and "__pycache__" not in p.parts
    }
    assert q_entries == expected_q


def test_ws10r_bundle_and_internal_hashes_verify():
    import hashlib
    import zipfile

    ws = ROOT / "qualification/protocol/ws10r"
    bundle = ws / "WS-10R_ENGINE_NEUTRAL_PROTOCOL_BUNDLE.zip"
    digest_line = (ws / "WS-10R_ENGINE_NEUTRAL_PROTOCOL_BUNDLE.zip.sha256").read_text().strip()
    expected_digest, name = digest_line.split("  ", 1)
    assert name == bundle.name
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == expected_digest
    inner = {}
    for line in (ws / "SHA256SUMS").read_text().splitlines():
        d, n = line.split("  ", 1)
        inner[n] = d
    with zipfile.ZipFile(bundle) as z:
        names = set(z.namelist())
        assert set(inner) | {"SHA256SUMS"} == names
        for name, digest in inner.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest
        assert z.read("SHA256SUMS") == (ws / "SHA256SUMS").read_bytes()


def test_exact_main_workflow_is_unfiltered_and_provider_absence_is_fail_closed():
    text = (ROOT / ".github/workflows/production-qualification.yml").read_text(encoding="utf-8")
    assert "paths:" not in text and "paths-ignore:" not in text
    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in text
    assert (
        "COMMANDER_LAB_RSP_PROVIDER_CMD: ${{ vars.COMMANDER_LAB_RSP_PROVIDER_CMD || '' }}" in text
    )
    assert 'run_args+=(--command "$COMMANDER_LAB_RSP_PROVIDER_CMD")' in text
    assert "assert p['production_admission'] == 'FAIL'" in text
    assert "assert any(x['verdict'] == 'NOT_RUN' for x in p['blocking_results'])" in text


def test_production_admission_markdown_exactly_regenerates_from_json(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("ws17_harness", ROOT / "qualification/harness.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected = mod.render_md(ROOT / "qualification/aggregate/PRODUCTION_ADMISSION.json")
    assert (ROOT / "qualification/aggregate/PRODUCTION_ADMISSION.md").read_text(
        encoding="utf-8"
    ) == expected


def _load_ws17_harness():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "dq01_ws17_harness", ROOT / "qualification/harness.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _canonical_sha256(value):
    import hashlib

    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _dq01_fixture_context(candidate="xmage"):
    manifest = j("qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json")
    source_lock = j("qualification/WS17_SOURCE_LOCK.json")
    fixture = manifest["fixtures"][0]
    manifest = {**manifest, "fixtures": [fixture]}
    provider_lock = source_lock["candidate_locks"][candidate]
    binding_core = {
        "candidate": candidate,
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": _canonical_sha256(fixture),
        "source_lock_sha256": _canonical_sha256(source_lock),
        "authority_lock_sha256": manifest["authority_lock_sha256"],
        "denominator_hashes": manifest["denominator_hashes"],
        "provider_lock": provider_lock,
    }
    binding_sha256 = _canonical_sha256(binding_core)
    return manifest, source_lock, fixture, provider_lock, binding_core, binding_sha256


def _bound_provider_response(
    request,
    *,
    candidate="xmage",
    fixture_id=None,
    evidence_class="RUNTIME_VERIFIED",
    provider_identity_overrides=None,
    artifact_hashes_overrides=None,
):
    manifest, source_lock, fixture, provider_lock, _binding_core, binding_sha256 = (
        _dq01_fixture_context(candidate)
    )
    provider_identity = {
        "candidate": candidate,
        "repository": provider_lock["repository"],
        "commit": provider_lock["commit"],
        "source_lock_sha256": _canonical_sha256(source_lock),
        "qualification_binding_sha256": binding_sha256,
    }
    for optional in ("tree", "version"):
        if optional in provider_lock:
            provider_identity[optional] = provider_lock[optional]
    if provider_identity_overrides:
        provider_identity.update(provider_identity_overrides)

    payload = {
        "fixture_id": fixture_id or fixture["fixture_id"],
        "verdict": "PASS",
        "evidence_class": evidence_class,
        "provider_identity": provider_identity,
        "reason": "DQ-01 fully bound positive control",
        "events": [{"event_type": "DQ01_BOUND_EVIDENCE", "sequence": 0}],
        "artifact_hashes": {},
    }
    fixture_result_sha256 = _canonical_sha256(
        {key: value for key, value in payload.items() if key != "artifact_hashes"}
    )
    payload["artifact_hashes"] = {
        "fixture_result_sha256": fixture_result_sha256,
        "qualification_binding_sha256": binding_sha256,
        "events_sha256": _canonical_sha256(payload["events"]),
    }
    if artifact_hashes_overrides:
        payload["artifact_hashes"].update(artifact_hashes_overrides)

    return {
        "protocol": manifest["protocol"],
        "message_type": "FIXTURE_RESULT",
        "request_id": request["request_id"],
        "session_id": request.get("session_id"),
        "actor_id": request.get("actor_id"),
        "state_revision": request.get("state_revision"),
        "payload": payload,
    }


def _execute_with_response(monkeypatch, response_factory):
    mod = _load_ws17_harness()
    manifest, source_lock, _fixture, _provider_lock, _binding_core, _binding_sha256 = (
        _dq01_fixture_context()
    )

    def fake_provider(_command, request, timeout=120):
        assert timeout == 120
        return response_factory(request), None

    monkeypatch.setattr(mod, "run_provider", fake_provider)
    return mod, mod.execute("xmage", source_lock, manifest, command="fake-provider")


def _assert_provider_response_rejected(results):
    assert len(results) == 1
    result = results[0]
    assert result["verdict"] == "FAIL"
    assert result["evidence_class"] == "NOT_RUN"
    assert result["classification"] == "QUALIFICATION_INFRASTRUCTURE_MISSING"
    assert result["fixture_id"] == "PLAYER_COUNT_2P"


def test_dq01_minimal_fake_pass_fails_closed(monkeypatch):
    _mod, results = _execute_with_response(
        monkeypatch, lambda _request: {"payload": {"verdict": "PASS"}}
    )
    _assert_provider_response_rejected(results)


def test_dq01_wrong_fixture_id_fails_closed(monkeypatch):
    _mod, results = _execute_with_response(
        monkeypatch,
        lambda request: _bound_provider_response(request, fixture_id="CARD_29"),
    )
    _assert_provider_response_rejected(results)


def test_dq01_missing_fixture_id_fails_closed(monkeypatch):
    def response(request):
        document = _bound_provider_response(request)
        del document["payload"]["fixture_id"]
        return document

    _mod, results = _execute_with_response(monkeypatch, response)
    _assert_provider_response_rejected(results)


def test_dq01_wrong_or_missing_request_correlation_fails_closed(monkeypatch):
    for mode in ("wrong", "missing"):
        def response(request, mode=mode):
            document = _bound_provider_response(request)
            if mode == "wrong":
                document["request_id"] = "not-the-request"
            else:
                del document["request_id"]
            return document

        _mod, results = _execute_with_response(monkeypatch, response)
        _assert_provider_response_rejected(results)


def test_dq01_wrong_or_missing_session_correlation_fails_closed(monkeypatch):
    for mode in ("wrong", "missing"):
        def response(request, mode=mode):
            document = _bound_provider_response(request)
            if mode == "wrong":
                document["session_id"] = "unexpected-session"
            else:
                del document["session_id"]
            return document

        _mod, results = _execute_with_response(monkeypatch, response)
        _assert_provider_response_rejected(results)


def test_dq01_wrong_protocol_message_type_fails_closed(monkeypatch):
    def response(request):
        document = _bound_provider_response(request)
        document["message_type"] = "HELLO_RESPONSE"
        return document

    _mod, results = _execute_with_response(monkeypatch, response)
    _assert_provider_response_rejected(results)


def test_dq01_missing_provider_identity_fails_closed(monkeypatch):
    def response(request):
        document = _bound_provider_response(request)
        del document["payload"]["provider_identity"]
        return document

    _mod, results = _execute_with_response(monkeypatch, response)
    _assert_provider_response_rejected(results)


def test_dq01_wrong_provider_identity_fails_closed(monkeypatch):
    _mod, results = _execute_with_response(
        monkeypatch,
        lambda request: _bound_provider_response(
            request,
            provider_identity_overrides={
                "candidate": "forge",
                "repository": "Card-Forge/forge",
            },
        ),
    )
    _assert_provider_response_rejected(results)


def test_dq01_missing_evidence_class_fails_closed(monkeypatch):
    def response(request):
        document = _bound_provider_response(request)
        del document["payload"]["evidence_class"]
        return document

    _mod, results = _execute_with_response(monkeypatch, response)
    _assert_provider_response_rejected(results)


def test_dq01_non_runtime_evidence_class_cannot_earn_pass(monkeypatch):
    _mod, results = _execute_with_response(
        monkeypatch,
        lambda request: _bound_provider_response(request, evidence_class="CODE_DERIVED"),
    )
    _assert_provider_response_rejected(results)


def test_dq01_missing_or_unbound_artifact_hashes_fail_closed(monkeypatch):
    for mode in (
        "missing",
        "empty",
        "missing-evidence",
        "empty-evidence",
        "unknown-artifact",
        "wrong-result",
        "wrong-binding",
        "wrong-evidence",
    ):
        def response(request, mode=mode):
            document = _bound_provider_response(request)
            if mode == "missing":
                del document["payload"]["artifact_hashes"]
            elif mode == "empty":
                document["payload"]["artifact_hashes"] = {}
            elif mode == "missing-evidence":
                del document["payload"]["events"]
                document["payload"]["artifact_hashes"].pop("events_sha256")
            elif mode == "empty-evidence":
                document["payload"]["events"] = []
                document["payload"]["artifact_hashes"]["events_sha256"] = _canonical_sha256([])
                result_payload = {
                    key: value
                    for key, value in document["payload"].items()
                    if key != "artifact_hashes"
                }
                document["payload"]["artifact_hashes"]["fixture_result_sha256"] = (
                    _canonical_sha256(result_payload)
                )
            elif mode == "unknown-artifact":
                document["payload"]["artifact_hashes"]["unverifiable_sha256"] = "1" * 64
            elif mode == "wrong-result":
                document["payload"]["artifact_hashes"]["fixture_result_sha256"] = "0" * 64
            elif mode == "wrong-binding":
                document["payload"]["artifact_hashes"]["qualification_binding_sha256"] = "0" * 64
            else:
                document["payload"]["artifact_hashes"]["events_sha256"] = "0" * 64
            return document

        _mod, results = _execute_with_response(monkeypatch, response)
        _assert_provider_response_rejected(results)


def test_dq01_source_or_pin_mismatch_fails_closed(monkeypatch):
    for key, value in (
        ("commit", "0" * 40),
        ("source_lock_sha256", "0" * 64),
        ("qualification_binding_sha256", "0" * 64),
    ):
        _mod, results = _execute_with_response(
            monkeypatch,
            lambda request, key=key, value=value: _bound_provider_response(
                request, provider_identity_overrides={key: value}
            ),
        )
        _assert_provider_response_rejected(results)


def test_dq01_malformed_but_json_valid_response_fails_closed(monkeypatch):
    manifest, _source_lock, _fixture, _provider_lock, _binding_core, _binding_sha256 = (
        _dq01_fixture_context()
    )

    _mod, results = _execute_with_response(
        monkeypatch,
        lambda request: {
            "protocol": manifest["protocol"],
            "message_type": "FIXTURE_RESULT",
            "request_id": request["request_id"],
            "payload": [],
        },
    )
    _assert_provider_response_rejected(results)


def test_dq01_fully_bound_provider_pass_is_accepted(monkeypatch):
    _mod, results = _execute_with_response(
        monkeypatch,
        lambda request: _bound_provider_response(request),
    )
    assert len(results) == 1
    result = results[0]
    assert result["fixture_id"] == "PLAYER_COUNT_2P"
    assert result["verdict"] == "PASS"
    assert result["evidence_class"] == "RUNTIME_VERIFIED"
    assert result["classification"] == "RUNTIME_PASS"
    assert result["artifact_hashes"]["fixture_result_sha256"]
    assert result["artifact_hashes"]["qualification_binding_sha256"]


def test_dq01_duplicate_fixture_results_fail_closed():
    mod = _load_ws17_harness()
    fixture_id = "PLAYER_COUNT_2P"
    good = {
        "fixture_id": fixture_id,
        "verdict": "PASS",
        "reason": "valid unique result",
    }
    duplicate = {
        "fixture_id": fixture_id,
        "verdict": "PASS",
        "reason": "duplicate must not overwrite or double-count",
    }
    result = mod.aggregate([good, duplicate], [fixture_id])
    assert result["production_admission"] == "FAIL"
    assert result["pass_count"] == 0
    assert result["duplicate_fixture_ids"] == [fixture_id]
    assert any(
        row["fixture_id"] == fixture_id and row["verdict"] == "FAIL"
        for row in result["blocking_results"]
    )

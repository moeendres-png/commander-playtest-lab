#!/usr/bin/env python3
"""H4 Docker materialization evidence verifier (fail closed, stdlib only).

WS-A1D-H4 qualification harness. This script never grants H4 PASS: it checks
captured Docker/container evidence against the sole pin authority
(``config/rules_engines.json``) and emits a machine-readable verdict with
per-boundary ``PASS`` / ``FAIL`` / ``NOT_RUN`` (``RECORDED`` for the
informational engine-verify outcome). H4 adjudication itself stays with the
Coordinator.

Authority reuse, not duplication: expected provider identity is resolved with
``scripts/docker_resolve_engine_pin.py`` (the manifest consumer). This script
stores no pins.

Subcommands:

``emit-handshake`` prints the four JSONL bridge requests (``start_engine``,
``get_provider_version``, ``get_capabilities``, ``shutdown_engine``) with the
manifest protocol version, for piping into a container running the real
bridge. ``--out-requests`` records the emitted requests so ``verify`` can
match response ``request_id`` values.

``verify`` adjudicates captured evidence files (all inputs are paths to files
captured from real Docker/container commands, except short scalar identities
passed as flags)::

    image_build:            --build-exit-code (0 required; the caller attests
                            the real `docker build` exit status, visible in CI logs)
    provenance_match:       --provenance (image /opt/engine-provenance.json
                            capture) vs manifest provider/repository/commit/protocol
    source_head_match:      --source-head (image `git rev-parse HEAD` capture)
                            vs manifest commit
    startup_provenance_gate: PASS when the bridge handshake passed (the
                            entrypoint execs the bridge only after gate exit 0)
                            or when --gate-exit-code is 0 (gate-only probe on
                            the real image); NOT_RUN when neither is present
    bridge_handshake:       --handshake-requests + --handshake-transcript
                            (container stdout); every response must match its
                            request id, carry the manifest protocol version,
                            report success, identify the configured provider,
                            and attest the manifest Rules-Core commit
                            (providerVersion) plus
                            runtime_kind=external_rules_engine
                            (capabilities). XMage keeps its exact historical
                            payload contract; Forge accepts its documented
                            qualified shapes (status strings) with identical
                            rigor elsewhere. NOT_RUN when absent.
    engine_verify:          informational --engine-verify outcome record only.

Exit codes: 0 (no FAIL boundary), 2 (usage error), 3 (fail closed: any FAIL
boundary or unreadable authority/evidence).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_FAIL_CLOSED = 3

VERDICT_SCHEMA = "h4-materialization-verdict/1"
HANDSHAKE_METHODS = (
    "start_engine",
    "get_provider_version",
    "get_capabilities",
    "shutdown_engine",
)
_KNOWN_PROVIDERS = ("xmage", "forge")
# H4F qualified additive surface relative to the Rules-Core base. The materialization
# source container diff must stay inside it; anything else is unapproved Rules-Core
# drift and fails the rules_linkage boundary. Mirrors docker/forge/Dockerfile.
_H4F_SURFACE_DIR_PREFIX = "forge-protocol2-bridge/"
_H4F_SURFACE_FILES = ("pom.xml",)


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_resolver():
    path = _scripts_dir() / "docker_resolve_engine_pin.py"
    if not path.is_file():
        raise FileNotFoundError(f"pin resolver is missing: {path}")
    spec = importlib.util.spec_from_file_location("docker_resolve_engine_pin", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load pin resolver: {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve string annotations,
    # mirroring what the normal import system guarantees.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path, what: str):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{what} is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{what} is unreadable: {path} ({exc})") from exc
    return payload


def _read_json_lines(path: Path, what: str) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"{what} is missing: {path}") from exc
    except OSError as exc:
        raise ValueError(f"{what} is unreadable: {path} ({exc})") from exc
    records = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{what} line {lineno} is not valid JSON: {exc}") from exc
    return records


def _boundary(status: str, detail: str, extra: dict | None = None) -> dict:
    record: dict = {"status": status, "detail": detail}
    if extra:
        record.update(extra)
    return record


def emit_handshake(args: argparse.Namespace) -> int:
    resolver = _load_resolver()
    try:
        manifest = resolver.load_manifest(args.manifest)
        pin = resolver.resolve(args.provider, manifest)
    except Exception as exc:  # fail closed on any authority problem
        print(f"h4_verify: FAIL CLOSED: pin authority unusable: {exc}", file=sys.stderr)
        return EXIT_FAIL_CLOSED
    requests = []
    for method in HANDSHAKE_METHODS:
        requests.append(
            {
                "request_id": str(uuid.uuid4()),
                "protocol_version": pin.protocol_version,
                "message_type": method,
                "method": method,
                "params": {},
            }
        )
    if args.out_requests is not None:
        Path(args.out_requests).write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in requests),
            encoding="utf-8",
        )
    sys.stdout.write("".join(json.dumps(r, sort_keys=True) + "\n" for r in requests))
    return EXIT_OK


def _check_handshake(
    provider: str, expected_commit: str, expected_protocol: str, requests: list, responses: list
) -> tuple[dict, dict]:
    """Return (boundary, observed) for the handshake transcript.

    Step shape policy: XMage keeps its exact historical payload contract. Forge
    accepts its documented qualified shapes (``status`` strings instead of
    boolean flags, ``provider`` instead of ``engine`` for provider identity on
    get_provider_version, and a status-only shutdown payload) with identical
    rigor everywhere else — request/response identity, protocol version,
    success, provider identity, manifest commit attestation and runtime_kind.
    The observed shape is recorded; no shape is silently normalized into
    another.
    """
    observed: dict = {}
    if len(requests) != len(HANDSHAKE_METHODS):
        return _boundary(
            "FAIL",
            f"expected {len(HANDSHAKE_METHODS)} handshake requests, saw {len(requests)}",
        ), observed
    if len(responses) != len(HANDSHAKE_METHODS):
        return _boundary(
            "FAIL",
            f"expected {len(HANDSHAKE_METHODS)} handshake responses, saw {len(responses)}",
        ), observed
    for index, (method, request, response) in enumerate(
        zip(HANDSHAKE_METHODS, requests, responses, strict=True)
    ):
        where = f"handshake step {index} ({method})"
        if not isinstance(request, dict) or not isinstance(response, dict):
            return _boundary("FAIL", f"{where}: request/response must be JSON objects"), observed
        if request.get("message_type") != method:
            return _boundary(
                "FAIL", f"{where}: request message_type is {request.get('message_type')!r}"
            ), observed
        if response.get("request_id") != request.get("request_id"):
            return _boundary(
                "FAIL", f"{where}: response request_id does not match request"
            ), observed
        if response.get("protocol_version") != expected_protocol:
            return _boundary(
                "FAIL",
                f"{where}: protocol_version is {response.get('protocol_version')!r}, "
                f"expected {expected_protocol!r}",
            ), observed
        if response.get("success") is not True:
            errors = response.get("errors")
            return _boundary(
                "FAIL", f"{where}: bridge reported failure: {json.dumps(errors, sort_keys=True)}"
            ), observed
        payload = response.get("payload")
        if not isinstance(payload, dict):
            return _boundary("FAIL", f"{where}: response payload must be a JSON object"), observed
        if index == 0:
            if provider == "xmage":
                if payload.get("engine") != provider or payload.get("started") is not True:
                    return _boundary(
                        "FAIL", f"{where}: start_engine payload misidentifies the provider"
                    ), observed
            else:
                started = payload.get("started")
                status = payload.get("status")
                if payload.get("engine") != provider or not (
                    started is True or status == "started"
                ):
                    return _boundary(
                        "FAIL", f"{where}: start_engine payload misidentifies the provider"
                    ), observed
                observed["handshake_shape"] = "started-flag" if started is True else "status-string"
        elif index == 1:
            if provider == "forge":
                # Qualified Forge shape (BridgeEngine.getProviderVersion):
                # identity key is "provider", not "engine" (live H4F proof and
                # BridgeProtocolProcessTest assert payload.provider == "forge").
                # Accept the qualified "provider" shape and the historical
                # "engine" test shape, but any present identity key must equal
                # the provider and at least one must identify it.
                engine_id = payload.get("engine")
                provider_id = payload.get("provider")
                if engine_id is not None and engine_id != provider:
                    return _boundary(
                        "FAIL",
                        f"{where}: providerVersion engine is {engine_id!r}, expected {provider!r}",
                    ), observed
                if provider_id is not None and provider_id != provider:
                    return _boundary(
                        "FAIL",
                        f"{where}: providerVersion provider is {provider_id!r}, "
                        f"expected {provider!r}",
                    ), observed
                if engine_id != provider and provider_id != provider:
                    return _boundary(
                        "FAIL",
                        f"{where}: providerVersion engine is {engine_id!r}, expected {provider!r}",
                    ), observed
                observed["provider_identity_shape"] = (
                    "provider-key"
                    if provider_id == provider and engine_id != provider
                    else "engine-key"
                    if engine_id == provider and provider_id != provider
                    else "dual-key"
                )
            elif payload.get("engine") != provider:
                return _boundary(
                    "FAIL",
                    f"{where}: providerVersion engine is {payload.get('engine')!r}, "
                    f"expected {provider!r}",
                ), observed
            if payload.get("engine_commit") != expected_commit:
                return _boundary(
                    "FAIL",
                    f"{where}: providerVersion engine_commit contradicts the manifest pin",
                ), observed
            observed["engine_version"] = payload.get("engine_version")
            observed["engine_commit"] = payload.get("engine_commit")
        elif index == 2:
            capabilities = payload.get("capabilities", payload)
            if not isinstance(capabilities, dict):
                return _boundary("FAIL", f"{where}: capabilities must be a JSON object"), observed
            if capabilities.get("runtime_kind") != "external_rules_engine":
                return _boundary(
                    "FAIL",
                    f"{where}: runtime_kind is {capabilities.get('runtime_kind')!r}, "
                    "expected 'external_rules_engine'",
                ), observed
            observed["capabilities"] = {
                key: capabilities.get(key)
                for key in (
                    "commander_supported",
                    "partner_supported",
                    "multiplayer_supported",
                    "max_players",
                    "headless_supported",
                    "deck_import_supported",
                    "legal_actions_supported",
                    "action_submission_supported",
                    "event_log_supported",
                    "game_shutdown_supported",
                    "engine_shutdown_supported",
                    "runtime_kind",
                )
            }
        elif index == 3:
            if provider == "forge":
                # Qualified Forge shutdown (BridgeEngine.shutdownEngine) is a
                # status-only payload {"status": "engine_shut_down"} with no
                # engine/provider identity keys; identity is already bound at
                # steps 0-2. Accept that shape, accept the historical
                # engine-bearing test shape, but any present identity key must
                # equal the provider.
                engine_id = payload.get("engine")
                provider_id = payload.get("provider")
                if engine_id is not None and engine_id != provider:
                    return _boundary("FAIL", f"{where}: shutdown payload is malformed"), observed
                if provider_id is not None and provider_id != provider:
                    return _boundary("FAIL", f"{where}: shutdown payload is malformed"), observed
                if not (
                    payload.get("shutdown") is True or payload.get("status") == "engine_shut_down"
                ):
                    return _boundary("FAIL", f"{where}: shutdown payload is malformed"), observed
                observed["shutdown_shape"] = (
                    "status-only"
                    if engine_id is None and provider_id is None
                    else "identity-bearing"
                )
            elif provider == "xmage":
                if payload.get("engine") != provider or payload.get("shutdown") is not True:
                    return _boundary("FAIL", f"{where}: shutdown payload is malformed"), observed
            elif payload.get("engine") != provider or not (
                payload.get("shutdown") is True or payload.get("status") == "engine_shut_down"
            ):
                return _boundary("FAIL", f"{where}: shutdown payload is malformed"), observed
    return _boundary(
        "PASS",
        "container handshake succeeded: 4/4 responses match requests, carry "
        f"protocol {expected_protocol}, identify provider {provider}, attest "
        "manifest commit, and report runtime_kind=external_rules_engine",
        {"observed": observed},
    ), observed


def verify(args: argparse.Namespace) -> int:
    boundaries: dict[str, dict] = {}
    context: dict = {
        "provider": args.provider,
        "image_id": args.image_id,
        "image_tag": args.image_tag,
    }
    if args.docker_version:
        context["docker_version"] = args.docker_version
    if args.runner:
        context["runner"] = args.runner
    if args.lab_head:
        context["lab_head"] = args.lab_head

    resolver = _load_resolver()
    try:
        manifest = resolver.load_manifest(args.manifest)
        pin = resolver.resolve(args.provider, manifest)
    except Exception as exc:
        print(f"h4_verify: FAIL CLOSED: pin authority unusable: {exc}", file=sys.stderr)
        return EXIT_FAIL_CLOSED
    context["manifest"] = {
        "repository": pin.repository,
        "commit": pin.commit,
        "release": pin.release,
        "protocol_version": pin.protocol_version,
    }

    if args.build_exit_code == 0:
        boundaries["image_build"] = _boundary(
            "PASS",
            f"caller attests real docker build exit 0 for {args.image_tag} "
            f"(image {args.image_id}; see CI logs)",
        )
    else:
        boundaries["image_build"] = _boundary(
            "FAIL", f"docker build exit code was {args.build_exit_code}, expected 0"
        )

    try:
        provenance = _read_json(Path(args.provenance), "image provenance capture")
    except ValueError as exc:
        boundaries["provenance_match"] = _boundary("FAIL", str(exc))
        provenance = None
    if provenance is not None:
        if not isinstance(provenance, dict):
            boundaries["provenance_match"] = _boundary(
                "FAIL", "image provenance capture must be a JSON object"
            )
        else:
            expected = {
                "provider": args.provider,
                "repository": pin.repository,
                "commit": pin.commit,
                "protocol_version": pin.protocol_version,
            }
            mismatches = [k for k in expected if provenance.get(k) != expected[k]]
            if mismatches:
                boundaries["provenance_match"] = _boundary(
                    "FAIL",
                    "image provenance contradicts pin authority "
                    f"(fields: {','.join(sorted(mismatches))})",
                )
            else:
                boundaries["provenance_match"] = _boundary(
                    "PASS",
                    "image /opt/engine-provenance.json matches manifest on "
                    "provider, repository, commit and protocol_version",
                )
            if args.provider == "forge":
                # Dual identity: the materialization/bridge source recorded in the
                # image must independently match secondary_engine.bridge_source.
                # Half-present dual identity fails closed.
                bridge = manifest.get("secondary_engine", {}).get("bridge_source")
                if not isinstance(bridge, dict):
                    boundaries["materialization_match"] = _boundary(
                        "FAIL",
                        "pin authority is missing secondary_engine.bridge_source; "
                        "Forge dual identity cannot be proven",
                    )
                elif bridge.get("rules_core_base_commit") != pin.commit:
                    boundaries["materialization_match"] = _boundary(
                        "FAIL",
                        "pin authority bridge_source.rules_core_base_commit does not "
                        "equal the Rules-Core pin; materialization and Rules pin "
                        "are cross-wired",
                    )
                else:
                    bridge_expected = {
                        "bridge_repository": bridge.get("repository"),
                        "bridge_commit": bridge.get("commit"),
                        "rules_core_base_commit": bridge.get("rules_core_base_commit"),
                    }
                    bridge_mismatches = [
                        key
                        for key in bridge_expected
                        if provenance.get(key) != bridge_expected[key]
                    ]
                    if bridge_mismatches:
                        boundaries["materialization_match"] = _boundary(
                            "FAIL",
                            "image bridge provenance contradicts pin authority "
                            f"(fields: {','.join(sorted(bridge_mismatches))})",
                        )
                    else:
                        boundaries["materialization_match"] = _boundary(
                            "PASS",
                            "image bridge provenance matches manifest bridge_source on "
                            "bridge_repository, bridge_commit and rules_core_base_commit",
                        )

    try:
        head_text = Path(args.source_head).read_text(encoding="utf-8").strip()
    except OSError as exc:
        boundaries["source_head_match"] = _boundary(
            "FAIL", f"image source HEAD capture unreadable: {exc}"
        )
        head_text = ""
    if "source_head_match" not in boundaries:
        # Forge materializes the candidate bridge source, so its source HEAD must
        # equal bridge_source.commit; XMage materializes the Rules pin directly.
        if args.provider == "forge":
            bridge = manifest.get("secondary_engine", {}).get("bridge_source", {})
            expected_head = bridge.get("commit") if isinstance(bridge, dict) else None
            head_detail = "manifest secondary_engine.bridge_source.commit"
        else:
            expected_head = pin.commit
            head_detail = "manifest commit"
        if not isinstance(expected_head, str) or not expected_head:
            boundaries["source_head_match"] = _boundary(
                "FAIL", f"expected source HEAD authority ({head_detail}) is missing"
            )
        elif head_text == expected_head:
            boundaries["source_head_match"] = _boundary(
                "PASS",
                f"image /opt/engine-source HEAD equals {head_detail}",
                {"source_head": head_text},
            )
        else:
            boundaries["source_head_match"] = _boundary(
                "FAIL",
                f"image source HEAD {head_text!r} contradicts {head_detail} {expected_head!r}",
            )

    if args.provider == "forge":
        # Rules-Core linkage: the captured merge-base proof must show the Rules pin
        # is an ancestor of the materialized source, and every changed path must
        # stay inside the qualified H4F additive surface. Absent linkage evidence
        # fails closed; XMage carries no such boundary.
        if args.linkage_merge_base_exit is None or args.linkage_diff_names is None:
            boundaries["rules_linkage"] = _boundary(
                "FAIL",
                "rules linkage evidence is half-present or absent: linkage "
                "merge-base exit and diff names must be supplied together for forge",
            )
        elif args.linkage_merge_base_exit != 0:
            boundaries["rules_linkage"] = _boundary(
                "FAIL",
                "materialization source does not descend from the Rules-Core pin "
                f"(merge-base exit {args.linkage_merge_base_exit})",
            )
        else:
            try:
                diff_lines = [
                    line
                    for line in Path(args.linkage_diff_names)
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
            except OSError as exc:
                boundaries["rules_linkage"] = _boundary(
                    "FAIL", f"linkage diff-names capture unreadable: {exc}"
                )
                diff_lines = None
            if diff_lines is not None:
                outside = [
                    line
                    for line in diff_lines
                    if line != "pom.xml" and not line.startswith(_H4F_SURFACE_DIR_PREFIX)
                ]
                if outside:
                    boundaries["rules_linkage"] = _boundary(
                        "FAIL",
                        "materialization source drifts outside the qualified H4F "
                        f"surface: {','.join(sorted(outside)[:8])}",
                    )
                else:
                    boundaries["rules_linkage"] = _boundary(
                        "PASS",
                        "materialization source descends from the Rules-Core pin and "
                        "differs from it only inside the qualified H4F surface",
                        {"changed_paths": len(diff_lines)},
                    )

    handshake_boundary: dict | None = None
    if args.handshake_requests is not None or args.handshake_transcript is not None:
        if args.handshake_requests is None or args.handshake_transcript is None:
            handshake_boundary = _boundary(
                "FAIL",
                "handshake evidence is half-present: requests and transcript "
                "must be supplied together",
            )
        else:
            try:
                requests = _read_json_lines(Path(args.handshake_requests), "handshake requests")
                responses = _read_json_lines(
                    Path(args.handshake_transcript), "handshake transcript"
                )
                handshake_boundary, _ = _check_handshake(
                    args.provider, pin.commit, pin.protocol_version, requests, responses
                )
            except ValueError as exc:
                handshake_boundary = _boundary("FAIL", str(exc))
        boundaries["bridge_handshake"] = handshake_boundary
    else:
        boundaries["bridge_handshake"] = _boundary(
            "NOT_RUN",
            "no handshake transcript supplied (no conforming bridge run attempted)",
        )

    gate_status = boundaries["bridge_handshake"]["status"]
    if gate_status == "PASS":
        boundaries["startup_provenance_gate"] = _boundary(
            "PASS",
            "entrypoint provenance gate passed on the real image: the real "
            "bridge started and answered (the entrypoint execs "
            "ENGINE_START_COMMAND only after gate exit 0)",
        )
    elif args.gate_exit_code is not None:
        if args.gate_exit_code == 0:
            boundaries["startup_provenance_gate"] = _boundary(
                "PASS",
                "gate-only probe (verify_container_provenance.py) exited 0 on the real image",
            )
        else:
            boundaries["startup_provenance_gate"] = _boundary(
                "FAIL", f"gate-only probe exited {args.gate_exit_code}, expected 0"
            )
    else:
        boundaries["startup_provenance_gate"] = _boundary(
            "NOT_RUN", "no gate execution observed on the image"
        )

    if args.engine_verify is not None:
        try:
            record = _read_json(Path(args.engine_verify), "engine-verify capture")
            observed_status = record.get("status") if isinstance(record, dict) else None
            boundaries["engine_verify"] = _boundary(
                "RECORDED",
                f"engine-verify outcome recorded (status={observed_status!r}); "
                "informational only, not an H4 gate",
                {"observed_status": observed_status},
            )
        except ValueError as exc:
            boundaries["engine_verify"] = _boundary(
                "RECORDED", f"engine-verify capture issue: {exc}"
            )
    else:
        boundaries["engine_verify"] = _boundary("NOT_RUN", "engine-verify was not run")

    decisive = {k: v for k, v in boundaries.items() if k != "engine_verify"}
    if any(v["status"] == "FAIL" for v in decisive.values()):
        overall = "EVIDENCE_MISMATCH"
        rc = EXIT_FAIL_CLOSED
    elif any(v["status"] == "NOT_RUN" for v in decisive.values()):
        overall = "EVIDENCE_PARTIAL"
        rc = EXIT_OK
    else:
        overall = "EVIDENCE_COMPLETE"
        rc = EXIT_OK

    verdict = {
        "schema": VERDICT_SCHEMA,
        "context": context,
        "boundaries": boundaries,
        "overall": overall,
        "h4_note": "Evidence record only. H4 PASS/FAIL/PARTIAL/UNKNOWN is a "
        "Coordinator adjudication, never this script's output.",
    }
    Path(args.out).write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sys.stdout.write(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    if rc != EXIT_OK:
        print(f"h4_verify: FAIL CLOSED: verdict is {overall}", file=sys.stderr)
    return rc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H4 Docker materialization evidence verifier.")
    sub = parser.add_subparsers(dest="command", required=True)

    emit = sub.add_parser("emit-handshake", help="print JSONL handshake requests")
    emit.add_argument("--provider", required=True, choices=_KNOWN_PROVIDERS)
    emit.add_argument("--manifest", required=True)
    emit.add_argument("--out-requests", default=None)

    check = sub.add_parser("verify", help="adjudicate captured evidence files")
    check.add_argument("--provider", required=True, choices=_KNOWN_PROVIDERS)
    check.add_argument("--manifest", required=True)
    check.add_argument("--provenance", required=True)
    check.add_argument("--source-head", required=True)
    check.add_argument("--image-id", required=True)
    check.add_argument("--image-tag", required=True)
    check.add_argument("--build-exit-code", required=True, type=int)
    check.add_argument("--handshake-requests", default=None)
    check.add_argument("--handshake-transcript", default=None)
    check.add_argument("--gate-exit-code", default=None, type=int)
    check.add_argument("--engine-verify", default=None)
    check.add_argument("--docker-version", default=None)
    check.add_argument("--runner", default=None)
    check.add_argument("--lab-head", default=None)
    check.add_argument("--linkage-merge-base-exit", default=None, type=int)
    check.add_argument("--linkage-diff-names", default=None)
    check.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or EXIT_USAGE)
    if args.command == "emit-handshake":
        if args.provider not in _KNOWN_PROVIDERS:
            print(f"h4_verify: unsupported provider {args.provider!r}", file=sys.stderr)
            return EXIT_USAGE
        return emit_handshake(args)
    if args.command == "verify":
        if args.provider not in _KNOWN_PROVIDERS:
            print(f"h4_verify: unsupported provider {args.provider!r}", file=sys.stderr)
            return EXIT_USAGE
        return verify(args)
    print(f"h4_verify: unknown command {args.command!r}", file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())

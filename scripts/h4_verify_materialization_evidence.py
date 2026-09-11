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
                            and attest the manifest commit (providerVersion)
                            plus runtime_kind=external_rules_engine
                            (capabilities). NOT_RUN when absent (e.g. Forge:
                            no conforming bridge exists, so no handshake may
                            be attempted).
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
    """Return (boundary, observed) for the handshake transcript."""
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
            if payload.get("engine") != provider or payload.get("started") is not True:
                return _boundary(
                    "FAIL", f"{where}: start_engine payload misidentifies the provider"
                ), observed
        elif index == 1:
            if payload.get("engine") != provider:
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
        elif index == 3 and (
            payload.get("engine") != provider or payload.get("shutdown") is not True
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

    try:
        head_text = Path(args.source_head).read_text(encoding="utf-8").strip()
    except OSError as exc:
        boundaries["source_head_match"] = _boundary(
            "FAIL", f"image source HEAD capture unreadable: {exc}"
        )
        head_text = ""
    if "source_head_match" not in boundaries:
        if head_text == pin.commit:
            boundaries["source_head_match"] = _boundary(
                "PASS",
                "image /opt/engine-source HEAD equals the manifest commit",
                {"source_head": head_text},
            )
        else:
            boundaries["source_head_match"] = _boundary(
                "FAIL",
                f"image source HEAD {head_text!r} contradicts manifest commit {pin.commit!r}",
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

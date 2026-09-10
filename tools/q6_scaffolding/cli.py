"""Deterministic CLI for the Q6 scaffolding pipeline.

Composable subcommands with machine-readable JSON I/O::

    intake                external inputs + source locks -> intake records
    classify              intake records -> parsed + classified records
    generate-skeletons    classified records -> skeletons + routed states
    build-review-queues   routed records -> deterministic review queues
    build-manifest        routed records + queues -> verifiable manifest
    validate              verify manifest hash, schemas, states, and gates

Every subcommand fails closed (non-zero exit, no partial output file) on:
missing source-lock metadata, invalid schema, hash mismatch, duplicate or
conflicting identities, promotion/contamination fields, or ambiguous
provenance where required. Stdout carries a JSON summary; artifacts go to
``--out`` files only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import Q6_SCAFFOLDING_VERSION
from .classify import classify_card
from .forge_parser import FORGE_PARSER_VERSION, extract_features, parse_script
from .gate import PromotionRejected, reject_promotion_fields, validate_output
from .intake import IntakeError, detect_conflicts, intake_card
from .manifest import build_manifest, verify_manifest
from .provenance import ProvenanceError, SourceLock
from .queues import build_queues, queue_summary
from .skeleton import generate_skeleton, route_state
from .states import ScaffoldingState


class CliError(ValueError):
    """Fail-closed CLI error (message goes to stderr, exit code 2)."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"cannot read JSON input {path}: {exc}") from exc


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _emit(summary: dict) -> int:
    print(json.dumps(summary, sort_keys=True))
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    spec = _read_json(Path(args.inputs))
    if not isinstance(spec, dict) or not isinstance(spec.get("inputs"), list):
        raise CliError('inputs file must be {"inputs": [...]}')
    corpus_root = Path(args.corpus_root) if args.corpus_root else None
    records = []
    for entry in spec["inputs"]:
        if not isinstance(entry, dict):
            raise CliError(f"invalid input entry (not an object): {entry!r}")
        try:
            reject_promotion_fields(entry, source="inputs spec entry")
        except PromotionRejected as exc:
            raise CliError(str(exc)) from exc
        for key in ("path", "source_corpus", "source_repository", "source_commit"):
            if not entry.get(key):
                raise CliError(f"input entry missing required source-lock field {key!r}: {entry!r}")
        raw_path = Path(entry["path"])
        if not raw_path.is_absolute() and corpus_root is not None:
            raw_path = corpus_root / raw_path
        try:
            raw = raw_path.read_bytes()
        except OSError as exc:
            raise CliError(f"cannot read input file {raw_path}: {exc}") from exc
        lock = SourceLock(
            source_corpus=entry["source_corpus"],
            source_repository=entry["source_repository"],
            source_commit=entry["source_commit"],
            source_path=entry.get("source_path", str(entry["path"])),
        )
        try:
            record = intake_card(
                raw,
                lock,
                expected_hash=entry.get("expected_hash"),
                extra_metadata=entry.get("metadata"),
            )
        except (ProvenanceError, IntakeError) as exc:
            raise CliError(str(exc)) from exc
        records.append(record)
    try:
        detect_conflicts(records)
    except IntakeError as exc:
        raise CliError(str(exc)) from exc
    payload = {
        "tool_version": Q6_SCAFFOLDING_VERSION,
        "records": [r.as_dict() for r in sorted(records, key=lambda r: r.intake_id)],
    }
    validate_output(payload, artifact="intake-batch")
    _write_json(Path(args.out), payload)
    return _emit(
        {
            "command": "intake",
            "records": len(records),
            "tool_version": Q6_SCAFFOLDING_VERSION,
        }
    )


def _require_records(payload: Any, *, source: str) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise CliError(f'{source} must be {{"records": [...]}}')
    return payload["records"]


def cmd_classify(args: argparse.Namespace) -> int:
    payload = _read_json(Path(args.in_file))
    enriched = []
    for record in _require_records(payload, source="intake file"):
        if record.get("state") != ScaffoldingState.INTAKE_ONLY.value:
            raise CliError(
                f"classify expects INTAKE_ONLY records "
                f"(got {record.get('state')} for {record.get('intake_id')})"
            )
        raw_text = record.get("raw_text", "")
        parsed = parse_script(raw_text, record["provenance"]["source_path"])
        features = extract_features(parsed, raw_text)
        classification = classify_card(record["intake_id"], features)
        record = dict(record)
        record["parsed"] = parsed
        record["features"] = features
        record["classification"] = classification.as_dict()
        record["stage_history"] = [ScaffoldingState.PARSED.value]
        record["state"] = ScaffoldingState.STRUCTURED.value
        record["stage_history"].append(ScaffoldingState.STRUCTURED.value)
        validate_output(record, artifact="classified-record")
        enriched.append(record)
    enriched.sort(key=lambda r: r["intake_id"])
    out = {"tool_version": Q6_SCAFFOLDING_VERSION, "records": enriched}
    validate_output(out, artifact="classified-batch")
    _write_json(Path(args.out), out)
    return _emit(
        {
            "command": "classify",
            "records": len(enriched),
            "parser_version": FORGE_PARSER_VERSION,
        }
    )


def cmd_generate_skeletons(args: argparse.Namespace) -> int:
    payload = _read_json(Path(args.in_file))
    routed = []
    for record in _require_records(payload, source="classified file"):
        if record.get("state") != ScaffoldingState.STRUCTURED.value:
            raise CliError(
                f"generate-skeletons expects STRUCTURED records "
                f"(got {record.get('state')} for {record.get('intake_id')})"
            )
        features = record["features"]
        classification_data = record["classification"]
        from .classify import Classification as _Classification

        classification = _Classification(
            intake_id=classification_data["intake_id"],
            schema=classification_data.get("schema", ""),
            capability_families=classification_data.get("capability_families", []),
            adversarial_tags=classification_data.get("adversarial_tags", []),
            expected_decision_pretags=classification_data.get("expected_decision_pretags", []),
            taxonomy_version=classification_data.get("taxonomy_version", "q6-taxonomy-0.1.0"),
        )
        skeleton = generate_skeleton(
            record["intake_id"],
            record.get("card_name_hint", ""),
            features,
            classification,
            capability_override=args.capability,
        )
        parsed = record["parsed"]
        state, reasons = route_state(
            ambiguous=bool(parsed.get("ambiguous")),
            unsupported=list(parsed.get("unsupported", [])),
            features=features,
            classification=classification,
            skeleton=skeleton,
            provenance_complete=bool(record.get("provenance")),
        )
        record = dict(record)
        record["skeleton"] = skeleton.as_dict()
        record["skeleton_id"] = skeleton.skeleton_id
        record["capability"] = skeleton.capability_under_test
        record["capability_families"] = classification.capability_families
        record["state"] = state.value
        record["reasons"] = reasons
        record["stage_history"] = [
            *record.get("stage_history", []),
            ScaffoldingState.SKELETON_GENERATED.value,
            state.value,
        ]
        validate_output(record, artifact="routed-record")
        routed.append(record)
    routed.sort(key=lambda r: r["intake_id"])
    slim = [
        {
            "intake_id": r["intake_id"],
            "card_name_hint": r.get("card_name_hint", ""),
            "state": r["state"],
            "reasons": r["reasons"],
            "capability": r.get("capability", "UNCLUSTERED"),
            "capability_families": r.get("capability_families", []),
            "skeleton_id": r.get("skeleton_id", ""),
            "input_hash": r["provenance"]["input_hash"],
            "source_commit": r["provenance"]["source_commit"],
            "source_path": r["provenance"]["source_path"],
            "source_corpus": r["provenance"]["source_corpus"],
            "source_repository": r["provenance"]["source_repository"],
            "skeleton": r["skeleton"],
            "provenance_complete": True,
        }
        for r in routed
    ]
    out = {"tool_version": Q6_SCAFFOLDING_VERSION, "records": slim}
    validate_output(out, artifact="skeleton-batch")
    _write_json(Path(args.out), out)
    return _emit({"command": "generate-skeletons", "records": len(slim)})


def cmd_build_review_queues(args: argparse.Namespace) -> int:
    payload = _read_json(Path(args.in_file))
    records = _require_records(payload, source="skeleton file")
    queues = build_queues(records)
    out = {
        "tool_version": Q6_SCAFFOLDING_VERSION,
        "queues": queues,
        "summary": queue_summary(queues),
    }
    validate_output(out, artifact="queue-batch")
    _write_json(Path(args.out), out)
    return _emit({"command": "build-review-queues", **out["summary"]})


def cmd_build_manifest(args: argparse.Namespace) -> int:
    payload = _read_json(Path(args.in_file))
    records = _require_records(payload, source="skeleton file")
    queues_payload = _read_json(Path(args.queues)) if args.queues else {"queues": {}}
    queues = queues_payload.get("queues", {})
    configuration = {}
    if args.configuration:
        configuration = _read_json(Path(args.configuration))
        if not isinstance(configuration, dict):
            raise CliError("configuration file must be a JSON object")
        try:
            reject_promotion_fields(configuration, source="configuration")
        except PromotionRejected as exc:
            raise CliError(str(exc)) from exc
    manifest = build_manifest(
        records,
        queues,
        configuration=configuration,
        manifest_id=args.manifest_id,
    )
    out = manifest.as_dict()
    _write_json(Path(args.out), out)
    return _emit(
        {
            "command": "build-manifest",
            "manifest_id": manifest.manifest_id,
            "manifest_hash": manifest.manifest_hash,
            "records": len(records),
        }
    )


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = _read_json(Path(args.manifest))
    try:
        verify_manifest(manifest)
    except ValueError as exc:
        raise CliError(str(exc)) from exc
    known_states = {s.value for s in ScaffoldingState}
    records = manifest.get("records", [])
    for entry in records:
        if entry.get("state") not in known_states:
            raise CliError(
                f"unknown scaffolding state {entry.get('state')!r} for {entry.get('intake_id')}"
            )
    try:
        validate_output(manifest, artifact="campaign-manifest")
    except PromotionRejected as exc:
        raise CliError(str(exc)) from exc
    if args.queues:
        queues_payload = _read_json(Path(args.queues))
        queues = queues_payload.get("queues", {})
        known_ids = {r["intake_id"] for r in records}
        for name, items in queues.items():
            for item in items:
                if item.get("intake_id") not in known_ids:
                    raise CliError(
                        f"queue {name} references unknown intake {item.get('intake_id')}"
                    )
        try:
            validate_output(queues_payload, artifact="queue-batch")
        except PromotionRejected as exc:
            raise CliError(str(exc)) from exc
    return _emit(
        {
            "command": "validate",
            "result": "VALID",
            "manifest_hash": manifest.get("manifest_hash"),
            "records": len(records),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="q6-scaffolding",
        description="Q6 actual-card scaffolding pipeline (preparation only; "
        "structurally incapable of behavior PASS).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", help="ingest external inputs under source locks")
    p.add_argument("--inputs", required=True, help="JSON {inputs:[...]} spec file")
    p.add_argument("--corpus-root", default=None, help="root for relative input paths")
    p.add_argument("--out", required=True, help="write intake records JSON here")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("classify", help="parse + capability-cluster intake records")
    p.add_argument("--in", dest="in_file", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("generate-skeletons", help="generate valueless skeletons + route states")
    p.add_argument("--in", dest="in_file", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--capability", default=None)
    p.set_defaults(func=cmd_generate_skeletons)

    p = sub.add_parser("build-review-queues", help="build deterministic review queues")
    p.add_argument("--in", dest="in_file", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build_review_queues)

    p = sub.add_parser("build-manifest", help="build reproducible campaign manifest")
    p.add_argument("--in", dest="in_file", required=True)
    p.add_argument("--queues", default=None)
    p.add_argument("--configuration", default=None)
    p.add_argument("--manifest-id", default="q6-campaign")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build_manifest)

    p = sub.add_parser("validate", help="verify manifest, states, schemas, gates")
    p.add_argument("--manifest", required=True)
    p.add_argument("--queues", default=None)
    p.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CliError as exc:
        print(f"q6-scaffolding: FAIL-CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

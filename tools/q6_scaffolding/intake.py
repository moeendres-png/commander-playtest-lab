"""Deterministic actual-card intake pipeline.

Ingests one external card-script input plus its source lock and produces an
intake record at state INTAKE_ONLY. Intake performs no parsing, no
classification, and no judgment: it stamps provenance, screens for
promotion/contamination fields (fail closed), and detects duplicate or
conflicting identities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import SCHEMA_INTAKE_RECORD_V1
from .gate import PromotionRejected, reject_promotion_fields, validate_output
from .provenance import (
    Provenance,
    ProvenanceError,
    SourceLock,
    build_provenance,
    check_input_hash,
)
from .states import ScaffoldingState


class IntakeError(ValueError):
    """Raised for duplicate/conflicting identities or malformed intake input."""


@dataclass
class IntakeRecord:
    """A single ingested card input awaiting parsing."""

    intake_id: str
    card_name_hint: str
    provenance: dict
    raw_text: str
    state: str = ScaffoldingState.INTAKE_ONLY.value
    schema: str = SCHEMA_INTAKE_RECORD_V1
    ambiguity_flags: list = field(default_factory=list)
    unsupported_flags: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _card_name_hint(raw_text: str) -> str:
    """Best-effort display hint only (authoritative identity comes later).

    The first ``Name:`` line is used when present; otherwise empty. This is
    a convenience label, never an identity: identity is the intake ID.
    """
    for line in raw_text.splitlines():
        if line.startswith("Name:"):
            return line.split(":", 1)[1].strip()
        if line.startswith("Name$"):
            return line.split("$", 1)[1].strip() if "$" in line else ""
    return ""


def intake_card(
    raw: bytes,
    lock: SourceLock,
    *,
    expected_hash: str | None = None,
    extra_metadata: dict | None = None,
) -> IntakeRecord:
    """Ingest one card-script input under a validated source lock.

    Fail-closed on: missing source-lock metadata, hash mismatch, promotion
    fields in operator-supplied metadata, or undecodable input bytes.
    """
    provenance: Provenance = build_provenance(lock, raw)
    if expected_hash is not None:
        check_input_hash(raw, expected_hash, source=lock.source_path)
    if extra_metadata:
        try:
            reject_promotion_fields(extra_metadata, source="intake metadata")
        except PromotionRejected as exc:
            raise IntakeError(str(exc)) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntakeError(f"input is not valid UTF-8: {lock.source_path} ({exc})") from exc
    record = IntakeRecord(
        intake_id=provenance.intake_id,
        card_name_hint=_card_name_hint(text),
        provenance=provenance.as_dict(),
        raw_text=text,
    )
    validate_output(record.as_dict(), artifact="intake-record")
    return record


def detect_conflicts(records: list[IntakeRecord]) -> None:
    """Fail closed on duplicate conflicting identities.

    Two records sharing an intake ID must carry byte-identical content (same
    input hash); two records sharing a source path must carry the same input
    hash. Anything else is a conflicting identity and raises
    :class:`IntakeError`.
    """
    by_id: dict[str, IntakeRecord] = {}
    by_path: dict[str, IntakeRecord] = {}
    for record in records:
        seen = by_id.get(record.intake_id)
        if seen is not None:
            if seen.provenance["input_hash"] != record.provenance["input_hash"]:
                raise IntakeError(
                    f"conflicting identity {record.intake_id}: same intake ID "
                    "with different content hashes "
                    f"({seen.provenance['input_hash']} vs "
                    f"{record.provenance['input_hash']})"
                )
            if seen.provenance["source_path"] != record.provenance["source_path"]:
                raise IntakeError(
                    f"conflicting identity {record.intake_id}: same intake ID "
                    "from different source paths "
                    f"({seen.provenance['source_path']} vs "
                    f"{record.provenance['source_path']})"
                )
            raise IntakeError(
                f"duplicate intake identity {record.intake_id} ({record.provenance['source_path']})"
            )
        by_id[record.intake_id] = record
        path = record.provenance["source_path"]
        other = by_path.get(path)
        if other is not None and (
            other.provenance["input_hash"] != record.provenance["input_hash"]
            or other.provenance["source_commit"] != record.provenance["source_commit"]
        ):
            raise IntakeError(
                f"conflicting source path {path}: different content or pin "
                f"({other.provenance['input_hash']} vs "
                f"{record.provenance['input_hash']})"
            )
        by_path.setdefault(path, record)


def record_identity_chain(record: IntakeRecord) -> dict:
    """Return the stable identity triple for manifest/queue linkage."""
    if not record.intake_id:
        raise ProvenanceError("intake record has no intake ID")
    return {
        "intake_id": record.intake_id,
        "card_name_hint": record.card_name_hint,
        "input_hash": record.provenance["input_hash"],
        "source_commit": record.provenance["source_commit"],
        "source_path": record.provenance["source_path"],
    }

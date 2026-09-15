# WS218 CANONICALIZATION_CONTRACT — `semantic-canonical-1.0.0`

Implementation: `semantic_replay/canonicalization.py`. UTF-8 bytes of
`json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False,
allow_nan=False)`. Ordered sequences stay ordered; unordered sets are
sorted by semantic fingerprint by the caller before hashing. Timestamps,
wall-clock diagnostics, request ids, and process-local identities are
excluded by projection (never generic-stripped). Free-text redaction
(`redact_text`/`redact_choice_text`) removes `object_id='...'` attributes,
bare UUIDs, and GameLog `[xxx]` short-ids while preserving Rules text
(lineage: production `_semantic_text`/`redactObjectIds`/`choiceText`;
twin-stability proven). Version persisted in every digest input; unit
tests pin byte stability, NaN rejection, and twin redaction equality.

Machine companion: `CANONICALIZATION_CONTRACT.json`.

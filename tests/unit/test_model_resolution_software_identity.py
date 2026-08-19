from __future__ import annotations

from commander_lab.model_resolution_software_identity import (
    MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION,
    model_resolution_software_identity,
    model_resolution_software_scope,
)


def test_model_resolution_software_identity_is_content_addressed(repo_root) -> None:
    identity = model_resolution_software_identity(repo_root)

    assert identity["schema_version"] == "1.1.0"
    assert identity["identity_version"] == MODEL_RESOLUTION_SOFTWARE_IDENTITY_VERSION
    assert len(identity["resolution_source_manifest_sha256"]) == 64
    assert len(identity["measurement_entrypoint_blob_sha1"]) == 40
    assert len(identity["package_manifest_blob_sha1"]) == 40
    assert len(identity["identity_sha256"]) == 64
    assert identity["scope_paths"] == list(model_resolution_software_scope())
    assert set(identity["source_objects"]) == set(model_resolution_software_scope())
    assert all(len(value) == 40 for value in identity["source_objects"].values())
    assert (
        identity["freshness_semantics"]
        == "content_addressed_resolution_relevant_software_not_commit_identity"
    )


def test_model_resolution_software_scope_separates_structural_from_external_gameplay() -> None:
    scope = set(model_resolution_software_scope())

    assert "src/commander_lab/engine/structural" in scope
    assert "src/commander_lab/whole_deck" in scope
    assert "src/commander_lab/agents" in scope
    assert "src/commander_lab/models/structural.py" in scope
    assert "src/commander_lab/models/pilots.py" in scope
    assert "src/commander_lab/model_resolution_measurement.py" in scope
    assert "src/commander_lab/models/game.py" not in scope
    assert "src/commander_lab/models/engine_runtime.py" not in scope
    assert "src/commander_lab/models/rules.py" not in scope
    assert "src/commander_lab/engine/rules" not in scope


def test_model_resolution_software_identity_is_stable_within_same_checkout(repo_root) -> None:
    first = model_resolution_software_identity(repo_root)
    second = model_resolution_software_identity(repo_root)

    assert first == second

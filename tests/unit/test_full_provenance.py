from __future__ import annotations
import json
from pathlib import Path
import pytest
from commander_lab.models import SourceRecord, SourceType, ProvenanceGraph, ArtifactRecord, DerivedDataRecord, TransformationRecord, SupersessionRecord
from commander_lab.provenance import ProvenanceStore, ProvenanceError
import hashlib

def test_synthetic_assumption_not_observed():
    with pytest.raises(ValueError):
        SourceRecord(source_id="s", source_type=SourceType.SYNTHETIC_ASSUMPTION, title="x", content_hash="0"*64, observed=True)

def test_duplicate_and_cycle_rejected(tmp_path: Path):
    store=ProvenanceStore(tmp_path)
    a=ArtifactRecord(artifact_id="a",artifact_type="x",title="a",content_hash="0"*64,derived_from=("b",))
    b=ArtifactRecord(artifact_id="b",artifact_type="x",title="b",content_hash="1"*64,derived_from=("a",))
    with pytest.raises(ProvenanceError): store.validate(ProvenanceGraph(graph_id="g",artifacts=[a,b]))

def test_hash_change_detected(tmp_path: Path):
    f=tmp_path/"x.txt"; f.write_text("a")
    src=SourceRecord(source_id="s",source_type=SourceType.GOOGLE_DRIVE_FILE,title="x",url_or_drive_id="x.txt",content_hash=hashlib.sha256(f.read_bytes()).hexdigest())
    store=ProvenanceStore(tmp_path); store.save(ProvenanceGraph(graph_id="g",sources=[src]))
    assert store.verify_source_hash("s")["status"]=="match"
    f.write_text("b")
    assert store.verify_source_hash("s")["status"]=="changed"

def test_lower_authority_cannot_supersede():
    with pytest.raises(ValueError): SupersessionRecord(supersession_id="x",old_id="a",new_id="b",reason="x",authority_rank_old=5,authority_rank_new=4)

def test_project_graph_valid(repo_root: Path):
    store=ProvenanceStore(repo_root); graph=store.load(); store.validate(graph)
    assert store.audit_claims()["passed"]

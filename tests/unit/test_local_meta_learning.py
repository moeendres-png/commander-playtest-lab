from pathlib import Path
import json
import pytest
from commander_lab.local_meta import LocalMetaStore, LocalMetaConflictError
from commander_lab.models import LocalGameRecord, LocalGameParticipant, LocalCardObservation, ObservationStatus

def game(gid='g1', correction_of=None):
    return LocalGameRecord(game_id=gid,pod_size=2,correction_of=correction_of,participants=(LocalGameParticipant(participant_id='a',public_label='self',commander='Korvold',seat_position=0),LocalGameParticipant(participant_id='b',public_label='cosmic',commander='Cosmic Spider-Man',seat_position=1,visible_cards=(LocalCardObservation(card_name='Known Card',status=ObservationStatus.DIRECTLY_OBSERVED),))))

def test_duplicate_and_correction_rules(tmp_path:Path):
    s=LocalMetaStore(tmp_path); assert s.ingest(game())['appended']; assert s.ingest(game())['duplicate_identical']
    changed=game(); changed.notes='changed'
    with pytest.raises(LocalMetaConflictError): s.ingest(changed)
    assert s.ingest(game('g1-c1','g1'))['appended']

def test_unknown_card_does_not_create_complete_list(tmp_path:Path):
    s=LocalMetaStore(tmp_path); s.ingest(game()); p=s.update_profile('cosmic','Cosmic Spider-Man')
    assert p.sample_size==1 and [x.card_name for x in p.observed_cards]==['Known Card']
    assert not p.official_precon_superseded

def test_small_sample_is_shrunk(tmp_path:Path):
    s=LocalMetaStore(tmp_path); s.ingest(game()); p=s.update_profile('cosmic','Cosmic Spider-Man')
    assert p.interaction_density.observations==1
    assert p.interaction_density.shrunk_frequency != p.interaction_density.raw_frequency

def test_empty_project_profiles_are_insufficient(repo_root:Path):
    s=LocalMetaStore(repo_root); info=s.inspect(); assert info['real_game_count']==0; assert info['data_quality']=='insufficient_data'

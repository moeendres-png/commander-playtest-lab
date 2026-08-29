import json, subprocess, sys
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parents[2]

def j(p): return json.loads((ROOT/p).read_text())

def test_schemas_are_valid_and_manifest_validates():
    for p in [
        'qualification/protocol/ws10r/rules_service_protocol_v1.schema.json',
        'qualification/protocol/ws10r/rsp_semantics_v1.schema.json',
        'qualification/protocol/ws10r/architecture_freeze_contract_v1.schema.json',
        'qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json',
        'qualification/evidence/normalized_evidence_v1.schema.json',
        'qualification/evidence/candidate_result_v1.schema.json']:
        Draft202012Validator.check_schema(j(p))
    Draft202012Validator(j('qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json')).validate(j('qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json'))

def test_common_fixture_minimum_and_29_cards():
    m=j('qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json'); ids={x['fixture_id'] for x in m['fixtures']}
    for pc in [2,3,4,5]: assert f'PLAYER_COUNT_{pc}P' in ids
    assert len([x for x in m['fixtures'] if x['category']=='actual_card'])==29
    for req in ['WS05-MP-PRIO-3','WS05-MP-PRIO-5','WS05-MP-TRIG-3','WS05-MP-TRIG-5','WS05-CMD-PARTNER-TAX','WS05-CMD-ZONE-GY-YES','WS05-CMD-ZONE-HAND-YES']:
        assert req in ids

def test_missing_provider_is_not_run_and_blocks_admission(tmp_path):
    out=tmp_path/'results.json'
    subprocess.run([sys.executable,str(ROOT/'qualification/harness.py'),'run','--candidate','none','--source-lock',str(ROOT/'qualification/WS17_SOURCE_LOCK.json'),'--manifest',str(ROOT/'qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json'),'--output',str(out)],check=True)
    r=json.loads(out.read_text()); assert all(x['verdict']=='NOT_RUN' for x in r['fixture_results'])
    adm=tmp_path/'adm.json'; md=tmp_path/'adm.md'; sha='a'*40
    subprocess.run([sys.executable,str(ROOT/'qualification/harness.py'),'aggregate','--manifest',str(ROOT/'qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json'),'--results',str(out),'--admitted-main-sha',sha,'--actual-sha',sha,'--output',str(adm),'--md-output',str(md)],check=True)
    assert json.loads(adm.read_text())['production_admission']=='FAIL'

def test_exact_main_mismatch_blocks_admission(tmp_path):
    adm=tmp_path/'adm.json'
    subprocess.run([sys.executable,str(ROOT/'qualification/harness.py'),'aggregate','--manifest',str(ROOT/'qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json'),'--results',str(ROOT/'qualification/evidence/BASELINE_COMMON_RESULTS.json'),'--admitted-main-sha','a'*40,'--actual-sha','b'*40,'--output',str(adm)],check=True)
    assert json.loads(adm.read_text())['production_admission']=='FAIL'
    assert json.loads(adm.read_text())['blocking_results'][0]['fixture_id']=='EXACT_MAIN_SHA'

def test_no_required_obligation_accepts_unknown_partial_not_run():
    c=j('qualification/obligations/QUALIFICATION_OBLIGATION_CATALOG_v1.json')
    for o in c['obligations']:
        if o['required']:
            assert 'UNKNOWN' not in o['satisfying_verdicts']; assert 'PARTIAL' not in o['satisfying_verdicts']; assert 'NOT_RUN' not in o['satisfying_verdicts']

def test_production_admission_md_is_generated_shape():
    assert 'generated from `PRODUCTION_ADMISSION.json`' in (ROOT/'qualification/aggregate/PRODUCTION_ADMISSION.md').read_text()


def test_candidate_reports_account_for_every_common_fixture():
    manifest=j('qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json')
    expected={x['fixture_id'] for x in manifest['fixtures']}
    schema=j('qualification/evidence/candidate_result_v1.schema.json')
    for name in ['xmage','forge','phase_rs','argentum']:
        report=j(f'qualification/evidence/candidates/{name}.json')
        Draft202012Validator(schema).validate(report)
        results=report['fixture_results']
        assert {x['fixture_id'] for x in results} == expected
        assert len(results) == len(expected)
        assert all(x['verdict']=='NOT_RUN' for x in results)
        assert all(x['omission_reason_code'] in {'PROTOCOL_ADAPTER_MISSING','REMEDIATION_REQUIRED'} for x in results)

def test_active_deck_denominators_are_exact():
    d=j('qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json')
    assert len(d['current_rogshai_unique_identity_list']) == 87
    assert len(d['current_kaervek_unique_identity_list']) == 77
    assert len(d['rogshai_kaervek_shared_identity_list']) == 10
    assert d['active_deck_source_locks']['rogshai']['git_blob'] == '4db4174011e6ea0b07196e68165aa4549cff1971'
    assert d['active_deck_source_locks']['kaervek']['git_blob'] == 'beebc3cf50e32b29db5c1e594821f754da69249d'

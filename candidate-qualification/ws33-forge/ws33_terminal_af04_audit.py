#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, re
from collections import Counter

CONTRACT_VERSION='commander-lab.semantic-fixture-materialization/1.0.2'
WS32_COMMIT='038d0f38635eecee4e331c99af41f148de267a26'
WS32_TREE='0d160128119f2bad30b220a17c43419b50b7edbe'
WS32_BUNDLE='61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b'
FORGE_COMMIT='1e604105f9e279331063824943b9222b6589f5d8'
FORGE_TREE='994976e06aaf99b807646b60b1aa2ac9f7703df4'
FORGE_VERSION='2.0.15-SNAPSHOT'
FRESH_MASTER='c817743ecbda4a4983a4246a13375d1a6adf8a4e'
FRESH_MASTER_TREE='d0ff27956e44ffb76baa11be1645675e1b013a3a'
BASELINE_RUN=33573571385
BASELINE_JOB=100072542091
BASELINE_ARTIFACT=9825831255
BASELINE_ARTIFACT_SHA256='c8b191bad743ee0e8847671cda89a3da50c9b88accb0b92ba23a6ec4b39009f8'


def txt(p: pathlib.Path) -> str:
    return p.read_text(encoding='utf-8')

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--materialization',type=pathlib.Path,required=True)
    ap.add_argument('--mapping',type=pathlib.Path,required=True)
    ap.add_argument('--generated-provider',type=pathlib.Path,required=True)
    ap.add_argument('--pinned-combat',type=pathlib.Path,required=True)
    ap.add_argument('--pinned-human-controller',type=pathlib.Path,required=True)
    ap.add_argument('--pinned-damage-ui',type=pathlib.Path,required=True)
    ap.add_argument('--fresh-combat',type=pathlib.Path,required=True)
    ap.add_argument('--fresh-human-controller',type=pathlib.Path,required=True)
    ap.add_argument('--output-dir',type=pathlib.Path,required=True)
    args=ap.parse_args()

    mat=json.loads(txt(args.materialization))
    assert mat['schema_version']==CONTRACT_VERSION
    assert len(mat['records'])==135
    ids={r['fixture_id'] for r in mat['records']}
    owned=sorted({x for x in ids if not x.startswith('CARD_')} | {'CARD_02'})
    assert len(owned)==107
    by={r['fixture_id']:r for r in mat['records']}

    mapping=json.loads(txt(args.mapping))
    callbacks=mapping['callbacks']
    counts=Counter(c['classification'] for c in callbacks)
    assert len(callbacks)==109, len(callbacks)
    assert counts['FAIL_CLOSED_UNSUPPORTED']==82, counts
    assign=[c for c in callbacks if c['name']=='assignCombatDamage']
    assert len(assign)==1 and assign[0]['classification']=='FAIL_CLOSED_UNSUPPORTED', assign

    provider=txt(args.generated_provider)
    assert 'throw failClosed("assignCombatDamage")' in provider
    assert 'RemoteClientGuiGame' not in provider
    assert not re.search(r'import\s+forge\.(?:ai|gui)', provider)

    combat=txt(args.pinned_combat)
    human=txt(args.pinned_human_controller)
    damage_ui=txt(args.pinned_damage_ui)
    assert combat.count('getController().assignCombatDamage(') >= 2
    assert 'getGui().assignCombatDamage' in human
    required_ui_tokens=[
        'attackerHasDeathtouch', 'attackerHasInfect', 'attackerHasTrample',
        'overrideCombatantOrder', 'getDamageToKill', 'canAssignTo', 'checkDamageQueue'
    ]
    missing=[x for x in required_ui_tokens if x not in damage_ui]
    assert not missing, missing

    fresh_combat=txt(args.fresh_combat)
    fresh_human=txt(args.fresh_human_controller)
    assert fresh_combat.count('getController().assignCombatDamage(') >= 2
    assert 'getGui().assignCombatDamage' in fresh_human

    defect={
      'defect_id':'WS33-FORGE-PROVIDER-AF04-001',
      'taxonomy':'FORGE_PROVIDER_DEFECT',
      'severity':'TERMINAL_STOP',
      'gate':'AF04',
      'failure_signature':'COMBAT_DAMAGE_LEGALITY_LIVES_IN_CONTROLLER_GUI_NOT_RULES_CORE_LEGAL_OPTION_API',
      'production_reachable':True,
      'current_provider_behavior':'FAIL_CLOSED_UNSUPPORTED',
      'pinned_core_callsite':'Combat -> assigningPlayer.getController().assignCombatDamage(...)',
      'pinned_human_path':'PlayerControllerHuman -> getGui().assignCombatDamage(...)',
      'gui_legality_dimensions':required_ui_tokens,
      'forbidden_remediations':['forge_gui_default','forge_ai','provider_legality_reconstruction','pilot_legality_reconstruction','silent_default','random_distribution'],
      'why_terminal':(
        'WS-33 requires the Forge Rules Core to be sole legality authority and the provider to expose complete engine-legal options. '
        'Pinned Forge delegates discretionary combat-damage construction to PlayerController and the human implementation contains '
        'legality-sensitive damage-assignment logic in GUI code. The isolated GPL provider intentionally excludes Forge GUI/AI and '
        'currently hard-fails this callback. Recreating lethal/order/deathtouch/trample/infect assignment legality in the provider '
        'would create a second rules engine; using GUI/AI is explicitly forbidden. Closing this boundary therefore requires a Forge-core '
        'legal-option/validation API or upstream/core refactor, which is outside WS-33 authorization.'
      ),
      'fresh_master_same_boundary':True,
    }

    ledger=[]
    for fid in owned:
        r=by[fid]
        if fid=='PLAYER_COUNT_2P':
            status='BASELINE_RUNTIME_NO_SUCCESSOR_CREDIT'
            attempted=True
            reason='Native baseline executed, but WS-32 normalized constructed-state digest equality was not emitted/proven; zero successor credit.'
            provenance={'run_id':BASELINE_RUN,'job_id':BASELINE_JOB,'artifact_id':BASELINE_ARTIFACT,'artifact_sha256':BASELINE_ARTIFACT_SHA256}
        else:
            status='NOT_RUN_AFTER_AF04_STOP_CONDITION'
            attempted=False
            reason='WS-33 hard stop after production-reachable AF04 legality-boundary defect.'
            provenance=None
        ledger.append({
          'fixture_id':fid,
          'fixture_family':r['fixture_family'],
          'execution_entry_mode':r['execution_entry_mode'],
          'materialization_digest':r['materialization_digest'],
          'requested_state_digest':r['requested_state_digest'],
          'attempted':attempted,
          'status':status,
          'behavioral_credit':False,
          'defect_taxonomy':None,
          'blocked_by':'WS33-FORGE-PROVIDER-AF04-001' if status.startswith('NOT_RUN_AFTER') else None,
          'reason':reason,
          'runtime_provenance':provenance,
        })

    out={
      'schema_version':'commander-lab.ws33-terminal-af04-audit/1.0.0',
      'terminal_status':'STOPPED_FAIL_CLOSED',
      'workstream_terminal':True,
      'architecture_freeze_declared':False,
      'stop_condition':'PRODUCTION_DECISION_PATH_CANNOT_BE_EXTERNALIZED_SAFELY_WITH_RULES_CORE_AS_SOLE_LEGALITY_AUTHORITY',
      'source_lock':{
        'ws32':{'contract_version':CONTRACT_VERSION,'commit':WS32_COMMIT,'tree':WS32_TREE,'bundle_digest':WS32_BUNDLE,'owned_denominator':107},
        'forge_selected':{'commit':FORGE_COMMIT,'tree':FORGE_TREE,'version':FORGE_VERSION},
        'forge_fresh_master':{'commit':FRESH_MASTER,'tree':FRESH_MASTER_TREE,'same_af04_boundary':True},
      },
      'provider_callback_counts':dict(counts),
      'defect':defect,
      'gate_results':{
        'AF04':'FAIL_TERMINAL_FORGE_PROVIDER_DEFECT',
        'AF05':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
        'AF06':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
        'AF08':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
        'AF09':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
        'REPLAY_RNG':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
        'CARD_02':'NOT_RUN_AFTER_AF04_STOP_CONDITION',
      },
      'successor_corpus':{
        'denominator':107,
        'PASS':0,
        'BASELINE_RUNTIME_NO_SUCCESSOR_CREDIT':1,
        'NOT_RUN_AFTER_AF04_STOP_CONDITION':106,
        'successor_runtime_credit':0,
      },
      'baseline_evidence':{'run_id':BASELINE_RUN,'job_id':BASELINE_JOB,'artifact_id':BASELINE_ARTIFACT,'artifact_sha256':BASELINE_ARTIFACT_SHA256},
    }
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'WS33_TERMINAL_AF04_AUDIT.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (args.output_dir/'WS33_SUCCESSOR_RESULT_LEDGER.json').write_text(json.dumps({
      'schema_version':'commander-lab.ws33-result-ledger/1.0.0',
      'terminal_status':out['terminal_status'],
      'stop_condition':out['stop_condition'],
      'denominator':107,
      'counts':out['successor_corpus'],
      'rows':ledger,
    },indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'terminal_status':out['terminal_status'],'AF04':out['gate_results']['AF04'],'denominator':107,'pass':0,'unsupported_callbacks':counts['FAIL_CLOSED_UNSUPPORTED']},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())

from __future__ import annotations

import sys
from pathlib import Path

from commander_lab.engine.rules import (
    ExternalRulesAdapter,
    load_interaction_catalog,
    validate_with_external_adapter,
)
from commander_lab.models import RulesBackend, ValidationLevel


def test_legacy_or_mock_adapter_cannot_promote_observation_to_rules_engine_validated(
    repo_root: Path, tmp_path: Path
) -> None:
    script = tmp_path / "fake_forge_bridge.py"
    script.write_text(
        """
import json, sys
sessions = {}
for raw in sys.stdin:
    req = json.loads(raw)
    rid, method, params = req['request_id'], req['method'], req.get('params', {})
    if method == 'probe':
        result = {
          'backend':'forge','availability':'available','backend_version':'fake-forge-1',
          'command':[],
          'capabilities':{
            'deck_loading':True,'commander_games':True,'deterministic_seed':False,
            'reproducible_starting_state':True,'scenario_injection':True,
            'legal_action_query':True,'action_submission':True,'event_logs':True,
            'game_logs':True,'multiplayer':True,'maximum_players':8,'notes':[]
          },'details':[]
        }
    elif method == 'create_scenario':
        scenario = params['scenario']; sid='s1'; sessions[sid]=scenario
        result = {
          'backend':'forge','session_id':sid,'game_id':scenario['state']['game_id'],
          'state':scenario['state'],'seed':scenario['state']['seed'],'deck_handles':[],
          'scenario_id':scenario['scenario_id'],'created_from':'scenario'
        }
    elif method == 'get_result':
        scenario = sessions[params['session_id']]
        result = {
          'backend':'forge','session_id':params['session_id'],'completed':True,
          'final_state':scenario['state'],
          'normalized_result':{'commander_tax':4,'total_cast_cost':9,'legal':True},
          'validation_level':'rules_engine_validated','backend_version':'fake-forge-1',
          'warnings':[]
        }
    elif method == 'shutdown':
        print(json.dumps({'request_id':rid,'ok':True,'result':{'shutdown':True}}), flush=True)
        break
    else:
        print(json.dumps({'request_id':rid,'ok':False,'error':{'code':'unsupported','message':method}}), flush=True)
        continue
    print(json.dumps({'request_id':rid,'ok':True,'result':result}), flush=True)
""".strip(),
        encoding="utf-8",
    )
    adapter = ExternalRulesAdapter(
        RulesBackend.FORGE, (sys.executable, str(script)), cwd=repo_root
    )
    try:
        case = load_interaction_catalog(
            repo_root / "data/rules/project_critical_interactions.json"
        )[0]
        import pytest
        with pytest.raises(RuntimeError, match="unverified|legacy|external rules engine"):
            validate_with_external_adapter(case, adapter)
    finally:
        adapter.close()

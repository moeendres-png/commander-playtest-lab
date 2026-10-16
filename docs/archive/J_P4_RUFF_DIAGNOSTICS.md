# J-P4 Ruff diagnostics

## ruff check
```text
F401 [*] `collections.defaultdict` imported but unused
 --> scripts/run_j_p4_sensitivity.py:7:25
  |
5 | import json
6 | import random
7 | from collections import defaultdict
  |                         ^^^^^^^^^^^
8 | from pathlib import Path
  |
help: Remove unused import: `collections.defaultdict`
  |
6 | import random
  - from collections import defaultdict
7 | from pathlib import Path
  |

SIM300 [*] Yoda condition detected
  --> tests/golden/test_j_p4_pilot_quality.py:48:16
   |
46 |         strategy_cases = [case for case in cases if case.strategy == strategy]
47 |         covered = {dimension for case in strategy_cases for dimension in case.expected_utility_dimensions}
48 |         assert REQUIRED_DIMENSIONS <= covered
   |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
49 |     assert any(case.state.hidden_information_uncertainty >= 0.8 for case in cases)
50 |     assert any(case.state.opponent_intent_uncertainty >= 0.8 for case in cases)
   |
help: Rewrite as `covered >= REQUIRED_DIMENSIONS`
   |
47 |         covered = {dimension for case in strategy_cases for dimension in case.expected_utility_dimensions}
   -         assert REQUIRED_DIMENSIONS <= covered
48 +         assert covered >= REQUIRED_DIMENSIONS
49 |     assert any(case.state.hidden_information_uncertainty >= 0.8 for case in cases)
   |

Found 2 errors.
[*] 2 fixable with the `--fix` option.
```

## ruff format --check
```text
unformatted: File would be reformatted
   --> scripts/run_j_p4_sensitivity.py:199:46
    |
198 |                 "bad_rate": sum(row["outcome"] == "bad" for row in subset) / n,
    -                 "critical_failure_rate": sum(
    -                     row["outcome"] == "critical_failure" for row in subset
    -                 )
199 +                 "critical_failure_rate": sum(row["outcome"] == "critical_failure" for row in subset)
200 |                 / n,
--------------------------------------------------------------------------------
213 |             "bad_rate": sum(row["outcome"] == "bad" for row in subset) / n,
    -             "critical_failure_rate": sum(
    -                 row["outcome"] == "critical_failure" for row in subset
    -             )
214 +             "critical_failure_rate": sum(row["outcome"] == "critical_failure" for row in subset)
215 |             / n,
--------------------------------------------------------------------------------
240 |     gate = all(
    -         metrics["contract_preserving_rate"] >= 0.95
    -         and metrics["critical_failure_rate"] == 0.0
241 +         metrics["contract_preserving_rate"] >= 0.95 and metrics["critical_failure_rate"] == 0.0
242 |         for levels in summary.values()
    |

unformatted: File would be reformatted
   --> src/commander_lab/agents/pilots.py:696:22
    |
695 |             bonus -= denial_penalty
    -             bonus -= state.boardwipe_risk * float(
    -                 action.metadata.get("increases_board_exposure", 0.45)
    -             ) * 1.1
696 +             bonus -= (
697 +                 state.boardwipe_risk
698 +                 * float(action.metadata.get("increases_board_exposure", 0.45))
699 +                 * 1.1
700 +             )
701 |         if CardRole.SACRIFICE_OUTLET in action.roles:
--------------------------------------------------------------------------------
867 |                 bonus -= 1.4 + exposure_ratio * 1.2
    -             bonus -= state.boardwipe_risk * float(
    -                 action.metadata.get("increases_board_exposure", 0.45)
    -             ) * 1.2
868 +             bonus -= (
869 +                 state.boardwipe_risk
870 +                 * float(action.metadata.get("increases_board_exposure", 0.45))
871 +                 * 1.2
872 +             )
873 |             if ishai and ishai.next_cost >= 7.0 and not protected_window:
    |

unformatted: File would be reformatted
  --> tests/golden/test_j_p4_pilot_quality.py:30:16
   |
29 |     assert all(case.preferred_action_classes for case in cases)
   -     assert all(case.bad_action_classes or case.critical_failure_actions or case.acceptable_action_classes for case in cases)
30 +     assert all(
31 +         case.bad_action_classes or case.critical_failure_actions or case.acceptable_action_classes
32 +         for case in cases
33 +     )
34 |     results = run_golden_cases(cases, source=str(path.relative_to(repo_root)))
--------------------------------------------------------------------------------
49 |         strategy_cases = [case for case in cases if case.strategy == strategy]
   -         covered = {dimension for case in strategy_cases for dimension in case.expected_utility_dimensions}
50 +         covered = {
51 +             dimension for case in strategy_cases for dimension in case.expected_utility_dimensions
52 +         }
53 |         assert REQUIRED_DIMENSIONS <= covered
   |

3 files would be reformatted, 407 files already formatted
```

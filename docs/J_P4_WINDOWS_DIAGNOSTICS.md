# J-P4 Windows pytest diagnostics

```text
.......................s.......F........................................ [ 20%]
........................................................................ [ 41%]
........................................................................ [ 61%]
........................................................................ [ 82%]
..............................................................           [100%]
================================== FAILURES ===================================
______ test_j_p4_holdout_bytes_match_pre_tuning_seal_without_evaluating _______
tests\golden\test_j_p4_pilot_quality.py:66: in test_j_p4_holdout_bytes_match_pre_tuning_seal_without_evaluating
    assert hashlib.sha256(holdout.read_bytes()).hexdigest() == seal["sha256"]
E   AssertionError: assert 'd7c4b8bb8063...cc63308b96dc7' == '426e184e2dd3...55ab16b0859f2'
E     
E     - 426e184e2dd3ade9245dd4756ee58e796841e1fa71237c3239b55ab16b0859f2
E     + d7c4b8bb806334020935fffc608895ab8635b02bd9a34e41c4ecc63308b96dc7
=========================== short test summary info ===========================
SKIPPED [1] tests\differential\test_phase6_differential.py:53: requires configured XMage or Forge differential command
FAILED tests/golden/test_j_p4_pilot_quality.py::test_j_p4_holdout_bytes_match_pre_tuning_seal_without_evaluating - AssertionError: assert 'd7c4b8bb8063...cc63308b96dc7' == '426e184e2dd3...55ab16b0859f2'
  
  - 426e184e2dd3ade9245dd4756ee58e796841e1fa71237c3239b55ab16b0859f2
  + d7c4b8bb806334020935fffc608895ab8635b02bd9a34e41c4ecc63308b96dc7
1 failed, 348 passed, 1 skipped in 241.02s (0:04:01)
```

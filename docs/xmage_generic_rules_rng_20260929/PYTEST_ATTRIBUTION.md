# Full Python suite attribution

Local runs in the Claude Code cloud container: Python 3.12 venv from `requirements/lock.txt`, `pytest -q tests`.

| Run | Head | Result |
|---|---|---|
| Baseline | `origin/main` `afe09c61` (clean detached worktree) | 103 failed, 2082 passed, 10 skipped |
| This change | `d5faf6f4` working tree | 115 failed, 2070 passed, 10 skipped |

Every baseline failure also fails on this change, and there are no baseline-only failures. The 12 failures that appear only on this change are accounted for as follows:

- `tests/qualification/test_ws17_qualification.py::test_all_ws17_hash_manifests_verify_and_cover_changed_artifacts` failed because the handoff was first placed under the sealed `qualification/` tree. It was moved to `docs/` and passes on the pushed head.
- The other 11 ran while the baseline suite was running in parallel, and they are resource or timing sensitive (subprocess servers, MCP stdio, isolated-process self-test). All 11 pass when re-run alone on this change's head:

- `tests/integration/test_multi_pilot_tools.py::test_ensemble_variant_and_report_tools_do_not_apply_deck_changes`
- `tests/integration/test_multi_pilot_tools.py::test_pilot_toolchain_smoke_and_reproducibility`
- `tests/integration/test_opponent_ensemble_tools.py::test_opponent_ensemble_toolchain_reports_structural_uncertainty`
- `tests/integration/test_phase10_acceptance.py::test_api_self_test_runs_in_isolated_process`
- `tests/integration/test_phase10_acceptance.py::test_phase10_smoke_never_claims_external_validation`
- `tests/integration/test_phase12_17_mcp_stdio.py::test_real_stdio_mcp_roundtrip`
- `tests/integration/test_phase5_demo.py::test_phase5_demo_end_to_end`
- `tests/integration/test_phase5_server.py::test_function_tool_server_lists_and_invokes_tools`
- `tests/integration/test_priority_prefix_and_frontier_1180.py::test_frontier_reports_cut_composition_and_preserves_candidate_recall`
- `tests/regressions/test_public_diagnose_cohort_forwarding.py::test_public_diagnose_forwards_cohort_context`
- `tests/unit/test_audit_e_runtime_hygiene.py::test_phase86_audit_keeps_checkout_clean`

The 103 baseline failures are environmental to this container: Foundry launcher, safe-push, bubblewrap and git-remote tooling, plus git-ancestry checks (`test_technical_truth`) on a checkout without the full history. They are not attributable to this change.

Classification: `DIRECTLY_VERIFIED` (local). CI on the PR head is the authoritative gate.

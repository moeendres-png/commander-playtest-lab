# ChatGPT Tool Usage

This document describes the local Commander Lab tool API. It does not define which execution environment owns project work.

For execution routing, the canonical policy is [`PROJECT_EXECUTION_POLICY.md`](PROJECT_EXECUTION_POLICY.md).

There are exactly three project execution paths:

- normal ChatGPT Sol High for coordination, research, architecture, review, adjudication, and all useful pre-work before Work;
- OpenCode Go with Muse Spark 1.3 Contributor for repository implementation, debugging, CI, qualification, audits and mechanical repository work;
- ChatGPT Work with Astra only as an exceptional minimal fallback after `WORK_NECESSITY = PASS`.

Muse Spark 1.3 is one AI model and must not be split into separate Muse and Spark resources.

The only authorized OpenCode model is `opencode-go/muse-spark-1.3-contributor`. Allowed effort is `high` or `xhigh` only, with `high` as both the minimum and the project default. `medium` and all lower effort variants are not authorized for Commander Simulator Next OpenCode execution. Use High for all other project OpenCode work, including helpers and bounded/mechanical tasks. Prefer XHigh when task difficulty or length materially benefits from it, including difficult implementation, long-running autonomous campaigns, difficult debugging/root-cause analysis, complex multi-file remediation, provider/Rules-Core boundary work, qualification campaigns, semantic integration, and difficult evidence reconciliation. The repository root `opencode.json` enforces the current OpenCode provider/model/effort policy.

For ChatGPT Work, Astra Medium is the default. Astra High is allowed only rarely when the exact irreducible Work-only operation materially requires more reasoning than Medium. Work must be token-efficient: normal Sol High should complete all useful research, source locking, adjudication, planning, narrowing and context reduction before handoff. Work receives only the minimum exact inputs, already-proven facts, blocker, required output, hard gates and stop condition needed to perform the operation. Work must not repeat completed Sol/OpenCode work or expand into broad discovery. Control returns to normal Sol High immediately after the irreducible operation is complete.

Do not interpret the local API or Agents SDK examples below as a requirement to use ChatGPT Work or as authorization to substitute another OpenCode model, lower OpenCode reasoning effort, or a broader Work scope than the canonical policy permits.

## Local API

Start the local API:

```bash
commander-lab serve-tools --host 127.0.0.1 --port 8765 --root .
```

Discover tools:

```bash
curl -s http://127.0.0.1:8765/v1/tools
```

Invoke a tool:

```bash
curl -s -X POST \
  http://127.0.0.1:8765/v1/tools/validate_deck:invoke \
  -H 'content-type: application/json' \
  -d '{"arguments":{"deck_id":"korvold/current"}}'
```

Run the bounded API demo:

```bash
curl -s -X POST \
  'http://127.0.0.1:8765/v1/demos/phase10?iterations=4&seed=20260805&workers=1'
```

## OpenAI Agents SDK integration

For a live OpenAI Agents SDK workflow, install `.[openai]`, configure `OPENAI_API_KEY`, and call `POST /v1/workflows:run`. The orchestrator uses Deck Analyst, Simulation Analyst and Red-Team Reviewer as tool-using specialists. Large simulations remain subject to approval and hard iteration limits.

This API integration is an implementation capability, not project execution-routing authority. Project work must still follow `PROJECT_EXECUTION_POLICY.md`.

# ChatGPT Tool Usage

This document describes the local Commander Lab tool API. It does not define which execution environment owns project work.

For execution routing, the canonical policy is [`PROJECT_EXECUTION_POLICY.md`](PROJECT_EXECUTION_POLICY.md).

There are exactly three project execution paths:

- normal ChatGPT Sol High for coordination, research, architecture, review and adjudication;
- OpenCode Go with Muse Spark 1.3 Contributor for repository implementation, debugging, CI, qualification, audits and mechanical repository work;
- ChatGPT Work with Sol Medium only as an exceptional minimal fallback after `WORK_NECESSITY = PASS`.

Muse Spark 1.3 is one AI model and must not be split into separate Muse and Spark resources.

The only authorized OpenCode model is `opencode-go/muse-spark-1.3-contributor`. Allowed effort is `medium`, `high`, or `xhigh`, with `high` as the project default. The repository root `opencode.json` enforces the current OpenCode provider/model policy.

Do not interpret the local API or Agents SDK examples below as a requirement to use ChatGPT Work or as authorization to substitute another OpenCode model.

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

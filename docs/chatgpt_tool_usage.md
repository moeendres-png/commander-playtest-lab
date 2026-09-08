# ChatGPT Tool Usage

This document describes the local Commander Lab tool API. It does **not** define which ChatGPT execution environment should own project work.

For execution routing, the canonical policy is [`PROJECT_EXECUTION_POLICY.md`](PROJECT_EXECUTION_POLICY.md).

In particular:

- normal ChatGPT **Sol High** is the default coordinator/reasoning environment;
- **OpenCode** is the preferred repository implementation/runtime worker;
- **Muse** is the preferred independent audit/review worker;
- **Spark 1.3** is preferred for bounded mechanical work;
- **ChatGPT Work is exceptional only**, normally Sol Medium, and requires `WORK_NECESSITY = PASS` before use.

Do not interpret the local API or Agents SDK examples below as a requirement to use ChatGPT Work.

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

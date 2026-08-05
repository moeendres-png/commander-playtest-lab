# ChatGPT Tool Usage

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

For a live OpenAI Agents SDK workflow, install `.[openai]`, configure `OPENAI_API_KEY`, and call `POST /v1/workflows:run`. The orchestrator uses Deck Analyst, Simulation Analyst and Red-Team Reviewer as tool-using specialists. Large simulations remain subject to approval and hard iteration limits.

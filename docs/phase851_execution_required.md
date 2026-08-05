# Phase 8.5.1: required real execution

Phase 8.5.1 is **not complete** in the sandbox. DNS to GitHub and Maven Central fails, and Maven/Docker are absent. No XMage build, Java bridge, external handshake, action loop or multiplayer game has been executed.

## Fastest reliable route

Use GitHub Actions from a GitHub repository containing this project:

1. Push the repository without secrets.
2. Open **Actions → External XMage Integration → Run workflow**.
3. Keep the full XMage commit SHA unless release verification shows a mismatch.
4. The workflow will deliberately fail at `Require real provider-specific bridge` until `engine-bridge/` contains the real XMage API binding.
5. Implement the bridge in a network-enabled Codex/local environment after inspecting the pinned XMage source. Do not use the Tactical Oracle implementation in the bridge.
6. Rerun until build, handshake, action loop, four-player Commander game, replay and critical scenarios all pass.
7. Download `external-engine-evidence` and import the evidence into `artifacts/external_engine/`.

## Local alternative

```bash
unzip commander-playtest-lab-phase86-repository.zip
cd commander-playtest-lab
git checkout phase/8.6-system-audit
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,api,openai]'
./scripts/bootstrap_engine_linux.sh xmage
# Implement/build engine-bridge against the downloaded pinned source.
export ENGINE_PROVIDER=xmage
export ENGINE_MODE=external
export ALLOW_TACTICAL_ORACLE_FALLBACK=false
export ENGINE_START_COMMAND='java -jar /absolute/path/to/bridge.jar'
./scripts/verify_engine.sh
commander-lab validate-engine-phase85
```

The final status may be changed to `external_engine_ready` only after real evidence exists. A mock, fixture bridge or Tactical Oracle is insufficient.

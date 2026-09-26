# Installation

## Python

Requirements:

- Python 3.12 or newer;
- Git;
- approximately 2 GiB free space for the Python project and run artifacts.

Recommended installation:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,api]'
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,api]"
```

OpenAI-backed workflows additionally require the `openai` extra and `OPENAI_API_KEY`:

```bash
python -m pip install -e '.[openai]'
```

The structural simulator, tactical oracle, CLI demo and local API demo do not require an API key.

## Verification

```bash
commander-lab doctor --root .
pytest -q
commander-lab accept-phase10 --iterations 12 --workers 2 --root .
```

## External rules engine

The external XMage bridge is not validated in the current runtime. Follow `docs/phase851_execution_required.md`. Do not set `external_engine_validation_pending=false` until the real handshake, action loop, multiplayer game and replay gates pass.

# J-P6 Fresh-Install CLI Boundary Fix

The Release Artifacts fresh-wheel roundtrip found a real packaging/usability defect: the base wheel intentionally excludes the optional FastAPI dependency, but `commander-lab --help` imported `commander_lab.api` eagerly and therefore failed with `ModuleNotFoundError: fastapi`.

J-P6 corrected the dependency boundary rather than making FastAPI mandatory:

- the CLI no longer imports `commander_lab.api.create_app` at module import time;
- `serve-tools` imports both `uvicorn` and `create_app` lazily only when that optional API command is invoked;
- missing API dependencies retain the explicit guidance to install `commander-playtest-lab[api]`;
- the Release Artifacts roundtrip continues to install the **base wheel** and execute `commander-lab --help`, so this boundary is tested in the actual minimal installation surface.

This change does not modify simulator, pilot, optimizer, Objective, Holdout, deck, inventory, purchase or allocation semantics. It is a packaging/CLI usability hardening fix.

# WS223 PYTHONHASHSEED Policy

- Every workflow that executes Python tests, qualification, conformance, or
  measurements sets top-level `env: PYTHONHASHSEED: "0"` (15/16 workflows).
- Exempt: `.github/workflows/opencode.yml` (agent lane; no Python
  execution). Any future workflow without Python execution joins the
  exemption only with the same documented reason.
- Explicit non-claim: `PYTHONHASHSEED` governs CPython hash iteration only.
  It does not seed, order, or otherwise control JVM Rules randomness, which
  remains engine-owned (XMage `GameRandom` seeding per WS208/WS212).
- Enforcement: `tests/unit/test_ws223_environment_identity.py` fails any
  non-exempt workflow missing the pin or using a different value.

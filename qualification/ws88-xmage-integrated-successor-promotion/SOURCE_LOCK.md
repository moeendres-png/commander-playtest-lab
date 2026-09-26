# WS88 Source Lock

## CPL repository

- Repository: `moeendres-png/commander-playtest-lab`
- Audit base: `f0e314e5cd250f2a0d79ba50f33c87435807be89`
- Audit-base tree: `80982bd46cb5e270569f7748cd6f9b20ebae8b10`
- Branch: `ws88/xmage-integrated-successor-promotion-20260913`
- Evidence head: the WS88 migration commit on this branch (heavy runtime
  evidence ran on its tree); validated head is recorded in
  `WORKSTREAM_STATE.yaml` (`validated_head`) after the manifest reseal.
- Preserved from main: WS79 corrected-H01 authority, WS80 fail-closed callback
  integration, WS78/WS86 Foundry token-economy tooling (no file from those
  surfaces modified except authorized pin constants plus ledger addenda).

## XMage engine

- Current runtime pin (pre-WS88): `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`
- Accepted qualification ancestor: `7135d5e85ddb4c8aa4b49b4192ca51947c822704`
- Accepted technical successor (Coordinator input):
  `cfc36f445f917f101fa2ed588770e043f53bc44c`
- Successor tree: `e51ba998d35decff087b5bebfdc001e62e8d33e4`
- Remote branch: `ws85/xmage-cr61412-future-state-hardening-20260913`
  (head equals the successor; 17 ahead / 0 behind the old runtime pin).
- Repository: `https://github.com/moeendres-png/mage.git`

## Accepted WS85 claim (taken as input, not re-decided)

- `H01_CORRECTED = PASS`
- `CR61412_LAYER6_ABILITY_REMOVAL_SUPPORT = PASS`
- `FULL_CR61412_FUTURE_STATE_SUPPORT = UNKNOWN` (never upgraded here)

## Source-truth rule applied

`config/rules_engines.json` is the current machine-readable pin authority.
Historical reports remain historical and were not edited.

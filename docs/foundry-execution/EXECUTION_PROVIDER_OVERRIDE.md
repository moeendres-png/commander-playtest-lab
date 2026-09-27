# Legacy explicit execution-provider override

Status: COMPATIBILITY ONLY.

Current normal execution routing is defined by
`docs/foundry-execution/EXECUTION_MODEL_ROUTING.md`:

- Space Bunny Free MAX — preferred;
- Muse Spark 1.3 Contributor XHIGH — supported alternate.

Both normal lanes use `opencode-go` and are selected by the Foundry launcher's
`--execution-model bunny|muse` plus the lane-matching effort.

The historical `--execution-provider zen` path remains only for bounded reproducibility
of work that explicitly depended on the older Zen override. It is not an automatic
fallback and is not the preferred way to run Space Bunny or Muse.

Never combine model/provider selection implicitly. Quota, auth, transport or catalog
failure does not select another lane.

All existing source-lock, writer-lock, state-path, permission, privacy and publication
gates remain in force. The legacy Zen path does not change Rules Provider selection or
Architecture Freeze state.

# ARCHITECTURE FREEZE CONTRACT — WS-10R / AF 1.1.0

All AF00–AF11 gates are mandatory. `PASS` is the only satisfying verdict. `UNKNOWN`, `NOT_RUN`, `PARTIAL`, `UNSUPPORTED` and `FAIL` block Freeze eligibility. `NOT_APPLICABLE` is not valid for these twelve required architecture gates.

The contract is candidate-neutral. A clean build, import success, green upstream CI, process exit 0, or code presence does not substitute for required runtime behavior. A provider is Freeze-eligible only when every AF gate is `PASS` against the same canonical denominators, authority lock, fixture manifest and evidence schema.

This workstream never selects an architecture winner; `architecture_winner` is fixed to `false`.

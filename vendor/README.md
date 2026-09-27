# Offline engine inputs

Place an already downloaded checkout in `vendor/engine-source/<provider>/` or an
already built, independently verified bridge/runtime in
`vendor/engine-binaries/<provider>/`. Nothing in this directory is treated as
verified merely because it exists. `scripts/verify_engine.sh` checks provider,
protocol, version and capability identity before the runtime can become healthy.

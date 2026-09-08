#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
WS47_TREE = "f596c54d2cb229b9827c6c94a278175e8312c65c"
WS47_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
WS47_FILE_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"


def replace_const(text: str, name: str, value: str, *, required: bool = True) -> str:
    pattern = rf'^{name} = "[^"]+"$'
    repl = f'{name} = "{value}"'
    text, count = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE)
    if required and count != 1:
        raise SystemExit(f"WS48_RUNNER_CONST_PATCH_CARDINALITY:{name}:{count}")
    return text


def patch_noecho(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    # Keep local variable names stable to minimize inherited-code churn; bind their values to WS47.
    text = replace_const(text, "WS44_SCHEMA", WS47_SCHEMA)
    text = replace_const(text, "WS44_BUNDLE", WS47_BUNDLE)
    text = replace_const(text, "WS44_FILE_SHA", WS47_FILE_SHA)
    text = text.replace("WS44 materialization digest mismatch", "WS47 materialization digest mismatch")
    text = text.replace("WS44 identity mismatch", "WS47 identity mismatch")
    text = text.replace('"commander-lab.ws45-strict-no-request-echo-runtime/1.0.0"', '"commander-lab.ws48-strict-no-request-echo-runtime/1.0.0"')
    text = text.replace('"ws44":{', '"ws47":{')
    text = text.replace('"ws45-noecho-"', '"ws48-noecho-"')
    path.write_text(text, encoding="utf-8")


def patch_construction(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_const(text, "WS44_COMMIT", WS47_COMMIT)
    text = replace_const(text, "WS44_TREE", WS47_TREE)
    text = replace_const(text, "WS44_SCHEMA", WS47_SCHEMA)
    text = replace_const(text, "WS44_BUNDLE", WS47_BUNDLE)
    text = replace_const(text, "WS44_FILE_SHA", WS47_FILE_SHA)
    text = text.replace("immutable WS44 materialization file digest mismatch", "immutable WS47 materialization file digest mismatch")
    text = text.replace("immutable WS44 materialization identity mismatch", "immutable WS47 materialization identity mismatch")
    text = text.replace("WS44 provider denominator is not exact 107 unique IDs", "WS47 provider denominator is not exact 107 unique IDs")
    text = text.replace('"commander-lab.ws45-forge-fresh-construction-107/1.0.0"', '"commander-lab.ws48-forge-fresh-construction-107/1.0.0"')
    text = text.replace('"ws44": {', '"ws47": {')
    text = text.replace('"ws45-construct-"', '"ws48-construct-"')
    text = text.replace('"no_request_echo_authority": ["WS45_CHECKPOINT_19_STRICT_NO_REQUEST_ECHO_PASS", "NATURAL_LIFECYCLE_NO_ECHO_EXTENSION"]', '"no_request_echo_authority": ["WS48_FRESH_STRICT_NO_REQUEST_ECHO_PASS"]')
    text = text.replace('print(f"WS45 CONSTRUCTION ', 'print(f"WS48 CONSTRUCTION ')
    path.write_text(text, encoding="utf-8")


def assert_no_stale_v104(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for forbidden in (
        "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54",
        "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35",
        "commander-lab.semantic-fixture-materialization/1.0.4",
    ):
        if forbidden in text:
            raise SystemExit(f"WS48_STALE_V104_IDENTITY_REMAINS:{path}:{forbidden}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--noecho-runner", type=Path, required=True)
    ap.add_argument("--construction-runner", type=Path)
    args = ap.parse_args()
    patch_noecho(args.noecho_runner)
    assert_no_stale_v104(args.noecho_runner)
    if args.construction_runner is not None:
        patch_construction(args.construction_runner)
        assert_no_stale_v104(args.construction_runner)
    print("WS48_V105_RUNNER_IDENTITY_REBIND=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

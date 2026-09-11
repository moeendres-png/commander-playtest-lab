#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


def render(source: str) -> str:
    source = replace_once(
        source,
        "    private Ws23ForgeBootstrap() {}\n",
        "    private Ws23ForgeBootstrap() {}\n\n"
        "    private static long configuredRulesSeed() {\n"
        '        String raw = System.getenv("COMMANDER_LAB_FORGE_RULES_SEED");\n'
        "        if (raw == null || raw.isBlank()) {\n"
        "            return QUALIFICATION_SEED;\n"
        "        }\n"
        "        try {\n"
        "            return Long.parseLong(raw);\n"
        "        } catch (NumberFormatException e) {\n"
        '            throw new IllegalStateException("COMMANDER_LAB_FORGE_RULES_SEED must be an integer", e);\n'
        "        }\n"
        "    }\n",
        "bootstrap constructor anchor",
    )
    source = replace_once(
        source,
        "        MyRandom.setRandom(new Random(QUALIFICATION_SEED));",
        "        MyRandom.setRandom(new Random(configuredRulesSeed()));",
        "rules seed initialization",
    )
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rendered = render(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()

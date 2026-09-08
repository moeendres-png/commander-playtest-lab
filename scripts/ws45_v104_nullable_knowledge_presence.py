#!/usr/bin/env python3
import argparse
from pathlib import Path

DEC_BLOCK = '''    private static String dec(String s) {
        return URLDecoder.decode(s == null ? "" : s, StandardCharsets.UTF_8);
    }
'''
DEC_BLOCK_PATCHED = '''    private static String dec(String s) {
        return URLDecoder.decode(s == null ? "" : s, StandardCharsets.UTF_8);
    }

    private static String optDec(String s) {
        return s == null || s.isEmpty() ? null : dec(s);
    }
'''
OLD_FACT = '''                    dec(r[4]), dec(r[5]), dec(r[6]), optInt(r[7]), optInt(r[8]), optBool(r[9]), optBool(r[10]), dec(r[11]),
'''
NEW_FACT = '''                    optDec(r[4]), optDec(r[5]), optDec(r[6]), optInt(r[7]), optInt(r[8]), optBool(r[9]), optBool(r[10]), optDec(r[11]),
'''


def replace_once(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one patch target, found {count}")
    return text.replace(old, new, 1), True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict-java", type=Path, required=True)
    args = ap.parse_args()

    p = args.strict_java
    text = p.read_text()
    changed = False

    text, c = replace_once(text, DEC_BLOCK, DEC_BLOCK_PATCHED, "WS45_V104_OPTDEC_HELPER")
    changed |= c
    text, c = replace_once(text, OLD_FACT, NEW_FACT, "WS45_V104_KNOWLEDGE_FACT_NULLABLES")
    changed |= c

    if 'if (r.length != 15) throw fail("WS45_KNOWLEDGE_FACT_ARITY:" + r.length);' not in text:
        raise SystemExit("WS45_V104_KNOWLEDGE_FACT_ARITY_GUARD_MISSING")
    if "optDec(r[4])" not in text or "optDec(r[11])" not in text:
        raise SystemExit("WS45_V104_NULLABLE_KNOWLEDGE_PATCH_INCOMPLETE")

    if changed:
        p.write_text(text)
        print("WS45_V104_NULLABLE_KNOWLEDGE_PRESENCE=PASS")
    else:
        print("WS45_V104_NULLABLE_KNOWLEDGE_PRESENCE=ALREADY_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

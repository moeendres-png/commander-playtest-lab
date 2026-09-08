#!/usr/bin/env python3
import argparse
from pathlib import Path

# Raw literal is intentional: generated Java contains the two-character escape sequences \\n and \\t.
ROWS_BLOCK = r'''    private static List<String[]> rows(String envName) {
        List<String[]> out = new ArrayList<>();
        String raw = decodeB64Env(envName);
        if (raw.isEmpty()) return out;
        for (String line : raw.split("\\n")) {
            if (line.isEmpty()) continue;
            out.add(line.split("\\t", -1));
        }
        return out;
    }
'''
ROWS_PATCHED = ROWS_BLOCK + '''
    private static Map<Integer,Integer> knowledgeLibraryMinimums() {
        Map<Integer,Integer> out = new HashMap<>();
        for (String[] r : rows("COMMANDER_LAB_WS45_KNOWLEDGE_FACT_ROWS_B64")) {
            if (r.length != 15) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_LIBRARY_CAPACITY_KNOWLEDGE_ARITY:" + r.length);
            }
            if (!"KNOWN_LIBRARY_RANGE".equals(r[0])) continue;
            String pid = dec(r[3]);
            if (!pid.matches("P[1-6]")) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_LIBRARY_CAPACITY_BAD_PLAYER:" + pid);
            }
            int seat = Integer.parseInt(pid.substring(1));
            int start = Integer.parseInt(r[7]);
            int count = Integer.parseInt(r[8]);
            if (start < 0 || count < 0) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS45_LIBRARY_CAPACITY_NEGATIVE_RANGE:" + pid);
            }
            out.merge(seat, start + count, Math::max);
        }
        return out;
    }
'''

BUILD_HEAD = '''        Map<String,Integer> ids = new HashMap<>();
        int next = 1000;
        for (ObjSpec s : objectSpecs) ids.put(s.semanticId, next++);

        for (int seat = 1; seat <= game.getPlayers().size(); seat++) {
'''
BUILD_HEAD_PATCHED = '''        Map<String,Integer> ids = new HashMap<>();
        int next = 1000;
        for (ObjSpec s : objectSpecs) ids.put(s.semanticId, next++);
        Map<Integer,Integer> libraryMinimums = knowledgeLibraryMinimums();

        for (int seat = 1; seat <= game.getPlayers().size(); seat++) {
'''

VALUES_BLOCK = '''                List<String> values = new ArrayList<>();
                for (ObjSpec s : specs) values.add(cardEntry(s, ids));
                lines.add(prefix + zone + "=" + String.join(";", values));
'''
VALUES_PATCHED = '''                List<String> values = new ArrayList<>();
                for (ObjSpec s : specs) values.add(cardEntry(s, ids));
                if ("library".equals(zone)) {
                    int minimum = libraryMinimums.getOrDefault(seat, 0);
                    while (values.size() < minimum) {
                        int opaqueIndex = values.size();
                        int opaqueId = 900000 + seat * 1000 + opaqueIndex;
                        values.add("Forest|Id:" + opaqueId);
                    }
                }
                lines.add(prefix + zone + "=" + String.join(";", values));
'''

REGISTER_BLOCK = '''        Set<String> names = new HashSet<>();
        for (ObjSpec s : objectSpecs) names.add(s.name);
        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) if (p.length >= 4) names.add(dec(p[3]));
        registerCardRules(names);
'''
REGISTER_PATCHED = '''        Set<String> names = new HashSet<>();
        for (ObjSpec s : objectSpecs) names.add(s.name);
        for (String[] p : rows("COMMANDER_LAB_WS40_STACK_SPECS_B64")) if (p.length >= 4) names.add(dec(p[3]));
        if (!knowledgeLibraryMinimums().isEmpty()) names.add("Forest");
        registerCardRules(names);
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
    ap.add_argument("--state-java", type=Path, required=True)
    args = ap.parse_args()
    p = args.state_java
    text = p.read_text()
    changed = False
    for old,new,label in [
        (ROWS_BLOCK, ROWS_PATCHED, "WS45_LIBRARY_CAPACITY_ROWS"),
        (BUILD_HEAD, BUILD_HEAD_PATCHED, "WS45_LIBRARY_CAPACITY_BUILD_HEAD"),
        (VALUES_BLOCK, VALUES_PATCHED, "WS45_LIBRARY_CAPACITY_VALUES"),
        (REGISTER_BLOCK, REGISTER_PATCHED, "WS45_LIBRARY_CAPACITY_REGISTER"),
    ]:
        text,c = replace_once(text,old,new,label)
        changed |= c
    required = [
        'knowledgeLibraryMinimums()',
        '"KNOWN_LIBRARY_RANGE".equals(r[0])',
        'values.add("Forest|Id:" + opaqueId)',
        'if (!knowledgeLibraryMinimums().isEmpty()) names.add("Forest")',
    ]
    if not all(x in text for x in required):
        raise SystemExit("WS45_V104_OPAQUE_LIBRARY_CAPACITY_PATCH_INCOMPLETE")
    if changed:
        p.write_text(text)
        print("WS45_V104_OPAQUE_LIBRARY_CAPACITY=PASS")
    else:
        print("WS45_V104_OPAQUE_LIBRARY_CAPACITY=ALREADY_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

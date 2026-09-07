#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

OLD='str(bool(o["emit_semantic"])).lower()])'
NEW='str(bool(o["emit_semantic"])).lower(),enc(o.get("card_lineage_id"))])'

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--runner',type=Path,required=True); a=ap.parse_args()
    s=a.runner.read_text(encoding='utf-8')
    if NEW in s:
        print('WS45_NOECHO_LINEAGE_TRANSPORT=ALREADY_APPLIED'); return
    if s.count(OLD)!=1:
        raise SystemExit(f'expected exactly one object-row transport target, got {s.count(OLD)}')
    a.runner.write_text(s.replace(OLD,NEW,1),encoding='utf-8')
    print('WS45_NOECHO_LINEAGE_TRANSPORT=PASS')
if __name__=='__main__': main()

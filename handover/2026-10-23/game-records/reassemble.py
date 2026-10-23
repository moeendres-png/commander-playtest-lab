#!/usr/bin/env python3
"""Rebuild the original files from manifest.json and verify their sha256.
Usage: python reassemble.py [target_dir]  (default: ./restored)"""
import base64, gzip, hashlib, json, os, sys

here = os.path.dirname(os.path.abspath(__file__))
out_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'restored')
manifest = json.load(open(os.path.join(here, 'manifest.json')))
bad = 0
for entry in manifest['files']:
    parts = entry['stored_as']
    blob = b''.join(open(os.path.join(here, p), 'rb').read() for p in parts)
    if '.b64' in parts[0]:
        blob = gzip.decompress(base64.b64decode(blob))
    ok = hashlib.sha256(blob).hexdigest() == entry['sha256'] and len(blob) == entry['bytes']
    if not ok:
        bad += 1
        print('MISMATCH', entry['path'])
        continue
    dest = os.path.join(out_root, entry['path'])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, 'wb').write(blob)
print(f"done: {len(manifest['files']) - bad}/{len(manifest['files'])} files restored and verified")

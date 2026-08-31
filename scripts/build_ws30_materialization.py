#!/usr/bin/env python3
from pathlib import Path
import base64,hashlib,shutil,zlib
EXPECTED_SHA256='6a5fe0bfcb73c08deef9ab8ce68d1ce76e00cd755b3293772bdd4fe4a1d5f773'
path=Path(__file__)
chunk_dir=path.parent/'ws30_bootstrap_chunks'
data=''.join(p.read_text(encoding='ascii') for p in sorted(chunk_dir.glob('*.txt')))
raw=zlib.decompress(base64.b64decode(data))
assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA256
path.write_bytes(raw)
shutil.rmtree(chunk_dir)
exec(compile(raw,str(path),'exec'),{'__name__':'__main__','__file__':str(path)})

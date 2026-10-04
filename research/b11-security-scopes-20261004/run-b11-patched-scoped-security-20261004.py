from pathlib import Path
path=Path('/mnt/c/Users/moeen/.codex/.chatgpt-projects/g-p-6a9197e782048191a98ff349f1c39525/work-evidence/run-b11-scoped-security-20261004.py')
code=path.read_text().replace('B11-live-scopes','B11-patched-scopes').replace('b11-product-20261004','b11-product-patched-20261004')
exec(compile(code,str(path), 'exec'))

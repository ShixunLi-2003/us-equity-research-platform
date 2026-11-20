"""Create a source-only ZIP from an explicit directory and extension allowlist."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
allowed_dirs = {'src', 'cpp', 'tests', 'docs', 'scripts', '.github'}
allowed_suffixes = {'.py', '.cpp', '.hpp', '.md', '.toml', '.yml', '.txt'}
files = []
for p in root.rglob('*'):
    if not p.is_file():
        continue
    rel = p.relative_to(root)
    if '_native' in rel.parts or '__pycache__' in rel.parts:
        continue
    if len(rel.parts) == 1 and p.name in {'README.md', 'pyproject.toml', 'CMakeLists.txt', '.gitignore'}:
        files.append(p)
    elif rel.parts[0] in allowed_dirs and p.suffix in allowed_suffixes:
        files.append(p)
out = root / 'dist'
out.mkdir(exist_ok=True)
manifest = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
with zipfile.ZipFile(out / 'us-equity-research-platform.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for p in files:
        archive.write(p, p.relative_to(root))
    archive.writestr('SOURCE_MANIFEST.json', json.dumps(manifest, indent=2))
print('Source files:', len(files))
print(out / 'us-equity-research-platform.zip')

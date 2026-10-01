"""Relabel the already verified native ARM installer for the friend's M4 Mac."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path('native-output')
DEST = Path('release-files')
EXPECTED = 'cee634483bcb6799e3c7e704de193f163aa0114f003616ef33fabd5fb1231c06'
NAME = 'SOL.01-macOS-Apple-M4-0.1.0.dmg'

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

images = list(ROOT.rglob('*.dmg'))
assert len(images) == 1, images
image = images[0]
assert image.name == 'SOL.01-macOS-arm64-0.1.0.dmg'
assert digest(image) == EXPECTED, 'Native installer SHA-256 mismatch'
assert image.with_suffix('.dmg.sha256').read_text().split()[0] == EXPECTED
provenances = [p for p in ROOT.rglob('BUILD_PROVENANCE.json') if (p.parent / 'BUNDLE_SMOKE_TEST.json').is_file()]
assert len(provenances) == 1, provenances
build = provenances[0].parent
provenance = json.loads(provenances[0].read_text())
assert provenance['architecture'] == 'arm64'
assert provenance['minimum_macos'] == '15.7'
for report_name, frozen in [('SOURCE_SMOKE_TEST.json', False), ('BUNDLE_SMOKE_TEST.json', True)]:
    report = json.loads((build / report_name).read_text())
    assert report['result'] == 'PASS' and report['frozen'] == frozen
    assert report['mac_integration']['test_host'] == 'darwin'
    assert report['mac_integration']['native_macos_verified']
DEST.mkdir()
shutil.copy2(image, DEST / NAME)
assert digest(DEST / NAME) == EXPECTED
(DEST / (NAME + '.sha256')).write_text(f'{EXPECTED}  {NAME}\n')
print(f'Verified Apple M4 installer: {NAME}; SHA-256 {EXPECTED}')

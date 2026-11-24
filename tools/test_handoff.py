import json
from pathlib import Path
import tempfile
import unittest
from build_handoff import safe_relative, verify, sha


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aegis_source_manifest_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'AEGIS/example.py'
        self.source.parent.mkdir()
        self.source.write_text('# synthetic test\n', encoding='utf-8')
        self.manifest = dict(schema='aegis-source-handoff-v1', model_included=False,
                             runtime_data_included=False, files=[dict(path='AEGIS/example.py',
                             size=self.source.stat().st_size, sha256=sha(self.source))])
        self.save()

    def save(self):
        (self.root / 'MANIFEST.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_intact_then_tampered(self):
        verify(self.root)
        self.source.write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError): verify(self.root)

    def test_unlisted_runtime_rejected(self):
        (self.root / 'private.db').write_bytes(b'')
        with self.assertRaises(ValueError): verify(self.root)

    def test_missing_and_duplicate_rejected(self):
        self.manifest['files'] *= 2
        self.save()
        with self.assertRaises(ValueError): verify(self.root)
        self.manifest['files'] = self.manifest['files'][:1]
        self.save()
        self.source.unlink()
        with self.assertRaises(ValueError): verify(self.root)

    def test_paths_and_runtime_boundaries(self):
        for path in ['../AEGIS/x.py', '/AEGIS/x.py', 'AEGIS/../private.py', 'AEGIS/.env',
                     'AEGIS-AI/weights/best.pt', 'AEGIS/node_modules/a.js', 'D:/AEGIS/a.py',
                     'AEGIS\\x.py', 'AEGIS/.git/config', 'AEGIS/private.sqlite3']:
            with self.subTest(path=path), self.assertRaises(ValueError): safe_relative(path)


if __name__ == '__main__': unittest.main()

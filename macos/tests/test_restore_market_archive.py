"""Small fixtures exercise public-archive boundaries and byte verification."""
import hashlib
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restore_market_archive import restore_archive, safe_path
from market_data import MANIFEST_NAME, YEAR_FOLDER


class RestoreArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol01-archive-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "fixture.zip"
        self.destination = self.root / "macos"
        self.content = {"day.dbn.zst": b"ordinary-day", "bad/retained.dbn.zst": b"retained-original"}
        self.manifest = {
            "schema_version": 1, "dataset_id": "fixture-dataset", "folder": YEAR_FOLDER,
            "files": {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in self.content.items()},
            "file_count": len(self.content), "total_bytes": sum(map(len, self.content.values())),
        }

    def create_archive(self, *, extra=None, content_override=None, symlink_member=None):
        manifest_bytes = json.dumps(self.manifest).encode()
        items = {"market_data/" + MANIFEST_NAME: manifest_bytes}
        items.update({"market_data/" + YEAR_FOLDER + "/" + name: content for name, content in self.content.items()})
        if extra:
            items.update(extra)
        if content_override:
            items.update(content_override)
        with zipfile.ZipFile(self.archive, "w") as bundle:
            for name, content in items.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = ((stat.S_IFLNK | 0o777) if name == symlink_member else (stat.S_IFREG | 0o644)) << 16
                bundle.writestr(info, content)
        return {
            "expected_size": self.archive.stat().st_size,
            "expected_sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            "expected_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "expected_dataset_id": self.manifest["dataset_id"],
            "expected_file_count": self.manifest["file_count"], "expected_total_bytes": self.manifest["total_bytes"],
        }

    def test_complete_restore_and_idempotence(self):
        expected = self.create_archive()
        first = restore_archive(self.archive, self.destination, **expected)
        self.assertEqual(first["restored_files"], 3)
        for name, content in self.content.items():
            self.assertEqual((self.destination / "market_data" / YEAR_FOLDER / name).read_bytes(), content)
        self.assertEqual(restore_archive(self.archive, self.destination, **expected)["restored_files"], 0)

    def test_changed_existing_file_prevents_any_restore(self):
        expected = self.create_archive()
        existing = self.destination / "market_data" / YEAR_FOLDER / "day.dbn.zst"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"must-preserve")
        with self.assertRaisesRegex(ValueError, "different existing"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertEqual(existing.read_bytes(), b"must-preserve")
        self.assertFalse((self.destination / "market_data" / MANIFEST_NAME).exists())

    def test_wrong_archive_checksum_prevents_restore(self):
        expected = self.create_archive()
        expected["expected_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pinned release asset"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse(self.destination.exists())

    def test_extra_member_outside_market_data_rejected(self):
        expected = self.create_archive(extra={"launch.py": b"unexpected"})
        with self.assertRaisesRegex(ValueError, "only market_data"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse(self.destination.exists())

    def test_traversal_member_rejected(self):
        expected = self.create_archive(extra={"market_data/../escape": b"unexpected"})
        with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse(self.destination.exists())

    def test_wrong_member_bytes_rejected_before_publication(self):
        name = "market_data/" + YEAR_FOLDER + "/day.dbn.zst"
        expected = self.create_archive(content_override={name: b"different!!!"})
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse((self.destination / "market_data").exists())

    def test_path_variants_rejected(self):
        for path in ("../escape", "/absolute", "C:/absolute", "market_data\\escape", "market_data//escape"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(path)

    def test_symlink_archive_member_rejected(self):
        name = "market_data/" + YEAR_FOLDER + "/day.dbn.zst"
        expected = self.create_archive(symlink_member=name)
        with self.assertRaisesRegex(ValueError, "regular files"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse(self.destination.exists())

    def test_case_colliding_names_rejected(self):
        name = "market_data/" + YEAR_FOLDER + "/DAY.dbn.zst"
        expected = self.create_archive(extra={name: b"collision"})
        with self.assertRaisesRegex(ValueError, "duplicate names"):
            restore_archive(self.archive, self.destination, **expected)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()

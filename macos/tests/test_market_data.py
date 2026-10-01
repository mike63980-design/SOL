"""Small, isolated tests for dataset integrity and preservation of user data."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_data import MANIFEST_NAME, YEAR_FOLDER, install_payload, load_manifest, set_default_data_folder, verify_payload


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol01-data-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / "market_data"
        self.support = self.root / "support"
        self.content = {"day.dbn.zst": b"historical-day", "bad/retained.dbn.zst": b"bad-original-retained"}
        for relative, content in self.content.items():
            path = self.payload / YEAR_FOLDER / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.manifest = {
            "schema_version": 1, "dataset_id": "fixture-year-v1", "folder": YEAR_FOLDER,
            "files": {name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)} for name, content in self.content.items()},
            "file_count": len(self.content), "total_bytes": sum(map(len, self.content.values())),
        }
        self.write_manifest()

    def write_manifest(self):
        (self.payload / MANIFEST_NAME).write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_verified_copy_preserves_tree_and_runs_once(self):
        self.assertEqual(verify_payload(self.payload, required=True)["file_count"], 2)
        result = install_payload(self.payload, self.support)
        self.assertEqual(result.copied, 2)
        self.assertFalse(result.already_installed)
        for relative, content in self.content.items():
            self.assertEqual((result.folder / relative).read_bytes(), content)
        # User edits and deletions after installation must survive a later launch.
        (result.folder / "day.dbn.zst").write_bytes(b"user-changed")
        (result.folder / "bad" / "retained.dbn.zst").unlink()
        repeated = install_payload(self.payload, self.support)
        self.assertTrue(repeated.already_installed)
        self.assertEqual(repeated.copied, 0)
        self.assertEqual((result.folder / "day.dbn.zst").read_bytes(), b"user-changed")
        self.assertFalse((result.folder / "bad" / "retained.dbn.zst").exists())

    def test_existing_user_file_is_not_replaced(self):
        folder = self.support / "data" / "nq_ticks" / YEAR_FOLDER
        folder.mkdir(parents=True)
        (folder / "day.dbn.zst").write_bytes(b"user-historical-data")
        result = install_payload(self.payload, self.support)
        self.assertEqual(result.copied, 1)
        self.assertEqual(result.preserved, 1)
        self.assertEqual((folder / "day.dbn.zst").read_bytes(), b"user-historical-data")

    def test_removed_whole_year_folder_is_restored_despite_existing_receipt(self):
        installed = install_payload(self.payload, self.support)
        self.assertTrue(installed.folder.resolve().is_relative_to(self.root.resolve()))
        shutil.rmtree(installed.folder)
        self.assertFalse(installed.folder.exists())
        restored = install_payload(self.payload, self.support)
        self.assertFalse(restored.already_installed)
        self.assertEqual(restored.copied, 2)
        for relative, content in self.content.items():
            self.assertEqual((restored.folder / relative).read_bytes(), content)
        self.assertTrue(install_payload(self.payload, self.support).already_installed)

    def test_corrupt_source_is_never_published_or_marked_complete(self):
        (self.payload / YEAR_FOLDER / "day.dbn.zst").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            verify_payload(self.payload, required=True)
        with self.assertRaises(ValueError):
            install_payload(self.payload, self.support)
        folder = self.support / "data" / "nq_ticks" / YEAR_FOLDER
        self.assertFalse((folder / "day.dbn.zst").exists())
        self.assertEqual(list(folder.rglob(".sol01-data-*")), [])
        self.assertFalse((folder.parent / ".sol01-market-data").exists())

    def test_traversal_and_case_collisions_are_rejected_before_copy(self):
        record = self.manifest["files"].pop("day.dbn.zst")
        self.manifest["files"]["../escape.dbn.zst"] = record
        self.write_manifest()
        with self.assertRaises(ValueError):
            install_payload(self.payload, self.support)
        self.assertFalse(self.support.exists())
        self.manifest["files"].pop("../escape.dbn.zst")
        self.manifest["files"]["DAY.dbn.zst"] = record
        self.manifest["files"]["day.dbn.zst"] = record
        self.manifest["file_count"] += 1
        self.manifest["total_bytes"] += record["size"]
        self.write_manifest()
        with self.assertRaises(ValueError):
            load_manifest(self.payload)

    def test_manifest_totals_and_missing_full_release_are_rejected(self):
        self.manifest["total_bytes"] += 1
        self.write_manifest()
        with self.assertRaises(ValueError):
            verify_payload(self.payload)
        absent = self.root / "absent"
        self.assertIsNone(verify_payload(absent))
        with self.assertRaises(ValueError):
            verify_payload(absent, required=True)
        unlisted = self.root / "unlisted"
        unlisted.mkdir()
        with self.assertRaises(ValueError):
            verify_payload(unlisted)

    def test_destination_symlink_cannot_write_outside_support(self):
        outside = self.root / "outside"
        outside.mkdir()
        parent = self.support / "data" / "nq_ticks"
        parent.mkdir(parents=True)
        try:
            (parent / YEAR_FOLDER).symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink creation is unavailable on this test host: {error}")
        with self.assertRaises(ValueError):
            install_payload(self.payload, self.support)
        self.assertEqual(list(outside.iterdir()), [])

    def test_custom_folder_and_unrelated_preferences_are_preserved(self):
        self.support.mkdir()
        resources = self.root / "resources"
        resources.mkdir()
        custom = self.root / "my-data"
        custom.mkdir()
        settings = self.support / "settings.json"
        original = {"data_folder": str(custom), "commission_per_side": 9.5, "auto_load_data": False}
        settings.write_text(json.dumps(original), encoding="utf-8")
        target = self.support / "data" / "nq_ticks" / YEAR_FOLDER
        self.assertFalse(set_default_data_folder(settings, self.support, resources, target))
        self.assertEqual(json.loads(settings.read_text()), original)
        defaults = [self.support / "data" / "nq_ticks", self.support / "demo", resources / "demo", self.root / "no-longer-present"]
        for selection in defaults:
            if selection != defaults[-1]:
                selection.mkdir(parents=True, exist_ok=True)
            original["data_folder"] = str(selection)
            settings.write_text(json.dumps(original), encoding="utf-8")
            self.assertTrue(set_default_data_folder(settings, self.support, resources, target))
            updated = json.loads(settings.read_text())
            self.assertEqual(updated["data_folder"], str(target))
            self.assertEqual(updated["commission_per_side"], 9.5)
            self.assertFalse(updated["auto_load_data"])
        settings.write_text("{broken-user-settings", encoding="utf-8")
        self.assertFalse(set_default_data_folder(settings, self.support, resources, target))
        self.assertEqual(settings.read_text(), "{broken-user-settings")


if __name__ == "__main__":
    unittest.main()

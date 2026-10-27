import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


spec = importlib.util.spec_from_file_location("workbuddy_builder", Path(__file__).resolve().parents[1] / "build_workbuddy_zip.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackagingTests(unittest.TestCase):
    def test_mismatched_examples_rejected_before_replacing_archive(self):
        metadata = copy.deepcopy(builder.METADATA)
        metadata["examples_en"].pop()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "skill.zip"
            output.write_bytes(b"keep previous release")
            with patch.object(builder, "METADATA", metadata), patch.object(builder, "OUTPUT", output):
                with self.assertRaises(ValueError):
                    builder.main()
            self.assertEqual(output.read_bytes(), b"keep previous release")

    def test_upload_archive_contains_only_required_runtime_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "skill-curator-workbuddy.zip"
            with patch.object(builder, "OUTPUT", output):
                builder.main()
            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {"SKILL.md", "scripts/skill_curator.py", "references/host-notes.md"})
                self.assertIsNone(archive.testzip())
                manifest = archive.read("SKILL.md").decode("utf-8")
                self.assertIn("\nname: skill-curator\n", manifest)
                self.assertIn(f'version: "{builder.VERSION}"', manifest)
                self.assertIn("check --host workbuddy --no-cache", manifest)


if __name__ == "__main__":
    unittest.main()

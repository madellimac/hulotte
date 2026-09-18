import tempfile
import unittest
from pathlib import Path

from framework.project import generate_project, init_project


ROOT = Path(__file__).resolve().parents[2]


class ExternalProjectTests(unittest.TestCase):
    def test_init_creates_isolated_external_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "user_pipeline"
            init_project(
                project,
                hulotte_root=ROOT,
                streampu_root=ROOT / "vendor" / "streampu",
            )

            self.assertTrue((project / "hulotte.project.yaml").is_file())
            self.assertTrue((project / "pipeline.yaml").is_file())
            self.assertTrue((project / "src" / "custom").is_dir())
            self.assertFalse((project / "Common").exists())
            self.assertFalse((project / "templates").exists())
            self.assertFalse((project / "hulotte_core").exists())

            output = generate_project(project)
            self.assertTrue(output.is_file())
            self.assertIn("Source_random<int> source(16);", output.read_text(encoding="utf-8"))

    def test_init_refuses_non_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "user_pipeline"
            project.mkdir()
            (project / "existing.txt").write_text("user data", encoding="utf-8")
            with self.assertRaises(ValueError):
                init_project(project)


if __name__ == "__main__":
    unittest.main()
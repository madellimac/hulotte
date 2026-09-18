import tempfile
import subprocess
import unittest
from pathlib import Path

from framework.project import ProjectGenerationError, build_project, generate_project


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_project"


class ProjectGenerationTests(unittest.TestCase):
    def test_generates_from_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = generate_project(FIXTURE, output_path=Path(temp_dir) / "main.cpp")
            self.assertTrue(output.is_file())
            self.assertIn("Source_random<int> source(16);", output.read_text(encoding="utf-8"))

    def test_invalid_pipeline_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            (project / "catalog").mkdir(parents=True)
            (project / "catalog" / "modules.yaml").write_text(
                (FIXTURE / "catalog" / "modules.yaml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "pipeline.yaml").write_text(
                (FIXTURE / "pipeline.invalid.yaml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                generate_project(project)
            self.assertFalse((project / "generated").exists())

    def test_missing_project_is_reported(self):
        with self.assertRaises(ProjectGenerationError):
            generate_project(ROOT / "does-not-exist")

    @unittest.skipUnless(
        (ROOT / "vendor" / "streampu" / "include" / "streampu.hpp").is_file()
        and (ROOT / "vendor" / "streampu" / "build" / "lib" / "libstreampu.a").is_file(),
        "local StreamPU build is not available",
    )
    def test_builds_and_runs_fixture(self):
        executable = build_project(
            FIXTURE,
            streampu_root=ROOT / "vendor" / "streampu",
        )
        result = subprocess.run([str(executable)], check=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

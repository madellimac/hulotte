import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "framework"))  # hulotte.py lives in framework/, not as a top-level package

from hulotte import main


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_project"


class CliTests(unittest.TestCase):
    def test_generate_command_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            code = main([
                "generate",
                "--project-root",
                str(FIXTURE),
                "--output",
                str(Path(temp_dir) / "generated.cpp"),
            ])
            self.assertEqual(code, 0)
            self.assertTrue((Path(temp_dir) / "generated.cpp").is_file())

    def test_generate_command_returns_one_for_missing_project(self):
        self.assertEqual(main(["generate", "--project-root", "/missing/project"]), 1)


if __name__ == "__main__":
    unittest.main()

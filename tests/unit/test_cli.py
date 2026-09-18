import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "framework"))  # hulotte.py lives in framework/, not as a top-level package

from hulotte import main


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_project"


class CliTests(unittest.TestCase):
    def test_help_command_succeeds(self):
        with self.assertRaises(SystemExit) as error:
            main(["--help"])
        self.assertEqual(error.exception.code, 0)

    def test_config_set_show_and_unset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "streampu"
            (root / "include").mkdir(parents=True)
            (root / "build" / "lib").mkdir(parents=True)
            (root / "include" / "streampu.hpp").write_text("// fixture\n", encoding="utf-8")
            (root / "build" / "lib" / "libstreampu.a").write_bytes(b"fixture")
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(Path(temp_dir) / "config")}, clear=False):
                self.assertEqual(main(["config", "set", "streampu-root", str(root)]), 0)
                self.assertEqual(main(["config", "show"]), 0)
                self.assertEqual(main(["config", "unset", "streampu-root"]), 0)

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

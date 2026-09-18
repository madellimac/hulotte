import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from framework.config import (
    ConfigurationError,
    config_path,
    resolve_streampu_root,
    set_user_value,
    unset_user_value,
)


class ConfigurationTests(unittest.TestCase):
    @staticmethod
    def make_streampu_root(parent: Path, name: str) -> Path:
        root = parent / name
        (root / "include").mkdir(parents=True)
        (root / "build" / "lib").mkdir(parents=True)
        (root / "include" / "streampu.hpp").write_text("// fixture\n", encoding="utf-8")
        (root / "build" / "lib" / "libstreampu.a").write_bytes(b"fixture")
        return root

    def test_user_configuration_is_stored_under_xdg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                root = self.make_streampu_root(Path(temp_dir), "streampu")
                path = set_user_value("streampu-root", str(root))
                self.assertEqual(path, Path(temp_dir) / "hulotte" / "config.yaml")
                self.assertEqual(resolve_streampu_root(), root.resolve())
                self.assertEqual(unset_user_value("streampu-root"), path)
                self.assertNotIn("streampu_root", path.read_text(encoding="utf-8"))

    def test_explicit_path_has_priority_over_project_and_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            explicit = self.make_streampu_root(base, "explicit")
            project = self.make_streampu_root(base, "project")
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(base / "config")}, clear=False):
                set_user_value("streampu-root", str(self.make_streampu_root(base, "user")))
                resolved = resolve_streampu_root(
                    explicit=explicit,
                    project_config={"dependencies": {"streampu_root": str(project)}},
                )
                self.assertEqual(resolved, explicit.resolve())

    def test_invalid_root_reports_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ConfigurationError, "missing required files"):
                resolve_streampu_root(explicit=Path(temp_dir))

    def test_config_path_uses_xdg_config_home(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": temp_dir}, clear=False):
                self.assertEqual(config_path(), Path(temp_dir) / "hulotte" / "config.yaml")


if __name__ == "__main__":
    unittest.main()

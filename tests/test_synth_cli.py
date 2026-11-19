import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "hulotte.py"
# Stream interface of the Hamming (7,4) decoder of istc_challenge_2027.
HAMMING_INTERFACE = ("--in-type", "int8_t", "--in-width", "6", "--in-lanes", "7",
                     "--out-width", "1", "--out-lanes", "4")
ARCHITECTURE = "synth/odatix_userconfig/architectures/Decoder_hw"
WRAPPER = "src/hw/synth/Decoder_hw_synth_top.sv"


def odatix_command() -> list:
    """The odatix executable next to the Python running the tests, or the one in the PATH."""
    local = Path(sys.executable).with_name("odatix")
    if local.is_file():
        return [str(local)]
    return [shutil.which("odatix")] if shutil.which("odatix") else []


class SynthAddTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, str(CLI_PATH), *arguments],
                              capture_output=True, text=True, timeout=60)

    def make_project(self, directory: Path, *interface) -> Path:
        project_dir = directory / "project"
        for arguments in (("init", str(project_dir)),
                          ("module", "add", str(project_dir), "--type", "verilator", "--name", "Decoder_hw",
                           "--yes", *interface)):
            result = self.run_cli(*arguments)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return project_dir

    def test_synth_add_writes_the_odatix_workspace_of_a_block(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory), *HAMMING_INTERFACE)
            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("IN_WIDTH = 6, IN_LANES = 7, OUT_WIDTH = 1, OUT_LANES = 4", result.stdout)
            for path in ("synth/odatix.yml", "synth/synth_settings.yml", "synth/fmax_settings.yml",
                         "synth/odatix_userconfig/targets/target_vivado.yml", "synth/.gitignore",
                         f"{ARCHITECTURE}/_settings.yml", f"{ARCHITECTURE}/verified.txt", WRAPPER):
                self.assertTrue((project_dir / path).is_file(), path)

            settings = (project_dir / f"{ARCHITECTURE}/_settings.yml").read_text()
            self.assertIn('rtl_path: "../src/hw"', settings)
            self.assertIn('top_level_module: "Decoder_hw_synth_top"', settings)
            self.assertIn('param_target_file: "synth/Decoder_hw_synth_top.sv"', settings)
            self.assertIn('start_delimiter: "module Decoder_hw_synth_top #("', settings)
            self.assertIn("xc7a100t-csg324-1", (project_dir / "synth/odatix_userconfig/targets/target_vivado.yml").read_text())
            self.assertIn("Decoder_hw/verified", (project_dir / "synth/synth_settings.yml").read_text())
            self.assertIn("work/", (project_dir / "synth/.gitignore").read_text())

            verified = (project_dir / f"{ARCHITECTURE}/verified.txt").read_text()
            for line in ("IN_WIDTH  = 6,", "IN_LANES  = 7,", "OUT_WIDTH = 1,", "OUT_LANES = 4"):
                self.assertIn(line, verified)

            # Odatix replaces the text between the delimiters: they must appear once, in the header.
            wrapper = (project_dir / WRAPPER).read_text()
            self.assertEqual(wrapper.count("module Decoder_hw_synth_top #("), 1)
            header = wrapper[wrapper.index("module Decoder_hw_synth_top #("):]
            self.assertIn("parameter int OUT_LANES = 4\n) (", header)
            self.assertIn("Decoder_hw #(", wrapper)

    def test_synth_add_without_wrapper_synthesizes_the_block_itself(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--no-wrap-io", "--yes")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            settings = (project_dir / f"{ARCHITECTURE}/_settings.yml").read_text()
            self.assertIn('top_level_module: "Decoder_hw"', settings)
            self.assertIn('param_target_file: "Decoder_hw.sv"', settings)
            self.assertFalse((project_dir / "src/hw/synth").exists())

    def test_synth_add_refuses_a_missing_block_or_a_changed_header(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            result = self.run_cli("synth", "add", str(project_dir), "--name", "Missing_hw", "--yes")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Hardware block not found: src/hw/Missing_hw.sv", result.stderr)

            rtl = project_dir / "src/hw/Decoder_hw.sv"
            rtl.write_text(rtl.read_text().replace("module Decoder_hw #(", "module Decoder_hw\n#("))
            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes")
            self.assertEqual(result.returncode, 1)
            self.assertIn("must contain 'module Decoder_hw #(' exactly once", result.stderr)
            self.assertFalse((project_dir / "synth").exists())

    def test_synth_add_keeps_shared_files_and_overwrites_block_files_only_with_force(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            self.assertEqual(self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes").returncode, 0)
            odatix_yml = project_dir / "synth/odatix.yml"
            odatix_yml.write_text(odatix_yml.read_text() + "# edited by hand\n")
            verified = project_dir / f"{ARCHITECTURE}/verified.txt"
            verified.write_text("edited")

            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes")
            self.assertEqual(result.returncode, 1)
            self.assertIn("use --force", result.stderr)
            self.assertEqual(verified.read_text(), "edited")

            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes", "--force")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("synth/odatix.yml  (kept, already exists)", result.stdout)
            self.assertIn("verified.txt  (overwritten)", result.stdout)
            self.assertIn("# edited by hand", odatix_yml.read_text())
            self.assertIn("OUT_LANES", verified.read_text())

    def test_synth_add_warns_when_the_target_file_lacks_the_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            self.assertEqual(self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes").returncode, 0)
            result = self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes", "--force",
                                  "--target", "xc7a35t-cpg236-1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not list xc7a35t-cpg236-1", result.stdout)

    def test_synth_add_asks_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            result = subprocess.run([sys.executable, str(CLI_PATH), "synth", "add", str(project_dir),
                                     "--name", "Decoder_hw"], input="n\n", capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cancelled; no files were created.", result.stdout)
            self.assertFalse((project_dir / "synth").exists())

    def test_generated_cmake_does_not_compile_the_synthesis_wrapper(self):
        cmake = (REPOSITORY_ROOT / "templates/project/CMakeLists.txt.j2").read_text()
        self.assertIn('"${CMAKE_CURRENT_SOURCE_DIR}/src/hw/*.sv"', cmake)
        self.assertNotIn("GLOB_RECURSE HULOTTE_VERILOG_SOURCES", cmake)

    @unittest.skipUnless(odatix_command(), "Odatix is not installed")
    def test_odatix_replaces_the_parameters_of_the_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory), *HAMMING_INTERFACE)
            self.assertEqual(self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes").returncode, 0)
            # Replace with other values to see that the replacement happens in the header.
            replacement = Path(temporary_directory) / "other.txt"
            replacement.write_text((project_dir / f"{ARCHITECTURE}/verified.txt").read_text().replace("= 7,", "= 9,"))
            output = Path(temporary_directory) / "replaced.sv"
            result = subprocess.run(
                [*odatix_command(), "replace", "-Q", "-s", "module Decoder_hw_synth_top #(", "-S", ") (",
                 "-i", str(project_dir / WRAPPER), "-o", str(output), "-r", str(replacement)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Content replaced successfully", result.stdout)
            replaced = output.read_text()
            header = replaced[replaced.index("module Decoder_hw_synth_top #("):replaced.index(") (")]
            self.assertIn("IN_LANES  = 9,", header)

            if shutil.which("verilator"):
                result = subprocess.run(
                    ["verilator", "--lint-only", "-Wno-fatal", "--top-module", "Decoder_hw_synth_top",
                     str(project_dir / "src/hw/Decoder_hw.sv"), str(output)],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("%Error", result.stderr)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("verilator") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake/Verilator to run the synthesis wrapper build test",
    )
    def test_project_with_a_synthesis_wrapper_still_builds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            self.assertEqual(self.run_cli("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes").returncode, 0)

            def run(*command):
                return subprocess.run(command, capture_output=True, text=True, timeout=300)
            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Decoder_hw_synth_top", (project_dir / "build/CMakeCache.txt").read_text())
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(list((project_dir / "build").rglob("*Decoder_hw_synth_top*")))


if __name__ == "__main__":
    unittest.main()

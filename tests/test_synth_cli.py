import hashlib
import json
import os
import runpy
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

class SynthStatusTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, str(CLI_PATH), *arguments],
                              capture_output=True, text=True, timeout=60)

    def make_project(self, directory: Path) -> Path:
        project_dir = directory / "project"
        for arguments in (("init", str(project_dir)),
                          ("module", "add", str(project_dir), "--type", "verilator", "--name", "Decoder_hw",
                           "--yes", *HAMMING_INTERFACE),
                          ("synth", "add", str(project_dir), "--name", "Decoder_hw", "--yes")):
            result = self.run_cli(*arguments)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return project_dir

    def write_record(self, project_dir: Path, parameters=None):
        """A synth/verified file as mark_verified() writes it, for the current RTL."""
        namespace = runpy.run_path(str(CLI_PATH))
        rtl_sha256, files = namespace["rtl_manifest"](project_dir)
        parameters = parameters or {"IN_WIDTH": 6, "IN_LANES": 7, "OUT_WIDTH": 1, "OUT_LANES": 4}
        lines = ['module: "Decoder_hw"', 'test: "check_hw"', 'date: "2026-11-20T10:00:00"',
                 f'rtl_sha256: "{rtl_sha256}"', "rtl_files:"]
        lines += [f'  "{name}": "{digest}"' for name, digest in files.items()]
        lines += ["parameters: " + json.dumps(parameters), "cycles:",
                  '  - {"condition": "Eb/N0 = 0.0 dB", "frames": 10, "latency_min": 17, "latency_mean": 17, '
                  '"latency_max": 17, "interval_min": 18, "interval_mean": 18, "interval_max": 18}']
        record = project_dir / "synth/verified/Decoder_hw.yml"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("\n".join(lines) + "\n")

    def test_rtl_hash_covers_every_sv_of_src_hw_except_the_synthesis_wrappers(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            (project_dir / "src/hw/lib").mkdir()
            (project_dir / "src/hw/lib/Adder.sv").write_text("module Adder; endmodule\n")
            namespace = runpy.run_path(str(CLI_PATH))
            rtl_sha256, files = namespace["rtl_manifest"](project_dir)
            self.assertEqual(list(files), ["src/hw/Decoder_hw.sv", "src/hw/lib/Adder.sv"])
            manifest = "".join(f"{digest}  {name}\n" for name, digest in files.items())
            self.assertEqual(rtl_sha256, hashlib.sha256(manifest.encode()).hexdigest())
            (project_dir / "src/hw/synth/Decoder_hw_synth_top.sv").write_text("// changed\n")
            self.assertEqual(namespace["rtl_manifest"](project_dir)[0], rtl_sha256)

    def test_status_reports_verified_modified_and_never_verified_blocks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 1)
            self.assertRegex(result.stdout, r"Decoder_hw\s+never verified")

            self.write_record(project_dir)
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"Decoder_hw\s+verified\s+check_hw, 2026-11-20T10:00:00")
            self.assertIn("Eb/N0 = 0.0 dB: latency 17-17, interval 18-18", result.stdout)

            # Any .sv of src/hw counts, not only the block itself.
            (project_dir / "src/hw/Other_hw.sv").write_text("module Other_hw; endmodule\n")
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("MODIFIED", result.stdout)
            self.assertIn("changed since the check: src/hw/Other_hw.sv", result.stdout)
            self.assertRegex(result.stdout, r"Other_hw\s+never verified")

    def test_status_reports_parameters_that_differ_from_verified_txt(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = self.make_project(Path(temporary_directory))
            self.write_record(project_dir, {"IN_WIDTH": 5, "IN_LANES": 7, "OUT_WIDTH": 1, "OUT_LANES": 4})
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("verified.txt differ from the check IN_WIDTH=5", result.stdout)

    def test_generated_cmake_writes_the_rtl_hash_header(self):
        cmake = (REPOSITORY_ROOT / "templates/project/CMakeLists.txt.j2").read_text()
        self.assertIn('list(FILTER HULOTTE_RTL_FILES EXCLUDE REGEX "^src/hw/synth/")', cmake)
        self.assertIn("CMAKE_CONFIGURE_DEPENDS", cmake)
        self.assertIn("hulotte_rtl_hash.hpp", cmake)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("verilator") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake/Verilator to run the mark_verified integration test",
    )
    def test_mark_verified_writes_the_check_that_status_reads(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "checked"
            for arguments in (("init", str(project_dir)),
                              ("module", "add", str(project_dir), "--type", "verilator", "--name", "Echo_hw", "--yes"),
                              ("synth", "add", str(project_dir), "--name", "Echo_hw", "--yes")):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            main_path = project_dir / "src/main.cpp"
            main_cpp = main_path.read_text()
            main_cpp = main_cpp.replace('#include "Pass_through.hpp"', '#include "custom/Echo_hw.hpp"')
            main_cpp = main_cpp.replace("spu::module::Pass_through pass_through(frame_size);",
                                        "hulotte::module::Echo_hw pass_through(frame_size);")
            main_cpp = main_cpp.replace('pass_through["process::in"]', 'pass_through["simulate::input"]')
            main_cpp = main_cpp.replace('pass_through["process::out"]', 'pass_through["simulate::output"]')
            main_cpp = main_cpp.replace(
                "    for (int frame = 0; frame < 3; ++frame)\n        sequence.exec_seq();\n",
                "    for (int frame = 0; frame < 3; ++frame)\n        sequence.exec_seq();\n"
                '    pass_through.record_cycle_point("point \\"A\\"");\n'
                "    pass_through.reset_cycle_stats();\n"
                "    sequence.exec_seq();\n"
                '    pass_through.record_cycle_point("point B");\n')
            main_cpp = main_cpp.replace(
                '    std::cout << "[PASS] No mismatches over "',
                '    pass_through.mark_verified("smoke");\n    std::cout << "[PASS] No mismatches over "')
            main_path.write_text(main_cpp)

            def run(*command, **kwargs):
                return subprocess.run(command, capture_output=True, text=True, timeout=300, **kwargs)
            def build_and_run(configure=True):
                commands = [("cmake", "--build", str(project_dir / "build"), "--parallel", "2"),
                            (str(project_dir / "build/checked"),)]
                if configure:
                    commands.insert(0, ("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                                        "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"]))
                for command in commands:
                    result = run(*command, cwd=project_dir)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            build_and_run()
            namespace = runpy.run_path(str(CLI_PATH))
            record = namespace["read_verified_record"](project_dir / "synth/verified/Echo_hw.yml")
            rtl_sha256, files = namespace["rtl_manifest"](project_dir)
            self.assertEqual(record["module"], "Echo_hw")
            self.assertEqual(record["test"], "smoke")
            self.assertEqual(record["rtl_sha256"], rtl_sha256)
            self.assertEqual(record["rtl_files"], files)
            self.assertEqual(record["parameters"], {"IN_WIDTH": 32, "IN_LANES": 1, "OUT_WIDTH": 32, "OUT_LANES": 1})
            self.assertEqual([point["condition"] for point in record["cycles"]], ['point "A"', "point B"])
            self.assertEqual([point["frames"] for point in record["cycles"]], [3, 1])
            self.assertEqual(self.run_cli("synth", "status", str(project_dir)).returncode, 0)

            rtl = project_dir / "src/hw/Echo_hw.sv"
            rtl.write_text(rtl.read_text() + "// edited\n")
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("changed since the check: src/hw/Echo_hw.sv", result.stdout)

            # The build alone re-runs CMake after the change: the new run records the new hash.
            build_and_run(configure=False)
            result = self.run_cli("synth", "status", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

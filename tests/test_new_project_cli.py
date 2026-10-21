import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from jinja2 import DictLoader, Environment, StrictUndefined, TemplateNotFound, UndefinedError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPOSITORY_ROOT / "hulotte.py"


class NewProjectCliTests(unittest.TestCase):
    def test_failed_write_removes_only_files_created_by_this_operation(self):
        namespace = runpy.run_path(str(CLI_PATH))
        files = namespace["custom_module_files"]("Gain")
        original_open = Path.open

        def open_file(path, *arguments, **keywords):
            if path.name == "Gain.cpp":
                raise OSError("Simulated write failure")
            return original_open(path, *arguments, **keywords)

        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory)
            marker = project_dir / "keep.txt"
            marker.write_text("preserve")
            with patch.object(Path, "open", open_file):
                with self.assertRaisesRegex(OSError, "Simulated write failure"):
                    namespace["write_project_files"](project_dir, files)
            self.assertFalse((project_dir / "src/custom/Gain.hpp").exists())
            self.assertFalse((project_dir / "src/custom/Gain.cpp").exists())
            self.assertEqual(marker.read_text(), "preserve")

    def test_minimal_source_copy_runs_and_reports_missing_template_cleanly(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "source"
            source_dir.mkdir()
            copied_cli = source_dir / "hulotte.py"
            shutil.copy2(CLI_PATH, copied_cli)
            shutil.copytree(REPOSITORY_ROOT / "templates", source_dir / "templates")
            result = subprocess.run(
                [sys.executable, str(copied_cli), "init", str(root / "working")],
                cwd=root, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            (source_dir / "templates/project/main.cpp.j2").unlink()
            result = subprocess.run(
                [sys.executable, str(copied_cli), "init", str(root / "incomplete")],
                cwd=root, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "incomplete").exists())

    def test_cli_reports_version_and_rejects_systemverilog_keyword(self):
        result = subprocess.run([sys.executable, str(CLI_PATH), "--version"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "Hulotte 0.1.0")
        namespace = runpy.run_path(str(CLI_PATH))
        with self.assertRaisesRegex(ValueError, "SystemVerilog keyword"):
            namespace["validate_module_name"]("logic", "verilator")

    def test_stream_pu_install_dry_run_does_not_create_dependency_files(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            install = namespace["install_stream_pu"]
            output = StringIO()
            with patch.dict(install.__globals__, missing_install_tools=lambda: []):
                with redirect_stdout(output):
                    result = install(repository_root, dry_run=True)
            self.assertEqual(result, repository_root / "dependencies/streampu")
            self.assertIn("Would clone StreamPU", output.getvalue())
            self.assertFalse((repository_root / "dependencies").exists())

    def test_stream_pu_install_refuses_a_different_existing_revision(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            stream_pu_root = repository_root / "dependencies/streampu"
            (stream_pu_root / ".git").mkdir(parents=True)
            marker = stream_pu_root / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            install = namespace["install_stream_pu"]
            with patch.dict(install.__globals__, checkout_revision=lambda _path: "different-revision"):
                with self.assertRaisesRegex(ValueError, "Move it manually"):
                    install(repository_root)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_stream_pu_install_clones_pinned_revision_and_builds_static_library(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            commands = []

            def run_command(command, cwd=None):
                commands.append(command)
                if command[:3] == ["git", "clone", "--no-checkout"]:
                    staged_root = Path(command[-1])
                    (staged_root / ".git").mkdir(parents=True)
                elif command[:2] == ["cmake", "--build"]:
                    stream_pu_root = repository_root / "dependencies/streampu"
                    (stream_pu_root / "include").mkdir()
                    (stream_pu_root / "include/streampu.hpp").touch()
                    (stream_pu_root / "build/lib").mkdir(parents=True)
                    (stream_pu_root / "build/lib/libstreampu.a").touch()

            install = namespace["install_stream_pu"]
            with patch.dict(
                install.__globals__,
                {"missing_install_tools": lambda: [], "run_command": run_command},
            ):
                result = install(repository_root)

            self.assertEqual(result, repository_root / "dependencies/streampu")
            self.assertTrue((result / "build/lib/libstreampu.a").is_file())
            self.assertIn(namespace["STREAMPU_REVISION"], commands[1])
            self.assertEqual(commands[2][3:], ["submodule", "update", "--init", "--recursive"])
            self.assertIn("-DSPU_TESTS=OFF", commands[-2])

    def test_stream_pu_status_requires_header_and_static_library(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            stream_pu_root = repository_root / "dependencies/streampu"
            self.assertFalse(namespace["stream_pu_is_built"](stream_pu_root))
            (stream_pu_root / "include").mkdir(parents=True)
            (stream_pu_root / "include/streampu.hpp").touch()
            (stream_pu_root / "build/lib").mkdir(parents=True)
            (stream_pu_root / "build/lib/libstreampu.a").touch()
            self.assertTrue(namespace["stream_pu_is_built"](stream_pu_root))

    def test_dependency_prerequisites_require_cmake_320_or_newer(self):
        namespace = runpy.run_path(str(CLI_PATH))
        result = subprocess.CompletedProcess(
            args=["cmake", "--version"], returncode=0, stdout="cmake version 3.19.7\n", stderr=""
        )
        with patch("shutil.which", return_value="/usr/bin/tool"):
            with patch("subprocess.run", return_value=result):
                self.assertIn("CMake >= 3.20", namespace["missing_install_tools"]())

    def test_confirmation_reprompts_and_cancellation_creates_no_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "cancel-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            for answer in ("maybe\nn\n", "n\n", ""):
                result = subprocess.run(
                    [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Gain"],
                    input=answer, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 1 if not answer else 0, result.stderr)
                if answer.startswith("maybe"):
                    self.assertIn("Please answer yes or no.", result.stdout)
                self.assertFalse((project_dir / "src/custom/Gain.cpp").exists())

    def test_template_failure_does_not_create_project_directory(self):
        namespace = runpy.run_path(str(CLI_PATH))
        create_project = namespace["create_project"]
        environment = Environment(loader=DictLoader({}), undefined=StrictUndefined)
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "not-created"
            with patch.dict(create_project.__globals__, TEMPLATE_ENVIRONMENT=environment):
                with self.assertRaises(TemplateNotFound):
                    create_project(project_dir)
            self.assertFalse(project_dir.exists())

    def test_generated_instance_name_is_not_a_cpp_keyword(self):
        namespace = runpy.run_path(str(CLI_PATH))
        self.assertEqual(namespace["module_instance_name"]("Class"), "class_module")
        with self.assertRaises(ValueError):
            namespace["validate_module_name"]("Reserved__Name")

    def test_module_writes_refuse_external_symlink_directory(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project_dir = namespace["create_project"](root / "project")
            outside = root / "outside"
            outside.mkdir()
            (project_dir / "src/custom").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "escapes"):
                namespace["add_custom_module"](project_dir, "Gain")
            self.assertEqual(list(outside.iterdir()), [])

    def test_template_rendering_rejects_missing_variables_and_templates(self):
        render_template = runpy.run_path(str(CLI_PATH))["render_template"]
        with self.assertRaises(UndefinedError):
            render_template("custom/Module.hpp.j2")
        with self.assertRaises(TemplateNotFound):
            render_template("missing-template.j2")
        rendered = render_template("custom/Module.hpp.j2", class_name="Gain")
        self.assertIn("class Gain", rendered)
        self.assertIn("#include <streampu.hpp>", rendered)
        self.assertTrue(rendered.endswith("\n"))

    def test_templates_are_loaded_independently_of_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "external-project"
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("project(external_project LANGUAGES CXX)", cmake)
            self.assertIn("${STREAMPU_ROOT}", cmake)
            self.assertNotIn("{{", cmake)

    def test_init_creates_readable_stream_pipeline(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "my-pipeline"
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("project(my_pipeline LANGUAGES CXX)", cmake)
            readme = (project_dir / "README.md").read_text()
            self.assertIn("<h2>Build and run</h2>", readme)
            self.assertIn("cmake -S . -B build&#10;", readme)
            self.assertNotIn("{{", readme)
            self.assertIn("src/Comparator.cpp", cmake)
            main_cpp = (project_dir / "src" / "main.cpp").read_text()
            self.assertIn('source["generate::out_data"] = comparator["check::in_ref"]', main_cpp)
            self.assertIn('source["generate::out_data"] = pass_through["process::in"]', main_cpp)
            self.assertIn('pass_through["process::out"] = comparator["check::in_got"]', main_cpp)
            self.assertIn("if (comparator.has_errors())", main_cpp)
            self.assertIn("return 1;", main_cpp)
            self.assertIn("PassThrough* PassThrough::clone()", (project_dir / "src" / "PassThrough.cpp").read_text())
            self.assertIn("reference[index] != output[index]", (project_dir / "src" / "Comparator.cpp").read_text())

    def test_module_add_generates_module_and_prints_manual_integration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "module-project"
            init_result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            main_path = project_dir / "src" / "main.cpp"
            main_before = main_path.read_text()

            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir)],
                input="1\nGain\nY\n",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project_dir / "src/custom/Gain.hpp").is_file())
            self.assertTrue((project_dir / "src/custom/Gain.cpp").is_file())
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("CONFIGURE_DEPENDS", cmake)
            self.assertIn('"${CMAKE_CURRENT_SOURCE_DIR}/src/custom/*.cpp"', cmake)
            self.assertIn('source["generate::out_data"] = gain["process::in"]', result.stdout)
            self.assertEqual(main_path.read_text(), main_before)

    def test_module_add_refuses_invalid_names_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "module-project"
            subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=True,
                capture_output=True,
                text=True,
            )

            invalid_result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "not-valid", "--yes"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(invalid_result.returncode, 1)
            self.assertFalse((project_dir / "src/custom/not-valid.hpp").exists())

            create_result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Gain", "--yes"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(create_result.returncode, 0, create_result.stderr)

            duplicate_result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Gain", "--yes"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(duplicate_result.returncode, 1)
            self.assertIn("Refusing to overwrite", duplicate_result.stderr)

    def test_init_renames_reserved_cmake_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "test"
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("project(test LANGUAGES CXX)", cmake)
            self.assertIn("add_executable(hulotte_test", cmake)
            self.assertIn("./build/hulotte_test", (project_dir / "README.md").read_text())

    def test_init_refuses_to_overwrite_non_empty_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "existing-project"
            project_dir.mkdir()
            marker = project_dir / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            self.assertFalse((project_dir / "CMakeLists.txt").exists())


    def test_module_add_generates_verilator_model_and_stream_adapter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "verilator-project"
            init_result = subprocess.run(
                [sys.executable, str(CLI_PATH), "init", str(project_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            main_path = project_dir / "src" / "main.cpp"
            main_before = main_path.read_text()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "module",
                    "add",
                    str(project_dir),
                ],
                input="2\nIncrementer\nY\n",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            system_verilog = (project_dir / "src/hw/Incrementer.sv").read_text()
            adapter_header = (project_dir / "src/custom/Incrementer.hpp").read_text()
            adapter_source = (project_dir / "src/custom/Incrementer.cpp").read_text()
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("input  logic [31:0] in_data", system_verilog)
            self.assertIn("namespace hulotte::module", adapter_header)
            self.assertIn("VModel_Incrementer", adapter_source)
            self.assertIn("verilate(", cmake)
            self.assertIn("hulotte::module::Incrementer incrementer(frame_size);", result.stdout)
            self.assertIn("Ready/Valid passthrough example", result.stdout)
            self.assertEqual(main_path.read_text(), main_before)


    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake to run the custom integration test",
    )
    def test_custom_module_build_and_comparator_without_verilator(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "minimal"

            def run(*command):
                return subprocess.run(command, capture_output=True, text=True, timeout=180)

            result = run(sys.executable, str(CLI_PATH), "init", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"],
                         "-DCMAKE_DISABLE_FIND_PACKAGE_verilator=TRUE")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Gain", "--yes")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            main_path = project_dir / "src/main.cpp"
            main_cpp = main_path.read_text().replace(
                '#include "PassThrough.hpp"', '#include "PassThrough.hpp"\n#include "custom/Gain.hpp"'
            ).replace(
                "spu::module::PassThrough pass_through(frame_size);",
                "spu::module::PassThrough pass_through(frame_size);\n    hulotte::module::Gain gain(frame_size);"
            ).replace(
                'source["generate::out_data"] = pass_through["process::in"];',
                'source["generate::out_data"] = gain["process::in"];\n'
                '    gain["process::out"] = pass_through["process::in"];'
            )
            main_path.write_text(main_cpp)
            result = run("cmake", "--build", str(project_dir / "build"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("ctest", "--test-dir", str(project_dir / "build"), "--output-on-failure")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            module_path = project_dir / "src/custom/Gain.cpp"
            module_path.write_text(module_path.read_text().replace(
                "std::copy(input, input + frame_size, output);",
                "std::copy(input, input + frame_size, output);\n    output[0] ^= 1;"
            ))
            result = run("cmake", "--build", str(project_dir / "build"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(str(project_dir / "build/minimal"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("mismatched element(s)", result.stderr)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("verilator") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake/Verilator to run the VCD integration test",
    )
    def test_verilator_vcd_trace_runs_across_frames(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "waveforms"
            def run(*command, **kwargs):
                return subprocess.run(command, capture_output=True, text=True, timeout=180, **kwargs)

            for arguments in (
                ("init", str(project_dir)),
                ("module", "add", str(project_dir), "--type", "verilator", "--name", "WaveBlock", "--yes"),
                ("module", "add", str(project_dir), "--type", "verilator", "--name", "SecondBlock", "--yes"),
            ):
                result = run(sys.executable, str(CLI_PATH), *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            main_path = project_dir / "src/main.cpp"
            main_cpp = main_path.read_text()
            main_cpp = main_cpp.replace('#include "PassThrough.hpp"',
                                        '#include "custom/WaveBlock.hpp"\n#include "custom/SecondBlock.hpp"')
            main_cpp = main_cpp.replace("int main()", "int main(int argc, char** argv)")
            main_cpp = main_cpp.replace(
                "spu::module::PassThrough pass_through(frame_size);",
                'hulotte::module::WaveBlock pass_through(frame_size, argc > 1 ? argv[1] : "");\n'
                '    auto probe = std::unique_ptr<hulotte::module::WaveBlock>(pass_through.clone());\n'
                '    hulotte::module::SecondBlock second(frame_size, argc > 2 ? argv[2] : "");',
            )
            main_cpp = main_cpp.replace('pass_through["process::in"]', 'pass_through["simulate::input"]')
            main_cpp = main_cpp.replace('pass_through["process::out"]', 'pass_through["simulate::output"]')
            main_cpp = main_cpp.replace(
                'pass_through["simulate::output"] = comparator["check::in_got"];',
                'pass_through["simulate::output"] = second["simulate::input"];\n'
                '    second["simulate::output"] = comparator["check::in_got"];',
            )
            main_path.write_text(main_cpp)

            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            executable = str(project_dir / "build/waveforms")
            result = run(executable, cwd=project_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(list(project_dir.rglob("*.vcd")), [])

            result = run(executable, "traces/first.vcd", "traces/second.vcd", cwd=project_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("No mismatches over 3 frame(s)", result.stdout)
            waveform = (project_dir / "traces/first.vcd").read_text()
            self.assertTrue((project_dir / "traces/second.vcd").is_file())
            for signal in ("clk", "reset", "in_data", "in_valid", "in_ready", "out_data", "out_valid", "out_ready"):
                self.assertRegex(waveform, r"\$var[^\n]*\b" + signal + r"\b")
            timestamps = [int(value) for value in re.findall(r"^#(\d+)$", waveform, re.MULTILINE)]
            self.assertGreaterEqual(len(timestamps), 3 * 16 * 2)
            self.assertTrue(all(previous < current for previous, current in zip(timestamps, timestamps[1:])))
            reset_id = re.search(r"\$var\s+\w+\s+1\s+(\S+)\s+reset\b", waveform).group(1)
            self.assertIn("1" + reset_id, waveform)
            self.assertIn("0" + reset_id, waveform)

            result = run(executable, "traces/duplicate.vcd", "traces/duplicate.vcd", cwd=project_dir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("VCD trace path already in use", result.stderr)

            blocker = project_dir / "not_a_directory"
            blocker.write_text("blocked")
            result = run(executable, "not_a_directory/trace.vcd", cwd=project_dir)
            self.assertNotEqual(result.returncode, 0)

            rtl_path = project_dir / "src/hw/WaveBlock.sv"
            rtl_path.write_text(rtl_path.read_text().replace(
                "assign out_valid = !reset && in_valid;", "assign out_valid = 1'b0;"
            ))
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(executable, "traces/stalled.vcd", cwd=project_dir)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Verilator frame timeout in WaveBlock", result.stderr)
            partial_waveform = (project_dir / "traces/stalled.vcd").read_text()
            self.assertIn("$enddefinitions", partial_waveform)
            self.assertRegex(partial_waveform, r"(?m)^#\d+$")


if __name__ == "__main__":
    unittest.main()
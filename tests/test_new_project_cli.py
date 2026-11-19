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
            # Resolve the directory: on macOS the temporary directory is reached through a symlink.
            project_dir = Path(temporary_directory).resolve()
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

    def test_aff3ct_install_pins_revision_limits_submodules_and_builds_static_library(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            aff3ct_root = repository_root / "dependencies/aff3ct"
            commands = []

            def run_command(command, cwd=None):
                commands.append(command)
                if command[:3] == ["git", "clone", "--no-checkout"]:
                    (Path(command[-1]) / ".git").mkdir(parents=True)
                elif command[:2] == ["cmake", "--build"]:
                    (aff3ct_root / "include").mkdir()
                    (aff3ct_root / "include/aff3ct.hpp").touch()
                    (aff3ct_root / "build/lib").mkdir(parents=True)
                    (aff3ct_root / "build/lib/libaff3ct-4.1.2.a").touch()

            install = namespace["install_aff3ct"]
            with patch.dict(install.__globals__, {"missing_install_tools": lambda: [], "run_command": run_command}):
                result = install(repository_root)

            self.assertEqual(result, aff3ct_root)
            self.assertIn(namespace["AFF3CT_REVISION"], commands[1])
            self.assertEqual(commands[2][3:], ["submodule", "update", "--init", "--recursive", "--",
                                               "lib/MIPP", "lib/cli", "lib/date", "lib/streampu"])
            configure = commands[-2]
            for option in ("-DAFF3CT_COMPILE_EXE=OFF", "-DAFF3CT_COMPILE_STATIC_LIB=ON", "-DSPU_TESTS=OFF"):
                self.assertIn(option, configure)
            self.assertLessEqual(int(commands[-1][commands[-1].index("--parallel") + 1]), 8)

    def test_aff3ct_install_refuses_a_different_revision_and_status_reports_both_libraries(self):
        namespace = runpy.run_path(str(CLI_PATH))
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            aff3ct_root = repository_root / "dependencies/aff3ct"
            (aff3ct_root / ".git").mkdir(parents=True)
            (aff3ct_root / "include").mkdir()
            (aff3ct_root / "include/aff3ct.hpp").touch()
            (aff3ct_root / "build/lib").mkdir(parents=True)
            (aff3ct_root / "build/lib/libaff3ct-4.1.2.a").touch()
            install = namespace["install_aff3ct"]
            with patch.dict(install.__globals__, checkout_revision=lambda _path: "other"):
                with self.assertRaisesRegex(ValueError, "Move it manually"):
                    install(repository_root)
                output = StringIO()
                with redirect_stdout(output):
                    ready = namespace["print_dependency_status"](repository_root)
            self.assertFalse(ready)
            self.assertIn("AFF3CT: built, but expected revision", output.getvalue())
            self.assertIn("StreamPU: not installed", output.getvalue())

    def test_deps_install_asks_for_the_library_in_a_terminal_and_defaults_to_streampu_otherwise(self):
        namespace = runpy.run_path(str(CLI_PATH))
        main = namespace["main"]
        calls = []
        stubs = {
            "install_stream_pu": lambda root, dry_run=False: calls.append("streampu"),
            "install_aff3ct": lambda root, dry_run=False: calls.append("aff3ct"),
        }
        with patch.dict(main.__globals__, stubs):
            with patch("builtins.input", side_effect=["x", "2"]):
                with patch("sys.stdin.isatty", return_value=True):
                    with redirect_stdout(StringIO()) as output:
                        self.assertEqual(main(["deps", "install"]), 0)
            self.assertIn("Please answer 1 or 2.", output.getvalue())
            with patch("builtins.input", side_effect=[""]):
                with patch("sys.stdin.isatty", return_value=True):
                    with redirect_stdout(StringIO()):
                        main(["deps", "install"])
            with patch("builtins.input", side_effect=AssertionError("must not prompt")):
                with patch("sys.stdin.isatty", return_value=False):
                    main(["deps", "install"])
                main(["deps", "install", "--library", "aff3ct"])
        self.assertEqual(calls, ["aff3ct", "streampu", "streampu", "aff3ct"])

    def test_module_list_shows_both_catalogs_and_can_filter_by_library(self):
        result = subprocess.run([sys.executable, str(CLI_PATH), "module", "list"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        for module_id in ("Source_random", "Modem_BPSK", "Channel_AWGN_LLR", "Quantizer_pow2_fast", "Decoder_NO"):
            self.assertIn(module_id, result.stdout)
        result = subprocess.run([sys.executable, str(CLI_PATH), "module", "list", "--library", "streampu"],
                                capture_output=True, text=True, timeout=30)
        self.assertIn("Source_random", result.stdout)
        self.assertNotIn("Modem_BPSK", result.stdout)

    def test_catalog_module_preview_describes_sockets_and_writes_no_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "catalog-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            before = sorted(path.relative_to(project_dir) for path in project_dir.rglob("*"))
            main_before = (project_dir / "src/main.cpp").read_text()
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "aff3ct", "--name", "Channel_AWGN_LLR"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for expected in ("#include <aff3ct.hpp>",
                             "aff3ct::module::Channel_AWGN_LLR<float> channel_awgn_llr(N);",
                             "channel_awgn_llr[\"task::socket\"]",
                             "in  CP  float[1]", "out  Y_N  float[N]", "-DAFF3CT_ROOT="):
                self.assertIn(expected, result.stdout)
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "streampu", "--name", "Source_random"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("spu::module::Source_random<int> source_random(frame_size);", result.stdout)
            self.assertNotIn("AFF3CT_ROOT", result.stdout)
            self.assertEqual(sorted(path.relative_to(project_dir) for path in project_dir.rglob("*")), before)
            self.assertEqual((project_dir / "src/main.cpp").read_text(), main_before)

    def test_catalog_module_add_rejects_unknown_ids_and_projects_without_aff3ct_support(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "legacy-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "aff3ct", "--name", "Nope"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Unknown aff3ct module 'Nope'", result.stderr)
            self.assertIn("Modem_BPSK", result.stderr)
            cmake_path = project_dir / "CMakeLists.txt"
            cmake_path.write_text(cmake_path.read_text().replace("AFF3CT_ROOT", "OTHER_ROOT"))
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "aff3ct", "--name", "Modem_BPSK"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("no AFF3CT support", result.stderr)

    def test_module_assistant_offers_catalog_modules_by_number(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "assistant-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir)],
                input="4\n3\n", capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Existing AFF3CT module from the catalog", result.stdout)
            self.assertIn("aff3ct::module::Modem_BPSK<int32_t, float, float> modem_bpsk(N);", result.stdout)

    def test_catalog_validation_reports_the_offending_file_and_field(self):
        namespace = runpy.run_path(str(CLI_PATH))
        load_catalog = namespace["load_catalog"]
        for library in ("streampu", "aff3ct"):
            self.assertTrue(load_catalog(library)["modules"])
        with tempfile.TemporaryDirectory() as temporary_directory:
            script = Path(temporary_directory) / "hulotte.py"
            shutil.copy2(CLI_PATH, script)
            (Path(temporary_directory) / "catalog").mkdir()
            broken = {"library": "aff3ct", "namespace": "x", "include": "x.hpp",
                      "modules": [{"id": "A", "summary": "s", "class": "A", "arguments": [], "tasks": []}]}
            (Path(temporary_directory) / "catalog/aff3ct.json").write_text(
                __import__("json").dumps(broken), encoding="utf-8")
            isolated = runpy.run_path(str(script))
            with self.assertRaisesRegex(ValueError, r"aff3ct\.json.*'A' needs at least one task"):
                isolated["load_catalog"]("aff3ct")

    def test_dependencies_are_compiled_for_the_native_instruction_set_on_x86_64_only(self):
        namespace = runpy.run_path(str(CLI_PATH))
        arguments = namespace["native_arch_arguments"]
        module_platform = arguments.__globals__["platform"]
        with patch.object(module_platform, "machine", return_value="x86_64"):
            with patch.dict(os.environ, {"CXXFLAGS": ""}):
                self.assertEqual(arguments(), ["-DCMAKE_CXX_FLAGS=-march=native"])
            with patch.dict(os.environ, {"CXXFLAGS": "-O2"}):
                self.assertEqual(arguments(), ["-DCMAKE_CXX_FLAGS=-O2 -march=native"])
            with patch.dict(os.environ, {"CXXFLAGS": "-march=haswell"}):
                self.assertEqual(arguments(), [])
        with patch.object(module_platform, "machine", return_value="arm64"):
            self.assertEqual(arguments(), [])

    def test_generated_cmake_selects_aff3ct_over_streampu_and_requires_one_of_them(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "dual"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("if(NOT STREAMPU_ROOT AND NOT AFF3CT_ROOT)", cmake)
            self.assertIn("if(AFF3CT_ROOT)", cmake)
            self.assertIn("libaff3ct-*.a", cmake)
            self.assertLess(cmake.index("if(AFF3CT_ROOT)"), cmake.index("find_library(STREAMPU_LIBRARY"))
            self.assertNotIn("{{", cmake)

    def test_generated_cmake_defaults_to_release_and_detects_aff3ct_include(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "release"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            cmake = (project_dir / "CMakeLists.txt").read_text()
            self.assertIn("if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)", cmake)
            self.assertIn("set(CMAKE_BUILD_TYPE Release CACHE STRING", cmake)
            self.assertIn("CMAKE_CONFIGURE_DEPENDS", cmake)
            self.assertIn('MATCHES "#include[ \\t]*[<\\"]aff3ct\\\\.hpp")', cmake)
            self.assertLess(cmake.index("aff3ct\\\\.hpp"), cmake.index("if(AFF3CT_ROOT)"))
            self.assertIn("option(HULOTTE_NATIVE_ARCH", cmake)
            self.assertIn("add_compile_options(-march=native)", cmake)
            self.assertLess(cmake.index("add_compile_options(-march=native)"), cmake.index("add_executable("))

    @unittest.skipIf(shutil.which("cmake") is None, "CMake is not installed")
    def test_configuring_aff3ct_graph_without_aff3ct_root_fails_with_clear_message(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "needs_aff3ct"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           capture_output=True, text=True, check=True, timeout=30)
            main_path = project_dir / "src/main.cpp"
            main_path.write_text("#include <aff3ct.hpp>\n" + main_path.read_text())
            environment = {key: value for key, value in os.environ.items()
                           if key not in ("AFF3CT_ROOT", "STREAMPU_ROOT")}
            result = subprocess.run(
                ["cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                 f"-DSTREAMPU_ROOT={temporary_directory}/missing_streampu"],
                capture_output=True, text=True, timeout=120, env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("src/main.cpp includes aff3ct.hpp: set AFF3CT_ROOT", result.stderr)

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
        rendered = render_template("custom/Module.hpp.j2", class_name="Gain", in_type="int", out_type="int")
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
            self.assertIn("project(external_project LANGUAGES C CXX)", cmake)
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
            self.assertIn("project(my_pipeline LANGUAGES C CXX)", cmake)
            readme = (project_dir / "README.md").read_text()
            self.assertIn("<h2>Build and run</h2>", readme)
            self.assertIn("cmake -S . -B build&#10;", readme)
            self.assertNotIn("{{", readme)
            self.assertIn('file(GLOB HULOTTE_PROJECT_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")', cmake)
            self.assertNotIn("src/Comparator.cpp", cmake)
            main_cpp = (project_dir / "src" / "main.cpp").read_text()
            self.assertIn('source["generate::out_data"] = comparator["check::in_ref"]', main_cpp)
            self.assertIn('source["generate::out_data"] = pass_through["process::in"]', main_cpp)
            self.assertIn('pass_through["process::out"] = comparator["check::in_got"]', main_cpp)
            self.assertIn("if (comparator.has_errors())", main_cpp)
            self.assertIn("return 1;", main_cpp)
            self.assertIn("Pass_through* Pass_through::clone()", (project_dir / "src" / "Pass_through.cpp").read_text())
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
            self.assertIn("project(test LANGUAGES C CXX)", cmake)
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
            self.assertIn("parameter int IN_WIDTH  = 32", system_verilog)
            self.assertIn("input  logic [IN_LANES*IN_WIDTH-1:0]   in_data", system_verilog)
            self.assertIn("input  logic                           in_last", system_verilog)
            self.assertIn("assign out_data = in_data;", system_verilog)
            self.assertIn("namespace hulotte::module", adapter_header)
            self.assertIn("using in_t = int;", adapter_header)
            self.assertIn("VModel_Incrementer", adapter_source)
            self.assertIn("this->set_single_wave(true);", adapter_source)
            self.assertIn("verilate(", cmake)
            self.assertIn("hulotte::module::Incrementer incrementer(frame_size);", result.stdout)
            self.assertIn("Ready/Valid passthrough example", result.stdout)
            self.assertEqual(main_path.read_text(), main_before)

    def test_verilator_module_accepts_an_asymmetric_stream_interface(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "decoder-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "verilator",
                 "--name", "Decoder", "--in-type", "int8_t", "--in-width", "6", "--in-lanes", "16",
                 "--out-type", "int32_t", "--out-width", "1", "--out-lanes", "4", "--yes"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            system_verilog = (project_dir / "src/hw/Decoder.sv").read_text()
            adapter_header = (project_dir / "src/custom/Decoder.hpp").read_text()
            self.assertIn("parameter int IN_WIDTH  = 6", system_verilog)
            self.assertIn("parameter int IN_LANES  = 16", system_verilog)
            self.assertIn("parameter int OUT_WIDTH = 1", system_verilog)
            self.assertIn("parameter int OUT_LANES = 4", system_verilog)
            self.assertIn("assign out_valid = 1'b0;", system_verilog)
            self.assertNotIn("assign out_data = in_data;", system_verilog)
            self.assertIn("using in_t = int8_t;", adapter_header)
            self.assertIn("using out_t = int32_t;", adapter_header)
            self.assertIn("Decoder(int n_in, int n_out, const std::string& trace_path = \"\");", adapter_header)
            self.assertIn("hulotte::module::Decoder decoder(n_in, n_out);", result.stdout)
            self.assertIn("int8_t, 16 element(s) of 6 bit(s) per beat", result.stdout)
            self.assertIn("skeleton", result.stdout)

    def test_stream_interface_options_are_validated(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "invalid-interface"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           check=True, capture_output=True, text=True)
            cases = (
                (["--type", "verilator", "--in-type", "int8_t", "--in-width", "9"], "--in-width must be between 1 and 8"),
                (["--type", "verilator", "--out-lanes", "0"], "--out-lanes must be a positive integer"),
                (["--type", "verilator", "--in-lanes", "200"], "exceeds 4096 bits"),
                (["--type", "custom", "--in-lanes", "2"], "only apply to verilator modules"),
                (["--type", "cfunction", "--in-lanes", "2"], "only apply to verilator modules"),
                (["--type", "verilator", "--in-type", "float"], "--in-type must be one of: int, int8_t"),
            )
            for options, message in cases:
                result = subprocess.run(
                    [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Block", "--yes", *options],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1, options)
                self.assertIn(message, result.stderr)
                self.assertFalse((project_dir / "src/custom/Block.hpp").exists())
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Block",
                 "--type", "verilator", "--in-type", "complex"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)

    def test_cfunction_module_generates_c_api_example_and_adapter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "cfunction-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           check=True, capture_output=True, text=True)
            main_before = (project_dir / "src/main.cpp").read_text()
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir)],
                input="5\nSoft_decoder\nY\n", capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            api = (project_dir / "src/custom/soft_decoder_api.h").read_text()
            self.assertIn("soft_decoder_state* soft_decoder_create(int n_in, int n_out);", api)
            self.assertIn("int soft_decoder_process(soft_decoder_state* state, const int* in, int* out);", api)
            self.assertIn('extern "C"', api)
            self.assertIn("free(state);", (project_dir / "src/custom/soft_decoder_impl.c").read_text())
            self.assertIn("std::unique_ptr<soft_decoder_state, void (*)(soft_decoder_state*)> state;",
                          (project_dir / "src/custom/Soft_decoder.hpp").read_text())
            self.assertIn("hulotte::module::Soft_decoder soft_decoder(n_in, n_out);", result.stdout)
            self.assertEqual((project_dir / "src/main.cpp").read_text(), main_before)

            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "cfunction",
                 "--name", "Float_decoder", "--in-type", "float", "--out-type", "int32_t", "--yes"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("const float* in, int32_t* out", (project_dir / "src/custom/float_decoder_api.h").read_text())

    def test_cfunction_module_refuses_projects_without_c_support(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "old-project"
            subprocess.run([sys.executable, str(CLI_PATH), "init", str(project_dir)],
                           check=True, capture_output=True, text=True)
            cmake_path = project_dir / "CMakeLists.txt"
            cmake_path.write_text(cmake_path.read_text().replace('    "${CMAKE_CURRENT_SOURCE_DIR}/src/custom/*.c"\n', ""))
            result = subprocess.run(
                [sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--type", "cfunction",
                 "--name", "Legacy", "--yes"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not compile C sources", result.stderr)
            self.assertFalse((project_dir / "src/custom/Legacy.hpp").exists())


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
                '#include "Pass_through.hpp"', '#include "Pass_through.hpp"\n#include "custom/Gain.hpp"'
            ).replace(
                "spu::module::Pass_through pass_through(frame_size);",
                "spu::module::Pass_through pass_through(frame_size);\n    hulotte::module::Gain gain(frame_size);"
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
                "        output[i] = i < n_in ? static_cast<out_t>(input[i]) : out_t(0);\n",
                "        output[i] = i < n_in ? static_cast<out_t>(input[i]) : out_t(0);\n    output[0] ^= 1;\n"
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
                ("module", "add", str(project_dir), "--type", "verilator", "--name", "Wave_block", "--yes"),
                ("module", "add", str(project_dir), "--type", "verilator", "--name", "Second_block", "--yes"),
            ):
                result = run(sys.executable, str(CLI_PATH), *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            main_path = project_dir / "src/main.cpp"
            main_cpp = main_path.read_text()
            main_cpp = main_cpp.replace('#include "Pass_through.hpp"',
                                        '#include "custom/Wave_block.hpp"\n#include "custom/Second_block.hpp"')
            main_cpp = main_cpp.replace("int main()", "int main(int argc, char** argv)")
            main_cpp = main_cpp.replace(
                "spu::module::Pass_through pass_through(frame_size);",
                'hulotte::module::Wave_block pass_through(frame_size, argc > 1 ? argv[1] : "");\n'
                '    auto probe = std::unique_ptr<hulotte::module::Wave_block>(pass_through.clone());\n'
                '    hulotte::module::Second_block second(frame_size, argc > 2 ? argv[2] : "");',
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

            rtl_path = project_dir / "src/hw/Wave_block.sv"
            rtl_path.write_text(rtl_path.read_text().replace(
                "assign out_valid = !reset && in_valid;", "assign out_valid = 1'b0;"
            ))
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(executable, "traces/stalled.vcd", cwd=project_dir)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Verilator frame timeout in Wave_block", result.stderr)
            partial_waveform = (project_dir / "traces/stalled.vcd").read_text()
            self.assertIn("$enddefinitions", partial_waveform)
            self.assertRegex(partial_waveform, r"(?m)^#\d+$")

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("verilator") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake/Verilator to run the asymmetric Verilator test",
    )
    def test_verilator_wide_asymmetric_block_streams_frames_and_counts_cycles(self):
        # 16 signed 6-bit LLRs per beat (a 96-bit bus) become 8 hard decisions per beat:
        # decision i is the sign of llr[2i] + llr[2i+1], registered once (one cycle of latency).
        rtl = r'''module Pair_decoder #(
    parameter int IN_WIDTH  = 6,
    parameter int IN_LANES  = 16,
    parameter int OUT_WIDTH = 1,
    parameter int OUT_LANES = 8
) (
    input  logic                           clk,
    input  logic                           reset,
    input  logic [IN_LANES*IN_WIDTH-1:0]   in_data,
    input  logic                           in_valid,
    input  logic                           in_last,
    output logic                           in_ready,
    output logic [OUT_LANES*OUT_WIDTH-1:0] out_data,
    output logic                           out_valid,
    input  logic                           out_ready
);
    logic [OUT_LANES-1:0] decisions;
    logic [OUT_LANES-1:0] decisions_q;
    logic valid_q;
    always_comb
        for (int i = 0; i < OUT_LANES; i++) begin
            automatic logic signed [IN_WIDTH:0] sum =
                $signed(in_data[2*i*IN_WIDTH +: IN_WIDTH]) + $signed(in_data[(2*i+1)*IN_WIDTH +: IN_WIDTH]);
            decisions[i] = sum < 0;
        end
    assign in_ready = !reset && (!valid_q || out_ready);
    always_ff @(posedge clk)
        if (reset)
            valid_q <= 1'b0;
        else if (in_valid && in_ready) begin
            decisions_q <= decisions;
            valid_q <= 1'b1;
        end else if (out_ready)
            valid_q <= 1'b0;
    assign out_data = decisions_q;
    assign out_valid = valid_q;
endmodule
'''
        main = r'''#include <streampu.hpp>

#include "custom/Pair_decoder.hpp"

#include <cstdint>
#include <iostream>
#include <vector>

int main() try
{
    constexpr int n_in = 32, n_out = 16, n_frames = 4;
    hulotte::module::Pair_decoder decoder(n_in, n_out);
    decoder.set_n_frames(n_frames);

    std::vector<int8_t> llrs(n_in * n_frames);
    std::vector<int32_t> expected(n_out * n_frames);
    for (int f = 0; f < n_frames; ++f)
        for (int i = 0; i < n_out; ++i)
        {
            const int a = ((f * 7 + i * 5) % 64) - 32, b = ((f * 3 + i * 11) % 61) - 30;
            llrs[f * n_in + 2 * i] = static_cast<int8_t>(a);
            llrs[f * n_in + 2 * i + 1] = static_cast<int8_t>(b);
            expected[f * n_out + i] = a + b < 0 ? 1 : 0;
        }
    decoder["simulate::input"] = llrs.data();
    decoder("simulate").exec();

    const auto* output = static_cast<const int32_t*>(decoder["simulate::output"].get_dataptr());
    for (int i = 0; i < n_out * n_frames; ++i)
        if (output[i] != expected[i])
        {
            std::cerr << "[FAIL] element " << i << ": got " << output[i] << ", expected " << expected[i] << std::endl;
            return 1;
        }
    decoder.print_cycle_stats(std::cout);
    std::cout << "frames=" << decoder.get_frame_count() << " latency=" << decoder.get_latency_min() << "/"
              << decoder.get_latency_max() << " interval=" << decoder.get_interval_min() << "/"
              << decoder.get_interval_max() << " intervals=" << decoder.get_interval_count() << std::endl;
    return 0;
}
catch (const std::exception& error)
{
    std::cerr << "[FAIL] " << error.what() << std::endl;
    return 1;
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "pair_decoder"

            def run(*command, **kwargs):
                return subprocess.run(command, capture_output=True, text=True, timeout=300, **kwargs)

            for arguments in (
                ("init", str(project_dir)),
                ("module", "add", str(project_dir), "--type", "verilator", "--name", "Pair_decoder",
                 "--in-type", "int8_t", "--in-width", "6", "--in-lanes", "16",
                 "--out-type", "int32_t", "--out-width", "1", "--out-lanes", "8", "--yes"),
            ):
                result = run(sys.executable, str(CLI_PATH), *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (project_dir / "src/hw/Pair_decoder.sv").write_text(rtl)
            (project_dir / "src/main.cpp").write_text(main)

            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(str(project_dir / "build/pair_decoder"), cwd=project_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Two input beats per frame, accepted every cycle: the last output beat comes two
            # cycles after the first input beat, and a new frame starts every two cycles.
            self.assertIn("frames=4 latency=2/2 interval=2/2 intervals=3", result.stdout)
            self.assertIn("Pair_decoder: 4 frame(s), latency min/mean/max = 2/2/2 cycles", result.stdout)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake to run the typed custom module test",
    )
    def test_custom_module_with_types_and_sizes_processes_every_frame_of_a_wave(self):
        # float LLRs in, one decided bit per pair of LLRs out (n_out = n_in / 2), three frames per wave.
        main = r'''#include <streampu.hpp>

#include "custom/Pair_decider.hpp"

#include <cstdint>
#include <iostream>
#include <vector>

int main() try
{
    constexpr int n_in = 8, n_out = 4, n_frames = 3;
    hulotte::module::Pair_decider decider(n_in, n_out);
    decider.set_n_frames(n_frames);
    std::vector<float> llrs(n_in * n_frames);
    for (int i = 0; i < n_in * n_frames; ++i)
        llrs[i] = (i % 3 == 0 ? -2.0f : 1.0f) + 0.25f * i;
    decider["process::in"] = llrs.data();
    decider("process").exec();
    const auto* bits = static_cast<const int32_t*>(decider["process::out"].get_dataptr());
    for (int i = 0; i < n_out * n_frames; ++i)
        if (bits[i] != (llrs[2 * i] + llrs[2 * i + 1] < 0.0f ? 1 : 0))
        {
            std::cerr << "[FAIL] bit " << i << std::endl;
            return 1;
        }
    std::cout << "[PASS] " << n_out * n_frames << " bits" << std::endl;
    return 0;
}
catch (const std::exception& error)
{
    std::cerr << "[FAIL] " << error.what() << std::endl;
    return 1;
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "typed_custom"

            def run(*command):
                return subprocess.run(command, capture_output=True, text=True, timeout=300)

            result = run(sys.executable, str(CLI_PATH), "init", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(sys.executable, str(CLI_PATH), "module", "add", str(project_dir), "--name", "Pair_decider",
                         "--in-type", "float", "--out-type", "int32_t", "--yes")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("hulotte::module::Pair_decider pair_decider(n_in, n_out);", result.stdout)
            self.assertIn("in   in   float[n_in]", result.stdout)
            module_path = project_dir / "src/custom/Pair_decider.cpp"
            module_path.write_text(module_path.read_text().replace(
                "        output[i] = i < n_in ? static_cast<out_t>(input[i]) : out_t(0);\n",
                "        output[i] = input[2 * i] + input[2 * i + 1] < 0.0f ? 1 : 0;\n"))
            (project_dir / "src/main.cpp").write_text(main)
            for name in ("Pass_through.hpp", "Pass_through.cpp", "Comparator.hpp", "Comparator.cpp"):
                (project_dir / "src" / name).unlink()   # the example modules are not needed
            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"],
                         "-DCMAKE_DISABLE_FIND_PACKAGE_verilator=TRUE")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(str(project_dir / "build/typed_custom"))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[PASS] 12 bits", result.stdout)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_STREAMPU_ROOT") and shutil.which("cmake"),
        "Set HULOTTE_TEST_STREAMPU_ROOT and install CMake to run the cfunction integration test",
    )
    def test_cfunction_module_runs_c_code_per_frame_and_reports_errors(self):
        implementation = r'''#include "hard_decider_api.h"

#include <stdlib.h>

struct hard_decider_state { int n; };

hard_decider_state* hard_decider_create(int n_in, int n_out)
{
    if (n_in != n_out)
        return NULL;
    hard_decider_state* state = (hard_decider_state*)malloc(sizeof(*state));
    if (state != NULL)
        state->n = n_in;
    return state;
}

int hard_decider_process(hard_decider_state* state, const float* in, int32_t* out)
{
    if (in[0] == 999.0f)
        return 7;
    for (int i = 0; i < state->n; ++i)
        out[i] = in[i] < 0.0f ? 1 : 0;
    return 0;
}

void hard_decider_destroy(hard_decider_state* state) { free(state); }
'''
        main = r'''#include <streampu.hpp>

#include "custom/Hard_decider.hpp"

#include <iostream>
#include <memory>
#include <vector>

int run(hulotte::module::Hard_decider& decider, std::vector<float>& llrs, int n, int n_frames)
{
    decider["process::in"] = llrs.data();
    decider("process").exec();
    const auto* bits = static_cast<const int32_t*>(decider["process::out"].get_dataptr());
    for (int i = 0; i < n * n_frames; ++i)
        if (bits[i] != (llrs[i] < 0.0f ? 1 : 0))
            return 1;
    return 0;
}

int main() try
{
    constexpr int n = 8, n_frames = 3;
    hulotte::module::Hard_decider decider(n, n);
    decider.set_n_frames(n_frames);
    std::vector<float> llrs(n * n_frames);
    for (int i = 0; i < n * n_frames; ++i)
        llrs[i] = (i % 3 == 0 ? -1.0f : 1.0f) * (0.5f + i);
    if (run(decider, llrs, n, n_frames) != 0)
        return 1;
    // A clone creates and later destroys its own state (only a Sequence allocates its outputs).
    std::unique_ptr<hulotte::module::Hard_decider> copy(decider.clone());
    copy.reset();
    std::cout << "[PASS] frames and clone" << std::endl;

    llrs[n] = 999.0f;
    run(decider, llrs, n, n_frames);
    return 1;
}
catch (const std::exception& error)
{
    std::cerr << "[FAIL] " << error.what() << std::endl;
    return 2;
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "c_decider"

            def run(*command, **kwargs):
                return subprocess.run(command, capture_output=True, text=True, timeout=300, **kwargs)

            for arguments in (
                ("init", str(project_dir)),
                ("module", "add", str(project_dir), "--type", "cfunction", "--name", "Hard_decider",
                 "--in-type", "float", "--out-type", "int32_t", "--yes"),
            ):
                result = run(sys.executable, str(CLI_PATH), *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (project_dir / "src/custom/hard_decider_impl.c").write_text(implementation)
            (project_dir / "src/main.cpp").write_text(main)

            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DSTREAMPU_ROOT=" + os.environ["HULOTTE_TEST_STREAMPU_ROOT"],
                         "-DCMAKE_DISABLE_FIND_PACKAGE_verilator=TRUE")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "2")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run(str(project_dir / "build/c_decider"))
            self.assertIn("[PASS] frames and clone", result.stdout, result.stderr)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("hard_decider_process() failed with code 7 in Hard_decider", result.stderr)

    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_AFF3CT_ROOT") and shutil.which("cmake"),
        "Set HULOTTE_TEST_AFF3CT_ROOT and install CMake to run the AFF3CT integration test",
    )
    def test_aff3ct_catalog_chain_builds_and_responds_to_noise(self):
        chain = r'''#include <aff3ct.hpp>

#include "Comparator.hpp"

#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) try
{
    constexpr int K = 8;
    constexpr int N = 32;
    std::vector<float> sigma(1, argc > 1 ? std::strtof(argv[1], nullptr) : 0.1f);
    const int n_frames = argc > 2 ? std::atoi(argv[2]) : 20;

    spu::module::Source_random<int> source(K);
    aff3ct::module::Encoder_repetition_sys<int32_t> encoder(K, N);
    aff3ct::module::Modem_BPSK<int32_t, float, float> modem(N);
    aff3ct::module::Channel_AWGN_LLR<float> channel(N);
    aff3ct::module::Decoder_repetition_std<int32_t, float> decoder(K, N);
    spu::module::Comparator comparator(K);

    source["generate::out_data"] = comparator["check::in_ref"];
    source["generate::out_data"] = encoder["encode::U_K"];
    encoder["encode::X_N"] = modem["modulate::X_N1"];
    modem["modulate::X_N2"] = channel["add_noise::X_N"];
    channel["add_noise::Y_N"] = modem["demodulate::Y_N1"];
    modem["demodulate::Y_N2"] = decoder["decode_siho::Y_N"];
    decoder["decode_siho::V_K"] = comparator["check::in_got"];
    channel["add_noise::CP"] = sigma.data();
    modem["demodulate::CP"] = sigma.data();

    std::vector<spu::runtime::Task*> first_tasks;
    first_tasks.push_back(&source("generate"));
    spu::runtime::Sequence sequence(first_tasks);
    for (int frame = 0; frame < n_frames; ++frame)
        sequence.exec_seq();

    if (comparator.has_errors())
    {
        std::cerr << "[FAIL] " << comparator.get_n_errors() << " mismatched element(s) over "
                  << comparator.get_frame_count() << " frame(s)." << std::endl;
        return 1;
    }
    std::cout << "[PASS] No mismatches over " << comparator.get_frame_count() << " frame(s)." << std::endl;
    return 0;
}
catch (const std::exception& error)
{
    std::cerr << "[FAIL] " << error.what() << std::endl;
    return 1;
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "aff3ct_chain"

            def run(*command):
                return subprocess.run(command, capture_output=True, text=True, timeout=900)

            result = run(sys.executable, str(CLI_PATH), "init", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (project_dir / "src/main.cpp").write_text(chain)
            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DAFF3CT_ROOT=" + os.environ["HULOTTE_TEST_AFF3CT_ROOT"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "4")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            executable = str(project_dir / "build/aff3ct_chain")
            result = run(executable, "0.05", "20")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[PASS] No mismatches over 20 frame(s).", result.stdout)

            result = run(executable, "4.0", "100")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("mismatched element(s) over 100 frame(s)", result.stderr)


    @unittest.skipUnless(
        os.environ.get("HULOTTE_TEST_AFF3CT_ROOT") and shutil.which("cmake"),
        "Set HULOTTE_TEST_AFF3CT_ROOT and install CMake to run the AFF3CT polar integration test",
    )
    def test_aff3ct_catalog_polar_ca_scl_chain_counts_errors(self):
        # Every module below is instantiated as the catalog describes it.
        chain = r'''#include <aff3ct.hpp>

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <vector>

int main(int argc, char** argv) try
{
    constexpr int K_info = 48, crc_size = 16, K = K_info + crc_size, N = 128, L = 4;
    std::vector<float> sigma(1, std::strtof(argv[1], nullptr));
    const int n_frames = std::atoi(argv[2]);

    aff3ct::tools::Frozenbits_generator_GA_Arikan frozen_bits_generator(K, N);
    aff3ct::tools::Sigma<> design_sigma(0.5f);
    frozen_bits_generator.set_noise(design_sigma);
    std::vector<bool> frozen_bits(N);
    frozen_bits_generator.generate(frozen_bits);

    aff3ct::module::Source_random_fast<int32_t> source(K_info);
    aff3ct::module::CRC_polynomial<int32_t> crc_polynomial(K_info, "16-CCITT", 0);
    aff3ct::module::Encoder_polar<int32_t> encoder(K, N, frozen_bits);
    aff3ct::module::Modem_BPSK<int32_t, float, float> modem(N);
    aff3ct::module::Channel_AWGN_LLR<float> channel(N);
    aff3ct::module::Quantizer_pow2<float, int8_t> quantizer(N, 2, 6);
    aff3ct::module::Decoder_polar_SCL_naive_CA<int32_t, float> decoder(K, N, L, frozen_bits, crc_polynomial);
    aff3ct::module::Monitor_BFER<int32_t> monitor(K_info, 1000);

    source["generate::out_data"] = crc_polynomial["build::U_K1"];
    crc_polynomial["build::U_K2"] = encoder["encode::U_K"];
    encoder["encode::X_N"] = modem["modulate::X_N1"];
    modem["modulate::X_N2"] = channel["add_noise::X_N"];
    channel["add_noise::Y_N"] = modem["demodulate::Y_N1"];
    modem["demodulate::Y_N2"] = quantizer["process::Y_N1"];
    modem["demodulate::Y_N2"] = decoder["decode_siho::Y_N"];
    decoder["decode_siho::V_K"] = crc_polynomial["extract::V_K1"];
    crc_polynomial["extract::V_K2"] = monitor["check_errors::V"];
    source["generate::out_data"] = monitor["check_errors::U"];
    channel["add_noise::CP"] = sigma.data();
    modem["demodulate::CP"] = sigma.data();

    std::vector<spu::runtime::Task*> first_tasks;
    first_tasks.push_back(&source("generate"));
    spu::runtime::Sequence sequence(first_tasks);
    int max_quantized = 0;
    for (int frame = 0; frame < n_frames; ++frame)
    {
        sequence.exec_seq();
        const auto* quantized = static_cast<const int8_t*>(quantizer["process::Y_N2"].get_dataptr());
        for (int i = 0; i < N; ++i)
            max_quantized = std::max(max_quantized, std::abs(static_cast<int>(quantized[i])));
    }
    std::cout << "frames=" << monitor.get_n_analyzed_fra() << " fe=" << monitor.get_n_fe()
              << " max_quantized=" << max_quantized << std::endl;
    return 0;
}
catch (const std::exception& error)
{
    std::cerr << "[FAIL] " << error.what() << std::endl;
    return 1;
}
'''
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory) / "polar_chain"

            def run(*command):
                return subprocess.run(command, capture_output=True, text=True, timeout=900)

            result = run(sys.executable, str(CLI_PATH), "init", str(project_dir))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for module_id in ("Source_random_fast", "CRC_polynomial", "Encoder_polar", "Quantizer_pow2",
                              "Decoder_polar_SCL_naive_CA", "Monitor_BFER"):
                result = run(sys.executable, str(CLI_PATH), "module", "add", str(project_dir),
                             "--type", "aff3ct", "--name", module_id)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            (project_dir / "src/main.cpp").write_text(chain)
            result = run("cmake", "-S", str(project_dir), "-B", str(project_dir / "build"),
                         "-DAFF3CT_ROOT=" + os.environ["HULOTTE_TEST_AFF3CT_ROOT"],
                         "-DCMAKE_DISABLE_FIND_PACKAGE_verilator=TRUE")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run("cmake", "--build", str(project_dir / "build"), "--parallel", "4")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            executable = str(project_dir / "build/polar_chain")
            # Eb/N0 around 14 dB: no frame error; LLRs (2y/sigma^2) are large, so the
            # 6-bit quantizer saturates at 31.
            result = run(executable, "0.2", "200")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("frames=200 fe=0 max_quantized=31", result.stdout)
            # Very noisy channel: most frames fail.
            result = run(executable, "3.0", "50")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            frame_errors = int(re.search(r"fe=(\d+)", result.stdout).group(1))
            self.assertGreater(frame_errors, 10, result.stdout)


if __name__ == "__main__":
    unittest.main()
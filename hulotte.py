#!/usr/bin/env python3
"""Create readable C++ StreamPU projects and guide module creation."""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

__version__ = "0.1.0"
STREAMPU_URL = "https://github.com/aff3ct/streampu.git"
STREAMPU_REVISION = "b036089b872a950ae5fe6eae31e7963a4e043670"


RESERVED_CMAKE_TARGETS = {
    "all",
    "clean",
    "edit_cache",
    "help",
    "install",
    "list_install_components",
    "package",
    "package_source",
    "preinstall",
    "rebuild_cache",
    "test",
}

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit",
    "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch",
    "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const",
    "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return",
    "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else",
    "enum", "explicit", "export", "extern", "false", "float", "for", "friend", "goto",
    "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept", "not",
    "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
    "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof",
    "static", "static_assert", "static_cast", "struct", "switch", "synchronized", "template",
    "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union",
    "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
}

SYSTEMVERILOG_KEYWORDS = set("""
accept_on alias always always_comb always_ff always_latch and assert assign assume
automatic before begin bind bins binsof bit break buf bufif0 bufif1 byte case casex
casez cell chandle checker class clocking cmos config const constraint context
continue cover covergroup coverpoint cross deassign default defparam design disable
dist do edge else end endcase endchecker endclass endclocking endconfig endfunction
endgenerate endgroup endinterface endmodule endpackage endprimitive endprogram
endproperty endspecify endsequence endtable endtask enum event eventually expect
export extends extern final first_match for force foreach forever fork forkjoin
function generate genvar global highz0 highz1 if iff ifnone ignore_bins illegal_bins
implements implies import incdir include initial inout input inside int integer
interconnect interface intersect join join_any join_none large let liblist library
local localparam logic longint macromodule matches medium modport module nand
negedge nettype new nexttime nmos nor noshowcancelled not notif0 notif1 null or output
package packed parameter pmos posedge primitive priority program property protected
pull0 pull1 pulldown pullup pulsestyle_ondetect pulsestyle_onevent pure rand randc
randcase randsequence rcmos real realtime ref reg reject_on release repeat restrict
return rnmos rpmos rtran rtranif0 rtranif1 s_always s_eventually s_nexttime s_until
s_until_with scalared sequence shortint shortreal showcancelled signed small soft
solve specify specparam static string strong strong0 strong1 struct super supply0
supply1 sync_accept_on sync_reject_on table tagged task this throughout time
timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type
typedef union unique unique0 unsigned until until_with untyped use uwire var vectored
virtual void wait wait_order wand weak weak0 weak1 while wildcard wire with within
wor xnor xor
""".split())


TEMPLATE_ENVIRONMENT = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


def render_template(template_name: str, **context) -> str:
    return TEMPLATE_ENVIRONMENT.get_template(template_name).render(**context)


def project_target_name(project_dir: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", project_dir.name)
    if not name:
        name = "hulotte_project"
    if name[0].isdigit():
        name = f"project_{name}"
    return name


def executable_target_name(project_name: str) -> str:
    if project_name.casefold() in RESERVED_CMAKE_TARGETS:
        return f"hulotte_{project_name}"
    return project_name


def project_files(project_name: str, executable_name: str) -> dict[str, str]:
    context = {"project_name": project_name, "executable_name": executable_name}
    return {
        'CMakeLists.txt': render_template('project/CMakeLists.txt.j2', **context),
        'README.md': render_template('project/README.md.j2', **context),
        'src/main.cpp': render_template('project/main.cpp.j2', **context),
        'src/PassThrough.hpp': render_template('project/PassThrough.hpp.j2', **context),
        'src/PassThrough.cpp': render_template('project/PassThrough.cpp.j2', **context),
        'src/Comparator.hpp': render_template('project/Comparator.hpp.j2', **context),
        'src/Comparator.cpp': render_template('project/Comparator.cpp.j2', **context),
    }


def validate_project_directory(project_dir: Path) -> Path:
    project_dir = project_dir.expanduser().resolve()
    if not project_dir.is_dir() or not (project_dir / "CMakeLists.txt").is_file() or not (project_dir / "src/main.cpp").is_file():
        raise ValueError(f"Not a Hulotte project: {project_dir}")
    return project_dir


def validate_module_name(class_name: str, module_type: str = "custom") -> None:
    if (
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", class_name)
        or class_name in CPP_KEYWORDS
        or "__" in class_name
    ):
        raise ValueError("Module name must be a non-keyword C++ identifier starting with a letter, without double underscores")
    if module_type == "verilator" and class_name in SYSTEMVERILOG_KEYWORDS:
        raise ValueError(f"Module name is a reserved SystemVerilog keyword: {class_name}")


def module_instance_name(class_name: str) -> str:
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = name.lower()
    return f"{name}_module" if name in CPP_KEYWORDS else name


def custom_module_files(class_name: str) -> dict[str, str]:
    return {
        f"src/custom/{class_name}.hpp": render_template("custom/Module.hpp.j2", class_name=class_name),
        f"src/custom/{class_name}.cpp": render_template("custom/Module.cpp.j2", class_name=class_name),
    }


def verilator_module_files(class_name: str) -> dict[str, str]:
    return {
        f"src/hw/{class_name}.sv": render_template("verilator/Module.sv.j2", class_name=class_name),
        f"src/custom/{class_name}.hpp": render_template("verilator/Module.hpp.j2", class_name=class_name),
        f"src/custom/{class_name}.cpp": render_template("verilator/Module.cpp.j2", class_name=class_name),
    }


def preview_custom_module(project_dir: Path, class_name: str) -> str:
    return render_template(
        "custom/preview.txt.j2",
        project_dir=project_dir,
        class_name=class_name,
        instance_name=module_instance_name(class_name),
    )


def preview_verilator_module(project_dir: Path, class_name: str) -> str:
    return render_template(
        "verilator/preview.txt.j2",
        project_dir=project_dir,
        class_name=class_name,
        instance_name=module_instance_name(class_name),
    )


def check_output_paths(project_dir: Path, files: dict[str, str]) -> list[Path]:
    output_paths = [project_dir / relative_path for relative_path in files]
    for path in output_paths:
        try:
            path.resolve().relative_to(project_dir)
        except ValueError as error:
            raise ValueError(f"Output path escapes the project directory: {path}") from error
    existing_paths = [path for path in output_paths if path.exists() or path.is_symlink()]
    if existing_paths:
        existing_names = ", ".join(str(path.relative_to(project_dir)) for path in existing_paths)
        raise FileExistsError(f"Refusing to overwrite existing files: {existing_names}")
    return output_paths


def write_project_files(project_dir: Path, files: dict[str, str]) -> list[Path]:
    output_paths = check_output_paths(project_dir, files)
    created_paths = []
    try:
        for path, contents in zip(output_paths, files.values()):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as output:
                created_paths.append(path)
                output.write(contents)
    except OSError:
        for path in reversed(created_paths):
            path.unlink()
        raise
    return output_paths


def add_custom_module(project_dir: Path, class_name: str) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    validate_module_name(class_name)
    return write_project_files(project_dir, custom_module_files(class_name))


def add_verilator_module(project_dir: Path, class_name: str) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    validate_module_name(class_name, "verilator")
    return write_project_files(project_dir, verilator_module_files(class_name))


def prompt_for_module_details() -> tuple[str, str]:
    print("Available module type:")
    print("  1. Custom C++ StreamPU module")
    print("  2. StreamPU adapter around a Verilator model")
    selection = input("Select module type [1]: ").strip()
    if selection in {"", "1"}:
        module_type = "custom"
    elif selection == "2":
        module_type = "verilator"
    else:
        raise ValueError("Select 1 for a custom module or 2 for a Verilator adapter")
    return module_type, input("Module class name: ").strip()


def confirm_module_creation() -> bool:
    while True:
        response = input("Create these files? [Y/n]: ").strip().lower()
        if response in {"", "y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def create_project(project_dir: Path) -> Path:
    project_dir = project_dir.expanduser().resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty directory: {project_dir}")

    project_name = project_target_name(project_dir)
    executable_name = executable_target_name(project_name)
    files = project_files(project_name, executable_name)
    write_project_files(project_dir, files)
    return project_dir


def stream_pu_path(repository_root: Optional[Path] = None) -> Path:
    repository_root = repository_root or Path(__file__).resolve().parent
    return repository_root / "dependencies" / "streampu"


def stream_pu_is_built(stream_pu_root: Path) -> bool:
    return (
        (stream_pu_root / "include/streampu.hpp").is_file()
        and (stream_pu_root / "build/lib/libstreampu.a").is_file()
    )


def available_compiler() -> Optional[str]:
    configured_compiler = shlex.split(os.environ.get("CXX", ""))
    candidates = configured_compiler[:1] + ["c++", "g++", "clang++"]
    return next((compiler for compiler in candidates if shutil.which(compiler)), None)


def cmake_version() -> Optional[tuple[int, int, int]]:
    if shutil.which("cmake") is None:
        return None
    try:
        result = subprocess.run(["cmake", "--version"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r"cmake version (\d+)\.(\d+)(?:\.(\d+))?", result.stdout, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def missing_install_tools() -> list[str]:
    missing = ["git"] if shutil.which("git") is None else []
    if cmake_version() is None or cmake_version() < (3, 20, 0):
        missing.append("CMake >= 3.20")
    if available_compiler() is None:
        missing.append("C++ compiler (set CXX or install c++, g++, or clang++)")
    return missing


def run_command(command: list[str], cwd: Optional[Path] = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as error:
        raise RuntimeError(f"Required command not found: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Command failed with exit code {error.returncode}: {shlex.join(command)}") from error


def checkout_revision(stream_pu_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(stream_pu_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"Could not read the StreamPU Git revision at {stream_pu_root}") from error
    return result.stdout.strip()


def install_stream_pu(repository_root: Path, dry_run: bool = False) -> Path:
    stream_pu_root = stream_pu_path(repository_root)
    existing_checkout = stream_pu_root.exists() or stream_pu_root.is_symlink()
    if existing_checkout:
        if stream_pu_root.is_symlink() or not (stream_pu_root / ".git").exists():
            raise ValueError(f"Refusing to modify existing non-Git StreamPU path: {stream_pu_root}")
        revision = checkout_revision(stream_pu_root)
        if revision != STREAMPU_REVISION:
            raise ValueError(
                f"StreamPU already exists at {stream_pu_root} but is at {revision}; "
                f"expected {STREAMPU_REVISION}. Move it manually before installing."
            )
        if stream_pu_is_built(stream_pu_root):
            print(f"StreamPU is already installed at {stream_pu_root}")
            return stream_pu_root
    missing_tools = missing_install_tools()
    if missing_tools:
        raise ValueError("Missing required tools: " + ", ".join(missing_tools))
    if dry_run:
        if existing_checkout:
            print(f"Would initialize StreamPU Git submodules at {stream_pu_root}")
        else:
            print(f"Would clone StreamPU {STREAMPU_REVISION} into {stream_pu_root}")
            print("Would initialize its Git submodules, configure CMake, and build libstreampu.a")
        if existing_checkout:
            print("Would configure and build StreamPU")
        return stream_pu_root

    if not existing_checkout:
        dependencies_dir = stream_pu_root.parent
        dependencies_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".hulotte-streampu-", dir=dependencies_dir) as temporary_dir:
            staged_stream_pu = Path(temporary_dir) / "streampu"
            run_command(["git", "clone", "--no-checkout", STREAMPU_URL, str(staged_stream_pu)])
            run_command(["git", "-C", str(staged_stream_pu), "checkout", "--detach", STREAMPU_REVISION])
            run_command(["git", "-C", str(staged_stream_pu), "submodule", "update", "--init", "--recursive"])
            staged_stream_pu.rename(stream_pu_root)
    else:
        run_command(["git", "-C", str(stream_pu_root), "submodule", "update", "--init", "--recursive"])

    run_command([
        "cmake", "-S", str(stream_pu_root), "-B", str(stream_pu_root / "build"),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DSPU_COMPILE_STATIC_LIB=ON",
        "-DSPU_COMPILE_SHARED_LIB=OFF",
        "-DSPU_TESTS=OFF",
    ])
    run_command(["cmake", "--build", str(stream_pu_root / "build"), "--parallel"])
    if not stream_pu_is_built(stream_pu_root):
        raise RuntimeError(f"StreamPU build completed but the expected library is missing under {stream_pu_root}")
    print(f"StreamPU installed at {stream_pu_root}")
    print(f"Configure generated projects with -DSTREAMPU_ROOT={stream_pu_root}")
    return stream_pu_root


def print_dependency_status(repository_root: Path) -> bool:
    stream_pu_root = stream_pu_path(repository_root)
    if stream_pu_is_built(stream_pu_root):
        try:
            revision = checkout_revision(stream_pu_root)
        except RuntimeError:
            revision = "unknown revision"
        expected = revision == STREAMPU_REVISION
        state = "built" if expected else f"built, but expected revision {STREAMPU_REVISION}"
        print(f"StreamPU: {state} ({revision})")
        print(f"Path: {stream_pu_root}")
        return expected
    print(f"StreamPU: not installed at {stream_pu_root}")
    return False


def run_doctor(repository_root: Path) -> int:
    missing_tools = missing_install_tools()
    git_path = shutil.which("git")
    print(f"git: {'available (' + git_path + ')' if git_path else 'missing'}")
    cmake_path = shutil.which("cmake")
    version = cmake_version()
    if cmake_path and version:
        print(f"cmake: available ({cmake_path}, version {'.'.join(map(str, version))})")
    elif cmake_path:
        print(f"cmake: available ({cmake_path}), version could not be determined")
    else:
        print("cmake: missing")
    compiler = available_compiler()
    print(f"C++ compiler: {compiler or 'missing'}")
    stream_pu_ready = print_dependency_status(repository_root)
    if missing_tools:
        print("Install the missing build tools, then rerun hulotte doctor.")
    elif not stream_pu_ready:
        print("Run hulotte deps install to install StreamPU.")
    return 1 if missing_tools or not stream_pu_ready else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create and build readable Hulotte C++ projects")
    parser.add_argument("--version", action="version", version=f"Hulotte {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create a StreamPU project")
    init_parser.add_argument("project_dir", type=Path, help="new project directory")
    module_parser = subparsers.add_parser("module", help="create or add project modules")
    module_subparsers = module_parser.add_subparsers(dest="module_command", required=True)
    add_parser = module_subparsers.add_parser("add", help="create a custom or Verilator-backed StreamPU module")
    add_parser.add_argument("project_dir", type=Path, help="existing Hulotte project directory")
    add_parser.add_argument("--type", dest="module_type", choices=["custom", "verilator"], help="module type; prompt when omitted")
    add_parser.add_argument("--name", help="C++ module class name; prompt when omitted")
    add_parser.add_argument("--yes", action="store_true", help="create files without a confirmation prompt")
    deps_parser = subparsers.add_parser("deps", help="install or inspect native dependencies")
    deps_subparsers = deps_parser.add_subparsers(dest="deps_command", required=True)
    install_parser = deps_subparsers.add_parser("install", help="install the pinned StreamPU dependency")
    install_parser.add_argument("--dry-run", action="store_true", help="show the planned installation without changing files")
    deps_subparsers.add_parser("status", help="show the local StreamPU installation status")
    subparsers.add_parser("doctor", help="check build tools and installed dependencies")
    args = parser.parse_args(argv)

    repository_root = Path(__file__).resolve().parent
    if args.command == "deps":
        try:
            if args.deps_command == "install":
                install_stream_pu(repository_root, args.dry_run)
                return 0
            return 0 if print_dependency_status(repository_root) else 1
        except (OSError, RuntimeError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nCancelled; the dependency checkout was not modified further.", file=sys.stderr)
            return 130

    if args.command == "doctor":
        return run_doctor(repository_root)

    if args.command == "module":
        try:
            project_dir = validate_project_directory(args.project_dir)
            if args.module_type is None and args.name is None:
                module_type, prompted_name = prompt_for_module_details()
            else:
                module_type, prompted_name = args.module_type or "custom", args.name
            class_name = args.name if args.name is not None else prompted_name
            if class_name is None:
                class_name = input("Module class name: ").strip()
            validate_module_name(class_name, module_type)
            files = custom_module_files(class_name) if module_type == "custom" else verilator_module_files(class_name)
            check_output_paths(project_dir, files)

            preview = preview_custom_module if module_type == "custom" else preview_verilator_module
            print(preview(project_dir, class_name), end="")
            if not args.yes and not confirm_module_creation():
                print("Cancelled; no files were created.")
                return 0
            output_paths = write_project_files(project_dir, files)
        except (EOFError, OSError, ValueError, TemplateError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nCancelled; no further files will be created.", file=sys.stderr)
            return 130

        print("Created:")
        for path in output_paths:
            print(f"  {path}")
        print("CMake will discover the new sources on the next build. main.cpp was not modified.")
        return 0

    try:
        project_dir = create_project(args.project_dir)
    except (OSError, ValueError, TemplateError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Created project: {project_dir}")
    print("Build with: cmake -S . -B build -DSTREAMPU_ROOT=" + str(stream_pu_path()))
    print("Then run: cmake --build build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
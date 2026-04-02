#!/usr/bin/env python3
"""
Interactive script to generate a new project based on Hulotte framework.
Supports StreamPU, optional AFF3CT, and optional custom modules.
"""

import os
import sys
import argparse
import json
import math
import wave
import struct
import shutil
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional
from jinja2 import Environment, FileSystemLoader
from hulotte_utils import to_relative_path, print_ascii_art, play_owl_hoot


def render_template(template_name, context):
    """Render a Jinja2 template."""
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


def ask_yes_no(question, default=False):
    """Ask a yes/no question and return boolean."""
    default_str = "y/N" if not default else "Y/n"
    while True:
        response = input(f"{question} [{default_str}]: ").strip().lower()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        elif response == "":
            return default
        else:
            print("Please answer 'y' or 'n'")


def ask_path(question, default=None, must_exist=True):
    """Ask for a path, with optional default."""
    while True:
        if default:
            response = input(f"{question} [{default}]: ").strip()
            if not response:
                response = default
        else:
            response = input(f"{question}: ").strip()
        
        path = Path(response).expanduser()
        if not must_exist or path.exists():
            return str(path.resolve())
        else:
            print(f"Path does not exist: {response}")
            if ask_yes_no("Try anyway?", default=False):
                return str(path.resolve())


def ask_streampu_root(default=None):
    """Ask for StreamPU root and validate libstreampu.a presence."""
    while True:
        root = ask_path("Path to StreamPU directory", default, must_exist=True)
        lib_path = Path(root) / "build" / "lib" / "libstreampu.a"
        if lib_path.exists():
            return root
        print(f"libstreampu.a not found at {lib_path}")
        if not ask_yes_no("Try another StreamPU path?", default=True):
            return root


def ask_aff3ct_root(default=None):
    """Ask for AFF3CT root and validate header presence."""
    while True:
        root = ask_path("Path to AFF3CT directory", default, must_exist=True)
        header_path = Path(root) / "include" / "aff3ct.hpp"
        if header_path.exists():
            return root
        print(f"aff3ct.hpp not found at {header_path}")
        if not ask_yes_no("Try another AFF3CT path?", default=True):
            return root


def ask_name(question, default=None):
    """Ask for a project name."""
    while True:
        if default:
            response = input(f"{question} [{default}]: ").strip()
            if not response:
                response = default
        else:
            response = input(f"{question}: ").strip()
        
        if response and response.replace("_", "").replace("-", "").isalnum():
            return response
        else:
            print("Invalid name. Use alphanumeric characters, hyphens, or underscores.")


def copy_common_files(project_dir, hulotte_dir):
    """Copy Common HW/SW files to project."""
    src_common = Path(hulotte_dir) / "Common" / "streampu"
    dst_common = Path(project_dir) / "common"
    
    if src_common.exists():
        shutil.copytree(src_common, dst_common, dirs_exist_ok=True)
        print(f"✓ Copied common files to common/")
        return True
    else:
        print(f"WARNING: Common directory not found at {src_common}")
        return False


def copy_common_sw_files(project_dir, hulotte_dir):
    """Copy only Common SW support files (e.g. Comparator.hpp) to project.
    Used for StreamPU projects that don't need the full HW common directory."""
    src_sw = Path(hulotte_dir) / "Common" / "streampu" / "sw"
    dst_sw = Path(project_dir) / "common" / "sw"

    if src_sw.exists():
        dst_sw.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_sw, dst_sw, dirs_exist_ok=True)
        print(f"✓ Copied common/sw support files")
        return True
    else:
        print(f"WARNING: Common/sw directory not found at {src_sw}")
        return False


@dataclass
class ProjectConfig:
    """Pure configuration object used by the project generation core API."""
    project_name: str
    output_dir: str
    hulotte_root: str
    streampu_root: str
    use_streampu: bool = True
    use_aff3ct: bool = False
    use_custom: bool = True
    use_hw: bool = False
    aff3ct_root: Optional[str] = None


CONFIG_VERSION = 1
ALLOWED_CONFIG_KEYS = {
    "version",
    "project_name",
    "output_dir",
    "hulotte_root",
    "streampu_root",
    "use_streampu",
    "use_aff3ct",
    "use_custom",
    "use_hw",
    "aff3ct_root",
}


def _require_bool(value, key_name):
    if not isinstance(value, bool):
        raise ValueError(f"'{key_name}' must be a boolean")
    return value


def project_config_from_dict(raw_config, default_hulotte_root=None):
    """Build and validate a ProjectConfig from a plain dict."""
    if not isinstance(raw_config, dict):
        raise ValueError("config root must be a JSON object")

    unknown_keys = set(raw_config.keys()) - ALLOWED_CONFIG_KEYS
    if unknown_keys:
        raise ValueError(f"unknown config keys: {sorted(unknown_keys)}")

    version = raw_config.get("version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ValueError(f"unsupported config version '{version}', expected {CONFIG_VERSION}")

    project_name = raw_config.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise ValueError("'project_name' is required and must be a non-empty string")

    output_dir = raw_config.get("output_dir", ".")
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise ValueError("'output_dir' must be a non-empty string")

    hulotte_root = raw_config.get("hulotte_root", default_hulotte_root)
    if not isinstance(hulotte_root, str) or not hulotte_root.strip():
        raise ValueError("'hulotte_root' is required and must be a non-empty string")

    streampu_root = raw_config.get("streampu_root")
    if not isinstance(streampu_root, str) or not streampu_root.strip():
        raise ValueError("'streampu_root' is required and must be a non-empty string")

    use_streampu = _require_bool(raw_config.get("use_streampu", True), "use_streampu")
    use_aff3ct = _require_bool(raw_config.get("use_aff3ct", False), "use_aff3ct")
    use_custom = _require_bool(raw_config.get("use_custom", True), "use_custom")
    use_hw = _require_bool(raw_config.get("use_hw", False), "use_hw")

    aff3ct_root = raw_config.get("aff3ct_root")
    if aff3ct_root is not None and not isinstance(aff3ct_root, str):
        raise ValueError("'aff3ct_root' must be a string when provided")
    if use_aff3ct and not aff3ct_root:
        raise ValueError("'aff3ct_root' is required when 'use_aff3ct' is true")

    return ProjectConfig(
        project_name=project_name,
        output_dir=output_dir,
        hulotte_root=hulotte_root,
        streampu_root=streampu_root,
        use_streampu=use_streampu,
        use_aff3ct=use_aff3ct,
        use_custom=use_custom,
        use_hw=use_hw,
        aff3ct_root=aff3ct_root,
    )


def load_project_config_file(config_path, default_hulotte_root=None):
    """Load a versioned JSON project config file and return a validated config."""
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = json.load(f)
    return project_config_from_dict(raw_config, default_hulotte_root=default_hulotte_root)


def project_config_to_dict(config: ProjectConfig):
    """Serialize ProjectConfig to the stable versioned JSON schema."""
    return {
        "version": CONFIG_VERSION,
        "project_name": config.project_name,
        "output_dir": config.output_dir,
        "hulotte_root": config.hulotte_root,
        "streampu_root": config.streampu_root,
        "use_streampu": config.use_streampu,
        "use_aff3ct": config.use_aff3ct,
        "use_custom": config.use_custom,
        "use_hw": config.use_hw,
        "aff3ct_root": config.aff3ct_root,
    }


def save_project_config_file(config: ProjectConfig, config_path):
    """Save ProjectConfig to a JSON file."""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(project_config_to_dict(config), f, indent=2)
        f.write("\n")


def generate_project_from_config(config: ProjectConfig, log: Optional[Callable[[str], None]] = None) -> Path:
    """Generate a project from a fully-resolved config.

    This function is the non-interactive core API and does not perform any input().
    """
    if log is None:
        log = lambda _msg: None

    if not config.project_name:
        raise ValueError("project_name cannot be empty")
    if config.use_streampu and not config.streampu_root:
        raise ValueError("streampu_root is required when use_streampu=True")
    if config.use_aff3ct and not config.aff3ct_root:
        raise ValueError("aff3ct_root is required when use_aff3ct=True")

    hulotte_dir = str(Path(config.hulotte_root).resolve())
    streampu_dir = str(Path(config.streampu_root).resolve())
    aff3ct_dir = str(Path(config.aff3ct_root).resolve()) if config.use_aff3ct and config.aff3ct_root else None

    project_dir = Path(config.output_dir).resolve() / config.project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    log(f"\nCreating project in: {to_relative_path(project_dir)}\n")

    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)

    if config.use_hw:
        hw_dir = src_dir / "hw"
        hw_dir.mkdir(exist_ok=True)

        with open(hw_dir / "PassThrough.sv", "w") as f:
            f.write(render_template("PassThrough.sv", {}))
        log("✓ Created src/hw/PassThrough.sv")

        if not copy_common_files(project_dir, hulotte_dir):
            raise RuntimeError(
                "Failed to copy common hardware/software support files "
                f"from {Path(hulotte_dir) / 'Common' / 'streampu'}"
            )

        common_hw_dir = project_dir / "common" / "hw"
        common_hw_dir.mkdir(parents=True, exist_ok=True)

        with open(common_hw_dir / "universal_simulation_top.sv", "w") as f:
            f.write(render_template("universal_simulation_top.sv.j2", {}))
        with open(common_hw_dir / "VerilatorSimulation.hpp", "w") as f:
            f.write(render_template("VerilatorSimulation.hpp.j2", {}))
        log("✓ Generated Verification environment (Universal Top & Verilator wrapper)")

    elif config.use_streampu:
        copy_common_sw_files(project_dir, hulotte_dir)

    cmake_context = {
        "project_name": config.project_name,
        "hulotte_root": hulotte_dir,
        "streampu_root": streampu_dir,
        "aff3ct_root": aff3ct_dir,
        "use_aff3ct": config.use_aff3ct,
        "use_custom": config.use_custom,
        "use_hw": config.use_hw,
        "use_streampu": config.use_streampu,
    }
    with open(project_dir / "CMakeLists.txt", "w") as f:
        f.write(render_template("CMakeLists.txt.j2", cmake_context))
    log("✓ Created CMakeLists.txt")

    main_context = {
        "project_name": config.project_name,
        "use_custom": config.use_custom,
        "use_aff3ct": config.use_aff3ct,
        "use_hw": config.use_hw,
        "use_streampu": config.use_streampu,
    }
    with open(src_dir / "main.cpp", "w") as f:
        f.write(render_template("main.cpp.j2", main_context))
    log("✓ Created src/main.cpp")

    if config.use_custom:
        custom_dir = src_dir / "custom"
        custom_dir.mkdir(exist_ok=True)
        context = {"module_name": "MyModule"}
        with open(custom_dir / "MyModule.hpp", "w") as f:
            f.write(render_template("MyModule.hpp.j2", context))
        log("✓ Created src/custom/MyModule.hpp")
        with open(custom_dir / "MyModule.cpp", "w") as f:
            f.write(render_template("MyModule.cpp.j2", context))
        log("✓ Created src/custom/MyModule.cpp")

    gitignore = """build/
*.a
*.o
*.so
*.dylib
*.exe
.DS_Store
cmake-build-debug/
cmake-build-release/
.idea/
.vscode/
obj_dir/
"""
    with open(project_dir / ".gitignore", "w") as f:
        f.write(gitignore)
    log("✓ Created .gitignore")

    cmake_args_lines = [f'-DSTREAMPU_ROOT="{streampu_dir}"']
    if config.use_aff3ct:
        cmake_args_lines.append(f'-DAFF3CT_ROOT="{aff3ct_dir}"')
    if config.use_hw:
        verilator_prefix = "/usr/local/share/verilator"
        if os.path.exists("/usr/share/verilator/verilator-config.cmake"):
            verilator_prefix = "/usr/share/verilator"
        cmake_args_lines.append(f'-DCMAKE_PREFIX_PATH="{verilator_prefix}"')

    cmake_args_block = " \\\n+    ".join(cmake_args_lines)

    build_script = f"""#!/bin/bash
# Build script for {config.project_name}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BUILD_DIR="${{SCRIPT_DIR}}/build"

mkdir -p "${{BUILD_DIR}}"
cd "${{BUILD_DIR}}"

cmake .. \\
    {cmake_args_block} \\
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./build/{config.project_name}"
else
    echo "Build failed"
    exit 1
fi
"""
    build_script_path = project_dir / "build.sh"
    with open(build_script_path, "w") as f:
        f.write(build_script)
    os.chmod(build_script_path, 0o755)
    log("✓ Created build.sh")

    readme_context = {
        "project_name": config.project_name,
        "streampu_root": streampu_dir,
        "aff3ct_root": aff3ct_dir,
        "hulotte_root": hulotte_dir,
        "use_aff3ct": config.use_aff3ct,
        "use_custom": config.use_custom,
        "use_hw": config.use_hw,
    }
    with open(project_dir / "README.md", "w") as f:
        f.write(render_template("README.md.j2", readme_context))
    log("✓ Created README.md")

    if config.use_hw:
        with open(project_dir / "view_waves.sh", "w") as f:
            f.write(render_template("view_waves.sh.j2", {
                "project_name": config.project_name,
                "hulotte_root": hulotte_dir,
            }))
        os.chmod(project_dir / "view_waves.sh", 0o755)
        log("✓ Created view_waves.sh")

    return project_dir


def create_project(hoot=False, project_name=None, use_streampu=None, use_aff3ct=None, use_custom=None, use_hw=None, streampu_root=None, aff3ct_root=None, output_dir="."):
    """Main project generation function."""
    print_ascii_art()
    if hoot:
        play_owl_hoot()
    print("\n" + "="*60)
    print("HULOTTE PROJECT GENERATOR")
    print("="*60 + "\n")
    
    # Gather user input
    if project_name is None:
        project_name = ask_name("Project name:", "my_spu_project")

    # Use the installation directory of create_project.py, not the current working directory.
    # This allows generating projects from anywhere (e.g., when script is in PATH).
    hulotte_dir = str(Path(__file__).resolve().parent)
    
    # StreamPU is mandatory
    use_streampu = True

    if streampu_root:
        streampu_dir = str(Path(streampu_root).resolve())
    else:
        streampu_dir = ask_streampu_root(None)
    
    if use_aff3ct is None:
        use_aff3ct = ask_yes_no("Use AFF3CT?", default=False)
    
    if use_aff3ct:
        if aff3ct_root:
            aff3ct_dir = str(Path(aff3ct_root).resolve())
        else:
            aff3ct_dir = ask_aff3ct_root(None)
    else:
        aff3ct_dir = None
    
    if use_custom is None:
        use_custom = ask_yes_no("Add custom module?", default=True)

    if use_hw is None:
        use_hw = ask_yes_no("Add hardware simulation (Verilator)?", default=False)
    config = ProjectConfig(
        project_name=project_name,
        output_dir=output_dir,
        hulotte_root=hulotte_dir,
        streampu_root=streampu_dir,
        use_streampu=use_streampu,
        use_aff3ct=use_aff3ct,
        use_custom=use_custom,
        use_hw=use_hw,
        aff3ct_root=aff3ct_dir,
    )

    try:
        project_dir = generate_project_from_config(config, log=print)
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    
    # Summary
    print("\n" + "="*60)
    print("PROJECT CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"\nProject: {project_name}")
    print(f"Location: {to_relative_path(project_dir)}")
    print(f"StreamPU: {to_relative_path(streampu_dir)}")
    print(f"Hulotte: {to_relative_path(hulotte_dir)}")
    print(f"AFF3CT: {'Enabled' if use_aff3ct else 'Disabled'}")
    print(f"Custom module: {'Enabled' if use_custom else 'Disabled'}")
    print(f"Hardware simulation: {'Enabled' if use_hw else 'Disabled'}")
    print(f"\nNext steps:")
    print(f"  1. cd {to_relative_path(project_dir)}")
    print(f"  2. ./build.sh")
    print(f"  3. ./build/{project_name}")
    print()
    
    return True


def run_tui(hoot=False):
    """Lightweight terminal UI wizard for project generation."""
    print_ascii_art()
    if hoot:
        play_owl_hoot()

    print("\n" + "="*60)
    print("HULOTTE PROJECT GENERATOR (TUI)")
    print("="*60 + "\n")

    hulotte_dir = str(Path(__file__).resolve().parent)

    project_name = ask_name("Project name", "my_spu_project")
    output_dir = ask_path("Output directory", ".", must_exist=True)
    streampu_root = ask_streampu_root(str(Path(hulotte_dir) / "streampu"))

    use_aff3ct = ask_yes_no("Use AFF3CT?", default=False)
    aff3ct_root = None
    if use_aff3ct:
        aff3ct_root = ask_aff3ct_root(str(Path(hulotte_dir) / "aff3ct"))

    use_custom = ask_yes_no("Add custom module?", default=True)
    use_hw = ask_yes_no("Add hardware simulation (Verilator)?", default=False)

    config = ProjectConfig(
        project_name=project_name,
        output_dir=output_dir,
        hulotte_root=hulotte_dir,
        streampu_root=streampu_root,
        use_streampu=True,
        use_aff3ct=use_aff3ct,
        use_custom=use_custom,
        use_hw=use_hw,
        aff3ct_root=aff3ct_root,
    )

    # Validate config before final confirmation.
    config = project_config_from_dict(project_config_to_dict(config), default_hulotte_root=hulotte_dir)

    print("\n" + "-"*60)
    print("CONFIG SUMMARY")
    print("-"*60)
    print(f"project_name : {config.project_name}")
    print(f"output_dir   : {to_relative_path(config.output_dir)}")
    print(f"hulotte_root : {to_relative_path(config.hulotte_root)}")
    print(f"streampu_root: {to_relative_path(config.streampu_root)}")
    print(f"use_aff3ct   : {config.use_aff3ct}")
    print(f"use_custom   : {config.use_custom}")
    print(f"use_hw       : {config.use_hw}")
    print(f"aff3ct_root  : {to_relative_path(config.aff3ct_root) if config.aff3ct_root else 'None'}")

    if ask_yes_no("Save this config to a JSON file?", default=True):
        default_cfg = str(Path(config.output_dir).resolve() / f"{config.project_name}.config.json")
        cfg_path = ask_path("Config file path", default_cfg, must_exist=False)
        save_project_config_file(config, cfg_path)
        print(f"✓ Saved config: {to_relative_path(cfg_path)}")

    if not ask_yes_no("Generate project now?", default=True):
        print("Cancelled by user.")
        return False

    project_dir = generate_project_from_config(config, log=print)

    print("\n" + "="*60)
    print("PROJECT CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"\nProject: {config.project_name}")
    print(f"Location: {to_relative_path(project_dir)}")
    print(f"StreamPU: {to_relative_path(config.streampu_root)}")
    print(f"Hulotte: {to_relative_path(config.hulotte_root)}")
    print(f"AFF3CT: {'Enabled' if config.use_aff3ct else 'Disabled'}")
    print(f"Custom module: {'Enabled' if config.use_custom else 'Disabled'}")
    print(f"Hardware simulation: {'Enabled' if config.use_hw else 'Disabled'}")
    print(f"\nNext steps:")
    print(f"  1. cd {to_relative_path(project_dir)}")
    print(f"  2. ./build.sh")
    print(f"  3. ./build/{config.project_name}")
    print()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a new Hulotte project")
    parser.add_argument("positional_name", nargs="?", help="Project name")
    parser.add_argument("--name", dest="flag_name", help="Project name (via flag)")
    parser.add_argument("--config", help="Path to a JSON project config file (versioned schema)")
    parser.add_argument("--output-dir", help="Override output directory")
    parser.add_argument("--tui", action="store_true", help="Run terminal UI wizard")
    parser.add_argument("--hoot", action="store_true", help="Enable startup sound")
    
    # Enable/Disable arguments
    
    # AFF3CT
    parser.add_argument("--aff3ct", action="store_const", const=True, dest="aff3ct", help="Enable AFF3CT support")
    parser.add_argument("--no-aff3ct", action="store_const", const=False, dest="aff3ct", help="Disable AFF3CT support")
    
    # Custom Module
    parser.add_argument("--custom", action="store_const", const=True, dest="custom", help="Enable custom module")
    parser.add_argument("--no-custom", action="store_const", const=False, dest="custom", help="Disable custom module")
    
    # Hardware Simulation
    parser.add_argument("--hw", action="store_const", const=True, dest="hw", help="Enable hardware simulation")
    parser.add_argument("--no-hw", action="store_const", const=False, dest="hw", help="Disable hardware simulation")

    parser.add_argument("--streampu-root", help="Path to StreamPU root")
    parser.add_argument("--aff3ct-root", help="Path to AFF3CT root")
    args = parser.parse_args()

    project_name = args.flag_name if args.flag_name else args.positional_name
    hulotte_dir = str(Path(__file__).resolve().parent)

    if args.tui:
        try:
            success = run_tui(hoot=args.hoot)
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            print("\n\nCancelled by user.")
            sys.exit(1)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    if args.config:
        try:
            config = load_project_config_file(args.config, default_hulotte_root=hulotte_dir)
        except Exception as e:
            print(f"\nERROR: invalid config file '{args.config}': {e}")
            sys.exit(1)

        # Optional CLI overrides on top of config file values
        if project_name:
            config.project_name = project_name
        if args.output_dir:
            config.output_dir = args.output_dir
        if args.streampu_root:
            config.streampu_root = args.streampu_root
        if args.aff3ct_root:
            config.aff3ct_root = args.aff3ct_root
        if args.aff3ct is not None:
            config.use_aff3ct = args.aff3ct
        if args.custom is not None:
            config.use_custom = args.custom
        if args.hw is not None:
            config.use_hw = args.hw

        try:
            config = project_config_from_dict({
                "version": CONFIG_VERSION,
                "project_name": config.project_name,
                "output_dir": config.output_dir,
                "hulotte_root": config.hulotte_root,
                "streampu_root": config.streampu_root,
                "use_streampu": config.use_streampu,
                "use_aff3ct": config.use_aff3ct,
                "use_custom": config.use_custom,
                "use_hw": config.use_hw,
                "aff3ct_root": config.aff3ct_root,
            }, default_hulotte_root=hulotte_dir)
        except Exception as e:
            print(f"\nERROR: invalid effective config after overrides: {e}")
            sys.exit(1)

        print_ascii_art()
        if args.hoot:
            play_owl_hoot()
        print("\n" + "="*60)
        print("HULOTTE PROJECT GENERATOR")
        print("="*60 + "\n")

        try:
            project_dir = generate_project_from_config(config, log=print)
            print("\n" + "="*60)
            print("PROJECT CREATED SUCCESSFULLY!")
            print("="*60)
            print(f"\nProject: {config.project_name}")
            print(f"Location: {to_relative_path(project_dir)}")
            print(f"StreamPU: {to_relative_path(config.streampu_root)}")
            print(f"Hulotte: {to_relative_path(config.hulotte_root)}")
            print(f"AFF3CT: {'Enabled' if config.use_aff3ct else 'Disabled'}")
            print(f"Custom module: {'Enabled' if config.use_custom else 'Disabled'}")
            print(f"Hardware simulation: {'Enabled' if config.use_hw else 'Disabled'}")
            print(f"\nNext steps:")
            print(f"  1. cd {to_relative_path(project_dir)}")
            print(f"  2. ./build.sh")
            print(f"  3. ./build/{config.project_name}")
            print()
            sys.exit(0)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Determine values based on args and interactivity mode
    # If project_name is present, we are in non-interactive mode for unset values -> we apply defaults.
    # If project_name is missing, we are in interactive mode -> we pass None to trigger questions.
    
    is_non_interactive = (project_name is not None)
    
    use_streampu = True
    use_custom   = args.custom   if args.custom is not None else (True if is_non_interactive else None)
    use_aff3ct   = args.aff3ct   if args.aff3ct is not None else (False if is_non_interactive else None)
    use_hw       = args.hw       if args.hw is not None else (False if is_non_interactive else None)

    try:
        success = create_project(
            hoot=args.hoot,
            project_name=project_name,
            use_streampu=use_streampu,
            use_aff3ct=use_aff3ct,
            use_custom=use_custom,
            use_hw=use_hw,
            streampu_root=args.streampu_root,
            aff3ct_root=args.aff3ct_root,
            output_dir=args.output_dir if args.output_dir else "."
        )
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

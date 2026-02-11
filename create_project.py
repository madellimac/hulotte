#!/usr/bin/env python3
"""
Interactive script to generate a new project based on Hulotte framework.
Supports StreamPU, optional AFF3CT, and optional custom modules.
"""

import os
import sys
import argparse
import math
import wave
import struct
import shutil
import tempfile
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def to_relative_path(path):
    """Convert absolute path to relative path from current directory."""
    try:
        path_obj = Path(path).resolve()
        cwd = Path.cwd().resolve()
        try:
            rel_path = path_obj.relative_to(cwd)
            return f"./{rel_path}" if str(rel_path) != "." else "."
        except ValueError:
            # Path is not relative to cwd, return as-is
            return str(path)
    except:
        return str(path)


def render_template(template_name, context):
    """Render a Jinja2 template."""
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


def print_ascii_art():
    """Print hulotte ASCII art if available."""
    try:
        art_path = Path(__file__).resolve().parent / "hulotte.txt"
        if art_path.exists():
            print(art_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def play_wav_file(wav_path):
    """Play a WAV file (best-effort)."""
    if sys.platform.startswith("win"):
        try:
            import winsound
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        except Exception:
            print("\a", end="")
        return
    if sys.platform == "darwin":
        if shutil.which("afplay"):
            subprocess.run(["afplay", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print("\a", end="")
        return

    if shutil.which("paplay"):
        subprocess.run(["paplay", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("aplay"):
        subprocess.run(["aplay", "-q", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("play"):
        subprocess.run(["play", "-q", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("\a", end="")


def play_owl_hoot():
    """Play a short owl-like hoot sound (best-effort)."""
    try:
        sample_rate = 22050
        preset = os.getenv("HULOTTE_HOOT_PRESET", "classic").strip().lower()
        wav_override = os.getenv("HULOTTE_HOOT_WAV", "").strip()
        local_wav = Path(__file__).resolve().parent / "hulotte.wav"

        if local_wav.exists():
            play_wav_file(local_wav)
            return

        if wav_override:
            wav_path = Path(wav_override).expanduser().resolve()
            if wav_path.exists() and wav_path.suffix.lower() == ".wav":
                play_wav_file(wav_path)
                return

        download_dirs = [Path.home() / "Téléchargements", Path.home() / "Downloads"]
        for dl_dir in download_dirs:
            if dl_dir.exists():
                wav_files = sorted(dl_dir.glob("*.wav"))
                if len(wav_files) == 1:
                    play_wav_file(wav_files[0])
                    return

        def synth_hoot(freq_start, freq_end, duration, vibrato_hz=0.0, vibrato_depth=0.0):
            samples = int(sample_rate * duration)
            data = []
            for i in range(samples):
                t = i / sample_rate
                sweep = freq_start + (freq_end - freq_start) * (t / duration)
                if vibrato_hz > 0.0:
                    sweep += vibrato_depth * math.sin(2 * math.pi * vibrato_hz * t)
                env = math.sin(math.pi * t / duration)
                val = 0.5 * env * math.sin(2 * math.pi * sweep * t)
                data.append(int(max(-1.0, min(1.0, val)) * 32767))
            return data

        if preset == "deep":
            hoot_duration = 0.60
            pause_duration = 0.20
            hoot1 = synth_hoot(300, 240, hoot_duration)
            hoot2 = synth_hoot(280, 220, hoot_duration)
        elif preset == "vibrato":
            hoot_duration = 0.50
            pause_duration = 0.18
            hoot1 = synth_hoot(380, 320, hoot_duration, vibrato_hz=5.0, vibrato_depth=12.0)
            hoot2 = synth_hoot(360, 300, hoot_duration, vibrato_hz=5.0, vibrato_depth=12.0)
        elif preset == "soft":
            hoot_duration = 0.55
            pause_duration = 0.20
            hoot1 = synth_hoot(340, 300, hoot_duration)
            hoot2 = synth_hoot(320, 280, hoot_duration)
        else:
            hoot_duration = 0.45
            pause_duration = 0.15
            hoot1 = synth_hoot(360, 320, hoot_duration)
            hoot2 = synth_hoot(340, 300, hoot_duration)

        pause = [0] * int(sample_rate * pause_duration)
        samples = hoot1 + pause + hoot2

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(struct.pack("<h", s) for s in samples))

        play_wav_file(wav_path)

        try:
            os.remove(wav_path)
        except Exception:
            pass
    except Exception:
        print("\a", end="")


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


def create_project(hoot=False, project_name=None, use_streampu=None, use_aff3ct=None, use_custom=None, use_hw=None, streampu_root=None, aff3ct_root=None):
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
        
    output_dir = "." # Default to current directory when running with args, could be improved
    # To support interactive output dir when name is not provided:
    # If project_name is missing, we are in interactive mode -> we pass None to trigger questions.
    
    if project_name is None:
        output_dir = ask_path("Output directory:", ".", must_exist=True)
    else:
        output_dir = "."

    hulotte_dir = str(Path.cwd().resolve())
    
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
    
    # Create project directory
    project_dir = Path(output_dir) / project_name
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"ERROR: Cannot create project directory: {e}")
        return False
    
    print(f"\nCreating project in: {to_relative_path(project_dir)}\n")
    
    # Create source directory
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # HW Support
    if use_hw:
        hw_dir = src_dir / "hw"
        hw_dir.mkdir(exist_ok=True)
        
        with open(hw_dir / "Top_Level.sv", "w") as f:
            f.write(render_template("Top_Level.sv.j2", {}))
        print(f"✓ Created src/hw/Top_Level.sv")
        
        copy_common_files(project_dir, hulotte_dir)

    # Create CMakeLists.txt
    cmake_context = {
        "project_name": project_name,
        "hulotte_root": hulotte_dir,
        "streampu_root": streampu_dir,
        "aff3ct_root": aff3ct_dir,
        "use_aff3ct": use_aff3ct,
        "use_custom": use_custom,
        "use_hw": use_hw,
        "use_streampu": use_streampu
    }
    cmake_content = render_template("CMakeLists.txt.j2", cmake_context)
    
    with open(project_dir / "CMakeLists.txt", "w") as f:
        f.write(cmake_content)
    print(f"✓ Created CMakeLists.txt")
    
    # Create main.cpp
    main_context = {
        "project_name": project_name if project_name else "project",
        "use_custom": use_custom,
        "use_aff3ct": use_aff3ct,
        "use_hw": use_hw,
        "use_streampu": use_streampu
    }
    main_content = render_template("main.cpp.j2", main_context)
    with open(src_dir / "main.cpp", "w") as f:
        f.write(main_content)
    print(f"✓ Created src/main.cpp")
    
    # Create custom module if requested
    if use_custom:
        custom_dir = src_dir / "custom"
        custom_dir.mkdir(exist_ok=True)
        
        header = render_template("MyModule.hpp.j2", {})
        impl = render_template("MyModule.cpp.j2", {})
        
        with open(custom_dir / "MyModule.hpp", "w") as f:
            f.write(header)
        print(f"✓ Created src/custom/MyModule.hpp")
        
        with open(custom_dir / "MyModule.cpp", "w") as f:
            f.write(impl)
        print(f"✓ Created src/custom/MyModule.cpp")
    
    # Create .gitignore
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
    print(f"✓ Created .gitignore")
    
    # Create build script
    cmake_args = f'-DSTREAMPU_ROOT="{streampu_dir}" \\'
    if use_aff3ct:
        cmake_args += f'\n    -DAFF3CT_ROOT="{aff3ct_dir}" \\'
    
    build_script = f"""#!/bin/bash
# Build script for {project_name}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BUILD_DIR="${{SCRIPT_DIR}}/build"

mkdir -p "${{BUILD_DIR}}"
cd "${{BUILD_DIR}}"

cmake .. \\
    {cmake_args}
    -DHULOTTE_ROOT="{hulotte_dir}" \\
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./build/{project_name}"
else
    echo "Build failed"
    exit 1
fi
"""
    build_script_path = project_dir / "build.sh"
    with open(build_script_path, "w") as f:
        f.write(build_script)
    os.chmod(build_script_path, 0o755)
    print(f"✓ Created build.sh")
    
    # Create README
    readme = f"""# {project_name}

Generated by Hulotte framework.

## Build

```bash
./build.sh
```

Or manually:

```bash
mkdir build && cd build
cmake .. \\
    -DSTREAMPU_ROOT={streampu_dir} \\
    -DAFF3CT_ROOT={aff3ct_dir} \\
    -DHULOTTE_ROOT={hulotte_dir}
make -j
```

## Run

```bash
./build/{project_name}
```

## Features

- StreamPU integration: ✓
- AFF3CT support: {"✓" if use_aff3ct else "✗"}
- Custom module: {"✓" if use_custom else "✗"}
- Hardware simulation: {"✓" if use_hw else "✗"}
"""
    with open(project_dir / "README.md", "w") as f:
        f.write(readme)
    print(f"✓ Created README.md")
    
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a new Hulotte project")
    parser.add_argument("positional_name", nargs="?", help="Project name")
    parser.add_argument("--name", dest="flag_name", help="Project name (via flag)")
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
            aff3ct_root=args.aff3ct_root
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

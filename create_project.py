#!/usr/bin/env python3
"""
Interactive script to generate a new project based on Hulotte framework.
Supports StreamPU, optional AFF3CT, and optional custom modules.
"""

import os
import sys
import math
import wave
import struct
import shutil
import tempfile
import subprocess
from pathlib import Path


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


def create_cmakelists(project_name, hulotte_path, streampu_path, aff3ct_path, use_aff3ct, use_custom):
    """Generate CMakeLists.txt content."""
    cmake = f"""cmake_minimum_required(VERSION 3.10)
project({project_name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ============================================================
# DEPENDENCIES
# ============================================================
set(STREAMPU_ROOT "{streampu_path}" CACHE PATH "Path to StreamPU")
set(AFF3CT_ROOT "{aff3ct_path}" CACHE PATH "Path to AFF3CT")
set(HULOTTE_ROOT "{hulotte_path}" CACHE PATH "Path to Hulotte")

# ============================================================
# LOAD HULOTTE ENVIRONMENT
# ============================================================
# Configure StreamPU paths
set(STREAMPU_INCLUDE_DIRS
    ${{STREAMPU_ROOT}}/include
    ${{STREAMPU_ROOT}}/src
    ${{STREAMPU_ROOT}}/lib/rang/include
    ${{STREAMPU_ROOT}}/lib/json/include
)
include_directories(${{STREAMPU_INCLUDE_DIRS}})

# Configure AFF3CT paths (if enabled)
"""
    
    if use_aff3ct:
        cmake += f"""set(AFF3CT_INCLUDE_DIRS
    ${{AFF3CT_ROOT}}/include
    ${{AFF3CT_ROOT}}/src
    ${{AFF3CT_ROOT}}/lib/MIPP/src
    ${{AFF3CT_ROOT}}/lib/cli/src
    ${{AFF3CT_ROOT}}/lib/date/include/date
)
include_directories(${{AFF3CT_INCLUDE_DIRS}})

# Find AFF3CT library
file(GLOB AFF3CT_LIBRARY "${{AFF3CT_ROOT}}/build/lib/libaff3ct*.a")

"""
    
    cmake += f"""
# Find StreamPU library directly
if(EXISTS "${{STREAMPU_ROOT}}/build/lib/libstreampu.a")
    set(STREAMPU_LIBRARY "${{STREAMPU_ROOT}}/build/lib/libstreampu.a")
else()
    message(FATAL_ERROR "libstreampu.a not found at ${{STREAMPU_ROOT}}/build/lib/libstreampu.a")
endif()

# Find cpptrace (optional, for better error messages)
find_library(CPPTRACE_LIBRARY NAMES cpptrace libcpptrace.a
    PATHS ${{STREAMPU_ROOT}}/build/lib/cpptrace/lib)

# Combine all libraries
set(HULOTTE_LIBS ${{STREAMPU_LIBRARY}})
"""
    
    if use_aff3ct:
        cmake += """if(AFF3CT_LIBRARY)
    list(APPEND HULOTTE_LIBS ${AFF3CT_LIBRARY})
    add_definitions(-DHULOTTE_USE_AFF3CT)
    add_definitions(-DAFF3CT_POLAR_BIT_PACKING)
    add_definitions(-DAFF3CT_MULTI_PREC)
endif()
"""
    
    cmake += """if(CPPTRACE_LIBRARY)
    list(APPEND HULOTTE_LIBS ${CPPTRACE_LIBRARY})
    include_directories(${STREAMPU_ROOT}/lib/cpptrace/include)
endif()

add_definitions(-DHULOTTE_USE_STREAMPU)

# ============================================================
# PROJECT SOURCES
# ============================================================
"""
    
    if use_custom:
        cmake += f"""# Custom module
add_library({project_name}_custom STATIC
    src/custom/MyModule.cpp
)
target_include_directories({project_name}_custom PUBLIC src)
target_link_libraries({project_name}_custom PUBLIC ${{HULOTTE_LIBS}})

# Main executable
add_executable({project_name} src/main.cpp)
target_link_libraries({project_name} {project_name}_custom)
"""
    else:
        cmake += f"""# Main executable
add_executable({project_name} src/main.cpp)
target_link_libraries({project_name} ${{HULOTTE_LIBS}})
"""
    
    return cmake

def create_main_cpp(use_custom, use_aff3ct):
    """Generate main.cpp content."""
    includes = "#include <iostream>\n#include <streampu.hpp>\n"
    if use_custom:
        includes += "#include \"custom/MyModule.hpp\"\n"
    
    main = f"""{includes}
using namespace spu;

int main(int argc, char** argv)
{{
    std::cout << "Hulotte project started!\\n";
"""
    
    if use_aff3ct:
        main += """    
    // AFF3CT is available (include it as needed in your code)
    // #include <aff3ct.hpp>
"""
    
    if use_custom:
        main += """    
    // Custom module example
    MyModule my_module;
    my_module.run();
"""
    
    main += """    
    return 0;
}
"""
    return main


def create_custom_module():
    """Generate custom module files."""
    header = """#pragma once

#include <cstdint>
#include <streampu.hpp>

class MyModule
{
public:
    MyModule();
    ~MyModule() = default;
    
    void run();
    
private:
    // Add your custom logic here
};
"""
    
    implementation = """#include "MyModule.hpp"
#include <iostream>

MyModule::MyModule()
{
    std::cout << "MyModule initialized\\n";
}

void MyModule::run()
{
    std::cout << "MyModule::run() called\\n";
    // Implement your logic here
}
"""
    
    return header, implementation


def create_project():
    """Main project generation function."""
    print_ascii_art()
    play_owl_hoot()
    print("\n" + "="*60)
    print("HULOTTE PROJECT GENERATOR")
    print("="*60 + "\n")
    
    # Gather user input
    project_name = ask_name("Project name:", "my_spu_project")
    output_dir = ask_path("Output directory:", ".", must_exist=True)
    
    hulotte_dir = str(Path.cwd().resolve())
    
    streampu_dir = ask_streampu_root("/home/cleroux/PROJECTS/streampu")
    
    use_aff3ct = ask_yes_no("Use AFF3CT?", default=False)
    
    if use_aff3ct:
        aff3ct_dir = ask_aff3ct_root("/home/cleroux/PROJECTS/aff3ct")
    else:
        aff3ct_dir = "/home/cleroux/PROJECTS/aff3ct"
    
    use_custom = ask_yes_no("Add custom module?", default=True)
    
    # Create project directory
    project_dir = Path(output_dir) / project_name
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"ERROR: Cannot create project directory: {e}")
        return False
    
    print(f"\nCreating project in: {project_dir}\n")
    
    # Create source directory
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Create CMakeLists.txt
    cmake_content = create_cmakelists(
        project_name,
        hulotte_dir,
        streampu_dir,
        aff3ct_dir,
        use_aff3ct,
        use_custom
    )
    
    with open(project_dir / "CMakeLists.txt", "w") as f:
        f.write(cmake_content)
    print(f"✓ Created CMakeLists.txt")
    
    # Create main.cpp
    main_content = create_main_cpp(use_custom, use_aff3ct)
    with open(src_dir / "main.cpp", "w") as f:
        f.write(main_content)
    print(f"✓ Created src/main.cpp")
    
    # Create custom module if requested
    if use_custom:
        custom_dir = src_dir / "custom"
        custom_dir.mkdir(exist_ok=True)
        
        header, impl = create_custom_module()
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
"""
    with open(project_dir / ".gitignore", "w") as f:
        f.write(gitignore)
    print(f"✓ Created .gitignore")
    
    # Create build script
    build_script = f"""#!/bin/bash
# Build script for {project_name}

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BUILD_DIR="${{SCRIPT_DIR}}/build"

mkdir -p "${{BUILD_DIR}}"
cd "${{BUILD_DIR}}"

cmake .. \\
    -DSTREAMPU_ROOT="{streampu_dir}" \\
    -DAFF3CT_ROOT="{aff3ct_dir}" \\
    -DHULOTTE_ROOT="{hulotte_dir}" \\
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./{project_name}"
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
"""
    with open(project_dir / "README.md", "w") as f:
        f.write(readme)
    print(f"✓ Created README.md")
    
    # Summary
    print("\n" + "="*60)
    print("PROJECT CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"\nProject: {project_name}")
    print(f"Location: {project_dir}")
    print(f"StreamPU: {streampu_dir}")
    print(f"Hulotte: {hulotte_dir}")
    print(f"AFF3CT: {'Enabled' if use_aff3ct else 'Disabled'}")
    print(f"Custom module: {'Enabled' if use_custom else 'Disabled'}")
    print(f"\nNext steps:")
    print(f"  1. cd {project_dir}")
    print(f"  2. ./build.sh")
    print(f"  3. ./build/{project_name}")
    print()
    
    return True


if __name__ == "__main__":
    try:
        success = create_project()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

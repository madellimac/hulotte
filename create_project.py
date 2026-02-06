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
"""
    if use_aff3ct:
        cmake += f'set(AFF3CT_ROOT "{aff3ct_path}" CACHE PATH "Path to AFF3CT")\n'
    
    cmake += f'set(HULOTTE_ROOT "{hulotte_path}" CACHE PATH "Path to Hulotte")\n\n'
    
    cmake += """# ============================================================
# LOAD HULOTTE ENVIRONMENT
# ============================================================
"""

    if use_aff3ct:
        cmake += """
# Configure AFF3CT paths
set(AFF3CT_INCLUDE_DIRS
    ${AFF3CT_ROOT}/include
    ${AFF3CT_ROOT}/src
    ${AFF3CT_ROOT}/lib/MIPP/src
    ${AFF3CT_ROOT}/lib/cli/src
    ${AFF3CT_ROOT}/lib/date/include/date
)
include_directories(${AFF3CT_INCLUDE_DIRS})

# Find AFF3CT library
file(GLOB AFF3CT_LIBRARY "${AFF3CT_ROOT}/build/lib/libaff3ct*.a")

if(AFF3CT_LIBRARY)
    message(STATUS "Found AFF3CT: ${AFF3CT_LIBRARY}")
    
    # When using AFF3CT, use the StreamPU headers/symbols bundled in AFF3CT
    # to avoid Diamond Dependency / ABI mismatches.
    set(STREAMPU_INCLUDE_DIRS
        ${AFF3CT_ROOT}/lib/streampu/include
        ${AFF3CT_ROOT}/lib/streampu/lib/rang/include
        ${AFF3CT_ROOT}/lib/streampu/lib/json/include
    )
    include_directories(${STREAMPU_INCLUDE_DIRS})
    
    # Link ONLY AFF3CT (it contains StreamPU symbols)
    set(HULOTTE_LIBS ${AFF3CT_LIBRARY})
    
    add_definitions(-DHULOTTE_USE_AFF3CT)
    add_definitions(-DAFF3CT_POLAR_BIT_PACKING)
    add_definitions(-DAFF3CT_MULTI_PREC)
else()
    message(WARNING "AFF3CT library not found! Falling back to standalone StreamPU.")
    
    # Standalone StreamPU
    set(STREAMPU_INCLUDE_DIRS
        ${STREAMPU_ROOT}/include
        ${STREAMPU_ROOT}/src
        ${STREAMPU_ROOT}/lib/rang/include
        ${STREAMPU_ROOT}/lib/json/include
    )
    include_directories(${STREAMPU_INCLUDE_DIRS})
    
    if(EXISTS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
        set(HULOTTE_LIBS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
    else()
        message(FATAL_ERROR "libstreampu.a not found at ${STREAMPU_ROOT}/build/lib/libstreampu.a")
    endif()
endif()
"""
    else:
        # Standard StreamPU Only
        cmake += """
# Configure StreamPU paths
set(STREAMPU_INCLUDE_DIRS
    ${STREAMPU_ROOT}/include
    ${STREAMPU_ROOT}/src
    ${STREAMPU_ROOT}/lib/rang/include
    ${STREAMPU_ROOT}/lib/json/include
)
include_directories(${STREAMPU_INCLUDE_DIRS})

# Find StreamPU library
if(EXISTS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
    set(HULOTTE_LIBS "${STREAMPU_ROOT}/build/lib/libstreampu.a")
else()
    message(FATAL_ERROR "libstreampu.a not found at ${STREAMPU_ROOT}/build/lib/libstreampu.a")
endif()
"""

    cmake += """
# Find cpptrace (optional, for better error messages)
find_library(CPPTRACE_LIBRARY NAMES cpptrace libcpptrace.a
    PATHS ${STREAMPU_ROOT}/build/lib/cpptrace/lib)

if(CPPTRACE_LIBRARY)
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
    
    includes = """#include <iostream>
#include <vector>
#include <fstream>
#include <streampu.hpp>
"""
    if use_aff3ct:
        includes += """#include <aff3ct.hpp>
"""
    if use_custom:
        includes += '#include "custom/MyModule.hpp"\n'

    body = ""
    
    if use_aff3ct:
        # AFF3CT Chain: RS Encoder -> RS Decoder -> Finalizer
        modules = """
    // 1. Modules creation
    
    // RS(255, 239) => t=8, m=8. Bits 2040 -> 1912.
    // NOTE: This uses aff3ct B_32 (32-bit integer) template instantiation.
    const int N_rs = 255;  // Symbols
    const int K_rs = 239;  // Symbols
    const int m = 8;       // Bits per symbol
    const int t = (N_rs - K_rs) / 2; // Correction power
    const int N = N_rs * m; // Total bits
    const int K = K_rs * m; // Info bits

    module::Source_random<> source(K);
    module::Finalizer    <> finalizer(K);
    
    // Create RS Polynomial Generator (needed for RS construction)
    aff3ct::tools::RS_polynomial_generator poly(N_rs, t);
    
    // Create Encoder and Decoder
    aff3ct::module::Encoder_RS<>     encoder(K_rs, N_rs, poly);
    aff3ct::module::Decoder_RS_std<> decoder(K_rs, N_rs, poly);    
"""
        if use_custom:
            modules += """    module::MyModule         my_module(K);
"""

        sockets_bind = """
    // 2. Sockets binding
    using namespace aff3ct::module;
    using namespace aff3ct::tools;
"""
        if use_custom:
            sockets_bind += """    // Init -> Custom -> Encoder -> Decoder -> Finalizer
            
    // Warning: Socket binding uses explicit cast to (int) for C++11 enum classes
    source   [src::tsk::generate][(int)src::sck::generate::out_data] = my_module ["process::in"];
    my_module["process::out"]  = encoder   [enc::tsk::encode][(int)enc::sck::encode::U_K];
    
    encoder  [enc::tsk::encode][(int)enc::sck::encode::X_N] = 
          decoder[dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::Y_N];
          
    decoder  [dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::V_K] = finalizer["finalize::in"];
"""
        else:
            sockets_bind += """    // Init -> Encoder -> Decoder -> Finalizer
            
    source   [src::tsk::generate][(int)src::sck::generate::out_data] = encoder   [enc::tsk::encode][(int)enc::sck::encode::U_K];
    
    encoder[enc::tsk::encode][(int)enc::sck::encode::X_N] = 
          decoder[dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::Y_N];
          
    decoder[dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::V_K] = finalizer["finalize::in"];
"""
    
    # Standard StreamPU Chain: Init -> Incr -> Finalizer
    else:
        modules = """
    // 1. Modules creation
    const int n_elmts = 16;
    module::Initializer<int> initializer(n_elmts);
    module::Incrementer<int> incrementer(n_elmts);
    module::Finalizer  <int> finalizer(n_elmts);
"""
        if use_custom:
            modules += """    module::MyModule         my_module(n_elmts);
"""
    
        sockets_bind = """
    // 2. Sockets binding
"""
        if use_custom:
            sockets_bind += """    initializer["initialize::out"] = incrementer["increment::in"];
    incrementer["increment::out"] = my_module  ["process::in"];
    my_module  ["process::out"]   = finalizer  ["finalize::in"];
"""
        else:
            sockets_bind += """    initializer["initialize::out"] = incrementer["increment::in"];
    incrementer["increment::out"] = finalizer  ["finalize::in"];
"""

    first_task_code = 'first_tasks.push_back(&source("generate"));' if use_aff3ct else 'first_tasks.push_back(&initializer("initialize"));'

    main_content = f"""{includes}
using namespace spu;
using namespace spu::module;

int main(int argc, char** argv)
{{
    std::cout << "Starting Hulotte project..." << std::endl;

{modules}
{sockets_bind}
    
    // 3. Sequence creation
    std::vector<runtime::Task*> first_tasks;
    {first_task_code}

    runtime::Sequence sequence(first_tasks);

    // Configuration
    for (auto& type : sequence.get_tasks_per_types())
        for (auto& t : type)
        {{
            t->set_stats(true);
            t->set_debug(false);
        }}

    // 4. Execution
    std::cout << "Processing..." << std::endl;
    
    // Export dot file for visualization
    std::ofstream file("graph.dot");
    sequence.export_dot(file);

    // Run the sequence
    for (auto i = 0; i < 3; i++)
        sequence.exec_seq(); // Run 1 frame at a time

    // 5. Stats
    std::cout << "\\nEnd of execution." << std::endl;
    tools::Stats::show(sequence.get_tasks_per_types(), true, false);

    return 0;
}}
"""
    return main_content


def create_custom_module():
    """Generate custom module files (StreamPU Stateful module)."""
    header = """#pragma once
#include <streampu.hpp>

namespace spu {
namespace module {

class MyModule : public Stateful
{
private:
    int n_elmts;

public:
    MyModule(const int n_elmts);
    virtual ~MyModule() = default;
    
    virtual MyModule* clone() const override;

protected:
    void _process(const int* in, int* out, const int frame_id);
};

}
}
"""
    
    implementation = """#include "MyModule.hpp"
#include <algorithm>
#include <iostream>

using namespace spu;
using namespace spu::module;

MyModule::MyModule(const int n_elmts)
: Stateful(), n_elmts(n_elmts)
{
    const std::string name = "MyModule";
    this->set_name(name);
    this->set_short_name(name);

    auto &t = this->create_task("process");
    auto p_in  = this->create_socket_in <int>(t, "in",  n_elmts);
    auto p_out = this->create_socket_out<int>(t, "out", n_elmts);

    this->create_codelet(t, [p_in, p_out](Module &m, runtime::Task &t, const size_t frame_id) -> int
    {
        auto &mod = static_cast<MyModule&>(m);
        mod._process(static_cast<int*>(t[p_in].get_dataptr()),
                     static_cast<int*>(t[p_out].get_dataptr()),
                     frame_id);
        return runtime::status_t::SUCCESS;
    });
}

MyModule* MyModule::clone() const
{
    auto m = new MyModule(*this);
    m->deep_copy(*this);
    return m;
}

void MyModule::_process(const int* in, int* out, const int frame_id)
{
    // Minimal example: copy input to output and print trace
    // std::cout << "MyModule processing frame " << frame_id << std::endl;
    std::copy(in, in + this->n_elmts, out);
}
"""
    
    return header, implementation


def create_project(quiet=False, project_name=None, use_aff3ct=None, use_custom=None, streampu_root=None, aff3ct_root=None):
    """Main project generation function."""
    print_ascii_art()
    if not quiet:
        play_owl_hoot()
    print("\n" + "="*60)
    print("HULOTTE PROJECT GENERATOR")
    print("="*60 + "\n")
    
    # Gather user input
    if project_name is None:
        project_name = ask_name("Project name:", "my_spu_project")
        
    output_dir = "." # Default to current directory when running with args, could be improved
    # To support interactive output dir when name is not provided:
    if project_name is None: # Wait, logic above sets it. 
        # Actually ask_name is blocking. If name provided, we skip.
        # But we also have output_dir ask. 
        # For full non-interactive, we should skip output_dir prompt if project_name is provided (assumption).
        pass

    if project_name and not quiet: # If interactive mode mostly
         # If we are fully automated, we might want to skip this.
         # But let's keep it simple: if name is passed, we assume non-interactive for basic stuff.
         pass
    
    # We'll just define logic: if arguments are passed, use them.
    
    # output_dir isn't in args yet, let's just stick to "." or ask if interactive.
    # If project_name IS passed, we assume we want to be less interactive? 
    # Or just asking for output dir is fine?
    # Let's check original code. It asks for output_dir.
    
    if project_name is None:
        output_dir = ask_path("Output directory:", ".", must_exist=True)
    else:
        output_dir = "."

    hulotte_dir = str(Path.cwd().resolve())
    
    if streampu_root:
        streampu_dir = streampu_root
    else:
        streampu_dir = ask_streampu_root(None)
    
    if use_aff3ct is None:
        use_aff3ct = ask_yes_no("Use AFF3CT?", default=False)
    
    if use_aff3ct:
        if aff3ct_root:
            aff3ct_dir = aff3ct_root
        else:
            aff3ct_dir = ask_aff3ct_root(None)
    else:
        aff3ct_dir = None
    
    if use_custom is None:
        use_custom = ask_yes_no("Add custom module?", default=True)
    
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
    print(f"\nNext steps:")
    print(f"  1. cd {to_relative_path(project_dir)}")
    print(f"  2. ./build.sh")
    print(f"  3. ./build/{project_name}")
    print()
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a new Hulotte project")
    parser.add_argument("name", nargs="?", help="Project name")
    parser.add_argument("--quiet", "-q", action="store_true", help="Disable startup sound")
    parser.add_argument("--aff3ct", action="store_true", help="Enable AFF3CT support")
    parser.add_argument("--no-custom", action="store_true", help="Disable custom module")
    parser.add_argument("--streampu-root", help="Path to StreamPU root")
    parser.add_argument("--aff3ct-root", help="Path to AFF3CT root")
    args = parser.parse_args()

    # Determine values based on args and interactivity mode
    use_custom = False if args.no_custom else (True if args.name else None)
    use_aff3ct = True if args.aff3ct else (False if args.name else None)

    try:
        success = create_project(
            quiet=args.quiet,
            project_name=args.name,
            use_aff3ct=use_aff3ct,
            use_custom=use_custom,
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

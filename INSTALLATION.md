# Installing Hulotte

## Current installation model

Hulotte is not currently distributed as a Python package. Run `hulotte.py` from a Hulotte checkout; the generated project is a standalone C++17/CMake project.

Obtain the source archive or checkout for the intended release, and keep its `hulotte.py`, `requirements.txt`, and `templates/` directory together. Local development dependencies and Python environments are not included in a source distribution.

The active workflow requires StreamPU, or AFF3CT when you want to use AFF3CT modules (AFF3CT embeds its own StreamPU). Verilator is optional and only needed when creating a Verilator-backed module. UART and Ethernet are not yet integrated.

## Requirements

- Python 3.9 or later, with pip and virtual environment support.
- Jinja2 3.1 or later, as specified in `requirements.txt`.
- CMake 3.20 or later.
- A C++17 compiler, such as GCC or Clang.
- Git, required by `hulotte deps install` to retrieve StreamPU or AFF3CT.
- StreamPU or AFF3CT, installed by the following steps or supplied as another built source tree.
- Verilator 5 or later, only if you want to generate and build a Verilator-backed module.

On Ubuntu, the compiler and Git can be installed with:

```sh
# Refresh the package index.
sudo apt update
# Install a C++ compiler toolchain and Git.
sudo apt install build-essential git
```

Install or select CMake separately if the system package is older than 3.20. Check the installed version with:

```sh
# Print the installed CMake version.
cmake --version
```

## Install the Python requirements

From the Hulotte repository root:

```sh
# Create a Python environment for Hulotte, if one does not already exist.
python3 -m venv .venv
# Activate the environment in the current shell.
source .venv/bin/activate
# Install the template engine required by the generator.
python -m pip install -r requirements.txt
```

Activate this environment in each shell where you run Hulotte. If `venv` or pip is unavailable, install your operating system's Python virtual environment support first. Keep `hulotte.py` and its `templates/` directory together when moving the checkout.

Jinja2 is required only by the generator. Generated C++ projects build and run without Python or Jinja2.

## Install StreamPU

From the Hulotte repository root, preview and install the pinned StreamPU revision:

```sh
# Preview the clone and build steps without changing files.
python3 hulotte.py deps install --dry-run
# Clone and build StreamPU under dependencies/streampu.
python3 hulotte.py deps install
# Check the managed dependency revision and build status.
python3 hulotte.py deps status
# Check build tools and dependency readiness.
python3 hulotte.py doctor
```

The installer requires Git, CMake 3.20 or later, and a C++ compiler. It clones StreamPU at revision `b036089b872a950ae5fe6eae31e7963a4e043670`, initializes its submodules, and builds a Release static library. It does not install system packages or require `sudo`. A failed source download is cleaned up; if compilation fails, the checkout is kept so the build can be resumed.

The installer refuses to overwrite a non-Git path or a checkout at a different revision. Move that checkout manually before installing if you want Hulotte to create its managed copy. If the pinned checkout already has the expected library, installation is a no-op.

To build a separate StreamPU checkout manually instead:

```sh
# Clone StreamPU and its submodules into your home directory.
git clone --recursive https://github.com/aff3ct/streampu.git "$HOME/streampu"
# Select the StreamPU revision tested with Hulotte 0.1.0.
git -C "$HOME/streampu" checkout b036089b872a950ae5fe6eae31e7963a4e043670
# Synchronize submodules with that revision.
git -C "$HOME/streampu" submodule update --init --recursive
# Configure StreamPU to produce a static library.
cmake -S "$HOME/streampu" -B "$HOME/streampu/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DSPU_COMPILE_STATIC_LIB=ON
# Compile StreamPU.
cmake --build "$HOME/streampu/build" --parallel
```

Check that the expected header and static library exist:

```sh
# Point to the StreamPU source and build tree managed by Hulotte.
export STREAMPU_ROOT="$PWD/dependencies/streampu"
# Confirm the header required by Hulotte is present.
test -f "$STREAMPU_ROOT/include/streampu.hpp"
# Confirm the static library required by Hulotte is present.
test -f "$STREAMPU_ROOT/build/lib/libstreampu.a"
```

If you maintain another built StreamPU checkout, use its root instead:

```sh
# Point to the external StreamPU checkout.
export STREAMPU_ROOT="/path/to/streampu"
```

Run that command from the Hulotte repository root. You can use another path if StreamPU is installed elsewhere.

Do not assume `dependencies/streampu` exists after extracting a source release; it is local development data and is not bundled.

## Install AFF3CT

Choose AFF3CT when your pipeline uses AFF3CT modules. AFF3CT embeds its own StreamPU (v1.9.0), which is the one used by those projects; the standalone StreamPU above is not linked. Run `python3 hulotte.py deps install` and answer `2` when asked which library to install, or select it directly:

```sh
# Preview the clone and build steps without changing files.
python3 hulotte.py deps install --library aff3ct --dry-run
# Clone and build AFF3CT under dependencies/aff3ct.
python3 hulotte.py deps install --library aff3ct
```

Without `--library`, the command asks in a terminal and installs StreamPU only when it is not run in one. The installer clones AFF3CT at revision `60e113d4de30c6954e03ff31770741d28e6fcc07` (v4.1.2), initializes only the submodules needed for the library (`lib/MIPP`, `lib/cli`, `lib/date` and `lib/streampu`), and builds a Release static library without the AFF3CT executable. Building AFF3CT compiles a large template library and uses a lot of memory, so parallel jobs are capped at 8.

The two libraries can coexist under `dependencies/`. A generated project selects one at configure time:

```sh
# StreamPU only.
cmake -S . -B build -DSTREAMPU_ROOT=/path/to/hulotte/dependencies/streampu
# AFF3CT modules; this takes precedence and STREAMPU_ROOT is ignored.
cmake -S . -B build -DAFF3CT_ROOT=/path/to/hulotte/dependencies/aff3ct
```

Projects generated before AFF3CT support do not contain the `AFF3CT_ROOT` block in `CMakeLists.txt`; create a new project or copy the block from `templates/project/CMakeLists.txt.j2`.

## Generate and build a project

Run these commands from the Hulotte repository root, in the same shell where `STREAMPU_ROOT` is set:

```sh
# Generate a new project outside the Hulotte repository.
python3 hulotte.py init "$HOME/projects/my_pipeline"
# Change to the generated project directory.
cd "$HOME/projects/my_pipeline"
# Configure the C++ project with CMake.
cmake -S . -B build
# Compile the generated executable.
cmake --build build
# Run the generated pipeline's smoke test.
ctest --test-dir build --output-on-failure
# Run the executable directly.
./build/my_pipeline
```

The generator refuses to overwrite a non-empty destination directory. Choose a new path if the directory already contains files.

The executable name is derived from the destination directory: punctuation is replaced with underscores, leading digits get a `project_` prefix, and reserved CMake target names get a `hulotte_` prefix. For example, the directory `test` produces `hulotte_test`. The generated README shows the actual executable name.

## Add a Verilator-backed module

Verilator is not required for a StreamPU-only project. Install Verilator 5 or later and ensure its CMake package configuration is available when you need this module type.

From the Hulotte repository root, run the guided assistant and choose the Verilator option:

```sh
# Open the module assistant for an existing project.
python3 hulotte.py module add "$HOME/projects/my_pipeline"
```

Or create the starter block non-interactively:

```sh
# Generate a Verilator-backed StreamPU adapter named FilterBlock.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type verilator --name FilterBlock --yes
```

The command creates `src/hw/FilterBlock.sv` and the C++ StreamPU adapter under `src/custom/`. The SystemVerilog file is a Ready/Valid passthrough example that you should edit for your design. CMake detects the `.sv` file, configures Verilator, and builds the generated model. The command prints the C++ instantiation and socket bindings for manual integration into `src/main.cpp`; it does not modify that file.

## Optional waveform viewers

Verilator adapters generated by the current version can record VCD waveforms readable by Surfer or GTKWave. Neither viewer is needed to build or run the simulation. For example, GTKWave can be installed on Ubuntu with:

```sh
# Install the optional GTKWave waveform viewer.
sudo apt install gtkwave
```

See [the waveform workflow](README.md#view-hardware-waveforms) for constructor arguments and commands. Viewing on a remote SSH host requires a graphical session, or transferring the VCD to a local machine with a viewer installed.

## Run Hulotte's tests

From the Hulotte repository root:

```sh
# Run the CLI project-generation tests.
python3 -m unittest discover -s tests -p 'test_new_project_cli.py' -v
```

## Troubleshooting

If Python reports that `jinja2` is missing, activate the environment where you installed `requirements.txt`. The generator's own `--help` and version output are available with:

```sh
# Show the available CLI commands.
python3 hulotte.py --help
# Print the source release version.
python3 hulotte.py --version
```

If CMake cannot find StreamPU, verify that `STREAMPU_ROOT` points to the StreamPU root, not to its `include/` or `build/` subdirectory. Both required files must exist:

- `$STREAMPU_ROOT/include/streampu.hpp`
- `$STREAMPU_ROOT/build/lib/libstreampu.a`

If CMake cannot locate Verilator, verify its installation and CMake package location. For a nonstandard installation, set `VERILATOR_ROOT` or pass `-Dverilator_DIR=/path/to/verilator/cmake/package` when configuring the generated project.

If a hardware frame times out, inspect the VCD and the Ready/Valid protocol. The initial wrapper requires equal input and output lengths and allows at most `frame_size * 16 + 64` cycles per frame; it reports a timeout rather than silently changing data.

## Tested configuration

The release checks were run on Linux with Python 3.12.3, Jinja2 3.1.2, CMake 3.28.3, GCC 13.3, Verilator 5.028, StreamPU revision `b036089b872a950ae5fe6eae31e7963a4e043670`, and AFF3CT revision `60e113d4de30c6954e03ff31770741d28e6fcc07` (v4.1.2). Other tool versions satisfying the declared requirements have not all been certified. Waveform file contents are tested automatically; graphical viewer behavior is not part of the automated release checks.

The current generator creates a StreamPU source, a custom `PassThrough` module, and a `Comparator` that checks the module output against the source. The guided `hulotte.py module add <project>` command can create custom C++ modules or Verilator-backed adapters, and describe modules from the StreamPU and AFF3CT catalogs; their C++ integration is shown for manual insertion into `main.cpp`. Physical-device I/O integrations are not yet available.

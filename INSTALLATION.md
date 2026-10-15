# Installing Hulotte

## Current installation model

Hulotte is not currently distributed as a Python package. Run `hulotte.py` from a Hulotte checkout; the generated project is a standalone C++17/CMake project.

Obtain the source archive or checkout for the intended release, and keep its `hulotte.py`, `requirements.txt`, and `templates/` directory together. Local development dependencies and Python environments are not included in a source distribution.

The active workflow requires StreamPU. Verilator is optional and only needed when creating a Verilator-backed module. AFF3CT module instantiation, UART, and Ethernet are not yet integrated.

## Requirements

- Python 3.9 or later, with pip and virtual environment support.
- Jinja2 3.1 or later, as specified in `requirements.txt`.
- CMake 3.20 or later.
- A C++17 compiler, such as GCC or Clang.
- Git, if you need to clone StreamPU.
- A built StreamPU source tree containing `include/streampu.hpp` and `build/lib/libstreampu.a`.
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

## Prepare StreamPU

If StreamPU is already built, skip this section and set `STREAMPU_ROOT` to its root directory.

To build a local StreamPU checkout:

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
# Point to the StreamPU source and build tree.
export STREAMPU_ROOT="$HOME/streampu"
# Confirm the header required by Hulotte is present.
test -f "$STREAMPU_ROOT/include/streampu.hpp"
# Confirm the static library required by Hulotte is present.
test -f "$STREAMPU_ROOT/build/lib/libstreampu.a"
```

If you already have a local development checkout under `dependencies/streampu`, use:

```sh
# Point to the local StreamPU checkout.
export STREAMPU_ROOT="$PWD/dependencies/streampu"
```

Run that command from the Hulotte repository root. You can use another path if StreamPU is installed elsewhere.

Do not assume `dependencies/streampu` exists after extracting a source release; it is local development data and is not bundled.

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

The release checks were run on Linux with Python 3.12.3, Jinja2 3.1.2, CMake 3.28.3, GCC 13.3, Verilator 5.028, and StreamPU revision `b036089b872a950ae5fe6eae31e7963a4e043670`. Other tool versions satisfying the declared requirements have not all been certified. Waveform file contents are tested automatically; graphical viewer behavior is not part of the automated release checks.

The current generator creates a StreamPU source, a custom `PassThrough` module, and a `Comparator` that checks the module output against the source. The guided `hulotte.py module add <project>` command can create custom C++ modules or Verilator-backed adapters; their C++ integration is shown for manual insertion into `main.cpp`. Native/AFF3CT catalogs and physical-device I/O integrations are not yet available.

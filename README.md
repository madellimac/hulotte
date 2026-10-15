# Hulotte

Hulotte is currently a minimal generator for C++17/CMake projects using StreamPU. The processing graph stays visible and editable as C++ code, with no GUI or intermediate graph format.

Version **0.1.0** is an initial experimental source release. See [CHANGELOG.md](CHANGELOG.md) for its scope and known limitations.

## Current features

- `python3 hulotte.py init <directory>` creates a standalone project and refuses to overwrite a non-empty directory.
- The generated project contains a `Source_random<int>` source, a custom StreamPU `PassThrough` module, and a `Comparator` module, with the graph explicitly connected in `src/main.cpp`.
- The comparator checks the custom module output against the original source and returns a failure exit code if any elements differ.
- The executable processes three frames and includes a CTest smoke test.
- The generated CMake project locates StreamPU through the `STREAMPU_ROOT` environment variable.
- `hulotte.py module add <project>` guides you through creating a custom C++ StreamPU module and prints the code to integrate manually.
- The same assistant can generate a StreamPU adapter and Ready/Valid SystemVerilog starter block for Verilator.
- CMake automatically discovers added module sources under `src/custom/` on the next build.
- CMake enables Verilator only when a block exists under `src/hw/`.

The assistant does not yet offer a catalog of built-in StreamPU or AFF3CT modules, and it does not edit `main.cpp` for you.

See [INSTALLATION.md](INSTALLATION.md) for setup and installation instructions.

## Requirements

- Python 3.9 or later and Jinja2 (listed in `requirements.txt`).
- CMake 3.20 or later and a C++17 compiler.
- A built StreamPU tree containing `include/streampu.hpp` and `build/lib/libstreampu.a`.
- Verilator 5 or later is only required when generating a Verilator-backed module.

The local StreamPU checkout is under `dependencies/streampu`. For another installation, set `STREAMPU_ROOT` to its root directory.

Install the Python requirements in a virtual environment as described in [INSTALLATION.md](INSTALLATION.md#install-the-python-requirements).

## Create and run a project

Run these commands from the repository root:

```sh
# Point CMake to the local StreamPU sources and library.
export STREAMPU_ROOT="$PWD/dependencies/streampu"
# Generate the project skeleton in your home directory.
python3 hulotte.py init "$HOME/projects/my_pipeline"
# Change to the generated project directory.
cd "$HOME/projects/my_pipeline"
# Configure the project and create build files under build/.
cmake -S . -B build
# Compile the pipeline executable.
cmake --build build
# Run the automated test that checks the pipeline executes.
ctest --test-dir build --output-on-failure
# Run the generated pipeline directly.
./build/my_pipeline
```

The pipeline is defined in `src/main.cpp`. The custom module and comparator are implemented in `src/PassThrough.hpp`, `src/PassThrough.cpp`, `src/Comparator.hpp`, and `src/Comparator.cpp`; edit these files to experiment.

## Add a custom StreamPU module

Run the assistant from the Hulotte repository root:

```sh
# Open the guided custom-module creation flow for an existing project.
python3 hulotte.py module add "$HOME/projects/my_pipeline"
```

The assistant previews the files and C++ integration snippet, then asks before writing. It does not modify `main.cpp`; copy the displayed include, instance, and socket bindings into the graph yourself. For scripted use, provide `--name Gain --yes` to skip the prompts and confirmation.

To create a StreamPU adapter backed by a Verilator model:

```sh
# Open the assistant and choose the Verilator-backed module type.
python3 hulotte.py module add "$HOME/projects/my_pipeline"
# Or create a Verilator module without prompts.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type verilator --name FilterBlock --yes
```

The generated SystemVerilog block starts as a Ready/Valid passthrough example. Edit `src/hw/FilterBlock.sv` to implement the desired hardware behavior. CMake discovers `.sv` files, invokes Verilator during configuration, and compiles the generated model on the next build. The assistant prints the wrapper instantiation and socket bindings; integrate them into `src/main.cpp` manually.

Replace the existing processing-path bindings when inserting a new module; do not connect two producers to the same input socket. Newly added classes are under `hulotte::module`, while the initial example `PassThrough` and `Comparator` are under `spu::module`.

## View hardware waveforms

Newly generated Verilator adapters accept an optional VCD output path. Replace the existing instance declaration in `src/main.cpp` with:

```cpp
hulotte::module::FilterBlock filter_block(frame_size, "traces/filter_block.vcd");
```

The one-argument constructor keeps tracing disabled. Paths are relative to the executable's working directory; parent directories are created automatically. Use a distinct path for each hardware instance. An existing file is replaced on a new simulation run, but two active instances cannot share the same path.

The VCD contains reset, clock, interface signals, and traceable internal signals. Time is continuous across frames, using a 1 ns resolution and 5 ns simulation steps (a nominal 100 MHz clock within a frame). Temporary StreamPU clones do not record traces; parallel worker tracing is not supported in this initial version. The file is flushed after each frame and closed when the adapter is destroyed.

From the generated project directory:

```sh
# Rebuild after enabling tracing in main.cpp.
cmake --build build
# Run from the project directory so traces/ is created there.
./build/my_pipeline
# Open the waveform with Surfer, if installed.
surfer traces/filter_block.vcd
# Alternatively, open it with GTKWave.
gtkwave traces/filter_block.vcd
```

Viewers are optional and are not launched or installed by Hulotte. With remote SSH, open the file locally or use a graphical session on the remote host. Previously generated wrappers are not automatically updated; preserve your edited RTL and port the trace changes explicitly if needed.

## Test the generator

Run this command from the repository root:

```sh
# Run the Hulotte generator tests.
python3 -m unittest discover -s tests -p 'test_new_project_cli.py' -v
```

Native integration tests are optional. Set `HULOTTE_TEST_STREAMPU_ROOT` when CMake and a built StreamPU tree are available. The additional RTL/VCD integration test requires Verilator:

```sh
# Enable custom-module compilation and, if Verilator is installed, RTL/VCD checks.
HULOTTE_TEST_STREAMPU_ROOT="$PWD/dependencies/streampu" python3 -m unittest discover -s tests -p 'test_new_project_cli.py' -v
```

## Generator templates

`hulotte.py` handles CLI arguments, prompts, validation, and file creation. Generated content is stored in Jinja2 templates:

- `templates/project/`: the default C++/CMake project and its README.
- `templates/custom/`: custom C++ modules and their integration preview.
- `templates/verilator/`: SystemVerilog blocks, StreamPU adapters, and their integration preview.

Templates use explicit rendering contexts and `StrictUndefined`: a missing variable causes an error rather than silently generating incomplete code. Templates are located relative to `hulotte.py`, not the current working directory. Generated projects do not need Python or Jinja2 to build and run.

## Not yet available

The new workflow does not yet provide a catalog of built-in StreamPU/AFF3CT modules, AFF3CT module instantiation, UART/Ethernet transports, or dependency installation. Verilator-backed modules are available when Verilator 5 or later is installed. `dependencies/aff3ct` is present locally but is not used by this generator.

The previous generator, its templates and shared components, example projects, and prototypes are archived under `legacy/` for reference. They are not part of the new workflow.

## Release limitations

- Supported installation layout: a built standalone StreamPU source tree, not an arbitrary system-installed library. The tested StreamPU revision and toolchain are recorded in [INSTALLATION.md](INSTALLATION.md).
- Module addition requires the current generated CMake setup. Older projects are not migrated automatically; update their source-discovery and Verilator configuration manually when necessary.
- Each `src/hw/*.sv` file is treated as a top-level, with a module name matching its filename. Hierarchical RTL projects and parameterized designs need manual CMake integration.
- A hardware adapter exchanges exactly `frame_size` 32-bit integers on both input and output. Different frame lengths and framing protocols need an adapted wrapper. A frame exceeding `frame_size * 16 + 64` cycles raises an explicit error.
- Each hardware instance has an independent simulation context and time, reset once at construction and retained between frames. Cross-block, cycle-accurate interaction requires a shared RTL top-level rather than multiple frame-based adapters.
- VCD output is optional and sequential; worker clones do not record traces. Parallel hardware execution and clone state restoration are not certified in this release.
- Debug output is enabled in the default example. For throughput measurements, disable task debug output and VCD recording, and configure CMake with `-DCMAKE_BUILD_TYPE=Release`.

For a source distribution, include `hulotte.py`, `requirements.txt`, `templates/`, `tests/`, `README.md`, `INSTALLATION.md`, `CHANGELOG.md`, and `LICENSE`. Do not bundle local environments, `dependencies/`, `Sandbox/`, caches, or generated build products. `legacy/` is reference material, not required at runtime. Committing, tagging, and publishing are separate release steps.

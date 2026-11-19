# Hulotte

Hulotte is currently a minimal generator for C++17/CMake projects using StreamPU. The processing graph stays visible and editable as C++ code, with no GUI or intermediate graph format.

Version **0.1.0** is an initial experimental source release. See [CHANGELOG.md](CHANGELOG.md) for its scope and known limitations.

## Current features

- `python3 hulotte.py init <directory>` creates a standalone project and refuses to overwrite a non-empty directory.
- The generated project contains a `Source_random<int>` source, a custom StreamPU `Pass_through` module, and a `Comparator` module, with the graph explicitly connected in `src/main.cpp`.
- The comparator checks the custom module output against the original source and returns a failure exit code if any elements differ.
- The executable processes three frames and includes a CTest smoke test.
- The generated CMake project locates StreamPU through the `STREAMPU_ROOT` environment variable.
- `hulotte deps install` installs the pinned StreamPU revision under `dependencies/`, or AFF3CT with its embedded StreamPU; it asks which one in a terminal. `hulotte doctor` checks build tools and dependency status.
- `hulotte.py module add <project>` guides you through creating a custom C++ StreamPU module and prints the code to integrate manually.
- The same assistant can generate a StreamPU adapter and Ready/Valid SystemVerilog starter block for Verilator, with a configurable stream interface and cycle measurements.
- It can also wrap C code behind a fixed three-function API (`--type cfunction`).
- CMake automatically discovers added module sources under `src/custom/` on the next build.
- CMake enables Verilator only when a block exists under `src/hw/`.

- `hulotte module list` shows the catalog of existing StreamPU and AFF3CT modules; `hulotte module add <project> --type streampu|aff3ct --name <id>` prints how to use one (include, instantiation, tasks and sockets) without writing files.

The assistant does not edit `main.cpp` for you.

See [INSTALLATION.md](INSTALLATION.md) for setup and installation instructions.

## Requirements

- Python 3.9 or later and Jinja2 (listed in `requirements.txt`).
- CMake 3.20 or later and a C++17 compiler.
- StreamPU, or AFF3CT (which embeds its own StreamPU), installed with `python3 hulotte.py deps install`.
- Verilator 5 or later is only required when generating a Verilator-backed module.

StreamPU is installed under `dependencies/streampu` and AFF3CT under `dependencies/aff3ct` by `hulotte deps install`. For another installation, set `STREAMPU_ROOT` or `AFF3CT_ROOT` to its root directory. A project uses either StreamPU or AFF3CT; when `AFF3CT_ROOT` is set it takes precedence and `STREAMPU_ROOT` is ignored.

Install the Python requirements in a virtual environment as described in [INSTALLATION.md](INSTALLATION.md#install-the-python-requirements).

## Create and run a project

Run these commands from the repository root:

```sh
# Install the pinned StreamPU checkout and static library if needed.
python3 hulotte.py deps install
# Point generated projects to the managed StreamPU tree.
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

The pipeline is defined in `src/main.cpp`. The custom module and comparator are implemented in `src/Pass_through.hpp`, `src/Pass_through.cpp`, `src/Comparator.hpp`, and `src/Comparator.cpp`; edit these files to experiment. CMake compiles every `.cpp` file directly under `src/`, so these example modules can be deleted once `main.cpp` no longer uses them (re-run `cmake -S . -B build` after adding or removing a file).

## Add a custom StreamPU module

Run the assistant from the Hulotte repository root:

```sh
# Open the guided custom-module creation flow for an existing project.
python3 hulotte.py module add "$HOME/projects/my_pipeline"
```

The assistant previews the files and C++ integration snippet, then asks before writing. It does not modify `main.cpp`; copy the displayed include, instance, and socket bindings into the graph yourself. For scripted use, provide `--name Gain --yes` to skip the prompts and confirmation.

A custom module has one task `process` with an input socket `in` and an output socket `out`. By default both carry `int` elements and have the same frame size: `Gain gain(frame_size)`. Choose other element types with `--in-type` and `--out-type` (any integer type of the stream interface, `float` or `double`), and pass different frame sizes to the second constructor, `Gain gain(n_in, n_out)`:

```sh
# A decoder: n_in float LLRs in, n_out int32_t bits out.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --name My_decoder --in-type float --out-type int32_t --yes
```

Write the processing of one frame in `process()`. The generated codelet calls it for every frame of a StreamPU wave (`set_n_frames()`).

To create a StreamPU adapter backed by a Verilator model:

```sh
# Open the assistant and choose the Verilator-backed module type.
python3 hulotte.py module add "$HOME/projects/my_pipeline"
# Or create a Verilator module without prompts.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type verilator --name Filter_block --yes
```

The generated SystemVerilog block starts as a Ready/Valid passthrough example. Edit `src/hw/Filter_block.sv` to implement the desired hardware behavior. CMake discovers `.sv` files, invokes Verilator during configuration, and compiles the generated model on the next build. The assistant prints the wrapper instantiation and socket bindings; integrate them into `src/main.cpp` manually.

Replace the existing processing-path bindings when inserting a new module; do not connect two producers to the same input socket. Newly added classes are under `hulotte::module`, while the initial example `Pass_through` and `Comparator` are under `spu::module`.

## Use an existing StreamPU or AFF3CT module

The catalog describes modules that already exist in StreamPU and AFF3CT:

```sh
# List the catalog.
python3 hulotte.py module list
# Show how to use the AFF3CT AWGN channel in a project.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type aff3ct --name Channel_AWGN_LLR
```

The command prints the include, the instantiation, and the tasks and sockets to bind (`module["task::socket"]`). It writes no file and does not modify `main.cpp`. The catalog covers `Source_random`, `Relayer` and `Sink_NO` (StreamPU), and from AFF3CT: `Source_random_fast`, `CRC_polynomial`, the repetition codec (`Encoder_repetition_sys`, `Decoder_repetition_std`), the hard decision of an uncoded link (`Decoder_NO`), the polar codec (`Encoder_polar`, `Decoder_polar_SC_naive`, `Decoder_polar_SCL_naive`, `Decoder_polar_SCL_naive_CA`), `Modem_BPSK`, `Channel_AWGN_LLR`, the quantizers `Quantizer_pow2_fast` and `Quantizer_pow2` (with saturation, for hardware LLR formats), and the error counter `Monitor_BFER`. The catalog entries of the polar codec explain how to build the frozen bits. The catalog entries are JSON files under `catalog/`.

To build a project with AFF3CT modules, install AFF3CT and configure with its root instead of the StreamPU one:

```sh
# Install AFF3CT with its embedded StreamPU (choose option 2 when asked).
python3 hulotte.py deps install --library aff3ct
# Configure the project against AFF3CT (path of your Hulotte checkout).
cmake -S . -B build -DAFF3CT_ROOT=/path/to/hulotte/dependencies/aff3ct
```

When `src/main.cpp` includes `aff3ct.hpp` and `AFF3CT_ROOT` is not set, CMake stops at configuration with an explicit message. Only `main.cpp` is checked; an AFF3CT include in `src/custom/` alone is not detected.

AFF3CT noise is passed through the `CP` socket of the channel and the demodulator: bind both to the same `float` array holding the noise standard deviation (sigma). The socket holds one value per frame: one element for one frame per execution, and `F` elements, all set to sigma, after `set_n_frames(F)`. Projects created before this feature have no AFF3CT support in their `CMakeLists.txt`; the assistant says so rather than generating a snippet that cannot build.

## Wrap C code behind a fixed API

A `cfunction` module calls C code through three functions, so that the code needs no StreamPU or C++ knowledge. This suits code supplied by third parties, such as the participants of an implementation contest:

```sh
# Float LLRs in, int32_t bits out.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type cfunction --name Soft_decoder \
    --in-type float --out-type int32_t --yes
```

The command creates `src/custom/soft_decoder_api.h`, which declares the API, an example implementation `src/custom/soft_decoder_impl.c` that copies its input, and the StreamPU adapter `Soft_decoder` (task `process`, sockets `in` and `out`):

```c
soft_decoder_state* soft_decoder_create(int n_in, int n_out);  /* NULL on failure */
int soft_decoder_process(soft_decoder_state* state, const float* in, int32_t* out);  /* 0 on success */
void soft_decoder_destroy(soft_decoder_state* state);
```

Replace the example with the real implementation, in C or in a `.cpp` file that includes the header. Each instance and each StreamPU clone owns its own state, so an implementation that keeps its working memory in the state is thread-safe. A non-zero return code from `process` stops the simulation with an error naming the code. The element types are those of the Verilator modules, plus `float` and `double`. Generated projects compile `src/custom/*.c`; older projects need the C language and this source pattern in their `CMakeLists.txt`.

## Describe the hardware stream interface

By default a Verilator block exchanges one 32-bit `int` per beat on both sides, with as many output as input elements. A hardware decoder usually differs: it reads N quantized LLRs, several per clock cycle, and returns K bits. Describe each side with these options:

| Option | Meaning | Default |
|---|---|---|
| `--in-type`, `--out-type` | C++ element type of the socket: `int`, `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`, `uint32_t` | `int` |
| `--in-width`, `--out-width` | bits of one element on the bus | size of the type |
| `--in-lanes`, `--out-lanes` | elements per beat | 1 |
| `--out-unsigned` | zero-extend output elements | sign extension for a signed type wider than 1 bit |

```sh
# 16 LLRs of 6 bits per beat in, 8 decided bits per beat out.
python3 hulotte.py module add "$HOME/projects/my_pipeline" --type verilator --name Decoder \
    --in-type int8_t --in-width 6 --in-lanes 16 --out-type int32_t --out-width 1 --out-lanes 8 --yes
```

The SystemVerilog block receives `IN_WIDTH`, `IN_LANES`, `OUT_WIDTH` and `OUT_LANES` as parameters; its buses are `IN_LANES*IN_WIDTH` and `OUT_LANES*OUT_WIDTH` bits wide, lane 0 in the least significant bits. Buses wider than 64 bits are supported. `in_last` is high on the last input beat of each frame; a frame whose length is not a multiple of the lanes is padded with zeros. When both sides have the same format, the block starts as a passthrough example; otherwise it is a skeleton to complete.

The adapter takes both frame sizes, in elements:

```cpp
hulotte::module::Decoder decoder(N, K);  // task "simulate", sockets "input" (N x int8_t) and "output" (K x int32_t)
```

## Measure latency and throughput in cycles

A StreamPU execution processes `n_frames` frames (`sequence.set_n_frames(F)` for a whole graph, or `module.set_n_frames(F)`). The Verilator adapter receives these F frames together and streams them back to back: the block can accept frame f+1 while it still outputs frame f, as it would in a real pipeline. The adapter records, for every frame:

- the latency: cycles from the first input beat accepted to the last output beat (0 for a combinational single-beat block);
- the interval: cycles between the first input beats of two consecutive frames of the same execution, that is the initiation interval in steady state.

```cpp
decoder.print_cycle_stats(std::cout);
// Decoder: 1000 frame(s), latency min/mean/max = 70/70/70 cycles, interval min/mean/max = 8/8/8 cycles
```

`get_latency_min()`, `get_latency_mean()`, `get_latency_max()`, the matching `get_interval_*()` accessors and `get_frame_count()` give the same values; `reset_cycle_stats()` clears them. Outputs must come out in frame order. A frame fails with an explicit error when no input or output transfer happens during `get_stall_limit()` cycles (100000 by default, change it with `set_stall_limit()`), or when the block outputs a frame before receiving its first input beat.

## View hardware waveforms

Newly generated Verilator adapters accept an optional VCD output path. Replace the existing instance declaration in `src/main.cpp` with:

```cpp
hulotte::module::Filter_block filter_block(frame_size, "traces/filter_block.vcd");
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
- `templates/cfunction/`: C API headers, example implementations, StreamPU adapters, and their integration preview.

Templates use explicit rendering contexts and `StrictUndefined`: a missing variable causes an error rather than silently generating incomplete code. Templates are located relative to `hulotte.py`, not the current working directory. Generated projects do not need Python or Jinja2 to build and run.

## Not yet available

The new workflow does not yet provide AFF3CT codecs beyond the catalog (repetition and polar codecs, CRC, BPSK modem, AWGN channel, quantizers and error counter), or UART/Ethernet transports to an FPGA. StreamPU and AFF3CT installation is available through `hulotte deps install`. Verilator-backed modules are available when Verilator 5 or later is installed.

The previous generator, its templates and shared components, example projects, and prototypes are archived under `legacy/` for reference. They are not part of the new workflow.

## Release limitations

- Supported installation layout: a built standalone StreamPU source tree, not an arbitrary system-installed library. The tested StreamPU revision and toolchain are recorded in [INSTALLATION.md](INSTALLATION.md).
- Module addition requires the current generated CMake setup. Older projects are not migrated automatically; update their source-discovery and Verilator configuration manually when necessary.
- Each `src/hw/*.sv` file is treated as a top-level, with a module name matching its filename. Hierarchical RTL projects and parameterized designs need manual CMake integration.
- A hardware adapter exchanges integer elements of up to 32 bits over a Ready/Valid stream with `in_last`; the output side is always ready (no back-pressure). Other framing protocols need an adapted wrapper.
- Each hardware instance has an independent simulation context and time, reset once at construction and retained between frames. Cross-block, cycle-accurate interaction requires a shared RTL top-level rather than multiple frame-based adapters.
- VCD output is optional and sequential; worker clones do not record traces. Parallel hardware execution and clone state restoration are not certified in this release.
- Debug output is enabled in the default example. For throughput measurements, disable task debug output and VCD recording. Generated projects build in `Release` by default; pass `-DCMAKE_BUILD_TYPE=Debug` to debug.

For a source distribution, include `hulotte.py`, `requirements.txt`, `templates/`, `tests/`, `README.md`, `INSTALLATION.md`, `CHANGELOG.md`, and `LICENSE`. Do not bundle local environments, `dependencies/`, `Sandbox/`, caches, or generated build products. `legacy/` is reference material, not required at runtime. Committing, tagging, and publishing are separate release steps.

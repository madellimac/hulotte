# Changelog

## Unreleased

- Verilator adapters record the simulation check for synthesis: `record_cycle_point(condition)` stores the cycle counts of an operating condition (such as an Eb/N0), and `mark_verified(test_name)` writes `synth/verified/<Block>.yml` with the SHA-256 of the RTL, the interface parameters and the cycle points. Generated projects compute the RTL hash over every `.sv` under `src/hw/` except `src/hw/synth/` (`hulotte_rtl_hash.hpp`, re-configured when the RTL changes). `hulotte synth status` compares the RTL with these records.
- `hulotte synth add` writes the Odatix workspace of a Verilator block under `synth/`: architecture settings, the checked interface configuration read from the adapter (`verified.txt`), Vivado target (`xc7a100t-csg324-1` by default), and a wrapper registering the inputs and outputs of the block (`src/hw/synth/<Block>_synth_top.sv`, ignored by Verilator; `--no-wrap-io` to skip it). First step of the Odatix integration described in `doc/spec_odatix.md`.
- On x86-64, `hulotte deps install` compiles StreamPU and AFF3CT with `-march=native`, and generated projects add it too (CMake option `HULOTTE_NATIVE_ARCH`). Fixed: AFF3CT pipelines stopped with `mipp::mul<int32_t> (SSE2) is undefined!`, MIPP falling back to SSE2. An AFF3CT installed by an older Hulotte must be removed and reinstalled.
- Generated projects build in `Release` by default when no build type is given.
- Generated projects fail at CMake configuration with an explicit message when `src/main.cpp` includes `aff3ct.hpp` without `AFF3CT_ROOT`.
- Verilator modules describe their stream interface: element type, bit width and lanes per beat on each side (`--in-type`, `--in-width`, `--in-lanes`, `--out-type`, `--out-width`, `--out-lanes`, `--out-unsigned`), with different input and output frame sizes and buses wider than 64 bits. The generated block receives these values as SystemVerilog parameters and an `in_last` frame marker.
- Verilator adapters stream all the frames of an execution back to back and record per-frame latency and initiation interval in cycles (`print_cycle_stats()` and accessors). The fixed per-frame cycle limit is replaced by a configurable stall limit.
- `cfunction` modules wrap C code behind a `create` / `process` / `destroy` API with one state per instance and per clone, and an example implementation. Generated projects enable the C language and compile `src/custom/*.c`.
- The AFF3CT catalog describes `Source_random_fast`, `CRC_polynomial`, the polar codec (`Encoder_polar`, `Decoder_polar_SC_naive`, `Decoder_polar_SCL_naive`, `Decoder_polar_SCL_naive_CA`), `Quantizer_pow2` with saturation, and `Monitor_BFER`, enough for a CA-SCL error-rate simulation.
- Generated projects compile every `.cpp` file directly under `src/`, so the example `Pass_through` and `Comparator` modules can be removed without editing `CMakeLists.txt`.
- The AFF3CT catalog describes `Decoder_NO`, the hard decision of an uncoded link.
- Custom C++ modules accept `--in-type` and `--out-type` (integer types, `float`, `double`) and a second constructor `(n_in, n_out)` for different input and output frame sizes.
- Fixed: a custom C++ module processed only the first frame of a StreamPU wave when several frames were set with `set_n_frames()`.
- Names follow the style of AFF3CT and StreamPU: the example module of generated projects is `Pass_through` (`src/Pass_through.hpp`, `src/Pass_through.cpp`), and the documentation uses class names such as `Filter_block`.
- The catalog and the README state that the `CP` (sigma) socket of the AFF3CT channel and demodulator holds one value per frame, so a wave of `F` frames needs `F` values.
- Fixed: a Verilator adapter processed only the first frame when a task carried several frames.
- Fixed: Verilator adapters failed to link with Verilator 5.018 (undefined `sc_time_stamp()`).

## 0.1.0

Initial experimental source release. Publication and tagging are separate steps.

### Features

- Standalone C++17/CMake project generation with an explicit StreamPU graph.
- A default random source, custom pass-through module, and data comparator.
- Guided or non-interactive custom C++ and Verilator module creation.
- Integration snippets for manual edits to `main.cpp`.
- Optional per-instance VCD recording, continuous across frames.
- External Jinja2 templates with strict variable checking.

### Release hardening

- Explicit errors for incomplete Verilator frames, handled by the generated executable.
- Safe confirmation and cancellation before writing module files.
- Shared output validation, refusal of overwrites and paths outside the project, and cleanup of files created during failed writes.
- Rendering before project directory creation, with actionable template errors.
- C++/SystemVerilog name validation and safe names for reserved CMake targets.
- Automated generation tests and optional real Verilator/VCD integration tests, including two distinct hardware blocks in cascade.

### Known limitations

AFF3CT codecs beyond the initial catalog, physical UART/Ethernet adapters, automatic graph editing, package installation via pip, and migration of older generated projects are not included. StreamPU and AFF3CT can be installed with `hulotte deps install`, and existing StreamPU and AFF3CT modules are described by `hulotte module list` and `module add --type streampu|aff3ct`. Hardware wrappers support equal-length 32-bit integer frames with a fixed cycle limit. See the README and installation guide for supported layouts and execution limits.
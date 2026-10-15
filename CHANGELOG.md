# Changelog

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

AFF3CT catalogs, physical UART/Ethernet adapters, dependency installation, automatic graph editing, package installation via pip, and migration of older generated projects are not included. Hardware wrappers support equal-length 32-bit integer frames with a fixed cycle limit. See the README and installation guide for supported layouts and execution limits.
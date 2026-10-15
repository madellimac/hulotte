# Hulotte Copilot Instructions

## Overview

The active Hulotte workflow is a Python project generator for standalone C++17/CMake projects using StreamPU. The generated processing graph is explicit in `src/main.cpp` and can be edited directly.

The current generator creates a `Source_random<int>` source, a custom `PassThrough` module, and a `Comparator` that checks the output against the source. `hulotte.py module add <project>` creates custom C++ modules or StreamPU adapters for Verilator and prints snippets for manual integration. CMake discovers sources under `src/custom/` and enables Verilator when `src/hw/*.sv` files are present. Native/AFF3CT catalogs, UART, Ethernet, and dependency installation are not yet implemented in the active workflow.

## Repository layout

- `hulotte.py`: active CLI entry point; use `python3 hulotte.py init <directory>` to create a project.
- `templates/project/`, `templates/custom/`, and `templates/verilator/`: active Jinja2 templates for generated files and integration previews.
- `requirements.txt`: generator dependency on Jinja2.
- `tests/test_new_project_cli.py`: tests for the active generator.
- `README.md`: current prerequisites, usage, and feature status.
- `legacy/`: archived scripts, Jinja templates, shared components, old projects, GUI prototypes, and generated test artifacts. Do not use these as the active implementation unless explicitly requested.
- `dependencies/`: local third-party source checkouts. Do not modify or translate upstream dependency contents.

## Active workflow conventions

- Keep the generated graph explicit and readable in C++ `main.cpp`; do not introduce a required GUI or an opaque intermediate format.
- Custom StreamPU modules should inherit from an appropriate StreamPU module base such as `spu::module::Stateful`.
- Connect tasks through StreamPU sockets, for example `source["task::socket"] = destination["task::socket"]`.
- Generated projects use CMake and resolve StreamPU through `STREAMPU_ROOT`.
- Keep generated project files standalone and editable after initialization.
- Keep generated C++/CMake/SystemVerilog content in templates rather than inline Python strings. Render with `StrictUndefined` and resolve template paths relative to the CLI script.

## Language

All Hulotte-maintained documentation, comments, and user-facing messages must be written in English. Preserve technical identifiers and third-party text as-is.

## Archived workflow

Legacy `add_*.py` scripts were designed to be idempotent using `--id` and content comparison:
- `0`: a change was applied successfully.
- `2`: no-op because the same resource already exists.
- `1`: validation error or conflicting resource.

These rules apply only when explicitly working on the archived scripts.

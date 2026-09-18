```
 ,_,
(o,o)
{`"'}
-"-"-
```

# Hulotte - Hybrid Unified Libraries for Opensource TesTing of Embedded systems

Modular framework to build processing chains with StreamPU and AFF3CT.

## 1) Installation

From the Hulotte repository root, install the native dependencies with the
CMake preset that matches your needs:

```bash
cmake --preset streampu-only
cmake --build --preset streampu-only
```

The available presets are:

- `streampu-only`: standalone StreamPU, recommended for graph projects;
- `aff3ct-only`: AFF3CT and its bundled StreamPU;
- `streampu-aff3ct`: standalone StreamPU and AFF3CT;
- `all-dependencies`: standalone StreamPU, AFF3CT and optional Surfer support.

Install Hulotte and its Python dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Verify the installation:

```bash
hulotte --help
```

For the `streampu-only` preset, configure StreamPU with the source path used
by the preset:

```bash
hulotte config set streampu-root build/dependencies/streampu-only/dependencies/src/streampu
hulotte config show
```

The CMake build currently generates the dependency manifest in the selected
build directory. Automatic import of that manifest into Hulotte configuration
will be added in a later step.

You can now create and build a graph project:

```bash
hulotte init "$HOME/projects/my_pipeline"
cd "$HOME/projects/my_pipeline"
hulotte generate
hulotte build
```

The legacy `framework/install_dependencies.py` script is still available for
compatibility, but CMake presets are the recommended installation method.

## 2) CLI graph workflow

The graph workflow uses `pipeline.yaml` and generates C++ and CMake artifacts
without copying Hulotte's catalog, templates, or common sources into the
project. A local `catalog/modules.yaml` is used when present; otherwise the
installed catalog is used.

### 2.1 Create and build an external project

```bash
hulotte init "$HOME/projects/my_pipeline"
cd "$HOME/projects/my_pipeline"
hulotte generate
hulotte build
```

Explicit roots remain available for advanced or reproducible builds:

```bash
hulotte init "$HOME/projects/my_pipeline" \
    --hulotte-root /path/to/hulotte \
    --streampu-root /path/to/streampu

hulotte build \
    --streampu-root /path/to/streampu \
    --aff3ct-root /path/to/aff3ct
```

`hulotte generate` creates `generated/main.cpp`. `hulotte build` configures
and builds under `generated/build/`. The generated files are artifacts and
should not be edited manually.

The graph workflow currently supports StreamPU, custom modules, and the
initial AFF3CT RS catalog entries. Verilator and UART remain part of the
legacy workflow.

### 2.2 Development invocation

The same commands can be run without installing the package:

```bash
python3 -m framework.hulotte init /path/to/project
python3 -m framework.hulotte generate --project-root /path/to/project
python3 -m framework.hulotte build --project-root /path/to/project
```

## 3) Legacy project workflow

Recommended flow:
1. Create a base project with `framework/create_project.py`
2. Add modules incrementally with `framework/add_*.py`
3. Validate `hulotte.project.json`
4. Build and run

Default behavior note:
- In non-interactive mode, omitted feature flags now default to a minimal setup
    (`--no-aff3ct --no-custom --no-hw --no-uart-io`).
- Legacy behavior remains available explicitly (for example with `--custom`).

### 3.1 Minimal project

```bash
python3 framework/create_project.py --name my_project \
    --no-aff3ct --no-custom --no-hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 3.2 Project with HW support (required for hardware add scripts)

```bash
python3 framework/create_project.py --name my_hw_project \
    --no-aff3ct --no-custom --hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 3.3 Add modules incrementally

Add a custom StreamPU module:

```bash
./framework/add_custom_module.py \
    --project-root /path/to/my_project \
    --name DataProcessor \
    --id data_processor_main
```

Add a Verilator hardware block:

```bash
./framework/add_hardware_module.py \
    --project-root /path/to/my_hw_project \
    --name FilterBlock \
    --id filter_block_main
```

Add a UART-wrapped hardware block:

```bash
./framework/add_uart_hw_module.py \
    --project-root /path/to/my_hw_project \
    --name UartWrappedFilter \
    --id uart_wrapped_filter_main
```

### 3.4 Validate manifest

Each generated project includes `hulotte.project.json`.

```bash
./framework/create_project.py --validate-manifest /path/to/my_project/hulotte.project.json
```

If you are in a project directory:

```bash
/path/to/hulotte/framework/create_project.py --validate-manifest
```

### 3.5 Build and run

```bash
cd /path/to/my_project
./build.sh
./build/my_project
```

### 3.6 Exit codes for add scripts

- `0`: changes applied successfully
- `2`: idempotent no-op (same module/id already present)
- `1`: error

### 3.7 Idempotence notes

All `add_*.py` scripts are idempotent by `--id`:
- re-running with the same `--id` and same content should return `2`
- using a new `--id` adds a new module instance
- use `--force` only to overwrite an existing conflicting definition

All add scripts also support:
- `--dry-run` to preview changes
- legacy positional arguments for backward compatibility

## 3) Run integration checks

Run the repository test flow:

```bash
./tests/integration/test.sh
```

This script checks:
- project generation matrix
- manifest validation per generated project
- build and run of generated executables
- add scripts idempotence (`exit 2` expected on second identical run)

Generated projects are created in a temporary directory and removed when the
script exits. Set `HULOTTE_TEST_OUTPUT_DIR=/path/to/output` to keep them for
debugging.
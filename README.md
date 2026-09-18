```
 ,_,
(o,o)
{`"'}
-"-"-
```

# Hulotte - Hybrid Unified Libraries for Opensource TesTing of Embedded systems

Modular framework to build processing chains with StreamPU and AFF3CT.

## 1) Installation

### Prerequisites
- GCC/Clang with C++11 support
- CMake >= 3.10
- Git

### Automated installation (recommended)

If AFF3CT and/or StreamPU are not installed, you can use the automated installer:

```bash
python3 framework/install_dependencies.py
```

After installation, use Hulotte's virtual environment so that PyYAML and
Jinja2 are available:

```bash
source .venv/bin/activate
python -m unittest discover -s tests/unit -v
python framework/hulotte.py generate --project-root tests/unit/fixtures/minimal_project
```

Alternatively, prefix commands with `.venv/bin/python` without activating it.

With a local StreamPU build, the software-only fixture can also be compiled
and executed:

```bash
python hulotte.py build \
    --project-root tests/unit/fixtures/minimal_project \
    --streampu-root /path/to/streampu
```

The command generates a minimal CMake project under `generated/build/`. The
graph workflow supports StreamPU, custom modules, and the initial AFF3CT RS
catalog entry; Verilator and UART remain part of the legacy workflow for now.

AFF3CT RS support is also available in the graph catalog. It uses the AFF3CT
embedded StreamPU headers and requires both roots:

```bash
python hulotte.py build \
    --project-root /path/to/aff3ct_project \
    --streampu-root /path/to/streampu \
    --aff3ct-root /path/to/aff3ct
```

The initial catalog supports `Encoder_RS<int>` and
`Decoder_RS_std<int, float>`, sharing one `RS_polynomial_generator`.
Standalone StreamPU is not linked into an AFF3CT target; it is used only to
locate the compatible `cpptrace` library.

The script will:
- Check prerequisites (git, cmake, g++)
- Ask if you want to install AFF3CT (with StreamPU compiled statically inside)
- Ask if you want to install StreamPU standalone
- Clone, configure, and compile libraries

### Manual installation

#### AFF3CT (with StreamPU compiled statically)

```bash
git clone --recursive https://github.com/aff3ct/aff3ct.git
cd aff3ct && mkdir build && cd build
cmake .. -DAFF3CT_COMPILE_STATIC_LIB=ON -DSPU_COMPILE_STATIC_LIB=ON
make -j
```

Expected files:
- `libaff3ct-*.a` in `.../vendor/aff3ct/build/lib/`
- `libstreampu.a` in `.../vendor/aff3ct/build/lib/streampu/lib/`

#### StreamPU standalone

```bash
git clone --recursive https://github.com/aff3ct/streampu.git
cd streampu && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DSPU_COMPILE_STATIC_LIB=ON
make -j
```

Expected file:
- `libstreampu.a` in `.../vendor/streampu/build/lib/`

# Hulotte - Hybrid Unified Libraries for Opensource TesTing of Embedded systems

Modular framework to build processing chains with StreamPU and AFF3CT.
## 2) Create and compose a project (recommended workflow)

Recommended flow:
1. Create a base project with `framework/create_project.py`
2. Add modules incrementally with `framework/add_*.py`
3. Validate `hulotte.project.json`
4. Build and run

Default behavior note:
- In non-interactive mode, omitted feature flags now default to a minimal setup
    (`--no-aff3ct --no-custom --no-hw --no-uart-io`).
- Legacy behavior remains available explicitly (for example with `--custom`).

### 2.0.1 External user projects

The graph workflow can create projects outside the Hulotte source tree. Hulotte
keeps its catalog and Python implementation in its own installation; the user
project contains only its configuration, pipeline, sources, and generated
artifacts:

```bash
python hulotte.py init "$HOME/projects/my_pipeline" \
    --hulotte-root /path/to/hulotte \
    --streampu-root /path/to/streampu

cd "$HOME/projects/my_pipeline"
python /path/to/hulotte/hulotte.py generate
```

`generate` first accepts a project-local `catalog/modules.yaml` when present,
then falls back to the catalog under `--hulotte-root`, `HULOTTE_HOME`, or the
Hulotte source installation. It does not copy `framework/common/` or
`framework/templates/` into the user project. The legacy `create_project.py`
workflow remains available for existing projects.

### 2.0 Graph generation preview

The graph-oriented workflow is currently available for StreamPU and custom
modules. A project contains `pipeline.yaml` and `catalog/modules.yaml`; the
command validates the graph before creating `generated/main.cpp`:

```bash
python3 framework/hulotte.py generate --project-root /path/to/project
```

The generated file is an artifact and should not be edited manually. AFF3CT,
Verilator, UART, CMake generation, and integration with the legacy project
generator are introduced in later steps.

### 2.1 Minimal project

```bash
python3 framework/create_project.py --name my_project \
    --no-aff3ct --no-custom --no-hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 2.2 Project with HW support (required for hardware add scripts)

```bash
python3 framework/create_project.py --name my_hw_project \
    --no-aff3ct --no-custom --hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 2.3 Add modules incrementally

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

### 2.4 Validate manifest

Each generated project includes `hulotte.project.json`.

```bash
./framework/create_project.py --validate-manifest /path/to/my_project/hulotte.project.json
```

If you are in a project directory:

```bash
/path/to/hulotte/framework/create_project.py --validate-manifest
```

### 2.5 Build and run

```bash
cd /path/to/my_project
./build.sh
./build/my_project
```

### 2.6 Exit codes for add scripts

- `0`: changes applied successfully
- `2`: idempotent no-op (same module/id already present)
- `1`: error

### 2.7 Idempotence notes

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
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
- GCC/Clang with C++17 support
- CMake >= 3.16
- Git
- Python >= 3.9

### Installation de Hulotte

Install Hulotte from the repository to make the `hulotte` command available
from any directory:

```bash
python3 -m pip install .
```

For development without installation, use:

```bash
python3 -m framework.hulotte --help
```

The package installs the Python dependencies (`PyYAML` and `Jinja2`) and the
catalog and templates required by generated projects.

### Automated installation (recommended)

If AFF3CT and/or StreamPU are not installed, you can use the automated installer:

```bash
python3 framework/install_dependencies.py
```

After installing the native dependencies, run the CLI directly:

```bash
hulotte --help
hulotte config show
hulotte generate --project-root tests/unit/fixtures/minimal_project
```

The unit tests can be run from the repository with:

```bash
python3 -m unittest discover -s tests/unit -v
```

### Configuration de StreamPU

Hulotte validates a StreamPU installation by checking for:

- `include/streampu.hpp`
- `build/lib/libstreampu.a`

Store the installation once in the user configuration:

```bash
hulotte config set streampu-root /path/to/streampu
hulotte config show
hulotte config unset streampu-root
```

The configuration is stored at `$XDG_CONFIG_HOME/hulotte/config.yaml`, or at
`~/.config/hulotte/config.yaml` when `XDG_CONFIG_HOME` is not set. The
`HULOTTE_STREAMPU_ROOT` environment variable is also supported.

StreamPU resolution uses this priority:

1. an explicit `--streampu-root` option;
2. the project configuration;
3. the user configuration;
4. `HULOTTE_STREAMPU_ROOT` or `STREAMPU_ROOT`;
5. standard local or system paths.

With a local StreamPU build, the software-only fixture can also be compiled
and executed:

```bash
hulotte build \
    --project-root tests/unit/fixtures/minimal_project \
    --streampu-root /path/to/streampu
```

The command generates a minimal CMake project under `generated/build/`. The
graph workflow supports StreamPU, custom modules, and the initial AFF3CT RS
catalog entry; Verilator and UART remain part of the legacy workflow for now.

AFF3CT RS support is also available in the graph catalog. It uses the AFF3CT
embedded StreamPU headers and requires both roots:

```bash
hulotte build \
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
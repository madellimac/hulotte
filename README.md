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
python3 install_dependencies.py
```

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
- `libaff3ct-*.a` in `.../aff3ct/build/lib/`
- `libstreampu.a` in `.../aff3ct/build/lib/streampu/lib/`

#### StreamPU standalone

```bash
git clone --recursive https://github.com/aff3ct/streampu.git
cd streampu && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DSPU_COMPILE_STATIC_LIB=ON
make -j
```

Expected file:
- `libstreampu.a` in `.../streampu/build/lib/`

## 2) Create and compose a project (recommended workflow)

Recommended flow:
1. Create a base project with `create_project.py`
2. Add modules incrementally with `add_*.py`
3. Validate `hulotte.project.json`
4. Build and run

Default behavior note:
- In non-interactive mode, omitted feature flags now default to a minimal setup
    (`--no-aff3ct --no-custom --no-hw --no-uart-io`).
- Legacy behavior remains available explicitly (for example with `--custom`).

### 2.1 Minimal project

```bash
python3 create_project.py --name my_project \
    --no-aff3ct --no-custom --no-hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 2.2 Project with HW support (required for hardware add scripts)

```bash
python3 create_project.py --name my_hw_project \
    --no-aff3ct --no-custom --hw --no-uart-io \
    --streampu-root /path/to/streampu
```

### 2.3 Add modules incrementally

Add a custom StreamPU module:

```bash
./add_custom_module.py \
    --project-root /path/to/my_project \
    --name DataProcessor \
    --id data_processor_main
```

Add a Verilator hardware block:

```bash
./add_hardware_module.py \
    --project-root /path/to/my_hw_project \
    --name FilterBlock \
    --id filter_block_main
```

Add a UART-wrapped hardware block:

```bash
./add_uart_hw_module.py \
    --project-root /path/to/my_hw_project \
    --name UartWrappedFilter \
    --id uart_wrapped_filter_main
```

### 2.4 Validate manifest

Each generated project includes `hulotte.project.json`.

```bash
./create_project.py --validate-manifest /path/to/my_project/hulotte.project.json
```

If you are in a project directory:

```bash
./create_project.py --validate-manifest
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
./test.sh
```

This script checks:
- project generation matrix
- manifest validation per generated project
- build and run of generated executables
- add scripts idempotence (`exit 2` expected on second identical run)
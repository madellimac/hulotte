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

### Automated Installation (Recommended)

If AFF3CT and/or StreamPU are not installed, you can use the automated installer:

```bash
python3 install_dependencies.py
```

The script will:
- Check prerequisites (git, cmake, g++)
- Ask if you want to install AFF3CT (with StreamPU compiled statically inside)
- Ask if you want to install StreamPU standalone
- Clone, configure, and compile the libraries automatically
- Save installation paths in `INSTALL_INFO.txt`

### Manual Installation

#### AFF3CT (with StreamPU compiled statically)

```bash
git clone --recursive https://github.com/aff3ct/aff3ct.git
cd aff3ct && mkdir build && cd build
cmake .. -DAFF3CT_COMPILE_STATIC_LIB=ON -DSPU_COMPILE_STATIC_LIB=ON
make -j
```

> Expected files: 
> - `libaff3ct-*.a` in `.../aff3ct/build/lib/`
> - `libstreampu.a` in `.../aff3ct/build/lib/streampu/lib/`

#### StreamPU standalone

```bash
git clone --recursive https://github.com/aff3ct/streampu.git
cd streampu && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DSPU_COMPILE_STATIC_LIB=ON
make -j
```

> Expected file: `libstreampu.a` in `.../streampu/build/lib/`

## 2) Create a project

Use the interactive generator:

```bash
python3 create_project.py
```

The script will ask for:
- project name
- StreamPU path
- AFF3CT path (if enabled)
- whether to add a custom module

Then:

```bash
cd <project_name>
./build.sh
./build/<project_name>
```

## 3) Run the examples

From Hulotte:

```bash
mkdir -p build && cd build

# StreamPU only
cmake .. -DSTREAMPU_ROOT=/path/to/streampu \
         -DHULOTTE_USE_AFF3CT=OFF
make -j
./examples/ex1_spu_only/ex1_spu_only

# StreamPU + custom
./examples/ex2_spu_custom/ex2_spu_custom
```

With AFF3CT:

```bash
cmake .. -DSTREAMPU_ROOT=/path/to/streampu \
         -DHULOTTE_USE_AFF3CT=ON \
         -DAFF3CT_ROOT=/path/to/aff3ct
make -j
./examples/ex3_spu_aff3ct/ex3_spu_aff3ct
```
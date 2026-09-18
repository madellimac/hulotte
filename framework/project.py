"""Project-level orchestration for graph generation."""

from pathlib import Path
import subprocess

import yaml
from .catalog import load_catalog
from .generator import write_cpp
from .paths import PathResolutionError, resolve_catalog
from .pipeline import load_pipeline
from .validation import validate_pipeline


class ProjectGenerationError(ValueError):
    """Raised when a project cannot be generated."""


def generate_project(
    project_root: str | Path,
    catalog_path: str | Path | None = None,
    pipeline_path: str | Path | None = None,
    output_path: str | Path | None = None,
    hulotte_root: str | Path | None = None,
) -> Path:
    """Validate a project graph and generate its C++ artifact.

    All inputs are resolved before creating the output directory. This keeps a
    failed validation from leaving a partially generated project behind.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ProjectGenerationError(f"project directory not found: {root}")
    project_config = _load_project_config(root)
    hulotte_root = hulotte_root or project_config.get("hulotte", {}).get("root")
    if not hulotte_root:
        hulotte_root = None

    pipeline_file = _resolve_path(root, pipeline_path, "pipeline.yaml")
    if not pipeline_file.is_file():
        raise ProjectGenerationError(f"pipeline file not found: {pipeline_file}")

    try:
        catalog_file = resolve_catalog(root, catalog_path, hulotte_root)
    except PathResolutionError as error:
        raise ProjectGenerationError(str(error)) from error

    pipeline = load_pipeline(pipeline_file)
    catalog = load_catalog(catalog_file)
    capabilities = {kind: True for kind in {module.kind for module in pipeline.modules.values()}}
    validate_pipeline(pipeline, capabilities=capabilities, require_source=False)

    destination = _resolve_path(root, output_path, "generated/main.cpp")
    return write_cpp(destination, pipeline, catalog)


def build_project(
    project_root: str | Path,
    streampu_root: str | Path | None = None,
    aff3ct_root: str | Path | None = None,
    build_path: str | Path | None = None,
    hulotte_root: str | Path | None = None,
) -> Path:
    """Generate, configure, and build a software-only graph project."""
    root = Path(project_root).resolve()
    project_config = _load_project_config(root)
    streampu_root = streampu_root or project_config.get("dependencies", {}).get("streampu_root")
    aff3ct_root = aff3ct_root or project_config.get("dependencies", {}).get("aff3ct_root")
    hulotte_root = hulotte_root or project_config.get("hulotte", {}).get("root")
    generated_main = generate_project(root, hulotte_root=hulotte_root)
    pipeline = load_pipeline(_resolve_path(root, None, "pipeline.yaml"))
    uses_aff3ct = any(module.kind == "aff3ct" for module in pipeline.modules.values())
    if uses_aff3ct:
        aff_root = _resolve_aff3ct_root(root, aff3ct_root)
        stream_root = _resolve_streampu_root(root, streampu_root)
    else:
        aff_root = None
        stream_root = _resolve_streampu_root(root, streampu_root)
    generated_root = generated_main.parent
    cmake_file = generated_root / "CMakeLists.txt"
    cmake_file.write_text(
        _cmake_project(root.name, stream_root, aff3ct_root=aff_root), encoding="utf-8"
    )

    build_dir = _resolve_path(root, build_path, "generated/build")
    _run_command(
        ["cmake", "-S", str(generated_root), "-B", str(build_dir)],
        root,
    )
    _run_command(["cmake", "--build", str(build_dir)], root)
    executable = build_dir / root.name
    if not executable.is_file():
        raise ProjectGenerationError(f"build completed but executable was not found: {executable}")
    return executable


def _resolve_path(root: Path, path: str | Path | None, default: str) -> Path:
    resolved = Path(path) if path is not None else Path(default)
    if not resolved.is_absolute():
        resolved = root / resolved
    return resolved.resolve()


def _resolve_streampu_root(root: Path, configured: str | Path | None) -> Path:
    if configured is not None:
        stream_root = Path(configured)
        if not stream_root.is_absolute():
            stream_root = root / stream_root
    else:
        config_file = root / "project.yaml"
        external_config_file = root / "hulotte.project.yaml"
        config_file = config_file if config_file.is_file() else external_config_file
        if not config_file.is_file():
            raise ProjectGenerationError(
                "StreamPU root is required; pass streampu_root or provide project.yaml"
            )
        with config_file.open("r", encoding="utf-8") as file_desc:
            config = yaml.safe_load(file_desc) or {}
        configured_root = config.get("streampu_root")
        configured_root = configured_root or config.get("dependencies", {}).get("streampu_root")
        stream_root = Path(configured_root or "")
        if not stream_root.is_absolute():
            stream_root = root / stream_root

    stream_root = stream_root.resolve()
    library = stream_root / "build" / "lib" / "libstreampu.a"
    headers = stream_root / "include" / "streampu.hpp"
    if not library.is_file() or not headers.is_file():
        raise ProjectGenerationError(
            f"invalid StreamPU root '{stream_root}'; expected {headers} and {library}"
        )
    return stream_root


def _resolve_aff3ct_root(root: Path, configured: str | Path | None) -> Path:
    if configured is None:
        raise ProjectGenerationError("AFF3CT root is required for an AFF3CT pipeline")
    aff_root = Path(configured)
    if not aff_root.is_absolute():
        aff_root = root / aff_root
    aff_root = aff_root.resolve()
    headers = aff_root / "include" / "aff3ct.hpp"
    libraries = list((aff_root / "build" / "lib").glob("libaff3ct*.a"))
    if not headers.is_file() or not libraries:
        raise ProjectGenerationError(
            f"invalid AFF3CT root '{aff_root}'; expected {headers} and libaff3ct*.a"
        )
    return aff_root


def _cmake_project(
    project_name: str, streampu_root: Path, aff3ct_root: Path | None = None
) -> str:
    if aff3ct_root is not None:
        return _cmake_aff3ct_project(project_name, aff3ct_root, streampu_root)
    return f'''cmake_minimum_required(VERSION 3.16)
project({project_name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(STREAMPU_ROOT "{streampu_root}")
find_package(Threads REQUIRED)
set(STREAMPU_INCLUDE_DIRS
    ${{STREAMPU_ROOT}}/include
    ${{STREAMPU_ROOT}}/src
    ${{STREAMPU_ROOT}}/lib/rang/include
    ${{STREAMPU_ROOT}}/lib/json/include
    ${{STREAMPU_ROOT}}/lib/cpptrace/include
)

file(GLOB CUSTOM_SOURCES "${{CMAKE_CURRENT_SOURCE_DIR}}/../src/custom/*.cpp")
add_executable({project_name} main.cpp ${{CUSTOM_SOURCES}})
target_include_directories({project_name} PRIVATE
    ${{CMAKE_CURRENT_SOURCE_DIR}}/../src
    ${{STREAMPU_INCLUDE_DIRS}}
)
target_compile_definitions({project_name} PRIVATE SPU_STACKTRACE)
target_link_libraries({project_name} PRIVATE
    ${{STREAMPU_ROOT}}/build/lib/libstreampu.a
    ${{STREAMPU_ROOT}}/build/lib/cpptrace/lib/libcpptrace.a
    Threads::Threads
)
'''


def _cmake_aff3ct_project(
    project_name: str, aff3ct_root: Path, cpptrace_root: Path
) -> str:
    libraries = sorted((aff3ct_root / "build" / "lib").glob("libaff3ct*.a"))
    aff3ct_library = libraries[0]
    return f'''cmake_minimum_required(VERSION 3.16)
project({project_name} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Threads REQUIRED)

set(AFF3CT_ROOT "{aff3ct_root}")
set(CPPTRACE_ROOT "{cpptrace_root}")
file(GLOB CUSTOM_SOURCES "${{CMAKE_CURRENT_SOURCE_DIR}}/../src/custom/*.cpp")
add_executable({project_name} main.cpp ${{CUSTOM_SOURCES}})
target_include_directories({project_name} PRIVATE
    ${{AFF3CT_ROOT}}/include
    ${{AFF3CT_ROOT}}/src
    ${{AFF3CT_ROOT}}/lib/MIPP/src
    ${{AFF3CT_ROOT}}/lib/cli/src
    ${{AFF3CT_ROOT}}/lib/date/include/date
    ${{AFF3CT_ROOT}}/lib/streampu/include
    ${{AFF3CT_ROOT}}/lib/streampu/lib/rang/include
    ${{AFF3CT_ROOT}}/lib/streampu/lib/json/include
    ${{CPPTRACE_ROOT}}/lib/cpptrace/include
    ${{CMAKE_CURRENT_SOURCE_DIR}}/../src
)
target_compile_definitions({project_name} PRIVATE
    AFF3CT_MULTI_PREC AFF3CT_POLAR_BIT_PACKING HULOTTE_USE_AFF3CT
    HULOTTE_USE_STREAMPU SPU_STACKTRACE
)
target_link_libraries({project_name} PRIVATE
    "{aff3ct_library}"
    "{cpptrace_root}/build/lib/cpptrace/lib/libcpptrace.a"
    Threads::Threads
)
'''


def _run_command(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise ProjectGenerationError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{output}"
        )


def _load_project_config(root: Path) -> dict:
    config_file = root / "hulotte.project.yaml"
    if not config_file.is_file():
        return {}
    with config_file.open("r", encoding="utf-8") as file_desc:
        config = yaml.safe_load(file_desc) or {}
    if not isinstance(config, dict):
        raise ProjectGenerationError(f"project config must be a mapping: {config_file}")
    return config


def init_project(
    project_path: str | Path,
    hulotte_root: str | Path | None = None,
    streampu_root: str | Path | None = None,
    aff3ct_root: str | Path | None = None,
) -> Path:
    """Create an external user project without copying Hulotte sources."""
    root = Path(project_path).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ProjectGenerationError(f"project directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "src" / "custom").mkdir(parents=True, exist_ok=True)
    (root / "hardware" / "sv").mkdir(parents=True, exist_ok=True)
    (root / "generated").mkdir(exist_ok=True)

    config = [
        "schema_version: 1",
        "project:",
        f"  name: {root.name}",
        "hulotte:",
        f"  root: {Path(hulotte_root).expanduser().resolve() if hulotte_root else ''}",
        "dependencies:",
        f"  streampu_root: {Path(streampu_root).expanduser().resolve() if streampu_root else ''}",
        f"  aff3ct_root: {Path(aff3ct_root).expanduser().resolve() if aff3ct_root else ''}",
        "capabilities:",
        "  streampu: true",
        "  custom: true",
        "  aff3ct: false",
        "  verilator: false",
        "  uart: false",
        "",
    ]
    (root / "hulotte.project.yaml").write_text("\n".join(config), encoding="utf-8")
    (root / "pipeline.yaml").write_text(
        """modules:\n  source:\n    type: streampu\n    catalog: source_random_int\n    parameters:\n      frame_size: 16\n    sockets:\n      generate:\n        outputs:\n          out_data: {type: int32, frame_size: 16}\nconnections: []\n""",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("generated/\nbuild/\n", encoding="utf-8")
    return root

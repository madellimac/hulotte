#!/usr/bin/env python3
"""Create readable C++ StreamPU projects and guide module creation."""

import argparse
import difflib
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

__version__ = "0.1.0"
STREAMPU_URL = "https://github.com/aff3ct/streampu.git"
STREAMPU_REVISION = "b036089b872a950ae5fe6eae31e7963a4e043670"
AFF3CT_URL = "https://github.com/aff3ct/aff3ct.git"
AFF3CT_REVISION = "60e113d4de30c6954e03ff31770741d28e6fcc07"
# 'conf' and 'refs' only hold simulator data and are not needed to build the library.
AFF3CT_SUBMODULES = ("lib/MIPP", "lib/cli", "lib/date", "lib/streampu")
# AFF3CT translation units are memory hungry, so parallel jobs are capped.
AFF3CT_MAX_BUILD_JOBS = 8
CATALOG_LIBRARIES = ("streampu", "aff3ct")
CATALOG_SOCKET_DIRECTIONS = ("in", "out", "fwd")

# Integer element types allowed on generated module sockets, with their size in bits.
# "int" keeps the historical default of the generated modules.
ELEMENT_TYPES = {
    "int": 32,
    "int8_t": 8,
    "uint8_t": 8,
    "int16_t": 16,
    "uint16_t": 16,
    "int32_t": 32,
    "uint32_t": 32,
}
# Software modules (custom C++ and cfunction) may also exchange floating-point elements,
# which hardware buses do not carry.
CFUNCTION_TYPES = {**ELEMENT_TYPES, "float": 32, "double": 64}
# Stream interface options that also apply to custom and cfunction modules.
CFUNCTION_INTERFACE_OPTIONS = ("in_type", "out_type")
# Widest Ready/Valid data bus (lanes x width) accepted for a Verilator block.
MAX_BUS_WIDTH = 4096
DEFAULT_STREAM_INTERFACE = {
    "in_type": "int",
    "out_type": "int",
    "in_width": None,
    "out_width": None,
    "in_lanes": 1,
    "out_lanes": 1,
    "out_unsigned": False,
}


# Synthesis with Odatix (`hulotte synth`): supported tools, and defaults of `synth add`.
SYNTH_TOOLS = ("vivado",)
DEFAULT_SYNTH_TARGET = "xc7a100t-csg324-1"  # Nexys A7
DEFAULT_SYNTH_FREQUENCY = 100  # MHz, default frequency of a fixed-frequency synthesis
DEFAULT_FMAX_BOUNDS = (50, 500)  # MHz, bounds of the Fmax search
# Interface constants of a Verilator adapter, written in src/custom/<Block>.hpp by `module add`.
VERILATOR_INTERFACE_CONSTANTS = ("in_width", "in_lanes", "out_width", "out_lanes")
# Registry of the files that Hulotte generated in a project and that `hulotte update` may rewrite.
GENERATED_REGISTRY = ".hulotte/generated.json"
RESERVED_CMAKE_TARGETS = {
    "all",
    "clean",
    "edit_cache",
    "help",
    "install",
    "list_install_components",
    "package",
    "package_source",
    "preinstall",
    "rebuild_cache",
    "test",
}

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit",
    "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch",
    "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const",
    "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return",
    "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else",
    "enum", "explicit", "export", "extern", "false", "float", "for", "friend", "goto",
    "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept", "not",
    "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
    "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof",
    "static", "static_assert", "static_cast", "struct", "switch", "synchronized", "template",
    "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union",
    "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
}

SYSTEMVERILOG_KEYWORDS = set("""
accept_on alias always always_comb always_ff always_latch and assert assign assume
automatic before begin bind bins binsof bit break buf bufif0 bufif1 byte case casex
casez cell chandle checker class clocking cmos config const constraint context
continue cover covergroup coverpoint cross deassign default defparam design disable
dist do edge else end endcase endchecker endclass endclocking endconfig endfunction
endgenerate endgroup endinterface endmodule endpackage endprimitive endprogram
endproperty endspecify endsequence endtable endtask enum event eventually expect
export extends extern final first_match for force foreach forever fork forkjoin
function generate genvar global highz0 highz1 if iff ifnone ignore_bins illegal_bins
implements implies import incdir include initial inout input inside int integer
interconnect interface intersect join join_any join_none large let liblist library
local localparam logic longint macromodule matches medium modport module nand
negedge nettype new nexttime nmos nor noshowcancelled not notif0 notif1 null or output
package packed parameter pmos posedge primitive priority program property protected
pull0 pull1 pulldown pullup pulsestyle_ondetect pulsestyle_onevent pure rand randc
randcase randsequence rcmos real realtime ref reg reject_on release repeat restrict
return rnmos rpmos rtran rtranif0 rtranif1 s_always s_eventually s_nexttime s_until
s_until_with scalared sequence shortint shortreal showcancelled signed small soft
solve specify specparam static string strong strong0 strong1 struct super supply0
supply1 sync_accept_on sync_reject_on table tagged task this throughout time
timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type
typedef union unique unique0 unsigned until until_with untyped use uwire var vectored
virtual void wait wait_order wand weak weak0 weak1 while wildcard wire with within
wor xnor xor
""".split())


TEMPLATE_ENVIRONMENT = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


def render_template(template_name: str, **context) -> str:
    return TEMPLATE_ENVIRONMENT.get_template(template_name).render(**context)


def project_target_name(project_dir: Path) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", project_dir.name)
    if not name:
        name = "hulotte_project"
    if name[0].isdigit():
        name = f"project_{name}"
    return name


def executable_target_name(project_name: str) -> str:
    if project_name.casefold() in RESERVED_CMAKE_TARGETS:
        return f"hulotte_{project_name}"
    return project_name


def project_files(project_name: str, executable_name: str) -> dict[str, str]:
    context = {"project_name": project_name, "executable_name": executable_name}
    return {
        'CMakeLists.txt': render_template('project/CMakeLists.txt.j2', **context),
        'README.md': render_template('project/README.md.j2', **context),
        'src/main.cpp': render_template('project/main.cpp.j2', **context),
        'src/Pass_through.hpp': render_template('project/Pass_through.hpp.j2', **context),
        'src/Pass_through.cpp': render_template('project/Pass_through.cpp.j2', **context),
        'src/Comparator.hpp': render_template('project/Comparator.hpp.j2', **context),
        'src/Comparator.cpp': render_template('project/Comparator.cpp.j2', **context),
    }


def validate_project_directory(project_dir: Path) -> Path:
    project_dir = project_dir.expanduser().resolve()
    if not project_dir.is_dir() or not (project_dir / "CMakeLists.txt").is_file() or not (project_dir / "src/main.cpp").is_file():
        raise ValueError(f"Not a Hulotte project: {project_dir}")
    return project_dir


def validate_module_name(class_name: str, module_type: str = "custom") -> None:
    if (
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", class_name)
        or class_name in CPP_KEYWORDS
        or "__" in class_name
    ):
        raise ValueError("Module name must be a non-keyword C++ identifier starting with a letter, without double underscores")
    if module_type == "verilator" and class_name in SYSTEMVERILOG_KEYWORDS:
        raise ValueError(f"Module name is a reserved SystemVerilog keyword: {class_name}")


def module_instance_name(class_name: str) -> str:
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = name.lower()
    return f"{name}_module" if name in CPP_KEYWORDS else name


def custom_module_files(class_name: str, in_type: Optional[str] = None, out_type: Optional[str] = None) -> dict[str, str]:
    context = cfunction_context(class_name, in_type, out_type)
    return {
        f"src/custom/{class_name}.hpp": render_template("custom/Module.hpp.j2", **context),
        f"src/custom/{class_name}.cpp": render_template("custom/Module.cpp.j2", **context),
    }


def stream_interface(**options) -> dict:
    """Return a complete, validated stream interface; omitted widths default to the type size."""
    interface = dict(DEFAULT_STREAM_INTERFACE)
    interface.update({key: value for key, value in options.items() if value is not None})
    unknown = set(interface) - set(DEFAULT_STREAM_INTERFACE)
    if unknown:
        raise ValueError("Unknown stream interface option(s): " + ", ".join(sorted(unknown)))
    for side in ("in", "out"):
        element_type = interface[f"{side}_type"]
        if element_type not in ELEMENT_TYPES:
            raise ValueError(f"--{side}-type must be one of: {', '.join(ELEMENT_TYPES)}")
        type_bits = ELEMENT_TYPES[element_type]
        width = interface[f"{side}_width"]
        if width is None:
            width = interface[f"{side}_width"] = type_bits
        if not isinstance(width, int) or not 1 <= width <= type_bits:
            raise ValueError(f"--{side}-width must be between 1 and {type_bits} for {element_type}")
        lanes = interface[f"{side}_lanes"]
        if not isinstance(lanes, int) or lanes < 1:
            raise ValueError(f"--{side}-lanes must be a positive integer")
        if lanes * width > MAX_BUS_WIDTH:
            raise ValueError(f"The {side}put bus ({lanes} x {width} bits) exceeds {MAX_BUS_WIDTH} bits")
    interface["passthrough"] = all(
        interface[f"in_{key}"] == interface[f"out_{key}"] for key in ("type", "width", "lanes")
    )
    # Output elements are sign-extended only for a signed type and more than one bit, so that
    # hard-decision bits stored in a signed type read as 0 and 1.
    interface["out_sign_extend"] = (
        not interface["out_unsigned"] and not interface["out_type"].startswith("uint") and interface["out_width"] > 1
    )
    return interface


def verilator_module_files(class_name: str, interface: Optional[dict] = None) -> dict[str, str]:
    context = {"class_name": class_name, **(interface or stream_interface())}
    return {
        f"src/hw/{class_name}.sv": render_template("verilator/Module.sv.j2", **context),
        f"src/custom/{class_name}.hpp": render_template("verilator/Module.hpp.j2", **context),
        f"src/custom/{class_name}.cpp": render_template("verilator/Module.cpp.j2", **context),
    }


def cfunction_context(class_name: str, in_type: Optional[str] = None, out_type: Optional[str] = None) -> dict:
    context = {"class_name": class_name, "prefix": module_instance_name(class_name),
               "in_type": in_type or "int", "out_type": out_type or "int"}
    for side in ("in", "out"):
        if context[f"{side}_type"] not in CFUNCTION_TYPES:
            raise ValueError(f"--{side}-type must be one of: {', '.join(CFUNCTION_TYPES)}")
    return context


def cfunction_module_files(class_name: str, in_type: Optional[str] = None, out_type: Optional[str] = None) -> dict[str, str]:
    context = cfunction_context(class_name, in_type, out_type)
    prefix = context["prefix"]
    return {
        f"src/custom/{prefix}_api.h": render_template("cfunction/api.h.j2", **context),
        f"src/custom/{prefix}_impl.c": render_template("cfunction/impl.c.j2", **context),
        f"src/custom/{class_name}.hpp": render_template("cfunction/Module.hpp.j2", **context),
        f"src/custom/{class_name}.cpp": render_template("cfunction/Module.cpp.j2", **context),
    }


def preview_cfunction_module(project_dir: Path, class_name: str, in_type: Optional[str] = None,
                             out_type: Optional[str] = None) -> str:
    return render_template(
        "cfunction/preview.txt.j2",
        project_dir=project_dir,
        instance_name=module_instance_name(class_name),
        **cfunction_context(class_name, in_type, out_type),
    )


def check_project_c_support(project_dir: Path) -> None:
    if 'src/custom/*.c"' not in (project_dir / "CMakeLists.txt").read_text(encoding="utf-8"):
        raise ValueError(
            f"{project_dir / 'CMakeLists.txt'} does not compile C sources. Create the project with a current "
            "Hulotte, or enable the C language and add src/custom/*.c as in templates/project/CMakeLists.txt.j2."
        )


def preview_custom_module(project_dir: Path, class_name: str, in_type: Optional[str] = None,
                          out_type: Optional[str] = None) -> str:
    return render_template(
        "custom/preview.txt.j2",
        project_dir=project_dir,
        instance_name=module_instance_name(class_name),
        **cfunction_context(class_name, in_type, out_type),
    )


def preview_verilator_module(project_dir: Path, class_name: str, interface: Optional[dict] = None) -> str:
    return render_template(
        "verilator/preview.txt.j2",
        project_dir=project_dir,
        class_name=class_name,
        instance_name=module_instance_name(class_name),
        **(interface or stream_interface()),
    )


def check_output_paths(project_dir: Path, files: dict[str, str]) -> list[Path]:
    output_paths = [project_dir / relative_path for relative_path in files]
    for path in output_paths:
        try:
            path.resolve().relative_to(project_dir)
        except ValueError as error:
            raise ValueError(f"Output path escapes the project directory: {path}") from error
    existing_paths = [path for path in output_paths if path.exists() or path.is_symlink()]
    if existing_paths:
        existing_names = ", ".join(str(path.relative_to(project_dir)) for path in existing_paths)
        raise FileExistsError(f"Refusing to overwrite existing files: {existing_names}")
    return output_paths


def write_project_files(project_dir: Path, files: dict[str, str]) -> list[Path]:
    output_paths = check_output_paths(project_dir, files)
    created_paths = []
    try:
        for path, contents in zip(output_paths, files.values()):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as output:
                created_paths.append(path)
                output.write(contents)
    except OSError:
        for path in reversed(created_paths):
            path.unlink()
        raise
    return output_paths


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_generated_registry(project_dir: Path) -> Optional[dict]:
    """Relative path -> SHA-256 of the contents Hulotte wrote, or None for a project without registry."""
    path = project_dir / GENERATED_REGISTRY
    if not path.is_file():
        return None
    try:
        files = json.loads(path.read_text(encoding="utf-8"))["files"]
        return {name: entry["sha256"] for name, entry in files.items()}
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"Invalid {GENERATED_REGISTRY}: {error}") from error


def record_generated_files(project_dir: Path, files: dict[str, str]) -> None:
    """Record the files that `hulotte update` may rewrite, with the hash of what was written."""
    if not files:
        return
    path = project_dir / GENERATED_REGISTRY
    registry = {"files": {}}
    if path.is_file():
        read_generated_registry(project_dir)  # validates the format
        registry = json.loads(path.read_text(encoding="utf-8"))
    for name, contents in files.items():
        registry["files"][name] = {"sha256": sha256_text(contents), "hulotte": __version__}
    registry["files"] = dict(sorted(registry["files"].items()))
    registry = {"comment": "Files generated by Hulotte, rewritten by `hulotte update`. Commit this file.", **{
        key: value for key, value in registry.items() if key != "comment"}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def generated_subset(files: dict[str, str]) -> dict[str, str]:
    """The files of a generation that `hulotte update` owns: the CMake file and the module adapters.

    Hardware descriptions, C implementations and API headers, main.cpp and the example modules
    belong to the user once written.
    """
    return {name: contents for name, contents in files.items()
            if name == "CMakeLists.txt" or re.fullmatch(r"src/custom/[A-Za-z][A-Za-z0-9_]*\.(hpp|cpp)", name)}


def read_adapter_types(header: str, file_name: str, allowed: dict) -> tuple[str, str]:
    types = []
    for side in ("in", "out"):
        match = re.search(rf"using\s+{side}_t\s*=\s*([A-Za-z0-9_]+)\s*;", header)
        if not match or match.group(1) not in allowed:
            raise ValueError(f"{file_name}: cannot read 'using {side}_t = ...;' (one of {', '.join(allowed)})")
        types.append(match.group(1))
    return types[0], types[1]


def expected_generated_files(project_dir: Path) -> dict[str, str]:
    """What the current Hulotte generates for the files it owns in an existing project."""
    cmake = (project_dir / "CMakeLists.txt").read_text(encoding="utf-8")
    project_match = re.search(r"^project\(([A-Za-z_][A-Za-z0-9_]*)", cmake, re.M)
    executable_match = re.search(r"^add_executable\(([A-Za-z_][A-Za-z0-9_]*)", cmake, re.M)
    if not project_match or not executable_match:
        raise ValueError("CMakeLists.txt: cannot read the project and executable names (project(...), add_executable(...))")
    files = {"CMakeLists.txt": render_template("project/CMakeLists.txt.j2", project_name=project_match.group(1),
                                               executable_name=executable_match.group(1))}
    custom_dir = project_dir / "src/custom"
    for header_path in sorted(custom_dir.glob("*.hpp")) if custom_dir.is_dir() else []:
        name, header = header_path.stem, header_path.read_text(encoding="utf-8")
        relative = f"src/custom/{name}.hpp"
        if (project_dir / f"src/hw/{name}.sv").is_file() and f"class VModel_{name};" in header:
            in_type, out_type = read_adapter_types(header, relative, ELEMENT_TYPES)
            interface = read_verilator_interface(project_dir, name)
            source_path = project_dir / f"src/custom/{name}.cpp"
            sign_match = re.search(r"constexpr\s+bool\s+sign_extend\s*=\s*(true|false)\s*;",
                                   source_path.read_text(encoding="utf-8") if source_path.is_file() else "")
            if not sign_match:
                raise ValueError(f"src/custom/{name}.cpp: cannot read 'constexpr bool sign_extend = ...;'")
            sign_extend = sign_match.group(1) == "true"
            signed = not out_type.startswith("uint")
            options = {**interface, "in_type": in_type, "out_type": out_type,
                       "out_unsigned": not sign_extend and signed and interface["out_width"] > 1}
            generated = verilator_module_files(name, stream_interface(**options))
        else:
            api_match = re.search(r'#include\s+"([A-Za-z0-9_]+)_api\.h"', header)
            if not api_match or api_match.group(1) != module_instance_name(name) or "around the C API" not in header:
                continue  # a custom C++ module: the user's code
            in_type, out_type = read_adapter_types(header, relative, CFUNCTION_TYPES)
            generated = cfunction_module_files(name, in_type, out_type)
        files.update(generated_subset(generated))
    return files


def plan_update(project_dir: Path) -> list:
    """(relative path, state, current contents or None, expected contents) for each file Hulotte owns.

    States: "up to date"; "outdated" (unchanged since Hulotte wrote it); "edited" (changed by hand
    since); "unknown" (no record of what Hulotte wrote, as in projects older than the registry);
    "missing".
    """
    project_dir = validate_project_directory(project_dir)
    registry = read_generated_registry(project_dir)
    plan = []
    for name, expected in expected_generated_files(project_dir).items():
        path = project_dir / name
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == expected:
            state = "up to date"
        elif current is None:
            state = "missing"
        elif registry is None or name not in registry:
            state = "unknown"
        elif registry[name] == sha256_text(current):
            state = "outdated"
        else:
            state = "edited"
        plan.append((name, state, current, expected))
    return plan


def describe_update(plan: list, show_all_diffs: bool = False) -> str:
    labels = {"up to date": "up to date", "outdated": "will be updated", "missing": "will be created",
              "unknown": "will be updated (not recorded as generated: check the diff)",
              "edited": "EDITED BY HAND since generated: only updated with --force (a .orig copy is kept)"}
    lines = ["Files generated by Hulotte:"]
    lines += [f"    {name}: {labels[state]}" for name, state, _, _ in plan]
    for name, state, current, expected in plan:
        if current is not None and current != expected and (show_all_diffs or state in ("unknown", "edited")):
            lines.append("")
            lines += [line.rstrip("\n") for line in difflib.unified_diff(
                current.splitlines(True), expected.splitlines(True), f"{name} (current)", f"{name} (Hulotte {__version__})")]
    return "\n".join(lines) + "\n"


def apply_update(project_dir: Path, plan: list, force: bool = False) -> tuple[list, list]:
    """Write the planned files; return (written paths, skipped paths edited by hand)."""
    project_dir = validate_project_directory(project_dir)
    written, skipped = [], []
    for name, state, current, expected in plan:
        if state == "up to date":
            continue
        if state == "edited" and not force:
            skipped.append(name)
            continue
        path = project_dir / name
        if state in ("edited", "unknown") and current is not None:
            path.with_name(path.name + ".orig").write_text(current, encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        written.append(name)
    record_generated_files(project_dir, {name: expected for name, _, _, expected in plan if name not in skipped})
    return written, skipped


def add_custom_module(project_dir: Path, class_name: str, in_type: Optional[str] = None,
                      out_type: Optional[str] = None) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    validate_module_name(class_name)
    return write_project_files(project_dir, custom_module_files(class_name, in_type, out_type))


def add_verilator_module(project_dir: Path, class_name: str, interface: Optional[dict] = None) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    validate_module_name(class_name, "verilator")
    files = verilator_module_files(class_name, interface)
    output_paths = write_project_files(project_dir, files)
    record_generated_files(project_dir, generated_subset(files))
    return output_paths


def add_cfunction_module(project_dir: Path, class_name: str, in_type: Optional[str] = None,
                         out_type: Optional[str] = None) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    validate_module_name(class_name)
    check_project_c_support(project_dir)
    files = cfunction_module_files(class_name, in_type, out_type)
    output_paths = write_project_files(project_dir, files)
    record_generated_files(project_dir, generated_subset(files))
    return output_paths


def read_verilator_interface(project_dir: Path, block: str) -> dict:
    """Interface parameters of a Verilator block, read from its generated adapter (the source of truth)."""
    adapter = project_dir / f"src/custom/{block}.hpp"
    if not adapter.is_file():
        raise ValueError(f"Verilator adapter not found: src/custom/{block}.hpp (create the block with `module add --type verilator`)")
    text = adapter.read_text(encoding="utf-8")
    interface = {}
    for name in VERILATOR_INTERFACE_CONSTANTS:
        match = re.search(rf"static\s+constexpr\s+unsigned\s+{name}\s*=\s*(\d+)\s*;", text)
        if not match:
            raise ValueError(f"src/custom/{block}.hpp does not define 'static constexpr unsigned {name} = ...;'")
        interface[name] = int(match.group(1))
    return interface


def synth_delimiters(top_module: str) -> tuple[str, str]:
    """Delimiters around the parameters that Odatix replaces in the top-level file."""
    return f"module {top_module} #(", ") ("


def check_synth_delimiters(text: str, top_module: str, file_name: str) -> None:
    start, stop = synth_delimiters(top_module)
    if text.count(start) != 1:
        raise ValueError(f"{file_name} must contain '{start}' exactly once, as generated by Hulotte")
    if text.find(stop, text.index(start)) < 0:
        raise ValueError(f"{file_name} must close its parameter list with '{stop}', as generated by Hulotte")


def synth_files(block: str, interface: dict, tool: str, target: str, wrap_io: bool) -> tuple[dict, dict]:
    """Files of the Odatix workspace: those shared by all blocks, and those of this block."""
    top_module = f"{block}_synth_top" if wrap_io else block
    context = {
        "block": block, "tool": tool, "target": target, "top_module": top_module,
        "top_file": f"synth/{top_module}.sv" if wrap_io else f"{block}.sv",
        "frequency": DEFAULT_SYNTH_FREQUENCY, "fmax_lower": DEFAULT_FMAX_BOUNDS[0], "fmax_upper": DEFAULT_FMAX_BOUNDS[1],
        **interface,
    }
    shared = {
        "synth/odatix.yml": render_template("synth/odatix.yml.j2", **context),
        "synth/synth_settings.yml": render_template("synth/synth_settings.yml.j2", **context),
        "synth/fmax_settings.yml": render_template("synth/fmax_settings.yml.j2", **context),
        f"synth/odatix_userconfig/targets/target_{tool}.yml": render_template(f"synth/target_{tool}.yml.j2", **context),
        "synth/.gitignore": render_template("synth/gitignore.j2", **context),
    }
    architecture = f"synth/odatix_userconfig/architectures/{block}"
    block_files = {
        f"{architecture}/_settings.yml": render_template("synth/_settings.yml.j2", **context),
        f"{architecture}/verified.txt": render_template("synth/verified.txt.j2", **context),
    }
    if wrap_io:
        wrapper = render_template("synth/synth_top.sv.j2", **context)
        check_synth_delimiters(wrapper, top_module, "the synthesis wrapper")
        block_files[f"src/hw/{context['top_file']}"] = wrapper
    return shared, block_files


def plan_synth_add(project_dir: Path, block: str, tool: str = SYNTH_TOOLS[0], target: str = DEFAULT_SYNTH_TARGET,
                   wrap_io: bool = True, force: bool = False) -> tuple[dict, str]:
    """Check a block and return the files to write (relative path -> contents) and the preview text.

    Shared files that already exist are kept; the files of the block are only overwritten with force.
    """
    project_dir = validate_project_directory(project_dir)
    validate_module_name(block, "verilator")
    if tool not in SYNTH_TOOLS:
        raise ValueError(f"Unsupported synthesis tool: {tool} (supported: {', '.join(SYNTH_TOOLS)})")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", target):
        raise ValueError(f"Invalid target name: {target}")
    rtl = project_dir / f"src/hw/{block}.sv"
    if not rtl.is_file():
        raise ValueError(f"Hardware block not found: src/hw/{block}.sv")
    check_synth_delimiters(rtl.read_text(encoding="utf-8"), block, f"src/hw/{block}.sv")
    interface = read_verilator_interface(project_dir, block)
    shared, block_files = synth_files(block, interface, tool, target, wrap_io)
    for relative_path in [*shared, *block_files]:
        try:
            (project_dir / relative_path).resolve().relative_to(project_dir)
        except ValueError as error:
            raise ValueError(f"Output path escapes the project directory: {relative_path}") from error

    states, files = [], {}
    for relative_path, contents in shared.items():
        if (project_dir / relative_path).exists():
            states.append((relative_path, "kept"))
        else:
            states.append((relative_path, "new"))
            files[relative_path] = contents
    existing = [path for path in block_files if (project_dir / path).exists()]
    if existing and not force:
        raise FileExistsError("Refusing to overwrite existing files (use --force): " + ", ".join(existing))
    for relative_path, contents in block_files.items():
        states.append((relative_path, "overwritten" if relative_path in existing else "new"))
        files[relative_path] = contents

    top_module = f"{block}_synth_top" if wrap_io else block
    preview = render_template(
        "synth/preview.txt.j2", project_dir=project_dir, block=block, tool=tool, target=target,
        top_module=top_module, wrap_io=wrap_io, files=states, **interface,
    )
    target_file = project_dir / f"synth/odatix_userconfig/targets/target_{tool}.yml"
    if target_file.exists() and not re.search(rf"^\s*-\s*{re.escape(target)}\s*$", target_file.read_text(encoding="utf-8"), re.M):
        preview += f"\nWARNING: {target_file.relative_to(project_dir)} already exists and does not list {target}: add it there.\n"
    return files, preview


def rtl_manifest(project_dir: Path) -> tuple[str, dict]:
    """SHA-256 of the RTL sources, computed as the CMake of generated projects does for mark_verified().

    Every .sv under src/hw except src/hw/synth, sorted by path; the manifest holds one
    "<sha256>  <path>" line per file and the RTL hash is the SHA-256 of the manifest.
    """
    hw_dir = project_dir / "src/hw"
    files = {}
    if hw_dir.is_dir():
        for path in hw_dir.rglob("*.sv"):
            relative = path.relative_to(project_dir).as_posix()
            if path.is_file() and not relative.startswith("src/hw/synth/"):
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = "".join(f"{files[name]}  {name}\n" for name in sorted(files))
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest(), {name: files[name] for name in sorted(files)}


def read_verified_record(path: Path) -> dict:
    """Read a synth/verified/<Block>.yml file as written by mark_verified() (JSON values in YAML)."""
    record, section = {"rtl_files": {}, "cycles": []}, None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            if line.startswith("  - ") and section == "cycles":
                record["cycles"].append(json.loads(line[4:]))
            elif line.startswith("  ") and section == "rtl_files":
                name, digest = re.fullmatch(r'\s+("(?:[^"\\]|\\.)*"):\s*(".*")', line).groups()
                record["rtl_files"][json.loads(name)] = json.loads(digest)
            else:
                key, value = line.split(":", 1)
                section = key.strip()
                if value.strip():
                    record[section] = json.loads(value)
        except (AttributeError, ValueError) as error:
            raise ValueError(f"{path.name}, line {number}: unexpected content (written by mark_verified()?)") from error
    for key in ("module", "rtl_sha256", "parameters"):
        if key not in record:
            raise ValueError(f"{path.name}: missing '{key}'")
    return record


def read_verified_txt(path: Path) -> dict:
    """Interface parameters of a verified.txt configuration of the Odatix workspace."""
    return {name: int(value) for name, value in
            re.findall(r"parameter\s+(?:int\s+)?([A-Z_]+)\s*=\s*(\d+)", path.read_text(encoding="utf-8"))}


def synth_status(project_dir: Path) -> tuple[list, bool]:
    """State of each Verilator block of src/hw: verified, modified since the check, or never verified."""
    project_dir = validate_project_directory(project_dir)
    rtl_sha256, rtl_files = rtl_manifest(project_dir)
    blocks = sorted(path.stem for path in (project_dir / "src/hw").glob("*.sv")) if (project_dir / "src/hw").is_dir() else []
    verified_dir = project_dir / "synth/verified"
    records = {path.stem: path for path in verified_dir.glob("*.yml")} if verified_dir.is_dir() else {}
    lines, all_verified = [], True
    width = max([len(name) for name in [*blocks, *records]] + [5])
    for block in sorted(set(blocks) | set(records)):
        if block not in records:
            lines.append(f"{block:<{width}}  never verified")
            all_verified = False
            continue
        record = read_verified_record(records[block])
        details = f"{record.get('test', '?')}, {record.get('date', '?')}"
        problems = []
        if block not in blocks:
            problems.append(f"src/hw/{block}.sv no longer exists")
        if record["rtl_sha256"] != rtl_sha256:
            recorded = record["rtl_files"]
            changed = [name for name in sorted(set(recorded) | set(rtl_files)) if recorded.get(name) != rtl_files.get(name)]
            problems.append("changed since the check: " + (", ".join(changed) if changed else "src/hw"))
        verified_txt = project_dir / f"synth/odatix_userconfig/architectures/{block}/verified.txt"
        if verified_txt.is_file() and read_verified_txt(verified_txt) != record["parameters"]:
            problems.append(f"parameters of {verified_txt.relative_to(project_dir)} differ from the check "
                            + ", ".join(f"{name}={value}" for name, value in record["parameters"].items()))
        if problems:
            lines.append(f"{block:<{width}}  MODIFIED        {details}; " + "; ".join(problems))
            all_verified = False
        else:
            cycles = "; ".join(
                f"{point.get('condition', '')}: latency {point.get('latency_min')}-{point.get('latency_max')}, "
                f"interval {point.get('interval_min')}-{point.get('interval_max')}"
                for point in record["cycles"][:3])
            more = f" (+{len(record['cycles']) - 3} more)" if len(record["cycles"]) > 3 else ""
            lines.append(f"{block:<{width}}  verified        {details}" + (f"; {cycles}{more}" if cycles else ""))
    if not lines:
        lines.append("No Verilator block under src/hw.")
    return lines, all_verified


def write_synth_files(project_dir: Path, files: dict[str, str]) -> list[Path]:
    project_dir = validate_project_directory(project_dir)
    output_paths = []
    for relative_path, contents in files.items():
        path = project_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        output_paths.append(path)
    return output_paths


def load_catalog(library: str) -> dict:
    path = Path(__file__).resolve().parent / "catalog" / f"{library}.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read module catalog {path}: {error}") from error

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"Invalid module catalog {path}: {message}")

    require(isinstance(catalog, dict) and catalog.get("library") == library, f"'library' must be '{library}'")
    for key in ("namespace", "include"):
        require(isinstance(catalog.get(key), str) and catalog[key], f"missing '{key}'")
    modules = catalog.get("modules")
    require(isinstance(modules, list) and modules, "'modules' must be a non-empty list")
    seen_ids = set()
    for entry in modules:
        require(isinstance(entry, dict), "every module must be an object")
        module_id = entry.get("id")
        require(isinstance(module_id, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", module_id) is not None,
                f"invalid module id {module_id!r}")
        require(module_id not in seen_ids, f"duplicate module id '{module_id}'")
        seen_ids.add(module_id)
        for key in ("summary", "class"):
            require(isinstance(entry.get(key), str) and entry[key], f"'{module_id}' is missing '{key}'")
        require(isinstance(entry.get("template_arguments", ""), str), f"'{module_id}' has invalid 'template_arguments'")
        require(isinstance(entry.get("notes", []), list), f"'{module_id}' has invalid 'notes'")
        arguments = entry.get("arguments")
        require(isinstance(arguments, list), f"'{module_id}' is missing 'arguments'")
        for argument in arguments:
            require(isinstance(argument, dict) and all(isinstance(argument.get(key), str) and argument[key]
                    for key in ("name", "type", "example", "description")),
                    f"'{module_id}' has an incomplete argument")
        tasks = entry.get("tasks")
        require(isinstance(tasks, list) and tasks, f"'{module_id}' needs at least one task")
        for task in tasks:
            require(isinstance(task, dict) and isinstance(task.get("name"), str), f"'{module_id}' has an invalid task")
            sockets = task.get("sockets")
            require(isinstance(sockets, list) and sockets, f"'{module_id}.{task['name']}' needs sockets")
            for socket in sockets:
                require(isinstance(socket, dict) and socket.get("direction") in CATALOG_SOCKET_DIRECTIONS
                        and all(isinstance(socket.get(key), str) and socket[key]
                                for key in ("name", "type", "size", "description")),
                        f"'{module_id}.{task['name']}' has an incomplete socket")
    return catalog


def catalog_entry(library: str, module_id: str) -> dict:
    for entry in load_catalog(library)["modules"]:
        if entry["id"] == module_id:
            return entry
    available = ", ".join(entry["id"] for entry in load_catalog(library)["modules"])
    raise ValueError(f"Unknown {library} module '{module_id}'. Available modules: {available}")


def list_catalog(libraries) -> str:
    lines = []
    for library in libraries:
        modules = load_catalog(library)["modules"]
        width = max(len(entry["id"]) for entry in modules)
        lines.append(f"{library}:")
        lines.extend(f"  {entry['id'].ljust(width)}  {entry['summary']}" for entry in modules)
    return "\n".join(lines) + "\n"


def catalog_dependency_hint(library: str) -> str:
    if library == "aff3ct":
        if not aff3ct_is_built(aff3ct_path()):
            return "AFF3CT is not installed; run: python3 hulotte.py deps install --library aff3ct"
    elif not (stream_pu_is_built(stream_pu_path()) or aff3ct_is_built(aff3ct_path())):
        return "StreamPU is not installed; run: python3 hulotte.py deps install"
    return ""


def check_project_library_support(project_dir: Path, library: str) -> None:
    if library == "aff3ct" and "AFF3CT_ROOT" not in (project_dir / "CMakeLists.txt").read_text(encoding="utf-8"):
        raise ValueError(
            f"{project_dir / 'CMakeLists.txt'} has no AFF3CT support. Create the project with a current "
            "Hulotte, or copy the AFF3CT_ROOT block from templates/project/CMakeLists.txt.j2."
        )


def preview_catalog_module(library: str, entry: dict) -> str:
    catalog = load_catalog(library)
    template_arguments = f"<{entry['template_arguments']}>" if entry.get("template_arguments") else ""
    return render_template(
        "catalog/preview.txt.j2",
        library=library,
        entry=entry,
        include=catalog["include"],
        qualified_class=f"{catalog['namespace']}::{entry['class']}{template_arguments}",
        instance_name=entry["id"].lower(),
        call_arguments=", ".join(argument["example"] for argument in entry["arguments"]),
        dependency_hint=catalog_dependency_hint(library),
        aff3ct_root=aff3ct_path(),
    )


def prompt_for_catalog_module(library: str) -> str:
    modules = load_catalog(library)["modules"]
    print(f"Available {library} modules:")
    for number, entry in enumerate(modules, start=1):
        print(f"  {number}. {entry['id']} - {entry['summary']}")
    selection = input("Select module number or name: ").strip()
    if selection.isdigit() and 1 <= int(selection) <= len(modules):
        return modules[int(selection) - 1]["id"]
    return selection


def prompt_for_module_details() -> tuple[str, str]:
    print("Available module type:")
    print("  1. Custom C++ StreamPU module")
    print("  2. StreamPU adapter around a Verilator model")
    print("  3. Existing StreamPU module from the catalog")
    print("  4. Existing AFF3CT module from the catalog")
    print("  5. StreamPU adapter around a C function API")
    module_types = {"": "custom", "1": "custom", "2": "verilator", "3": "streampu", "4": "aff3ct", "5": "cfunction"}
    selection = input("Select module type [1]: ").strip()
    if selection not in module_types:
        raise ValueError("Select 1 for a custom module, 2 for a Verilator adapter, 3 for a StreamPU catalog module, "
                         "4 for an AFF3CT catalog module, or 5 for a C function adapter")
    module_type = module_types[selection]
    if module_type in CATALOG_LIBRARIES:
        return module_type, prompt_for_catalog_module(module_type)
    return module_type, input("Module class name: ").strip()


def confirm_module_creation(prompt: str = "Create these files?") -> bool:
    while True:
        response = input(f"{prompt} [Y/n]: ").strip().lower()
        if response in {"", "y", "yes"}:
            return True
        if response in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def create_project(project_dir: Path) -> Path:
    project_dir = project_dir.expanduser().resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty directory: {project_dir}")

    project_name = project_target_name(project_dir)
    executable_name = executable_target_name(project_name)
    files = project_files(project_name, executable_name)
    write_project_files(project_dir, files)
    record_generated_files(project_dir, generated_subset(files))
    return project_dir


def stream_pu_path(repository_root: Optional[Path] = None) -> Path:
    repository_root = repository_root or Path(__file__).resolve().parent
    return repository_root / "dependencies" / "streampu"


def stream_pu_is_built(stream_pu_root: Path) -> bool:
    return (
        (stream_pu_root / "include/streampu.hpp").is_file()
        and (stream_pu_root / "build/lib/libstreampu.a").is_file()
    )


def aff3ct_path(repository_root: Optional[Path] = None) -> Path:
    repository_root = repository_root or Path(__file__).resolve().parent
    return repository_root / "dependencies" / "aff3ct"


def aff3ct_library(aff3ct_root: Path) -> Optional[Path]:
    return next(iter(sorted((aff3ct_root / "build/lib").glob("libaff3ct-*.a"))), None)


def aff3ct_is_built(aff3ct_root: Path) -> bool:
    return (aff3ct_root / "include/aff3ct.hpp").is_file() and aff3ct_library(aff3ct_root) is not None


def available_compiler() -> Optional[str]:
    configured_compiler = shlex.split(os.environ.get("CXX", ""))
    candidates = configured_compiler[:1] + ["c++", "g++", "clang++"]
    return next((compiler for compiler in candidates if shutil.which(compiler)), None)


def cmake_version() -> Optional[tuple[int, int, int]]:
    if shutil.which("cmake") is None:
        return None
    try:
        result = subprocess.run(["cmake", "--version"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r"cmake version (\d+)\.(\d+)(?:\.(\d+))?", result.stdout, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def missing_install_tools() -> list[str]:
    missing = ["git"] if shutil.which("git") is None else []
    if cmake_version() is None or cmake_version() < (3, 20, 0):
        missing.append("CMake >= 3.20")
    if available_compiler() is None:
        missing.append("C++ compiler (set CXX or install c++, g++, or clang++)")
    return missing


def run_command(command: list[str], cwd: Optional[Path] = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as error:
        raise RuntimeError(f"Required command not found: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Command failed with exit code {error.returncode}: {shlex.join(command)}") from error


def checkout_revision(checkout_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"Could not read the Git revision at {checkout_root}") from error
    return result.stdout.strip()


def install_checkout(
    name: str,
    root: Path,
    url: str,
    revision: str,
    submodule_paths: tuple,
    configure_arguments: list,
    is_built: Callable[[Path], bool],
    root_option: str,
    dry_run: bool,
    jobs: Optional[int] = None,
) -> Path:
    existing_checkout = root.exists() or root.is_symlink()
    if existing_checkout:
        if root.is_symlink() or not (root / ".git").exists():
            raise ValueError(f"Refusing to modify existing non-Git {name} path: {root}")
        current_revision = checkout_revision(root)
        if current_revision != revision:
            raise ValueError(
                f"{name} already exists at {root} but is at {current_revision}; "
                f"expected {revision}. Move it manually before installing."
            )
        if is_built(root):
            print(f"{name} is already installed at {root}")
            return root
    missing_tools = missing_install_tools()
    if missing_tools:
        raise ValueError("Missing required tools: " + ", ".join(missing_tools))
    if dry_run:
        if existing_checkout:
            print(f"Would initialize {name} Git submodules at {root}")
            print(f"Would configure and build {name}")
        else:
            print(f"Would clone {name} {revision} into {root}")
            print(f"Would initialize its Git submodules, configure CMake, and build {name}")
        return root

    submodule_command = ["submodule", "update", "--init", "--recursive"]
    if submodule_paths:
        submodule_command += ["--", *submodule_paths]
    if not existing_checkout:
        dependencies_dir = root.parent
        dependencies_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".hulotte-{root.name}-", dir=dependencies_dir) as temporary_dir:
            staged_root = Path(temporary_dir) / root.name
            run_command(["git", "clone", "--no-checkout", url, str(staged_root)])
            run_command(["git", "-C", str(staged_root), "checkout", "--detach", revision])
            run_command(["git", "-C", str(staged_root), *submodule_command])
            staged_root.rename(root)
    else:
        run_command(["git", "-C", str(root), *submodule_command])

    run_command(["cmake", "-S", str(root), "-B", str(root / "build"), *configure_arguments])
    run_command(["cmake", "--build", str(root / "build"), "--parallel", *([str(jobs)] if jobs else [])])
    if not is_built(root):
        raise RuntimeError(f"{name} build completed but the expected library is missing under {root}")
    print(f"{name} installed at {root}")
    print(f"Configure generated projects with -D{root_option}={root}")
    return root


def native_arch_arguments() -> list:
    """CMake arguments compiling a dependency for the instruction set of the build machine.

    Without -march=native, x86-64 compilers target SSE2 only, where MIPP (used by AFF3CT) lacks some
    operations such as the 32-bit integer multiplication: AFF3CT modules then fail at run time with
    "mipp::... (SSE2) is undefined". ARM has NEON by default and needs nothing. A -march already present
    in CXXFLAGS is left as it is.
    """
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        return []
    cxx_flags = os.environ.get("CXXFLAGS", "").strip()
    if "-march=" in cxx_flags:
        return []
    return [f"-DCMAKE_CXX_FLAGS={' '.join(filter(None, [cxx_flags, '-march=native']))}"]


def install_stream_pu(repository_root: Path, dry_run: bool = False) -> Path:
    return install_checkout(
        "StreamPU", stream_pu_path(repository_root), STREAMPU_URL, STREAMPU_REVISION, (),
        [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DSPU_COMPILE_STATIC_LIB=ON",
            "-DSPU_COMPILE_SHARED_LIB=OFF",
            "-DSPU_TESTS=OFF",
            *native_arch_arguments(),
        ],
        stream_pu_is_built, "STREAMPU_ROOT", dry_run,
    )


def install_aff3ct(repository_root: Path, dry_run: bool = False) -> Path:
    return install_checkout(
        "AFF3CT", aff3ct_path(repository_root), AFF3CT_URL, AFF3CT_REVISION, AFF3CT_SUBMODULES,
        [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DAFF3CT_COMPILE_EXE=OFF",
            "-DAFF3CT_COMPILE_STATIC_LIB=ON",
            "-DAFF3CT_COMPILE_SHARED_LIB=OFF",
            "-DSPU_TESTS=OFF",
            *native_arch_arguments(),
        ],
        aff3ct_is_built, "AFF3CT_ROOT", dry_run,
        jobs=min(os.cpu_count() or 1, AFF3CT_MAX_BUILD_JOBS),
    )


def prompt_for_library() -> str:
    print("Select the library to install:")
    print("  1. StreamPU only (pinned revision)")
    print("  2. AFF3CT with its embedded StreamPU")
    while True:
        selection = input("Select library [1]: ").strip()
        if selection in {"", "1"}:
            return "streampu"
        if selection == "2":
            return "aff3ct"
        print("Please answer 1 or 2.")


def print_dependency_status(repository_root: Path) -> bool:
    libraries = (
        ("StreamPU", stream_pu_path(repository_root), stream_pu_is_built, STREAMPU_REVISION),
        ("AFF3CT", aff3ct_path(repository_root), aff3ct_is_built, AFF3CT_REVISION),
    )
    any_ready = False
    for name, root, is_built, revision in libraries:
        if not is_built(root):
            print(f"{name}: not installed at {root}")
            continue
        try:
            current_revision = checkout_revision(root)
        except RuntimeError:
            current_revision = "unknown revision"
        ready = current_revision == revision
        any_ready = any_ready or ready
        state = "built" if ready else f"built, but expected revision {revision}"
        print(f"{name}: {state} ({current_revision})")
        print(f"  Path: {root}")
    return any_ready


def run_doctor(repository_root: Path) -> int:
    missing_tools = missing_install_tools()
    git_path = shutil.which("git")
    print(f"git: {'available (' + git_path + ')' if git_path else 'missing'}")
    cmake_path = shutil.which("cmake")
    version = cmake_version()
    if cmake_path and version:
        print(f"cmake: available ({cmake_path}, version {'.'.join(map(str, version))})")
    elif cmake_path:
        print(f"cmake: available ({cmake_path}), version could not be determined")
    else:
        print("cmake: missing")
    compiler = available_compiler()
    print(f"C++ compiler: {compiler or 'missing'}")
    dependencies_ready = print_dependency_status(repository_root)
    if missing_tools:
        print("Install the missing build tools, then rerun hulotte doctor.")
    elif not dependencies_ready:
        print("Run hulotte deps install to install StreamPU or AFF3CT.")
    return 1 if missing_tools or not dependencies_ready else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create and build readable Hulotte C++ projects")
    parser.add_argument("--version", action="version", version=f"Hulotte {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create a StreamPU project")
    init_parser.add_argument("project_dir", type=Path, help="new project directory")
    module_parser = subparsers.add_parser("module", help="create or add project modules")
    module_subparsers = module_parser.add_subparsers(dest="module_command", required=True)
    list_parser = module_subparsers.add_parser("list", help="list the modules available in the StreamPU and AFF3CT catalogs")
    list_parser.add_argument("--library", choices=list(CATALOG_LIBRARIES), help="only list this library")
    add_parser = module_subparsers.add_parser("add", help="create a module, or show how to use a catalog module")
    add_parser.add_argument("project_dir", type=Path, help="existing Hulotte project directory")
    add_parser.add_argument("--type", dest="module_type", choices=["custom", "verilator", "cfunction", *CATALOG_LIBRARIES], help="module type; prompt when omitted")
    add_parser.add_argument("--name", help="C++ module class name, or catalog module id for streampu and aff3ct; prompt when omitted")
    add_parser.add_argument("--yes", action="store_true", help="create files without a confirmation prompt")
    interface_group = add_parser.add_argument_group(
        "stream interface",
        "element formats of a verilator module (default: one 32-bit int per beat on both sides); "
        "custom and cfunction modules only take --in-type and --out-type, which also accept float and double",
    )
    for side, label in (("in", "input"), ("out", "output")):
        interface_group.add_argument(f"--{side}-type", choices=list(CFUNCTION_TYPES), help=f"C++ type of an {label} element")
        interface_group.add_argument(f"--{side}-width", type=int, metavar="BITS",
                                     help=f"bits of an {label} element on the bus (default: size of the type)")
        interface_group.add_argument(f"--{side}-lanes", type=int, metavar="N", help=f"{label} elements per beat (default: 1)")
    interface_group.add_argument("--out-unsigned", action="store_const", const=True,
                                 help="zero-extend output elements (by default a signed type wider than 1 bit is sign-extended)")
    synth_parser = subparsers.add_parser("synth", help="synthesize Verilator blocks with Odatix")
    synth_subparsers = synth_parser.add_subparsers(dest="synth_command", required=True)
    synth_add_parser = synth_subparsers.add_parser("add", help="write the Odatix workspace of a Verilator block under synth/")
    synth_add_parser.add_argument("project_dir", type=Path, help="existing Hulotte project directory")
    synth_add_parser.add_argument("--name", required=True, help="Verilator block: src/hw/<name>.sv and src/custom/<name>.hpp")
    synth_add_parser.add_argument("--tool", choices=list(SYNTH_TOOLS), default=SYNTH_TOOLS[0], help="synthesis tool (default: %(default)s)")
    synth_add_parser.add_argument("--target", default=DEFAULT_SYNTH_TARGET, help="target part (default: %(default)s)")
    synth_add_parser.add_argument("--wrap-io", action=argparse.BooleanOptionalAction, default=True,
                                  help="synthesize the block inside a wrapper that registers its inputs and outputs (default: on)")
    synth_add_parser.add_argument("--force", action="store_true", help="overwrite the files of this block if they exist")
    synth_add_parser.add_argument("--yes", action="store_true", help="create files without a confirmation prompt")
    synth_status_parser = synth_subparsers.add_parser(
        "status", help="compare the RTL of each Verilator block with the check recorded by mark_verified()")
    synth_status_parser.add_argument("project_dir", type=Path, help="existing Hulotte project directory")
    update_parser = subparsers.add_parser(
        "update", help="rewrite the files Hulotte generated in a project (CMake, module adapters) with the current templates")
    update_parser.add_argument("project_dir", type=Path, help="existing Hulotte project directory")
    update_parser.add_argument("--check", action="store_true", help="only list the files; exit with 1 if an update is available")
    update_parser.add_argument("--diff", action="store_true", help="show the diff of every file to update")
    update_parser.add_argument("--yes", action="store_true", help="update without a confirmation prompt")
    update_parser.add_argument("--force", action="store_true", help="also update files edited by hand (a .orig copy is kept)")
    deps_parser = subparsers.add_parser("deps", help="install or inspect native dependencies")
    deps_subparsers = deps_parser.add_subparsers(dest="deps_command", required=True)
    install_parser = deps_subparsers.add_parser("install", help="install StreamPU only or AFF3CT with its embedded StreamPU")
    install_parser.add_argument("--library", choices=["streampu", "aff3ct"], help="library to install; prompt when omitted in a terminal, StreamPU otherwise")
    install_parser.add_argument("--dry-run", action="store_true", help="show the planned installation without changing files")
    deps_subparsers.add_parser("status", help="show the local StreamPU and AFF3CT installation status")
    subparsers.add_parser("doctor", help="check build tools and installed dependencies")
    args = parser.parse_args(argv)

    repository_root = Path(__file__).resolve().parent
    if args.command == "deps":
        try:
            if args.deps_command == "install":
                library = args.library or (prompt_for_library() if sys.stdin.isatty() else "streampu")
                install = install_aff3ct if library == "aff3ct" else install_stream_pu
                install(repository_root, args.dry_run)
                return 0
            return 0 if print_dependency_status(repository_root) else 1
        except (EOFError, OSError, RuntimeError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nCancelled; the dependency checkout was not modified further.", file=sys.stderr)
            return 130

    if args.command == "doctor":
        return run_doctor(repository_root)

    if args.command == "update":
        try:
            plan = plan_update(args.project_dir)
            print(describe_update(plan, args.diff), end="")
            pending = [name for name, state, _, _ in plan if state != "up to date"]
            if args.check:
                return 1 if pending else 0
            if not pending:
                print("Nothing to update.")
                return 0
            if not args.yes and not confirm_module_creation("Update these files?"):
                print("Cancelled; no files were changed.")
                return 0
            written, skipped = apply_update(args.project_dir, plan, args.force)
        except (EOFError, OSError, ValueError, TemplateError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        for name in written:
            print(f"Updated: {name}")
        for name in skipped:
            print(f"Skipped (edited by hand, use --force): {name}")
        if written:
            print("Configure again from an empty build directory so that CMake takes the new options into account.")
        return 1 if skipped else 0

    if args.command == "synth" and args.synth_command == "status":
        try:
            lines, all_verified = synth_status(args.project_dir)
        except (OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("\n".join(lines))
        return 0 if all_verified else 1

    if args.command == "synth":
        try:
            files, preview_text = plan_synth_add(args.project_dir, args.name, args.tool, args.target, args.wrap_io, args.force)
            print(preview_text, end="")
            if not args.yes and not confirm_module_creation():
                print("Cancelled; no files were created.")
                return 0
            output_paths = write_synth_files(args.project_dir, files)
        except (EOFError, OSError, ValueError, TemplateError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nCancelled; no further files will be created.", file=sys.stderr)
            return 130
        print("Written:")
        for path in output_paths:
            print(f"  {path}")
        return 0

    if args.command == "module" and args.module_command == "list":
        try:
            print(list_catalog([args.library] if args.library else CATALOG_LIBRARIES), end="")
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0

    if args.command == "module":
        try:
            project_dir = validate_project_directory(args.project_dir)
            if args.module_type is None and args.name is None:
                module_type, prompted_name = prompt_for_module_details()
            else:
                module_type, prompted_name = args.module_type or "custom", args.name
            class_name = args.name if args.name is not None else prompted_name
            interface_options = {key: getattr(args, key) for key in DEFAULT_STREAM_INTERFACE}
            given_options = [key for key, value in interface_options.items() if value is not None]
            allowed_options = {"verilator": DEFAULT_STREAM_INTERFACE, "cfunction": CFUNCTION_INTERFACE_OPTIONS,
                               "custom": CFUNCTION_INTERFACE_OPTIONS}
            rejected_options = [key for key in given_options if key not in allowed_options.get(module_type, ())]
            if rejected_options:
                applies_to = ("verilator modules" if any(key not in CFUNCTION_INTERFACE_OPTIONS for key in rejected_options)
                              else "verilator, cfunction and custom modules")
                raise ValueError("Stream interface options (" + ", ".join(
                    "--" + key.replace("_", "-") for key in rejected_options) + f") only apply to {applies_to}")
            if module_type == "verilator":
                interface = stream_interface(**interface_options)
            if module_type in CATALOG_LIBRARIES:
                if class_name is None:
                    class_name = prompt_for_catalog_module(module_type)
                entry = catalog_entry(module_type, class_name)
                check_project_library_support(project_dir, module_type)
                print(preview_catalog_module(module_type, entry), end="")
                return 0
            if class_name is None:
                class_name = input("Module class name: ").strip()
            validate_module_name(class_name, module_type)
            if module_type == "custom":
                files = custom_module_files(class_name, args.in_type, args.out_type)
                preview_text = preview_custom_module(project_dir, class_name, args.in_type, args.out_type)
            elif module_type == "cfunction":
                check_project_c_support(project_dir)
                files = cfunction_module_files(class_name, args.in_type, args.out_type)
                preview_text = preview_cfunction_module(project_dir, class_name, args.in_type, args.out_type)
            else:
                files = verilator_module_files(class_name, interface)
                preview_text = preview_verilator_module(project_dir, class_name, interface)
            check_output_paths(project_dir, files)
            print(preview_text, end="")
            if not args.yes and not confirm_module_creation():
                print("Cancelled; no files were created.")
                return 0
            output_paths = write_project_files(project_dir, files)
            if module_type in ("verilator", "cfunction"):
                record_generated_files(project_dir, generated_subset(files))
        except (EOFError, OSError, ValueError, TemplateError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nCancelled; no further files will be created.", file=sys.stderr)
            return 130

        print("Created:")
        for path in output_paths:
            print(f"  {path}")
        print("CMake will discover the new sources on the next build. main.cpp was not modified.")
        return 0

    try:
        project_dir = create_project(args.project_dir)
    except (OSError, ValueError, TemplateError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Created project: {project_dir}")
    print("Build with: cmake -S . -B build -DSTREAMPU_ROOT=" + str(stream_pu_path()))
    if aff3ct_is_built(aff3ct_path()):
        print("For projects using AFF3CT modules, pass -DAFF3CT_ROOT=" + str(aff3ct_path()) + " instead")
    print("Then run: cmake --build build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
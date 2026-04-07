#!/usr/bin/env python3
"""
Add a new UART-wrapped hardware block to an existing Hulotte project.

Two files are generated per module:

  <ModuleName>Core.sv   — FPGA-synthesizable core
                          Interface: clk, reset, uart_rx (in), uart_tx (out)
                          Contains: UART_recv -> custom_hw (ready/valid) -> UART_fifoed_send
                          This file is the one to target for FPGA synthesis.

  <ModuleName>.sv       — Verilator simulation wrapper
                          Interface: 32-bit ready/valid (same as other Hulotte blocks)
                          Wraps <ModuleName>Core between host-side UART transceivers
                          connected by simulation wires.

Usage:
    python3 add_uart_hw_module.py <project_path> <module_name>

Example:
    python3 add_uart_hw_module.py /path/to/my_project UartWrappedFilter
"""

import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def render_template(template_name, context, template_dir):
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


def get_project_name(project_dir):
    cmake_path = Path(project_dir) / "CMakeLists.txt"
    if not cmake_path.exists():
        return None

    with open(cmake_path, "r") as file_desc:
        for line in file_desc:
            if line.startswith("project("):
                import re
                match = re.search(r"project\((\w+)", line)
                if match:
                    return match.group(1)
    return None


def create_uart_hardware_module(project_dir, module_name, template_dir):
    hw_dir = Path(project_dir) / "src" / "hw"
    hw_dir.mkdir(parents=True, exist_ok=True)

    context = {"module_name": module_name}

    # Generate the FPGA-synthesizable core
    core_name = f"{module_name}Core"
    core_content = render_template("fpga_core_hw_module.sv.j2", context, template_dir)
    core_path = hw_dir / f"{core_name}.sv"
    with open(core_path, "w") as file_desc:
        file_desc.write(core_content)
    print(f"✓ Created {core_path.relative_to(project_dir)}")

    # Generate the Verilator simulation wrapper
    wrapper_content = render_template("uart_hw_module.sv.j2", context, template_dir)
    wrapper_path = hw_dir / f"{module_name}.sv"
    with open(wrapper_path, "w") as file_desc:
        file_desc.write(wrapper_content)
    print(f"✓ Created {wrapper_path.relative_to(project_dir)}")

    return wrapper_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 add_uart_hw_module.py <project_path> <module_name>")
        print("\nExample:")
        print("  python3 add_uart_hw_module.py /path/to/my_project UartWrappedFilter")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    module_name = sys.argv[2]

    if not project_dir.exists():
        print(f"ERROR: Project directory not found: {project_dir}")
        sys.exit(1)

    if not (project_dir / "CMakeLists.txt").exists():
        print("ERROR: Not a valid Hulotte project (no CMakeLists.txt)")
        sys.exit(1)

    project_name = get_project_name(project_dir)
    if not project_name:
        print("ERROR: Could not determine project name from CMakeLists.txt")
        sys.exit(1)

    template_dir = Path(__file__).resolve().parent / "templates"
    if not template_dir.exists():
        print(f"ERROR: Templates directory not found: {template_dir}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("ADDING UART-WRAPPED HARDWARE BLOCK TO PROJECT")
    print(f"{'='*70}\n")

    print(f"Project: {project_name}")
    print(f"Location: {project_dir}")
    print(f"New UART hardware block: {module_name}\n")

    create_uart_hardware_module(project_dir, module_name, template_dir)

    print(f"\n{'='*70}")
    print("UART HARDWARE BLOCK CREATED SUCCESSFULLY!")
    print(f"{'='*70}\n")

    print("✨ FILES CREATED:")
    print(f"   • src/hw/{module_name}Core.sv    (FPGA-synthesizable core: uart_rx → hw → uart_tx)")
    print(f"   • src/hw/{module_name}.sv        (Verilator simulation wrapper: rv ↔ UART ↔ Core ↔ UART ↔ rv)\n")

    print("📝 NEXT STEPS:\n")
    print("1. IMPLEMENT YOUR CORE LOGIC")
    print(f"   Edit src/hw/{module_name}Core.sv and replace the TODO assignment")
    print("   inside the custom hardware core section with your own transform.")
    print(f"   The simulation wrapper src/hw/{module_name}.sv does NOT need to be modified.\n")

    print("2. CONNECT THE BLOCK MANUALLY IN MAIN.CPP")
    print("   Edit src/main.cpp and add:")
    print(f'     - #include "VModel_{module_name}.h"')
    print(f'     - auto hw = std::make_unique<VerilatorSimulation<VModel_{module_name}>>(n_elmts, "trace_{module_name.lower()}", false);')
    print( '     - socket bindings for hw in the pipeline\n')

    print("3. FOR FPGA SYNTHESIS")
    print(f"   Synthesize src/hw/{module_name}Core.sv.")
    print("   Connect uart_rx/uart_tx to the physical UART pins on the FPGA.\n")

    print("4. REBUILD")
    print(f"   cd {project_dir}")
    print("   rm -rf build && ./build.sh\n")

    print("5. TEST")
    print("   cd build && ./build_executable_name\n")


if __name__ == "__main__":
    main()

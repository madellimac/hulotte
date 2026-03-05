#!/usr/bin/env python3
"""
Add a new hardware block to an existing Hulotte project.

Each hardware block:
- Implements the standard ready/valid interface
- Gets automatically discovered and compiled by CMakeLists.txt
- Can be instantiated independently in main.cpp

Usage:
    python3 add_hardware_module.py <project_path> <module_name>

Example:
    python3 add_hardware_module.py /path/to/my_project FilterBlock
"""

import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def render_template(template_name, context, template_dir):
    """Render a Jinja2 template."""
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    return template.render(context)


def get_project_name(project_dir):
    """Extract project name from CMakeLists.txt."""
    cmake_path = Path(project_dir) / "CMakeLists.txt"
    if not cmake_path.exists():
        return None
    
    with open(cmake_path, 'r') as f:
        for line in f:
            if line.startswith('project('):
                import re
                match = re.search(r'project\((\w+)', line)
                if match:
                    return match.group(1)
    return None


def create_hardware_module(project_dir, module_name, template_dir):
    """Create hardware module files from templates."""
    hw_dir = Path(project_dir) / "src" / "hw"
    hw_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate from template
    context = {"module_name": module_name}
    
    sv_content = render_template("hw_module.sv.j2", context, template_dir)
    
    sv_path = hw_dir / f"{module_name}.sv"
    
    # Create file
    with open(sv_path, 'w') as f:
        f.write(sv_content)
    print(f"✓ Created {sv_path.relative_to(project_dir)}")
    
    return sv_path


def add_include_to_main(project_dir, module_name):
    """Add #include directive to main.cpp"""
    main_cpp = project_dir / "src" / "main.cpp"
    if not main_cpp.exists():
        return False
    
    include_line = f'#include "VModel_{module_name}.h"'
    
    with open(main_cpp, 'r') as f:
        content = f.read()
    
    # Check if already included
    if include_line in content:
        return True
    
    # Find the position after #include "VModel_PassThrough.h"
    insert_pos = content.find('#include "VModel_PassThrough.h"')
    if insert_pos != -1:
        # Find end of line
        eol = content.find('\n', insert_pos)
        if eol != -1:
            content = content[:eol+1] + include_line + '\n' + content[eol+1:]
    else:
        # Fallback: insert after last #include
        last_include = content.rfind('#include')
        if last_include != -1:
            eol = content.find('\n', last_include)
            if eol != -1:
                content = content[:eol+1] + include_line + '\n' + content[eol+1:]
    
    with open(main_cpp, 'w') as f:
        f.write(content)
    return True


def add_instantiation_to_main(project_dir, module_name):
    """Add hardware block instantiation to main.cpp"""
    main_cpp = project_dir / "src" / "main.cpp"
    if not main_cpp.exists():
        return False
    
    # Instantiation code with TRACE DISABLED by default
    # Using stack allocation (no make_unique) for simpler access
    instantiation = f'    module::VerilatorSimulation<VModel_{module_name}> hw_{module_name}(K, "trace_{module_name}", false);\n'
    
    with open(main_cpp, 'r') as f:
        content = f.read()
    
    # Check if already instantiated
    if f'hw_{module_name}' in content:
        return True
    
    # Find insertion point: after "// 1. Modules creation" section, before "// 2. Sockets binding"
    modules_section = content.find('// 1. Modules creation')
    sockets_section = content.find('// 2. Sockets binding')
    
    if modules_section != -1 and sockets_section != -1:
        # Find last module creation line before sockets section
        last_module_line = content.rfind('\n', modules_section, sockets_section)
        if last_module_line != -1:
            content = content[:last_module_line+1] + instantiation + content[last_module_line+1:]
    
    with open(main_cpp, 'w') as f:
        f.write(content)
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 add_hardware_module.py <project_path> <module_name>")
        print("\nExample:")
        print("  python3 add_hardware_module.py /path/to/my_project FilterBlock")
        sys.exit(1)
    
    project_dir = Path(sys.argv[1]).resolve()
    module_name = sys.argv[2]
    
    # Validate project exists
    if not project_dir.exists():
        print(f"ERROR: Project directory not found: {project_dir}")
        sys.exit(1)
    
    if not (project_dir / "CMakeLists.txt").exists():
        print(f"ERROR: Not a valid Hulotte project (no CMakeLists.txt)")
        sys.exit(1)
    
    # Get project name
    project_name = get_project_name(project_dir)
    if not project_name:
        print("ERROR: Could not determine project name from CMakeLists.txt")
        sys.exit(1)
    
    # Find template directory
    template_dir = Path(__file__).resolve().parent / "templates"
    if not template_dir.exists():
        print(f"ERROR: Templates directory not found: {template_dir}")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"ADDING HARDWARE BLOCK TO PROJECT")
    print(f"{'='*70}\n")
    
    print(f"Project: {project_name}")
    print(f"Location: {project_dir}")
    print(f"New hardware block: {module_name}\n")
    
    # Generate hardware module file
    sv_path = create_hardware_module(project_dir, module_name, template_dir)
    
    print(f"\n{'='*70}")
    print("HARDWARE BLOCK CREATED SUCCESSFULLY!")
    print(f"{'='*70}\n")
    
    print("✨ FILES CREATED/UPDATED:")
    print(f"   • src/hw/{module_name}.sv (hardware implementation)")
    if add_include_to_main(project_dir, module_name):
        print(f"   • src/main.cpp (added #include)")
    if add_instantiation_to_main(project_dir, module_name):
        print(f"   • src/main.cpp (added instantiation with trace DISABLED)\n")
    
    print("⚠️  IMPORTANT - VERILATOR TRACE LIMITATION:")
    print("   Only ONE hardware module can have tracing enabled at a time due to Verilator.")
    print("   New modules are automatically created with trace DISABLED (enable_trace=false).")
    print("   To enable tracing on a different module:")
    print(f"       1. Set enable_trace=true for: hw_{module_name}")
    print(f"       2. Set enable_trace=false for all other hardware blocks\n")
    
    print("📝 NEXT STEPS:\n")
    
    print("1. IMPLEMENT YOUR LOGIC")
    print(f"   Edit src/hw/{module_name}.sv and replace the pass-through example")
    print("   with your custom processing logic.\n")
    print("   Interface (DO NOT CHANGE):")
    print("      Input:  clk, reset, in_data[31:0], in_valid, out_ready")
    print("      Output: in_ready, out_data[31:0], out_valid\n")
    
    print("2. CONNECT THE BLOCK (if main.cpp was generated, update bindings)")
    print("   Edit src/main.cpp and add socket bindings in '// 2. Sockets binding':")
    print(f"       source[\"generate::out_data\"] = (*hw_{module_name})[\"simulate::input\"];")
    print(f"       (*hw_{module_name})[\"simulate::output\"] = finalizer[\"finalize::in\"];\n")
    
    print("3. REBUILD")
    print(f"   cd {project_dir}")
    print("   rm -rf build && ./build.sh\n")
    
    print("4. TEST")
    print("   cd build && ./build_executable_name\n")


if __name__ == "__main__":
    main()

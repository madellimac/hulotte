#!/usr/bin/env python3
"""
Add a new custom StreamPU module to an existing Hulotte project.

This script generates the .hpp and .cpp files for a new module and
automatically updates CMakeLists.txt. You'll only need to update 
main.cpp to instantiate and bind the module.

Usage:
    python3 add_custom_module.py <project_path> <module_name>

Example:
    python3 add_custom_module.py /path/to/my_project DataProcessor
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


def create_custom_module(project_dir, module_name, template_dir):
    """Create custom module files from templates."""
    custom_dir = Path(project_dir) / "src" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate from templates
    context = {"module_name": module_name}
    
    header_content = render_template("MyModule.hpp.j2", context, template_dir)
    impl_content = render_template("MyModule.cpp.j2", context, template_dir)
    
    header_path = custom_dir / f"{module_name}.hpp"
    impl_path = custom_dir / f"{module_name}.cpp"
    
    # Create files
    with open(header_path, 'w') as f:
        f.write(header_content)
    print(f"✓ Created {header_path.relative_to(project_dir)}")
    
    with open(impl_path, 'w') as f:
        f.write(impl_content)
    print(f"✓ Created {impl_path.relative_to(project_dir)}")
    
    return header_path, impl_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 add_custom_module.py <project_path> <module_name>")
        print("\nExample:")
        print("  python3 add_custom_module.py /path/to/my_project DataProcessor")
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
    print(f"ADDING CUSTOM MODULE TO PROJECT")
    print(f"{'='*70}\n")
    
    print(f"Project: {project_name}")
    print(f"Location: {project_dir}")
    print(f"New module: {module_name}\n")
    
    # Generate module files
    header_path, impl_path = create_custom_module(project_dir, module_name, template_dir)
    
    print(f"\n{'='*70}")
    print("MODULE FILES CREATED SUCCESSFULLY!")
    print(f"{'='*70}\n")
    
    print("✨ FILES CREATED:")
    print(f"   • src/custom/{module_name}.hpp")
    print(f"   • src/custom/{module_name}.cpp\n")
    
    print("📝 NEXT STEPS:\n")
    
    print("CMakeLists.txt: ✓ NO CHANGES NEEDED")
    print("(Automatically compiles all .cpp files in src/custom/)\n")
    
    print("1. UPDATE main.cpp (only step):")
    print(f"   Add include at top:")
    print(f'       #include "custom/{module_name}.hpp"\n')
    print("   Add instantiation in '// 1. Modules creation':")
    print(f'       module::{module_name} {module_name.lower()}(n_elmts);\n')
    print("   Add socket binding in '// 2. Sockets binding':")
    print(f'       my_module ["process::out"] = {module_name.lower()} ["process::in"];')
    print(f"       {module_name.lower()} [\"process::out\"] = finalizer [\"finalize::in\"];\n")
    
    print("2. REBUILD:")
    print(f"   cd {project_dir}/build")
    print("   cmake ..  (to discover new modules)")
    print("   make\n")


if __name__ == "__main__":
    main()

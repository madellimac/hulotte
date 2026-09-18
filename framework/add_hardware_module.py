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

import argparse
import json
import re
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


NOOP_EXIT_CODE = 2


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


def validate_module_name(module_name):
    """Validate a module identifier suitable for generated files and SV modules."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module_name):
        raise ValueError(
            "module name must match [A-Za-z_][A-Za-z0-9_]* for generated Verilog/C++ artifacts"
        )


def load_manifest(project_dir):
    """Load the optional Hulotte project manifest."""
    manifest_path = Path(project_dir) / "hulotte.project.json"
    if not manifest_path.exists():
        return None, manifest_path

    with open(manifest_path, "r", encoding="utf-8") as file_desc:
        return json.load(file_desc), manifest_path


def save_manifest(manifest_path, manifest_data, dry_run=False):
    """Save the Hulotte project manifest unless in dry-run mode."""
    if dry_run:
        print(f"~ Would update {manifest_path.relative_to(manifest_path.parent)}")
        return

    with open(manifest_path, "w", encoding="utf-8") as file_desc:
        json.dump(manifest_data, file_desc, indent=2)
        file_desc.write("\n")
    print(f"✓ Updated {manifest_path.relative_to(manifest_path.parent)}")


def ensure_hw_project(project_dir, manifest_data):
    """Ensure the target project was generated with hardware support."""
    common_hw_dir = Path(project_dir) / "common" / "hw"
    if manifest_data is not None:
        features = manifest_data.get("features", {})
        if features.get("hardware") is not True:
            raise ValueError(
                "project manifest indicates hardware support is disabled; generate the project with --hw first"
            )

    if not common_hw_dir.exists():
        raise ValueError(
            "project does not contain common/hw support files; generate the project with --hw first"
        )


def create_hardware_module(project_dir, module_name, template_dir, dry_run=False, force=False):
    """Create hardware module files from templates."""
    hw_dir = Path(project_dir) / "src" / "hw"
    if not dry_run:
        hw_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate from template
    context = {"module_name": module_name}
    
    sv_content = render_template("hw_module.sv.j2", context, template_dir)
    
    sv_path = hw_dir / f"{module_name}.sv"

    if sv_path.exists():
        existing_content = sv_path.read_text(encoding="utf-8")
        if existing_content == sv_content and not force:
            print(f"= No changes needed for {sv_path.relative_to(project_dir)}")
            return sv_path, False
        if not force:
            raise FileExistsError(
                f"{sv_path.relative_to(project_dir)} already exists with different content; use --force to overwrite"
            )

    if dry_run:
        action = "overwrite" if sv_path.exists() else "create"
        print(f"~ Would {action} {sv_path.relative_to(project_dir)}")
        return sv_path, True

    with open(sv_path, 'w', encoding="utf-8") as f:
        f.write(sv_content)

    if sv_path.exists():
        print(f"✓ Wrote {sv_path.relative_to(project_dir)}")

    return sv_path, True


def update_manifest(project_dir, manifest_data, manifest_path, module_name, module_id, dry_run=False, force=False):
    """Register the hardware module in the project manifest when available."""
    if manifest_data is None:
        print("! No hulotte.project.json found; skipping manifest update")
        return False

    hardware_modules = manifest_data.setdefault("hardware_modules", [])
    desired_entry = {
        "id": module_id,
        "module_name": module_name,
        "source": f"src/hw/{module_name}.sv",
        "enabled": True,
    }

    for index, module_entry in enumerate(hardware_modules):
        if module_entry.get("id") != module_id:
            continue

        if module_entry == desired_entry:
            print(f"= Manifest already contains hardware module '{module_id}'")
            return False

        if not force:
            raise ValueError(
                f"manifest already contains hardware module id '{module_id}' with different settings; use --force to overwrite"
            )

        hardware_modules[index] = desired_entry
        save_manifest(manifest_path, manifest_data, dry_run=dry_run)
        return True

    hardware_modules.append(desired_entry)
    save_manifest(manifest_path, manifest_data, dry_run=dry_run)
    return True


def parse_args():
    """Parse CLI arguments while keeping legacy positional compatibility."""
    parser = argparse.ArgumentParser(description="Add a new hardware block to an existing Hulotte project")
    parser.add_argument("project_path", nargs="?", help="Legacy positional project path")
    parser.add_argument("legacy_module_name", nargs="?", help="Legacy positional module name")
    parser.add_argument("--project-root", help="Path to the Hulotte project root")
    parser.add_argument("--name", dest="module_name", help="Hardware module name")
    parser.add_argument("--id", dest="module_id", help="Unique manifest id for the hardware block")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing conflicting module entry")
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = args.project_root if args.project_root else args.project_path
    module_name = args.module_name if args.module_name else args.legacy_module_name

    if not project_root or not module_name:
        print("ERROR: both project path and module name are required")
        print("Example: python3 add_hardware_module.py --project-root /path/to/project --name FilterBlock")
        sys.exit(1)

    try:
        validate_module_name(module_name)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    module_id = args.module_id if args.module_id else module_name.lower()
    
    # Validate project exists
    project_dir = Path(project_root).resolve()
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

    try:
        manifest_data, manifest_path = load_manifest(project_dir)
        ensure_hw_project(project_dir, manifest_data)
    except Exception as exc:
        print(f"ERROR: {exc}")
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
    print(f"Hardware block id: {module_id}\n")
    
    try:
        sv_path, module_changed = create_hardware_module(
            project_dir,
            module_name,
            template_dir,
            dry_run=args.dry_run,
            force=args.force,
        )
        manifest_changed = update_manifest(
            project_dir,
            manifest_data,
            manifest_path,
            module_name,
            module_id,
            dry_run=args.dry_run,
            force=args.force,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if not module_changed and not manifest_changed:
        print("\nNo changes applied.")
        sys.exit(NOOP_EXIT_CODE)
    
    print(f"\n{'='*70}")
    print("HARDWARE BLOCK CREATED SUCCESSFULLY!")
    print(f"{'='*70}\n")
    
    print("✨ FILES CREATED/UPDATED:")
    print(f"   • src/hw/{module_name}.sv (hardware implementation)")
    if manifest_data is not None:
        print("   • hulotte.project.json (hardware_modules updated)")
    print("   • src/main.cpp (not modified by design)\n")
    
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
    
    print("2. CONNECT THE BLOCK MANUALLY")
    print("   Edit src/main.cpp and add:")
    print(f'     - #include "VModel_{module_name}.h"')
    print(f'     - auto hw_{module_name.lower()} = std::make_unique<VerilatorSimulation<VModel_{module_name}>>(n_elmts, "trace_{module_name.lower()}", false);')
    print(f'     - socket bindings for hw_{module_name.lower()} in the pipeline\n')
    
    print("3. REBUILD")
    print(f"   cd {project_dir}")
    print("   rm -rf build && ./build.sh\n")
    
    print("4. TEST")
    print("   cd build && ./build_executable_name\n")


if __name__ == "__main__":
    main()

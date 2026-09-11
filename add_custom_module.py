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
    """Validate a module identifier suitable for generated C++ artifacts."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module_name):
        raise ValueError(
            "module name must match [A-Za-z_][A-Za-z0-9_]* for generated C++ artifacts"
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


def ensure_streampu_project(manifest_data):
    """Ensure the target project is a StreamPU-based project when manifest is available."""
    if manifest_data is None:
        return

    features = manifest_data.get("features", {})
    if features.get("streampu") is not True:
        raise ValueError("project manifest indicates StreamPU support is disabled")


def create_custom_module(project_dir, module_name, template_dir, dry_run=False, force=False):
    """Create custom module files from templates."""
    custom_dir = Path(project_dir) / "src" / "custom"
    if not dry_run:
        custom_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate from templates
    context = {"module_name": module_name}
    
    header_content = render_template("MyModule.hpp.j2", context, template_dir)
    impl_content = render_template("MyModule.cpp.j2", context, template_dir)
    
    header_path = custom_dir / f"{module_name}.hpp"
    impl_path = custom_dir / f"{module_name}.cpp"

    changed = False
    for path, content in ((header_path, header_content), (impl_path, impl_content)):
        if path.exists():
            existing_content = path.read_text(encoding="utf-8")
            if existing_content == content and not force:
                print(f"= No changes needed for {path.relative_to(project_dir)}")
                continue
            if not force:
                raise FileExistsError(
                    f"{path.relative_to(project_dir)} already exists with different content; use --force to overwrite"
                )

        if dry_run:
            action = "overwrite" if path.exists() else "create"
            print(f"~ Would {action} {path.relative_to(project_dir)}")
            changed = True
            continue

        with open(path, 'w', encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Wrote {path.relative_to(project_dir)}")
        changed = True
    
    return header_path, impl_path, changed


def update_manifest(manifest_data, manifest_path, module_name, module_id, dry_run=False, force=False):
    """Register the custom module in the project manifest when available."""
    if manifest_data is None:
        print("! No hulotte.project.json found; skipping manifest update")
        return False

    features = manifest_data.setdefault("features", {})
    features["custom"] = True

    custom_modules = manifest_data.setdefault("custom_modules", [])
    desired_entry = {
        "id": module_id,
        "class_name": module_name,
        "header": f"src/custom/{module_name}.hpp",
        "source": f"src/custom/{module_name}.cpp",
        "enabled": True,
    }

    for index, module_entry in enumerate(custom_modules):
        if module_entry.get("id") != module_id:
            continue

        if module_entry == desired_entry:
            print(f"= Manifest already contains custom module '{module_id}'")
            return False

        if not force:
            raise ValueError(
                f"manifest already contains custom module id '{module_id}' with different settings; use --force to overwrite"
            )

        custom_modules[index] = desired_entry
        save_manifest(manifest_path, manifest_data, dry_run=dry_run)
        return True

    custom_modules.append(desired_entry)
    save_manifest(manifest_path, manifest_data, dry_run=dry_run)
    return True


def parse_args():
    """Parse CLI arguments while keeping legacy positional compatibility."""
    parser = argparse.ArgumentParser(description="Add a new custom StreamPU module to an existing Hulotte project")
    parser.add_argument("project_path", nargs="?", help="Legacy positional project path")
    parser.add_argument("legacy_module_name", nargs="?", help="Legacy positional module name")
    parser.add_argument("--project-root", help="Path to the Hulotte project root")
    parser.add_argument("--name", dest="module_name", help="Custom module class name")
    parser.add_argument("--id", dest="module_id", help="Unique manifest id for the custom module")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing conflicting module entry")
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = args.project_root if args.project_root else args.project_path
    module_name = args.module_name if args.module_name else args.legacy_module_name

    if not project_root or not module_name:
        print("ERROR: both project path and module name are required")
        print("Example: python3 add_custom_module.py --project-root /path/to/project --name DataProcessor")
        sys.exit(1)

    try:
        validate_module_name(module_name)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    module_id = args.module_id if args.module_id else module_name.lower()

    project_dir = Path(project_root).resolve()
    
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

    try:
        manifest_data, manifest_path = load_manifest(project_dir)
        ensure_streampu_project(manifest_data)
    except Exception as exc:
        print(f"ERROR: {exc}")
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
    print(f"Custom module id: {module_id}\n")
    
    try:
        header_path, impl_path, module_changed = create_custom_module(
            project_dir,
            module_name,
            template_dir,
            dry_run=args.dry_run,
            force=args.force,
        )
        manifest_changed = update_manifest(
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
    print("MODULE FILES CREATED SUCCESSFULLY!")
    print(f"{'='*70}\n")
    
    print("✨ FILES CREATED:")
    print(f"   • src/custom/{module_name}.hpp")
    print(f"   • src/custom/{module_name}.cpp\n")
    if manifest_data is not None:
        print("   • hulotte.project.json (custom_modules updated)\n")
    
    print("📝 NEXT STEPS:\n")
    
    print("CMakeLists.txt: ✓ NO CHANGES NEEDED")
    print("(Automatically compiles all .cpp files in src/custom/)\n")
    
    print("1. UPDATE main.cpp (only step):")
    print(f"   //Add include at top:")
    print(f'       #include "custom/{module_name}.hpp"\n')
    print("   //Add instantiation in '// 1. Modules creation':")
    print(f'       module::{module_name} {module_name.lower()}(n_elmts);\n')
    print("   //Add socket binding in '// 2. Sockets binding':")
    print(f'       my_module ["process::out"] = {module_name.lower()} ["process::in"];')
    print(f"       {module_name.lower()} [\"process::out\"] = finalizer [\"finalize::in\"];\n")
    
    print("2. REBUILD:")
    print(f"   cd {project_dir}/build")
    print("   cmake ..  (to discover new modules)")
    print("   make\n")


if __name__ == "__main__":
    main()

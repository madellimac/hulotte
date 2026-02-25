#!/usr/bin/env python3
"""
Hulotte Dependencies Installer
Interactive script to install AFF3CT and StreamPU dependencies
"""

import os
import sys
import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path
from hulotte_utils import (
    to_relative_path, Colors, print_header, print_success, print_info, 
    print_warning, print_error, print_ascii_art, play_owl_hoot
)


def run_command(cmd, cwd=None, show_output=True):
    """
    Run a shell command and return success status
    """
    try:
        if show_output:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                shell=True,
                check=True
            )
        else:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {cmd}")
        if not show_output and e.stderr:
            print(e.stderr.decode())
        return False


def ask_yes_no(question, default=True):
    """
    Ask a yes/no question and return boolean
    """
    if default:
        prompt = f"{question} [Y/n]: "
    else:
        prompt = f"{question} [y/N]: "
    
    while True:
        response = input(prompt).strip().lower()
        if response == '':
            return default
        elif response in ['y', 'yes', 'oui', 'o']:
            return True
        elif response in ['n', 'no', 'non']:
            return False
        else:
            print_warning("Please answer 'y' or 'n'")


def get_cpu_cores():
    """Get number of CPU cores for parallel compilation"""
    try:
        return str(os.cpu_count())
    except:
        return "4"


def get_latest_tag(repo_url):
    """Fetch latest tag from a git repository."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-version:refname", repo_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.decode().split('\n')
            for line in lines:
                if line.strip():
                    tag = line.split('refs/tags/')[-1].rstrip('^{}')
                    if tag and not tag.endswith('^{}'):
                        return tag
    except Exception as e:
        print_warning(f"Could not fetch tags: {e}")
    return None


def choose_version(repo_url, repo_name="repository"):
    """Let user choose a version tag (default to latest)."""
    latest_tag = get_latest_tag(repo_url)
    
    if latest_tag:
        print_info(f"Latest {repo_name} version: {latest_tag}")
        if ask_yes_no(f"Use {latest_tag}?", default=True):
            return latest_tag
        
        custom_tag = input(f"Enter {repo_name} tag/branch (or empty for default): ").strip()
        if custom_tag:
            return custom_tag
        return latest_tag
    else:
        print_warning(f"Could not determine latest {repo_name} version, using default")
        custom_tag = input(f"Enter {repo_name} tag/branch (or empty for main/master): ").strip()
        return custom_tag if custom_tag else None


def check_git():
    """Check if git is installed"""
    print_info("Checking for git...")
    result = subprocess.run(
        ["which", "git"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        print_error("git is not installed!")
        print_info("Please install git: sudo apt-get install git")
        return False
    print_success("git found")
    return True


def check_cmake():
    """Check if cmake is installed"""
    print_info("Checking for cmake...")
    result = subprocess.run(
        ["which", "cmake"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        print_error("cmake is not installed!")
        print_info("Please install cmake: sudo apt-get install cmake")
        return False
    print_success("cmake found")
    return True


def check_compiler():
    """Check if g++ is installed"""
    print_info("Checking for g++...")
    result = subprocess.run(
        ["which", "g++"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        print_error("g++ is not installed!")
        print_info("Please install g++: sudo apt-get install build-essential")
        return False
    print_success("g++ found")
    return True


def install_aff3ct(hulotte_root):
    """
    Install AFF3CT with StreamPU as static library
    """
    print_header("Installing AFF3CT with StreamPU")
    
    aff3ct_url = "https://github.com/aff3ct/aff3ct.git"
    aff3ct_tag = choose_version(aff3ct_url, "AFF3CT")
    
    aff3ct_dir = hulotte_root / "aff3ct"
    
    # Check if AFF3CT already exists
    if aff3ct_dir.exists():
        print_warning(f"AFF3CT directory already exists: {to_relative_path(aff3ct_dir)}")
        if not ask_yes_no("Do you want to delete and reinstall?", default=False):
            print_info("Skipping AFF3CT installation")
            return None
        print_info("Removing existing AFF3CT directory...")
        run_command(f"rm -rf {aff3ct_dir}")
    
    # Clone AFF3CT
    print_info("Cloning AFF3CT repository...")
    clone_cmd = f"git clone --recursive {aff3ct_url}"
    if aff3ct_tag:
        clone_cmd += f" --branch {aff3ct_tag}"
    
    if not run_command(clone_cmd, cwd=hulotte_root):
        print_error("Failed to clone AFF3CT")
        return None
    
    print_success("AFF3CT cloned successfully")
    
    # Create build directory
    build_dir = aff3ct_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Configure with CMake
    print_info("Configuring AFF3CT with CMake...")
    cmake_cmd = (
        "cmake .. "
        "-DCMAKE_BUILD_TYPE=Release "
        "-DAFF3CT_COMPILE_EXE=OFF "
        "-DAFF3CT_COMPILE_STATIC_LIB=ON "
        "-DAFF3CT_COMPILE_SHARED_LIB=OFF "
        "-DAFF3CT_LINK_HWLOC=OFF "
        "-DAFF3CT_EXT_STRINGS=ON "
        "-DSPU_COMPILE_STATIC_LIB=ON "
    )
    
    if not run_command(cmake_cmd, cwd=build_dir):
        print_error("CMake configuration failed")
        return None
    
    print_success("CMake configuration successful")
    
    # Compile
    cores = get_cpu_cores()
    print_info(f"Compiling AFF3CT (using {cores} cores)...")
    print_info("This may take several minutes...")
    
    if not run_command(f"make -j{cores}", cwd=build_dir):
        print_error("AFF3CT compilation failed")
        return None
    
    print_success("AFF3CT compiled successfully")
    
    # Verify installation
    lib_file = build_dir / "lib" / "libaff3ct-4.1.0.a"
    if not lib_file.exists():
        # Try to find the library with any version
        lib_files = list((build_dir / "lib").glob("libaff3ct-*.a"))
        if lib_files:
            lib_file = lib_files[0]
            print_success(f"AFF3CT library found: {lib_file.name}")
        else:
            print_error("AFF3CT library not found after compilation")
            return None
    else:
        print_success(f"AFF3CT library found: {lib_file.name}")
    
    # Check for StreamPU
    streampu_lib = build_dir / "lib" / "streampu" / "lib" / "libstreampu.a"
    if streampu_lib.exists():
        print_success(f"StreamPU library found (compiled with AFF3CT)")
        return {
            "aff3ct_root": str(aff3ct_dir.resolve()),
            "streampu_root": str((aff3ct_dir / "lib" / "streampu").resolve()),
            "aff3ct_lib": str(lib_file.resolve()),
            "streampu_lib": str(streampu_lib.resolve())
        }
    else:
        print_warning("StreamPU library not found in AFF3CT build")
        return {
            "aff3ct_root": str(aff3ct_dir.resolve()),
            "aff3ct_lib": str(lib_file.resolve())
        }


def install_streampu(hulotte_root):
    """
    Install StreamPU as standalone static library
    """
    print_header("Installing StreamPU (standalone)")
    
    streampu_url = "https://github.com/aff3ct/streampu.git"
    streampu_tag = choose_version(streampu_url, "StreamPU")
    
    streampu_dir = hulotte_root / "streampu"
    
    # Check if StreamPU already exists
    if streampu_dir.exists():
        print_warning(f"StreamPU directory already exists: {to_relative_path(streampu_dir)}")
        if not ask_yes_no("Do you want to delete and reinstall?", default=False):
            print_info("Skipping StreamPU installation")
            return None
        print_info("Removing existing StreamPU directory...")
        run_command(f"rm -rf {streampu_dir}")
    
    # Clone StreamPU
    print_info("Cloning StreamPU repository...")
    clone_cmd = f"git clone --recursive {streampu_url}"
    if streampu_tag:
        clone_cmd += f" --branch {streampu_tag}"
    
    if not run_command(clone_cmd, cwd=hulotte_root):
        print_error("Failed to clone StreamPU")
        return None
    
    print_success("StreamPU cloned successfully")
    # Create build directory
    build_dir = streampu_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Configure with CMake
    print_info("Configuring StreamPU with CMake...")
    cmake_cmd = (
        "cmake .. "
        "-DCMAKE_BUILD_TYPE=Release "
        "-DSPU_COMPILE_STATIC_LIB=ON "
        "-DSPU_COMPILE_SHARED_LIB=OFF "
        "-DSPU_LINK_HWLOC=OFF "
    )
    
    if not run_command(cmake_cmd, cwd=build_dir):
        print_error("CMake configuration failed")
        return None
    
    print_success("CMake configuration successful")
    
    # Compile
    cores = get_cpu_cores()
    print_info(f"Compiling StreamPU (using {cores} cores)...")
    
    if not run_command(f"make -j{cores}", cwd=build_dir):
        print_error("StreamPU compilation failed")
        return None
    
    print_success("StreamPU compiled successfully")
    
    # Verify installation
    lib_file = build_dir / "lib" / "libstreampu.a"
    if not lib_file.exists():
        print_error("StreamPU library not found after compilation")
        return None
    
    print_success(f"StreamPU library found: {lib_file}")
    
    return {
        "streampu_root": str(streampu_dir.resolve()),
        "streampu_lib": str(lib_file.resolve())
    }


def install_surfer(hulotte_root):
    """Download and install Surfer binary"""
    print_header("Installing Surfer (Waveform Viewer)")
    
    # URL for Linux x86_64 binary (v0.3.0 Release)
    # Using stable release package instead of CI artifacts
    surfer_url = "https://gitlab.com/api/v4/projects/42073614/packages/generic/surfer/v0.3.0/surfer_linux_v0.3.0.zip"
    
    # Install in tools directory
    tools_dir = hulotte_root / "tools"
    tools_dir.mkdir(exist_ok=True)
    zip_file = tools_dir / "surfer.zip"
    target_file = tools_dir / "surfer"
    
    print_info(f"Downloading Surfer v0.3.0...")
    try:
        # Try wget first
        if shutil.which("wget"):
            cmd = f"wget -O {zip_file} {surfer_url} -q --show-progress"
            if not run_command(cmd, show_output=True):
                print_error("Failed to download Surfer with wget")
                return None
        # Try curl
        elif shutil.which("curl"):
            cmd = f"curl -L -o {zip_file} {surfer_url}"
            if not run_command(cmd, show_output=True):
                print_error("Failed to download Surfer with curl")
                return None
        else:
             print_error("Neither wget nor curl found. Cannot download Surfer.")
             return None

        # Extract zip
        print_info("Extracting Surfer...")
        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                # Assuming the binary is named 'surfer' inside the zip
                # List files to be sure
                file_names = zf.namelist()
                surfer_bin_name = next((name for name in file_names if "surfer" in name and not name.endswith("/")), None)
                
                if not surfer_bin_name:
                     print_error("Could not find surfer binary in zip archive")
                     return None
                
                # Extract to tools dir
                zf.extract(surfer_bin_name, tools_dir)
                
                # If extracted file is not named 'surfer' (e.g. inside a folder), move it
                extracted_path = tools_dir / surfer_bin_name
                if extracted_path.resolve() != target_file.resolve():
                    shutil.move(str(extracted_path), str(target_file))

        except zipfile.BadZipFile:
            print_error("Downloaded file is not a valid zip archive")
            return None

        target_file.chmod(0o755) # Make executable
        
        # Cleanup zip
        if zip_file.exists():
            zip_file.unlink()

        print_success(f"Surfer downloaded to {to_relative_path(target_file)}")
        print_info("Consider adding this directory to your PATH:")
        print_info(f"  export PATH=$PATH:{tools_dir}")
        
        return str(target_file)
        
    except Exception as e:
        print_error(f"Error installing Surfer: {e}")
        return None



def create_install_info(hulotte_root, aff3ct_info, streampu_info, surfer_path=None):
    """
    Create a file with installation information
    """
    info_file = hulotte_root / "INSTALL_INFO.txt"
    
    with open(info_file, 'w') as f:
        f.write("Hulotte Dependencies Installation Information\n")
        f.write("=" * 60 + "\n\n")
        
        if aff3ct_info:
            f.write("AFF3CT Installation:\n")
            f.write(f"  Root: {aff3ct_info.get('aff3ct_root', 'N/A')}\n")
            f.write(f"  Library: {aff3ct_info.get('aff3ct_lib', 'N/A')}\n")
            if 'streampu_root' in aff3ct_info:
                f.write(f"  StreamPU (submodule): {aff3ct_info['streampu_root']}\n")
                f.write(f"  StreamPU Library: {aff3ct_info.get('streampu_lib', 'N/A')}\n")
            f.write("\n")
        
        if streampu_info:
            f.write("StreamPU Standalone Installation:\n")
            f.write(f"  Root: {streampu_info.get('streampu_root', 'N/A')}\n")
            f.write(f"  Library: {streampu_info.get('streampu_lib', 'N/A')}\n")
            f.write("\n")

        if surfer_path:
             f.write(f"Surfer (Waveform Viewer): {surfer_path}\n")
        
        f.write("\nTo create a new project, run:\n")
        f.write("  python3 create_project.py\n")
    
    print_success(f"Installation info saved to: {info_file}")



def setup_python_environment(hulotte_root):
    """
    Setup Python virtual environment and install dependencies
    """
    print_header("Setting up Python Environment")
    
    # Create .venv in the current directory (hulotte root)
    venv_dir = hulotte_root / ".venv"
    
    # Check if venv exists
    if not venv_dir.exists():
        print_info(f"Creating virtual environment at: {to_relative_path(venv_dir)}")
        try:
             subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        except subprocess.CalledProcessError:
             print_error("Failed to create virtual environment")
             return None
    else:
        print_success(f"Virtual environment found at: {to_relative_path(venv_dir)}")
        
    # Install dependencies
    print_info("Installing Python dependencies (This may take a moment)...")
    
    # Dependencies list
    packages = ["jinja2"]
    
    # Pip inside venv
    pip_cmd = venv_dir / "bin" / "pip"
    
    try:
        # Upgrade pip first
        subprocess.run([str(pip_cmd), "install", "--upgrade", "pip"], 
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Install packages
        for package in packages:
            print_info(f"Installing {package}...")
            subprocess.run([str(pip_cmd), "install", package], check=True)
            
        print_success("Python dependencies installed successfully")
        return venv_dir
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return None


def main(hoot=False):
    """Main installation script"""
    print_ascii_art()
    if hoot:
        play_owl_hoot()
    print_header("Hulotte Dependencies Installer")
    
    # Get Hulotte root
    # Use the directory where this script is located, not necessarily CWD
    hulotte_root = Path(__file__).resolve().parent
    print_info(f"Hulotte root: {to_relative_path(hulotte_root)}")
    
    # Check prerequisites
    print_header("Checking Prerequisites")
    if not check_git():
        return 1
    if not check_cmake():
        return 1
    if not check_compiler():
        return 1
    
    print_success("All prerequisites satisfied")

    # Install Python dependencies
    venv_dir = setup_python_environment(hulotte_root)
    if venv_dir is None:
        print_error("Python environment setup failed")
        if not ask_yes_no("Continue anyway?", default=False):
            return 1
    
    # Ask about AFF3CT installation
    aff3ct_info = None
    if ask_yes_no("\nDo you want to install AFF3CT (with StreamPU)?", default=True):
        aff3ct_info = install_aff3ct(hulotte_root)
        if aff3ct_info is None:
            print_error("AFF3CT installation failed")
            if not ask_yes_no("Continue anyway?", default=False):
                return 1
    
    # Ask about standalone StreamPU installation
    streampu_info = None
    install_standalone = False
    
    # If AFF3CT was installed with StreamPU, ask if they still want standalone
    if aff3ct_info and 'streampu_root' in aff3ct_info:
        print_info("\nStreamPU was already installed as part of AFF3CT")
        install_standalone = ask_yes_no(
            "Do you still want to install StreamPU standalone?",
            default=False
        )
    else:
        install_standalone = ask_yes_no(
            "\nDo you want to install StreamPU (standalone)?",
            default=True
        )
    
    if install_standalone:
        streampu_info = install_streampu(hulotte_root)
        if streampu_info is None:
            print_error("StreamPU installation failed")

    # Ask about Surfer installation
    surfer_path = None
    if ask_yes_no("\nDo you want to install Surfer (Waveform Viewer)?", default=True):
        surfer_path = install_surfer(hulotte_root)
    
    # Create installation info file
    if aff3ct_info or streampu_info or surfer_path:
        create_install_info(hulotte_root, aff3ct_info, streampu_info, surfer_path)
    
    # Final summary
    print_header("Installation Complete")
    
    if aff3ct_info:
        print_success(f"AFF3CT installed at: {aff3ct_info['aff3ct_root']}")
        if 'streampu_root' in aff3ct_info:
            print_success(f"StreamPU (with AFF3CT) at: {aff3ct_info['streampu_root']}")
    
    if streampu_info:
        print_success(f"StreamPU (standalone) installed at: {streampu_info['streampu_root']}")

    if surfer_path:
        print_success(f"Surfer installed at: {surfer_path}")
    
    print("\n" + "="*60)

    print_info("Next steps:")
    if venv_dir:
        activate_path = venv_dir / "bin" / "activate"
        print(f"  1. Activate the python environment:")
        print(f"     source {to_relative_path(activate_path)}")
    print("  2. Run: python3 create_project.py")
    print("  3. Follow the prompts to create your project")
    print("  4. Use the paths shown above when asked")
    print("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install Hulotte dependencies")
    parser.add_argument("--hoot", action="store_true", help="Enable startup sound")
    args = parser.parse_args()

    try:
        sys.exit(main(hoot=args.hoot))
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

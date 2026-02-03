#!/usr/bin/env python3
"""
Hulotte Dependencies Installer
Interactive script to install AFF3CT and StreamPU dependencies
"""

import os
import sys
import math
import wave
import struct
import shutil
import tempfile
import subprocess
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text):
    """Print a success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_info(text):
    """Print an info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text):
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print an error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_ascii_art():
    """Print hulotte ASCII art if available."""
    try:
        art_path = Path(__file__).resolve().parent / "hulotte.txt"
        if art_path.exists():
            print(art_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def play_wav_file(wav_path):
    """Play a WAV file (best-effort)."""
    if sys.platform.startswith("win"):
        try:
            import winsound
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        except Exception:
            print("\a", end="")
        return
    if sys.platform == "darwin":
        if shutil.which("afplay"):
            subprocess.run(["afplay", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print("\a", end="")
        return

    if shutil.which("paplay"):
        subprocess.run(["paplay", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("aplay"):
        subprocess.run(["aplay", "-q", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif shutil.which("play"):
        subprocess.run(["play", "-q", str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("\a", end="")


def play_owl_hoot():
    """Play a short owl-like hoot sound (best-effort)."""
    try:
        sample_rate = 22050
        preset = os.getenv("HULOTTE_HOOT_PRESET", "classic").strip().lower()
        wav_override = os.getenv("HULOTTE_HOOT_WAV", "").strip()
        local_wav = Path(__file__).resolve().parent / "hulotte.wav"

        if local_wav.exists():
            play_wav_file(local_wav)
            return

        if wav_override:
            wav_path = Path(wav_override).expanduser().resolve()
            if wav_path.exists() and wav_path.suffix.lower() == ".wav":
                play_wav_file(wav_path)
                return

        download_dirs = [Path.home() / "Téléchargements", Path.home() / "Downloads"]
        for dl_dir in download_dirs:
            if dl_dir.exists():
                wav_files = sorted(dl_dir.glob("*.wav"))
                if len(wav_files) == 1:
                    play_wav_file(wav_files[0])
                    return

        def synth_hoot(freq_start, freq_end, duration, vibrato_hz=0.0, vibrato_depth=0.0):
            samples = int(sample_rate * duration)
            data = []
            for i in range(samples):
                t = i / sample_rate
                sweep = freq_start + (freq_end - freq_start) * (t / duration)
                if vibrato_hz > 0.0:
                    sweep += vibrato_depth * math.sin(2 * math.pi * vibrato_hz * t)
                env = math.sin(math.pi * t / duration)
                val = 0.5 * env * math.sin(2 * math.pi * sweep * t)
                data.append(int(max(-1.0, min(1.0, val)) * 32767))
            return data

        if preset == "deep":
            hoot_duration = 0.60
            pause_duration = 0.20
            hoot1 = synth_hoot(300, 240, hoot_duration)
            hoot2 = synth_hoot(280, 220, hoot_duration)
        elif preset == "vibrato":
            hoot_duration = 0.50
            pause_duration = 0.18
            hoot1 = synth_hoot(380, 320, hoot_duration, vibrato_hz=5.0, vibrato_depth=12.0)
            hoot2 = synth_hoot(360, 300, hoot_duration, vibrato_hz=5.0, vibrato_depth=12.0)
        elif preset == "soft":
            hoot_duration = 0.55
            pause_duration = 0.20
            hoot1 = synth_hoot(340, 300, hoot_duration)
            hoot2 = synth_hoot(320, 280, hoot_duration)
        else:
            hoot_duration = 0.45
            pause_duration = 0.15
            hoot1 = synth_hoot(360, 320, hoot_duration)
            hoot2 = synth_hoot(340, 300, hoot_duration)

        pause = [0] * int(sample_rate * pause_duration)
        samples = hoot1 + pause + hoot2

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"".join(struct.pack("<h", s) for s in samples))

        play_wav_file(wav_path)

        try:
            os.remove(wav_path)
        except Exception:
            pass
    except Exception:
        print("\a", end="")


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
    
    aff3ct_dir = hulotte_root / "aff3ct"
    
    # Check if AFF3CT already exists
    if aff3ct_dir.exists():
        print_warning(f"AFF3CT directory already exists: {aff3ct_dir}")
        if not ask_yes_no("Do you want to delete and reinstall?", default=False):
            print_info("Skipping AFF3CT installation")
            return None
        print_info("Removing existing AFF3CT directory...")
        run_command(f"rm -rf {aff3ct_dir}")
    
    # Clone AFF3CT
    print_info("Cloning AFF3CT repository...")
    if not run_command(
        "git clone --recursive https://github.com/aff3ct/aff3ct.git",
        cwd=hulotte_root
    ):
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
    
    streampu_dir = hulotte_root / "streampu"
    
    # Check if StreamPU already exists
    if streampu_dir.exists():
        print_warning(f"StreamPU directory already exists: {streampu_dir}")
        if not ask_yes_no("Do you want to delete and reinstall?", default=False):
            print_info("Skipping StreamPU installation")
            return None
        print_info("Removing existing StreamPU directory...")
        run_command(f"rm -rf {streampu_dir}")
    
    # Clone StreamPU
    print_info("Cloning StreamPU repository...")
    if not run_command(
        "git clone --recursive https://github.com/aff3ct/streampu.git",
        cwd=hulotte_root
    ):
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


def create_install_info(hulotte_root, aff3ct_info, streampu_info):
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
        
        f.write("\nTo create a new project, run:\n")
        f.write("  python3 create_project.py\n")
    
    print_success(f"Installation info saved to: {info_file}")


def main():
    """Main installation script"""
    print_ascii_art()
    play_owl_hoot()
    print_header("Hulotte Dependencies Installer")
    
    # Get Hulotte root (current directory)
    hulotte_root = Path.cwd().resolve()
    print_info(f"Hulotte root: {hulotte_root}")
    
    # Check prerequisites
    print_header("Checking Prerequisites")
    if not check_git():
        return 1
    if not check_cmake():
        return 1
    if not check_compiler():
        return 1
    
    print_success("All prerequisites satisfied")
    
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
    
    # Create installation info file
    if aff3ct_info or streampu_info:
        create_install_info(hulotte_root, aff3ct_info, streampu_info)
    
    # Final summary
    print_header("Installation Complete")
    
    if aff3ct_info:
        print_success(f"AFF3CT installed at: {aff3ct_info['aff3ct_root']}")
        if 'streampu_root' in aff3ct_info:
            print_success(f"StreamPU (with AFF3CT) at: {aff3ct_info['streampu_root']}")
    
    if streampu_info:
        print_success(f"StreamPU (standalone) installed at: {streampu_info['streampu_root']}")
    
    print("\n" + "="*60)
    print_info("Next steps:")
    print("  1. Run: python3 create_project.py")
    print("  2. Follow the prompts to create your project")
    print("  3. Use the paths shown above when asked")
    print("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

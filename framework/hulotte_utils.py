#!/usr/bin/env python3
"""
Shared utilities for Hulotte scripts.
"""

import os
import sys
import math
import wave
import struct
import shutil
import subprocess
import tempfile
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


def to_relative_path(path):
    """Convert absolute path to relative path from current directory."""
    try:
        path_obj = Path(path).resolve()
        cwd = Path.cwd().resolve()
        try:
            rel_path = path_obj.relative_to(cwd)
            return f"./{rel_path}" if str(rel_path) != "." else "."
        except ValueError:
            # Path is not relative to cwd, return as-is
            return str(path)
    except:
        return str(path)


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
    """Play the hulotte.wav sound file."""
    try:
        local_wav = Path(__file__).resolve().parent / "hulotte.wav"

        if local_wav.exists():
            play_wav_file(local_wav)
    except Exception:
        print("\a", end="")

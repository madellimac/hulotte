import os
import json
import subprocess
import threading
import signal
from threading import RLock
from pathlib import Path
from typing import Dict, Any, List, Optional

from create_project import validate_project_manifest_file

# Root directory of the Hulotte framework
HULOTTE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROJECTS_DIR = HULOTTE_ROOT / "projects"

# In-memory store for background processes and logs
class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.logs: Dict[str, List[str]] = {}
        self.statuses: Dict[str, str] = {}  # "idle", "building", "running", "error"
        self.lock = RLock()

    def append_log(self, project_name: str, message: str):
        with self.lock:
            if project_name not in self.logs:
                self.logs[project_name] = []
            self.logs[project_name].append(message)

    def get_logs(self, project_name: str) -> List[str]:
        with self.lock:
            return list(self.logs.get(project_name, []))

    def clear_logs(self, project_name: str):
        with self.lock:
            self.logs[project_name] = []

    def set_status(self, project_name: str, status: str):
        with self.lock:
            self.statuses[project_name] = status

    def get_status(self, project_name: str) -> str:
        with self.lock:
            return self.statuses.get(project_name, "idle")

    def register_process(self, project_name: str, proc: subprocess.Popen):
        with self.lock:
            self.processes[project_name] = proc

    def begin_process(self, project_name: str, status: str) -> bool:
        with self.lock:
            if self.statuses.get(project_name, "idle") in {"building", "running"}:
                return False
            self.statuses[project_name] = status
            return True

    def finish_process(self, project_name: str, proc: subprocess.Popen, status: str) -> bool:
        with self.lock:
            if self.processes.get(project_name) is not proc:
                return False
            del self.processes[project_name]
            self.statuses[project_name] = status
            return True

    def stop_process(self, project_name: str) -> bool:
        with self.lock:
            proc = self.processes.get(project_name)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
            self.finish_process(project_name, proc, "idle")
            self.append_log(project_name, "[GUI] Process stopped by user.\n")
            return True
        return False

process_manager = ProcessManager()


def get_projects_dir() -> Path:
    """Return the base directory where GUI projects are created/located."""
    projects_dir = DEFAULT_PROJECTS_DIR
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir


def list_projects() -> List[Dict[str, Any]]:
    """Scan projects directory and root for hulotte.project.json manifests."""
    projects = []
    search_dirs = [get_projects_dir(), HULOTTE_ROOT / "test_projects"]
    
    seen_names = set()
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for path in base_dir.iterdir():
            if path.is_dir():
                manifest_file = path / "hulotte.project.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            p_name = data.get("project", {}).get("name", path.name)
                            if p_name not in seen_names:
                                seen_names.add(p_name)
                                projects.append({
                                    "name": p_name,
                                    "path": str(path),
                                    "manifest": data,
                                    "status": process_manager.get_status(p_name),
                                    "pipeline_nodes": generate_pipeline_nodes(data)
                                })
                    except Exception:
                        pass
    return projects


def get_project(project_name: str) -> Optional[Dict[str, Any]]:
    """Get project details and manifest by project name."""
    projects = list_projects()
    for p in projects:
        if p["name"] == project_name:
            p["pipeline_nodes"] = generate_pipeline_nodes(p["manifest"])
            return p
    return None


def validate_project(project_name: str) -> Dict[str, Any]:
    """Validate a project's manifest and generated files without changing them."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found")

    manifest_path = Path(project["path"]) / "hulotte.project.json"
    errors, manifest_file = validate_project_manifest_file(manifest_path)
    if errors:
        process_manager.set_status(project_name, "error")
        process_manager.append_log(
            project_name,
            "[GUI] Project validation failed:\n" + "\n".join(f"- {error}" for error in errors) + "\n",
        )
        return {"valid": False, "manifest": str(manifest_file), "errors": errors}

    process_manager.set_status(project_name, "idle")
    process_manager.append_log(project_name, f"[GUI] Project '{project_name}' validated successfully.\n")
    return {"valid": True, "manifest": str(manifest_file), "errors": []}


def open_project_file(project_name: str, file_path: str) -> Dict[str, str]:
    """Open a declared project file with the user's default desktop editor."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found")
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("A file path is required")

    project_root = Path(project["path"]).resolve()
    requested_path = Path(file_path)
    resolved_path = (project_root / requested_path).resolve() if not requested_path.is_absolute() else requested_path.resolve()
    try:
        resolved_path.relative_to(project_root)
    except ValueError as error:
        raise PermissionError("The requested file is outside the project directory") from error

    declared_paths = set()
    for node in project.get("pipeline_nodes", []):
        for field in ("source", "header", "wrapper_source", "core_source"):
            declared_path = node.get(field)
            if isinstance(declared_path, str) and declared_path.strip():
                candidate = Path(declared_path)
                declared_paths.add(
                    (project_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
                )
    if resolved_path not in declared_paths:
        raise PermissionError("The requested file is not declared by a project module")

    if not resolved_path.is_file():
        raise FileNotFoundError(f"File not found: {resolved_path}")

    try:
        subprocess.Popen(
            ["xdg-open", str(resolved_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        raise RuntimeError(f"Unable to open file with the default editor: {error}") from error

    process_manager.append_log(project_name, f"[GUI] Opened file in default editor: {resolved_path}\n")
    return {"path": str(resolved_path)}


def generate_pipeline_nodes(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build a simplified pipeline node list from hulotte.project.json.
    Each node carries the manifest fields already available (id, enabled, source paths, ...)
    so the GUI can display module details on click without a second config representation.
    Uses real module entries from custom_modules/hardware_modules when present
    (as written by add_custom_module.py / add_hardware_module.py / add_uart_hw_module.py),
    falling back to a generic placeholder when a feature is enabled but no module entry exists yet.
    """
    features = manifest.get("features", {})

    nodes: List[Dict[str, Any]] = [{"name": "Source_random", "type": "source"}]

    if features.get("uart_io"):
        nodes.append({"name": "UartFrameIO", "type": "uart"})

    if features.get("hardware"):
        hardware_modules = [m for m in (manifest.get("hardware_modules") or []) if m.get("enabled", True)]
        if hardware_modules:
            for m in hardware_modules:
                nodes.append({
                    "name": m.get("module_name") or m.get("id"),
                    "type": "hardware",
                    **m,
                })
        else:
            nodes.append({"name": "VerilatorSimulation (PassThrough)", "type": "hardware", "generic": True})

    if features.get("custom"):
        custom_modules = [m for m in (manifest.get("custom_modules") or []) if m.get("enabled", True)]
        if custom_modules:
            for m in custom_modules:
                nodes.append({
                    "name": m.get("class_name") or m.get("id"),
                    "type": "custom",
                    **m,
                })
        else:
            nodes.append({"name": "MyModule (Custom)", "type": "custom", "generic": True})

    if features.get("aff3ct"):
        nodes.append({"name": "Encoder_RS", "type": "aff3ct"})
        nodes.append({"name": "Decoder_RS_std", "type": "aff3ct"})

    nodes.append({"name": "Comparator", "type": "comparator"})
    return nodes


def create_project(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call create_project.py to create a new project.
    """
    project_name = data.get("name")
    if not project_name:
        raise ValueError("Project name is required")

    projects_dir = get_projects_dir()
    streampu_root = data.get("streampu_root") or str(HULOTTE_ROOT / "streampu")
    aff3ct_root = data.get("aff3ct_root") or str(HULOTTE_ROOT / "aff3ct")

    cmd = [
        "python3",
        str(HULOTTE_ROOT / "create_project.py"),
        "--name", project_name,
        "--output-dir", str(projects_dir),
        "--streampu-root", str(streampu_root),
        "--aff3ct-root", str(aff3ct_root),
    ]

    # Feature flags
    cmd.append("--aff3ct" if data.get("use_aff3ct") else "--no-aff3ct")
    cmd.append("--custom" if data.get("use_custom", True) else "--no-custom")
    cmd.append("--hw" if data.get("use_hw") else "--no-hw")
    cmd.append("--uart-io" if data.get("use_uart_io") else "--no-uart-io")

    if data.get("uart_port"):
        cmd.extend(["--uart-port", str(data.get("uart_port"))])
    if data.get("uart_baud"):
        cmd.extend(["--uart-baud", str(data.get("uart_baud"))])
    if data.get("uart_frame_size"):
        cmd.extend(["--uart-frame-size", str(data.get("uart_frame_size"))])

    process_manager.clear_logs(project_name)
    process_manager.append_log(project_name, f"[GUI] Creating project with command: {' '.join(cmd)}\n")

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    process_manager.append_log(project_name, res.stdout)

    if res.returncode != 0:
        process_manager.set_status(project_name, "error")
        raise RuntimeError(f"create_project.py failed with return code {res.returncode}")

    process_manager.set_status(project_name, "idle")
    project = get_project(project_name)
    if not project:
        raise RuntimeError("Project created but manifest not found")
    return project


def build_project_async(project_name: str):
    """Run build.sh in a background thread."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found")

    project_path = Path(project["path"])
    build_script = project_path / "build.sh"
    if not build_script.exists():
        raise FileNotFoundError(f"build.sh not found in {project_path}")
    if not process_manager.begin_process(project_name, "building"):
        raise RuntimeError(f"Project '{project_name}' already has an active operation")

    def run_build():
        process_manager.append_log(project_name, f"[GUI] Starting build for {project_name}...\n")
        
        proc = subprocess.Popen(
            ["./build.sh"],
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        process_manager.register_process(project_name, proc)

        for line in proc.stdout:
            process_manager.append_log(project_name, line)

        proc.wait()
        final_status = "idle" if proc.returncode == 0 else "error"
        if process_manager.finish_process(project_name, proc, final_status):
            if proc.returncode == 0:
                process_manager.append_log(project_name, "[GUI] Build successful!\n")
            else:
                process_manager.append_log(project_name, f"[GUI] Build failed with code {proc.returncode}\n")

    thread = threading.Thread(target=run_build, daemon=True)
    thread.start()


def run_project_async(project_name: str):
    """Run the built executable in a background thread."""
    project = get_project(project_name)
    if not project:
        raise ValueError(f"Project '{project_name}' not found")

    project_path = Path(project["path"])
    binary_path = project_path / "build" / project_name
    if not binary_path.exists():
        raise FileNotFoundError(f"Binary not found at {binary_path}. Please build the project first.")
    if not process_manager.begin_process(project_name, "running"):
        raise RuntimeError(f"Project '{project_name}' already has an active operation")

    def run_executable():
        process_manager.append_log(project_name, f"[GUI] Running {project_name}...\n")

        proc = subprocess.Popen(
            [str(binary_path)],
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        process_manager.register_process(project_name, proc)

        for line in proc.stdout:
            process_manager.append_log(project_name, line)

        proc.wait()
        final_status = "idle" if proc.returncode == 0 else "error"
        if process_manager.finish_process(project_name, proc, final_status):
            if proc.returncode == 0:
                process_manager.append_log(project_name, "[GUI] Execution finished successfully.\n")
            else:
                process_manager.append_log(project_name, f"[GUI] Execution stopped with code {proc.returncode}\n")

    thread = threading.Thread(target=run_executable, daemon=True)
    thread.start()

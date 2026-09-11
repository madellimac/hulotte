from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from . import services

router = APIRouter(prefix="/api")

class CreateProjectRequest(BaseModel):
    name: str = Field(..., description="Project name")
    use_streampu: bool = True
    use_aff3ct: bool = False
    use_custom: bool = True
    use_hw: bool = False
    use_uart_io: bool = False
    uart_port: Optional[str] = "/dev/ttyUSB0"
    uart_baud: Optional[int] = 115200
    uart_frame_size: Optional[int] = 16
    streampu_root: Optional[str] = None
    aff3ct_root: Optional[str] = None

@router.get("/projects", response_model=List[Dict[str, Any]])
def get_projects():
    """List all available Hulotte projects."""
    return services.list_projects()

@router.post("/projects")
def create_project(req: CreateProjectRequest):
    """Create a new Hulotte project."""
    try:
        project = services.create_project(req.model_dump())
        return {"status": "success", "project": project}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/projects/{name}")
def get_project(name: str):
    """Get project details."""
    project = services.get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    return project

@router.post("/projects/{name}/generate")
def generate_project(name: str):
    """Re-generate project or validate manifest."""
    project = services.get_project(name)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")
    # In V1, create_project already generated all files and hulotte.project.json.
    services.process_manager.append_log(name, f"[GUI] Project '{name}' files verified and manifest loaded.\n")
    return {"status": "success", "message": f"Project '{name}' generated/verified"}

@router.post("/projects/{name}/build")
def build_project(name: str):
    """Trigger build.sh for the specified project."""
    try:
        services.build_project_async(name)
        return {"status": "building", "message": f"Build started for '{name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/projects/{name}/run")
def run_project(name: str):
    """Execute the built project binary."""
    try:
        services.run_project_async(name)
        return {"status": "running", "message": f"Execution started for '{name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/projects/{name}/stop")
def stop_project(name: str):
    """Stop running process for the project."""
    stopped = services.process_manager.stop_process(name)
    return {"status": "stopped" if stopped else "idle", "message": f"Process for '{name}' stopped"}

@router.get("/projects/{name}/status")
def get_project_status(name: str):
    """Get current status of project (idle, building, running, error)."""
    return {
        "name": name,
        "status": services.process_manager.get_status(name)
    }

@router.get("/projects/{name}/logs")
def get_project_logs(name: str):
    """Retrieve output logs for the project."""
    return {
        "name": name,
        "logs": services.process_manager.get_logs(name)
    }

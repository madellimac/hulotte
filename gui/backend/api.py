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


class OpenProjectFileRequest(BaseModel):
    path: str = Field(..., min_length=1)

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
    """Validate the project manifest and generated files without modifying them."""
    try:
        result = services.validate_project(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not result["valid"]:
        raise HTTPException(status_code=422, detail=result)
    return {"status": "success", "message": f"Project '{name}' validated", **result}


@router.post("/projects/{name}/open-file")
def open_project_file(name: str, req: OpenProjectFileRequest):
    """Open a project file using the local system's default editor."""
    try:
        result = services.open_project_file(name, req.path)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))
    return {"status": "opened", **result}

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

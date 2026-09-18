"""Static validation for Hulotte pipeline graphs."""

from dataclasses import dataclass
from .pipeline import Connection, ModuleSpec, Pipeline

ALLOWED_KINDS = {"streampu", "aff3ct", "custom", "verilator", "transport"}
CAPABILITY_BY_KIND = {
    "streampu": "streampu",
    "aff3ct": "aff3ct",
    "custom": "custom",
    "verilator": "verilator",
    "transport": "transport",
}


@dataclass(frozen=True)
class PipelineValidationError(ValueError):
    """Raised when a pipeline is structurally or semantically invalid."""

    errors: tuple[str, ...]

    def __str__(self) -> str:
        return "\n".join(self.errors)


def _socket_map(module: ModuleSpec, task: str, direction: str) -> dict:
    tasks = module.sockets
    if not isinstance(tasks, dict):
        return {}
    task_spec = tasks.get(task, {})
    if not isinstance(task_spec, dict):
        return {}
    sockets = task_spec.get(direction, {})
    return sockets if isinstance(sockets, dict) else {}


def _endpoint(endpoint: str) -> tuple[str, str, str] | None:
    parts = endpoint.split(".") if isinstance(endpoint, str) else []
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def _validate_endpoint(
    endpoint: str,
    modules: dict[str, ModuleSpec],
    direction: str,
    errors: list[str],
) -> tuple[str, str, str] | None:
    parsed = _endpoint(endpoint)
    if parsed is None:
        errors.append(f"invalid {direction} endpoint '{endpoint}'; expected module.task.socket")
        return None

    module_id, task, socket = parsed
    module = modules.get(module_id)
    if module is None:
        errors.append(f"{direction} endpoint '{endpoint}' references unknown module '{module_id}'")
        return parsed
    socket_direction = f"{direction}s"
    if socket not in _socket_map(module, task, socket_direction):
        errors.append(f"{direction} endpoint '{endpoint}' references an unknown socket")
    return parsed


def validate_pipeline(
    pipeline: Pipeline,
    capabilities: dict[str, bool] | None = None,
    require_source: bool = False,
) -> None:
    """Validate a pipeline or raise one error containing all detected issues."""
    errors: list[str] = []
    modules = pipeline.modules

    if not modules:
        errors.append("pipeline must contain at least one module")

    for module_id, module in modules.items():
        if not module_id:
            errors.append("module id must not be empty")
        if module.kind not in ALLOWED_KINDS:
            errors.append(f"module '{module_id}' has unsupported type '{module.kind}'")
        if not isinstance(module.parameters, dict):
            errors.append(f"module '{module_id}' parameters must be a mapping")
        if not isinstance(module.sockets, dict):
            errors.append(f"module '{module_id}' sockets must be a mapping")
        if capabilities is not None:
            capability = CAPABILITY_BY_KIND.get(module.kind)
            if capability and not capabilities.get(capability, False):
                errors.append(
                    f"module '{module_id}' requires disabled capability '{capability}'"
                )

    for resource_id, resource in pipeline.resources.items():
        if not resource_id:
            errors.append("resource id must not be empty")
        if not isinstance(resource.parameters, dict):
            errors.append(f"resource '{resource_id}' parameters must be a mapping")

    connected_inputs: set[str] = set()
    for connection in pipeline.connections:
        source = _validate_endpoint(connection.source, modules, "output", errors)
        target = _validate_endpoint(connection.target, modules, "input", errors)
        if target is not None:
            target_key = ".".join(target)
            if target_key in connected_inputs:
                errors.append(f"input socket '{target_key}' is connected more than once")
            connected_inputs.add(target_key)
        if source is not None and target is not None:
            source_spec = _socket_spec(modules[source[0]], source[1], "outputs", source[2])
            target_spec = _socket_spec(modules[target[0]], target[1], "inputs", target[2])
            _validate_compatibility(source_spec, target_spec, connection, errors)

    if require_source and not any(module.kind == "streampu" for module in modules.values()):
        errors.append("pipeline must contain a StreamPU source module")

    if errors:
        raise PipelineValidationError(tuple(errors))


def _socket_spec(module: ModuleSpec, task: str, direction: str, socket: str) -> dict:
    sockets = _socket_map(module, task, direction)
    spec = sockets.get(socket, {})
    return spec if isinstance(spec, dict) else {}


def _validate_compatibility(
    source: dict, target: dict, connection: Connection, errors: list[str]
) -> None:
    source_type = source.get("type")
    target_type = target.get("type")
    if source_type and target_type and source_type != target_type:
        errors.append(
            f"incompatible socket types for '{connection.source}' -> '{connection.target}': "
            f"'{source_type}' != '{target_type}'"
        )

    source_size = source.get("frame_size")
    target_size = target.get("frame_size")
    if source_size is not None and target_size is not None and source_size != target_size:
        errors.append(
            f"incompatible frame sizes for '{connection.source}' -> '{connection.target}': "
            f"{source_size} != {target_size}"
        )

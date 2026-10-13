"""Pipeline graph model and YAML loading."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModuleSpec:
    """A node in a StreamPU pipeline graph."""

    module_id: str
    kind: str
    catalog: str | None = None
    class_name: str | None = None
    source: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    sockets: dict[str, Any] = field(default_factory=dict)
    ports: dict[str, Any] = field(default_factory=dict)

    def ui_block(self) -> dict[str, Any]:
        """Return a GUI-friendly summary of a pipeline block."""
        return {
            "id": self.module_id,
            "kind": self.kind,
            "catalog": self.catalog,
            "class": self.class_name,
            "label": self.module_id,
            "parameters": self.parameters,
            "ports": self.ports or _ports_from_sockets(self.sockets),
        }


@dataclass(frozen=True)
class ResourceSpec:
    """A shared C++ object used by one or more pipeline modules."""

    resource_id: str
    kind: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Connection:
    """A directed connection between two task sockets."""

    source: str
    target: str


@dataclass(frozen=True)
class CanvasPort:
    """A block port exposed to the GUI canvas."""

    name: str
    direction: str
    type: str
    frame_size: int | None = None


@dataclass
class CanvasBlock:
    """A GUI block instance with typed ports."""

    block_id: str
    kind: str
    catalog: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    x: int = 0
    y: int = 0
    task: str | None = None
    inputs: tuple[CanvasPort, ...] = ()
    outputs: tuple[CanvasPort, ...] = ()

    def port_map(self) -> dict[str, tuple[CanvasPort, ...]]:
        return {"inputs": self.inputs, "outputs": self.outputs}

    def to_module_dict(self) -> dict[str, Any]:
        """Serialize this block to the declarative pipeline module format."""
        task_name = self.task or "main"
        module: dict[str, Any] = {"type": self.kind, "sockets": {}}
        if self.catalog:
            module["catalog"] = self.catalog
        if self.parameters:
            module["parameters"] = dict(self.parameters)
        if self.inputs:
            module["sockets"][task_name] = {"inputs": {}}
        if self.outputs:
            module["sockets"].setdefault(task_name, {})["outputs"] = {}

        for port in self.inputs:
            module["sockets"][task_name]["inputs"][port.name] = {
                "type": port.type,
                **({"frame_size": port.frame_size} if port.frame_size is not None else {}),
            }
        for port in self.outputs:
            module["sockets"][task_name]["outputs"][port.name] = {
                "type": port.type,
                **({"frame_size": port.frame_size} if port.frame_size is not None else {}),
            }
        return module


@dataclass(frozen=True)
class CanvasConnection:
    """A connection between ports on two canvas blocks."""

    source_block: str
    source_port: str
    target_block: str
    target_port: str
    source_task: str | None = None
    target_task: str | None = None


class BlockCanvasValidationError(ValueError):
    """Raised when a block connection is invalid."""


@dataclass
class BlockCanvas:
    """A GUI-oriented view of a pipeline graph."""

    blocks: dict[str, CanvasBlock]
    connections: tuple[CanvasConnection, ...] = ()
    resources: dict[str, Any] = field(default_factory=dict)

    def add_block(self, block: CanvasBlock) -> None:
        """Insert a block into the canvas."""
        self.blocks[block.block_id] = block

    def remove_block(self, block_id: str) -> None:
        """Remove a block and any connections pointing to or from it."""
        self.blocks.pop(block_id, None)
        remaining = []
        for connection in self._normalized_connections():
            if connection.source_block == block_id or connection.target_block == block_id:
                continue
            remaining.append(connection)
        self.connections = tuple(remaining)

    def connect(self, connection: CanvasConnection) -> None:
        """Create a valid connection between blocks and keep the model consistent."""
        self.validate_connection(connection)
        existing = list(self._normalized_connections())
        if connection not in existing:
            existing.append(connection)
        self.connections = tuple(existing)

    def disconnect(self, connection: CanvasConnection) -> None:
        """Remove a connection from the canvas."""
        remaining = [item for item in self._normalized_connections() if item != connection]
        self.connections = tuple(remaining)

    def validate_connection(self, connection: CanvasConnection) -> None:
        """Validate that a block-to-block connection is structurally and type-compatible."""
        source_block = self.blocks.get(connection.source_block)
        target_block = self.blocks.get(connection.target_block)
        if source_block is None:
            raise BlockCanvasValidationError(
                f"source block '{connection.source_block}' does not exist in the canvas"
            )
        if target_block is None:
            raise BlockCanvasValidationError(
                f"target block '{connection.target_block}' does not exist in the canvas"
            )

        source_port = _find_canvas_port(source_block.outputs, connection.source_port)
        target_port = _find_canvas_port(target_block.inputs, connection.target_port)
        if source_port is None:
            raise BlockCanvasValidationError(
                f"source block '{connection.source_block}' has no output port '{connection.source_port}'"
            )
        if target_port is None:
            raise BlockCanvasValidationError(
                f"target block '{connection.target_block}' has no input port '{connection.target_port}'"
            )

        if source_port.type != target_port.type:
            raise BlockCanvasValidationError(
                f"incompatible port types for '{connection.source_block}.{connection.source_port}' -> "
                f"'{connection.target_block}.{connection.target_port}': '{source_port.type}' != '{target_port.type}'"
            )

        if (
            source_port.frame_size is not None
            and target_port.frame_size is not None
            and source_port.frame_size != target_port.frame_size
        ):
            raise BlockCanvasValidationError(
                f"incompatible frame sizes for '{connection.source_block}.{connection.source_port}' -> "
                f"'{connection.target_block}.{connection.target_port}': {source_port.frame_size} != {target_port.frame_size}"
            )

    def _normalized_connections(self) -> tuple[CanvasConnection, ...]:
        if isinstance(self.connections, CanvasConnection):
            return (self.connections,)
        return tuple(self.connections)

    def serialize(self) -> dict[str, Any]:
        """Serialize the canvas into the declarative pipeline format used by the generator."""
        modules: dict[str, Any] = {}
        for block_id, block in self.blocks.items():
            module = block.to_module_dict()
            modules[block_id] = module

        connections: list[dict[str, str]] = []
        for connection in self._normalized_connections():
            self.validate_connection(connection)
            source_task = connection.source_task or "main"
            target_task = connection.target_task or "main"
            connections.append(
                {
                    "from": f"{connection.source_block}.{source_task}.{connection.source_port}",
                    "to": f"{connection.target_block}.{target_task}.{connection.target_port}",
                }
            )

        payload: dict[str, Any] = {"modules": modules, "connections": connections}
        if self.resources:
            payload["resources"] = dict(self.resources)
        return payload

    def to_pipeline(self) -> dict[str, Any]:
        """Backward-compatible alias for serializing the canvas to pipeline data."""
        return self.serialize()

    @classmethod
    def from_pipeline(cls, payload: dict[str, Any]) -> "BlockCanvas":
        """Rebuild a canvas from a declarative pipeline payload."""
        blocks: dict[str, CanvasBlock] = {}
        for block_id, module in payload.get("modules", {}).items():
            inputs: list[CanvasPort] = []
            outputs: list[CanvasPort] = []
            sockets = module.get("sockets", {})
            for task_name, task in sockets.items():
                if not isinstance(task, dict):
                    continue
                for direction, ports in (("inputs", task.get("inputs", {})), ("outputs", task.get("outputs", {}))):
                    if not isinstance(ports, dict):
                        continue
                    for port_name, port_spec in ports.items():
                        if not isinstance(port_spec, dict):
                            continue
                        port = CanvasPort(
                            name=port_name,
                            direction=direction[:-1] if direction.endswith("s") else direction,
                            type=str(port_spec.get("type", "unknown")),
                            frame_size=port_spec.get("frame_size"),
                        )
                        if direction == "inputs":
                            inputs.append(port)
                        else:
                            outputs.append(port)
            blocks[block_id] = CanvasBlock(
                block_id=block_id,
                kind=module.get("type", "unknown"),
                catalog=module.get("catalog"),
                parameters=module.get("parameters", {}),
                task=next(iter(sockets), None),
                inputs=tuple(inputs),
                outputs=tuple(outputs),
            )

        connections: list[CanvasConnection] = []
        for connection in payload.get("connections", []):
            if not isinstance(connection, dict):
                continue
            source = str(connection.get("from", "")).split(".")
            target = str(connection.get("to", "")).split(".")
            if len(source) >= 3 and len(target) >= 3:
                connections.append(
                    CanvasConnection(
                        source_block=source[0],
                        source_port=source[2],
                        target_block=target[0],
                        target_port=target[2],
                        source_task=source[1],
                        target_task=target[1],
                    )
                )

        return cls(
            blocks=blocks,
            connections=tuple(connections),
            resources=payload.get("resources", {}),
        )


class PipelineCycleError(ValueError):
    """Raised when the module graph contains a directed cycle."""


@dataclass(frozen=True)
class Pipeline:
    """A user-declared StreamPU pipeline."""

    modules: dict[str, ModuleSpec]
    connections: tuple[Connection, ...]
    resources: dict[str, ResourceSpec] = field(default_factory=dict)

    def topological_order(self) -> tuple[str, ...]:
        """Return a stable module order derived from graph connections."""
        adjacency = {module_id: [] for module_id in self.modules}
        indegree = {module_id: 0 for module_id in self.modules}

        for connection in self.connections:
            source = _endpoint_module(connection.source)
            target = _endpoint_module(connection.target)
            if source not in self.modules or target not in self.modules:
                continue
            if target not in adjacency[source]:
                adjacency[source].append(target)
                indegree[target] += 1

        ready = [module_id for module_id in self.modules if indegree[module_id] == 0]
        order: list[str] = []
        while ready:
            module_id = ready.pop(0)
            order.append(module_id)
            for descendant in adjacency[module_id]:
                indegree[descendant] -= 1
                if indegree[descendant] == 0:
                    ready.append(descendant)

        if len(order) != len(self.modules):
            cyclic = [module_id for module_id in self.modules if indegree[module_id] > 0]
            raise PipelineCycleError(
                "pipeline contains a cycle involving: " + ", ".join(cyclic)
            )
        return tuple(order)

    def source_modules(self) -> tuple[str, ...]:
        """Return modules with no incoming graph connection, in stable order."""
        targets = {
            target
            for connection in self.connections
            for target in [_endpoint_module(connection.target)]
            if target in self.modules
        }
        return tuple(module_id for module_id in self.topological_order() if module_id not in targets)

    def ui_graph(self) -> dict[str, Any]:
        """Return a GUI-friendly graph description without changing the core model."""
        ordered_module_ids = self.topological_order()
        blocks = [self.modules[module_id].ui_block() for module_id in ordered_module_ids]
        connections = [
            {"from": connection.source, "to": connection.target}
            for connection in self.connections
        ]
        return {"blocks": blocks, "connections": connections}


def parse_pipeline(data: Any) -> Pipeline:
    """Parse the unvalidated YAML object into the pipeline model."""
    if not isinstance(data, dict):
        raise ValueError("pipeline root must be a mapping")

    raw_modules = data.get("modules", {})
    raw_connections = data.get("connections", [])
    raw_resources = data.get("resources", {})
    if not isinstance(raw_modules, dict):
        raise ValueError("pipeline.modules must be a mapping")
    if not isinstance(raw_connections, list):
        raise ValueError("pipeline.connections must be a list")
    if not isinstance(raw_resources, dict):
        raise ValueError("pipeline.resources must be a mapping")

    resources: dict[str, ResourceSpec] = {}
    for resource_id, raw_resource in raw_resources.items():
        if not isinstance(resource_id, str) or not isinstance(raw_resource, dict):
            raise ValueError("each resource must have a string id and mapping value")
        resources[resource_id] = ResourceSpec(
            resource_id=resource_id,
            kind=raw_resource.get("type", ""),
            parameters=raw_resource.get("parameters", {}),
        )

    modules: dict[str, ModuleSpec] = {}
    for module_id, raw_module in raw_modules.items():
        if not isinstance(module_id, str) or not isinstance(raw_module, dict):
            raise ValueError("each module must have a string id and mapping value")
        modules[module_id] = ModuleSpec(
            module_id=module_id,
            kind=raw_module.get("type", ""),
            catalog=raw_module.get("catalog"),
            class_name=raw_module.get("class"),
            source=raw_module.get("source"),
            parameters=raw_module.get("parameters", {}),
            sockets=raw_module.get("sockets", {}),
            ports=raw_module.get("ports", {}),
        )

    connections: list[Connection] = []
    for connection in raw_connections:
        if not isinstance(connection, dict):
            raise ValueError("each connection must be a mapping")
        connections.append(
            Connection(
                source=connection.get("from", ""),
                target=connection.get("to", ""),
            )
        )

    return Pipeline(modules=modules, connections=tuple(connections), resources=resources)


def load_pipeline(path: str | Path) -> Pipeline:
    """Load a YAML pipeline file."""
    with Path(path).open("r", encoding="utf-8") as file_desc:
        return parse_pipeline(yaml.safe_load(file_desc))


def _endpoint_module(endpoint: str) -> str:
    parts = endpoint.split(".") if isinstance(endpoint, str) else []
    return parts[0] if len(parts) == 3 and parts[0] else ""


def _find_canvas_port(ports: tuple[CanvasPort, ...], port_name: str) -> CanvasPort | None:
    for port in ports:
        if port.name == port_name:
            return port
    return None


def _ports_from_sockets(sockets: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Derive a GUI-friendly port map from the existing socket declarations."""
    ports: dict[str, list[dict[str, Any]]] = {"inputs": [], "outputs": []}
    if not isinstance(sockets, dict):
        return ports

    for task_name, task_spec in sockets.items():
        if not isinstance(task_spec, dict):
            continue
        for direction in ("inputs", "outputs"):
            direction_spec = task_spec.get(direction, {})
            if not isinstance(direction_spec, dict):
                continue
            for socket_name, socket_spec in direction_spec.items():
                if not isinstance(socket_spec, dict):
                    continue
                ports[direction].append(
                    {
                        "name": socket_name,
                        "task": task_name,
                        "type": socket_spec.get("type"),
                        "frame_size": socket_spec.get("frame_size"),
                    }
                )
    return ports

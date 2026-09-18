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

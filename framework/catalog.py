"""Versioned module catalog used by the pipeline generator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CatalogError(ValueError):
    """Raised when a module catalog is invalid or cannot resolve a module."""


@dataclass(frozen=True)
class CatalogModule:
    """Generation metadata for one known StreamPU-compatible module."""

    catalog_id: str
    kind: str
    class_name: str
    include: str
    constructor: tuple[dict[str, Any], ...]
    sockets: dict[str, Any]


@dataclass(frozen=True)
class CatalogResource:
    """Generation metadata for a shared C++ resource."""

    catalog_id: str
    class_name: str
    include: str
    constructor: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ModuleCatalog:
    """Indexed collection of module generation metadata."""

    version: int
    modules: dict[str, CatalogModule]
    resources: dict[str, CatalogResource]

    def resolve(self, catalog_id: str) -> CatalogModule:
        try:
            return self.modules[catalog_id]
        except KeyError as error:
            raise CatalogError(f"unknown catalog module '{catalog_id}'") from error

    def resolve_resource(self, catalog_id: str) -> CatalogResource:
        try:
            return self.resources[catalog_id]
        except KeyError as error:
            raise CatalogError(f"unknown catalog resource '{catalog_id}'") from error


def load_catalog(path: str | Path) -> ModuleCatalog:
    """Load and structurally validate a YAML module catalog."""
    with Path(path).open("r", encoding="utf-8") as file_desc:
        data = yaml.safe_load(file_desc)

    if not isinstance(data, dict) or not isinstance(data.get("modules"), dict):
        raise CatalogError("catalog must contain a 'modules' mapping")
    version = data.get("version")
    if not isinstance(version, int):
        raise CatalogError("catalog version must be an integer")

    modules: dict[str, CatalogModule] = {}
    raw_resources = data.get("resources", {})
    if not isinstance(raw_resources, dict):
        raise CatalogError("catalog resources must be a mapping")
    resources: dict[str, CatalogResource] = {}
    for catalog_id, raw_resource in raw_resources.items():
        if not isinstance(catalog_id, str) or not isinstance(raw_resource, dict):
            raise CatalogError("each catalog resource must have a string id and mapping value")
        required = ("class", "include", "constructor")
        missing = [key for key in required if not raw_resource.get(key)]
        if missing:
            raise CatalogError(
                f"catalog resource '{catalog_id}' is missing: {', '.join(missing)}"
            )
        constructor = raw_resource["constructor"]
        if not isinstance(constructor, list) or not all(isinstance(arg, dict) for arg in constructor):
            raise CatalogError(f"catalog resource '{catalog_id}' constructor must be a list")
        resources[catalog_id] = CatalogResource(
            catalog_id=catalog_id,
            class_name=raw_resource["class"],
            include=raw_resource["include"],
            constructor=tuple(constructor),
        )
    for catalog_id, raw_module in data["modules"].items():
        if not isinstance(catalog_id, str) or not isinstance(raw_module, dict):
            raise CatalogError("each catalog module must have a string id and mapping value")
        required = ("type", "class", "include", "sockets")
        missing = [key for key in required if not raw_module.get(key)]
        if missing:
            raise CatalogError(
                f"catalog module '{catalog_id}' is missing: {', '.join(missing)}"
            )
        constructor = raw_module.get("constructor", [])
        if not isinstance(constructor, list) or not all(
            isinstance(argument, dict) for argument in constructor
        ):
            raise CatalogError(f"catalog module '{catalog_id}' constructor must be a list")
        sockets = raw_module["sockets"]
        if not isinstance(sockets, dict):
            raise CatalogError(f"catalog module '{catalog_id}' sockets must be a mapping")
        modules[catalog_id] = CatalogModule(
            catalog_id=catalog_id,
            kind=raw_module["type"],
            class_name=raw_module["class"],
            include=raw_module["include"],
            constructor=tuple(constructor),
            sockets=sockets,
        )

    return ModuleCatalog(version=version, modules=modules, resources=resources)

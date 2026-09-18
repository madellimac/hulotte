"""Core domain model for Hulotte pipeline projects."""

from .pipeline import Connection, ModuleSpec, Pipeline, PipelineCycleError, ResourceSpec, load_pipeline
from .validation import PipelineValidationError, validate_pipeline
from .catalog import CatalogError, CatalogModule, CatalogResource, ModuleCatalog, load_catalog
from .generator import GenerationError, generate_cpp, write_cpp
from .project import ProjectGenerationError, build_project, generate_project, init_project
from .paths import PathResolutionError, resolve_catalog, resolve_hulotte_root

__all__ = [
    "Connection",
    "CatalogError",
    "CatalogModule",
    "CatalogResource",
    "GenerationError",
    "ModuleSpec",
    "ModuleCatalog",
    "Pipeline",
    "PipelineCycleError",
    "PipelineValidationError",
    "ProjectGenerationError",
    "PathResolutionError",
    "ResourceSpec",
    "generate_cpp",
    "build_project",
    "generate_project",
    "init_project",
    "load_catalog",
    "load_pipeline",
    "resolve_catalog",
    "resolve_hulotte_root",
    "validate_pipeline",
    "write_cpp",
]

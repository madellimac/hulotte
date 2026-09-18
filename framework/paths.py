"""Resolve Hulotte installation and project resource paths."""

import os
from pathlib import Path


class PathResolutionError(ValueError):
    """Raised when an installation resource cannot be found."""


def resolve_hulotte_root(explicit: str | Path | None = None) -> Path:
    """Resolve the Hulotte installation without depending on the cwd."""
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env_root = os.environ.get("HULOTTE_HOME")
    if env_root:
        candidates.append(Path(env_root))

    # During source-tree development, the framework package may sit either at the
    # repo root or one directory below it.
    framework_dir = Path(__file__).resolve().parent
    repo_root = framework_dir.parent
    candidates.extend([framework_dir, repo_root])

    for candidate in candidates:
        root = candidate.resolve()
        if (root / "catalog" / "modules.yaml").is_file() or (root / "modules.yaml").is_file():
            return root
        framework_root = root / "framework"
        if (framework_root / "catalog" / "modules.yaml").is_file() or (
            framework_root / "modules.yaml"
        ).is_file():
            return framework_root
    searched = ", ".join(str(path.resolve()) for path in candidates)
    raise PathResolutionError(f"Hulotte installation not found; searched: {searched}")


def resolve_catalog(
    project_root: str | Path,
    explicit: str | Path | None = None,
    hulotte_root: str | Path | None = None,
) -> Path:
    """Resolve a project-local catalog or the installed official catalog."""
    root = Path(project_root).resolve()
    if explicit is not None:
        catalog = Path(explicit)
        if not catalog.is_absolute():
            catalog = root / catalog
        catalog = catalog.resolve()
        if catalog.is_file():
            return catalog
        raise PathResolutionError(f"catalog file not found: {catalog}")

    local_catalog = root / "catalog" / "modules.yaml"
    if local_catalog.is_file():
        return local_catalog

    hulotte_root_resolved = resolve_hulotte_root(hulotte_root)
    installed_candidates = [
        hulotte_root_resolved / "catalog" / "modules.yaml",
        hulotte_root_resolved / "modules.yaml",
        hulotte_root_resolved / "framework" / "catalog" / "modules.yaml",
        hulotte_root_resolved / "framework" / "modules.yaml",
    ]
    for installed_catalog in installed_candidates:
        if installed_catalog.is_file():
            return installed_catalog
    raise PathResolutionError(
        f"catalog file not found in Hulotte root: {hulotte_root_resolved}"
    )

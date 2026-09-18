"""User configuration and dependency resolution for Hulotte."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigurationError(ValueError):
    """Raised when Hulotte configuration is missing or invalid."""


def config_path() -> Path:
    """Return the user configuration path following the XDG convention."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return base / "hulotte" / "config.yaml"


def load_user_config() -> dict[str, Any]:
    """Load the user configuration, returning an empty mapping when absent."""
    path = config_path()
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file_desc:
            data = yaml.safe_load(file_desc) or {}
    except OSError as error:
        raise ConfigurationError(f"unable to read Hulotte configuration: {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigurationError(f"Hulotte configuration must be a mapping: {path}")
    return data


def save_user_config(data: Mapping[str, Any]) -> Path:
    """Persist the user configuration and return its path."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(yaml.safe_dump(dict(data), sort_keys=True), encoding="utf-8")
    except OSError as error:
        raise ConfigurationError(f"unable to write Hulotte configuration: {path}: {error}") from error
    return path


def set_user_value(key: str, value: str) -> Path:
    """Set one supported user configuration value."""
    if key != "streampu-root":
        raise ConfigurationError(f"unsupported configuration key: {key}")
    root = validate_streampu_root(value)
    data = load_user_config()
    data["streampu_root"] = str(root)
    return save_user_config(data)


def unset_user_value(key: str) -> Path:
    """Remove one supported user configuration value."""
    if key != "streampu-root":
        raise ConfigurationError(f"unsupported configuration key: {key}")
    data = load_user_config()
    data.pop("streampu_root", None)
    return save_user_config(data)


def validate_streampu_root(value: str | Path) -> Path:
    """Validate and normalize a StreamPU installation root."""
    root = Path(value).expanduser().resolve()
    headers = root / "include" / "streampu.hpp"
    library = root / "build" / "lib" / "libstreampu.a"
    missing = [str(path) for path in (headers, library) if not path.is_file()]
    if missing:
        details = ", ".join(missing)
        raise ConfigurationError(
            f"invalid StreamPU root '{root}'; missing required files: {details}"
        )
    return root


def resolve_streampu_root(
    explicit: str | Path | None = None,
    project_config: Mapping[str, Any] | None = None,
    project_root: str | Path | None = None,
    required: bool = True,
) -> Path | None:
    """Resolve StreamPU using explicit, project, user, environment, then defaults."""
    candidates: list[tuple[str, str | Path]] = []
    if explicit is not None:
        candidates.append(("explicit option", explicit))
    if project_config:
        dependencies = project_config.get("dependencies", {})
        project_value = project_config.get("streampu_root")
        if isinstance(dependencies, Mapping):
            project_value = project_value or dependencies.get("streampu_root")
        if project_value:
            if project_root is not None and not Path(project_value).is_absolute():
                project_value = Path(project_root) / project_value
            candidates.append(("project configuration", project_value))

    user_value = load_user_config().get("streampu_root")
    if user_value:
        candidates.append(("user configuration", user_value))

    env_value = os.environ.get("HULOTTE_STREAMPU_ROOT") or os.environ.get("STREAMPU_ROOT")
    if env_value:
        candidates.append(("environment", env_value))

    package_root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            ("repository default", package_root / "vendor" / "streampu"),
            ("system default", Path("/usr/local/streampu")),
            ("system default", Path("/opt/streampu")),
        ]
    )

    for source, candidate in candidates:
        try:
            return validate_streampu_root(candidate)
        except ConfigurationError as error:
            if source != "repository default" and source != "system default":
                raise ConfigurationError(f"{source} points to an invalid StreamPU installation: {error}") from error

    if not required:
        return None
    searched = ", ".join(str(Path(candidate).expanduser()) for _, candidate in candidates)
    raise ConfigurationError(f"StreamPU installation not found; searched: {searched}")


def configuration_status() -> dict[str, Any]:
    """Return a diagnostic representation of the user configuration."""
    configured = load_user_config().get("streampu_root")
    status: dict[str, Any] = {"path": str(config_path()), "streampu_root": configured}
    if configured:
        try:
            status["resolved_streampu_root"] = str(validate_streampu_root(configured))
            status["valid"] = True
        except ConfigurationError as error:
            status["valid"] = False
            status["error"] = str(error)
    else:
        status["valid"] = False
        status["error"] = "no StreamPU root configured"
    return status

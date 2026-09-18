#!/usr/bin/env python3
"""Hulotte graph-oriented command line interface."""

import argparse
import sys
from pathlib import Path

from framework.config import ConfigurationError, configuration_status, set_user_value, unset_user_value
from framework.project import ProjectGenerationError, build_project, generate_project, init_project
from framework.validation import PipelineValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Hulotte StreamPU pipeline artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config = subparsers.add_parser("config", help="manage user configuration")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show", help="show configuration and StreamPU status")
    config_set = config_subparsers.add_parser("set", help="set a configuration value")
    config_set.add_argument("key", choices=["streampu-root"])
    config_set.add_argument("value")
    config_unset = config_subparsers.add_parser("unset", help="remove a configuration value")
    config_unset.add_argument("key", choices=["streampu-root"])

    generate = subparsers.add_parser("generate", help="validate and generate a pipeline")
    generate.add_argument(
        "--project-root",
        default=".",
        help="Hulotte project directory (default: current directory)",
    )
    generate.add_argument("--hulotte-root", help="Hulotte installation directory")
    generate.add_argument("--pipeline", help="pipeline YAML path, relative to the project root")
    generate.add_argument("--catalog", help="module catalog path, relative to the project root")
    generate.add_argument(
        "--output",
        help="generated C++ path, relative to the project root (default: generated/main.cpp)",
    )
    build = subparsers.add_parser("build", help="validate, generate, and build a pipeline")
    build.add_argument("--project-root", default=".", help="Hulotte project directory")
    build.add_argument("--streampu-root", help="StreamPU installation directory")
    build.add_argument("--aff3ct-root", help="AFF3CT installation directory")
    build.add_argument("--hulotte-root", help="Hulotte installation directory")
    build.add_argument("--build-path", help="CMake build directory")
    init = subparsers.add_parser("init", help="create an external Hulotte project")
    init.add_argument("project_path", help="new project directory")
    init.add_argument("--hulotte-root", help="Hulotte installation directory")
    init.add_argument("--streampu-root", help="StreamPU installation directory")
    init.add_argument("--aff3ct-root", help="AFF3CT installation directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "config":
        try:
            if args.config_command == "show":
                import json

                print(json.dumps(configuration_status(), indent=2))
            elif args.config_command == "set":
                print(f"Configured: {set_user_value(args.key, args.value)}")
            else:
                print(f"Updated: {unset_user_value(args.key)}")
        except (ConfigurationError, OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0
    if args.command == "generate":
        try:
            output = generate_project(
                project_root=Path(args.project_root),
                catalog_path=args.catalog,
                pipeline_path=args.pipeline,
                output_path=args.output,
                hulotte_root=args.hulotte_root,
            )
        except (ProjectGenerationError, PipelineValidationError, ValueError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Generated: {output}")
        return 0
    if args.command == "build":
        try:
            executable = build_project(
                project_root=Path(args.project_root),
                streampu_root=args.streampu_root,
                aff3ct_root=args.aff3ct_root,
                hulotte_root=args.hulotte_root,
                build_path=args.build_path,
            )
        except (ProjectGenerationError, PipelineValidationError, ValueError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Built: {executable}")
        return 0
    if args.command == "init":
        try:
            project = init_project(
                args.project_path,
                hulotte_root=args.hulotte_root,
                streampu_root=args.streampu_root,
                aff3ct_root=args.aff3ct_root,
            )
        except (ProjectGenerationError, OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Initialized: {project}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

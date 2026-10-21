#!/usr/bin/env python3
"""Validate map files using the engine's Yamale schema and custom validators."""

import argparse
import importlib.util
from pathlib import Path

import yamale
import yaml
from yamale.validators import DefaultValidators, Validator


def construct_tagged_value(loader, suffix, node):
    """Accept engine-specific YAML tags without constructing arbitrary objects."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="*", type=Path, default=[root / "Resources/Maps"])
    args = parser.parse_args()

    schemas = root / "RobustToolbox/Schemas"
    spec = importlib.util.spec_from_file_location("mapfile_validators", schemas / "mapfile_validators.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load engine map validators")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validators = DefaultValidators.copy()
    for value in vars(module).values():
        if isinstance(value, type) and issubclass(value, Validator) and value is not Validator:
            validators[value.tag] = value

    # Yamale uses CSafeLoader when available, otherwise SafeLoader.
    yaml.SafeLoader.add_multi_constructor("!", construct_tagged_value)
    if hasattr(yaml, "CSafeLoader"):
        yaml.CSafeLoader.add_multi_constructor("!", construct_tagged_value)
    schema = yamale.make_schema(str(schemas / "mapfile.yml"), validators=validators)

    failed = False
    count = 0
    for directory in args.directories:
        if not directory.is_dir():
            raise FileNotFoundError(f"Map directory not found: {directory}")
        # Match the old action: every file beneath Resources/Maps, not just *.yml.
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            count += 1
            try:
                data = yamale.make_data(str(path))
                yamale.validate(schema, data, strict=True)
            except (yamale.YamaleError, yaml.YAMLError, ValueError) as error:
                failed = True
                print(f"{path}: {error}")

    print(f"Validated {count} map files.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
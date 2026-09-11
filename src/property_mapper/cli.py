from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import load_catalog_data, parse_catalog
from .config import config_for_model, load_configs
from .runner import process_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add SNACKS property sets to IFC elements.")
    parser.add_argument("--input", type=Path, default=Path("ifc-files/input"))
    parser.add_argument("--output", type=Path, default=Path("ifc-files/output"))
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config"),
        help="Mapping config file, or a directory of config files (each declaring its own models).",
    )
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--cache", type=Path, default=Path(".cache/snacks-0.1.0-alpha.json"))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _output_path(input_path: Path, configured_output: Path, batch: bool) -> Path:
    if not batch and configured_output.suffix.casefold() == ".ifc":
        return configured_output
    return configured_output / input_path.name


def main() -> int:
    args = _parser().parse_args()
    configs = load_configs(args.config)
    referenced_property_sets = tuple(
        dict.fromkeys(name for config in configs for name in config.referenced_property_sets)
    )
    data = load_catalog_data(args.cache, args.catalog)
    catalog = parse_catalog(data, referenced_property_sets)

    if args.input.is_dir():
        input_files = sorted(args.input.glob("*.ifc"))
        batch = True
    else:
        input_files = [args.input]
        batch = False

    if not input_files:
        raise SystemExit(f"No IFC files found at {args.input}")

    failed = 0
    for input_path in input_files:
        try:
            config = config_for_model(configs, input_path.name)
            result = process_file(
                input_path,
                _output_path(input_path, args.output, batch),
                config,
                catalog,
                dry_run=args.dry_run,
            )
            mode = "planned" if args.dry_run else "written"
            print(
                f"{input_path.name}: {mode}; selected={result.selected_elements}, "
                f"excluded={result.excluded_elements}, assignments={result.assignments}"
            )
        except Exception as error:
            failed += 1
            print(f"{input_path.name}: failed: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

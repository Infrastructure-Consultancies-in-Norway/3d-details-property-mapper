from __future__ import annotations

from pathlib import Path

import ifcopenshell

from .catalog import CatalogPropertySet
from .config import MappingConfig
from .ifc_mapper import MappingResult, apply_mapping, build_plan, direct_property_sets


def process_file(
    input_path: Path,
    output_path: Path,
    config: MappingConfig,
    catalog: dict[str, CatalogPropertySet],
    *,
    dry_run: bool = False,
) -> MappingResult:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must differ")

    model = ifcopenshell.open(input_path)
    if dry_run:
        plans, excluded = build_plan(model, config)
        assignments: dict[str, int] = {}
        for plan in plans:
            for name in plan.property_sets:
                assignments[name] = assignments.get(name, 0) + 1
        return MappingResult(len(plans), excluded, 0, 0, 0, assignments)

    result = apply_mapping(model, config, catalog)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        model.write(temporary_path)
        reopened = ifcopenshell.open(temporary_path)
        reopened_elements = {
            element.GlobalId: element for element in reopened.by_type(config.ifc_class)
        }
        for plan in build_plan(model, config)[0]:
            reopened_element = reopened_elements.get(plan.element.GlobalId)
            if reopened_element is None:
                raise ValueError(f"Output validation lost element {plan.element.GlobalId}")
            for set_name in plan.property_sets:
                if len(direct_property_sets(reopened_element, set_name)) != 1:
                    raise ValueError(
                        f"Output validation failed for {reopened_element.GlobalId} {set_name}"
                    )
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return result

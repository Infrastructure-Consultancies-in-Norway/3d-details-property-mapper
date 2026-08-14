from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ifcopenshell
from ifcopenshell.api.pset import add_pset, edit_pset

from .catalog import CatalogPropertySet
from .config import MappingConfig
from .rules import property_sets_for_name
from .values import canonical_datatype, create_ifc_value


class MappingError(ValueError):
    """Raised when an IFC cannot be enriched without ambiguity."""


@dataclass(frozen=True)
class ElementPlan:
    element: Any
    property_sets: tuple[str, ...]


@dataclass(frozen=True)
class MappingResult:
    selected_elements: int
    excluded_elements: int
    created_property_sets: int
    updated_property_sets: int
    written_properties: int
    assignments: dict[str, int]


def direct_property_sets(element: Any, name: str) -> list[Any]:
    matches: list[Any] = []
    for relationship in element.IsDefinedBy or ():
        if not relationship.is_a("IfcRelDefinesByProperties"):
            continue
        definition = relationship.RelatingPropertyDefinition
        if definition.is_a("IfcPropertySet") and definition.Name == name:
            matches.append(definition)
    return matches


def build_plan(model: ifcopenshell.file, config: MappingConfig) -> tuple[list[ElementPlan], int]:
    plans: list[ElementPlan] = []
    excluded = 0
    for element in model.by_type(config.ifc_class):
        property_sets = property_sets_for_name(element.Name, config)
        if not property_sets:
            excluded += 1
            continue
        plans.append(ElementPlan(element=element, property_sets=property_sets))
    return plans, excluded


def _preflight(
    plans: list[ElementPlan],
    catalog: dict[str, CatalogPropertySet],
) -> None:
    for plan in plans:
        for set_name in plan.property_sets:
            matches = direct_property_sets(plan.element, set_name)
            if len(matches) > 1:
                raise MappingError(
                    f"{plan.element.GlobalId} has duplicate direct property sets named {set_name}"
                )
            if not matches:
                continue
            existing_properties = {prop.Name: prop for prop in matches[0].HasProperties or ()}
            for definition in catalog[set_name].properties:
                existing = existing_properties.get(definition.name)
                if existing is None or not existing.is_a("IfcPropertySingleValue"):
                    continue
                if existing.NominalValue is None:
                    continue
                expected = canonical_datatype(definition.datatype)
                actual = existing.NominalValue.is_a()
                if actual != expected:
                    raise MappingError(
                        f"{plan.element.GlobalId} {set_name}.{definition.name} "
                        f"has {actual}, expected {expected}"
                    )


def apply_mapping(
    model: ifcopenshell.file,
    config: MappingConfig,
    catalog: dict[str, CatalogPropertySet],
) -> MappingResult:
    plans, excluded = build_plan(model, config)
    _preflight(plans, catalog)

    created = 0
    updated = 0
    written = 0
    assignments: dict[str, int] = {}
    for plan in plans:
        for set_name in plan.property_sets:
            matches = direct_property_sets(plan.element, set_name)
            if matches:
                property_set = matches[0]
                updated += 1
            else:
                property_set = add_pset(model, product=plan.element, name=set_name)
                created += 1
            properties = {
                definition.name: create_ifc_value(model, definition)
                for definition in catalog[set_name].properties
            }
            edit_pset(model, pset=property_set, properties=properties)
            written += len(properties)
            assignments[set_name] = assignments.get(set_name, 0) + 1

    return MappingResult(
        selected_elements=len(plans),
        excluded_elements=excluded,
        created_property_sets=created,
        updated_property_sets=updated,
        written_properties=written,
        assignments=assignments,
    )

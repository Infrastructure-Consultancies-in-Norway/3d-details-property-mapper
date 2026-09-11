from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ifcopenshell
from ifcopenshell.api.pset import add_pset, edit_pset, remove_pset

from .catalog import CatalogError, CatalogPropertySet
from .config import MappingConfig
from .rules import (
    property_sets_for_name,
    property_sets_to_delete_for_name,
    property_values_for_name,
)
from .values import canonical_datatype, create_ifc_value


class MappingError(ValueError):
    """Raised when an IFC cannot be enriched without ambiguity."""


@dataclass(frozen=True)
class ElementPlan:
    element: Any
    property_sets: tuple[str, ...]
    delete_property_sets: tuple[str, ...]
    property_values: dict[str, dict[str, object]]


@dataclass(frozen=True)
class MappingResult:
    selected_elements: int
    excluded_elements: int
    deleted_property_sets: int
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
        plans.append(
            ElementPlan(
                element=element,
                property_sets=property_sets,
                delete_property_sets=property_sets_to_delete_for_name(element.Name, config),
                property_values=property_values_for_name(element.Name, config),
            )
        )
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


def _validate_config_values(
    config: MappingConfig,
    catalog: dict[str, CatalogPropertySet],
) -> None:
    validation_model = ifcopenshell.file(schema="IFC2X3")
    configured_sources = [("default_values", config.default_values)]
    configured_sources.extend((f"rule {rule.rule_id}", rule.values) for rule in config.rules)

    for source, values_by_set in configured_sources:
        for set_name, configured_values in values_by_set.items():
            definitions = {
                definition.name: definition for definition in catalog[set_name].properties
            }
            unknown_properties = set(configured_values) - set(definitions)
            if unknown_properties:
                raise MappingError(
                    f"{source} references unknown or optional properties in {set_name}: "
                    f"{', '.join(sorted(unknown_properties))}"
                )
            for name, value in configured_values.items():
                try:
                    create_ifc_value(validation_model, definitions[name], value)
                except (CatalogError, TypeError, ValueError) as error:
                    raise MappingError(
                        f"{source} value for {set_name}.{name} is invalid: {error}"
                    ) from error


def _validate_plan_values(
    plans: list[ElementPlan],
    catalog: dict[str, CatalogPropertySet],
) -> None:
    for plan in plans:
        for set_name in plan.property_sets:
            configured_values = plan.property_values.get(set_name, {})
            missing = [
                definition.name
                for definition in catalog[set_name].properties
                if definition.name not in configured_values
            ]
            if missing:
                raise MappingError(
                    f"{plan.element.GlobalId} is missing YAML values for {set_name}: "
                    f"{', '.join(missing)}"
                )


def apply_mapping(
    model: ifcopenshell.file,
    config: MappingConfig,
    catalog: dict[str, CatalogPropertySet],
) -> MappingResult:
    _validate_config_values(config, catalog)
    plans, excluded = build_plan(model, config)
    _validate_plan_values(plans, catalog)
    _preflight(plans, catalog)

    created = 0
    updated = 0
    deleted = 0
    written = 0
    assignments: dict[str, int] = {}
    for plan in plans:
        for set_name in plan.delete_property_sets:
            for property_set in direct_property_sets(plan.element, set_name):
                remove_pset(model, product=plan.element, pset=property_set)
                deleted += 1
        for set_name in plan.property_sets:
            matches = direct_property_sets(plan.element, set_name)
            if matches:
                property_set = matches[0]
                updated += 1
            else:
                property_set = add_pset(model, product=plan.element, name=set_name)
                created += 1
            properties = {
                definition.name: create_ifc_value(
                    model,
                    definition,
                    plan.property_values[set_name][definition.name],
                )
                for definition in catalog[set_name].properties
            }
            edit_pset(model, pset=property_set, properties=properties)
            written += len(properties)
            assignments[set_name] = assignments.get(set_name, 0) + 1

    return MappingResult(
        selected_elements=len(plans),
        excluded_elements=excluded,
        deleted_property_sets=deleted,
        created_property_sets=created,
        updated_property_sets=updated,
        written_properties=written,
        assignments=assignments,
    )

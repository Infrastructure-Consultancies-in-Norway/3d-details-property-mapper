from __future__ import annotations

import re
from typing import Any

import ifcopenshell

from .catalog import CatalogError, CatalogProperty

_NUMBER = re.compile(r"^\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))")
_CANONICAL_TYPES = {
    "ifctext": "IfcText",
    "ifcinteger": "IfcInteger",
    "ifclengthmeasure": "IfcLengthMeasure",
    "ifclenghtmeasure": "IfcLengthMeasure",
    "ifcmassmeasure": "IfcMassMeasure",
    "ifcreal": "IfcReal",
}


def canonical_datatype(datatype: str) -> str:
    try:
        return _CANONICAL_TYPES[datatype.casefold()]
    except KeyError as error:
        raise CatalogError(f"Unsupported IFC datatype: {datatype}") from error


def _numeric_value(value: Any, context: str) -> float:
    if isinstance(value, bool):
        raise CatalogError(f"{context} must be numeric, got a boolean")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        match = _NUMBER.match(value)
        if match:
            return float(match.group(1).replace(",", "."))
    raise CatalogError(f"{context} does not start with a numeric value: {value!r}")


def create_ifc_value(
    model: ifcopenshell.file,
    property_definition: CatalogProperty,
    value: Any,
) -> ifcopenshell.entity_instance:
    datatype = canonical_datatype(property_definition.datatype)
    context = property_definition.name
    if datatype == "IfcText":
        converted = str(value)
    elif datatype == "IfcInteger":
        numeric = _numeric_value(value, context)
        if not numeric.is_integer():
            raise CatalogError(f"{context} must be a whole number")
        converted = int(numeric)
    else:
        converted = _numeric_value(value, context)
    return model.create_entity(datatype, converted)

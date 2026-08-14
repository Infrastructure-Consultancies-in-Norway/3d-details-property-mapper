import ifcopenshell
import pytest

from property_mapper.catalog import CatalogError, CatalogProperty
from property_mapper.values import create_ifc_value


@pytest.mark.parametrize(
    ("datatype", "source", "expected_type", "expected_value"),
    [
        ("IfcText", "demo", "IfcText", "demo"),
        ("Ifctext", "lowercase type", "IfcText", "lowercase type"),
        ("IfcInteger", "47", "IfcInteger", 47),
        ("IfcLengthMeasure", "20 mm", "IfcLengthMeasure", 20.0),
        ("IfcMassMeasure", "20 kg", "IfcMassMeasure", 20.0),
        ("IfcLengthMeasure", "12,5 mm", "IfcLengthMeasure", 12.5),
    ],
)
def test_create_ifc_value(
    datatype: str,
    source: str,
    expected_type: str,
    expected_value: object,
) -> None:
    model = ifcopenshell.file(schema="IFC2X3")

    value = create_ifc_value(model, CatalogProperty("Property", datatype, source))

    assert value.is_a() == expected_type
    assert value.wrappedValue == expected_value


def test_integer_rejects_fraction() -> None:
    model = ifcopenshell.file(schema="IFC2X3")

    with pytest.raises(CatalogError, match="whole number"):
        create_ifc_value(model, CatalogProperty("Count", "IfcInteger", "1.5"))

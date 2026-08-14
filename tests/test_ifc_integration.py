from pathlib import Path

import ifcopenshell

from property_mapper.catalog import parse_catalog
from property_mapper.config import load_config
from property_mapper.ifc_mapper import direct_property_sets
from property_mapper.runner import process_file

ROOT = Path(__file__).parents[1]
INPUT = ROOT / "ifc-files" / "input" / "SNACKS_Detalj_Overgangsplate.ifc"
CONFIG = ROOT / "config" / "mapping.yaml"


def _catalog_data() -> list[dict[str, object]]:
    data: list[dict[str, object]] = []
    for name in (
        "BIM_Tverrfaglig",
        "KON_Felles",
        "KON_Løsmasser",
        "KON_Armering",
        "KON_Betong",
    ):
        property_names = [f"{name} test"]
        if name == "KON_Felles":
            property_names.extend(
                [
                    "KON.10 - Konstruksjonsinndeling",
                    "KON.11 - Konstruksjonsdel",
                    "KON.13 - Elementnavn",
                ]
            )
        data.append(
            {
                "Name": name,
                "Properties": [
                    {
                        "PropertyName": property_name,
                        "Datatype": "IfcText",
                        "SampleValue": "catalog example",
                        "RequirementColor": "Svart",
                        "Required": True,
                    }
                    for property_name in property_names
                ],
            }
        )
    return data


def _assignment_count(model: ifcopenshell.file, name: str) -> int:
    return sum(bool(direct_property_sets(element, name)) for element in model.by_type("IfcElement"))


def test_process_real_fixture_and_rerun_idempotently(tmp_path: Path) -> None:
    original_bytes = INPUT.read_bytes()
    config = load_config(CONFIG)
    catalog = parse_catalog(_catalog_data(), config.referenced_property_sets)
    first_output = tmp_path / "first.ifc"
    second_output = tmp_path / "second.ifc"

    first = process_file(INPUT, first_output, config, catalog)
    first_model = ifcopenshell.open(first_output)
    managed_ids = {
        (element.GlobalId, property_set.Name): property_set.GlobalId
        for element in first_model.by_type("IfcElement")
        for set_name in config.referenced_property_sets
        for property_set in direct_property_sets(element, set_name)
    }

    assert first.selected_elements == 18
    assert first.excluded_elements == 1
    assert first.created_property_sets == 39
    assert first.assignments == {
        "BIM_Tverrfaglig": 18,
        "KON_Felles": 15,
        "KON_Armering": 1,
        "KON_Betong": 2,
        "KON_Løsmasser": 3,
    }
    assert len(first_model.by_type("IfcElement")) == 19
    assert _assignment_count(first_model, "BIM_Tverrfaglig") == 18
    assert _assignment_count(first_model, "KON_Felles") == 15
    assert _assignment_count(first_model, "KON_Løsmasser") == 3
    assert _assignment_count(first_model, "KON_Armering") == 1
    assert _assignment_count(first_model, "KON_Betong") == 2
    loose_materials = [
        element
        for element in first_model.by_type("IfcElement")
        if element.Name in {"Løsmasser_1", "Løsmasser_2"}
    ]
    assert len(loose_materials) == 3
    assert all(not direct_property_sets(element, "KON_Felles") for element in loose_materials)
    transition_slab = next(
        element for element in first_model.by_type("IfcElement") if element.Name == "Overgangsplate"
    )
    common_properties = {
        prop.Name: prop.NominalValue.wrappedValue
        for prop in direct_property_sets(transition_slab, "KON_Felles")[0].HasProperties
    }
    assert common_properties["KON.10 - Konstruksjonsinndeling"] == "Underbygning"
    assert common_properties["KON.11 - Konstruksjonsdel"] == "Landkar"
    assert common_properties["KON.13 - Elementnavn"] == "Overgangsplate"
    frame = next(
        element for element in first_model.by_type("IfcElement") if element.Name == "Ramme"
    )
    assert all(not direct_property_sets(frame, name) for name in config.referenced_property_sets)
    assert all(
        property_set.OwnerHistory is not None
        for property_set in first_model.by_type("IfcPropertySet")
        if property_set.Name in config.referenced_property_sets
    )

    second = process_file(first_output, second_output, config, catalog)
    second_model = ifcopenshell.open(second_output)

    assert second.created_property_sets == 0
    assert second.updated_property_sets == 39
    assert {
        (element.GlobalId, property_set.Name): property_set.GlobalId
        for element in second_model.by_type("IfcElement")
        for set_name in config.referenced_property_sets
        for property_set in direct_property_sets(element, set_name)
    } == managed_ids
    assert INPUT.read_bytes() == original_bytes

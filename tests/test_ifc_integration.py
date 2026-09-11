from pathlib import Path

import ifcopenshell

from property_mapper.catalog import CatalogProperty, CatalogPropertySet, parse_catalog
from property_mapper.config import load_config, parse_config
from property_mapper.ifc_mapper import apply_mapping, direct_property_sets
from property_mapper.runner import process_file

ROOT = Path(__file__).parents[1]
INPUT = ROOT / "ifc-files" / "input" / "SNACKS_Detalj_Bolter.ifc"
CONFIG = ROOT / "config" / "SNACKS_Detalj_Bolter.yaml"


def _catalog_data(config) -> list[dict[str, object]]:
    data: list[dict[str, object]] = []
    for name in config.referenced_property_sets:
        property_names = config.default_values[name]
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
    catalog = parse_catalog(_catalog_data(config), config.referenced_property_sets)
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

    assert first.selected_elements == 66
    assert first.excluded_elements == 3
    assert first.created_property_sets == 190
    assert first.assignments == {
        "BIM_Tverrfaglig": 66,
        "KON_Felles": 66,
        "KON_Festemidler": 43,
        "KON_Betong": 4,
        "KON_Stål": 11,
    }
    assert len(first_model.by_type("IfcElement")) == 69
    assert first_model.by_type("IfcProject")[0].Name == "SNACKS Detalj Bolter"
    assert first_model.by_type("IfcSite")[0].Name == "SNACKS Detalj Bolter"
    assert first_model.by_type("IfcBuilding")[0].Name == "Bru"
    assert first_model.by_type("IfcBuildingStorey")[0].Name == "Bolter"
    assert _assignment_count(first_model, "BIM_Tverrfaglig") == 66
    assert _assignment_count(first_model, "KON_Felles") == 66
    assert _assignment_count(first_model, "KON_Festemidler") == 43
    assert _assignment_count(first_model, "KON_Betong") == 4
    assert _assignment_count(first_model, "KON_Stål") == 11
    bolt_group = next(
        element for element in first_model.by_type("IfcElement") if element.Name == "Boltegruppe"
    )
    assert direct_property_sets(bolt_group, "KON_Festemidler")
    bridge_deck = next(
        element for element in first_model.by_type("IfcElement") if element.Name == "Bruplate"
    )
    assert direct_property_sets(bridge_deck, "KON_Betong")
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
    assert second.updated_property_sets == 190
    assert {
        (element.GlobalId, property_set.Name): property_set.GlobalId
        for element in second_model.by_type("IfcElement")
        for set_name in config.referenced_property_sets
        for property_set in direct_property_sets(element, set_name)
    } == managed_ids
    assert INPUT.read_bytes() == original_bytes


def test_apply_mapping_deletes_configured_direct_property_sets(tmp_path: Path) -> None:
    model = ifcopenshell.file(schema="IFC4")
    element = model.create_entity(
        "IfcBuildingElementProxy",
        ifcopenshell.guid.new(),
        None,
        "Fundament",
        None,
        None,
        None,
        None,
        None,
    )
    ifcopenshell.api.pset.add_pset(model, product=element, name="Tekla Common")
    ifcopenshell.api.pset.add_pset(model, product=element, name="Tekla Quantity")
    config = parse_config(
        {
            "version": 1,
            "models": ["Test.ifc"],
            "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
            "delete_property_sets": ["Tekla Common"],
            "base_property_sets": ["KON_Felles"],
            "default_values": {"KON_Felles": {"Common property": "value"}},
            "rules": [
                {
                    "id": "foundation",
                    "name_pattern": "^Fundament$",
                    "property_sets": ["KON_Betong"],
                    "delete_property_sets": ["Tekla Quantity"],
                    "values": {"KON_Betong": {"Concrete property": "value"}},
                }
            ],
        }
    )
    catalog = {
        "KON_Felles": CatalogPropertySet(
            "KON_Felles", (CatalogProperty("Common property", "IfcText"),)
        ),
        "KON_Betong": CatalogPropertySet(
            "KON_Betong", (CatalogProperty("Concrete property", "IfcText"),)
        ),
    }

    result = apply_mapping(model, config, catalog)
    output_path = tmp_path / "deleted.ifc"
    model.write(output_path)
    reopened = ifcopenshell.open(output_path)
    reopened_element = reopened.by_type("IfcBuildingElementProxy")[0]

    assert result.deleted_property_sets == 2
    assert direct_property_sets(reopened_element, "Tekla Common") == []
    assert direct_property_sets(reopened_element, "Tekla Quantity") == []
    assert len(direct_property_sets(reopened_element, "KON_Felles")) == 1
    assert len(direct_property_sets(reopened_element, "KON_Betong")) == 1

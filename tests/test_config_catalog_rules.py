from pathlib import Path

import ifcopenshell
import pytest

from property_mapper.catalog import CatalogProperty, CatalogPropertySet, parse_catalog
from property_mapper.config import ConfigError, load_config, parse_config
from property_mapper.ifc_mapper import MappingError, apply_mapping
from property_mapper.rules import (
    property_sets_for_name,
    property_sets_to_delete_for_name,
    property_values_for_name,
)

CONFIG_PATH = Path(__file__).parents[1] / "config" / "SNACKS_Detalj_Bolter.yaml"


def test_mapping_for_fixture_names() -> None:
    config = load_config(CONFIG_PATH)

    assert property_sets_for_name("Ramme", config) == ()
    assert property_sets_for_name("ramme", config) == ()
    assert config.spatial_structure == {
        "IfcProject": "SNACKS Detalj Bolter",
        "IfcSite": "SNACKS Detalj Bolter",
        "IfcBuilding": "Bru",
        "IfcBuildingStorey": "Bolter",
    }
    assert property_sets_for_name("Bruplate", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
        "KON_Betong",
    )
    assert property_sets_for_name("Boltegruppe", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
        "KON_Festemidler",
    )
    assert property_sets_for_name("Rekkverk", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
        "KON_Stål",
    )
    assert property_sets_for_name("Topeka", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
    )


def test_config_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(ConfigError, match="Duplicate rule id"):
        parse_config(
            {
                "version": 1,
                "models": ["Test.ifc"],
                "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
                "base_property_sets": ["BIM_Tverrfaglig"],
                "rules": [
                    {"id": "same", "name_pattern": "a", "property_sets": ["KON_Felles"]},
                    {"id": "same", "name_pattern": "b", "property_sets": ["KON_Betong"]},
                ],
            }
        )


def test_property_values_use_rule_over_default() -> None:
    config = parse_config(
        {
            "version": 1,
            "models": ["Test.ifc"],
            "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
            "base_property_sets": ["KON_Felles"],
            "default_values": {
                "KON_Felles": {
                    "KON.10 - Konstruksjonsinndeling": "Underbygning",
                    "KON.11 - Konstruksjonsdel": "Uspesifisert",
                }
            },
            "rules": [
                {
                    "id": "landkar",
                    "name_pattern": "^Landkar$",
                    "property_sets": ["KON_Betong"],
                    "values": {
                        "KON_Felles": {"KON.11 - Konstruksjonsdel": "Landkar"},
                        "KON_Betong": {"Concrete property": "project value"},
                    },
                }
            ],
        }
    )

    assert property_values_for_name("Landkar", config) == {
        "KON_Felles": {
            "KON.10 - Konstruksjonsinndeling": "Underbygning",
            "KON.11 - Konstruksjonsdel": "Landkar",
        },
        "KON_Betong": {"Concrete property": "project value"},
    }


def test_default_values_can_reference_rule_property_sets() -> None:
    config = parse_config(
        {
            "version": 1,
            "models": ["Test.ifc"],
            "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
            "base_property_sets": ["KON_Felles"],
            "default_values": {
                "KON_Felles": {"Common property": "common value"},
                "KON_Betong": {"Concrete property": "default concrete"},
            },
            "rules": [
                {
                    "id": "landkar",
                    "name_pattern": "^Landkar$",
                    "property_sets": ["KON_Betong"],
                }
            ],
        }
    )

    assert property_values_for_name("Landkar", config)["KON_Betong"] == {
        "Concrete property": "default concrete"
    }


def test_property_sets_to_delete_for_name_uses_global_and_rule_values() -> None:
    config = parse_config(
        {
            "version": 1,
            "models": ["Test.ifc"],
            "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": ["^Skip$"]},
            "delete_property_sets": ["Tekla Common", "Tekla Common"],
            "base_property_sets": ["KON_Felles"],
            "rules": [
                {
                    "id": "landkar",
                    "name_pattern": "^Landkar$",
                    "property_sets": ["KON_Betong"],
                    "delete_property_sets": ["Tekla Quantity"],
                }
            ],
        }
    )

    assert property_sets_to_delete_for_name("Landkar", config) == (
        "Tekla Common",
        "Tekla Quantity",
    )
    assert property_sets_to_delete_for_name("Skip", config) == ()


def test_config_rejects_deleting_assigned_property_sets() -> None:
    with pytest.raises(ConfigError, match="also assigns property sets"):
        parse_config(
            {
                "version": 1,
                "models": ["Test.ifc"],
                "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
                "base_property_sets": ["KON_Felles"],
                "rules": [
                    {
                        "id": "landkar",
                        "name_pattern": "^Landkar$",
                        "property_sets": ["KON_Betong"],
                        "delete_property_sets": ["KON_Betong"],
                    }
                ],
            }
        )

    with pytest.raises(ConfigError, match="also assigns property sets"):
        parse_config(
            {
                "version": 1,
                "models": ["Test.ifc"],
                "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
                "delete_property_sets": ["KON_Felles"],
                "base_property_sets": ["KON_Felles"],
                "rules": [
                    {
                        "id": "landkar",
                        "name_pattern": "^Landkar$",
                        "property_sets": ["KON_Betong"],
                    }
                ],
            }
        )


def test_mapping_requires_yaml_values_for_assigned_required_properties() -> None:
    model = ifcopenshell.file(schema="IFC4")
    model.create_entity(
        "IfcBuildingElementProxy",
        ifcopenshell.guid.new(),
        None,
        "Landkar",
        None,
        None,
        None,
        None,
        None,
    )
    config = parse_config(
        {
            "version": 1,
            "models": ["Test.ifc"],
            "selection": {"ifc_class": "IfcElement", "exclude_name_patterns": []},
            "base_property_sets": ["BIM_Tverrfaglig"],
            "rules": [
                {
                    "id": "landkar",
                    "name_pattern": "^Landkar$",
                    "property_sets": ["KON_Felles"],
                }
            ],
        }
    )
    catalog = {
        "BIM_Tverrfaglig": CatalogPropertySet("BIM_Tverrfaglig", ()),
        "KON_Felles": CatalogPropertySet(
            "KON_Felles",
            (CatalogProperty("Common property", "IfcText"),),
        )
    }

    with pytest.raises(MappingError, match="missing YAML values"):
        apply_mapping(model, config, catalog)


def test_catalog_keeps_black_required_names_and_skips_gray() -> None:
    parsed = parse_catalog(
        [
            {
                "Name": "KON_Felles",
                "Properties": [
                    {
                        "PropertyName": "Required sample",
                        "Datatype": "IfcText",
                        "SampleValue": "demo",
                        "RequirementColor": "Svart",
                        "Required": True,
                    },
                    {
                        "PropertyName": "Required fallback",
                        "Datatype": "IfcInteger",
                        "RecommendedValues": [0, 1],
                        "RequirementColor": " svart ",
                        "Required": True,
                    },
                    {
                        "PropertyName": "Optional",
                        "Datatype": "IfcText",
                        "SampleValue": "skip",
                        "RequirementColor": "Grå",
                        "Required": False,
                    },
                ],
            }
        ],
        ("KON_Felles",),
    )

    assert [prop.name for prop in parsed["KON_Felles"].properties] == [
        "Required sample",
        "Required fallback",
    ]


def test_catalog_accepts_required_property_without_example_value() -> None:
    parsed = parse_catalog(
        [
            {
                "Name": "KON_Felles",
                "Properties": [
                    {
                        "PropertyName": "Missing",
                        "Datatype": "IfcText",
                        "RequirementColor": "Svart",
                        "Required": True,
                    }
                ],
            }
        ],
        ("KON_Felles",),
    )

    assert parsed["KON_Felles"].properties == (CatalogProperty("Missing", "IfcText"),)

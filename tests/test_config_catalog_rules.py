from pathlib import Path

import pytest

from property_mapper.catalog import CatalogError, parse_catalog
from property_mapper.config import ConfigError, load_config, parse_config
from property_mapper.rules import property_sets_for_name, property_values_for_name

CONFIG_PATH = Path(__file__).parents[1] / "config" / "mapping.yaml"


def test_mapping_for_fixture_names() -> None:
    config = load_config(CONFIG_PATH)

    assert property_sets_for_name("Ramme", config) == ()
    assert property_sets_for_name("ramme", config) == ()
    assert property_sets_for_name("Landkar", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
        "KON_Betong",
    )
    assert property_sets_for_name("Løsmasser_2", config) == (
        "BIM_Tverrfaglig",
        "KON_Løsmasser",
    )
    assert property_sets_for_name("Armering_Rustfritt", config)[-1] == "KON_Armering"
    assert property_sets_for_name("Fuktisolering_(A3-4)", config) == (
        "BIM_Tverrfaglig",
        "KON_Felles",
    )


def test_config_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(ConfigError, match="Duplicate rule id"):
        parse_config(
            {
                "version": 1,
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


def test_catalog_keeps_black_required_and_skips_gray() -> None:
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

    assert [(prop.name, prop.value) for prop in parsed["KON_Felles"].properties] == [
        ("Required sample", "demo"),
        ("Required fallback", 0),
    ]


def test_catalog_rejects_required_property_without_value() -> None:
    with pytest.raises(CatalogError, match="no example or fallback"):
        parse_catalog(
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

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the mapping configuration is invalid."""


@dataclass(frozen=True)
class MappingRule:
    rule_id: str
    name_pattern: re.Pattern[str]
    property_sets: tuple[str, ...]
    exclude_property_sets: tuple[str, ...]
    values: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class MappingConfig:
    ifc_class: str
    exclude_name_patterns: tuple[re.Pattern[str], ...]
    base_property_sets: tuple[str, ...]
    default_values: dict[str, dict[str, Any]]
    rules: tuple[MappingRule, ...]

    @property
    def referenced_property_sets(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *self.base_property_sets,
                    *(name for rule in self.rules for name in rule.property_sets),
                )
            )
        )


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    return value


def _require_strings(value: Any, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ConfigError(f"{field} must be a non-empty list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{field} must contain only non-empty strings")
    return tuple(value)


def _compile(pattern: str, field: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        raise ConfigError(f"Invalid regex in {field}: {error}") from error


def _property_values(value: Any, field: str) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    sets = _require_mapping(value, field)
    parsed: dict[str, dict[str, Any]] = {}
    for set_name, raw_properties in sets.items():
        if not isinstance(set_name, str) or not set_name.strip():
            raise ConfigError(f"{field} must use non-empty property-set names")
        properties = _require_mapping(raw_properties, f"{field}.{set_name}")
        if not properties:
            raise ConfigError(f"{field}.{set_name} must not be empty")
        if any(not isinstance(name, str) or not name.strip() for name in properties):
            raise ConfigError(f"{field}.{set_name} must use non-empty property names")
        parsed[set_name] = dict(properties)
    return parsed


def parse_config(data: Any) -> MappingConfig:
    root = _require_mapping(data, "configuration")
    allowed_root = {"version", "selection", "base_property_sets", "default_values", "rules"}
    unknown = set(root) - allowed_root
    if unknown:
        raise ConfigError(f"Unknown configuration fields: {', '.join(sorted(unknown))}")
    if root.get("version") != 1:
        raise ConfigError("Only mapping configuration version 1 is supported")

    selection = _require_mapping(root.get("selection"), "selection")
    if set(selection) - {"ifc_class", "exclude_name_patterns"}:
        raise ConfigError("Unknown selection fields")
    ifc_class = selection.get("ifc_class")
    if not isinstance(ifc_class, str) or not ifc_class.startswith("Ifc"):
        raise ConfigError("selection.ifc_class must be an IFC class name")
    exclusions = _require_strings(
        selection.get("exclude_name_patterns", []),
        "selection.exclude_name_patterns",
        allow_empty=True,
    )

    base_sets = _require_strings(root.get("base_property_sets"), "base_property_sets")
    default_values = _property_values(root.get("default_values"), "default_values")
    unknown_default_sets = set(default_values) - set(base_sets)
    if unknown_default_sets:
        raise ConfigError(
            "default_values references non-base property sets: "
            + ", ".join(sorted(unknown_default_sets))
        )
    raw_rules = root.get("rules")
    if not isinstance(raw_rules, list):
        raise ConfigError("rules must be a list")

    rules: list[MappingRule] = []
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        rule = _require_mapping(raw_rule, f"rules[{index}]")
        required_fields = {"id", "name_pattern", "property_sets"}
        optional_fields = {"exclude_property_sets", "values"}
        if not required_fields <= set(rule) or set(rule) - required_fields - optional_fields:
            raise ConfigError(
                f"rules[{index}] must contain id, name_pattern, and property_sets; "
                "exclude_property_sets and values are optional"
            )
        rule_id = rule["id"]
        pattern = rule["name_pattern"]
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ConfigError(f"rules[{index}].id must be a non-empty string")
        if rule_id in seen_ids:
            raise ConfigError(f"Duplicate rule id: {rule_id}")
        if not isinstance(pattern, str) or not pattern:
            raise ConfigError(f"rules[{index}].name_pattern must be a non-empty string")
        property_sets = _require_strings(rule["property_sets"], f"rules[{index}].property_sets")
        excluded_sets = _require_strings(
            rule.get("exclude_property_sets", []),
            f"rules[{index}].exclude_property_sets",
            allow_empty=True,
        )
        unknown_excluded_sets = set(excluded_sets) - set(base_sets)
        if unknown_excluded_sets:
            raise ConfigError(
                f"rules[{index}].exclude_property_sets references non-base property sets: "
                + ", ".join(sorted(unknown_excluded_sets))
            )
        values = _property_values(rule.get("values"), f"rules[{index}].values")
        assigned_sets = (set(base_sets) - set(excluded_sets)) | set(property_sets)
        unknown_value_sets = set(values) - assigned_sets
        if unknown_value_sets:
            raise ConfigError(
                f"rules[{index}].values references unassigned property sets: "
                + ", ".join(sorted(unknown_value_sets))
            )
        seen_ids.add(rule_id)
        rules.append(
            MappingRule(
                rule_id=rule_id,
                name_pattern=_compile(pattern, f"rules[{index}].name_pattern"),
                property_sets=property_sets,
                exclude_property_sets=tuple(dict.fromkeys(excluded_sets)),
                values=values,
            )
        )

    return MappingConfig(
        ifc_class=ifc_class,
        exclude_name_patterns=tuple(
            _compile(pattern, "selection.exclude_name_patterns") for pattern in exclusions
        ),
        base_property_sets=tuple(dict.fromkeys(base_sets)),
        default_values=default_values,
        rules=tuple(rules),
    )


def load_config(path: Path) -> MappingConfig:
    with path.open(encoding="utf-8") as config_file:
        return parse_config(yaml.safe_load(config_file))

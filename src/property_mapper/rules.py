from __future__ import annotations

from .config import MappingConfig


def property_sets_for_name(name: str | None, config: MappingConfig) -> tuple[str, ...]:
    candidate = name or ""
    if any(pattern.fullmatch(candidate) for pattern in config.exclude_name_patterns):
        return ()

    property_sets = list(config.base_property_sets)
    for rule in config.rules:
        if rule.name_pattern.fullmatch(candidate):
            excluded = set(rule.exclude_property_sets)
            property_sets = [name for name in property_sets if name not in excluded]
            property_sets.extend(rule.property_sets)
    return tuple(dict.fromkeys(property_sets))


def property_values_for_name(
    name: str | None, config: MappingConfig
) -> dict[str, dict[str, object]]:
    candidate = name or ""
    if any(pattern.fullmatch(candidate) for pattern in config.exclude_name_patterns):
        return {}

    values = {set_name: dict(properties) for set_name, properties in config.default_values.items()}
    for rule in config.rules:
        if rule.name_pattern.fullmatch(candidate):
            for set_name in rule.exclude_property_sets:
                values.pop(set_name, None)
            for set_name, properties in rule.values.items():
                values.setdefault(set_name, {}).update(properties)
    return values


def property_sets_to_delete_for_name(name: str | None, config: MappingConfig) -> tuple[str, ...]:
    candidate = name or ""
    if any(pattern.fullmatch(candidate) for pattern in config.exclude_name_patterns):
        return ()

    property_sets = list(config.delete_property_sets)
    for rule in config.rules:
        if rule.name_pattern.fullmatch(candidate):
            property_sets.extend(rule.delete_property_sets)
    return tuple(dict.fromkeys(property_sets))

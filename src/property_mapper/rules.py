from __future__ import annotations

from .config import MappingConfig


def property_sets_for_name(name: str | None, config: MappingConfig) -> tuple[str, ...]:
    candidate = name or ""
    if any(pattern.fullmatch(candidate) for pattern in config.exclude_name_patterns):
        return ()

    property_sets = list(config.base_property_sets)
    for rule in config.rules:
        if rule.name_pattern.fullmatch(candidate):
            property_sets.extend(rule.property_sets)
    return tuple(dict.fromkeys(property_sets))

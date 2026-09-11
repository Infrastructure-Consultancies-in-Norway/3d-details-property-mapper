from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

CATALOG_URL = (
    "https://github.com/Infrastructure-Consultancies-in-Norway/SnacksDto/"
    "releases/download/0.1.0-alpha/snacks.json"
)
CATALOG_SHA256 = "33f4601aa617c63323a87fc8a508328bd3fa118cb4520fa728df064cdbe8020d"


class CatalogError(ValueError):
    """Raised when a SNACKS catalog is incomplete or inconsistent."""


@dataclass(frozen=True)
class CatalogProperty:
    name: str
    datatype: str


@dataclass(frozen=True)
class CatalogPropertySet:
    name: str
    properties: tuple[CatalogProperty, ...]


def _verified_bytes(content: bytes) -> bytes:
    digest = hashlib.sha256(content).hexdigest()
    if digest != CATALOG_SHA256:
        raise CatalogError(
            f"SNACKS catalog checksum mismatch: expected {CATALOG_SHA256}, got {digest}"
        )
    return content


def load_catalog_data(cache_path: Path, source_path: Path | None = None) -> Any:
    if source_path is not None:
        content = source_path.read_bytes()
    elif cache_path.exists():
        content = cache_path.read_bytes()
    else:
        try:
            with urlopen(CATALOG_URL, timeout=30) as response:  # noqa: S310
                content = response.read()
        except OSError as error:
            raise CatalogError(f"Could not download SNACKS catalog: {error}") from error
        _verified_bytes(content)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(cache_path)

    try:
        return json.loads(_verified_bytes(content).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogError(f"SNACKS catalog is not valid UTF-8 JSON: {error}") from error


def parse_catalog(data: Any, required_sets: tuple[str, ...]) -> dict[str, CatalogPropertySet]:
    if not isinstance(data, list):
        raise CatalogError("SNACKS catalog must be a JSON array")

    requested = set(required_sets)
    found: dict[str, CatalogPropertySet] = {}
    for raw_set in data:
        if not isinstance(raw_set, dict) or raw_set.get("Name") not in requested:
            continue
        set_name = raw_set["Name"]
        if set_name in found:
            raise CatalogError(f"Duplicate property set in catalog: {set_name}")
        raw_properties = raw_set.get("Properties")
        if not isinstance(raw_properties, list):
            raise CatalogError(f"{set_name}.Properties must be a list")

        properties: list[CatalogProperty] = []
        names: set[str] = set()
        for raw_property in raw_properties:
            if not isinstance(raw_property, dict):
                raise CatalogError(f"{set_name} contains an invalid property")
            color = str(raw_property.get("RequirementColor", "")).strip().casefold()
            required = raw_property.get("Required") is True
            if color != "svart" or not required:
                continue
            name = raw_property.get("PropertyName")
            datatype = raw_property.get("Datatype")
            if not isinstance(name, str) or not name.strip():
                raise CatalogError(f"{set_name} contains a required property without a name")
            if name in names:
                raise CatalogError(f"Duplicate property {set_name}.{name}")
            if not isinstance(datatype, str) or not datatype.startswith("Ifc"):
                raise CatalogError(f"{set_name}.{name} has an invalid IFC datatype")
            names.add(name)
            properties.append(CatalogProperty(name=name, datatype=datatype))

        found[set_name] = CatalogPropertySet(name=set_name, properties=tuple(properties))

    missing = requested - set(found)
    if missing:
        raise CatalogError(f"Missing property sets: {', '.join(sorted(missing))}")
    return found

# Agent instructions

## Purpose

This repository enriches IFC element occurrences with SNACKS property sets and
example values. Keep the implementation focused on this workflow; it is not a
general-purpose IFC graph transformation engine.

## Canonical environment and commands

- Use Python 3.12 from `.venv` on Windows.
- Install with `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.
- Run tests with `.\.venv\Scripts\python.exe -m pytest`.
- Run lint with `.\.venv\Scripts\python.exe -m ruff check .`.
- Run the CLI with `.\.venv\Scripts\snacks-ifc.exe`.

## Repository boundaries

- Treat `ifc-files/input/` as immutable source data. Never write in place.
- Write generated IFC files only below `ifc-files/output/` or pytest temporary
  directories. Generated outputs are not committed by default.
- Use IfcOpenShell APIs for IFC reads and writes. Never edit STEP text directly.
- Preserve schema, geometry, placements, units, GlobalIds, and unrelated
  relationships and properties. The current real fixture is IFC2X3.
- Identify occurrences by GlobalId and IFC class, never by unstable STEP IDs.
- Keep catalog loading, rule evaluation, IFC mutation, and file orchestration in
  separate modules.

## Mapping contract

- `config/mapping.yaml` is the source of truth for name-based assignment rules.
- Rules target direct occurrence property sets. Do not silently treat inherited
  type property sets as direct occurrence sets.
- Match decoded IFC names with configured case-insensitive regular expressions.
- Validate the complete config and SNACKS catalog before mutating a model.
- Use only property-set names present in the pinned SNACKS catalog. Do not invent
  material-specific sets to fill catalog gaps.
- Include black required properties and skip gray optional properties.
- Resolve values as SampleValue, first RecommendedValues, then first
  AllowedValues. Preserve valid false and zero values.

## IFC mutation safety

- Update one existing direct property set or create one; never accumulate
  duplicate property sets, relationships, or properties on repeated runs.
- Fail before mutation when direct duplicate property sets or incompatible
  existing property datatypes are found.
- IFC2X3 rooted entities must have valid OwnerHistory.
- Write to a temporary sibling, reopen and validate it, then atomically replace
  the requested output. A failed run must not replace a valid prior output.
- Idempotency is semantic rather than byte-for-byte: repeated runs retain the
  same managed values, counts, and existing managed property-set GlobalIds.

## Testing

- Add focused unit tests for config, catalog, matching, and conversion changes.
- IFC changes require integration tests that write to a temporary directory and
  reopen the result with IfcOpenShell.
- Every bug fix includes a regression test.
- Keep tests offline by injecting or caching catalog data.
- Verify the input fixture remains byte-identical after integration tests.

## Reference repository

`E:\COWIGit\IfcPropertyTools` is a read-only, non-authoritative reference for
IfcOpenShell patterns. Do not edit it, import it by path, or copy its graph
engine, mutable global workflow, legacy packaging, logging mandates, lossy
truthiness fallbacks, or swallowed write errors. Reuse ideas only when supported
by local tests.

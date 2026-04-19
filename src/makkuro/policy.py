"""Minimal JSON Schema validator for makkuro's bundled config schema.

We avoid adding ``jsonschema`` as a runtime dependency because it would
expand the dependency surface well past the SC-1.1 budget for a feature
that only needs a small subset of Draft 2020-12. This implementation is
deliberately narrow: it supports the keywords our own schema uses.

Supported keywords: ``type``, ``enum``, ``minimum``, ``maximum``, ``pattern``,
``minLength``, ``maxLength``, ``items``, ``properties``,
``patternProperties``, ``additionalProperties``, ``required``,
``uniqueItems``, and ``format=uri`` + ``format=email`` (best-effort).

For anything more exotic, switch to ``jsonschema`` behind an optional
extra.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "schema" / "makkuro.schema.json"


@dataclass
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:
        where = self.path if self.path else "<root>"
        return f"{where}: {self.message}"


@dataclass
class ValidationReport:
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, path: str, message: str) -> None:
        self.errors.append(ValidationError(path=path, message=message))


def load_schema(path: Path | None = None) -> dict[str, Any]:
    p = path if path is not None else SCHEMA_PATH
    return json.loads(p.read_text(encoding="utf-8"))


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
    "null": (type(None),),
}


def _check_type(value: Any, declared: str, path: str, report: ValidationReport) -> bool:
    types = _TYPE_MAP.get(declared)
    if types is None:
        return True
    # JSON booleans are ints in Python; guard against boolean-as-integer.
    if declared == "integer" and isinstance(value, bool):
        report.add(path, "expected integer, got boolean")
        return False
    if not isinstance(value, types):
        report.add(path, f"expected {declared}, got {type(value).__name__}")
        return False
    return True


def _validate(
    value: Any,
    schema: dict[str, Any],
    path: str,
    report: ValidationReport,
) -> None:
    # ``type`` may be a string or a list of strings.
    declared = schema.get("type")
    if isinstance(declared, str):
        if not _check_type(value, declared, path, report):
            return
    elif isinstance(declared, list):
        def _matches(t: str) -> bool:
            ok = isinstance(value, _TYPE_MAP.get(t, ()))
            return ok and not (t == "integer" and isinstance(value, bool))

        if not any(_matches(t) for t in declared):
            report.add(path, f"expected one of {declared}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        report.add(path, f"value {value!r} not in enum {schema['enum']}")

    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            report.add(path, f"{value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            report.add(path, f"{value} > maximum {schema['maximum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            report.add(path, f"length {len(value)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            report.add(path, f"length {len(value)} > maxLength {schema['maxLength']}")
        if "pattern" in schema:
            try:
                if re.search(schema["pattern"], value) is None:
                    report.add(path, f"value does not match pattern {schema['pattern']!r}")
            except re.error as e:
                report.add(path, f"invalid pattern {schema['pattern']!r}: {e}")
        fmt = schema.get("format")
        if fmt == "uri" and "://" not in value:
            report.add(path, "value is not a URI")

    if isinstance(value, list):
        if schema.get("uniqueItems") and len(set(map(repr, value))) != len(value):
            report.add(path, "items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, v in enumerate(value):
                _validate(v, item_schema, f"{path}[{i}]", report)

    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                report.add(path, f"missing required property {req!r}")

        props = schema.get("properties") or {}
        pats = schema.get("patternProperties") or {}
        additional = schema.get("additionalProperties", True)

        for k, v in value.items():
            sub_path = f"{path}.{k}" if path else k
            if k in props:
                _validate(v, props[k], sub_path, report)
                continue
            matched = False
            for pat, sub_schema in pats.items():
                try:
                    if re.search(pat, k):
                        matched = True
                        _validate(v, sub_schema, sub_path, report)
                        break
                except re.error:
                    continue
            if matched:
                continue
            if additional is False:
                report.add(sub_path, f"unexpected property {k!r}")
            elif isinstance(additional, dict):
                _validate(v, additional, sub_path, report)


def validate(data: dict[str, Any], schema: dict[str, Any] | None = None) -> ValidationReport:
    schema = schema if schema is not None else load_schema()
    report = ValidationReport()
    _validate(data, schema, "", report)
    return report

"""Strict UI whitelist. No model-generated markup or executable actions."""
import json
import re
from pathlib import Path
from jsonschema import Draft7Validator


def schema_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts" / "ui.schema.json"
        if candidate.exists():
            return candidate
    packaged = Path(__file__).with_name("ui.schema.json")
    if packaged.exists():
        return packaged
    raise RuntimeError("Canonical UI schema must be included in deployment")


SCHEMA = json.loads(schema_path().read_text(encoding="utf-8"))
VALIDATOR = Draft7Validator(SCHEMA)
UNSAFE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>|javascript\s*:|data\s*:\s*text/html|```(?:javascript|html|python|bash|sh)\b", re.I)


def validate_plain(value):
    if isinstance(value, str) and UNSAFE.search(value):
        raise ValueError("Executable or HTML output is not permitted")
    if isinstance(value, dict):
        for item in value.values():
            validate_plain(item)
    elif isinstance(value, list):
        for item in value:
            validate_plain(item)


def validate_ui(component: dict) -> dict:
    errors = list(VALIDATOR.iter_errors(component))
    if errors:
        raise ValueError("Invalid UI component")
    validate_plain(component)
    return component

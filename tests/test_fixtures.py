import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "annotation.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_valid_fixtures_pass_schema_and_semantics():
    paths = sorted((ROOT / "examples" / "valid").glob("*.json"))
    assert len(paths) >= 10
    for path in paths:
        document = load(path)
        assert list(VALIDATOR.iter_errors(document)) == [], path.name
        assert validate_semantics(document) == [], path.name


def test_all_invalid_fixtures_fail_schema_or_semantics():
    paths = sorted((ROOT / "examples" / "invalid").glob("*.json"))
    assert len(paths) >= 10
    for path in paths:
        document = load(path)
        schema_errors = list(VALIDATOR.iter_errors(document))
        semantic_errors = validate_semantics(document) if not schema_errors else []
        assert schema_errors or semantic_errors, f"{path.name} unexpectedly passed"

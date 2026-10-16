import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "annotation.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

# Semantic fixtures must pass the schema and fail with this code.
# Schema fixtures must fail JSON Schema; semantics are not the accepting check.
INVALID_EXPECTATIONS = {
    "01-version.json": ("schema", None),
    "02-missing-language.json": ("schema", None),
    "03-duplicate-token-id.json": ("semantics", "duplicate_token_id"),
    "04-token-out-of-bounds.json": ("semantics", "token_range"),
    "05-unknown-sentence.json": ("semantics", "unknown_sentence"),
    "06-unknown-head.json": ("semantics", "unknown_head"),
    "07-self-head.json": ("semantics", "self_head"),
    "08-root-has-head.json": ("semantics", "root_head"),
    "09-sentence-out-of-bounds.json": ("semantics", "sentence_range"),
    "10-boolean-coordinate.json": ("schema", None),
    "11-overlapping-tokens.json": ("semantics", "overlapping_token_ranges"),
    "12-whitespace-in-word.json": ("semantics", "whitespace_in_word_surface"),
    "13-missing-head.json": ("semantics", "missing_head"),
    "14-token-outside-sentence.json": ("semantics", "token_outside_sentence"),
    "15-duplicate-sentence-id.json": ("semantics", "duplicate_sentence_id"),
    "16-incomplete-complete.json": ("semantics", "incomplete_complete_analysis"),
    "17-head-cycle.json": ("semantics", "head_cycle"),
    "18-token-order.json": ("semantics", "token_order"),
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_valid_fixtures_pass_schema_and_semantics():
    paths = sorted((ROOT / "examples" / "valid").glob("*.json"))
    assert len(paths) >= 11
    for path in paths:
        document = load(path)
        assert list(VALIDATOR.iter_errors(document)) == [], path.name
        assert validate_semantics(document) == [], path.name


def test_invalid_fixtures_match_expected_check():
    paths = sorted((ROOT / "examples" / "invalid").glob("*.json"))
    assert {path.name for path in paths} == set(INVALID_EXPECTATIONS)
    for path in paths:
        layer, code = INVALID_EXPECTATIONS[path.name]
        document = load(path)
        schema_errors = list(VALIDATOR.iter_errors(document))
        if layer == "schema":
            assert schema_errors, path.name
            continue
        assert schema_errors == [], path.name
        semantic_codes = {issue.code for issue in validate_semantics(document)}
        assert code in semantic_codes, f"{path.name}: {semantic_codes}"

from copy import deepcopy
from pathlib import Path
import json

from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

SCHEMA = json.loads(Path("schemas/annotation.schema.json").read_text(encoding="utf-8"))


def valid_document():
    text = "Кот спит."
    return {
        "schema_version": "1.0",
        "document": {"id": "doc-1", "language": "ru", "text": text},
        "analysis": {
            "status": "complete",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": [
                {"id": "t1", "start": 0, "end": 3, "kind": "word", "sentence_id": "s1",
                 "lemma": "кот", "pos": "NOUN",
                 "syntax": {"role": "SUBJECT", "head": "t2", "relation": "nsubj"}},
                {"id": "t2", "start": 4, "end": 8, "kind": "word", "sentence_id": "s1",
                 "lemma": "спать", "pos": "VERB",
                 "syntax": {"role": "PREDICATE", "head": None, "relation": "root"}},
                {"id": "t3", "start": 8, "end": 9, "kind": "punctuation", "sentence_id": "s1"}
            ]
        }
    }


def schema_errors(doc):
    return list(Draft202012Validator(SCHEMA).iter_errors(doc))


def test_valid_document_passes_schema_and_semantics():
    doc = valid_document()
    assert schema_errors(doc) == []
    assert validate_semantics(doc) == []


def test_partial_analysis_allows_unannotated_word():
    doc = valid_document()
    doc["analysis"]["status"] = "partial"
    doc["analysis"]["tokens"][0].pop("syntax")
    assert schema_errors(doc) == []
    assert validate_semantics(doc) == []


def test_complete_analysis_requires_word_role():
    doc = valid_document()
    doc["analysis"]["tokens"][0].pop("syntax")
    assert any(i.code == "incomplete_complete_analysis" for i in validate_semantics(doc))


def test_duplicate_token_id_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][1]["id"] = "t1"
    assert any(i.code == "duplicate_token_id" for i in validate_semantics(doc))


def test_token_outside_text_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["end"] = 100
    assert any(i.code == "token_range" for i in validate_semantics(doc))


def test_unknown_sentence_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["sentence_id"] = "missing"
    assert any(i.code == "unknown_sentence" for i in validate_semantics(doc))


def test_unknown_head_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["syntax"]["head"] = "missing"
    assert any(i.code == "unknown_head" for i in validate_semantics(doc))


def test_self_head_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["syntax"]["head"] = "t1"
    assert any(i.code == "self_head" for i in validate_semantics(doc))


def test_root_must_have_null_head():
    doc = valid_document()
    doc["analysis"]["tokens"][1]["syntax"]["head"] = "t1"
    assert any(i.code == "root_head" for i in validate_semantics(doc))


def test_unicode_code_point_offsets_are_python_slice_offsets():
    text = "ёж 🛰️."
    doc = {
        "schema_version": "1.0",
        "document": {"id": "unicode", "language": "ru", "text": text},
        "analysis": {
            "status": "partial",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": [
                {"id": "w1", "start": 0, "end": 2, "kind": "word", "sentence_id": "s1"},
                {"id": "w2", "start": 3, "end": 5, "kind": "word", "sentence_id": "s1"}
            ]
        }
    }
    assert text[doc["analysis"]["tokens"][0]["start"]:doc["analysis"]["tokens"][0]["end"]] == "ёж"
    assert text[doc["analysis"]["tokens"][1]["start"]:doc["analysis"]["tokens"][1]["end"]] == "🛰️"
    assert validate_semantics(doc) == []


def test_overlapping_sentence_ranges_rejected():
    doc = valid_document()
    doc["analysis"]["sentences"].append({"id": "s2", "start": 2, "end": 5})
    assert any(i.code == "sentence_order" for i in validate_semantics(doc))


def test_cross_sentence_head_rejected():
    doc = valid_document()
    doc["document"]["text"] = "Кот. Спит."
    doc["analysis"]["sentences"] = [
        {"id": "s1", "start": 0, "end": 4},
        {"id": "s2", "start": 5, "end": 10}
    ]
    doc["analysis"]["tokens"] = [
        {"id": "t1", "start": 0, "end": 3, "kind": "word", "sentence_id": "s1",
         "syntax": {"role": "SUBJECT", "head": "t2", "relation": "nsubj"}},
        {"id": "t2", "start": 5, "end": 9, "kind": "word", "sentence_id": "s2",
         "syntax": {"role": "PREDICATE", "head": None, "relation": "root"}}
    ]
    assert any(i.code == "cross_sentence_head" for i in validate_semantics(doc))


def test_boolean_is_not_accepted_as_coordinate():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["start"] = True
    assert any(i.code == "token_range" for i in validate_semantics(doc))


def test_empty_text_and_empty_lists_are_valid_partial_document():
    doc = {
        "schema_version": "1.0",
        "document": {"id": "empty", "language": "ru", "text": ""},
        "analysis": {"status": "partial", "sentences": [], "tokens": []}
    }
    assert schema_errors(doc) == []
    assert validate_semantics(doc) == []


def test_unknown_schema_version_rejected_by_schema():
    doc = valid_document()
    doc["schema_version"] = "2.0"
    assert schema_errors(doc)


def test_invalid_token_kind_rejected_by_schema():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["kind"] = "unknown"
    assert schema_errors(doc)


def test_missing_document_language_rejected_by_schema():
    doc = valid_document()
    del doc["document"]["language"]
    assert schema_errors(doc)


def test_missing_required_token_id_rejected_by_schema():
    doc = valid_document()
    del doc["analysis"]["tokens"][0]["id"]
    assert schema_errors(doc)


def test_token_surface_may_contain_unicode_punctuation_and_whitespace_is_preserved():
    text = "Ёж	спит…"
    doc = {
        "schema_version": "1.0",
        "document": {"id": "whitespace", "language": "ru", "text": text},
        "analysis": {
            "status": "partial",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": [
                {"id": "t1", "start": 0, "end": 2, "kind": "word", "sentence_id": "s1"},
                {"id": "t2", "start": 3, "end": 7, "kind": "word", "sentence_id": "s1"}
            ]
        }
    }
    assert text == "Ёж\tспит…"
    assert validate_semantics(doc) == []


def test_sentence_range_outside_text_rejected():
    doc = valid_document()
    doc["analysis"]["sentences"][0]["end"] = len(doc["document"]["text"]) + 1
    assert any(i.code == "sentence_range" for i in validate_semantics(doc))


def test_token_start_order_is_checked():
    doc = valid_document()
    doc["analysis"]["tokens"][0], doc["analysis"]["tokens"][1] = (
        doc["analysis"]["tokens"][1], doc["analysis"]["tokens"][0]
    )
    assert any(i.code == "token_order" for i in validate_semantics(doc))

def test_overlapping_token_ranges_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][1]["start"] = 2
    assert any(i.code == "overlapping_token_ranges" for i in validate_semantics(doc))


def test_word_token_cannot_include_internal_whitespace():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["end"] = 5
    assert any(i.code == "whitespace_in_word_surface" for i in validate_semantics(doc))


def test_whitespace_only_punctuation_token_rejected():
    doc = {
        "schema_version": "1.0",
        "document": {"id": "space", "language": "ru", "text": " "},
        "analysis": {
            "status": "partial",
            "sentences": [{"id": "s1", "start": 0, "end": 1}],
            "tokens": [{"id": "p1", "start": 0, "end": 1, "kind": "punctuation", "sentence_id": "s1"}],
        },
    }
    assert any(i.code == "empty_token_surface" for i in validate_semantics(doc))


def test_token_must_be_contained_in_sentence():
    doc = valid_document()
    doc["analysis"]["sentences"][0]["end"] = 7
    assert any(i.code == "token_outside_sentence" for i in validate_semantics(doc))


def test_duplicate_sentence_id_rejected():
    doc = valid_document()
    doc["analysis"]["sentences"].append({"id": "s1", "start": 0, "end": 2})
    assert any(i.code == "duplicate_sentence_id" for i in validate_semantics(doc))


def test_non_root_relation_requires_head():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["syntax"]["head"] = None
    assert any(i.code == "missing_head" for i in validate_semantics(doc))


def test_head_cycle_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][1]["syntax"] = {
        "role": "PREDICATE", "head": "t1", "relation": "nsubj"
    }
    assert any(i.code == "head_cycle" for i in validate_semantics(doc))


def test_self_head_is_not_reported_as_longer_cycle():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["syntax"]["head"] = "t1"
    codes = {issue.code for issue in validate_semantics(doc)}
    assert "self_head" in codes
    assert "head_cycle" not in codes


def test_empty_token_range_rejected():
    doc = valid_document()
    doc["analysis"]["tokens"][0]["start"] = doc["analysis"]["tokens"][0]["end"]
    assert any(i.code == "token_range" for i in validate_semantics(doc))


def test_sentence_ranges_may_have_gaps():
    doc = valid_document()
    doc["document"]["text"] = "Кот.  Спит."
    doc["analysis"]["sentences"] = [
        {"id": "s1", "start": 0, "end": 4},
        {"id": "s2", "start": 6, "end": 11},
    ]
    doc["analysis"]["tokens"] = [
        {"id": "t1", "start": 0, "end": 3, "kind": "word", "sentence_id": "s1",
         "syntax": {"role": "SUBJECT", "head": None, "relation": "root"}},
        {"id": "t2", "start": 6, "end": 10, "kind": "word", "sentence_id": "s2",
         "syntax": {"role": "PREDICATE", "head": None, "relation": "root"}},
    ]
    assert validate_semantics(doc) == []


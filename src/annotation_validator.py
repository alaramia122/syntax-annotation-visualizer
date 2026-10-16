"""Semantic validation for annotation documents.

Structural validation is delegated to JSON Schema. This module validates
cross-field constraints that JSON Schema cannot conveniently express.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def validate_semantics(data: dict[str, Any]) -> list[ValidationIssue]:
    """Return semantic issues for a structurally valid document.

    Call JSON Schema validation first. This function is defensive and reports
    malformed structures rather than relying on unchecked indexing.
    """
    issues: list[ValidationIssue] = []
    document = data.get("document")
    analysis = data.get("analysis")
    if not isinstance(document, dict) or not isinstance(analysis, dict):
        return [ValidationIssue("structure", "$", "document and analysis must be objects")]

    text = document.get("text")
    sentences = analysis.get("sentences")
    tokens = analysis.get("tokens")
    if not isinstance(text, str) or not isinstance(sentences, list) or not isinstance(tokens, list):
        return [ValidationIssue("structure", "$", "text, sentences or tokens have an invalid type")]

    def add(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code, path, message))

    sentence_ids: set[str] = set()
    sentence_ranges: dict[str, tuple[int, int]] = {}
    previous_sentence_end = 0
    for index, sentence in enumerate(sentences):
        path = f"$.analysis.sentences[{index}]"
        if not isinstance(sentence, dict):
            add("sentence_type", path, "sentence must be an object")
            continue
        sid, start, end = sentence.get("id"), sentence.get("start"), sentence.get("end")
        if not isinstance(sid, str) or not sid:
            add("sentence_id", f"{path}.id", "sentence id must be a non-empty string")
            continue
        if sid in sentence_ids:
            add("duplicate_sentence_id", f"{path}.id", f"duplicate sentence id: {sid}")
        sentence_ids.add(sid)
        if not _valid_range(start, end, len(text)):
            add("sentence_range", path, "sentence range must satisfy 0 <= start <= end <= text length")
            continue
        sentence_ranges[sid] = (start, end)
        if start < previous_sentence_end:
            add("sentence_order", path, "sentence ranges must be ordered and non-overlapping")
        previous_sentence_end = max(previous_sentence_end, end)

    token_ids: set[str] = set()
    token_by_id: dict[str, dict[str, Any]] = {}
    previous_token_start = -1
    previous_token_end = -1
    for index, token in enumerate(tokens):
        path = f"$.analysis.tokens[{index}]"
        if not isinstance(token, dict):
            add("token_type", path, "token must be an object")
            continue
        tid, start, end = token.get("id"), token.get("start"), token.get("end")
        if not isinstance(tid, str) or not tid:
            add("token_id", f"{path}.id", "token id must be a non-empty string")
        elif tid in token_ids:
            add("duplicate_token_id", f"{path}.id", f"duplicate token id: {tid}")
        else:
            token_ids.add(tid)
            token_by_id[tid] = token

        if not _valid_range(start, end, len(text)) or start == end:
            add("token_range", path, "token range must satisfy 0 <= start < end <= text length")
            continue
        if start < previous_token_start:
            add("token_order", path, "tokens must be ordered by start coordinate")
        if start < previous_token_end:
            add("overlapping_token_ranges", path, "token ranges must not overlap")
        previous_token_start = start
        previous_token_end = max(previous_token_end, end)

        sid = token.get("sentence_id")
        if sid not in sentence_ids:
            add("unknown_sentence", f"{path}.sentence_id", f"unknown sentence id: {sid}")
        elif sid in sentence_ranges:
            s_start, s_end = sentence_ranges[sid]
            if start < s_start or end > s_end:
                add("token_outside_sentence", path, "token range must be contained in its sentence range")

        kind = token.get("kind")
        surface = text[start:end]
        if not surface or surface.isspace():
            add("empty_token_surface", path, "token must point to non-whitespace text")
        elif kind == "word" and any(character.isspace() for character in surface):
            add("whitespace_in_word_surface", path, "word token range must not include whitespace characters")
        syntax = token.get("syntax")
        if syntax is not None and isinstance(syntax, dict):
            head = syntax.get("head", "__missing__")
            if head != "__missing__" and head is not None and not isinstance(head, str):
                add("head_type", f"{path}.syntax.head", "head must be a token id or null")
            if head is not None and head != "__missing__" and isinstance(head, str) and head == tid:
                add("self_head", f"{path}.syntax.head", "token cannot be its own head")
            if syntax.get("relation") == "root" and head is not None:
                add("root_head", f"{path}.syntax.head", "root relation must have head null")
            if syntax.get("relation") != "root" and syntax.get("relation") and head is None:
                add("missing_head", f"{path}.syntax.head", "non-root relation with a relation label must reference a head")

    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            continue
        syntax = token.get("syntax")
        if not isinstance(syntax, dict):
            continue
        head = syntax.get("head")
        if isinstance(head, str):
            if head not in token_by_id:
                add("unknown_head", f"$.analysis.tokens[{index}].syntax.head", f"unknown head token id: {head}")
            else:
                own_sentence = token.get("sentence_id")
                head_sentence = token_by_id[head].get("sentence_id")
                if own_sentence != head_sentence:
                    add("cross_sentence_head", f"$.analysis.tokens[{index}].syntax.head", "head must belong to the same sentence")

    status = analysis.get("status")
    if status == "complete":
        for index, token in enumerate(tokens):
            if isinstance(token, dict) and token.get("kind") == "word":
                syntax = token.get("syntax")
                if not isinstance(syntax, dict) or not syntax.get("role"):
                    add("incomplete_complete_analysis", f"$.analysis.tokens[{index}].syntax", "word token without a syntax role requires analysis.status='partial'")

    return issues


def _valid_range(start: Any, end: Any, text_length: int) -> bool:
    # bool is a subclass of int in Python, but must not be accepted as a coordinate.
    return (
        isinstance(start, int) and not isinstance(start, bool)
        and isinstance(end, int) and not isinstance(end, bool)
        and 0 <= start <= end <= text_length
    )

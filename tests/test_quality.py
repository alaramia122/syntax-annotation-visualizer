"""Комплексные проверки этапа 10: безопасность, Unicode, объём, регрессия.

Не подменяют модульные и интеграционные тесты — дополняют их сценариями,
которые в плане этапа 10 названы явно.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app import app
from src.document_loader import Accepted, Rejected, load_bytes

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "examples" / "valid"
INVALID = ROOT / "examples" / "invalid"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _word_token(
    token_id: str,
    start: int,
    end: int,
    *,
    lemma: str = "слово",
    role: str = "SUBJECT",
    head: str | None = None,
    relation: str = "root",
) -> dict:
    return {
        "id": token_id,
        "kind": "word",
        "sentence_id": "s1",
        "start": start,
        "end": end,
        "lemma": lemma,
        "pos": "NOUN",
        "syntax": {
            "role": role,
            "relation": relation,
            "head": head,
        },
    }


def test_reject_script_tag_does_not_break_loader():
    """Текст с «опасной» разметкой — обычные символы, документ принимается."""
    text = "Слово <script>alert(1)</script> конец"
    doc = {
        "schema_version": "1.0",
        "document": {"id": "xss", "language": "ru", "text": text},
        "analysis": {
            "status": "partial",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": [_word_token("t1", 0, 5, lemma="слово")],
        },
    }
    result = load_bytes(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
    assert isinstance(result, Accepted)


def test_uploaded_script_escaped_in_html(client):
    """В HTML ответ tojson не вставляет сырой <script> из текста документа."""
    from io import BytesIO

    text = "А <script>alert(1)</script> Б"
    doc = {
        "schema_version": "1.0",
        "document": {"id": "xss-html", "language": "ru", "text": text},
        "analysis": {
            "status": "partial",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": [_word_token("t1", 0, 1, lemma="а")],
        },
    }
    raw = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    response = client.post(
        "/upload",
        data={"file": (BytesIO(raw), "xss.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    html = response.get_data(as_text=True)
    # Сырой тег из пользовательского текста не должен попасть в разметку страницы
    assert "<script>alert(1)</script>" not in html
    assert "ANNOTATION_DOCUMENT" in html


def test_client_js_avoids_innerhtml():
    """Клиент не должен вставлять пользовательские строки через innerHTML."""
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert "outerHTML" not in js
    assert "textContent" in js
    assert "createTextNode" in js


def test_all_invalid_fixtures_rejected_via_http(client):
    paths = sorted(INVALID.glob("*.json"))
    assert len(paths) >= 15
    for path in paths:
        response = client.post(
            "/upload",
            data={"file": (path.open("rb"), path.name)},
            content_type="multipart/form-data",
        )
        assert response.status_code in (400, 422), path.name
        html = response.get_data(as_text=True)
        assert "Документ не принят" in html
        assert "ANNOTATION_DOCUMENT" not in html


def test_unicode_and_special_fixtures_accepted():
    for name in (
        "04-whitespace-unicode.json",
        "08-non-bmp.json",
        "11-newlines.json",
        "09-unknown-role.json",
    ):
        result = load_bytes((VALID / name).read_bytes())
        assert isinstance(result, Accepted), name


def test_long_text_about_10000_codepoints_accepted_and_timed():
    """Ориентир ТЗ: текст до 10 000 символов; фиксируем приём и время загрузки."""
    word = "слово"
    parts: list[str] = []
    while sum(len(p) for p in parts) < 10000:
        parts.append(word)
        parts.append(" ")
    text = "".join(parts)[:10000]
    assert len(text) == 10000

    tokens = []
    pos = 0
    idx = 0
    while pos < len(text):
        if text[pos] == " ":
            pos += 1
            continue
        start = pos
        while pos < len(text) and text[pos] != " ":
            pos += 1
        idx += 1
        if idx == 1:
            tokens.append(
                _word_token(
                    f"t{idx}",
                    start,
                    pos,
                    role="SUBJECT",
                    head=None,
                    relation="root",
                )
            )
        else:
            tokens.append(
                _word_token(
                    f"t{idx}",
                    start,
                    pos,
                    role="OBJECT",
                    head="t1",
                    relation="obj",
                )
            )

    doc = {
        "schema_version": "1.0",
        "document": {"id": "long-10k", "language": "ru", "text": text},
        "analysis": {
            "status": "complete",
            "sentences": [{"id": "s1", "start": 0, "end": len(text)}],
            "tokens": tokens,
        },
    }
    raw = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    assert len(raw) < 2 * 1024 * 1024

    started = time.perf_counter()
    result = load_bytes(raw)
    elapsed = time.perf_counter() - started

    if isinstance(result, Rejected):
        pytest.fail("отклонён: " + "; ".join(result.errors[:5]))
    assert isinstance(result, Accepted)
    assert len(result.document["document"]["text"]) == 10000
    assert elapsed < 5.0, f"load_bytes слишком долгий: {elapsed:.3f} с"


def test_oversized_rejected_before_parse():
    raw = b"x" * (2 * 1024 * 1024 + 1)
    result = load_bytes(raw)
    assert isinstance(result, Rejected)
    assert result.http_status == 413


def test_unknown_top_level_field_rejected():
    """Дополнительные поля в корне запрещены схемой (additionalProperties: false)."""
    base = json.loads((VALID / "01-basic.json").read_text(encoding="utf-8"))
    base["unexpected"] = True
    result = load_bytes(json.dumps(base).encode("utf-8"))
    assert isinstance(result, Rejected)
    assert result.http_status == 422


def test_regression_valid_fixture_count():
    """Регрессия: число валидных/невалидных фикстур не должно «случайно» сжаться."""
    valid = list(VALID.glob("*.json"))
    invalid = list(INVALID.glob("*.json"))
    assert len(valid) >= 11
    assert len(invalid) >= 18

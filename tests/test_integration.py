"""Сквозные сценарии этапа 9: загрузка, отказ, смена документа, справка.

Проверяем, что после ответа сервера на странице нет «старого» документа
и что основные маршруты согласованы. Клиентский JS здесь не исполняется —
фиксируется HTML и HTTP.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import app

ROOT = Path(__file__).resolve().parents[1]
VALID_DIR = ROOT / "examples" / "valid"
INVALID_DIR = ROOT / "examples" / "invalid"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def _upload(client, path: Path):
    return client.post(
        "/upload",
        data={"file": (path.open("rb"), path.name)},
        content_type="multipart/form-data",
    )


def test_demo_page_embeds_document(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "ANNOTATION_DOCUMENT" in html
    assert "annotated-text" in html
    assert "token-card" in html
    assert "dictionary-block" in html
    assert "Файл:" not in html


def test_valid_upload_shows_new_document_not_errors(client):
    path = VALID_DIR / "11-newlines.json"
    response = _upload(client, path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Документ не принят" not in html
    assert "example-011" in html
    assert "11-newlines.json" in html
    assert "ANNOTATION_DOCUMENT" in html


def test_invalid_upload_clears_document(client):
    """После отказа нет текста и карточки — только список ошибок."""
    ok = _upload(client, VALID_DIR / "01-basic.json")
    assert ok.status_code == 200
    assert "ANNOTATION_DOCUMENT" in ok.get_data(as_text=True)

    bad_path = next(INVALID_DIR.glob("*.json"))
    bad = _upload(client, bad_path)
    assert bad.status_code in (400, 422)
    html = bad.get_data(as_text=True)
    assert "Документ не принят" in html
    assert "ANNOTATION_DOCUMENT" not in html
    assert 'id="annotated-text"' not in html
    assert 'id="token-card"' not in html


def test_second_valid_upload_replaces_previous(client):
    """Два подряд успешных ответа — в HTML только второй документ."""
    first = _upload(client, VALID_DIR / "01-basic.json")
    assert first.status_code == 200
    assert "01-basic.json" in first.get_data(as_text=True)

    second = _upload(client, VALID_DIR / "11-newlines.json")
    assert second.status_code == 200
    html = second.get_data(as_text=True)
    assert "11-newlines.json" in html
    assert "example-011" in html
    assert "01-basic.json" not in html


def test_upload_without_file(client):
    response = client.post("/upload", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Выберите JSON-файл" in html
    assert "ANNOTATION_DOCUMENT" not in html


def test_dictionary_independent_of_page_document(client):
    """Справка не зависит от того, какой документ сейчас на странице."""
    import app as app_module
    import src.dictionary as dict_module
    from src.dictionary import DictionaryLookup

    original_mod = dict_module.lookup
    original_app = app_module.lookup

    def fake_lookup(lemma, surface, opener=None):
        return DictionaryLookup(
            status="unavailable",
            source_name="тест",
            text=None,
            search_url="https://example.com/q",
        )

    dict_module.lookup = fake_lookup
    app_module.lookup = fake_lookup
    try:
        response = client.get("/dictionary?lemma=кот&surface=Кот")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "unavailable"
        assert data["search_url"] == "https://example.com/q"
    finally:
        dict_module.lookup = original_mod
        app_module.lookup = original_app


def test_static_assets_available(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "loadDictionary" in js
    assert "renderGroupedOccurrences" in js

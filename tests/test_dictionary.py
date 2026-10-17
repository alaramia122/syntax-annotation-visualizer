"""Проверки справочного порта: контракт lookup и обработка отказа."""
from __future__ import annotations

import json
from urllib.error import URLError

from src.dictionary import DictionaryLookup, lookup


class _FakeResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_lookup_ok_with_extract():
    payload = {
        "query": {
            "pages": {
                "1": {
                    "pageid": 1,
                    "title": "кот",
                    "extract": "Домашнее животное семейства кошачьих.",
                }
            }
        }
    }

    def opener(request, timeout=None):
        return _FakeResponse(payload)

    result = lookup("кот", "Кота", opener=opener)
    assert isinstance(result, DictionaryLookup)
    assert result.status == "ok"
    assert result.source_name == "Русский Викисловарь"
    assert "кошачьих" in (result.text or "")
    assert result.search_url and "search" in result.search_url


def test_lookup_missing_page():
    payload = {
        "query": {
            "pages": {
                "-1": {
                    "missing": "",
                    "title": "xyznonexistentword",
                }
            }
        }
    }

    def opener(request, timeout=None):
        return _FakeResponse(payload)

    result = lookup(None, "xyznonexistentword", opener=opener)
    assert result.status == "unavailable"
    assert result.search_url


def test_lookup_network_error():
    def opener(request, timeout=None):
        raise URLError("network down")

    result = lookup("кот", "кот", opener=opener)
    assert result.status == "unavailable"
    assert result.source_name == "Русский Викисловарь"
    assert result.search_url


def test_dictionary_route_returns_json():
    from app import app

    client = app.test_client()

    import app as app_module
    import src.dictionary as dict_module

    original = dict_module.lookup

    def fake_lookup(lemma, surface, opener=None):
        return DictionaryLookup(
            status="ok",
            source_name="тест",
            text="краткий текст",
            search_url="https://example.com/search",
        )

    dict_module.lookup = fake_lookup
    app_module.lookup = fake_lookup
    try:
        response = client.get("/dictionary?lemma=кот&surface=Кот")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["text"] == "краткий текст"
        assert data["source_name"] == "тест"
    finally:
        dict_module.lookup = original
        app_module.lookup = original

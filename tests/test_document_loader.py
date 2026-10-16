"""Тесты загрузчика документов."""
from pathlib import Path

from src.document_loader import Accepted, Rejected, load_bytes, load_schema

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "examples" / "valid"
INVALID = ROOT / "examples" / "invalid"


def _read(path: Path) -> bytes:
    return path.read_bytes()


def test_valid_fixture_accepted():
    raw = _read(VALID / "01-basic.json")
    result = load_bytes(raw)
    assert isinstance(result, Accepted)
    assert result.document["schema_version"] == "1.0"


def test_all_valid_fixtures_accepted():
    schema = load_schema()
    paths = sorted(VALID.glob("*.json"))
    assert len(paths) >= 11
    for path in paths:
        result = load_bytes(_read(path), schema=schema)
        assert isinstance(result, Accepted), path.name


def test_oversized_rejected_with_413():
    raw = b"{" + b"a" * (2 * 1024 * 1024) + b"}"
    result = load_bytes(raw, max_bytes=100)
    assert isinstance(result, Rejected)
    assert result.http_status == 413
    assert any("МиБ" in msg for msg in result.errors)


def test_invalid_utf8_rejected_with_400():
    result = load_bytes(b"\xff\xfe not utf-8")
    assert isinstance(result, Rejected)
    assert result.http_status == 400
    assert any("UTF-8" in msg for msg in result.errors)


def test_invalid_json_rejected_with_400():
    result = load_bytes(b"{not json")
    assert isinstance(result, Rejected)
    assert result.http_status == 400


def test_non_object_root_rejected_with_422():
    result = load_bytes(b"[1, 2, 3]")
    assert isinstance(result, Rejected)
    assert result.http_status == 422
    assert any("объектом" in msg for msg in result.errors)


def test_schema_error_stops_before_semantics():
    # Неизвестная версия схемы — структурная ошибка.
    raw = _read(INVALID / "01-version.json")
    result = load_bytes(raw)
    assert isinstance(result, Rejected)
    assert result.http_status == 422
    assert result.errors  # есть хотя бы одно сообщение


def test_semantic_error_returns_422():
    raw = _read(INVALID / "03-duplicate-token-id.json")
    result = load_bytes(raw)
    assert isinstance(result, Rejected)
    assert result.http_status == 422
    assert any("duplicate" in msg.lower() or "id" in msg.lower() for msg in result.errors)


def test_empty_document_is_accepted():
    raw = _read(VALID / "03-empty.json")
    result = load_bytes(raw)
    assert isinstance(result, Accepted)

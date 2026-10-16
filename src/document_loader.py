"""Загрузка и проверка JSON-документа с синтаксической разметкой.

На входе — сырые байты файла. На выходе — либо принятый документ,
либо отказ с HTTP-кодом и списком понятных сообщений об ошибках.

Порядок проверок фиксирован архитектурой (ADR-002):
размер → UTF-8 → JSON → объект → JSON Schema → семантика.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

# Лимит совпадает с настройкой Flask MAX_CONTENT_LENGTH.
DEFAULT_MAX_BYTES = 2 * 1024 * 1024

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "annotation.schema.json"


@dataclass(frozen=True)
class Accepted:
    """Документ прошёл все проверки и может быть показан клиенту."""

    document: dict[str, Any]


@dataclass(frozen=True)
class Rejected:
    """Документ отклонён. http_status — рекомендуемый код ответа."""

    http_status: int
    errors: list[str]


def load_schema() -> dict[str, Any]:
    """Читает JSON Schema с диска. Вынесено отдельно, чтобы можно было подменить в тестах."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_bytes(
    raw: bytes,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    schema: dict[str, Any] | None = None,
) -> Accepted | Rejected:
    """Разбирает и проверяет документ из сырых байт.

    Параметр schema нужен тестам: можно передать уже загруженную схему
    и не ходить на диск на каждый вызов.
    """
    if len(raw) > max_bytes:
        return Rejected(
            413,
            [f"Файл превышает допустимый размер {max_bytes // (1024 * 1024)} МиБ."],
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exp:
        return Rejected(400, [f"Не удалось прочитать JSON в UTF-8: {exp}"])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exp:
        return Rejected(400, [f"Не удалось прочитать JSON в UTF-8: {exp}"])

    if not isinstance(data, dict):
        return Rejected(422, ["Корневое значение JSON должно быть объектом."])

    # Сначала схема: если форма кривая, семантику не запускаем —
    # иначе сообщения ссылаются на поля, которых по сути нет.
    active_schema = schema if schema is not None else load_schema()
    schema_errors = sorted(
        Draft202012Validator(active_schema).iter_errors(data),
        key=lambda err: list(map(str, err.absolute_path)),
    )
    if schema_errors:
        messages = [
            f"{'.'.join(map(str, err.absolute_path)) or '$'}: {err.message}"
            for err in schema_errors
        ]
        return Rejected(422, messages)

    semantic_issues = validate_semantics(data)
    if semantic_issues:
        messages = [f"{issue.path}: {issue.message}" for issue in semantic_issues]
        return Rejected(422, messages)

    return Accepted(data)

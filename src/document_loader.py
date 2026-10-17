"""Загрузка и проверка JSON-документа с синтаксической разметкой.

Модуль — единственная точка, где сырые байты превращаются в документ,
которому можно доверять на стороне сервера (ADR-002).

Вход: содержимое загруженного файла как bytes.
Выход: либо Accepted с проверенным словарём документа, либо Rejected
с рекомендуемым HTTP-кодом и списком сообщений для пользователя.

Порядок проверок намеренно жёсткий и зафиксирован архитектурой:
  1) размер файла;
  2) декодирование UTF-8;
  3) разбор JSON;
  4) корень должен быть объектом;
  5) JSON Schema (форма и типы);
  6) семантика (ссылки, диапазоны, head и т.д.).

Семантику не запускаем, если схема уже не прошла: иначе сообщения
ссылаются на поля, которых в «нормальной» форме документа нет, и
пользователю труднее понять, что именно исправить.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

# Совпадает с MAX_CONTENT_LENGTH у Flask. Дублируем константу здесь,
# чтобы загрузчик можно было вызывать и без веб-слоя (тесты, скрипты).
DEFAULT_MAX_BYTES = 2 * 1024 * 1024

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "annotation.schema.json"


@dataclass(frozen=True)
class Accepted:
    """Документ прошёл все проверки и может быть отдан в шаблон/клиент.

    document — словарь контракта v1.0; дальше его не «чинят» и не
    дополняют на сервере.
    """

    document: dict[str, Any]


@dataclass(frozen=True)
class Rejected:
    """Документ отклонять. Веб-слой копирует http_status в ответ.

    errors — уже человекочитаемые строки (путь поля + текст), без
    стека и внутренних исключений.
    """

    http_status: int
    errors: list[str]


def load_schema() -> dict[str, Any]:
    """Читает JSON Schema с диска.

    Вынесено отдельно, чтобы в тестах можно было передать уже
    загруженную схему через параметр schema у load_bytes и не
    дергать файловую систему на каждый кейс.
    """
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_bytes(
    raw: bytes,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    schema: dict[str, Any] | None = None,
) -> Accepted | Rejected:
    """Разбирает и проверяет документ из сырых байт.

    Не знает про HTTP multipart и имя файла: это зона веб-слоя.
    Здесь только «байты → Accepted|Rejected».

    Параметр schema опционален: если передан, используется он;
    иначе схема читается с диска. Удобно для пакетных тестов.
    """
    # Лимит проверяем до любых разборов, чтобы не тратить память
    # и CPU на заведомо слишком большой файл.
    if len(raw) > max_bytes:
        return Rejected(
            413,
            [f"Файл превышает допустимый размер {max_bytes // (1024 * 1024)} Мб."],
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exp:
        # Сообщение включает причину от декодера — так проще отличить
        # «битая кодировка» от «битый JSON».
        return Rejected(400, [f"Не удалось прочитать JSON в UTF-8: {exp}"])

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exp:
        # Тот же префикс, что и у UTF-8: для UI это один класс ошибок
        # «файл не читается как JSON».
        return Rejected(400, [f"Не удалось прочитать JSON в UTF-8: {exp}"])

    if not isinstance(data, dict):
        # Схема тоже отвергнет не-объект, но явное сообщение на русском
        # понятнее, чем стандартный текст jsonschema.
        return Rejected(422, ["Корневое значение JSON должно быть объектом."])

    active_schema = schema if schema is not None else load_schema()
    schema_errors = sorted(
        Draft202012Validator(active_schema).iter_errors(data),
        key=lambda err: list(map(str, err.absolute_path)),
    )
    if schema_errors:
        # Путь в стиле JSON Pointer / dotted path: пустой путь → "$".
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

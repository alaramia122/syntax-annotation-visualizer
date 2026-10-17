"""Точка входа Flask-приложения.

Веб-слой сознательно тонкий: принять запрос, вызвать загрузчик,
отдать шаблон. Разбор JSON, схема и семантика живут в
src.document_loader — так проще тестировать проверки без HTTP.

Маршруты:
  GET  /            — страница с демонстрационным документом;
  POST /upload      — загрузка пользовательского JSON;
  GET  /dictionary  — краткая справка по слову (не влияет на код страницы).

Лимит размера задаётся и здесь (MAX_CONTENT_LENGTH), и в загрузчике.
Flask отсекает слишком большое тело до нашего кода (ответ 413 через
errorhandler); загрузчик дополнительно страхует вызовы вне веб-контекста.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from src.document_loader import DEFAULT_MAX_BYTES, Accepted, load_bytes
from src.dictionary import lookup

ROOT = Path(__file__).resolve().parent
DEMO_PATH = ROOT / "examples" / "valid" / "01-basic.json"


def load_demo() -> dict[str, Any]:
    """Демонстрационный документ для первого открытия страницы.

    Файл из examples/valid уже проходит схему и семантику; отдельная
    проверка при старте не делается, чтобы не замедлять GET /.
    """
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Собирает приложение. test_config нужен pytest/test_client."""
    app = Flask(__name__)
    app.config.from_mapping(MAX_CONTENT_LENGTH=DEFAULT_MAX_BYTES)
    if test_config:
        app.config.update(test_config)

    @app.get("/")
    def index():
        # Пустой экран при первом заходе хуже, чем сразу показать пример:
        # так видны линии ролей, карточка и общая компоновка.
        document = load_demo()
        return render_template(
            "index.html",
            document=document,
            errors=[],
            filename=None,
        )

    @app.post("/upload")
    def upload():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            # Нет файла — ошибка интерфейса, не ошибка формата документа.
            return (
                render_template(
                    "index.html",
                    document=None,
                    errors=["Выберите JSON-файл для загрузки."],
                    filename=None,
                ),
                400,
            )

        # Читаем на байт больше лимита: так отличаем «ровно max_bytes»
        # (ещё допустимо) от «больше max_bytes» (отклонить), даже если
        # Flask по какой-то причине не сработал раньше.
        raw = uploaded.read(DEFAULT_MAX_BYTES + 1)
        result = load_bytes(raw, max_bytes=DEFAULT_MAX_BYTES)

        if isinstance(result, Accepted):
            return render_template(
                "index.html",
                document=result.document,
                errors=[],
                filename=uploaded.filename,
            )

        # При отказе предыдущий документ на странице не сохраняем:
        # в шаблон уходит document=None и список ошибок.
        return (
            render_template(
                "index.html",
                document=None,
                errors=result.errors,
                filename=uploaded.filename,
            ),
            result.http_status,
        )

    @app.get("/dictionary")
    def dictionary():
        """Краткая справка по слову. Отказ источника не меняет код страницы документа.

        Клиент вызывает маршрут после выбора слова; карточка уже заполнена.
        """
        lemma = request.args.get("lemma") or None
        surface = request.args.get("surface") or ""
        if lemma is not None and not str(lemma).strip():
            lemma = None
        result = lookup(lemma, surface)
        body = {
            "status": result.status,
            "source_name": result.source_name,
            "text": result.text,
            "search_url": result.search_url,
        }
        return jsonify(body)

    @app.errorhandler(413)
    def too_large(_error):
        # Срабатывает, когда Flask сам отсёк тело по MAX_CONTENT_LENGTH,
        # до входа в upload(). Текст совпадает с сообщением загрузчика.
        return (
            render_template(
                "index.html",
                document=None,
                errors=["Файл превышает допустимый размер 2 МиБ."],
                filename=None,
            ),
            413,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)

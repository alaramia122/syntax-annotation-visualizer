"""Точка входа Flask-приложения.

Веб-слой только принимает запрос, вызывает загрузчик и отдаёт шаблон.
Разбор JSON и проверки живут в src.document_loader.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request

from src.document_loader import DEFAULT_MAX_BYTES, Accepted, load_bytes

ROOT = Path(__file__).resolve().parent
DEMO_PATH = ROOT / "examples" / "valid" / "01-basic.json"


def load_demo() -> dict[str, Any]:
    """Демонстрационный документ для первого открытия страницы."""
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(MAX_CONTENT_LENGTH=DEFAULT_MAX_BYTES)
    if test_config:
        app.config.update(test_config)

    @app.get("/")
    def index():
        # При первом заходе показываем заранее проверенный пример,
        # чтобы интерфейс не был пустым.
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
            return (
                render_template(
                    "index.html",
                    document=None,
                    errors=["Выберите JSON-файл для загрузки."],
                    filename=None,
                ),
                400,
            )

        # Читаем на один байт больше лимита, чтобы отличить
        # «ровно лимит» от «чуть больше лимита».
        raw = uploaded.read(DEFAULT_MAX_BYTES + 1)
        result = load_bytes(raw, max_bytes=DEFAULT_MAX_BYTES)

        if isinstance(result, Accepted):
            return render_template(
                "index.html",
                document=result.document,
                errors=[],
                filename=uploaded.filename,
            )

        return (
            render_template(
                "index.html",
                document=None,
                errors=result.errors,
                filename=uploaded.filename,
            ),
            result.http_status,
        )

    @app.errorhandler(413)
    def too_large(_error):
        # Срабатывает, если Flask сам отсёк тело запроса по MAX_CONTENT_LENGTH.
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

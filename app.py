"""Flask entry point for the syntax annotation visualizer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request
from jsonschema import Draft202012Validator

from src.annotation_validator import validate_semantics

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schemas" / "annotation.schema.json"
DEMO_PATH = ROOT / "examples" / "valid" / "01-basic.json"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_demo() -> dict[str, Any]:
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def validate_document(data: Any) -> list[str]:
    """Return human-readable structural and semantic errors."""
    if not isinstance(data, dict):
        return ["Корневое значение JSON должно быть объектом."]
    schema_errors = sorted(
        Draft202012Validator(load_schema()).iter_errors(data),
        key=lambda error: list(map(str, error.absolute_path)),
    )
    if schema_errors:
        return [
            f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in schema_errors
        ]
    return [
        f"{issue.path}: {issue.message}"
        for issue in validate_semantics(data)
    ]


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES)
    if test_config:
        app.config.update(test_config)

    @app.get("/")
    def index():
        document = load_demo()
        return render_template("index.html", document=document, errors=[], filename=None)

    @app.post("/upload")
    def upload():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return render_template(
                "index.html", document=None,
                errors=["Выберите JSON-файл для загрузки."], filename=None
            ), 400
        try:
            raw = uploaded.read(MAX_UPLOAD_BYTES + 1)
            if len(raw) > MAX_UPLOAD_BYTES:
                return render_template(
                    "index.html", document=None,
                    errors=["Файл превышает допустимый размер 2 МиБ."],
                    filename=uploaded.filename
                ), 413
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return render_template(
                "index.html", document=None,
                errors=[f"Не удалось прочитать JSON в UTF-8: {exc}"],
                filename=uploaded.filename
            ), 400

        errors = validate_document(data)
        if errors:
            return render_template(
                "index.html", document=None, errors=errors,
                filename=uploaded.filename
            ), 422
        return render_template(
            "index.html", document=data, errors=[],
            filename=uploaded.filename
        )

    @app.errorhandler(413)
    def too_large(_error):
        return render_template(
            "index.html", document=None,
            errors=["Файл превышает допустимый размер 2 МиБ."],
            filename=None
        ), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=False)

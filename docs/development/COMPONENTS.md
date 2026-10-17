# Компоненты реализации (сводка)

Актуально на закрытии этапов 1–10. Подробности границ — в [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) и ADR.

| Модуль / путь | Назначение |
|---------------|------------|
| `app.py` | Маршруты `GET /`, `POST /upload`, `GET /dictionary`; тонкий веб-слой |
| `src/document_loader.py` | Байты → `Accepted` / `Rejected` (размер, UTF-8, JSON, схема, семантика) |
| `src/annotation_validator.py` | Семантические правила (id, диапазоны, head, …) |
| `src/dictionary.py` | Порт справки: `lookup` → статусы ok / unavailable |
| `schemas/annotation.schema.json` | JSON Schema контракта v1.0 |
| `templates/index.html` | Разметка страницы, легенда, карточка, блок справки |
| `static/app.js` | Текст, линии ролей, карточка, употребления, запрос справки |
| `static/app.css` | Оформление и школьные линии |
| `examples/valid`, `examples/invalid` | Эталонные и бракованные документы |
| `tests/` | Модульные, интеграционные и качественные проверки |

Поток: файл → загрузчик → шаблон с встроенным JSON → клиент рисует текст и карточку → при выборе слова клиент вызывает `/dictionary`.

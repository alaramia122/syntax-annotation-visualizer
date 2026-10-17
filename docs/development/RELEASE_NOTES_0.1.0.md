# Заметки к выпуску 0.1.0

**Дата подготовки:** 2026-10-17  
**Версия в `pyproject.toml`:** 0.1.0  
**Целевой тег:** `v0.1.0`  
**Коммит подготовки (main на момент проверки):** см. актуальный `main` после коммита stage-12.

## Проверки перед выпуском

| Проверка | Результат |
|----------|-----------|
| Состав репозитория | исходники, docs, examples, tests, CI; без `.env` и секретов |
| `.gitignore` | venv, кэши, `.env` |
| Поиск секретов | ложных срабатываний на поле `tokens` в JSON; реальных ключей/паролей нет |
| `python -m pytest -q` | **62 passed** (2026-10-17) |
| Smoke HTTP | `GET /` 200; `GET /dictionary` 200 |
| CI | workflow `.github/workflows/tests.yml` (3.10–3.12) |
| Документация | USER_GUIDE, ERRORS, COMPONENTS, README |

Чистое `python -m venv` в среде агента недоступно (`ensurepip`); зависимости и тесты прогнаны через установку пакетов пользователя и pytest.

## Как опубликовать релиз на GitHub (владелец репозитория)

Из каталога клона с актуальным `main`:

```bash
git pull origin main
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
```

Затем: GitHub → Releases → «Draft a new release» → выбрать тег `v0.1.0` → вставить текст из этого файла / CHANGELOG → Publish.

Либо в веб-интерфейсе: Releases → Create a new release → Create new tag `v0.1.0` on `main`.

## Соответствие плану этапа 12

Подготовка (дерево, секреты, тесты, версия, заметки) выполнена агентом.  
Создание тега и GitHub Release требует прав push на репозиторий у владельца; из среды агента API создания release недоступен.

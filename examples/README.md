# Набор входных примеров

Примеры служат фикстурами для структурной и семантической валидации.

- `valid/` — документы, которые проходят JSON Schema и семантическую проверку.
- `invalid/` — документы, каждый из которых нарушает одно заявленное правило. Файл является самим входным документом, а не обёрткой с описанием ошибки.

Ожидаемый слой проверки невалидных файлов задан в `tests/test_fixtures.py`: для семантических примеров схема должна проходить, а среди кодов должен быть указанный код.

| Пример | Назначение |
|---|---|
| valid/01-basic.json | Полная разметка |
| valid/02-partial.json | Частичная разметка |
| valid/03-empty.json | Пустой текст и пустые списки |
| valid/04-whitespace-unicode.json | Табуляция и пунктуация |
| valid/05-lemma-search.json | Леммы |
| valid/06-analyzer-metadata.json | Метаданные анализатора |
| valid/07-morphology.json | Грамматические признаки |
| valid/08-non-bmp.json | Символы вне BMP |
| valid/09-unknown-role.json | Неизвестная синтаксическая роль |
| valid/10-minimal-token.json | Минимальный документ |
| valid/11-newlines.json | Переносы строк и промежуток между предложениями |
| invalid/01-version.json | Неподдерживаемая версия схемы |
| invalid/02-missing-language.json | Нет обязательного поля |
| invalid/03-duplicate-token-id.json | Повтор ID токена |
| invalid/04-token-out-of-bounds.json | Координаты токена за пределами текста |
| invalid/05-unknown-sentence.json | Неизвестное предложение |
| invalid/06-unknown-head.json | Неизвестный головной токен |
| invalid/07-self-head.json | Самоссылка |
| invalid/08-root-has-head.json | Корень с ненулевой головой |
| invalid/09-sentence-out-of-bounds.json | Координаты предложения за пределами текста |
| invalid/10-boolean-coordinate.json | Boolean вместо координаты |
| invalid/11-overlapping-tokens.json | Пересечение диапазонов токенов |
| invalid/12-whitespace-in-word.json | Пробел внутри словесного токена |
| invalid/13-missing-head.json | Некорневая связь без головы |
| invalid/14-token-outside-sentence.json | Токен вне диапазона предложения |
| invalid/15-duplicate-sentence-id.json | Повтор ID предложения |
| invalid/16-incomplete-complete.json | `complete` без роли слова |
| invalid/17-head-cycle.json | Цикл головных ссылок |
| invalid/18-token-order.json | Токены не по порядку координат |

Некорректный JSON как текст проверяется разбором на веб-границе и не хранится среди JSON-фикстур.

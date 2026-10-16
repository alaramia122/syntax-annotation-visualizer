# Architecture Decision Records (ADR)

Существенное архитектурное решение оформляется отдельным ADR: контекст, варианты, решение, последствия, статус и дата. Краткий указатель — в `docs/development/DECISIONS.md`.

| ADR | Решение |
|---|---|
| [001](001-stack.md) | Flask, JSON Schema, ванильный JS, pytest |
| [002](002-server-trust-boundary.md) | Сервер принимает документ до показа |
| [003](003-dictionary-port.md) | Справка — отдельный порт, источник ещё не выбран |
| [004](004-rendering-and-coordinates.md) | UTF-16 только в клиенте, одна линия на токен |

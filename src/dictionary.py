"""Справочный порт: краткая справка по слову из внешнего источника.

По ADR-003 отказ словаря не должен ломать просмотр текста, карточку
и поиск употреблений. Этот модуль только отвечает на lookup() и не
участвует в проверке JSON.

Источник первой версии — Русский Викисловарь (MediaWiki API):
короткий текстовый фрагмент страницы (extract). Если запрос не удался,
возвращается статус «недоступно» и ссылка на поиск — это не замена
полноценной статье.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal

# Таймаут: карточка уже показана, справка — дополнение.
REQUEST_TIMEOUT_SEC = 10.0
# Только ASCII в заголовках (latin-1). Более «браузерный» UA — меньше отказов
# на стороне Wikimedia, чем краткая служебная строка.
USER_AGENT = (
    "Mozilla/5.0 (compatible; syntax-annotation-visualizer/0.1; "
    "+https://github.com/alaramia122/syntax-annotation-visualizer)"
)
WIKTIONARY_API = "https://ru.wiktionary.org/w/api.php"
SOURCE_NAME = "Русский Викисловарь"


LookupStatus = Literal["ok", "unavailable", "not_configured"]


@dataclass(frozen=True)
class DictionaryLookup:
    """Результат обращения к справочнику.

    status:
      ok — есть текст справки;
      unavailable — источник выбран, но ответ получить не удалось;
      not_configured — адаптер ещё не подключён (для тестов/заглушек).

    text заполняется только при ok. search_url — ссылка на внешний поиск,
    не утверждение, что там уже есть готовая статья.
    """

    status: LookupStatus
    source_name: str | None = None
    text: str | None = None
    search_url: str | None = None


def _search_url(query: str) -> str:
    return (
        "https://ru.wiktionary.org/w/index.php?"
        + urllib.parse.urlencode({"search": query, "title": "Special:Search"})
    )


def _pick_query(lemma: str | None, surface: str) -> str:
    """Предпочитаем лемму; если её нет — словоформу из текста."""
    if lemma is not None and str(lemma).strip():
        return str(lemma).strip()
    return str(surface).strip()


def _normalize_extract(extract: str) -> str:
    """Убирает лишние пустые строки и ограничивает длину для карточки."""
    lines = [ln.strip() for ln in extract.splitlines()]
    lines = [ln for ln in lines if ln]
    text = "\n".join(lines)
    if len(text) > 800:
        text = text[:797].rstrip() + "…"
    return text


def _ssl_context() -> ssl.SSLContext:
    """Контекст TLS для urlopen.

    На части установок Windows проверка сертификатов у urllib падает,
    хотя браузер открывает тот же сайт. Сначала системное хранилище,
    при наличии — bundle certifi.
    """
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch_json(url: str, *, opener=None) -> dict:
    """GET JSON по URL. opener — подмена для тестов."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    open_fn = opener or urllib.request.urlopen
    kwargs: dict = {"timeout": REQUEST_TIMEOUT_SEC}
    # Подмена в тестах часто не принимает context=.
    if opener is None:
        kwargs["context"] = _ssl_context()
    with open_fn(request, **kwargs) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8"))


def lookup(
    lemma: str | None,
    surface: str,
    *,
    opener=None,
) -> DictionaryLookup:
    """Запрашивает краткую справку по лемме или словоформе.

    opener — необязательная подмена urllib (для тестов), должна вести
    себя как urllib.request.urlopen.
    """
    query = _pick_query(lemma, surface)
    if not query:
        return DictionaryLookup(
            status="unavailable",
            source_name=SOURCE_NAME,
            search_url=None,
        )

    search = _search_url(query)

    # Варианты заголовка: как в разметке и со сменой регистра первой буквы.
    titles: list[str] = [query]
    swapped = query[:1].swapcase() + query[1:]
    if swapped != query:
        titles.append(swapped)

    for title in titles:
        # Без exintro: у статей Викисловаря «вводный» блок до первого
        # заголовка часто пуст, и API возвращал пустой extract.
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": "1",
            "redirects": "1",
            "titles": title,
        }
        url = WIKTIONARY_API + "?" + urllib.parse.urlencode(params)
        try:
            payload = _fetch_json(url, opener=opener)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
            UnicodeError,
            ssl.SSLError,
        ):
            continue

        pages = (payload.get("query") or {}).get("pages") or {}
        if not pages:
            continue

        page = next(iter(pages.values()))
        if page.get("missing") is not None or int(page.get("pageid") or 0) < 0:
            continue

        extract = (page.get("extract") or "").strip()
        if not extract:
            continue

        return DictionaryLookup(
            status="ok",
            source_name=SOURCE_NAME,
            text=_normalize_extract(extract),
            search_url=search,
        )

    return DictionaryLookup(
        status="unavailable",
        source_name=SOURCE_NAME,
        search_url=search,
    )

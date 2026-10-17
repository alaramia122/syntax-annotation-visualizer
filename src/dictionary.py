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
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal

# Таймаут короткий: карточка уже показана, справка — дополнение.
REQUEST_TIMEOUT_SEC = 4.0
USER_AGENT = (
    "syntax-annotation-visualizer/0.1 "
    "(учебный проект; https://github.com/alaramia122/syntax-annotation-visualizer)"
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
        + urllib.parse.urlencode({"search": query, "title": "Служебная:Search"})
    )


def _pick_query(lemma: str | None, surface: str) -> str:
    """Предпочитаем лемму; если её нет — словоформу из текста."""
    if lemma is not None and str(lemma).strip():
        return str(lemma).strip()
    return str(surface).strip()


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
    open_fn = opener or urllib.request.urlopen

    # Несколько вариантов заголовка: как в разметке и с заглавной буквы
    # (в Викисловаре статьи нередко именуются с прописной).
    titles = [query]
    if query[:1].islower():
        titles.append(query[:1].upper() + query[1:])

    for title in titles:
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "redirects": "1",
            "titles": title,
        }
        url = WIKTIONARY_API + "?" + urllib.parse.urlencode(params)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with open_fn(request, timeout=REQUEST_TIMEOUT_SEC) as response:
                raw = response.read()
            payload = json.loads(raw.decode("utf-8"))
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            return DictionaryLookup(
                status="unavailable",
                source_name=SOURCE_NAME,
                search_url=search,
            )

        pages = (payload.get("query") or {}).get("pages") or {}
        if not pages:
            continue

        page = next(iter(pages.values()))
        if page.get("missing") is not None or int(page.get("pageid") or 0) < 0:
            continue

        extract = (page.get("extract") or "").strip()
        if not extract:
            continue

        if len(extract) > 800:
            extract = extract[:797].rstrip() + "…"

        return DictionaryLookup(
            status="ok",
            source_name=SOURCE_NAME,
            text=extract,
            search_url=search,
        )

    return DictionaryLookup(
        status="unavailable",
        source_name=SOURCE_NAME,
        search_url=search,
    )

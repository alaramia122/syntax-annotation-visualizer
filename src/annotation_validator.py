"""Семантическая проверка документа с синтаксической разметкой.

Структуру и типы полей (обязательность, enum, формат строк и чисел)
проверяет JSON Schema. Этот модуль закрывает то, что схемой выразить
неудобно или невозможно:

  • уникальность id предложений и токенов;
  • согласованность диапазонов с длиной текста и друг с другом;
  • вложенность токена в своё предложение;
  • корректность ссылок head (существование, то же предложение, не self);
  • циклы в цепочках head;
  • согласование analysis.status=complete с наличием ролей у слов.

Предполагается, что на вход уже пришёл объект, прошедший схему.
Функция всё же защитная: при неожиданной форме не падает с KeyError,
а возвращает issue с кодом structure — так проще вызывать её из
разных мест и не дублировать проверки типов.

Координаты start/end — индексы кодовых точек Unicode (как у срезов
строки в Python). bool как координата отвергается отдельно: в Python
bool — подкласс int, и без явной проверки True/False пролезли бы как 1/0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    """Одна семантическая ошибка для пользователя и для тестов.

    code  — стабильный машинный код (фикстуры и тесты завязаны на него);
    path  — путь в духе $.analysis.tokens[0].syntax.head;
    message — текст, который можно показать как есть.
    """

    code: str
    path: str
    message: str


def validate_semantics(data: dict[str, Any]) -> list[ValidationIssue]:
    """Возвращает список семантических проблем (пустой — всё в порядке).

    Не исправляет документ и не останавливается на первой ошибке:
    лучше показать сразу несколько независимых замечаний.
    """
    issues: list[ValidationIssue] = []
    document = data.get("document")
    analysis = data.get("analysis")
    if not isinstance(document, dict) or not isinstance(analysis, dict):
        return [ValidationIssue("structure", "$", "document and analysis must be objects")]

    text = document.get("text")
    sentences = analysis.get("sentences")
    tokens = analysis.get("tokens")
    if not isinstance(text, str) or not isinstance(sentences, list) or not isinstance(tokens, list):
        return [ValidationIssue("structure", "$", "text, sentences or tokens have an invalid type")]

    def add(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code, path, message))

    # ----- предложения -----
    # Собираем id и диапазоны, параллельно проверяя порядок и пересечения.
    # Допускаются разрывы между предложениями (пробелы, мусор между ними),
    # но не наложения и не «откат» start назад.
    sentence_ids: set[str] = set()
    sentence_ranges: dict[str, tuple[int, int]] = {}
    previous_sentence_end = 0
    for index, sentence in enumerate(sentences):
        path = f"$.analysis.sentences[{index}]"
        if not isinstance(sentence, dict):
            add("sentence_type", path, "sentence must be an object")
            continue
        sid, start, end = sentence.get("id"), sentence.get("start"), sentence.get("end")
        if not isinstance(sid, str) or not sid:
            add("sentence_id", f"{path}.id", "sentence id must be a non-empty string")
            continue
        if sid in sentence_ids:
            add("duplicate_sentence_id", f"{path}.id", f"duplicate sentence id: {sid}")
        sentence_ids.add(sid)
        if not _valid_range(start, end, len(text)):
            add("sentence_range", path, "sentence range must satisfy 0 <= start <= end <= text length")
            continue
        sentence_ranges[sid] = (start, end)
        if start < previous_sentence_end:
            add("sentence_order", path, "sentence ranges must be ordered and non-overlapping")
        previous_sentence_end = max(previous_sentence_end, end)

    # ----- токены: диапазоны, поверхность, принадлежность предложению -----
    token_ids: set[str] = set()
    token_by_id: dict[str, dict[str, Any]] = {}
    previous_token_start = -1
    previous_token_end = -1
    for index, token in enumerate(tokens):
        path = f"$.analysis.tokens[{index}]"
        if not isinstance(token, dict):
            add("token_type", path, "token must be an object")
            continue
        tid, start, end = token.get("id"), token.get("start"), token.get("end")
        if not isinstance(tid, str) or not tid:
            add("token_id", f"{path}.id", "token id must be a non-empty string")
        elif tid in token_ids:
            add("duplicate_token_id", f"{path}.id", f"duplicate token id: {tid}")
        else:
            token_ids.add(tid)
            token_by_id[tid] = token

        # У токена пустой диапазон (start == end) запрещён: нечего подчёркивать.
        if not _valid_range(start, end, len(text)) or start == end:
            add("token_range", path, "token range must satisfy 0 <= start < end <= text length")
            continue
        if start < previous_token_start:
            add("token_order", path, "tokens must be ordered by start coordinate")
        if start < previous_token_end:
            add("overlapping_token_ranges", path, "token ranges must not overlap")
        previous_token_start = start
        previous_token_end = max(previous_token_end, end)

        sid = token.get("sentence_id")
        if sid not in sentence_ids:
            add("unknown_sentence", f"{path}.sentence_id", f"unknown sentence id: {sid}")
        elif sid in sentence_ranges:
            s_start, s_end = sentence_ranges[sid]
            if start < s_start or end > s_end:
                add("token_outside_sentence", path, "token range must be contained in its sentence range")

        # Поверхность берём срезом исходного текста — канонический источник символов.
        kind = token.get("kind")
        surface = text[start:end]
        if not surface or surface.isspace():
            add("empty_token_surface", path, "token must point to non-whitespace text")
        elif kind == "word" and any(ch.isspace() for ch in surface):
            # У word внутри диапазона не должно быть пробелов; пунктуация
            # и прочие kind этим правилом не ограничены.
            add("whitespace_in_word_surface", path, "word token range must not include whitespace characters")

        # ----- синтаксис одного токена (без проверки «head существует») -----
        syntax = token.get("syntax")
        if syntax is not None and isinstance(syntax, dict):
            # sentinel: поля head может не быть вовсе — это не то же, что null.
            # null у non-root с relation — отдельная ошибка missing_head.
            head = syntax.get("head", "__missing__")
            if head != "__missing__" and head is not None and not isinstance(head, str):
                add("head_type", f"{path}.syntax.head", "head must be a token id or null")
            if head is not None and head != "__missing__" and isinstance(head, str) and head == tid:
                add("self_head", f"{path}.syntax.head", "token cannot be its own head")
            if syntax.get("relation") == "root" and head is not None:
                add("root_head", f"{path}.syntax.head", "root relation must have head null")
            if syntax.get("relation") != "root" and syntax.get("relation") and head is None:
                add("missing_head", f"{path}.syntax.head", "non-root relation with a relation label must reference a head")

    # ----- head: существование и то же предложение -----
    # Вынесено во второй проход: к этому моменту token_by_id уже полный.
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            continue
        syntax = token.get("syntax")
        if not isinstance(syntax, dict):
            continue
        head = syntax.get("head")
        if isinstance(head, str):
            if head not in token_by_id:
                add(
                    "unknown_head",
                    f"$.analysis.tokens[{index}].syntax.head",
                    f"unknown head token id: {head}",
                )
            else:
                own_sentence = token.get("sentence_id")
                head_sentence = token_by_id[head].get("sentence_id")
                if own_sentence != head_sentence:
                    add(
                        "cross_sentence_head",
                        f"$.analysis.tokens[{index}].syntax.head",
                        "head must belong to the same sentence",
                    )

    _add_head_cycles(tokens, add)

    # ----- полнота разметки -----
    # status=complete обещает, что у каждого word есть роль.
    # partial допускает слова без syntax/role — это штатный сценарий.
    status = analysis.get("status")
    if status == "complete":
        for index, token in enumerate(tokens):
            if isinstance(token, dict) and token.get("kind") == "word":
                syntax = token.get("syntax")
                if not isinstance(syntax, dict) or not syntax.get("role"):
                    add(
                        "incomplete_complete_analysis",
                        f"$.analysis.tokens[{index}].syntax",
                        "word token without a syntax role requires analysis.status='partial'",
                    )

    return issues


def _add_head_cycles(tokens: list[Any], add) -> None:
    """Ищет циклы в ориентированном графе head.

    Самоссылка (token → token) уже закрыта кодом self_head и в граф
    не попадает. Здесь — циклы длины 2 и больше (A→B→A, A→B→C→A, …).

    Обход с запоминанием пути: если текущий узел уже встречался в
    текущем пути, все вершины цикла помечаются ошибкой head_cycle.
    reported не даёт ругаться на один и тот же узел многократно.
    """
    heads: dict[str, str] = {}
    index_by_id: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            continue
        token_id = token.get("id")
        if not isinstance(token_id, str) or not token_id:
            continue
        index_by_id[token_id] = index
        syntax = token.get("syntax")
        if not isinstance(syntax, dict):
            continue
        head = syntax.get("head")
        if isinstance(head, str) and head != token_id:
            heads[token_id] = head

    reported: set[str] = set()
    for start in heads:
        path: list[str] = []
        path_index: dict[str, int] = {}
        current = start
        while current in heads and current not in reported:
            if current in path_index:
                cycle = path[path_index[current]:]
                for node in cycle:
                    reported.add(node)
                    add(
                        "head_cycle",
                        f"$.analysis.tokens[{index_by_id[node]}].syntax.head",
                        "head links must not form a cycle",
                    )
                break
            path_index[current] = len(path)
            path.append(current)
            current = heads[current]
        reported.update(path)


def _valid_range(start: Any, end: Any, text_length: int) -> bool:
    """Проверяет, что start/end — целые координаты в пределах текста.

    bool отвергаем явно: isinstance(True, int) == True в Python, но
    True/False как смещения в разметке бессмысленны и опасны.
    """
    return (
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and 0 <= start <= end <= text_length
    )

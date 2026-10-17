/**
 * Клиентская визуализация готовой синтаксической разметки.
 *
 * Документ уже проверен на сервере. Здесь только отображение:
 *   — исходный текст без потерь символов и пробелов;
 *   — одна линия под словом по его роли (школьные подчёркивания);
 *   — выбор слова и черновик карточки (этапы 6–7 ещё не приняты).
 *
 * В файле разметки смещения — по кодовым точкам Юникода (как срезы
 * строки в Python). В браузере строка режется по единицам UTF-16,
 * поэтому один раз строится таблица пересчёта и текст берётся только через неё.
 */
(() => {
  "use strict";

  const doc = window.ANNOTATION_DOCUMENT;
  if (!doc || !doc.document || !doc.analysis) {
    return;
  }

  const textRoot = document.getElementById("annotated-text");
  if (!textRoot) {
    return;
  }

  const source = doc.document.text;

  // Пересчёт: номер кодовой точки → позиция в строке браузера.
  // Нулевой элемент — 0; длина таблицы на единицу больше числа точек.
  const codePointToUtf16 = [0];
  let utf16Offset = 0;
  for (const character of source) {
    utf16Offset += character.length; // редкие символы вне BMP занимают две единицы
    codePointToUtf16.push(utf16Offset);
  }

  function sourceSlice(start, end) {
    return source.slice(codePointToUtf16[start], codePointToUtf16[end]);
  }

  // Сервер уже отсеял пересечения и выход за границы; фильтр здесь —
  // страховка на случай устаревшей страницы или ручной подстановки данных.
  const tokens = [...doc.analysis.tokens]
    .filter(
      (t) =>
        Number.isInteger(t.start) &&
        Number.isInteger(t.end) &&
        t.start >= 0 &&
        t.end > t.start &&
        t.end <= source.length
    )
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const tokenNodes = new Map();
  const byId = new Map(tokens.map((t) => [t.id, t]));
  let cursor = 0;

  /**
   * Класс подчёркивания по школьным правилам разбора предложения.
   * Нет роли → без линии.
   * Подлежащее, сказуемое, определение, дополнение, обстоятельство —
   * свои виды линий (см. ADR-004).
   * Любая другая непустая роль → серая сплошная «другая роль».
   */
  function roleClass(token) {
    const raw = token.syntax && token.syntax.role;
    if (raw == null || String(raw).trim() === "") {
      return "";
    }
    const role = String(raw).toUpperCase();
    // подлежащее
    if (role === "SUBJECT" || role === "ПОДЛЕЖАЩЕЕ") {
      return "role-subject";
    }
    // сказуемое
    if (role === "PREDICATE" || role === "СКАЗУЕМОЕ") {
      return "role-predicate";
    }
    // определение
    if (
      role === "DEFINITION" ||
      role === "ATTRIBUTE" ||
      role === "ОПРЕДЕЛЕНИЕ"
    ) {
      return "role-definition";
    }
    // дополнение
    if (role === "OBJECT" || role === "ДОПОЛНЕНИЕ") {
      return "role-object";
    }
    // обстоятельство
    if (
      role === "ADVERBIAL" ||
      role === "ADVERBIAL_MODIFIER" ||
      role === "ОБСТОЯТЕЛЬСТВО"
    ) {
      return "role-adverbial";
    }
    return "role-unknown";
  }

  function selectToken(id, scroll) {
    const token = byId.get(id);
    if (!token) {
      return;
    }

    tokenNodes.forEach((node, nodeId) => {
      node.classList.toggle("selected", nodeId === id);
    });

    const empty = document.getElementById("empty-selection");
    const card = document.getElementById("token-card");
    if (empty) {
      empty.hidden = true;
    }
    if (card) {
      card.hidden = false;
    }

    const surface = sourceSlice(token.start, token.end);
    setText("card-surface", surface);
    setText("card-lemma", token.lemma || "—");
    setText("card-pos", token.pos || "—");
    setText(
      "card-role",
      (token.syntax && token.syntax.role) || "—"
    );
    setText(
      "card-relation",
      (token.syntax && token.syntax.relation) || "—"
    );

    // Черновик поиска употреблений (этап 7): пока без группировки по ролям.
    const surfaceKey = surface;
    renderOccurrences(
      "surface-occurrences",
      tokens.filter((t) => sourceSlice(t.start, t.end) === surfaceKey),
      id
    );

    let lemmaMatches = [];
    if (token.lemma) {
      const key = String(token.lemma).toLocaleLowerCase();
      lemmaMatches = tokens.filter(
        (t) => t.lemma && String(t.lemma).toLocaleLowerCase() === key
      );
    }
    renderOccurrences("lemma-occurrences", lemmaMatches, id);

    if (scroll) {
      const node = tokenNodes.get(id);
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = value;
    }
  }

  function renderOccurrences(listId, matches, currentId) {
    const list = document.getElementById(listId);
    if (!list) {
      return;
    }
    list.replaceChildren();
    if (!matches.length) {
      const item = document.createElement("li");
      item.textContent = "Совпадений нет.";
      list.append(item);
      return;
    }
    matches.forEach((token) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const surface = sourceSlice(token.start, token.end);
      const role =
        token.syntax && token.syntax.role ? " · " + token.syntax.role : "";
      button.type = "button";
      button.textContent =
        surface + role + (token.id === currentId ? " (выбрано)" : "");
      button.addEventListener("click", () => selectToken(token.id, true));
      item.append(button);
      list.append(item);
    });
  }

  // Сборка текста: неразмеченные фрагменты — обычный текст,
  // слова с ролью — кнопки. Разметку из файла в HTML не вставляем:
  // иначе символы вроде < могли бы исказить страницу.
  textRoot.replaceChildren();
  tokens.forEach((token) => {
    if (token.start < cursor) {
      return;
    }
    if (token.start > cursor) {
      textRoot.append(
        document.createTextNode(sourceSlice(cursor, token.start))
      );
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "token";
    const role = roleClass(token);
    if (role) {
      button.classList.add(role);
    }
    button.textContent = sourceSlice(token.start, token.end);
    const label =
      sourceSlice(token.start, token.end) +
      (token.syntax && token.syntax.role ? ", " + token.syntax.role : "");
    button.setAttribute("aria-label", label);
    button.addEventListener("click", () => selectToken(token.id, false));
    textRoot.append(button);
    tokenNodes.set(token.id, button);
    cursor = token.end;
  });

  // Остаток после последнего слова (пробелы, перевод строки, знаки).
  const textEnd = codePointToUtf16.length - 1;
  if (cursor < textEnd) {
    textRoot.append(document.createTextNode(sourceSlice(cursor, textEnd)));
  }
})();

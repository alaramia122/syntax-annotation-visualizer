/**
 * Клиентская визуализация готовой синтаксической разметки.
 *
 * Документ уже проверен на сервере. Здесь только отображение:
 *   — исходный текст без потерь символов и пробелов;
 *   — одна линия под токеном по его роли (ADR-004);
 *   — выбор токена и черновик карточки (этапы 6–7 ещё не приняты).
 *
 * Координаты в JSON — индексы кодовых точек Unicode (как в Python).
 * В JavaScript slice работает в единицах UTF-16, поэтому один раз
 * строим таблицу codePoint → utf16 и режем текст только через неё.
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

  // Таблица: индекс кодовой точки → индекс в UTF-16 строке JS.
  // codePointToUtf16[0] === 0; для строки из N code points длина таблицы N+1.
  const codePointToUtf16 = [0];
  let utf16Offset = 0;
  for (const character of source) {
    utf16Offset += character.length; // суррогатная пара даёт length === 2
    codePointToUtf16.push(utf16Offset);
  }

  function sourceSlice(start, end) {
    return source.slice(codePointToUtf16[start], codePointToUtf16[end]);
  }

  // Сервер уже отсеял пересечения и выход за границы; фильтр — защита
  // на случай устаревшего шаблона или ручной подстановки документа.
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
   * CSS-класс линии роли по ADR-004.
   * Пустая / отсутствующая роль → без линии.
   * Известные пять групп → свой тип линии и цвет.
   * Любое другое непустое значение → нейтральная серая сплошная.
   */
  function roleClass(token) {
    const raw = token.syntax && token.syntax.role;
    if (raw == null || String(raw).trim() === "") {
      return "";
    }
    const role = String(raw).toUpperCase();
    if (role === "SUBJECT" || role === "ПОДЛЕЖАЩЕЕ") {
      return "role-subject";
    }
    if (role === "PREDICATE" || role === "СКАЗУЕМОЕ") {
      return "role-predicate";
    }
    if (
      role === "DEFINITION" ||
      role === "ATTRIBUTE" ||
      role === "ОПРЕДЕЛЕНИЕ"
    ) {
      return "role-definition";
    }
    if (role === "OBJECT" || role === "ДОПОЛНЕНИЕ") {
      return "role-object";
    }
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

    // Черновик поиска (этап 7): пока без группировки по ролям.
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

  // Рендер текста: чередуем текстовые узлы (неразмеченные фрагменты)
  // и кнопки токенов. innerHTML не используем — пользовательский текст
  // не должен интерпретироваться как разметка.
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

  // Хвост после последнего токена (пробелы, перевод строки, пунктуация).
  const textEnd = codePointToUtf16.length - 1;
  if (cursor < textEnd) {
    textRoot.append(document.createTextNode(sourceSlice(cursor, textEnd)));
  }
})();

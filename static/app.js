/**
 * Клиентская визуализация готовой синтаксической разметки.
 *
 * Документ уже проверен на сервере. Здесь:
 *   — исходный текст без потерь символов и пробелов;
 *   — подчёркивания по школьным правилам (см. ADR-004);
 *   — карточка выбранного слова (этап 6);
 *   — черновик списков употреблений (полная группировка — этап 7).
 *
 * В файле разметки смещения — по кодовым точкам Юникода.
 * В браузере строка режется иначе, поэтому один раз строится
 * таблица пересчёта, и фрагменты текста берутся только через неё.
 */
(() => {
  "use strict";

  const MISSING = "не указано";

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
  const codePointToUtf16 = [0];
  let utf16Offset = 0;
  for (const character of source) {
    utf16Offset += character.length;
    codePointToUtf16.push(utf16Offset);
  }

  function sourceSlice(start, end) {
    return source.slice(codePointToUtf16[start], codePointToUtf16[end]);
  }

  // Поле есть и непустая строка — показываем как есть; иначе «не указано».
  // Числа и логические значения из признаков тоже допустимы.
  function displayField(value) {
    if (value === null || value === undefined) {
      return MISSING;
    }
    if (typeof value === "string" && value.trim() === "") {
      return MISSING;
    }
    return String(value);
  }

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
  let selectedId = null;

  /**
   * Класс подчёркивания по школьным правилам разбора предложения.
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

  /**
   * Открывает карточку слова и подсвечивает его в тексте.
   * Недостающие сведения не угадываются — пишется «не указано».
   */
  function selectToken(id, scroll) {
    const token = byId.get(id);
    if (!token) {
      return;
    }
    selectedId = id;

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

    // Словоформа — срез исходного текста, без «сборки» из полей разметки.
    const surface = sourceSlice(token.start, token.end);
    setText("card-surface", surface);
    setText("card-lemma", displayField(token.lemma));
    setText("card-pos", displayField(token.pos));
    setText(
      "card-role",
      displayField(token.syntax && token.syntax.role)
    );
    setText(
      "card-relation",
      displayField(token.syntax && token.syntax.relation)
    );

    renderFeatures(token.features);

    // Списки употреблений: базовая версия; группировка по ролям — этап 7.
    renderOccurrences(
      "surface-occurrences",
      tokens.filter((t) => sourceSlice(t.start, t.end) === surface),
      id
    );

    const lemmaBlock = document.getElementById("lemma-occurrences-block");
    const lemmaHint = document.getElementById("lemma-occurrences-hint");
    if (!token.lemma) {
      // Нет леммы в разметке — поиск по лемме не запускаем.
      if (lemmaHint) {
        lemmaHint.textContent = "Лемма в разметке отсутствует";
      }
      const list = document.getElementById("lemma-occurrences");
      if (list) {
        list.replaceChildren();
      }
    } else {
      if (lemmaHint) {
        lemmaHint.textContent = "Совпадение по лемме";
      }
      const key = String(token.lemma).toLocaleLowerCase();
      const lemmaMatches = tokens.filter(
        (t) => t.lemma && String(t.lemma).toLocaleLowerCase() === key
      );
      renderOccurrences("lemma-occurrences", lemmaMatches, id);
    }
    if (lemmaBlock) {
      lemmaBlock.hidden = false;
    }

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

  /**
   * Грамматические признаки (features), если они есть в разметке.
   * Пустой объект или отсутствие поля — «не указано».
   */
  function renderFeatures(features) {
    const list = document.getElementById("card-features");
    if (!list) {
      return;
    }
    list.replaceChildren();

    if (!features || typeof features !== "object") {
      const item = document.createElement("li");
      item.textContent = MISSING;
      list.append(item);
      return;
    }

    const entries = Object.keys(features).sort();
    if (!entries.length) {
      const item = document.createElement("li");
      item.textContent = MISSING;
      list.append(item);
      return;
    }

    entries.forEach((key) => {
      const item = document.createElement("li");
      const val = features[key];
      const shown =
        val === null || val === undefined ? MISSING : String(val);
      item.textContent = key + ": " + shown;
      list.append(item);
    });
  }

  function renderOccurrences(listId, matches, currentId) {
    const list = document.getElementById(listId);
    if (!list) {
      return;
    }
    list.replaceChildren();

    // Текущее слово в список не входит.
    const others = matches.filter((t) => t.id !== currentId);
    if (!others.length) {
      const item = document.createElement("li");
      item.textContent = "Других употреблений нет";
      list.append(item);
      return;
    }

    others.forEach((token) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const surface = sourceSlice(token.start, token.end);
      const role =
        token.syntax && token.syntax.role ? " · " + token.syntax.role : "";
      button.type = "button";
      button.textContent = surface + role;
      button.addEventListener("click", () => selectToken(token.id, true));
      item.append(button);
      list.append(item);
    });
  }

  // Сборка текста: неразмеченные фрагменты и кнопки слов.
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

  const textEnd = codePointToUtf16.length - 1;
  if (cursor < textEnd) {
    textRoot.append(document.createTextNode(sourceSlice(cursor, textEnd)));
  }
})();

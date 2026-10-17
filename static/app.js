/**
 * Клиентская визуализация готовой синтаксической разметки.
 *
 * Документ уже проверен на сервере. Здесь:
 *   — исходный текст без потерь символов и пробелов;
 *   — подчёркивания по школьным правилам (см. ADR-004);
 *   — карточка выбранного слова (этап 6);
 *   — поиск употреблений с группировкой по ролям (этап 7);
 *   — запрос словарной справки после выбора слова (этап 8).
 *
 * В файле разметки смещения — по кодовым точкам Юникода.
 * В браузере строка режется иначе, поэтому один раз строится
 * таблица пересчёта, и фрагменты текста берутся только через неё.
 */
(() => {
  "use strict";

  const MISSING = "не указано";
  const ROLE_MISSING_GROUP = "Роль не указана";

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

  /** Имя группы в списке употреблений: роль как в разметке или запасная подпись. */
  function roleGroupName(token) {
    const role = token.syntax && token.syntax.role;
    if (role == null || String(role).trim() === "") {
      return ROLE_MISSING_GROUP;
    }
    return String(role);
  }

  /**
   * Открывает карточку слова и подсвечивает его в тексте.
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

    const surface = sourceSlice(token.start, token.end);
    setText("card-surface", surface);
    setText("card-lemma", displayField(token.lemma));
    setText("card-pos", displayField(token.pos));
    setText("card-role", displayField(token.syntax && token.syntax.role));
    setText(
      "card-relation",
      displayField(token.syntax && token.syntax.relation)
    );

    renderFeatures(token.features);

    // По словоформе: точное совпадение среза, без смены регистра и обрезки.
    const surfaceMatches = tokens.filter(
      (t) => sourceSlice(t.start, t.end) === surface
    );
    renderGroupedOccurrences("surface-occurrences", surfaceMatches, id);

    const lemmaHint = document.getElementById("lemma-occurrences-hint");
    if (!token.lemma) {
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
      // Сравнение через toLocaleLowerCase: для кириллицы близко к casefold;
      // «ё» и «е» не склеиваются.
      const key = String(token.lemma).toLocaleLowerCase();
      const lemmaMatches = tokens.filter(
        (t) => t.lemma && String(t.lemma).toLocaleLowerCase() === key
      );
      renderGroupedOccurrences("lemma-occurrences", lemmaMatches, id);
    }

    // Справка не блокирует карточку: запрос уходит после заполнения полей.
    loadDictionary(token.lemma || null, surface);

    if (scroll) {
      const node = tokenNodes.get(id);
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  /**
   * Запрашивает у сервера краткую справку. Пока ответа нет — «загрузка».
   * При отказе сети или статусе unavailable основные функции уже работают.
   */
  function loadDictionary(lemma, surface) {
    const statusEl = document.getElementById("dictionary-status");
    const textEl = document.getElementById("dictionary-text");
    const sourceEl = document.getElementById("dictionary-source");
    const linkWrap = document.getElementById("dictionary-link-wrap");
    const linkEl = document.getElementById("dictionary-link");

    if (statusEl) {
      statusEl.hidden = false;
      statusEl.textContent = "Загрузка справки…";
    }
    if (textEl) {
      textEl.hidden = true;
      textEl.textContent = "";
    }
    if (sourceEl) {
      sourceEl.hidden = true;
      sourceEl.textContent = "";
    }
    if (linkWrap) {
      linkWrap.hidden = true;
    }

    const params = new URLSearchParams();
    if (lemma) {
      params.set("lemma", lemma);
    }
    params.set("surface", surface || "");

    fetch("/dictionary?" + params.toString())
      .then(function (response) {
        if (!response.ok) {
          throw new Error("bad status");
        }
        return response.json();
      })
      .then(function (data) {
        if (!data || !data.status) {
          if (statusEl) {
            statusEl.textContent = "Справка временно недоступна";
          }
          return;
        }
        if (data.status === "ok" && data.text) {
          if (statusEl) {
            statusEl.hidden = true;
          }
          if (textEl) {
            textEl.hidden = false;
            textEl.textContent = data.text;
          }
          if (sourceEl && data.source_name) {
            sourceEl.hidden = false;
            sourceEl.textContent = "Источник: " + data.source_name;
          }
        } else if (data.status === "not_configured") {
          if (statusEl) {
            statusEl.textContent = "Словарный источник не подключён";
          }
        } else {
          if (statusEl) {
            statusEl.textContent = "Справка временно недоступна";
          }
        }
        if (linkEl && data.search_url) {
          linkEl.href = data.search_url;
          if (linkWrap) {
            linkWrap.hidden = false;
          }
        }
      })
      .catch(function () {
        if (statusEl) {
          statusEl.textContent = "Справка временно недоступна";
        }
      });
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = value;
    }
  }

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

  /**
   * Список употреблений, сгруппированный по синтаксической роли.
   *
   * Текущее слово в список не входит.
   * Порядок групп и элементов — порядок первых вхождений в документе
   * (токены уже отсортированы по координате начала).
   * Переход выбирает слово и прокручивает к нему.
   */
  function renderGroupedOccurrences(listId, matches, currentId) {
    const root = document.getElementById(listId);
    if (!root) {
      return;
    }
    root.replaceChildren();

    const others = matches.filter((t) => t.id !== currentId);
    if (!others.length) {
      const item = document.createElement("li");
      item.className = "occurrence-empty";
      item.textContent = "Других употреблений нет";
      root.append(item);
      return;
    }

    // Сохраняем порядок первого появления роли в документе.
    const groups = new Map();
    others.forEach((token) => {
      const name = roleGroupName(token);
      if (!groups.has(name)) {
        groups.set(name, []);
      }
      groups.get(name).push(token);
    });

    groups.forEach((groupTokens, groupName) => {
      const groupItem = document.createElement("li");
      groupItem.className = "occurrence-group";

      const title = document.createElement("p");
      title.className = "occurrence-group-title";
      title.textContent = groupName;
      groupItem.append(title);

      const sublist = document.createElement("ul");
      sublist.className = "occurrence-list";

      groupTokens.forEach((token) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        const surface = sourceSlice(token.start, token.end);
        // Краткий контекст: словоформа и позиция в тексте (с единицы для человека).
        button.type = "button";
        button.textContent =
          surface + " · позиция " + (token.start + 1);
        button.setAttribute(
          "aria-label",
          "Перейти к «" + surface + "», позиция " + (token.start + 1)
        );
        button.addEventListener("click", () => selectToken(token.id, true));
        item.append(button);
        sublist.append(item);
      });

      groupItem.append(sublist);
      root.append(groupItem);
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

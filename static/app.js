(() => {
  "use strict";
  const doc = window.ANNOTATION_DOCUMENT;
  if (!doc || !doc.document || !doc.analysis) return;

  const textRoot = document.getElementById("annotated-text");
  if (!textRoot) return;
  const source = doc.document.text;
  // Input offsets are Python Unicode code-point offsets; JS String#slice uses UTF-16 units.
  const codePointToUtf16 = [0];
  let utf16Offset = 0;
  for (const character of source) {
    utf16Offset += character.length;
    codePointToUtf16.push(utf16Offset);
  }
  const sourceSlice = (start, end) => source.slice(codePointToUtf16[start], codePointToUtf16[end]);
  const tokens = [...doc.analysis.tokens].filter(t =>
    Number.isInteger(t.start) && Number.isInteger(t.end) &&
    t.start >= 0 && t.end >= t.start && t.end <= source.length
  ).sort((a, b) => a.start - b.start || a.end - b.end);
  const tokenNodes = new Map();
  const byId = new Map(tokens.map(t => [t.id, t]));
  let cursor = 0;
  let selectedId = null;

  function roleClass(token) {
    const role = String(token.syntax?.role || "").toUpperCase();
    if (["SUBJECT", "ПОДЛЕЖАЩЕЕ"].includes(role)) return "role-subject";
    if (["PREDICATE", "СКАЗУЕМОЕ"].includes(role)) return "role-predicate";
    if (["DEFINITION", "ATTRIBUTE", "ОПРЕДЕЛЕНИЕ"].includes(role)) return "role-definition";
    if (["OBJECT", "ДОПОЛНЕНИЕ"].includes(role)) return "role-object";
    if (["ADVERBIAL", "ADVERBIAL_MODIFIER", "ОБСТОЯТЕЛЬСТВО"].includes(role)) return "role-adverbial";
    return "";
  }

  function selectToken(id, scroll = false) {
    const token = byId.get(id);
    if (!token) return;
    selectedId = id;
    tokenNodes.forEach((node, nodeId) => node.classList.toggle("selected", nodeId === id));
    document.getElementById("empty-selection").hidden = true;
    document.getElementById("token-card").hidden = false;
    document.getElementById("card-surface").textContent = sourceSlice(token.start, token.end);
    document.getElementById("card-lemma").textContent = token.lemma || "—";
    document.getElementById("card-pos").textContent = token.pos || "—";
    document.getElementById("card-role").textContent = token.syntax?.role || "—";
    document.getElementById("card-relation").textContent = token.syntax?.relation || "—";
    renderOccurrences("surface-occurrences", tokens.filter(t => sourceSlice(t.start, t.end) === sourceSlice(token.start, token.end)), id);
    const lemmaMatches = token.lemma
      ? tokens.filter(t => t.lemma && t.lemma.toLocaleLowerCase() === token.lemma.toLocaleLowerCase())
      : [];
    renderOccurrences("lemma-occurrences", lemmaMatches, id);
    if (scroll) tokenNodes.get(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function renderOccurrences(listId, matches, currentId) {
    const list = document.getElementById(listId);
    list.replaceChildren();
    if (!matches.length) {
      const item = document.createElement("li");
      item.textContent = "Совпадений нет.";
      list.append(item);
      return;
    }
    matches.forEach(token => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const surface = sourceSlice(token.start, token.end);
      const role = token.syntax?.role ? " · " + token.syntax.role : "";
      button.type = "button";
      button.textContent = surface + role + (token.id === currentId ? " (выбрано)" : "");
      button.addEventListener("click", () => selectToken(token.id, true));
      item.append(button);
      list.append(item);
    });
  }

  tokens.forEach(token => {
    if (token.start < cursor) return; // Invalid overlaps are rejected server-side; keep rendering defensive.
    textRoot.append(document.createTextNode(sourceSlice(cursor, token.start)));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "token";
    const role = roleClass(token);
    if (role) button.classList.add(role);
    button.textContent = sourceSlice(token.start, token.end);
    button.setAttribute("aria-label", sourceSlice(token.start, token.end) + (token.syntax?.role ? ", " + token.syntax.role : ""));
    button.addEventListener("click", () => selectToken(token.id));
    textRoot.append(button);
    tokenNodes.set(token.id, button);
    cursor = token.end;
  });
  textRoot.append(document.createTextNode(sourceSlice(cursor, codePointToUtf16.length - 1)));
})();

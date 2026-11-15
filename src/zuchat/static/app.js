// One page, one form, one streaming fetch. No framework, no build step.
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const newButton = document.getElementById("new");
const signInCard = document.getElementById("sign-in-card");

const STATUS_MESSAGES = {
  400: "the request was rejected",
  401: "session expired — sign in again",
  403: "this account is not allowed",
  422: "that message is too long",
  502: "the provider failed; try again",
  503: "the server is not ready yet",
};

const LABELS = { you: "you", bot: "zuchat", system: "system" };

// --- markdown -------------------------------------------------------------
// Replies arrive as markdown. This renders a small subset into DOM nodes:
// every piece of text goes through textContent and links are http(s) only, so a
// reply (or a prompt-injected tool result) cannot inject HTML. That keeps the
// page on `default-src 'self'` with no parser dependency and no sanitizer.

const SAFE_LINK = /^https?:\/\//i;
const INLINE =
  /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_|\[[^\]\n]+\]\([^)\s]+\))/g;
const FENCE = /^\s*```(\S*)\s*$/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const RULE = /^\s*([-*_])\1{2,}\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const UNORDERED = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*(\d+)[.)]\s+(.*)$/;

function inlineNode(token) {
  if (token.startsWith("`")) {
    const code = document.createElement("code");
    code.textContent = token.slice(1, -1);
    return code;
  }

  const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
  if (link) {
    const href = link[2].trim();
    // Anything else (javascript:, data:, relative) renders as plain text.
    if (!SAFE_LINK.test(href)) return document.createTextNode(link[1]);
    const a = document.createElement("a");
    a.href = href;
    a.textContent = link[1];
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    return a;
  }

  if (token.startsWith("**") || token.startsWith("__")) {
    const strong = document.createElement("strong");
    appendInline(strong, token.slice(2, -2));
    return strong;
  }

  const em = document.createElement("em");
  appendInline(em, token.slice(1, -1));
  return em;
}

function appendInline(parent, text) {
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) {
      parent.append(document.createTextNode(text.slice(last, match.index)));
    }
    parent.append(inlineNode(match[0]));
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parent.append(document.createTextNode(text.slice(last)));
  }
}

// Tables are common in answers. Keep the parser aligned with the inline format
// above: cells go through textContent, never innerHTML.
function tableCells(line) {
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|")) text = text.slice(0, -1);
  return text.split("|").map((cell) => cell.trim());
}

function isTableDivider(line) {
  if (!line.includes("|")) return false;
  const cells = tableCells(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdown(container, source) {
  container.replaceChildren();
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  let paragraph = [];
  let i = 0;

  const flush = () => {
    if (paragraph.length === 0) return;
    const p = document.createElement("p");
    appendInline(p, paragraph.join(" "));
    container.append(p);
    paragraph = [];
  };

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      flush();
      i += 1;
      continue;
    }

    const fence = line.match(FENCE);
    if (fence) {
      flush();
      const code = [];
      i += 1;
      while (i < lines.length && !FENCE.test(lines[i])) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // the closing fence, which streaming may not have sent yet
      const pre = document.createElement("pre");
      const block = document.createElement("code");
      if (fence[1]) block.className = `language-${fence[1]}`;
      block.textContent = code.join("\n");
      pre.append(block);
      container.append(pre);
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      flush();
      const el = document.createElement(`h${Math.min(heading[1].length + 2, 6)}`);
      appendInline(el, heading[2]);
      container.append(el);
      i += 1;
      continue;
    }

    if (RULE.test(line)) {
      flush();
      container.append(document.createElement("hr"));
      i += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      flush();
      const quoted = [];
      while (i < lines.length) {
        const match = lines[i].match(QUOTE);
        if (!match) break;
        quoted.push(match[1]);
        i += 1;
      }
      const blockquote = document.createElement("blockquote");
      appendInline(blockquote, quoted.join(" "));
      container.append(blockquote);
      continue;
    }

    if (UNORDERED.test(line)) {
      flush();
      const list = document.createElement("ul");
      while (i < lines.length) {
        const match = lines[i].match(UNORDERED);
        if (!match) break;
        const item = document.createElement("li");
        appendInline(item, match[1]);
        list.append(item);
        i += 1;
      }
      container.append(list);
      continue;
    }

    const ordered = line.match(ORDERED);
    if (ordered) {
      flush();
      const list = document.createElement("ol");
      const start = Number(ordered[1]);
      if (start > 1) list.start = start;
      while (i < lines.length) {
        const match = lines[i].match(ORDERED);
        if (!match) break;
        const item = document.createElement("li");
        appendInline(item, match[2]);
        list.append(item);
        i += 1;
      }
      container.append(list);
      continue;
    }

    if (line.includes("|") && isTableDivider(lines[i + 1] ?? "")) {
      flush();
      const headers = tableCells(line);
      const table = document.createElement("table");
      const headRow = document.createElement("tr");
      for (const cell of headers) {
        const th = document.createElement("th");
        appendInline(th, cell);
        headRow.append(th);
      }
      const thead = document.createElement("thead");
      thead.append(headRow);
      table.append(thead);
      i += 2; // header and divider

      const tbody = document.createElement("tbody");
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
        const cells = tableCells(lines[i]);
        const row = document.createElement("tr");
        for (let column = 0; column < headers.length; column += 1) {
          const td = document.createElement("td");
          appendInline(td, cells[column] ?? "");
          row.append(td);
        }
        tbody.append(row);
        i += 1;
      }
      if (tbody.children.length > 0) table.append(tbody);
      container.append(table);
      continue;
    }

    paragraph.push(line.trim());
    i += 1;
  }

  flush();
}

// textContent, never innerHTML: replies are untrusted.
function line(kind, text) {
  const article = document.createElement("article");
  article.className = kind;

  const header = document.createElement("header");
  const label = document.createElement("small");
  label.textContent = LABELS[kind] || kind;
  header.append(label);

  const body = document.createElement("div");
  body.className = "body";
  body.textContent = text;

  article.append(header, body);
  logEl.append(article);
  article.scrollIntoView({ block: "nearest" });
  return article;
}

// The raw markdown per bot line; every delta re-renders from it.
const sources = new WeakMap();

function appendText(article, text) {
  sources.set(article, (sources.get(article) ?? "") + text);
  renderMarkdown(article.querySelector(".body"), sources.get(article));
  article.scrollIntoView({ block: "nearest" });
}

// The API sends `data: <json>` frames, then `data: [DONE]`. A failure that
// happens after the status line is sent arrives as an `event: error` frame.
function consume(buffer, article) {
  const frames = buffer.split("\n\n");
  const rest = frames.pop();

  for (const frame of frames) {
    let event = "message";
    const data = [];
    for (const raw of frame.split("\n")) {
      if (raw.startsWith("event: ")) event = raw.slice("event: ".length).trim();
      else if (raw.startsWith("data: ")) data.push(raw.slice("data: ".length));
    }
    if (data.length === 0) continue;

    const payload = data.join("\n");
    if (event === "error") {
      line("system", "the provider failed; try again");
    } else if (payload === "[DONE]") {
      // Visible to the smoke test, and a truthful signal for the page itself.
      article.dataset.done = "1";
    } else {
      appendText(article, JSON.parse(payload).text ?? "");
    }
  }
  return rest;
}

function link(href, text) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  return a;
}

async function whoAmI() {
  const response = await fetch("/api/me", { credentials: "same-origin" });
  const signedIn = response.ok;

  // Nothing chat-related renders without a session: no empty transcript, no box.
  form.hidden = !signedIn;
  logEl.hidden = !signedIn;
  signInCard.hidden = signedIn;

  if (!signedIn) {
    statusEl.replaceChildren("signed out");
    return;
  }
  const user = await response.json();
  statusEl.replaceChildren(`${user.email} · `, link("/logout", "logout"));
}

function showSystem(message) {
  line("system", message);
}

// Enter sends; Shift+Enter is a newline.
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

// Every message is answered on its own, so a new conversation is just a fresh
// transcript — there is no server-side history to forget.
newButton.addEventListener("click", () => {
  logEl.replaceChildren();
  input.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  line("you", message);
  input.value = "";
  const answerEl = line("bot", "…");
  input.focus();

  let response;
  try {
    response = await fetch("/api/chat/stream", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch {
    answerEl.remove();
    showSystem("network error");
    return;
  }

  if (!response.ok) {
    answerEl.remove();
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload.detail === "string" ? payload.detail : null;
    showSystem(
      detail ||
        STATUS_MESSAGES[response.status] ||
        `request failed (${response.status})`,
    );
    if (response.status === 401) whoAmI();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = consume(buffer, answerEl);
  }
});

whoAmI();

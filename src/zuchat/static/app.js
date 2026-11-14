// No framework, no build step: sign-in state plus one chat round-trip.
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const send = document.getElementById("send");

function add(role, text) {
  const item = document.createElement("li");
  item.className = role;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "you" ? "you" : role === "bot" ? "zuchat" : "";
  const body = document.createElement("p");
  body.textContent = text; // textContent, never innerHTML: the reply is untrusted
  item.append(who, body);
  logEl.append(item);
  item.scrollIntoView({ block: "end" });
}

async function loadMe() {
  const response = await fetch("/me", { credentials: "same-origin" });
  if (response.ok) {
    const user = await response.json();
    statusEl.replaceChildren(
      Object.assign(document.createElement("span"), {
        textContent: `signed in as ${user.email} · `,
      }),
      Object.assign(document.createElement("a"), { href: "/logout", textContent: "logout" }),
    );
    return true;
  }
  statusEl.replaceChildren(
    Object.assign(document.createElement("a"), { href: "/login", textContent: "sign in with Google" }),
  );
  return false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  add("you", message);
  input.value = "";
  send.disabled = true;

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ message }),
    });

    if (response.status === 401) {
      add("system", "Session expired — sign in again.");
      await loadMe();
      return;
    }
    if (!response.ok) {
      add("system", `Request failed (${response.status}).`);
      return;
    }
    const data = await response.json();
    add("bot", data.reply);
  } catch {
    add("system", "Network error.");
  } finally {
    send.disabled = false;
    input.focus();
  }
});

loadMe().catch(() => {
  statusEl.textContent = "could not reach the server";
});

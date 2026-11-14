// One page, one form, one fetch. No framework, no build step.
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const send = form.querySelector("button");

// textContent, never innerHTML: replies are untrusted.
function line(kind, text) {
  const li = document.createElement("li");
  li.className = kind;
  li.textContent = text;
  logEl.append(li);
  li.scrollIntoView();
}

function link(href, text) {
  const a = document.createElement("a");
  a.href = href;
  a.textContent = text;
  return a;
}

async function whoAmI() {
  const response = await fetch("/me");
  if (!response.ok) {
    statusEl.textContent = "signed out · ";
    statusEl.append(link("/login", "sign in"));
    return;
  }
  const user = await response.json();
  statusEl.textContent = `${user.email} · `;
  statusEl.append(link("/logout", "logout"));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  line("you", message);
  input.value = "";
  send.disabled = true;

  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  send.disabled = false;
  input.focus();

  if (response.ok) {
    line("bot", (await response.json()).reply);
  } else if (response.status === 401) {
    line("system", "session expired — sign in again");
    whoAmI();
  } else {
    line("system", `request failed (${response.status})`);
  }
});

whoAmI();

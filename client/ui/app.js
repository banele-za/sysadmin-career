// The game's web UI. Python pushes events in through game.onEvent(event);
// we call Python through window.pywebview.api.<method>().

const $ = (id) => document.getElementById(id);

// ---- terminal ---------------------------------------------------------------

const term = new Terminal({
  fontFamily: "Consolas, 'Cascadia Mono', monospace",
  fontSize: 15,
  cursorBlink: true,
  theme: { background: "#14161a", foreground: "#d7dae0" },
});
const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
term.open($("terminal"));
fit.fit();

// Keystrokes must reach Python in order. pywebview may run API calls in
// parallel, so we send one batch at a time and queue whatever arrives meanwhile.
let pendingInput = "";
let sending = false;
async function flushInput() {
  if (sending || !pendingInput) return;
  sending = true;
  const data = pendingInput;
  pendingInput = "";
  try {
    await window.pywebview.api.term_input(data);
  } finally {
    sending = false;
    flushInput();
  }
}
term.onData((data) => { pendingInput += data; flushInput(); });

function sendSize() {
  fit.fit();
  if (window.pywebview) window.pywebview.api.term_resize(term.cols, term.rows);
}
new ResizeObserver(sendSize).observe($("terminal"));

// Terminal output arrives base64-encoded bytes; xterm decodes UTF-8 itself.
function writeBase64(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  term.write(bytes);
}

// ---- helpers ------------------------------------------------------------------

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Tiny formatter for mentor messages: blank lines split paragraphs,
// 4-space indented lines are code blocks, `backticks` are inline code.
function formatMessage(text) {
  const blocks = text.split(/\n\s*\n/);
  return blocks.map((block) => {
    const lines = block.split("\n");
    if (lines.every((l) => l.startsWith("    "))) {
      return `<pre>${escapeHtml(lines.map((l) => l.slice(4)).join("\n"))}</pre>`;
    }
    const html = escapeHtml(lines.join(" ")).replace(/`([^`]+)`/g, "<code>$1</code>");
    return `<p>${html}</p>`;
  }).join("");
}

function setOverlay(text, isError = false) {
  const overlay = $("overlay");
  overlay.hidden = !text;
  overlay.classList.toggle("error", isError);
  $("overlay-text").textContent = text || "";
  if (!text) term.focus();
}

function bump(id, value) {
  const el = $(id);
  if (el.textContent !== String(value)) {
    el.textContent = value;
    el.parentElement.classList.add("bump");
    setTimeout(() => el.parentElement.classList.remove("bump"), 1200);
  }
}

// ---- events from Python ---------------------------------------------------------

const handlers = {
  status(e) { setOverlay(e.text); },

  error(e) { setOverlay("Something went wrong:\n" + e.text, true); },

  stats(e) {
    bump("xp", e.xp);
    bump("rep", e.rep);
    const badge = $("mode-badge");
    badge.hidden = !e.mode;
    badge.textContent = e.mode === "slow" ? "Slow mode" : "Fast mode";
    badge.className = "badge " + (e.mode || "");
  },

  ticket(e) {
    $("ticket-empty").hidden = true;
    $("ticket-body").hidden = false;
    $("ticket-title").textContent = e.title;
    $("ticket-from").textContent = e.from;
    $("ticket-role").textContent = e.role ? `(${e.role})` : "";
    $("ticket-narrative").textContent = e.narrative;
    $("ticket-reward").textContent = `Reward: ${e.rewards.xp} XP · ${e.rewards.rep} rep`;
    $("checks").innerHTML = "";
    $("submit-btn").hidden = false;
    $("submit-btn").disabled = false;
    $("next-btn").hidden = true;
    $("chat").innerHTML = e.guided ? "" :
      '<div class="dim">No walkthrough on this one. You know where the man pages are.</div>';
  },

  term_reset() { term.reset(); sendSize(); },

  term(e) { writeBase64(e.data); },

  mentor(e) {
    // Grey out the previous message's "Got it" button.
    document.querySelectorAll("#chat .msg button").forEach((b) => b.remove());
    const msg = document.createElement("div");
    msg.className = "msg";
    msg.innerHTML = `<div class="who">Senior Admin</div>${formatMessage(e.text)}`;
    if (e.needs_ack) {
      const btn = document.createElement("button");
      btn.textContent = "Got it";
      btn.onclick = () => { btn.remove(); window.pywebview.api.mentor_ack(); };
      msg.appendChild(btn);
    }
    $("chat").appendChild(msg);
    msg.scrollIntoView({ behavior: "smooth", block: "start" });
  },

  submit_ignored() { $("submit-btn").disabled = false; },

  mentor_step_done() {
    const msgs = document.querySelectorAll("#chat .msg");
    if (msgs.length) msgs[msgs.length - 1].classList.add("done");
  },

  graded(e) {
    const list = $("checks");
    list.innerHTML = "";
    const banner = document.createElement("li");
    banner.className = "banner " + (e.passed ? "pass" : "fail");
    banner.textContent = e.passed ? `Solved! +${e.xp} XP, +${e.rep} rep` : "Not quite yet:";
    list.appendChild(banner);
    for (const c of e.checks) {
      const li = document.createElement("li");
      li.className = c.pass ? "pass" : "fail";
      li.textContent = c.msg || c.name;
      list.appendChild(li);
    }
    $("submit-btn").disabled = false;
    if (e.passed) {
      $("submit-btn").hidden = true;
      $("next-btn").hidden = false;
    }
  },
};

window.game = {
  onEvent(event) {
    const handler = handlers[event.type];
    if (handler) handler(event);
    else console.warn("unknown event", event);
  },
};

// ---- buttons -------------------------------------------------------------------------

$("submit-btn").onclick = () => {
  $("submit-btn").disabled = true;
  window.pywebview.api.submit();
};
$("next-btn").onclick = () => {
  $("next-btn").hidden = true;
  window.pywebview.api.next_ticket();
};

// pywebview injects window.pywebview.api asynchronously; start once it's there.
window.addEventListener("pywebviewready", () => {
  sendSize();
  window.pywebview.api.ready();
});

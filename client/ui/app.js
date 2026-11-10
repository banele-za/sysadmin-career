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
    const html = escapeHtml(lines.join(" "))
      .replace(/`([^`]+)`/g, "<code>$1</code>")          // `code`
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");          // **bold**
    return `<p>${html}</p>`;
  }).join("");
}

// The story modal shows one page at a time; "Next" turns the page, the last
// page's button closes it. (The game keeps running behind it.)
const story = { pages: [], index: 0 };

function showStoryPage() {
  const page = story.pages[story.index];
  const last = story.index === story.pages.length - 1;
  $("story-step").textContent = story.pages.length > 1 ? `${story.index + 1} / ${story.pages.length}` : "";
  $("story-title").textContent = page.title;
  $("story-text").innerHTML = formatMessage(page.text);
  $("story-next").textContent = last ? "Let's go" : "Next";
}

// Reward line and Hint button, from the hint fields of a ticket or hint event.
// Hints are paid out of the ticket's own rep reward (see engine/economy.py).
function showHintState(e) {
  if (e.rewards) $("ticket-reward").dataset.xp = e.rewards.xp;   // hint events don't repeat it
  const xp = $("ticket-reward").dataset.xp;
  let text = `Reward: ${xp} XP · ${e.reward_now} rep`;
  if (e.hints_used) text += ` (after ${e.hints_used} hint${e.hints_used > 1 ? "s" : ""})`;
  $("ticket-reward").textContent = text;
  const left = e.hints_total - e.hints_used;
  $("hint-btn").hidden = left <= 0;
  $("hint-btn").textContent = `Hint ${e.hints_used + 1}/${e.hints_total} (−${e.next_hint_cost} rep)`;
}

function setOverlay(text, isError = false) {
  const overlay = $("overlay");
  overlay.hidden = !text;
  overlay.classList.toggle("error", isError);
  $("overlay-text").textContent = text || "";
  if (!text) term.focus();
}

function showNotice(text, restart) {
  $("checkup-notice").hidden = false;
  $("checkup-notice-text").textContent = text;
  $("checkup-restart").hidden = !restart;
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
    $("tier-name").textContent = e.tier;
    $("tier-progress").textContent = `${e.tier_solved} / ${e.tier_total}`;
    const badge = $("mode-badge");
    badge.hidden = !e.mode;
    badge.textContent = e.mode === "slow" ? "Slow mode · Try to fix again" : "Fast mode";
    badge.className = "badge " + (e.mode || "");
  },

  // ---- checkup screen ----

  checkup(e) {
    const c = e.checkup;
    $("checkup").hidden = false;
    $("checkup-main").hidden = false;
    $("guide").hidden = true;
    $("download").hidden = true;
    if (!e.can_close) $("checkup-notice").hidden = true;

    $("checkup-intro").textContent =
      e.error ? "Something went wrong while starting the server. Here's what the checkup found:" :
      c.blocking ? "One thing needs sorting out before the game can start:" :
      c.mode === "slow" ? "Fast mode isn't available on this computer yet. You can play right now " +
                          "in slow mode, or try the fixes below first." :
      "Everything looks good. Your computer is ready.";
    $("checkup-fake").hidden = !e.fake.length;
    $("checkup-fake").textContent = `Test mode: pretending ${e.fake.join(", ")} (SYSADMIN_GAME_FAKE)`;
    $("checkup-error").hidden = !e.error;
    $("checkup-error").textContent = e.error;

    const list = $("checkup-list");
    list.innerHTML = "";
    for (const check of c.checks) {
      const li = document.createElement("li");
      li.className = check.status;
      li.innerHTML = `<span class="dot"></span><div><b></b><div class="msg-text"></div></div>`;
      li.querySelector("b").textContent = check.title;
      li.querySelector(".msg-text").textContent = check.message;
      for (const action of check.actions) {
        if (action.id === "retry") continue;            // the footer has "Check again"
        const btn = document.createElement("button");
        btn.textContent = action.label;
        btn.dataset.action = action.id;
        li.appendChild(btn);
      }
      list.appendChild(li);
    }

    // Footer: what can the player do next?
    const playing = e.can_close;
    $("checkup-close").hidden = !playing;
    $("checkup-continue").hidden = playing || c.blocking || c.mode === "slow";
    $("checkup-continue").textContent = e.error ? "Try again" : "Start playing";
    $("checkup-slow").hidden = playing || c.blocking || c.mode !== "slow";
    $("checkup-slow").className = c.mode === "slow" ? "primary" : "";
    if (e.error && c.mode === "slow" && !c.blocking) $("checkup-slow").textContent = "Try again in slow mode";
    else $("checkup-slow").textContent = "Play in slow mode";
    if (playing && e.running_mode === "slow" && c.mode === "fast") {
      showNotice("Fast mode works now! Close and reopen the game to switch to it.", false);
    }
  },

  checkup_notice(e) { showNotice(e.text, e.restart); },

  checkup_closed() { $("checkup").hidden = true; term.focus(); },

  download_progress(e) {
    $("download").hidden = false;
    const percent = Math.floor((e.done * 100) / Math.max(e.total, 1));
    $("download-bar").style.width = percent + "%";
    $("download-text").textContent =
      `Downloading the Linux server: ${(e.done / 1e6).toFixed(0)} of ${(e.total / 1e6).toFixed(0)} MB (${percent}%)`;
  },

  guide(e) {
    $("checkup-main").hidden = true;
    $("guide").hidden = false;
    $("guide-title").textContent = `Turning on the speed boost (${e.brand})`;
    $("guide-setting").textContent = e.setting;
    $("guide-placeholder").hidden = !e.placeholder;
    const steps = $("guide-steps");
    steps.innerHTML = "";
    for (const step of e.steps) {
      const li = document.createElement("li");
      li.innerHTML = "<b></b><p></p>";
      li.querySelector("b").textContent = step.title;
      li.querySelector("p").textContent = step.text;
      if (step.screen) {
        const screen = document.createElement("pre");     // placeholder "illustration"
        screen.className = "bios-screen";
        screen.textContent = step.screen;
        li.appendChild(screen);
      }
      steps.appendChild(li);
    }
    $("guide-notes").innerHTML = "";
    for (const note of e.notes) {
      const li = document.createElement("li");
      li.textContent = note;
      $("guide-notes").appendChild(li);
    }
  },

  ticket(e) {
    $("ticket-empty").hidden = true;
    $("ticket-body").hidden = false;
    $("ticket-title").textContent = e.title;
    $("ticket-from").textContent = e.from;
    $("ticket-role").textContent = e.role ? `(${e.role})` : "";
    $("ticket-avatar").textContent = e.initials;
    $("ticket-avatar").style.background = e.color;
    $("ticket-callback").hidden = !e.callback;
    $("ticket-callback").textContent = e.callback;
    $("ticket-narrative").textContent = e.narrative;
    $("hints").innerHTML = "";
    showHintState(e);
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

  hint(e) {
    const li = document.createElement("li");
    li.innerHTML = formatMessage(e.text);
    $("hints").appendChild(li);
    showHintState(e);
  },

  story(e) {
    story.pages = e.pages;
    story.index = 0;
    showStoryPage();
    $("story").hidden = false;
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
    if (e.man_bonus) {
      const li = document.createElement("li");
      li.className = "banner pass bonus";
      li.textContent = `Includes +${e.man_bonus} XP for reading the manual.`;
      list.appendChild(li);
    }
    for (const c of e.checks) {
      const li = document.createElement("li");
      li.className = c.pass ? "pass" : "fail";
      li.textContent = c.msg || c.name;
      list.appendChild(li);
    }
    $("submit-btn").disabled = false;
    if (e.passed) {
      $("submit-btn").hidden = true;
      $("hint-btn").hidden = true;
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
$("hint-btn").onclick = () => window.pywebview.api.hint();
$("story-next").onclick = () => {
  if (story.index < story.pages.length - 1) {
    story.index += 1;
    showStoryPage();
  } else {
    $("story").hidden = true;
    term.focus();
  }
};
$("next-btn").onclick = () => {
  $("next-btn").hidden = true;
  window.pywebview.api.next_ticket();
};

// Every checkup / guide button carries data-action="<name>" for Game.checkup_action.
// Buttons are created on the fly, so one listener on the whole modal handles them.
$("checkup").addEventListener("click", (event) => {
  const btn = event.target.closest("button");
  if (!btn) return;
  if (btn.hasAttribute("data-dismiss")) { $("checkup-notice").hidden = true; return; }
  const action = btn.dataset.action;
  if (!action) return;
  if (action === "download") btn.disabled = true;       // one download at a time
  window.pywebview.api.checkup_action(action);
});
$("guide-back").onclick = () => { $("guide").hidden = true; $("checkup-main").hidden = false; };
$("checkup-btn").onclick = () => window.pywebview.api.open_checkup();
$("mode-badge").onclick = () => window.pywebview.api.open_checkup();

// pywebview injects window.pywebview.api asynchronously; start once it's there.
window.addEventListener("pywebviewready", () => {
  sendSize();
  window.pywebview.api.ready();
});

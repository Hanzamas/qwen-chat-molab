UI_APP_JS = r"""
const MAX_FILE = 25 * 1024 * 1024;
const TAB_ICONS = { chat: "sliders", story: "book", cards: "card", memory: "bookmark", model: "cpu", learn: "learn" };
const TAB_NAMES = { chat: "Chat", story: "Story", cards: "Cards", memory: "Memory", model: "Model", learn: "Learn" };
const KIND_ICON = { chat: "chat", rp: "book", group: "users", studio: "sparkles" };
// Values the server stores or compares (knowledge kinds, truth and sources, thread kinds and statuses, proposal and
// fact status, fame, reply length, lore kinds) stay as they are; only the text on screen is English. An unknown value
// shows as it is.
const LABELS = {
  fakta: "fact", rahasia: "secret", pendapat: "opinion", perasaan: "feeling", janji: "promise", "salah paham": "misunderstanding",
  kenalan: "acquaintance", benar: "true", keliru: "false", "belum pasti": "unsure",
  "lihat sendiri": "saw it", "diberi tahu": "heard it", gosip: "gossip", menduga: "guessed",
  "janji temu": "appointment", misteri: "mystery", petunjuk: "clue", utang: "debt", dendam: "grudge", rencana: "plan", lain: "other",
  terbuka: "open", selesai: "done", gagal: "failed", batal: "dropped",
  menunggu: "pending", diterima: "accepted", ditolak: "rejected",
  terverifikasi: "verified", diperdebatkan: "disputed", "belum terverifikasi": "unverified",
  bintang: "star", terkenal: "famous", "dikenal di lingkungannya": "known locally", biasa: "ordinary",
  pendek: "short", sedang: "medium", panjang: "long",
  istilah: "term", tempat: "place", faksi: "faction", benda: "object", peristiwa: "event",
};
const lab = (v) => (Object.prototype.hasOwnProperty.call(LABELS, v) ? LABELS[v] : v);
// Time-skip labels ("2 jam") are parsed by the server: buttons keep the label, the screen shows it in English.
const SKIP_UNITS = { menit: "minute", jam: "hour", hari: "day", minggu: "week", bulan: "month", tahun: "year" };
const skipLabel = (t) => String(t ?? "").replace(/^\s*(\d+)\s*(menit|jam|hari|minggu|bulan|tahun)\s*$/i,
  (m, n, u) => `${n} ${SKIP_UNITS[u.toLowerCase()]}${Number(n) === 1 ? "" : "s"}`);

function render({ model, el }) {
  // marimo may render into the same element again: drop the previous view's listeners first,
  // or every click runs twice and toggles undo themselves.
  if (el.__qrCleanup) el.__qrCleanup();
  const ac = new AbortController();
  const listen = (type, fn, capture) => el.addEventListener(type, fn, { capture: !!capture, signal: ac.signal });
  el.classList.add("qr");
  el.innerHTML = `
  <aside class="qr-side">
    <div class="qr-brand">${icon("sparkles")}<span>Qwen Chat RP</span></div>
    <div class="qr-new">
      <button class="qr-btn qr-primary" data-act="new" data-kind="chat">${icon("plus")}Chat</button>
      <button class="qr-btn" data-act="story-wizard">${icon("book")}Story</button>
      <button class="qr-btn" data-act="studio">${icon("sparkles")}Studio</button>
    </div>
    <label class="qr-search">${icon("search")}<input class="qr-search-in" placeholder="Search chats (Enter: search message text)"></label>
    <nav class="qr-chats"></nav>
    <div class="qr-side-foot">
      <div class="qr-backup"></div>
      <div class="qr-row"><button class="qr-btn qr-sm" data-act="save-db">${icon("download")}Save</button>
        <button class="qr-btn qr-sm" data-act="load-db">${icon("upload")}Load</button></div>
    </div>
  </aside>
  <section class="qr-main">
    <header class="qr-top">
      <button class="qr-icon qr-toggle" data-act="toggle-side" aria-label="Chat list">${icon("menu")}</button>
      <div class="qr-title" title="Double-click to rename"></div>
      <div class="qr-chips"></div>
      <button class="qr-icon qr-toc-btn" data-act="toc" title="Chapters" hidden>${icon("bookmark")}</button>
      <button class="qr-icon" data-act="compact" title="Compact: condense old context">${icon("archive")}</button>
      <button class="qr-icon" data-act="open-tab" data-tab="story" title="Story and cards">${icon("book")}</button>
      <button class="qr-icon" data-act="open-tab" data-tab="chat" title="Settings">${icon("sliders")}</button>
    </header>
    <div class="qr-ctxbar"><div class="qr-ctxfill"></div></div>
    <div class="qr-status-panel" hidden></div>
    <div class="qr-body">
      <div class="qr-scroll" tabindex="0">
        <div class="qr-col">
          <button class="qr-btn qr-sm qr-more" data-act="load-more" hidden>Load earlier messages</button>
          <div class="qr-empty"></div>
          <div class="qr-list"></div>
          <div class="qr-live"></div>
        </div>
      </div>
      <aside class="qr-studio" hidden></aside>
      <button class="qr-jump" data-act="jump" hidden aria-label="Jump to the latest message">${icon("arrowdown")}</button>
    </div>
    <div class="qr-world" hidden></div>
    <div class="qr-composer">
      <div class="qr-notice" hidden></div>
      <div class="qr-speaker-bar" hidden></div>
      <div class="qr-pending" hidden></div>
      <div class="qr-statusline" hidden></div>
      <form class="qr-form">
        <button type="button" class="qr-icon" data-act="attach" title="Attach files">${icon("clip")}</button>
        <button type="button" class="qr-icon" data-act="impersonate" title="Draft my reply (impersonate)">${icon("wand")}</button>
        <textarea class="qr-input" rows="1" placeholder="Send a message · Enter to send · Shift+Enter for a new line · /ooc /note /bab /ingat /studio"></textarea>
        <button type="button" class="qr-note-chip" data-act="open-tab" data-tab="chat" hidden></button>
        <button type="submit" class="qr-send" aria-label="Send">${icon("send")}</button>
      </form>
    </div>
    <div class="qr-drop" hidden>Drop files to attach</div>
  </section>
  <aside class="qr-drawer" hidden>
    <div class="qr-drawer-head"><div class="qr-tabs"></div><button class="qr-icon" data-act="close-drawer" aria-label="Close">${icon("x")}</button></div>
    <div class="qr-drawer-body"></div>
  </aside>
  <div class="qr-modal" hidden><div class="qr-modal-box"><div class="qr-modal-head"><span class="qr-modal-title"></span>
    <button class="qr-icon" data-act="close-modal" aria-label="Close">${icon("x")}</button></div><div class="qr-modal-body"></div></div></div>
  <div class="qr-toasts"></div>
  <input type="file" class="qr-file-db" accept=".sqlite,.db" hidden>
  <input type="file" class="qr-file-att" multiple hidden>
  <input type="file" class="qr-file-card" accept=".json,.png" hidden>
  <input type="file" class="qr-file-avatar" accept="image/*" hidden>`;

  const $ = (q) => el.querySelector(q);
  const scroll = $(".qr-scroll"), list = $(".qr-list"), liveBox = $(".qr-live"), input = $(".qr-input");
  const drawer = $(".qr-drawer"), dbody = $(".qr-drawer-body"), modal = $(".qr-modal");
  const state = { tab: "chat", pending: [], open: new Set(), cardView: null, learn: false, studioCard: null, libFilter: "",
    cards: new Map() };
  const rootActive = () => el.getRootNode().activeElement || document.activeElement;
  const els = new Map();
  const fol = follower(scroll, (on) => { $(".qr-jump").hidden = on; });
  const ro1 = new ResizeObserver(() => fol.stick());
  ro1.observe($(".qr-col"));

  // Commands carry a sequence number and stay in the outbox until Python acknowledges them. The command traitlet is
  // synced as a value and marimo merges updates that queue up while the kernel is busy (only the last arrives), so
  // every message repeats all unacknowledged commands; Python skips the ones it already ran.
  const sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
  let unacked = [], seq = 0, flushTimer = 0;
  const flush = () => {
    flushTimer = 0;
    if (!unacked.length) return;
    model.set("command", { n: Date.now() + Math.random(), sid, batch: unacked.slice() });
    model.save_changes();
  };
  const send = (action, extra = {}) => {
    unacked.push({ action, ...extra, _seq: ++seq });
    if (!flushTimer) flushTimer = setTimeout(flush, 0);
  };
  model.on("change:ack", () => {
    const a = model.get("ack") || {};
    if (a.sid === sid) unacked = unacked.filter((c) => c._seq > a.seq);
  });
  // Redrawing a drawer section: while a field in it has focus the redraw waits until focus leaves the section
  // (redrawing under the cursor breaks typing and the phone keyboard). With keep, text typed and not saved yet stays.
  const TEXT_FIELDS = "input:not([type]), input[type=text], textarea";
  const fieldKey = (n) => {
    const row = n.closest("[data-kid],[data-tid],[data-pid],[data-sec],[data-entry]");
    const id = row ? ["kid", "tid", "pid", "sec", "entry"].map((k) => row.dataset[k] ?? "").join("/") : "";
    return `${id}|${n.className}|${n.dataset.field || ""}`;
  };
  const waiting = new Set();
  const redraw = (box, html, keep = false) => {
    if (!box) return;
    const f = rootActive();
    if (f && box.contains(f) && /^(INPUT|TEXTAREA|SELECT)$/.test(f.tagName)) { box._redraw = [html, keep]; waiting.add(box); return; }
    const typed = new Map(), chat = String(get("chat").id || "");
    if (keep && box.dataset.chat === chat)
      box.querySelectorAll(TEXT_FIELDS).forEach((n) => { if (n.value !== n.defaultValue) typed.set(fieldKey(n), n.value); });
    box._redraw = null; waiting.delete(box);
    box.innerHTML = typeof html === "function" ? html() : html;
    box.dataset.chat = chat;
    if (typed.size) box.querySelectorAll(TEXT_FIELDS).forEach((n) => { const k = fieldKey(n); if (typed.has(k)) n.value = typed.get(k); });
  };
  let pointerDown = false;
  const flushRedraws = () => {
    if (pointerDown) return;  // a click inside the section is under way: its button must still be there for the click
    for (const box of [...waiting]) {
      if (!box.isConnected || !box._redraw) { waiting.delete(box); continue; }
      const f = rootActive();
      if (!(f && box.contains(f) && /^(INPUT|TEXTAREA|SELECT)$/.test(f.tagName))) redraw(box, ...box._redraw);
    }
  };
  listen("focusout", () => setTimeout(flushRedraws, 0), true);
  listen("pointerdown", () => { pointerDown = true; }, true);
  for (const ev of ["pointerup", "pointercancel"]) listen(ev, () => setTimeout(() => { pointerDown = false; flushRedraws(); }, 60), true);
  const get = (k) => model.get(k) || {};
  const toast = (text, kind = "info", long = false) => {
    const t = document.createElement("div");
    t.className = `qr-toast qr-${kind}`;
    t.textContent = text;
    t.addEventListener("click", () => t.remove());
    $(".qr-toasts").appendChild(t);
    setTimeout(() => t.remove(), long ? 12000 : 4500);
  };
  const openModal = (title, html, wizard = false) => { state.wizard = wizard; $(".qr-modal-title").textContent = title; $(".qr-modal-body").innerHTML = html; modal.hidden = false; };
  const closeModal = () => { state.wizard = false; modal.hidden = true; $(".qr-modal-body").innerHTML = ""; };

  // theme follows marimo (dark class on the page) or the OS
  const syncTheme = () => {
    const d = document.documentElement, b = document.body;
    const dark = d.classList.contains("dark") || b.classList.contains("dark") || d.dataset.theme === "dark" ||
      (!d.classList.contains("light") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    el.dataset.theme = dark ? "dark" : "light";
  };
  syncTheme();
  const themeObs = new MutationObserver(syncTheme);
  themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme"] });
  themeObs.observe(document.body, { attributes: true, attributeFilter: ["class"] });

  // ---------- sidebar ----------
  function renderChats() {
    const chats = model.get("chats") || [], cur = get("chat").id;
    const q = $(".qr-search-in").value.trim().toLowerCase();
    const groups = { Stories: [], Studio: [], Chat: [] };
    for (const c of chats) {
      if (q && !c.title.toLowerCase().includes(q) && !(c.story_title || "").toLowerCase().includes(q)) continue;
      (c.kind === "rp" || c.kind === "group" ? groups.Stories : c.kind === "studio" ? groups.Studio : groups.Chat).push(c);
    }
    $(".qr-chats").innerHTML = Object.entries(groups).filter(([, v]) => v.length).map(([g, v]) => `
      <div class="qr-group">${g}</div>
      ${v.map((c) => `<div class="qr-chat ${c.id === cur ? "on" : ""}" data-chat="${c.id}">
        ${icon(KIND_ICON[c.kind] || "chat")}<span class="qr-chat-t" title="${esc(c.title)}">${esc(c.title)}</span>
        <button class="qr-icon qr-xs" data-act="rename-chat" data-id="${c.id}" title="Rename">${icon("edit")}</button>
        <button class="qr-icon qr-xs" data-act="delete-chat" data-id="${c.id}" title="Delete">${icon("trash")}</button></div>`).join("")}`).join("")
      || `<div class="qr-muted qr-pad">No chats yet.</div>`;
  }
  function renderBackup() {
    const b = get("backup");
    $(".qr-backup").innerHTML = b.enabled
      ? `${icon("cloud")}<span>${b.busy ? "Backup…" : b.last_error ? "Backup failed" : `Saved ${ago(b.last_ok)}`}${b.dirty ? " · unsaved changes" : ""}</span>`
      : `${icon("cloud")}<span>HF backup off · add a token in the Backup cell</span>`;
    $(".qr-backup").title = b.last_error || b.repo || "";
  }

  // ---------- top bar ----------
  function renderTop() {
    const c = get("chat"), s = get("server"), ctx = get("ctx"), p = get("panels");
    $(".qr-title").textContent = c.title || "New chat";
    const phaseCls = s.phase === "ready" ? "ok" : s.phase === "failed" ? "bad" : s.phase === "idle" ? "off" : "wait";
    const short = (s.preset || "Model not running").split(" · ")[0];
    const preset = (get("boot").presets || []).find((x) => x.name === s.preset);
    const lvl = (c.settings || {}).thinking || (preset ? preset.thinking[preset.thinking.length - 1] : "");
    const pct = ctx.max ? Math.min(100, (ctx.used / ctx.max) * 100) : 0;
    const ctxTitle = ctx.max ? `prompt ${fmtN(ctx.used)} / ${fmtN(ctx.max)} tokens${ctx.reserve ? ` · reply room ${fmtN(ctx.reserve)}` : ""} · auto compaction at ${Math.round((ctx.at || 0.8) * 100)}%` : "";
    $(".qr-chips").innerHTML = `
      <button class="qr-chip" data-act="open-tab" data-tab="model" title="${esc(s.preset || "")}"><i class="qr-dot ${phaseCls}"></i>${esc(short)}${s.ctx ? ` · ${Math.round(s.ctx / 1024)}K` : ""}</button>
      ${lvl ? `<span class="qr-chip qr-ghost" title="Thinking level">${icon("brain")}${esc(lvl)}</span>` : ""}
      ${ctx.max ? `<span class="qr-chip qr-ghost" title="${esc(ctxTitle)}">${pct.toFixed(0)}%</span>` : ""}
      ${p.time ? `<span class="qr-chip qr-ghost" title="World clock">${icon("clock")}${esc(p.time)}</span>` : ""}
      ${p.lang ? `<span class="qr-chip qr-ghost" title="Your character's ${esc(p.lang.label)} level; it rises as you play">${icon("book")}${esc(p.lang.label)} ${esc(p.lang.band)} · ${p.lang.value}</span>` : ""}`;
    $(".qr-ctxfill").style.width = `${pct}%`;
    $(".qr-ctxfill").classList.toggle("warn", pct > 85);
    const note = (c.settings || {}).note;
    $(".qr-note-chip").hidden = !note;
    $(".qr-note-chip").textContent = note ? `Note: ${note.slice(0, 40)}${note.length > 40 ? "…" : ""}` : "";
  }

  // ---------- panels (game format) ----------
  function renderPanels() {
    const p = get("panels");
    const sp = $(".qr-status-panel"), wp = $(".qr-world");
    const game = p.format === "game";
    sp.hidden = !game;
    wp.hidden = !game;
    if (!game) return;
    const bar = (s) => {
      const lo = s.min ?? 0, hi = s.max ?? 100;
      const pct = hi > lo ? Math.max(0, Math.min(100, ((s.value - lo) / (hi - lo)) * 100)) : 0;
      const ch = s.change && Math.abs(s.change.delta) >= 0.05 ? `<em class="${s.change.delta > 0 ? "up" : "dn"}">${s.change.delta > 0 ? "+" : ""}${Number(s.change.delta.toFixed(1))}</em>` : "";
      return `<div class="qr-stat" title="${esc(s.change ? s.change.reason || "" : "")}"><span>${esc(s.label)}</span>
        <div class="qr-sbar"><i style="width:${pct}%"></i></div><b>${Number(s.value)}</b>${ch}</div>`;
    };
    const status = Object.entries(p.status || {}).map(([k, v]) => `<span class="qr-tag">${esc(k)}: ${esc(Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : v)}</span>`).join("");
    // Without GM mode only what your character can see of the people around: no plans, attitudes, knowledge.
    const npcs = Object.entries(p.gm_view ? p.characters_gm || {} : p.characters || {});
    const gmBtn = `<button class="qr-btn qr-sm ${p.gm_view ? "qr-primary" : ""}" data-act="gm-view" title="Show every character's state (spoiler)">GM mode</button>`;
    const npcHTML = p.time !== undefined ? `<details class="qr-npcs" data-key="npcs" ${state.open.has("npcs") ? "open" : ""}><summary>${icon("users")}${p.gm_view ? "All characters (GM mode)" : "Visible around you"} (${npcs.length}) ${gmBtn}</summary>
      ${npcs.map(([name, st]) => `<div class="qr-npc"><b>${esc(name)}</b> ${Object.entries(st).map(([k, v]) => `<span class="qr-tag">${esc(k)}: ${esc(Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)).slice(0, 120)}</span>`).join("")}</div>`).join("")}</details>` : "";
    sp.innerHTML = `<div class="qr-sp-head">${icon("clock")}<b>${esc(p.time)}</b><span>·</span>${icon("map")}<span>${esc(p.location || "-")}</span>
        <span>·</span><span>Turn ${p.turn}</span>${p.story ? `<span class="qr-muted">· ${esc(p.story)}</span>` : ""}</div>
      ${p.stats && p.stats.length ? `<div class="qr-stats">${p.stats.map(bar).join("")}</div>` : ""}
      ${status ? `<div class="qr-tags">${status}</div>` : ""}
      ${(p.relations || []).length ? `<div class="qr-tags">${icon("users")}${p.relations.map((r) => `<span class="qr-tag" title="${esc(r.last)}">${esc(r.who)}: ${esc(r.word)} (${r.score > 0 ? "+" : ""}${Math.round(r.score)})</span>`).join("")}</div>` : ""}${npcHTML}`;
    const open = state.open.has("world");
    wp.innerHTML = `<button class="qr-world-head" data-act="toggle-world">${icon("globe")}<b>World</b>
        <span class="qr-muted">${esc(p.weather || "")}</span>${(p.events || []).some((e) => e.new) ? '<i class="qr-dot ok"></i>' : ""}${icon(open ? "down" : "right")}</button>
      <div class="qr-world-body" ${open ? "" : "hidden"}>
        ${(p.events || []).map((e) => `<div class="qr-event ${e.new ? "new" : ""}"><span class="qr-muted">${esc(e.time)}</span> ${esc(e.text)}</div>`).join("") || '<div class="qr-muted">No news yet.</div>'}
        ${(p.time_skips || []).length ? `<div class="qr-skips">${icon("skip")}${p.time_skips.map((t) => `<button class="qr-btn qr-sm" data-act="time-skip" data-label="${esc(t)}">${esc(skipLabel(t))}</button>`).join("")}</div>` : ""}
      </div>`;
  }

  // ---------- messages ----------
  function toolChips(tools, key) {
    if (!tools || !tools.length) return "";
    const chips = toolChipList(tools, key);
    if (tools.length === 1) return `<div class="qr-tools">${chips}</div>`;
    // several calls fold into one line; opened, each call shows as before
    const k = `${key}-ts`, run = tools.some((t) => t.running), err = tools.filter((t) => t.error).length;
    return `<div class="qr-tools"><details class="qr-tool qr-toolset ${err ? "err" : ""}" data-key="${k}" ${state.open.has(k) ? "open" : ""}>
      <summary>${icon("tool")}<b>${tools.length} tools</b><span>${esc([...new Set(tools.map((t) => t.name))].join(", "))}</span>${run ? "<em>running…</em>" : err ? `<em>${err} failed</em>` : ""}</summary>
      <div class="qr-tools">${chips}</div></details></div>`;
  }
  function toolChipList(tools, key) {
    return `${tools.map((t, j) => {
      const k = `${key}-t${j}`;
      const st = t.running ? "running…" : t.error ? "failed" : "";
      let args = "";
      try { args = Object.values(JSON.parse(t.args || "{}")).map((v) => typeof v === "object" ? JSON.stringify(v) : String(v)).join(", ").slice(0, 80); } catch (e) { args = String(t.args || "").slice(0, 80); }
      return `<details class="qr-tool ${t.error ? "err" : ""}" data-key="${k}" ${state.open.has(k) ? "open" : ""}>
        <summary>${icon("tool")}<b>${esc(t.name)}</b><span>${esc(args)}</span>${st ? `<em>${st}</em>` : ""}</summary>
        <pre>${esc(t.result || (t.running ? "…" : ""))}</pre></details>`;
    }).join("")}`;
  }
  // Live thinking opens by itself outside stories; in a story it stays closed (it can spoil the scene) until opened,
  // and then stays open for the next replies too.
  const rpChat = () => ["rp", "group"].includes(get("chat").kind);
  function thinkBlock(key, text, label, live) {
    return `<details class="qr-think" data-key="${key}" ${state.open.has(key) || (live && !rpChat()) ? "open" : ""}>
      <summary>${icon("brain")}<span>${label}</span><span class="qr-muted">${fmtN(words(text))} words</span></summary>
      <div class="qr-think-box"><div class="qr-think-body">${esc(text)}</div></div>
      ${live ? '<button class="qr-btn qr-sm qr-think-follow" data-act="think-follow" hidden>Follow</button>' : ""}
      <button class="qr-btn qr-sm qr-think-full" data-act="think-full">Show full</button></details>`;
  }
  function actionsBar(it) {
    const sw = it.swipe && it.swipe[1] > 1
      ? `<span class="qr-swipe"><button class="qr-icon qr-xs" data-act="swipe" data-id="${it.id}" data-dir="-1">${icon("left")}</button>${it.swipe[0]}/${it.swipe[1]}<button class="qr-icon qr-xs" data-act="swipe" data-id="${it.id}" data-dir="1">${icon("right")}</button></span>` : "";
    const b = (act, ic, title, id = it.id) => `<button class="qr-icon qr-xs" data-act="${act}" data-id="${id}" title="${title}">${icon(ic)}</button>`;
    const ba = (act, ic, title) => b(act, ic, title, it.answer_id || it.id);
    if (it.kind === "user") return `<div class="qr-actions">${sw}${it.has_note ? b("note-view", "eye", "System note for this turn") : ""}${b("copy", "copy", "Copy")}${b("edit", "edit", "Edit (creates a branch)")}${b("pin", "pin", it.pinned ? "Unpin" : "Pin")}${b("branch", "branch", "Branch from here")}${b("delete", "trash", "Delete")}</div>`;
    return `<div class="qr-actions">${sw}${b("copy", "copy", "Copy")}${b("reroll", "refresh", "Regenerate")}${b("continue", "forward", "Continue")}${ba("edit", "edit", "Edit")}${ba("pin", "pin", it.pinned ? "Unpin" : "Pin")}${ba("chapter", "bookmark", "Mark chapter")}${ba("fact-check", "flag", "Fact-check")}${ba("continuity", "users", "Check continuity")}${b("branch", "branch", "Branch from here")}${b("delete", "trash", "Delete")}</div>`;
  }
  function statsLine(st) {
    if (!st) return "";
    const bits = [];
    if (st.tokens) bits.push(`${fmtN(st.tokens)} tokens`);
    if (st.tps) bits.push(`${st.tps.toFixed(1)} tok/s`);
    if (st.think_s) bits.push(`thinking ${st.think_s.toFixed(0)} s`);
    if (st.tools) bits.push(`${st.tools} ${st.tools === 1 ? "tool" : "tools"}`);
    if (st.total_s) bits.push(`total ${st.total_s.toFixed(0)} s`);
    if (st.stopped) bits.push("stopped");
    return bits.length ? `<div class="qr-stats-line" title="${esc(st.model || "")}">${bits.join(" · ")}</div>` : "";
  }
  // Avatars go into one <style> per story (a class per character), not into every speaker paragraph.
  const avStyle = document.createElement("style");
  el.appendChild(avStyle);
  function syncAvatars() {
    const map = {}, css = [];
    (get("story").cards || []).filter((x) => x.role === "character").forEach((x) => {
      map[x.name.toLowerCase()] = { cls: x.avatar ? `qr-av-${x.id}` : "", name: x.name };
      if (x.avatar) css.push(`.qr .qr-av-${x.id}{background-image:url(data:image/png;base64,${x.avatar});background-size:cover;background-position:center}`);
    });
    const text = css.join("\n");
    if (avStyle.textContent !== text) avStyle.textContent = text;
    const sig = JSON.stringify(Object.entries(map).map(([k, v]) => [k, v.cls]));
    const changed = state.avSig !== undefined && state.avSig !== sig;
    state.avMap = map;
    state.avSig = sig;
    return changed;
  }
  function speakers(html) {
    const c = get("chat");
    if (c.kind !== "group") return html;
    const av = state.avMap || {};
    return html.replace(/<p><strong>([^<]{1,60})<\/strong>/g, (m, name) => {
      const key = name.replace(/[:：]$/, "").trim().toLowerCase();
      if (!(key in av)) return m;
      const img = av[key].cls ? `<span class="qr-avatar sm ${av[key].cls}"></span>` : `<span class="qr-avatar sm qr-noav">${icon("card")}</span>`;
      return `<p class="qr-speaker">${img}<strong>${name}</strong>`;
    });
  }
  // The speaker bar: with a large cast it shows who is in the scene (and the chosen speaker); everyone else is one
  // click away with a search, and the whole bar folds into one chip. The choice is remembered in this browser.
  function spkMode() {
    if (!state.spk) { try { state.spk = localStorage.getItem("qr-spk") || "scene"; } catch (e) { state.spk = "scene"; } }
    return state.spk;
  }
  function setSpk(mode) {
    state.spk = mode;
    try { localStorage.setItem("qr-spk", mode); } catch (e) { /* private window: this session only */ }
    renderSpeakerBar();
  }
  function renderSpeakerBar() {
    const c = get("chat"), bar = $(".qr-speaker-bar");
    const chars = Object.values(state.avMap || {});
    bar.hidden = c.kind !== "group" || !chars.length;
    if (bar.hidden) return;
    const f = rootActive();
    if (f && bar.contains(f) && f.classList.contains("qr-spk-q")) return;  // searching: do not redraw under the cursor
    const cur = ((c.settings || {}).speaker || "").toLowerCase(), single = (c.settings || {}).group_mode === "single";
    const lead = single ? "Model picks" : "GM (everyone)";
    const chip = (x) => `<button class="qr-chip ${cur === x.name.toLowerCase() ? "on" : ""}" data-act="speaker" data-name="${esc(x.name)}">${x.cls ? `<span class="qr-avatar sm ${x.cls}"></span>` : ""}${esc(x.name)}</button>`;
    const mode = spkMode();
    if (mode === "hidden") {
      const who = cur ? (chars.find((x) => x.name.toLowerCase() === cur) || { name: cur }).name : lead;
      bar.innerHTML = `<button class="qr-chip qr-ghost" data-act="spk-mode" data-mode="scene" title="Show the speaker choice">${icon("users")}Next: ${esc(who)}</button>`;
      return;
    }
    const small = chars.length <= 8, all = small || mode === "all";
    const here = new Set(Object.keys((get("panels") || {}).characters || {}).map((n) => n.toLowerCase()));
    const q = (state.spkQ || "").toLowerCase();
    const shown = all ? chars : chars.filter((x) => here.has(x.name.toLowerCase()) || cur === x.name.toLowerCase());
    bar.innerHTML = `<span class="qr-muted">Next:</span>
      <button class="qr-chip ${cur ? "" : "on"}" data-act="speaker" data-name="">${icon("users")}${lead}</button>
      ${small ? "" : all ? `<input class="qr-spk-q" placeholder="Search characters" value="${esc(state.spkQ || "")}"><button class="qr-chip qr-ghost" data-act="spk-mode" data-mode="scene">Scene only</button>`
        : `<button class="qr-chip qr-ghost" data-act="spk-mode" data-mode="all">All characters (${chars.length})</button>`}
      <label class="qr-check"><input type="checkbox" class="qr-single" ${single ? "checked" : ""}> one character per reply</label>
      <button class="qr-icon qr-xs" data-act="spk-mode" data-mode="hidden" title="Hide" aria-label="Hide the speaker choice">${icon("x")}</button>
      <div class="qr-spk-list ${all && !small ? "all" : ""}">${shown.map(chip).join("") || (all ? "" : '<span class="qr-muted">No other characters in the scene.</span>')}</div>`;
    if (q && all) filterSpk(q);
  }
  function filterSpk(q) {
    $(".qr-speaker-bar").querySelectorAll(".qr-spk-list .qr-chip").forEach((b) => { b.hidden = !b.dataset.name.toLowerCase().includes(q); });
  }
  function itemHTML(it) {
    const chap = it.chapter ? `<div class="qr-chapter">${icon("bookmark")}${esc(it.chapter)}</div>` : "";
    if (it.kind === "summary") {
      const k = `sum-${it.id}`;
      return `<div class="qr-msg qr-summary-row"><details class="qr-summary" data-key="${k}" ${state.open.has(k) ? "open" : ""}>
        <summary>${icon("archive")}Context condensed · messages ${it.range[0]}–${it.range[1]}${it.level === "era" ? " (era)" : ""}</summary>
        <div class="qr-md">${md(it.text)}</div></details></div>`;
    }
    if (it.kind === "user") {
      if (it.time_skip) return `${chap}<div class="qr-msg qr-skip-row" data-id="${it.id}"><span class="qr-pill">${icon("skip")}Time skip: ${esc(skipLabel(it.time_skip))}</span>${actionsBar(it)}</div>`;
      const atts = (it.attachments || []).map((a) => `<span class="qr-att">${icon("clip")}${esc(a.split(":").slice(1).join(":") || a)}</span>`).join("")
        + (it.notes || []).map((n) => `<span class="qr-att warn">${esc(n)}</span>`).join("");
      return `${chap}<div class="qr-msg qr-user ${it.ooc ? "ooc" : ""} ${it.pinned ? "pinned" : ""}" data-id="${it.id}">
        ${atts ? `<div class="qr-atts">${atts}</div>` : ""}
        <div class="qr-bubble">${it.ooc ? '<span class="qr-ooc">OOC</span>' : ""}${esc(it.content).replace(/\n/g, "<br>")}</div>
        ${actionsBar(it)}</div>`;
    }
    const k = `m${it.root}`;
    const think = it.reasoning ? thinkBlock(`${k}-th`, it.reasoning, `Thought${it.stats && it.stats.think_s ? ` for ${it.stats.think_s.toFixed(0)} s` : ""}`) : "";
    const dice = (it.dice || []).map((d) => `<span class="qr-dice ${d.success ? "ok" : "bad"}">${icon("dice")}${esc(d.event)} · ${Math.round(d.odds * 100)}% · ${d.success ? "success" : "failed"}</span>`).join("");
    const flags = (it.flags || []).map((f) => `<span class="qr-flag" title="${esc(f.text)}">${icon("warn")}${esc(f.text.length > 70 ? f.text.slice(0, 70) + "…" : f.text)}</span>`).join("");
    const cont = (it.continuity || []).map((x) => `<div class="qr-fact">${icon("warn")}<div><b>${esc(x.kind)}${x.who ? ` · ${esc(x.who)}` : ""}</b><br>${esc(x.text)}${x.fix ? ` <span class="qr-muted">→ ${esc(x.fix)}</span>` : ""}</div></div>`).join("");
    const facts = cont + (it.fact_warnings || []).map((f) => `<div class="qr-fact">${icon("flag")}<div><b>${esc(f.claim)}</b><br>${esc(f.correction)} ${f.source && /^https?:/.test(f.source) ? `<a href="${esc(f.source)}" target="_blank" rel="noopener noreferrer">source</a>` : esc(f.source || "")}</div></div>`).join("");
    const choices = it.choices && it.choices.problems && it.root === state.lastBot ? `<div class="qr-choices">${it.choices.problems.map((p, pi) => `
      <div class="qr-problem"><div class="qr-q">${esc(p.question)}</div>
      ${p.options.map((o, oi) => `<div class="qr-opt"><button class="qr-opt-main" data-act="choose" data-text="${esc(o)}">${esc(o)}</button>
        <button class="qr-icon qr-xs" data-act="choose-edit" data-text="${esc(o)}" title="Edit first">${icon("edit")}</button></div>`).join("")}</div>`).join("")}</div>` : "";
    return `${chap}<div class="qr-msg qr-bot ${it.ooc ? "ooc" : ""} ${it.pinned ? "pinned" : ""}" data-id="${it.id}">
      ${think}${toolChips(it.tools, k)}
      ${dice ? `<div class="qr-dices">${dice}</div>` : ""}
      <div class="qr-md">${it.ooc ? '<span class="qr-ooc">OOC</span>' : ""}${speakers(md(it.content, state.learn))}</div>
      ${it.partial ? `<div class="qr-partial">${icon("warn")}Reply cut off. <button class="qr-btn qr-sm" data-act="continue" data-id="${it.id}">Continue</button></div>` : ""}
      ${it.error ? `<div class="qr-error">${esc(it.error)}</div>` : ""}
      ${flags ? `<div class="qr-flags">${flags}<button class="qr-btn qr-sm" data-act="reroll" data-id="${it.id}">${icon("refresh")}Regenerate</button></div>` : ""}
      ${facts}${choices}${statsLine(it.stats)}${actionsBar(it)}</div>`;
  }
  function renderHistory() {
    const h = model.get("history") || { items: [] };
    $(".qr-toc-btn").hidden = !(h.chapters || []).length;
    const items = h.items || [];
    const lastBot = [...items].reverse().find((x) => x.kind === "bot");
    state.lastBot = lastBot ? lastBot.root : null;
    $(".qr-more").hidden = !(h.total > items.length);
    const empty = $(".qr-empty");
    const c = get("chat");
    empty.hidden = items.length > 0 || !!(get("live").active);
    empty.innerHTML = c.kind === "studio"
      ? `<h2>Studio</h2><p>Describe the story you want: the world, who you are, the characters, the tone. The model asks questions and fills in the cards in the right panel.</p>`
      : c.kind === "rp" || c.kind === "group" ? `<h2>${esc(c.title || "Story")}</h2><p>Write your first action.</p>`
      : `<h2>What do you want to talk about?</h2><p>Attach or drop images, videos, PDFs and documents here.</p>`;
    const keep = new Set();
    let prev = null;
    for (const it of items) {
      const key = `${it.kind}-${it.kind === "bot" ? it.root : it.id}`;
      keep.add(key);
      const sig = JSON.stringify(it) + (state.learn ? "L" : "") + (state.avSig || "") + (it.root === state.lastBot ? "Z" : "");
      let node = els.get(key);
      if (!node || node._sig !== sig) {
        const tmp = document.createElement("div");
        tmp.innerHTML = itemHTML(it);
        const fresh = document.createElement("div");
        fresh.className = "qr-item";
        fresh.dataset.key = key;
        while (tmp.firstChild) fresh.appendChild(tmp.firstChild);
        fresh._sig = sig;
        if (node) node.replaceWith(fresh); else list.appendChild(fresh);
        node = fresh;
        els.set(key, node);
      }
      const want = prev ? prev.nextSibling : list.firstChild;
      if (want !== node) list.insertBefore(node, want);
      prev = node;
    }
    for (const [k, node] of els) if (!keep.has(k)) { node.remove(); els.delete(k); }
    fol.stick();
  }

  // live message
  let liveParts = null, thinkFollow = true;
  function renderLive() {
    const lv = get("live");
    if (!lv.active) { liveBox.innerHTML = ""; liveParts = null; thinkFollow = true; renderStatusLine(); return; }
    $(".qr-empty").hidden = true;
    if (!liveParts) {
      liveBox.innerHTML = `<div class="qr-msg qr-bot qr-live-row">${thinkBlock(rpChat() ? "live-th-rp" : "live-th", "", "Thinking", true)}
        <div class="qr-live-tools"></div><div class="qr-md"></div><div class="qr-phase qr-muted"></div>
        <div class="qr-typing"><span></span><span></span><span></span></div></div>`;
      liveParts = { think: liveBox.querySelector(".qr-think"), sum: liveBox.querySelector(".qr-think summary span"),
        count: liveBox.querySelector(".qr-think summary .qr-muted"),
        box: liveBox.querySelector(".qr-think-box"), body: liveBox.querySelector(".qr-think-body"),
        follow: liveBox.querySelector(".qr-think-follow"), tools: liveBox.querySelector(".qr-live-tools"),
        md: liveBox.querySelector(".qr-live-row > .qr-md"), phase: liveBox.querySelector(".qr-phase"), typing: liveBox.querySelector(".qr-typing") };
      liveParts.think.hidden = true;
      const tb = liveParts.box;
      const leave = () => { thinkFollow = false; liveParts.follow.hidden = false; };
      tb.addEventListener("wheel", (e) => { if (e.deltaY < 0) leave(); }, { passive: true });
      tb.addEventListener("touchmove", leave, { passive: true });
      tb.addEventListener("scroll", () => { if (tb.scrollHeight - tb.scrollTop - tb.clientHeight < 6) { thinkFollow = true; liveParts.follow.hidden = true; } }, { passive: true });
    }
    const p = liveParts;
    if (lv.reasoning) {
      p.think.hidden = false;
      p.sum.textContent = lv.thinking ? "Thinking" : "Done thinking";
      p.count.textContent = `${fmtN(words(lv.reasoning))} words`;
      p.body.textContent = lv.reasoning;
      if (thinkFollow) p.box.scrollTop = p.box.scrollHeight;
    }
    p.tools.innerHTML = toolChips(lv.tools, "live");
    p.md.innerHTML = lv.content ? md(lv.content, state.learn) : "";
    p.phase.textContent = lv.phase || "";
    p.typing.hidden = !!lv.content;
    fol.stick();
  }
  function renderStatusLine() {
    const s = model.get("status") || "", q = model.get("queue") || 0;
    const line = $(".qr-statusline");
    const txt = [s, q ? `${q} ${q === 1 ? "message" : "messages"} queued` : ""].filter(Boolean).join(" · ");
    line.hidden = !txt;
    line.textContent = txt;
  }
  function renderBusy() {
    const busy = model.get("busy");
    const b = $(".qr-send");
    b.innerHTML = busy ? icon("stop") : icon("send");
    b.classList.toggle("stop", !!busy);
    b.setAttribute("aria-label", busy ? "Stop" : "Send");
  }

  // ---------- studio pane ----------
  function renderStudio() {
    const c = get("chat"), st = get("story"), pane = $(".qr-studio");
    const on = c.kind === "studio";
    pane.hidden = !on;
    el.classList.toggle("studio-on", on);
    if (!on) return;
    const cards = st.studio ? st.cards || [] : [];
    // only a card that belongs to this studio session may be shown
    if (!cards.some((x) => x.id === state.studioCard)) state.studioCard = cards.length ? cards[0].id : null;
    // A form with unsaved edits, or one the user is typing in, is left alone: only the tabs are refreshed.
    const oldForm = pane.querySelector(".qr-studio-form");
    const keep = oldForm && oldForm.querySelector(".qr-card-form") &&
      ((state.formDirty && state.formDirty === state.studioCard) || oldForm.contains(rootActive())) ? oldForm : null;
    const tabsHTML = cards.map((x) => `<button class="qr-tabbtn ${x.id === state.studioCard ? "on" : ""}" data-act="studio-card" data-id="${x.id}">${esc((get("boot").types || {})[x.type] || x.type)}: ${esc(x.name)}</button>`).join("") || '<span class="qr-muted">No cards yet. Start chatting on the left.</span>';
    if (keep && pane.querySelector(".qr-studio-tabs")) { pane.querySelector(".qr-studio-tabs").innerHTML = tabsHTML; return; }
    const quick = [["Fill the gaps", "Fill the card fields that are still empty with consistent suggestions."],
      ["Check consistency", "Check the cards for consistency with each other (and for anachronisms if the world is based on the real one), then fix them."],
      ["Test a scene", "Test a scene: write one opening paragraph with the current Style and GM cards."],
      ["Test the voice", "Test the main character's voice: reply to three situations (relaxed, angry, sad) as that character."],
      ["Interview", "I want to interview the main character. Answer as that character from now on until I say I'm done."]];
    const card = state.cards.get(state.studioCard) || {};
    pane.innerHTML = `<div class="qr-studio-head"><b>Cards in Studio</b>
        <button class="qr-btn qr-sm qr-primary" data-act="studio-finish" ${cards.length ? "" : "disabled"}>${icon("book")}Start RP</button></div>
      <div class="qr-studio-quick">${quick.map(([l, t]) => `<button class="qr-btn qr-sm" data-act="quick" data-text="${esc(t)}">${esc(l)}</button>`).join("")}</div>
      <div class="qr-studio-quick">
        <button class="qr-btn qr-sm" data-act="studio-image">${icon("upload")}From an image</button>
        <button class="qr-btn qr-sm" data-act="studio-tidy">${icon("edit")}Tidy text</button></div>
      <div class="qr-studio-tabs">${tabsHTML}</div>
      ${state.studioCard && card.id === state.studioCard ? `<div class="qr-row qr-var"><select class="qr-var-field">${(card.fields || [])
        .filter((f) => f.visibility !== "ui" || ["greetings", "opening"].includes(f.key)).map((f) => `<option value="${esc(f.key)}">${esc(f.label)}</option>`).join("")}</select>
        <button class="qr-btn qr-sm" data-act="variations">${icon("sparkles")}Variations</button></div>` : ""}
      <div class="qr-studio-form">${state.studioCard && card.id === state.studioCard ? cardForm(card, true) : ""}</div>`;
    if (state.studioCard && card.id !== state.studioCard) send("card_open", { card_id: state.studioCard });
  }

  // ---------- card form ----------
  // Suggestions the Style form can add to its rules. They only go into the form: the user edits them and saves.
  const STYLE_SUGGEST = [
    "Do not open a reply by repeating the player's action or words; go straight to the reaction and its consequences.",
    'Do not end a reply with a narrator question such as "What do you do?"; stop at a moment where the player can act.',
    "Vary how replies open; do not start several replies in a row with the same pattern.",
    "Dialogue translations use natural everyday English, not word-for-word translation.",
  ];
  function fieldInput(f, v) {
    const key = esc(f.key);  // keys come from cards the model or an import wrote: never trust them in markup
    const name = `f-${String(f.key).replace(/[^\w-]/g, "_")}`;
    const badge = `${f.core ? '<span class="qr-badge" title="Goes into the frozen prompt">core</span>' : ""}${f.visibility === "secret" ? `<span class="qr-badge">${icon("lock")}secret</span>` : ""}${f.visibility === "ui" ? '<span class="qr-badge">UI only</span>' : ""}`;
    const label = `<label class="qr-flabel" for="${name}">${esc(f.label)} ${badge}</label>${f.help ? `<div class="qr-help">${esc(f.help)}</div>` : ""}`;
    if (v !== null && typeof v === "object" && !["list", "tags", "table"].includes(f.type))
      return `${label}<textarea id="${name}" data-field="${key}" data-type="json" rows="4">${esc(JSON.stringify(v, null, 1))}</textarea>`;
    if (f.type === "longtext") return `${label}<textarea id="${name}" data-field="${key}" data-type="longtext" rows="3">${esc(v ?? "")}</textarea>`;
    if (f.type === "list") return `${label}<textarea id="${name}" data-field="${key}" data-type="list" rows="3" placeholder="One per line">${esc((Array.isArray(v) ? v : v ? [v] : []).join("\n"))}</textarea>`;
    if (f.type === "tags") return `${label}<input id="${name}" data-field="${key}" data-type="tags" value="${esc((Array.isArray(v) ? v : v ? [v] : []).join(", "))}" placeholder="Separate with commas">`;
    if (f.type === "select") {
      const opts = [...(f.options || [])];
      if (v && !opts.includes(v)) opts.push(v);
      return `${label}<select id="${name}" data-field="${key}" data-type="text"><option value=""></option>${opts.map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
    }
    if (f.type === "number" && v !== undefined && v !== null && v !== "" && isNaN(Number(v))) return `${label}<input id="${name}" data-field="${key}" data-type="text" value="${esc(v)}">`;
    if (f.type === "number") return `${label}<input id="${name}" type="number" data-field="${key}" data-type="number" value="${esc(v ?? "")}">`;
    if (f.type === "table") {
      const cols = f.columns || ["nilai"];
      const rows = Array.isArray(v) ? v : [];
      return `${label}<div class="qr-table" data-field="${key}" data-type="table" data-cols="${cols.length}">
        <div class="qr-trow qr-thead">${cols.map((c) => `<span>${esc(c)}</span>`).join("")}<span></span></div>
        ${rows.map((r) => `<div class="qr-trow">${cols.map((c, ci) => `<input value="${esc(Array.isArray(r) ? r[ci] ?? "" : (r || {})[c] ?? "")}">`).join("")}<button class="qr-icon qr-xs" data-act="row-del">${icon("x")}</button></div>`).join("")}
        <button class="qr-btn qr-sm" data-act="row-add">${icon("plus")}Row</button></div>`;
    }
    return `${label}<input id="${name}" data-field="${key}" data-type="text" value="${esc(v ?? "")}">`;
  }
  function cardForm(c, compact) {
    const sections = {};
    for (const f of c.fields || []) (sections[f.section || "Other"] ||= []).push(f);
    const lore = c.type === "world" || c.type === "character";
    return `<div class="qr-card-form" data-card="${c.id}" data-version="${c.version}">
      <div class="qr-card-top">${c.avatar ? `<img class="qr-avatar" src="data:image/png;base64,${c.avatar}" alt="">` : `<div class="qr-avatar qr-noav">${icon("card")}</div>`}
        <div><div class="qr-muted">${esc((get("boot").types || {})[c.type] || c.type)} · version ${c.version}</div><b>${esc(c.name)}</b></div></div>
      ${Object.entries(sections).map(([s, fs]) => `<fieldset><legend>${esc(s)}</legend>${fs.map((f) => `<div class="qr-field">${fieldInput(f, c.data[f.key])}${c.type === "style" && f.key === "rules" ? `<button class="qr-btn qr-sm" data-act="style-suggest" title="Adds suggestions to this field; change or delete them before Save">${icon("plus")}Add suggested rules</button>` : ""}</div>`).join("")}</fieldset>`).join("")}
      <div class="qr-row qr-wrap">
        <button class="qr-btn qr-primary" data-act="card-save">${icon("check")}Save</button>
        ${compact ? "" : `<button class="qr-btn" data-act="card-avatar">${icon("upload")}Avatar</button>
        <button class="qr-btn" data-act="card-export" data-fmt="qcard">${icon("download")}Export</button>
        ${c.type === "character" ? `<button class="qr-btn" data-act="card-export" data-fmt="st">${icon("download")}Export SillyTavern</button>` : ""}
        <select class="qr-version-sel"><option value="">Restore version…</option>${(c.versions || []).map((v) => `<option value="${v.version}">version ${v.version}</option>`).join("")}</select>
        <button class="qr-btn qr-danger" data-act="card-delete">${icon("trash")}Delete</button>`}
      </div>
      ${lore && !compact ? `<fieldset><legend>Lore</legend>${(c.lore || []).map((e) => `<details class="qr-lore"><summary>${e.core ? '<span class="qr-badge">core</span>' : ""}<b>${esc(e.title)}</b> <span class="qr-muted">${esc(lab(e.kind))} · ${esc(e.keys)}</span></summary>
          <div class="qr-lore-edit" data-entry="${e.id}"><input class="le-title" value="${esc(e.title)}"><input class="le-keys" value="${esc(e.keys)}" placeholder="keywords, comma-separated">
          <input class="le-known" value="${esc(e.known_to || "")}" placeholder="secret? known to (comma-separated); empty = everyone">
          <input class="le-kind" value="${esc(e.kind)}"><label class="qr-check"><input type="checkbox" class="le-core" ${e.core ? "checked" : ""}> core (always in the prompt)</label>
          <textarea class="le-text" rows="3">${esc(e.text)}</textarea><div class="qr-row"><button class="qr-btn qr-sm" data-act="lore-save">Save</button><button class="qr-btn qr-sm qr-danger" data-act="lore-del">Delete</button></div></div></details>`).join("")}
        <div class="qr-lore-edit" data-entry=""><input class="le-title" placeholder="New lore title"><input class="le-keys" placeholder="keywords, comma-separated">
          <input class="le-known" placeholder="secret? known to (comma-separated); empty = everyone"><input class="le-kind" placeholder="kind: place, faction, object…">
          <label class="qr-check"><input type="checkbox" class="le-core"> core</label><textarea class="le-text" rows="2" placeholder="Text"></textarea>
          <button class="qr-btn qr-sm" data-act="lore-save">${icon("plus")}Add lore</button></div></fieldset>` : ""}
      ${c.type === "world" && !compact ? `<fieldset><legend>Timeline</legend>${(c.timeline || []).map((e) => `<div class="qr-tl" data-entry="${e.id}"><input class="tl-at" value="${esc(e.at)}"><input class="tl-title" value="${esc(e.title)}">
          <input class="tl-text" value="${esc(e.text)}"><button class="qr-icon qr-xs" data-act="tl-save">${icon("check")}</button><button class="qr-icon qr-xs" data-act="tl-del">${icon("trash")}</button></div>`).join("")}
        <div class="qr-tl" data-entry=""><input class="tl-at" placeholder="YYYY-MM-DD HH:MM"><input class="tl-title" placeholder="Event"><input class="tl-text" placeholder="Details">
          <button class="qr-icon qr-xs" data-act="tl-save">${icon("plus")}</button></div></fieldset>
        <fieldset><legend>Fact book (${(c.facts || []).length})</legend>${(c.facts || []).slice(0, 60).map((f) => `<div class="qr-factrow">${esc(f.claim)} ${f.source_url ? `<a href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">source</a>` : ""} <span class="qr-muted">${esc(lab(f.status))}</span></div>`).join("") || '<div class="qr-muted">Empty. The model fills it in while researching.</div>'}</fieldset>` : ""}
    </div>`;
  }
  function collectCard(form) {
    const data = {};
    form.querySelectorAll("[data-field]").forEach((n) => {
      const k = n.dataset.field, t = n.dataset.type;
      if (t === "table") {
        data[k] = [...n.querySelectorAll(".qr-trow:not(.qr-thead)")].map((r) => [...r.querySelectorAll("input")].map((i) => i.value.trim())).filter((r) => r.some((x) => x));
      } else if (t === "json") { try { data[k] = JSON.parse(n.value); } catch (e) { data[k] = n.value; } }
      else if (t === "list") data[k] = n.value.split("\n").map((x) => x.trim()).filter(Boolean);
      else if (t === "tags") data[k] = n.value.split(",").map((x) => x.trim()).filter(Boolean);
      else if (t === "number") data[k] = n.value === "" ? "" : Number(n.value);
      else data[k] = n.value;
    });
    for (const k of Object.keys(data)) if (data[k] === "" || (Array.isArray(data[k]) && !data[k].length)) delete data[k];
    return data;
  }

  // ---------- drawer ----------
  // Proposals, threads and what a character knows depend on the active branch: ask again whenever it may have moved.
  function refreshStory() {
    if (drawer.hidden || state.tab !== "story" || !get("chat").id) return;
    send("proposals");
    send("threads");
    if (state.know && state.know.holder) send("knowledge", { holder: state.know.holder });
  }
  function openDrawer(tab) {
    state.tab = tab || state.tab;
    drawer.hidden = false;
    if (state.tab === "story") refreshStory();
    if (state.tab === "cards" || state.tab === "story") send("library");
    if (state.tab === "memory") send("memory", { q: "" });
    if (state.tab === "learn") send("vocab");
    renderDrawer();
  }
  function renderDrawer() {
    if (drawer.hidden) return;
    $(".qr-tabs").innerHTML = Object.keys(TAB_NAMES).map((t) => `<button class="qr-tabbtn ${t === state.tab ? "on" : ""}" data-act="tab" data-tab="${t}">${icon(TAB_ICONS[t])}${TAB_NAMES[t]}</button>`).join("");
    const fn = { chat: tabChat, story: tabStory, cards: tabCards, memory: tabMemory, model: tabModel, learn: tabLearn }[state.tab];
    if (state.tab === "cards" && state.cardView && state.formDirty === state.cardView && dbody.querySelector(".qr-card-form")) return;
    redraw(dbody, fn, state.tab === "story");
  }
  function tabChat() {
    const c = get("chat"), s = c.settings || {}, boot = get("boot"), srv = get("server");
    if (!c.id) return `<p class="qr-muted">Open or create a chat first.</p>`;
    const preset = (boot.presets || []).find((x) => x.name === srv.preset) || (boot.presets || [])[0] || { thinking: [] };
    const locked = (model.get("history") || {}).total > 1;
    const smp = s.sampling || {};
    const slider = (k, label, min, max, step, def) => `<label class="qr-slider">${label}<input type="range" data-smp="${k}" min="${min}" max="${max}" step="${step}" value="${smp[k] ?? def}"><output>${smp[k] ?? def}</output></label>`;
    return `<section><h4>This chat</h4>
      <label>Thinking level ${locked ? '<span class="qr-badge">locked once the chat starts</span>' : ""}
        <select data-set="thinking" ${locked ? "disabled" : ""}><option value="">default (${esc(preset.thinking[preset.thinking.length - 1] || "-")})</option>${preset.thinking.map((t) => `<option ${s.thinking === t ? "selected" : ""}>${t}</option>`).join("")}</select></label>
      <label>Reply length<select data-set="length"><option value="">follow the Style card</option>${["pendek", "sedang", "panjang"].map((t) => `<option value="${t}" ${s.length === t ? "selected" : ""}>${lab(t)}</option>`).join("")}</select></label>
      <label>Author's note (temporary, below the prompt)<textarea data-set="note" rows="2" placeholder="For example: this scene is tense, short sentences">${esc(s.note || "")}</textarea></label>
      <label>Fact checker<select data-set="fact_mode">${[["mati", "Off"], ["latar", "In the background"], ["ketat", "Strict (before the reply ends)"]].map(([v, l]) => `<option value="${v}" ${(s.fact_mode || "latar") === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
      ${c.kind === "group" ? `<label>Group mode<select data-set="group_mode"><option value="narrator" ${s.group_mode !== "single" ? "selected" : ""}>GM narrator (several characters per reply)</option><option value="single" ${s.group_mode === "single" ? "selected" : ""}>One character per reply</option></select></label>` : ""}
      <label class="qr-check"><input type="checkbox" data-set="learn" ${s.learn ? "checked" : ""}> Language learning mode (translations hidden, click dialogue for an explanation)</label>
    </section>
    <section><h4>Sampler <button class="qr-btn qr-sm" data-act="smp-reset">Reset to the model card</button></h4>
      ${slider("temperature", "Temperature", 0, 2, 0.05, 1)}${slider("top_p", "Top-p", 0, 1, 0.01, 0.95)}${slider("top_k", "Top-k", 0, 200, 1, 20)}
      ${slider("min_p", "Min-p", 0, 0.5, 0.01, 0)}${slider("presence_penalty", "Presence penalty", -2, 2, 0.05, 0)}${slider("repetition_penalty", "Repetition penalty", 1, 1.5, 0.01, 1)}
      <div class="qr-row"><label>Seed<input data-smp="seed" type="number" value="${smp.seed ?? ""}" placeholder="random"></label>
      <label>Max tokens<input data-set="max_tokens" type="number" value="${s.max_tokens ?? ""}" placeholder="auto"></label></div></section>
    <section><h4>Tools</h4><div class="qr-grid2">
      <button class="qr-btn" data-act="apply-now">${icon("refresh")}Apply now</button>
      <button class="qr-btn" data-act="compact">${icon("archive")}Compact</button>
      <button class="qr-btn" data-act="continue-new">${icon("forward")}Continue in a new chat</button>
      <button class="qr-btn" data-act="branches">${icon("branch")}Branch tree</button>
      <button class="qr-btn" data-act="prompt-view">${icon("eye")}View prompt</button>
      <button class="qr-btn" data-act="recall-test">${icon("brain")}Recall test</button>
      <button class="qr-btn" data-act="side-logs">${icon("archive")}Side task log</button>
      <button class="qr-btn" data-act="export" data-fmt="md">${icon("download")}Export MD</button>
      <button class="qr-btn" data-act="export" data-fmt="html">${icon("download")}Export HTML</button>
      <button class="qr-btn" data-act="export" data-fmt="epub">${icon("download")}Export EPUB</button></div></section>
    <details class="qr-adv"><summary>Advanced: manual system prompt</summary>
      <textarea data-system rows="5" placeholder="Usually empty; the prompt is built from the cards.">${esc(c.system || "")}</textarea>
      <button class="qr-btn qr-sm" data-act="save-system">Save</button></details>`;
  }
  function propsHTML() {
    const ps = state.props;
    if (!ps) { send("proposals"); return '<div class="qr-muted">Loading…</div>'; }
    return ps.map((p) => `<div class="qr-memrow" data-pid="${p.id}"><span class="qr-badge">${esc(p.card_name)} · ${esc(p.field)}</span>
      <span>${esc(typeof p.value === "string" ? p.value : JSON.stringify(p.value))}<br><span class="qr-muted">${esc(p.reason)}</span></span>
      ${p.status === "menunggu" ? `<button class="qr-btn qr-sm qr-primary" data-act="prop-yes">Accept</button><button class="qr-btn qr-sm" data-act="prop-no">Reject</button>`
        : `<span class="qr-muted">${esc(lab(p.status))}</span>`}</div>`).join("") || '<div class="qr-muted">No proposals yet.</div>';
  }
  function threadsHTML() {
    const t = state.threads;
    if (!t) { send("threads"); return '<div class="qr-muted">Loading…</div>'; }
    const row = (r) => `<div class="qr-memrow" data-tid="${r.id}"><span class="qr-badge">${esc(lab(r.kind))}</span>${r.overdue ? '<span class="qr-badge warn">overdue</span>' : r.due_soon ? '<span class="qr-badge">due soon</span>' : ""}
      <span><b>${esc(r.title)}</b>${r.who ? ` <span class="qr-muted">${esc(r.who)}</span>` : ""}${r.due ? ` <span class="qr-muted">· due ${esc(r.due)}</span>` : ""}${r.text ? `<br><span class="qr-muted">${esc(r.text)}</span>` : ""}</span>
      ${r.status === "terbuka" ? `<button class="qr-btn qr-sm" data-act="thread-close" data-status="selesai">Done</button><button class="qr-btn qr-sm" data-act="thread-close" data-status="batal">Drop</button>`
        : `<span class="qr-muted">${esc(lab(r.status))}</span>`}</div>`;
    const open = t.rows.filter((r) => r.status === "terbuka"), closed = t.rows.filter((r) => r.status !== "terbuka");
    return `${open.map(row).join("") || '<div class="qr-muted">No open threads.</div>'}
      ${closed.length ? `<details><summary class="qr-muted">Closed (${closed.length})</summary>${closed.map(row).join("")}</details>` : ""}
      <div class="qr-row"><select class="qr-thread-kind">${t.kinds.map((k) => `<option value="${esc(k)}">${esc(lab(k))}</option>`).join("")}</select>
        <input class="qr-thread-title" placeholder="New thread"><input class="qr-thread-due" placeholder="due YYYY-MM-DD HH:MM (optional)">
        <button class="qr-btn qr-sm" data-act="thread-add">${icon("plus")}Add</button></div>`;
  }
  function knowHTML() {
    const k = state.know;
    if (!k) { send("knowledge", { holder: "" }); return '<div class="qr-muted">Loading…</div>'; }
    const label = (h) => h === "player" ? `Your character${k.persona ? ` (${k.persona})` : ""}` : h;
    const kinds = ["fakta", "rahasia", "pendapat", "perasaan", "janji", "salah paham", "kenalan"];
    return `<select class="qr-know-holder">${k.holders.map((h) => `<option value="${esc(h)}" ${h === k.holder ? "selected" : ""}>${esc(label(h))}</option>`).join("")}</select>
      ${k.rows.map((r) => `<div class="qr-memrow" data-kid="${r.id}"><span class="qr-badge">${esc(lab(r.kind))}</span>${r.truth !== "benar" ? `<span class="qr-badge warn">${esc(lab(r.truth))}</span>` : ""}
        <span><input class="qr-know-text" value="${esc(r.text)}"><span class="qr-muted">${esc(lab(r.source))}${r.source_who ? ` from ${esc(r.source_who)}` : ""}${r.world_time ? ` · ${esc(r.world_time)}` : ""}</span></span>
        <select class="qr-know-truth">${["benar", "keliru", "belum pasti"].map((t) => `<option value="${t}" ${t === r.truth ? "selected" : ""}>${lab(t)}</option>`).join("")}</select>
        <button class="qr-icon qr-xs" data-act="know-save" title="Save">${icon("check")}</button>
        <button class="qr-icon qr-xs" data-act="know-del" title="Forget on this branch (can be restored)">${icon("trash")}</button></div>`).join("") || '<div class="qr-muted">Nothing yet.</div>'}
      ${(k.hidden || []).length ? `<details class="qr-know-hidden" data-key="know-hidden" ${state.open.has("know-hidden") ? "open" : ""}><summary class="qr-muted">Forgotten on this branch (${k.hidden.length})</summary>
        ${k.hidden.map((r) => `<div class="qr-memrow" data-kid="${r.id}"><span class="qr-badge">${esc(lab(r.kind))}</span><span class="qr-muted"><s>${esc(r.text)}</s></span>
          <button class="qr-btn qr-sm" data-act="know-restore">${icon("refresh")}Restore</button></div>`).join("")}</details>` : ""}
      <div class="qr-row"><input class="qr-know-new" placeholder="Add something they know or believe"><select class="qr-know-kind">${kinds.map((x) => `<option value="${x}">${lab(x)}</option>`).join("")}</select>
        <button class="qr-btn qr-sm" data-act="know-add">${icon("plus")}Add</button></div>`;
  }
  // ---------- pamor (fame) ----------
  const FAME_LEVELS = ["bintang", "terkenal", "dikenal di lingkungannya", "biasa"], TOP_FAME = ["bintang", "terkenal"];
  function topHTML(st) {
    const people = (st.cards || []).filter((x) => x.role === "character" || x.role === "persona");
    if (!people.some((x) => x.role === "character")) return "";
    const rank = (f) => { const i = FAME_LEVELS.indexOf(f); return i < 0 ? FAME_LEVELS.length : i; };
    const top = people.filter((x) => TOP_FAME.includes(x.fame)).sort((a, b) => rank(a.fame) - rank(b.fame) || a.name.localeCompare(b.name));
    const n = (f) => people.filter((x) => x.role === "character" && x.fame === f).length;
    return `<section><h4>Top characters (fame)</h4><div class="qr-help">Stars and famous characters are known to everyone even before they meet, are more active in the world, and their cards are always in the prompt when there are more than 12 characters. Changes reach the prompt after Apply now or compaction.</div>
      ${top.map((x) => `<div class="qr-linkrow"><span class="qr-badge">${esc(lab(x.fame))}</span><b>${esc(x.name)}</b>${x.role === "persona" ? '<span class="qr-muted">(your character)</span>' : ""}<span class="qr-muted">${esc(x.fame_for || "")}</span></div>`).join("") || '<div class="qr-muted">No one is a star or famous yet.</div>'}
      <div class="qr-muted">star ${n("bintang")}/5 · famous ${n("terkenal")}/10</div>
      <div class="qr-row"><button class="qr-btn qr-sm" data-act="fame-suggest">${icon("sparkles")}Suggest fame</button><button class="qr-btn qr-sm" data-act="fame-table">Set all</button></div></section>`;
  }
  // The table for every character (and the player's own card): suggestions arrive here too; nothing is saved until Save all.
  function fameModal(rows, suggested) {
    openModal(suggested ? "Fame suggestions" : "Set fame", `<div class="qr-help">${suggested ? "The model's suggestions from the card contents. Change the ones that do not fit, then Save all. " : ""}Suggested limits: star 5, famous 10.</div>
      <div class="qr-fame-count qr-muted"></div>
      ${rows.map((r) => `<div class="qr-fame-row" data-card="${Number(r.card_id)}" ${r.persona ? "data-persona" : ""}><b>${esc(r.name)}</b>${r.persona ? '<span class="qr-muted">(your character)</span>' : ""}${suggested && (r.current || "") !== (r.fame || "") ? `<span class="qr-muted">now: ${esc(lab(r.current) || "-")}</span>` : ""}
        <select class="fm-fame"><option value=""></option>${FAME_LEVELS.map((f) => `<option value="${f}" ${f === r.fame ? "selected" : ""}>${lab(f)}</option>`).join("")}</select>
        <input class="fm-for" value="${esc(r.fame_for || "")}" placeholder="Known for">${r.reason ? `<span class="qr-muted qr-fame-why">${esc(r.reason)}</span>` : ""}</div>`).join("") || "No characters yet."}
      <button class="qr-btn qr-primary" data-act="fame-save">${icon("check")}Save all</button>`);
    fameCount();
  }
  function fameCount() {
    const box = $(".qr-modal-body .qr-fame-count");
    if (!box) return;
    const vals = [...$(".qr-modal-body").querySelectorAll(".qr-fame-row:not([data-persona]) .fm-fame")].map((s) => s.value);
    const b = vals.filter((v) => v === "bintang").length, t = vals.filter((v) => v === "terkenal").length;
    box.innerHTML = `star ${b}/5 · famous ${t}/10${b > 5 || t > 10 ? ' <span class="qr-badge warn">over the limit</span>' : ""}`;
  }
  function tabStory() {
    const st = get("story"), c = get("chat"), lib = get("library");
    if (!st.id) return c.kind === "studio" ? `<p class="qr-muted">This is Studio. The cards being built are in the right panel.</p>`
      : `<p class="qr-muted">This chat is not a story.</p><button class="qr-btn qr-primary" data-act="story-wizard">${icon("book")}Start a new story</button>`;
    const roles = get("boot").roles || [];
    return `<section><h4>${esc(st.title)}</h4>${st.cards.map((x) => `<div class="qr-linkrow">${x.avatar ? `<img class="qr-avatar sm" src="data:image/png;base64,${x.avatar}" alt="">` : icon("card")}
        <span class="qr-muted">${esc((get("boot").types || {})[x.role] || x.role)}</span><b>${esc(x.name)}</b>
        ${x.latest > x.version ? '<span class="qr-badge" title="Takes effect after Apply now or compaction">new version</span>' : ""}
        <button class="qr-icon qr-xs" data-act="open-card" data-id="${x.id}" title="Open">${icon("edit")}</button>
        <button class="qr-icon qr-xs" data-act="detach" data-id="${x.id}" data-role="${esc(x.role)}" title="Detach">${icon("x")}</button></div>`).join("")}
      <div class="qr-row"><select class="qr-attach-role">${roles.map((r) => `<option value="${r}">${esc((get("boot").types || {})[r] || r)}</option>`).join("")}</select>
        <select class="qr-attach-card"><option value="">Attach a card…</option>${(lib.cards || []).map((x) => `<option value="${x.id}">${esc(x.type)} · ${esc(x.name)}</option>`).join("")}</select>
        <button class="qr-btn qr-sm" data-act="attach-card">Attach</button></div></section>
      ${topHTML(st)}
      <section><h4>Story book</h4>${Object.entries(st.canon || {}).map(([k, v]) => `<div class="qr-canon" data-sec="${esc(k)}"><b>${esc(k)}</b><textarea rows="3">${esc(v)}</textarea>
        <button class="qr-btn qr-sm" data-act="canon-save">Save</button></div>`).join("")}
        <div class="qr-canon" data-sec=""><input class="qr-canon-new" placeholder="New section, e.g. Open plot lines"><textarea rows="2"></textarea><button class="qr-btn qr-sm" data-act="canon-save">${icon("plus")}Add</button></div></section>
      <section><h4>Story threads</h4><div class="qr-threads">${threadsHTML()}</div></section>
      <section><h4>Card change proposals</h4><div class="qr-help">The model proposes changes to character cards as the story develops (automatically after compaction). You decide.</div>
        <div class="qr-props">${propsHTML()}</div><button class="qr-btn qr-sm" data-act="props-make">${icon("sparkles")}Ask for proposals now</button></section>
      <section><h4>Character memory</h4><div class="qr-help">What each character knows or believes in this chat (active branch). Characters act only on this.</div>
        <div class="qr-know">${knowHTML()}</div></section>
      <section><h4>Never forget</h4><textarea class="qr-nf" rows="4" placeholder="One fact per line">${esc((st.never_forget || []).join("\n"))}</textarea>
        <button class="qr-btn qr-sm" data-act="nf-save">Save</button></section>
      ${(st.pending || []).length ? `<section><h4>Waiting for the next epoch</h4>${st.pending.map((p) => `<div class="qr-muted">• ${esc(p)}</div>`).join("")}
        <button class="qr-btn qr-sm" data-act="apply-now">${icon("refresh")}Apply now</button></section>` : ""}`;
  }
  function tabCards() {
    const lib = get("library"), types = get("boot").types || {};
    const card = state.cards.get(state.cardView) || {};
    if (state.cardView && card.id === state.cardView) {
      return `<button class="qr-btn qr-sm" data-act="cards-back">${icon("left")}Library</button>${cardForm(card, false)}`;
    }
    const q = state.libFilter.toLowerCase();
    const by = {};
    for (const c of lib.cards || []) if (!q || c.name.toLowerCase().includes(q)) (by[c.type] ||= []).push(c);
    return `<div class="qr-row qr-wrap"><input class="qr-lib-filter" placeholder="Search cards" value="${esc(state.libFilter)}">
        <button class="qr-btn qr-sm" data-act="card-import">${icon("upload")}Import (qcard / SillyTavern JSON/PNG)</button>
        <button class="qr-btn qr-sm" data-act="story-wizard">${icon("book")}Start a story</button></div>
      ${Object.keys(types).map((t) => `<section><h4>${esc(types[t])} <button class="qr-btn qr-sm" data-act="card-new" data-type="${t}">${icon("plus")}New</button>
        <button class="qr-btn qr-sm" data-act="schema" data-type="${t}">Schema</button></h4>
        ${(by[t] || []).map((c) => `<button class="qr-libitem" data-act="open-card" data-id="${c.id}">${icon("card")}<span>${esc(c.name)}</span><span class="qr-muted">v${c.version}</span></button>`).join("") || '<div class="qr-muted">None yet.</div>'}</section>`).join("")}`;
  }
  function tabMemory() {
    const a = state.memory || { rows: [], log: [] };
    return `<label class="qr-search">${icon("search")}<input class="qr-mem-q" placeholder="Search memory" value="${esc(a.q || "")}"></label>
      <section><h4>Memory</h4>${(a.rows || []).map((m) => `<div class="qr-memrow"><span class="qr-badge">${esc(m.scope)}${m.kind === "summary_core" ? " · summary" : ""}</span>${m.other_branch ? '<span class="qr-badge" title="Made on another branch or chat; not used in this chat">other branch</span>' : ""}${m.forgotten_here ? '<span class="qr-badge" title="Forgotten on this branch; other branches still use it">forgotten here</span>' : ""}
        <span class="${m.other_branch ? "qr-muted" : ""}">#${m.id} ${esc(m.text)}</span><button class="qr-icon qr-xs" data-act="mem-del" data-id="${m.id}" title="Delete">${icon("trash")}</button></div>`).join("") || '<div class="qr-muted">Empty.</div>'}</section>
      <section><h4>Changes made by the model</h4>${(a.log || []).map((l) => `<div class="qr-memrow ${l.undone ? "undone" : ""}"><span class="qr-badge">${esc(l.action)}</span>
        <span>#${l.memory_id} ${esc((l.after || l.before || "").slice(0, 160))}</span>${l.undone ? '<span class="qr-muted">undone</span>' : `<button class="qr-btn qr-sm" data-act="mem-undo" data-id="${l.id}">Undo</button>`}</div>`).join("") || '<div class="qr-muted">None yet.</div>'}</section>`;
  }
  function tabModel() {
    const boot = get("boot"), s = get("server");
    const sel = state.modelSel || s.preset || (boot.presets[0] || {}).name;
    const p = boot.presets.find((x) => x.name === sel) || boot.presets[0];
    const ctxs = Object.entries(boot.ctx_choices || {}).filter(([, v]) => v <= p.yarn_max);
    return `<section><h4>Server</h4><div class="qr-srv"><i class="qr-dot ${s.phase === "ready" ? "ok" : s.phase === "failed" ? "bad" : s.phase === "idle" ? "off" : "wait"}"></i>
        <b>${esc(s.preset || "None")}</b> <span class="qr-muted">${esc(s.phase || "")}${s.ctx ? ` · ${fmtN(s.ctx)} token` : ""}${s.mtp ? " · MTP" : ""}${s.embed ? ` · embedder ${s.embed_ready ? "ready" : "loading"}` : ""}</span></div>
      ${(s.warnings || []).map((w) => `<div class="qr-flag">${icon("warn")}${esc(w)}</div>`).join("")}${s.error ? `<pre class="qr-error">${esc(s.error)}</pre>` : ""}
      <div class="qr-muted qr-gpu">${s.gpu ? `GPU ${s.gpu.util.toFixed(0)}% · VRAM ${s.gpu.used_gb.toFixed(1)} / ${s.gpu.total_gb.toFixed(0)} GB` : ""}</div>
      ${s.installed ? "" : `<div class="qr-flag">${icon("warn")}Not installed. Click Install in the model server cell.</div>`}</section>
      <section><h4>Switch model</h4><label>Model<select class="qr-model-sel">${boot.presets.map((x) => `<option ${x.name === sel ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></label>
      <label>Context<select class="qr-ctx-sel">${ctxs.map(([k, v]) => `<option value="${v}" ${v === (state.modelCtx || s.ctx || 524288) ? "selected" : ""}>${esc(k)}</option>`).join("")}</select></label>
      ${p.yarn_exp ? '<div class="qr-help">Above 262K this uses YaRN without an official recipe for this model (experimental).</div>' : ""}
      <label class="qr-check"><input type="checkbox" class="qr-mtp" ${state.modelMtp === false ? "" : "checked"}> MTP</label><label class="qr-check"><input type="checkbox" class="qr-emb" ${state.modelEmb === false ? "" : "checked"}> Embedder</label>
      <select class="qr-emb-model">${["0.6B", "4B"].map((m) => `<option ${m === (state.modelEmbModel || s.embed_model || "0.6B") ? "selected" : ""}>${m}</option>`).join("")}</select>
      <div class="qr-help">Switching models reprocesses the whole context on the next turn (several minutes for a long chat).</div>
      <div class="qr-row"><button class="qr-btn qr-primary" data-act="model-start">${icon("cpu")}Start</button><button class="qr-btn qr-danger" data-act="model-stop">Stop</button></div></section>`;
  }
  function tabLearn() {
    const v = state.vocab || { due: [], all: [] };
    const card = v.due[0];
    return `<section><h4>Flashcards (${v.due.length} due)</h4>${card ? `<div class="qr-flash"><div class="qr-flash-term">${esc(card.term)}</div>
        <details><summary>Show meaning</summary><div>${esc(card.translation)}</div><div class="qr-muted">${esc(card.note)}</div><div class="qr-muted">${esc(card.example)}</div></details>
        <div class="qr-row">${[["Forgot", 0], ["Hard", 1], ["Good", 2], ["Easy", 3]].map(([l, g]) => `<button class="qr-btn qr-sm" data-act="review" data-id="${card.id}" data-grade="${g}">${l}</button>`).join("")}</div></div>`
        : '<div class="qr-muted">Nothing due.</div>'}</section>
      <section><h4>Vocabulary (${v.all.length})</h4>${v.all.map((x) => `<div class="qr-memrow"><b>${esc(x.term)}</b><span>${esc(x.translation)}</span>
        <button class="qr-icon qr-xs" data-act="vocab-del" data-id="${x.id}">${icon("trash")}</button></div>`).join("") || '<div class="qr-muted">Click dialogue in the chat (learning mode), then add words.</div>'}</section>`;
  }

  // ---------- story wizard ----------
  function storyWizard() {
    send("library");
    state.wizard = true;
    renderWizard();
  }
  function renderWizard() {
    if (!state.wizard) return;
    // keep what the user already picked when the card list changes underneath
    const body = $(".qr-modal-body"), prev = body.querySelector(".qr-wizard") ? {
      title: body.querySelector(".wz-title")?.value || "", greet: body.querySelector(".wz-greet")?.value || "1",
      roles: Object.fromEntries([...body.querySelectorAll("select[data-role]")].map((x) => [x.dataset.role, x.value])),
      chars: new Set([...body.querySelectorAll(".qr-wz-chars input:checked")].map((x) => x.value)) } : null;
    const lib = get("library"), types = get("boot").types || {};
    const opt = (t) => (lib.cards || []).filter((c) => c.type === t).map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
    openModal("Start a story", `<div class="qr-wizard">
      <label>Title<input class="wz-title" placeholder="Empty = from the scenario"></label>
      ${["world", "scenario", "persona", "style", "gm"].map((t) => `<label>${esc(types[t] || t)}<select data-role="${t}"><option value="">${t === "style" || t === "gm" ? "default" : "none"}</option>${opt(t)}</select></label>`).join("")}
      <div class="qr-flabel">Characters</div><div class="qr-wz-chars">${(lib.cards || []).filter((c) => c.type === "character").map((c) => `<label class="qr-check"><input type="checkbox" value="${c.id}"> ${esc(c.name)}</label>`).join("") || '<span class="qr-muted">No character cards yet. Make one in Studio or import one.</span>'}</div>
      <label>Opening message #<input class="wz-greet" type="number" min="1" value="1"></label>
      <div class="qr-row"><button class="qr-btn qr-primary" data-act="wizard-go">${icon("book")}Start</button><button class="qr-btn" data-act="studio">${icon("sparkles")}Build in Studio first</button></div></div>`, true);
    if (prev) {
      body.querySelector(".wz-title").value = prev.title;
      body.querySelector(".wz-greet").value = prev.greet;
      for (const x of body.querySelectorAll("select[data-role]")) if (prev.roles[x.dataset.role] !== undefined) x.value = prev.roles[x.dataset.role];
      for (const x of body.querySelectorAll(".qr-wz-chars input")) x.checked = prev.chars.has(x.value);
    }
  }

  // ---------- events ----------
  function addFiles(files) {
    for (const f of files) {
      if (f.size > MAX_FILE) { toast(`${f.name} is larger than 25 MB.`, "warn"); continue; }
      if ((f.type || "").startsWith("audio/")) { toast(`${f.name}: audio is not supported.`, "warn"); continue; }
      state.pending.push(f);
    }
    renderPending();
  }
  function renderPending() {
    const box = $(".qr-pending");
    box.hidden = !state.pending.length;
    box.innerHTML = state.pending.map((f, i) => `<span class="qr-att">${icon("clip")}${esc(f.name)} <span class="qr-muted">${kb(f.size)}</span><button class="qr-icon qr-xs" data-act="unpend" data-i="${i}">${icon("x")}</button></span>`).join("");
  }
  const LONG_PH = input.placeholder;
  const ro2 = new ResizeObserver(() => { input.placeholder = el.clientWidth < 640 ? "Send a message" : LONG_PH; });
  ro2.observe(el);
  listen("keydown", (e) => { if (e.key === "Escape" && !modal.hidden) closeModal(); });
  const grow = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 240)}px`; };
  input.addEventListener("input", grow);
  input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229) return;  // 229: Enter that ends IME input
    e.preventDefault();
    if (!input.value.trim() && !state.pending.length) return;  // an empty Enter never stops a reply (Stop is the button)
    $(".qr-form").requestSubmit();
  });
  input.addEventListener("paste", (e) => { const fs = [...(e.clipboardData?.files || [])]; if (fs.length) { e.preventDefault(); addFiles(fs); } });
  $(".qr-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (model.get("busy") && !text && !state.pending.length) { send("stop"); return; }
    if (!text && !state.pending.length) return;
    if (state.sending) return;
    // clear first: a second Enter while big files are read must not send the same message twice
    const pending = state.pending;
    state.sending = true; input.value = ""; state.pending = []; renderPending(); grow();
    try {
      const files = await Promise.all(pending.map(async (f) => ({ name: f.name, mime: f.type || "", b64: await readB64(f) })));
      send("send", { text, files });
      fol.jump();
    } catch (err) {
      input.value = text; state.pending = pending; renderPending(); grow();
      toast(`Could not read the attachment: ${err}`, "error");
    } finally { state.sending = false; }
  });
  const main = $(".qr-main");
  let depth = 0;
  main.addEventListener("dragenter", (e) => { if (e.dataTransfer?.types?.includes("Files")) { depth++; $(".qr-drop").hidden = false; } });
  main.addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) $(".qr-drop").hidden = true; });
  main.addEventListener("dragover", (e) => e.preventDefault());
  main.addEventListener("drop", (e) => { e.preventDefault(); depth = 0; $(".qr-drop").hidden = true; addFiles([...(e.dataTransfer?.files || [])]); });
  $(".qr-search-in").addEventListener("input", renderChats);
  $(".qr-search-in").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.value.trim()) send("search", { q: e.target.value.trim() }); });
  listen("toggle", (e) => {
    const d = e.target;
    if (!(d instanceof HTMLDetailsElement) || !d.dataset.key) return;
    d.open ? state.open.add(d.dataset.key) : state.open.delete(d.dataset.key);
  }, true);
  $(".qr-file-db").addEventListener("change", async (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (f && confirm("Load this file? Every current chat, card and memory is replaced by its contents.")) send("load_db", { b64: await readB64(f) });
  });
  $(".qr-file-att").addEventListener("change", (e) => {
    addFiles([...(e.target.files || [])]);
    e.target.value = "";
    if (state.imageIntent && state.pending.length && get("chat").kind === "studio") {
      state.imageIntent = false;
      input.value = "Fill in the character's appearance from the attached image (card_draft_update, field appearance), then briefly explain what you filled in.";
      $(".qr-form").requestSubmit();
    }
  });
  $(".qr-file-att").addEventListener("cancel", () => { state.imageIntent = false; });
  $(".qr-speaker-bar").addEventListener("input", (e) => {
    if (e.target.classList.contains("qr-spk-q")) { state.spkQ = e.target.value; filterSpk(e.target.value.toLowerCase()); }
  });
  $(".qr-speaker-bar").addEventListener("change", (e) => {
    if (e.target.classList.contains("qr-single")) send("settings", { group_mode: e.target.checked ? "single" : null });
  });
  $(".qr-file-card").addEventListener("change", async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) send("card_import", { b64: await readB64(f), name: f.name }); });
  $(".qr-file-avatar").addEventListener("change", async (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    const form = el.querySelector(".qr-drawer .qr-card-form");
    if (f && form) send("card_save", { card_id: Number(form.dataset.card), data: collectCard(form), avatar: await readB64(f), version: Number(form.dataset.version) });
  });
  // typing in a card form marks it as having unsaved edits
  const markDirty = (e) => { const f = e.target.closest && e.target.closest(".qr-card-form"); if (f && !e.target.closest(".qr-lore-edit, .qr-tl, .qr-version-sel")) state.formDirty = Number(f.dataset.card); };
  const leaveForm = () => {
    if (state.formDirty && state.formDirty === state.cardView && !confirm("The card has unsaved changes. Leave and discard them?")) return false;
    if (state.formDirty === state.cardView) state.formDirty = null;
    return true;
  };
  listen("input", markDirty);
  listen("change", (e) => { if (e.target.classList && e.target.classList.contains("fm-fame")) fameCount(); });
  listen("change", markDirty);
  dbody.addEventListener("change", (e) => {
    const t = e.target;
    if (t.classList.contains("qr-know-holder")) send("knowledge", { holder: t.value });
    if (t.classList.contains("qr-ctx-sel")) state.modelCtx = Number(t.value);
    else if (t.classList.contains("qr-mtp")) state.modelMtp = t.checked;
    else if (t.classList.contains("qr-emb")) state.modelEmb = t.checked;
    else if (t.classList.contains("qr-emb-model")) state.modelEmbModel = t.value;
  });
  dbody.addEventListener("input", (e) => {
    const t = e.target;
    if (t.dataset.smp && t.type === "range") t.nextElementSibling.textContent = t.value;
    if (t.classList.contains("qr-lib-filter")) { state.libFilter = t.value; clearTimeout(state.lf); state.lf = setTimeout(() => { const pos = t.selectionStart; dbody.innerHTML = tabCards(); const n = dbody.querySelector(".qr-lib-filter"); n.focus(); n.setSelectionRange(pos, pos); }, 200); }
  });
  dbody.addEventListener("change", (e) => {
    const t = e.target;
    if (t.dataset.set) {
      const v = t.type === "checkbox" ? t.checked : t.type === "number" ? (t.value === "" ? null : Number(t.value)) : t.value || null;
      send("settings", { [t.dataset.set]: v });
      if (t.dataset.set === "learn") { state.learn = !!v; el.classList.toggle("learn", state.learn); els.clear(); list.innerHTML = ""; renderHistory(); }
    } else if (t.dataset.smp) {
      const s = { ...((get("chat").settings || {}).sampling || {}) };
      if (t.value === "") delete s[t.dataset.smp]; else s[t.dataset.smp] = Number(t.value);
      send("settings", { sampling: s });
    } else if (t.classList.contains("qr-model-sel")) { state.modelSel = t.value; dbody.innerHTML = tabModel(); }
    else if (t.classList.contains("qr-version-sel") && t.value) { const form = t.closest(".qr-card-form"); send("card_version", { card_id: Number(form.dataset.card), version: Number(t.value) }); }
    else if (t.classList.contains("qr-mem-q")) send("memory", { q: t.value });
  });
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  listen("click", (e) => {
    const chatRow = e.target.closest(".qr-chat");
    const btn = e.target.closest("[data-act]");
    if (!btn && chatRow) { send("select", { chat_id: Number(chatRow.dataset.chat) }); el.classList.remove("side-open"); return; }
    const q = e.target.closest(".qq");
    if (!btn && q && state.learn) { send("learn", { text: q.textContent.replace(/^["“„«]|["”“»]$/g, "") }); return; }
    if (!btn) return;
    const act = btn.dataset.act, id = btn.dataset.id ? Number(btn.dataset.id) : null;
    const row = btn.closest("[data-id]");
    const mid = id || (row ? Number(row.dataset.id) : null);
    switch (act) {
      case "new": send("new", { kind: btn.dataset.kind }); break;
      case "studio": closeModal(); state.wizard = false; send("studio_start"); break;
      case "story-wizard": storyWizard(); break;
      case "toggle-side": el.classList.toggle("side-open"); break;
      case "rename-chat": { e.stopPropagation(); const t = prompt("Chat name:", (model.get("chats") || []).find((c) => c.id === id)?.title || ""); if (t) send("rename", { chat_id: id, title: t }); break; }
      case "delete-chat": e.stopPropagation(); if (confirm("Delete this chat and all its messages? This cannot be undone.")) send("delete_chat", { chat_id: id }); break;
      case "save-db": send("save_db"); break;
      case "load-db": $(".qr-file-db").click(); break;
      case "attach": $(".qr-file-att").click(); break;
      case "unpend": state.pending.splice(Number(btn.dataset.i), 1); renderPending(); break;
      case "impersonate": send("impersonate", { hint: input.value.trim() }); break;
      case "jump": fol.jump(); break;
      case "load-more": send("load_more"); break;
      case "compact": if (confirm("Condense the old context now? This can take several minutes for a long chat.")) send("compact"); break;
      case "open-tab": openDrawer(btn.dataset.tab); break;
      case "close-drawer": drawer.hidden = true; break;
      case "tab": if (btn.dataset.tab !== state.tab && state.tab === "cards" && !leaveForm()) break; openDrawer(btn.dataset.tab); break;
      case "close-modal": closeModal(); state.wizard = false; break;
      case "gm-view": { e.preventDefault(); const p = get("panels");
        if (p.gm_view || confirm("GM mode shows every character's plans, attitudes and thoughts (spoilers). Show them?")) send("settings", { gm_view: !p.gm_view }); break; }
      case "toggle-world": state.open.has("world") ? state.open.delete("world") : state.open.add("world"); renderPanels(); break;
      case "time-skip": if (confirm(`Skip ahead ${skipLabel(btn.dataset.label)}?`)) send("time_skip", { label: btn.dataset.label }); break;
      case "copy": { const it = (model.get("history").items || []).find((x) => x.id === mid || (x.ids || []).includes(mid)); Promise.resolve(navigator.clipboard?.writeText(it ? it.content : "")).then(() => toast("Copied."), () => toast("Could not copy.", "warn")); break; }
      case "edit": {
        const it = (model.get("history").items || []).find((x) => x.id === mid || x.answer_id === mid);
        const text = it ? (it.kind === "bot" ? (it.edit_text ?? it.content) : it.content) : "";
        openModal("Edit message", `<textarea class="qr-edit-text" rows="10">${esc(text)}</textarea>
          <div class="qr-help">${it && it.kind === "user" ? "Creates a new branch and regenerates the reply from here." : "Saves a new version of this message."}</div>
          <button class="qr-btn qr-primary" data-act="edit-save" data-id="${mid}">Save</button>`);
        break;
      }
      case "edit-save": send("edit", { mid: id, text: el.querySelector(".qr-edit-text").value }); closeModal(); break;
      case "reroll": send("reroll", { mid }); break;
      case "continue": send("continue", { mid }); break;
      case "swipe": send("swipe", { mid: id, dir: Number(btn.dataset.dir) }); break;
      case "delete": if (confirm("Delete this message and every reply after it on this branch?")) send("delete_msg", { mid }); break;
      case "branch": send("branch", { mid }); break;
      case "pin": { const it = (model.get("history").items || []).find((x) => x.id === mid || x.answer_id === mid); send("pin", { mid, on: !(it && it.pinned) }); break; }
      case "chapter": { const t = prompt("Chapter title:"); if (t) send("chapter", { mid, title: t }); break; }
      case "fact-check": send("fact_check", { mid }); break;
      case "continuity": send("continuity", { mid }); break;
      case "choose": send("choose", { text: btn.dataset.text }); fol.jump(); break;
      case "choose-edit": input.value = btn.dataset.text; grow(); input.focus(); break;
      case "think-follow": { const box = btn.parentElement.querySelector(".qr-think-box"); thinkFollow = true; btn.hidden = true; box.scrollTop = box.scrollHeight; break; }
      case "think-full": { const d = btn.closest(".qr-think"); d.classList.toggle("full"); btn.textContent = d.classList.contains("full") ? "Collapse" : "Show full"; break; }
      case "quick": send("send", { text: btn.dataset.text }); break;
      case "studio-card": state.formDirty = null; state.studioCard = id; send("card_open", { card_id: id }); break;
      case "card-reload": state.formDirty = null; renderStudio(); if (state.tab === "cards") renderDrawer(); break;
      case "studio-finish": {
        const g = get("story").greetings || [];
        openModal("Start RP from Studio", `<label>Title<input class="sf-title" placeholder="Empty = from the scenario"></label>
          ${g.length ? `<label>Opening message<select class="sf-greet">${g.map((x, i) => `<option value="${i}">${i + 1}. ${esc(x.slice(0, 90))}</option>`).join("")}</select></label>` : ""}
          <button class="qr-btn qr-primary" data-act="studio-go">${icon("book")}Start</button>`);
        break;
      }
      case "studio-go": { const sel = el.querySelector(".sf-greet"); send("studio_finish", { title: el.querySelector(".sf-title").value, greeting: sel ? Number(sel.value) : 0 }); closeModal(); break; }
      case "studio-image": state.imageIntent = true; $(".qr-file-att").click(); break;
      case "studio-tidy": openModal("Tidy free text into cards", `<textarea class="qr-tidy" rows="12" placeholder="Paste a character, world or scenario description as it is"></textarea>
          <button class="qr-btn qr-primary" data-act="tidy-send">Tidy</button>`); break;
      case "tidy-send": { const t = el.querySelector(".qr-tidy").value.trim(); if (t) send("send", { text: `Tidy the following free text into the matching cards with card_draft_update (make new cards if needed, fill in as many fields as you can):\n\n${t}` }); closeModal(); break; }
      case "variations": { const f = el.querySelector(".qr-var-field"); if (f && state.studioCard) { send("variations", { card_id: state.studioCard, field: f.value }); toast("Making 3 alternatives…"); } break; }
      case "use-variation": { const v = state.variations; if (v) { send("card_field", { card_id: v.card_id, field: v.field, value: v.options[Number(btn.dataset.i)] }); closeModal(); } break; }
      case "note-view": send("note_view", { mid }); break;
      case "side-logs": send("side_logs"); break;
      case "notice-close": send("notice_clear"); break;
      case "compare": { const ids = [...el.querySelectorAll(".qr-cmp:checked")].map((i) => Number(i.value)); if (ids.length === 2) send("compare", { a: ids[0], b: ids[1] }); else toast("Pick exactly 2 branches.", "warn"); break; }
      case "card-save": { const form = btn.closest(".qr-card-form"); state.formDirty = null; send("card_save", { card_id: Number(form.dataset.card), data: collectCard(form), version: Number(form.dataset.version) }); break; }
      case "card-avatar": $(".qr-file-avatar").click(); break;
      case "card-export": { const form = btn.closest(".qr-card-form"); send("card_export", { card_id: Number(form.dataset.card), fmt: btn.dataset.fmt }); break; }
      case "card-delete": { const form = btn.closest(".qr-card-form"); if (confirm("Delete this card with its lore and timeline?")) { send("card_delete", { card_id: Number(form.dataset.card) }); state.cardView = null; } break; }
      case "card-new": send("card_new", { type: btn.dataset.type }); state.cardView = "new"; break;
      case "card-import": $(".qr-file-card").click(); break;
      case "open-card": if (!leaveForm()) break; state.formDirty = null; state.tab = "cards"; state.cardView = id; drawer.hidden = false; send("card_open", { card_id: id }); renderDrawer(); break;
      case "cards-back": if (!leaveForm()) break; state.formDirty = null; state.cardView = null; send("library"); renderDrawer(); break;
      case "schema": send("schema_get", { type: btn.dataset.type }); break;
      case "schema-save": send("schema_save", { schema: el.querySelector(".qr-schema-text").value }); break;
      case "row-add": { const tbl = btn.closest(".qr-table"); state.formDirty = Number(btn.closest(".qr-card-form").dataset.card); const n = Number(tbl.dataset.cols); const r = document.createElement("div"); r.className = "qr-trow"; r.innerHTML = Array(n).fill("<input>").join("") + `<button class="qr-icon qr-xs" data-act="row-del">${icon("x")}</button>`; tbl.insertBefore(r, btn); break; }
      case "style-suggest": { const ta = btn.closest(".qr-field").querySelector("textarea[data-field]");
        const have = new Set(ta.value.split("\n").map((x) => x.trim()).filter(Boolean)), add = STYLE_SUGGEST.filter((x) => !have.has(x));
        if (!add.length) { toast("All suggestions are already in this field."); break; }
        ta.value = (ta.value.trim() ? ta.value.trimEnd() + "\n" : "") + add.join("\n");
        ta.dispatchEvent(new Event("input", { bubbles: true }));
        toast(`${add.length} ${add.length === 1 ? "suggestion" : "suggestions"} added to the field. Change or delete them as you like, then Save.`); break; }
      case "row-del": state.formDirty = Number(btn.closest(".qr-card-form").dataset.card); btn.closest(".qr-trow").remove(); break;
      case "lore-save": { const box = btn.closest(".qr-lore-edit"), form = btn.closest(".qr-card-form"); const v = (c) => box.querySelector(c).value;
        if (!v(".le-title").trim()) { toast("The lore title is empty.", "warn"); break; }
        send("lore_save", { card_id: Number(form.dataset.card), title: v(".le-title"), text: v(".le-text"), keys: v(".le-keys"), kind: v(".le-kind") || "istilah", core: box.querySelector(".le-core").checked, entry_id: box.dataset.entry ? Number(box.dataset.entry) : null, known_to: v(".le-known") }); break; }
      case "lore-del": { const box = btn.closest(".qr-lore-edit"), form = btn.closest(".qr-card-form"); send("lore_delete", { card_id: Number(form.dataset.card), entry_id: Number(box.dataset.entry) }); break; }
      case "tl-save": { const r = btn.closest(".qr-tl"), form = btn.closest(".qr-card-form"); send("timeline_save", { card_id: Number(form.dataset.card), at: r.querySelector(".tl-at").value, title: r.querySelector(".tl-title").value, text: r.querySelector(".tl-text").value, entry_id: r.dataset.entry ? Number(r.dataset.entry) : null }); break; }
      case "tl-del": { const r = btn.closest(".qr-tl"), form = btn.closest(".qr-card-form"); send("timeline_delete", { card_id: Number(form.dataset.card), entry_id: Number(r.dataset.entry) }); break; }
      case "attach-card": { const cid = dbody.querySelector(".qr-attach-card").value; if (cid) send("story_attach", { card_id: Number(cid), role: dbody.querySelector(".qr-attach-role").value }); break; }
      case "detach": send("story_detach", { card_id: id, role: btn.dataset.role }); break;
      case "canon-save": { const box = btn.closest(".qr-canon"), ta = box.querySelector("textarea"), sec = box.dataset.sec || box.querySelector(".qr-canon-new").value.trim();
        if (sec) { send("canon", { section: sec, text: ta.value }); ta.defaultValue = ta.value; if (!box.dataset.sec) { ta.value = ta.defaultValue = ""; box.querySelector(".qr-canon-new").value = ""; } } break; }
      case "toc": { const h = model.get("history") || {}, cid = get("chat").id;
        openModal("Chapters", (h.chapters || []).map((c) => `<button class="qr-libitem" data-act="jump-to" data-chat="${cid}" data-id="${c.id}">${icon("bookmark")}<b>${esc(c.title)}</b><span class="qr-muted">message ${c.n}</span></button>`).join("") || "No chapters yet. Mark one with /bab or the chapter button on a reply."); break; }
      case "speaker": send("settings", { speaker: btn.dataset.name || null }); break;
      case "props-make": send("proposals_make"); break;
      case "fame-suggest": send("fame_suggest"); break;
      case "spk-mode": setSpk(btn.dataset.mode); break;
      case "fame-table": fameModal((get("story").cards || []).filter((x) => x.role === "character" || x.role === "persona")
        .map((x) => ({ card_id: x.id, name: x.name, fame: x.fame, fame_for: x.fame_for, persona: x.role === "persona" })), false); break;
      case "fame-save": {
        const items = [...$(".qr-modal-body").querySelectorAll(".qr-fame-row")].map((r) => ({ card_id: Number(r.dataset.card),
          fame: r.querySelector(".fm-fame").value, fame_for: r.querySelector(".fm-for").value.trim() }));
        send("fame_save", { items }); closeModal(); break; }
      case "prop-yes": case "prop-no": send("proposal", { pid: Number(btn.closest("[data-pid]").dataset.pid), accept: act === "prop-yes" }); break;
      case "thread-add": { const box = btn.closest(".qr-threads"), title = box.querySelector(".qr-thread-title").value.trim();
        if (title) { send("thread_add", { kind: box.querySelector(".qr-thread-kind").value, title, due: box.querySelector(".qr-thread-due").value.trim() });
          box.querySelector(".qr-thread-title").value = ""; box.querySelector(".qr-thread-due").value = ""; } break; }
      case "thread-close": send("thread_close", { tid: Number(btn.closest("[data-tid]").dataset.tid), status: btn.dataset.status }); break;
      case "know-add": { const box = btn.closest(".qr-know"), t = box.querySelector(".qr-know-new").value.trim();
        if (t && state.know) { send("knowledge_add", { holder: state.know.holder, text: t, kind: box.querySelector(".qr-know-kind").value });
          box.querySelector(".qr-know-new").value = ""; } break; }
      case "know-save": { const row = btn.closest("[data-kid]"), ta = row.querySelector(".qr-know-text");
        if (!state.know) break;
        send("knowledge_edit", { kid: Number(row.dataset.kid), holder: state.know.holder, text: ta.value,
          truth: row.querySelector(".qr-know-truth").value });
        ta.defaultValue = ta.value; break; }
      case "know-del": if (!state.know) break;
        if (!(model.get("history") || {}).total && !confirm("This chat has no messages yet, so this memory is deleted for good. Continue?")) break;
        send("knowledge_delete", { kid: Number(btn.closest("[data-kid]").dataset.kid), holder: state.know.holder }); break;
      case "know-restore": if (state.know) send("knowledge_restore", { kid: Number(btn.closest("[data-kid]").dataset.kid), holder: state.know.holder }); break;
      case "nf-save": { const ta = dbody.querySelector(".qr-nf"); send("never_forget", { items: ta.value.split("\n") }); ta.defaultValue = ta.value; break; }
      case "apply-now": send("apply_now"); break;
      case "continue-new": if (confirm("Continue this story in a new chat (the chronicle and the last scene come along)?")) send("continue_new"); break;
      case "branches": send("branches"); break;
      case "goto": send("goto", { mid: id }); closeModal(); break;
      case "prompt-view": send("prompt_view"); break;
      case "recall-test": send("recall_test"); toast("Recall test running…"); break;
      case "export": send("export", { fmt: btn.dataset.fmt }); break;
      case "save-system": send("settings", { system: dbody.querySelector("[data-system]").value }); break;
      case "smp-reset": send("settings", { sampling: {} }); break;
      case "mem-del": send("memory_delete", { mid: id }); break;
      case "mem-undo": send("memory_undo", { log_id: id }); break;
      case "model-start": {
        const em = dbody.querySelector(".qr-emb-model").value, on = dbody.querySelector(".qr-emb").checked, run = get("server").embed_model;
        if (on && run && em !== run && !confirm(`Switch embedder ${run} → ${em}? Every vector is rebuilt in the background; until then search by meaning uses keywords only.`)) break;
        send("model_switch", { preset: dbody.querySelector(".qr-model-sel").value, ctx: Number(dbody.querySelector(".qr-ctx-sel").value), mtp: dbody.querySelector(".qr-mtp").checked, embed: on, embed_model: em }); break; }
      case "model-stop": if (confirm("Stop the model server?")) send("model_stop"); break;
      case "review": send("vocab_review", { vid: id, grade: Number(btn.dataset.grade) }); break;
      case "vocab-del": send("vocab_delete", { vid: id }); break;
      case "vocab-add": send("vocab_add", { term: btn.dataset.term, translation: btn.dataset.tr, note: btn.dataset.note, example: btn.dataset.ex }); break;
      case "jump-to": send("jump", { chat_id: Number(btn.dataset.chat), mid: id }); closeModal(); break;
      case "wizard-go": {
        const box = el.querySelector(".qr-wizard"), cards = {};
        box.querySelectorAll("select[data-role]").forEach((s) => { if (s.value) cards[s.dataset.role] = Number(s.value); });
        cards.character = [...box.querySelectorAll(".qr-wz-chars input:checked")].map((i) => Number(i.value));
        send("start_story", { cards, title: box.querySelector(".wz-title").value, greeting: Number(box.querySelector(".wz-greet").value || 1) - 1 });
        state.wizard = false; closeModal(); break;
      }
    }
  });
  el.querySelector(".qr-title").addEventListener("dblclick", () => {
    const c = get("chat"); if (!c.id) return;
    const t = prompt("Chat name:", c.title); if (t) send("rename", { chat_id: c.id, title: t });
  });

  // ---------- model events ----------
  const onAux = () => {
    const a = model.get("aux") || {};
    if (!a.kind) return;
    const d = a.data;
    // answers for another chat (the user switched meanwhile) are dropped
    if (["proposals", "threads", "knowledge", "fame"].includes(a.kind) && d && d.chat_id && d.chat_id !== get("chat").id) return;
    if (a.kind === "fame") { fameModal(d.rows || [], true); return; }
    if (a.kind === "proposals") {
      state.props = d;
      const box = dbody.querySelector(".qr-props");
      if (state.tab === "story" && box) redraw(box, propsHTML, true);
    }
    else if (a.kind === "threads") {
      state.threads = d;
      const box = dbody.querySelector(".qr-threads");
      if (state.tab === "story" && box) redraw(box, threadsHTML, true);
    }
    else if (a.kind === "knowledge") {
      state.know = d;
      const box = dbody.querySelector(".qr-know");
      if (state.tab === "story" && box) redraw(box, knowHTML, true);
    }
    else if (a.kind === "memory") {
      state.memory = d;
      const f = rootActive();
      const typing = f && dbody.contains(f) && (f.tagName === "TEXTAREA" || (f.tagName === "INPUT" && !f.classList.contains("qr-mem-q")));
      if (state.tab === "memory" && !typing) {
        const q = f && f.classList.contains("qr-mem-q") ? f.value : null, pos = q !== null ? f.selectionStart : 0;
        dbody.innerHTML = tabMemory();
        if (q !== null) { const n = dbody.querySelector(".qr-mem-q"); n.value = q; n.focus(); n.setSelectionRange(pos, pos); }
      }
    }
    else if (a.kind === "vocab") { state.vocab = d; if (state.tab === "learn") dbody.innerHTML = tabLearn(); }
    else if (a.kind === "branches") openModal("Branch tree", (d.map((b) => `<div class="qr-branch ${b.active ? "on" : ""}"><input type="checkbox" class="qr-cmp" value="${b.id}" title="Select to compare">
        <span class="qr-badge">${b.depth} ${b.depth === 1 ? "message" : "messages"}</span><span>${esc(b.preview)}</span>${b.head ? '<span class="qr-muted">active</span>' : `<button class="qr-btn qr-sm" data-act="goto" data-id="${b.id}">Open</button>`}</div>`).join("") || "No branches yet.")
        + (d.length > 1 ? `<button class="qr-btn qr-primary" data-act="compare">${icon("branch")}Compare 2 branches</button>` : ""));
    else if (a.kind === "compare") {
      const col = (msgs, id) => `<div><div class="qr-row"><b>Branch</b><button class="qr-btn qr-sm" data-act="goto" data-id="${id}">Open</button></div>${msgs.map((m) =>
        `<div class="qr-cmp-msg ${m.role}"><span class="qr-muted">${m.role === "user" ? "You" : "Narrator"}</span><div class="qr-md">${md(m.content)}</div></div>`).join("")}</div>`;
      openModal(`Compare branches (split at message ${d.split_at + 1})`, `<div class="qr-cmp-grid">${col(d.a, d.a_id)}${col(d.b, d.b_id)}</div>`);
    }
    else if (a.kind === "note") openModal("System note for this turn", d.note ? `<pre class="qr-pre">${esc(d.note)}</pre>` : "No note for this turn.");
    else if (a.kind === "side_logs") openModal("Side task log", (d || []).map((r) => `<details class="qr-lore"><summary><span class="qr-badge">${esc(r.kind)}</span>
        <span class="qr-muted">${new Date(r.created * 1000).toLocaleString("en-GB")}</span></summary><pre class="qr-pre">${esc(JSON.stringify(r.data, null, 1))}</pre></details>`).join("") || "None yet.");
    else if (a.kind === "variations") {
      state.variations = d;
      openModal(`Variations: ${d.label}`, (d.options || []).map((o, i) => `<div class="qr-variation"><pre class="qr-pre">${esc(typeof o === "string" ? o : JSON.stringify(o, null, 1))}</pre>
        <button class="qr-btn qr-sm qr-primary" data-act="use-variation" data-i="${i}">Use this</button></div>`).join("") || "The model gave no alternatives. Try again.");
    }
    else if (a.kind === "prompt") openModal("Prompt sent", `<div class="qr-muted">${fmtN(d.tokens)} tokens (system ${fmtN(d.system_tokens)}) of ${fmtN(d.max)} · epoch ${d.epoch} · ${d.history_messages} history messages</div>
        <div class="qr-muted">kwargs ${esc(JSON.stringify(d.kwargs))} · sampler ${esc(JSON.stringify(d.sampling))}</div>
        <h4>System (frozen)</h4><pre class="qr-pre">${esc(d.system)}</pre><h4>Last message + temporary block</h4><pre class="qr-pre">${esc(d.last_user_text)}</pre>`);
    else if (a.kind === "search") openModal(`Results for "${d.q}"`, (d.results || []).map((r) => `<button class="qr-libitem" data-act="jump-to" data-chat="${r.chat_id}" data-id="${r.id}"><b>${esc(r.title)}</b><span>${esc(r.snippet)}</span></button>`).join("") || "Nothing found.");
    else if (a.kind === "learn") openModal("Explanation", `<blockquote>${esc(d.text)}</blockquote><p><b>${esc(d.translation || "")}</b></p>
        ${Array.isArray(d.grammar) && d.grammar.length ? `<ul>${d.grammar.map((g) => `<li>${esc(typeof g === "string" ? g : JSON.stringify(g))}</li>`).join("")}</ul>` : ""}
        ${(Array.isArray(d.vocab) ? d.vocab : []).filter((v) => v && typeof v === "object").map((v) => `<div class="qr-memrow"><b>${esc(v.term)}</b><span>${esc(v.translation)} <span class="qr-muted">${esc(v.note || "")}</span></span>
          <button class="qr-btn qr-sm" data-act="vocab-add" data-term="${esc(v.term)}" data-tr="${esc(v.translation)}" data-note="${esc(v.note || "")}" data-ex="${esc(d.text)}">${icon("plus")}</button></div>`).join("")}`);
    else if (a.kind === "recall") openModal("Recall test", d.error ? esc(d.error) : `<p><b>${d.score}/${d.total}</b> correct</p>${d.items.map((x) => `<div class="qr-recall ${x.ok ? "ok" : "bad"}">${icon(x.ok ? "check" : "x")}<div><b>${esc(x.q)}</b><br>
        <span class="qr-muted">expected:</span> ${esc(x.expected)}<br><span class="qr-muted">answer:</span> ${esc(x.got)}</div></div>`).join("")}`);
    else if (a.kind === "schema") openModal(`Schema: ${d.label || d.type}`, `<div class="qr-help">To add a field, add an object to "fields" (key, label, section, type, core, visibility, help, options, columns). No code changes needed.</div>
        <textarea class="qr-schema-text" rows="22">${esc(JSON.stringify(d, null, 2))}</textarea><button class="qr-btn qr-primary" data-act="schema-save">Save schema</button>`);
    else if (a.kind === "scroll_to") setTimeout(() => { const n = list.querySelector(`[data-id="${d}"]`); if (n) { fol.release(); n.scrollIntoView({ block: "center" }); n.classList.add("flash"); } }, 100);
  };
  const onExport = () => {
    const ex = model.get("export") || {};
    if (!ex.b64) return;
    const bytes = Uint8Array.from(atob(ex.b64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: ex.name || "export" });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };
  const onNotice = () => {
    const n = model.get("notice") || {}, box = $(".qr-notice");
    box.hidden = !n.text;
    box.innerHTML = n.text ? `${icon("globe")}<span>${esc(n.text)}</span><button class="qr-icon qr-xs" data-act="notice-close" aria-label="Close">${icon("x")}</button>` : "";
  };
  const onToast = () => { const t = model.get("toast") || {}; if (t.text) toast(t.text, t.kind || "info", !!t.long); };
  const onCompose = () => { const c = model.get("compose") || {}; if (c.text) { input.value = c.text; grow(); input.focus(); } };
  const onChat = () => {
    const c = get("chat");
    const learn = !!((c.settings || {}).learn);
    if (learn !== state.learn) { state.learn = learn; el.classList.toggle("learn", learn); els.clear(); list.innerHTML = ""; }
    if (state.lastChat !== c.id) { state.lastChat = c.id; state.studioCard = null; state.imageIntent = false; state.know = null; state.threads = null; state.props = null; els.clear(); list.innerHTML = ""; fol.jump(); }
    syncAvatars(); renderSpeakerBar();
    renderTop(); renderChats(); renderStudio(); renderDrawer(); renderHistory();
  };
  const onCard = () => {
    const card = get("card");
    if (!card.id) return;
    state.cards.set(card.id, card);
    if (state.cardView === "new") state.cardView = card.id;
    const forms = [...el.querySelectorAll(`.qr-card-form[data-card="${card.id}"]`)];
    if (state.formDirty === card.id && forms.some((f) => Number(f.dataset.version) !== card.version)) {
      for (const f of forms) {
        const note = f.querySelector(".qr-stale");
        const html = `${icon("warn")}<span>This card has changed (version ${card.version}). Your unsaved changes are still in this form.</span>
          <button class="qr-btn qr-sm" data-act="card-reload">Load the new version</button>`;
        if (note) note.innerHTML = html; else f.insertAdjacentHTML("afterbegin", `<div class="qr-stale">${html}</div>`);
      }
      return;
    }
    if (card.id === state.studioCard) renderStudio();
    if (state.tab === "cards" && card.id === state.cardView) renderDrawer();
  };
  let raf = 0;
  const onLive = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; renderLive(); }); };
  const handlers = {
    "change:chats": renderChats, "change:chat": onChat, "change:history": () => { renderHistory(); refreshStory(); if (get("chat").kind === "studio" && state.studioCard) send("card_open", { card_id: state.studioCard }); },
    "change:live": onLive, "change:busy": renderBusy, "change:status": renderStatusLine, "change:queue": renderStatusLine,
    "change:toast": onToast, "change:ctx": renderTop, "change:panels": () => { renderPanels(); renderTop(); renderSpeakerBar(); },
    "change:server": () => {
      renderTop();
      if (state.tab !== "model" || drawer.hidden) return;
      const s = get("server");
      const k = JSON.stringify([s.phase, s.preset, s.ctx, s.mtp, s.embed, s.embed_ready, s.embed_model, s.error, s.warnings, s.installed]);
      if (k !== state.srvKey) { state.srvKey = k; renderDrawer(); return; }
      const g = dbody.querySelector(".qr-gpu");  // only the GPU line changed: leave the form as it is
      if (g) g.textContent = s.gpu ? `GPU ${s.gpu.util.toFixed(0)}% · VRAM ${s.gpu.used_gb.toFixed(1)} / ${s.gpu.total_gb.toFixed(0)} GB` : "";
    }, "change:backup": renderBackup,
    "change:library": () => { if (state.tab === "cards" || state.tab === "story") renderDrawer(); renderWizard(); },
    "change:card": onCard, "change:story": () => { if (syncAvatars()) renderHistory(); renderSpeakerBar(); renderStudio(); if (state.tab === "story") renderDrawer(); },
    "change:rev": () => {
      if (drawer.hidden) return;
      if (state.tab === "memory") send("memory", { q: (state.memory || {}).q || "" });
      if (state.tab === "story" && state.know) send("knowledge", { holder: state.know.holder });
      if (state.tab === "story" && state.threads) send("threads");
      if (state.tab === "story" && state.props) send("proposals");
    },
    "change:aux": onAux, "change:notice": onNotice, "change:export": onExport, "change:compose": onCompose, "change:boot": renderDrawer,
  };
  for (const [ev, fn] of Object.entries(handlers)) model.on(ev, fn);
  const timer = setInterval(renderBackup, 30000);
  onChat(); renderBusy(); renderLive(); renderPanels(); renderBackup(); renderStatusLine();
  const cleanup = () => {
    for (const [ev, fn] of Object.entries(handlers)) model.off(ev, fn);
    clearInterval(timer); themeObs.disconnect(); ac.abort(); ro1.disconnect(); ro2.disconnect();
    if (el.__qrCleanup === cleanup) el.__qrCleanup = null;
  };
  el.__qrCleanup = cleanup;
  return cleanup;
}
export default { render };
"""

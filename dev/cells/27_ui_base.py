UI_BASE_JS = r"""
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-3.8L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.9 3.8L20 16"/><path d="M20 20v-4h-4"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>', down: '<path d="M6 9l6 6 6-6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  clip: '<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
  arrowdown: '<path d="M12 5v14M5 12l7 7 7-7"/>',
  branch: '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 7v10M18 10c0 4-6 3-12 7"/>',
  pin: '<path d="M9 4h6l-1 6 3 3H7l3-3-1-6zM12 13v7"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z"/><path d="M4 19a2 2 0 0 1 2-2h13"/>',
  sparkles: '<path d="M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8L12 3z"/><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z"/>',
  archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8M10 12h4"/>',
  chat: '<path d="M4 5h16v11H8l-4 4V5z"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15 14a5 5 0 0 1 6 5"/>',
  cloud: '<path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9a4.5 4.5 0 0 0 1 9z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  dice: '<rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r="1"/><circle cx="15" cy="15" r="1"/><circle cx="15" cy="9" r="1"/><circle cx="9" cy="15" r="1"/>',
  warn: '<path d="M12 4l9 16H3L12 4z"/><path d="M12 10v4M12 17v.5"/>',
  check: '<path d="M5 12l5 5 9-10"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  wand: '<path d="M4 20L15 9M14 4v3M18 6h-3M20 10h-3M17 13v-3"/>',
  forward: '<path d="M5 6l7 6-7 6M13 6l7 6-7 6"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>', upload: '<path d="M12 20V9M7 14l5-5 5 5M5 4h14"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 3 5 3 3 0 0 0 5 1V5a3 3 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-3 5 3 3 0 0 1-5 1"/>',
  tool: '<path d="M14 6a4 4 0 0 0 5 5l-9 9-3-3 9-9a4 4 0 0 0-2-2z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  card: '<rect x="4" y="3" width="16" height="18" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M8 17a4 4 0 0 1 8 0"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4V3z"/>',
  learn: '<path d="M2 9l10-5 10 5-10 5-10-5z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>', skip: '<path d="M5 5l9 7-9 7V5zM17 5v14"/>',
  map: '<path d="M9 4l6 2 5-2v14l-5 2-6-2-5 2V6l5-2zM9 4v14M15 6v14"/>',
};
const icon = (n, cls = "") => `<svg class="qi ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const words = (s) => (String(s || "").trim().match(/\S+/g) || []).length;
const fmtN = (n) => Number(n || 0).toLocaleString("id-ID");
const ago = (t) => {
  if (!t) return "belum";
  const m = Math.floor((Date.now() / 1000 - t) / 60);
  return m < 1 ? "baru saja" : m < 60 ? `${m} mnt lalu` : m < 1440 ? `${Math.floor(m / 60)} jam lalu` : `${Math.floor(m / 1440)} hari lalu`;
};
const kb = (n) => n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
const readB64 = (f) => new Promise((ok, fail) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result).split(",")[1] || "");
  r.onerror = () => fail(r.error);
  r.readAsDataURL(f);
});

// Markdown subset, escape-first: nothing from the model is ever inserted as raw HTML.
function inline(s, learn) {
  let t = esc(s);
  t = t.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  t = t.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?;:]|$)/g, "$1<em>$2</em>");
  t = t.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,!?;:]|$)/g, "$1<em>$2</em>");
  // dialogue: quoted speech, then a translation in parentheses right after it
  t = t.replace(/(&quot;|“|„|«)([^\n]{1,600}?)(&quot;|”|“|»)(\s*)\(([^()\n]{1,400})\)/g,
    (m, a, q, b, sp, tr) => `<span class="qq" data-q="${q.replace(/"/g, "&quot;")}">${a}${q}${b}</span>${sp}<span class="qtr">(${tr})</span>`);
  return t;
}
function md(src, learn) {
  const text = String(src || "").replace(/\r\n/g, "\n");
  const out = [];
  const lines = text.split("\n");
  let i = 0, para = [];
  const flush = () => { if (para.length) { out.push(`<p>${para.map((l) => inline(l, learn)).join("<br>")}</p>`); para = []; } };
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      flush();
      const buf = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { flush(); out.push(`<h${h[1].length + 2}>${inline(h[2], learn)}</h${h[1].length + 2}>`); i++; continue; }
    if (/^\s*([-*]|\d+[.)])\s+/.test(line)) {
      flush();
      const ordered = /^\s*\d/.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+[.)])\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+[.)])\s+/, ""));
      out.push(`<${ordered ? "ol" : "ul"}>${items.map((x) => `<li>${inline(x, learn)}</li>`).join("")}</${ordered ? "ol" : "ul"}>`);
      continue;
    }
    if (/^>\s?/.test(line)) {
      flush();
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote>${buf.map((l) => inline(l, learn)).join("<br>")}</blockquote>`);
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      flush();
      const row = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = row(line);
      i += 2;
      const body = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) body.push(row(lines[i++]));
      out.push(`<table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.map((r) =>
        `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    if (!line.trim()) { flush(); i++; continue; }
    para.push(line);
    i++;
  }
  flush();
  return out.join("");
}

// Scroll that only follows new content while the user has not scrolled away.
function follower(box, onState) {
  let follow = true, programmatic = false;
  const atBottom = (gap = 8) => box.scrollHeight - box.scrollTop - box.clientHeight <= gap;
  const leave = () => { if (follow) { follow = false; onState && onState(false); } };
  box.addEventListener("wheel", (e) => { if (e.deltaY < 0) leave(); }, { passive: true });
  box.addEventListener("touchmove", leave, { passive: true });
  box.addEventListener("keydown", (e) => { if (["PageUp", "ArrowUp", "Home"].includes(e.key)) leave(); });
  box.addEventListener("pointerdown", (e) => { if (e.offsetX > box.clientWidth) leave(); });
  box.addEventListener("scroll", () => {
    if (programmatic) { programmatic = false; return; }
    if (atBottom()) { if (!follow) { follow = true; onState && onState(true); } }
  }, { passive: true });
  return {
    get following() { return follow; },
    stick() {
      if (!follow) return;
      const target = box.scrollHeight - box.clientHeight;
      if (Math.abs(target - box.scrollTop) > 1) { programmatic = true; box.scrollTop = target; }
    },
    jump() { follow = true; onState && onState(true); programmatic = true; box.scrollTop = box.scrollHeight; },
    release() { leave(); },
  };
}
"""

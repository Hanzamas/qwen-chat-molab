UI_CSS = r"""
.qr { --bg:#212121; --panel:#171717; --raise:#2a2a2a; --bubble:#303030; --line:#363636; --text:#ececec; --muted:#9b9b9b;
  --accent:#2fb886; --accent-ink:#06130d; --danger:#ef5350; --warn:#e0a83a; --ok:#2fb886; --code:#0f0f0f;
  --tr:#a8a8a8; --radius:14px;
  color-scheme: dark; background:var(--bg); color:var(--text); display:flex; position:relative; overflow:hidden;
  height:calc(100vh - 140px); min-height:600px; border:1px solid var(--line); border-radius:18px;
  font: 15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.qr[data-theme="light"] { --bg:#ffffff; --panel:#f7f7f8; --raise:#ececf1; --bubble:#f1f1f3; --line:#e3e3e8; --text:#1f1f1f;
  --muted:#6b6b72; --accent:#13865f; --accent-ink:#ffffff; --code:#f4f4f6; --tr:#6f6f76; color-scheme: light; }
.qr *, .qr *::before, .qr *::after { box-sizing:border-box; }
.qr .qi { width:18px; height:18px; flex:none; fill:none; stroke:currentColor; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }
:where(.qr) button { font:inherit; color:inherit; cursor:pointer; }
.qr button:disabled { opacity:.5; cursor:not-allowed; }
.qr :focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.qr input, .qr textarea, .qr select { font:inherit; color:var(--text); background:var(--raise); border:1px solid var(--line);
  border-radius:10px; padding:7px 10px; width:100%; }
.qr textarea { resize:vertical; line-height:1.5; }
.qr label { display:flex; flex-direction:column; gap:4px; font-size:13px; color:var(--muted); margin:8px 0; }
.qr label.qr-check { flex-direction:row; align-items:center; gap:8px; color:var(--text); }
.qr label.qr-check input { width:auto; }
.qr h4 { margin:18px 0 8px; font-size:13px; text-transform:none; color:var(--text); display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.qr-muted { color:var(--muted); font-size:13px; }
.qr-pad { padding:10px; }
.qr-row { display:flex; gap:8px; align-items:center; }
.qr-wrap { flex-wrap:wrap; }
.qr-grid2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.qr-btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; background:var(--raise); border:1px solid var(--line);
  border-radius:10px; padding:7px 12px; font-size:14px; white-space:nowrap; }
.qr-btn:hover { border-color:color-mix(in srgb, var(--text) 25%, var(--line)); }
.qr-btn.qr-sm { padding:4px 9px; font-size:13px; border-radius:8px; }
.qr-btn.qr-primary { background:var(--accent); color:var(--accent-ink); border-color:transparent; font-weight:600; }
.qr-btn.qr-danger { color:var(--danger); }
.qr-icon { display:inline-grid; place-items:center; width:34px; height:34px; border-radius:10px; background:transparent; border:0; color:var(--muted); }
.qr-icon:hover { background:var(--raise); color:var(--text); }
.qr-icon.qr-xs { width:26px; height:26px; border-radius:7px; }
.qr-icon.qr-xs .qi { width:15px; height:15px; }
.qr-badge { display:inline-flex; align-items:center; gap:3px; font-size:11px; padding:1px 7px; border-radius:999px; background:var(--raise);
  border:1px solid var(--line); color:var(--muted); font-weight:500; }
.qr-badge .qi { width:11px; height:11px; }

/* sidebar */
.qr-side { width:270px; flex:none; background:var(--panel); border-right:1px solid var(--line); display:flex; flex-direction:column; padding:12px; gap:10px; }
.qr-brand { display:flex; align-items:center; gap:8px; font-weight:650; padding:4px 6px 2px; letter-spacing:-.01em; }
.qr-brand .qi { color:var(--accent); }
.qr-new { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; }
.qr-new .qr-btn { padding:7px 6px; font-size:13px; }
.qr-search { flex-direction:row !important; align-items:center; gap:6px !important; background:var(--raise); border:1px solid var(--line);
  border-radius:10px; padding:0 10px; margin:0 !important; color:var(--muted); }
.qr-search input { border:0; background:transparent; padding:8px 0; }
.qr-chats { flex:1; overflow-y:auto; overscroll-behavior:contain; margin:0 -4px; padding:0 4px; }
.qr-group { font-size:12px; color:var(--muted); padding:12px 8px 4px; font-weight:600; }
.qr-chat { display:flex; align-items:center; gap:8px; padding:7px 8px; border-radius:9px; cursor:pointer; color:var(--text); }
.qr-chat .qi { color:var(--muted); width:16px; height:16px; }
.qr-chat:hover { background:var(--raise); }
.qr-chat.on { background:color-mix(in srgb, var(--raise) 70%, var(--text) 8%); }
.qr-chat-t { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }
.qr-chat .qr-icon { visibility:hidden; }
.qr-chat:hover .qr-icon, .qr-chat.on .qr-icon { visibility:visible; }
.qr-side-foot { display:flex; flex-direction:column; gap:8px; border-top:1px solid var(--line); padding-top:10px; }
.qr-side-foot .qr-btn { flex:1; }
.qr-backup { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--muted); }

/* main */
.qr-main { flex:1; min-width:0; display:flex; flex-direction:column; position:relative; }
.qr-top { display:flex; align-items:center; gap:6px; padding:8px 12px; border-bottom:1px solid var(--line); min-height:52px; }
.qr-toggle { display:none; }
.qr-title { font-weight:600; flex:1; min-width:60px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; cursor:text; }
.qr-chips { display:flex; gap:6px; align-items:center; overflow:hidden; }
.qr-chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; background:var(--raise); border:1px solid var(--line);
  font-size:13px; white-space:nowrap; max-width:260px; overflow:hidden; text-overflow:ellipsis; }
.qr-chip.qr-ghost { background:transparent; color:var(--muted); }
.qr-chip .qi { width:14px; height:14px; }
.qr-dot { width:8px; height:8px; border-radius:50%; display:inline-block; background:var(--muted); flex:none; }
.qr-dot.ok { background:var(--ok); } .qr-dot.bad { background:var(--danger); } .qr-dot.wait { background:var(--warn); animation:qr-pulse 1.4s infinite; }
@keyframes qr-pulse { 50% { opacity:.35; } }
.qr-ctxbar { height:2px; background:transparent; }
.qr-ctxfill { height:100%; width:0; background:var(--accent); transition:width .4s ease; opacity:.7; }
.qr-ctxfill.warn { background:var(--danger); }
.qr-body { flex:1; min-height:0; display:flex; position:relative; }
.qr-scroll { flex:1; overflow-y:auto; overscroll-behavior:contain; outline:none; }
.qr-col { max-width:800px; margin:0 auto; padding:24px 20px 24px; }
.qr-more { display:flex; margin:0 auto 16px; }
.qr-empty { text-align:center; color:var(--muted); margin:16vh auto 0; max-width:520px; }
.qr-empty h2 { color:var(--text); font-weight:600; font-size:24px; margin:0 0 8px; letter-spacing:-.01em; }
.qr-item.flash .qr-msg { animation:qr-flash 1.6s ease; }
@keyframes qr-flash { 0% { background:color-mix(in srgb, var(--accent) 18%, transparent); } 100% { background:transparent; } }
.qr-msg { margin:0 0 26px; }
.qr-user { display:flex; flex-direction:column; align-items:flex-end; gap:6px; }
.qr-bubble { background:var(--bubble); border-radius:20px; padding:10px 16px; max-width:80%; overflow-wrap:anywhere; white-space:normal; }
.qr-user.ooc .qr-bubble, .qr-bot.ooc .qr-md { opacity:.85; font-size:14px; }
.qr-ooc { font-size:11px; font-weight:700; letter-spacing:.04em; color:var(--warn); margin-right:6px; }
.qr-user.pinned .qr-bubble, .qr-bot.pinned .qr-md { box-shadow:inset 3px 0 0 var(--accent); padding-left:12px; }
.qr-atts { display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }
.qr-att { display:inline-flex; align-items:center; gap:5px; font-size:12px; background:var(--raise); border:1px solid var(--line);
  border-radius:8px; padding:2px 8px; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.qr-att.warn { color:var(--warn); }
.qr-att .qi { width:13px; height:13px; }
.qr-actions { display:flex; gap:2px; align-items:center; opacity:0; transition:opacity .15s; margin-top:2px; }
.qr-msg:hover .qr-actions, .qr-msg:focus-within .qr-actions { opacity:1; }
@media (hover:none) { .qr-actions { opacity:1; } }
.qr-swipe { display:inline-flex; align-items:center; font-size:12px; color:var(--muted); margin-right:4px; }
.qr-skip-row { display:flex; flex-direction:column; align-items:center; gap:4px; }
.qr-pill { display:inline-flex; align-items:center; gap:6px; font-size:13px; color:var(--muted); border:1px dashed var(--line); border-radius:999px; padding:3px 12px; }
.qr-chapter { display:flex; align-items:center; gap:8px; justify-content:center; color:var(--muted); font-size:13px; margin:8px 0 22px; font-weight:600; }
.qr-chapter::before, .qr-chapter::after { content:""; flex:1; height:1px; background:var(--line); }

/* rendered prose */
.qr-md { overflow-wrap:anywhere; font-size:16px; line-height:1.72; max-width:72ch; }
.qr-md p { margin:0 0 14px; }
.qr-md p:last-child { margin-bottom:0; }
.qr-md h3, .qr-md h4, .qr-md h5, .qr-md h6 { margin:18px 0 8px; line-height:1.3; }
.qr-md ul, .qr-md ol { margin:0 0 14px; padding-left:22px; }
.qr-md blockquote { border-left:3px solid var(--line); margin:10px 0; padding-left:12px; color:var(--muted); }
.qr-md pre { background:var(--code); border:1px solid var(--line); border-radius:10px; padding:12px 14px; overflow-x:auto; font-size:13px; line-height:1.5; }
.qr-md code { font-family:ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size:.88em; }
.qr-md :not(pre) > code { background:var(--raise); padding:1px 6px; border-radius:6px; }
.qr-md a { color:var(--accent); }
.qr-md table { border-collapse:collapse; margin:10px 0; font-size:14px; }
.qr-md th, .qr-md td { border:1px solid var(--line); padding:5px 10px; }
.qr-md p.qr-speaker { display:block; }
.qr-md p.qr-speaker .qr-avatar { display:inline-grid; vertical-align:-6px; margin-right:6px; }
.qr-md .qtr { color:var(--tr); font-style:italic; font-size:.94em; }
.qr.learn .qr-md .qtr { filter:blur(5px); transition:filter .15s; }
.qr.learn .qr-md .qtr:hover { filter:none; }
.qr.learn .qr-md .qq { cursor:help; text-decoration:underline dotted color-mix(in srgb, var(--accent) 60%, transparent); text-underline-offset:4px; }

/* thinking and tools */
.qr-think { margin-bottom:12px; color:var(--muted); font-size:14px; }
.qr-think summary, .qr-tool summary, .qr-summary summary, .qr-adv summary, .qr-lore summary { cursor:pointer; list-style:none; display:flex; align-items:center; gap:8px; user-select:none; }
.qr-think summary::-webkit-details-marker, .qr-tool summary::-webkit-details-marker { display:none; }
.qr-think-box { max-height:340px; overflow-y:auto; overscroll-behavior:contain; border-left:2px solid var(--line); margin:8px 0 6px; padding:2px 0 2px 14px; }
.qr-think.full .qr-think-box { max-height:none; }
.qr-think-body { white-space:pre-wrap; font-size:13.5px; line-height:1.6; }
.qr-think-follow, .qr-think-full { margin:0 6px 0 16px; }
.qr-tools { display:flex; flex-direction:column; gap:4px; margin-bottom:10px; }
.qr-tool { font-size:13px; color:var(--muted); }
.qr-tool summary b { color:var(--text); font-family:ui-monospace, Menlo, Consolas, monospace; font-weight:500; font-size:12.5px; }
.qr-tool summary span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:420px; }
.qr-tool summary em { color:var(--warn); font-style:normal; }
.qr-tool.err summary em { color:var(--danger); }
.qr-tool pre { white-space:pre-wrap; background:var(--code); border:1px solid var(--line); border-radius:8px; padding:8px 10px; max-height:260px; overflow:auto; font-size:12px; }
.qr-dices, .qr-flags { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 10px; align-items:center; }
.qr-dice { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; border-radius:999px; padding:2px 10px; border:1px solid var(--line); }
.qr-dice.ok { color:var(--ok); } .qr-dice.bad { color:var(--danger); }
.qr-dice .qi, .qr-flag .qi { width:14px; height:14px; }
.qr-flag { display:inline-flex; align-items:center; gap:6px; font-size:12.5px; color:var(--warn); }
.qr-fact { display:flex; gap:8px; font-size:13px; border:1px solid color-mix(in srgb, var(--warn) 45%, var(--line)); border-radius:10px; padding:8px 10px; margin:8px 0; }
.qr-fact .qi { color:var(--warn); }
.qr-partial { display:flex; align-items:center; gap:8px; color:var(--warn); font-size:13px; margin-top:8px; }
.qr-error { color:var(--danger); font-size:13.5px; margin-top:8px; white-space:pre-wrap; }
.qr-stats-line { color:var(--muted); font-size:12px; margin-top:10px; }
.qr-phase { margin-top:6px; font-size:13px; }
.qr-typing { display:inline-flex; gap:4px; padding:6px 0; }
.qr-typing span { width:6px; height:6px; border-radius:50%; background:var(--muted); animation:qr-blink 1.2s infinite; }
.qr-typing span:nth-child(2) { animation-delay:.2s; } .qr-typing span:nth-child(3) { animation-delay:.4s; }
@keyframes qr-blink { 0%, 80%, 100% { opacity:.25; } 40% { opacity:1; } }
@media (prefers-reduced-motion: reduce) { .qr-typing span, .qr-dot.wait { animation:none; } }
.qr-summary { border:1px dashed var(--line); border-radius:12px; padding:8px 12px; color:var(--muted); font-size:13px; }
.qr-summary .qr-md { font-size:14px; color:var(--text); margin-top:8px; }

/* choices */
.qr-choices { display:flex; flex-direction:column; gap:14px; margin-top:16px; }
.qr-q { font-size:14.5px; color:var(--muted); margin-bottom:8px; line-height:1.55; }
.qr-opt { display:flex; align-items:stretch; gap:4px; margin-bottom:6px; }
.qr-opt-main { flex:1; text-align:left; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 14px;
  line-height:1.55; font-size:14.5px; }
.qr-opt-main:hover { border-color:var(--accent); }

/* game panels */
.qr-status-panel { border-bottom:1px solid var(--line); padding:8px 16px; font-size:13px; display:flex; flex-direction:column; gap:6px; }
.qr-sp-head { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.qr-sp-head .qi { width:14px; height:14px; color:var(--muted); }
.qr-stats { display:flex; flex-wrap:wrap; gap:4px 18px; }
.qr-stat { display:flex; align-items:center; gap:6px; }
.qr-stat span { color:var(--muted); }
.qr-sbar { width:70px; height:5px; background:var(--raise); border-radius:999px; overflow:hidden; }
.qr-sbar i { display:block; height:100%; background:var(--accent); }
.qr-stat em { font-style:normal; font-size:11.5px; } .qr-stat em.up { color:var(--ok); } .qr-stat em.dn { color:var(--danger); }
.qr-tags { display:flex; flex-wrap:wrap; gap:6px; }
.qr-tag { font-size:12px; color:var(--muted); background:var(--raise); border-radius:8px; padding:1px 8px; }
.qr-world { border-top:1px solid var(--line); max-height:34vh; overflow-y:auto; }
.qr-world-head { display:flex; align-items:center; gap:8px; width:100%; background:transparent; border:0; padding:8px 16px; font-size:13px; text-align:left; }
.qr-world-head .qr-muted { flex:1; }
.qr-world-body { padding:0 16px 10px; font-size:13.5px; }
.qr-event { padding:3px 0; } .qr-event.new { color:var(--text); font-weight:500; }
.qr-skips { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:8px; color:var(--muted); }

/* composer */
.qr-composer { padding:8px 20px 16px; }
.qr-pending, .qr-statusline { max-width:800px; margin:0 auto 6px; display:flex; flex-wrap:wrap; gap:6px; font-size:13px; color:var(--muted); }
.qr-form { max-width:800px; margin:0 auto; display:flex; align-items:flex-end; gap:4px; background:var(--bubble); border:1px solid var(--line);
  border-radius:26px; padding:6px 6px 6px 8px; }
.qr-form:focus-within { border-color:color-mix(in srgb, var(--text) 30%, var(--line)); }
.qr .qr-input:focus-visible { outline:none; }
.qr-input { flex:1; border:0 !important; background:transparent !important; resize:none !important; padding:8px 4px !important; max-height:240px; }
.qr-note-chip { font-size:12px; border:1px solid var(--line); background:var(--raise); border-radius:999px; padding:4px 10px; color:var(--muted);
  max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; align-self:center; }
.qr-send { width:36px; height:36px; border-radius:50%; border:0; background:var(--text); color:var(--bg); display:grid; place-items:center; flex:none; }
.qr-send.stop { background:var(--danger); color:#fff; }
.qr-jump { position:absolute; left:50%; transform:translateX(-50%); bottom:14px; width:36px; height:36px; border-radius:50%;
  background:var(--panel); border:1px solid var(--line); display:grid; place-items:center; color:var(--text); z-index:3; box-shadow:0 2px 10px rgba(0,0,0,.25); }
.qr-drop { position:absolute; inset:12px; border:2px dashed var(--accent); border-radius:16px; background:color-mix(in srgb, var(--accent) 8%, transparent);
  display:flex; align-items:center; justify-content:center; font-size:16px; pointer-events:none; z-index:5; }
.qr-drop[hidden], .qr [hidden] { display:none !important; }

/* studio pane */
.qr-studio { width:400px; flex:none; border-left:1px solid var(--line); overflow-y:auto; overscroll-behavior:contain; padding:12px 14px; background:var(--panel); }
.qr-studio-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.qr-studio-quick, .qr-studio-tabs { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }
.qr-tabbtn { display:inline-flex; align-items:center; gap:6px; background:transparent; border:1px solid transparent; border-radius:9px; padding:5px 9px; font-size:13px; color:var(--muted); }
.qr-tabbtn.on { background:var(--raise); border-color:var(--line); color:var(--text); }
.qr-tabbtn .qi { width:15px; height:15px; }

/* drawer */
.qr-drawer { position:absolute; top:0; right:0; bottom:0; width:min(460px, 100%); background:var(--panel); border-left:1px solid var(--line);
  display:flex; flex-direction:column; z-index:6; box-shadow:-8px 0 24px rgba(0,0,0,.25); }
.qr-drawer-head { display:flex; align-items:center; gap:6px; padding:8px 10px; border-bottom:1px solid var(--line); }
.qr-tabs { display:grid; grid-template-columns:repeat(6, 1fr); gap:2px; flex:1; }
.qr-tabs .qr-tabbtn { flex-direction:column; gap:2px; font-size:11.5px; padding:5px 2px; }
.qr-drawer-body { flex:1; overflow-y:auto; overscroll-behavior:contain; padding:4px 16px 24px; }
.qr-drawer-body section { border-bottom:1px solid var(--line); padding-bottom:12px; }
.qr-slider { flex-direction:row !important; align-items:center; gap:10px !important; }
.qr-slider input { flex:1; padding:0; background:transparent; border:0; accent-color:var(--accent); }
.qr-slider output { width:44px; text-align:right; color:var(--text); font-variant-numeric:tabular-nums; }
.qr-adv { margin-top:14px; font-size:13px; color:var(--muted); }
.qr-linkrow, .qr-memrow, .qr-branch, .qr-factrow { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid color-mix(in srgb, var(--line) 60%, transparent); font-size:13.5px; }
.qr-linkrow b, .qr-memrow span:not(.qr-badge):not(.qr-muted), .qr-branch span:not(.qr-badge):not(.qr-muted) { flex:1; min-width:0; overflow-wrap:anywhere; }
.qr-memrow.undone { opacity:.5; }
.qr-libitem { display:flex; align-items:center; gap:8px; width:100%; text-align:left; background:transparent; border:0; border-radius:9px; padding:7px 8px; font-size:14px; flex-wrap:wrap; }
.qr-libitem:hover { background:var(--raise); }
.qr-libitem span:nth-of-type(1) { flex:1; }
.qr-canon { display:flex; flex-direction:column; gap:6px; margin-bottom:10px; }
.qr-srv { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.qr-help { font-size:12px; color:var(--muted); margin:2px 0 6px; }
.qr-flash { border:1px solid var(--line); border-radius:12px; padding:14px; }
.qr-flash-term { font-size:22px; font-weight:600; margin-bottom:8px; }
.qr-recall { display:flex; gap:8px; margin:8px 0; font-size:13.5px; }
.qr-recall.ok .qi { color:var(--ok); } .qr-recall.bad .qi { color:var(--danger); }

/* card form */
.qr-card-form fieldset { border:1px solid var(--line); border-radius:12px; padding:6px 12px 10px; margin:12px 0; }
.qr-card-form legend { font-size:12.5px; color:var(--muted); padding:0 6px; font-weight:600; }
.qr-card-top { display:flex; align-items:center; gap:12px; margin:10px 0; }
.qr-avatar { width:56px; height:56px; border-radius:12px; object-fit:cover; background:var(--raise); display:grid; place-items:center; color:var(--muted); }
.qr-avatar.sm { width:26px; height:26px; border-radius:7px; }
.qr .qr-flabel { font-size:13px; color:var(--text); font-weight:500; display:flex; flex-direction:row; gap:6px; align-items:center;
  flex-wrap:wrap; margin:0 0 4px; }
.qr-field { margin:10px 0; }
.qr-field label { margin:0 0 4px; }
.qr-table { display:flex; flex-direction:column; gap:4px; }
.qr-trow { display:flex; gap:4px; align-items:center; }
.qr-trow input { padding:5px 8px; font-size:13px; }
.qr-thead span { flex:1; font-size:11.5px; color:var(--muted); }
.qr-thead span:last-child { flex:none; width:26px; }
.qr-lore { border-bottom:1px solid color-mix(in srgb, var(--line) 60%, transparent); padding:6px 0; font-size:13.5px; }
.qr-lore-edit { display:flex; flex-direction:column; gap:6px; margin:8px 0; }
.qr-tl { display:grid; grid-template-columns:150px 1fr 1fr 26px 26px; gap:4px; margin:4px 0; }
.qr-tl input { padding:5px 8px; font-size:13px; }
.qr-version-sel { width:auto; }

/* modal and toasts */
.qr-modal { position:absolute; inset:0; background:rgba(0,0,0,.45); display:grid; place-items:center; z-index:8; padding:16px; }
.qr-modal-box { background:var(--panel); border:1px solid var(--line); border-radius:16px; width:min(760px, 100%); max-height:88%; display:flex; flex-direction:column; }
.qr-modal-head { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-bottom:1px solid var(--line); font-weight:600; }
.qr-modal-body { overflow-y:auto; padding:12px 16px 18px; font-size:14px; }
.qr-pre { white-space:pre-wrap; background:var(--code); border:1px solid var(--line); border-radius:10px; padding:10px; font-size:12px; max-height:40vh; overflow:auto; }
.qr-wizard select, .qr-wizard input { margin-top:2px; }
.qr-wz-chars { display:flex; flex-wrap:wrap; gap:4px 16px; margin:4px 0 8px; }
.qr-toasts { position:absolute; left:50%; transform:translateX(-50%); bottom:96px; display:flex; flex-direction:column; gap:6px; z-index:9; width:min(560px, 92%); }
.qr-toast { background:var(--text); color:var(--bg); border-radius:12px; padding:9px 14px; font-size:13.5px; white-space:pre-wrap; box-shadow:0 4px 16px rgba(0,0,0,.3); cursor:pointer; }
.qr-toast.qr-error { background:var(--danger); color:#fff; } .qr-toast.qr-warn { background:var(--warn); color:#1a1200; }

/* narrow screens */
@media (max-width: 900px) { .qr.studio-on .qr-studio { position:absolute; inset:52px 0 0 auto; width:min(400px, 92%); z-index:4; box-shadow:-6px 0 18px rgba(0,0,0,.25); } }
@media (max-width: 760px) {
  .qr { height:calc(100vh - 80px); border-radius:12px; }
  .qr-side { position:absolute; z-index:7; inset:0 auto 0 0; transform:translateX(-102%); transition:transform .2s ease; box-shadow:6px 0 18px rgba(0,0,0,.3); }
  .qr.side-open .qr-side { transform:none; }
  .qr-toggle { display:inline-grid; }
  .qr-chips .qr-ghost { display:none; }
  .qr-col { padding:16px 12px; }
  .qr-composer { padding:6px 10px 10px; }
  .qr-bubble { max-width:92%; }
  .qr-grid2 { grid-template-columns:1fr; }
  .qr-tl { grid-template-columns:1fr 1fr; }
}
"""

UI_ESM = UI_BASE_JS + UI_APP_JS

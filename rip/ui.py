"""Seekr's internal exploration UI, served at /ui.

One self-contained page (hash-routed). Talks to the /v1 API with a bearer
token the operator pastes once and we keep in localStorage. Exploration,
review and debugging only — no ranking anywhere.
"""

UI_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seekr</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#fbfbfd; --surface:#ffffff; --surface2:#f5f6f8; --raised:#ffffff;
  --ink:#15171c; --ink2:#3d434e; --muted:#6b7280; --faint:#9aa1ad;
  --line:#e5e7ec; --line2:#eef0f4;
  --accent:#3b4ce8; --accent-ink:#ffffff; --accent-soft:#eef0fe;
  --ok:#16794c; --ok-soft:#e7f5ee;
  --warn:#a65b00; --warn-soft:#fdf1e3;
  --danger:#c2255c; --danger-soft:#fdecf2;
  --shadow:0 1px 2px rgba(16,18,24,.04), 0 4px 12px rgba(16,18,24,.05);
  --radius:8px; --radius-sm:6px;
  --sans:"Instrument Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono:"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0b0c0f; --surface:#141619; --surface2:#1b1e23; --raised:#181b1f;
    --ink:#e9ebef; --ink2:#c3c8d0; --muted:#8b919c; --faint:#6a707b;
    --line:#252932; --line2:#1f232a;
    --accent:#7b8bff; --accent-ink:#0b0c0f; --accent-soft:#1a1e33;
    --ok:#4ade80; --ok-soft:#132318;
    --warn:#fbbf24; --warn-soft:#251c0d;
    --danger:#fb7185; --danger-soft:#2a1119;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 4px 14px rgba(0,0,0,.28);
  }
}
:root[data-theme="dark"]{
  --bg:#0b0c0f; --surface:#141619; --surface2:#1b1e23; --raised:#181b1f;
  --ink:#e9ebef; --ink2:#c3c8d0; --muted:#8b919c; --faint:#6a707b;
  --line:#252932; --line2:#1f232a;
  --accent:#7b8bff; --accent-ink:#0b0c0f; --accent-soft:#1a1e33;
  --ok:#4ade80; --ok-soft:#132318;
  --warn:#fbbf24; --warn-soft:#251c0d;
  --danger:#fb7185; --danger-soft:#2a1119;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 4px 14px rgba(0,0,0,.28);
}
*{box-sizing:border-box; margin:0; padding:0}
html{-webkit-text-size-adjust:100%}
body{
  background:var(--bg); color:var(--ink); font-family:var(--sans);
  font-size:14px; line-height:1.5; -webkit-font-smoothing:antialiased;
}
a{color:var(--accent); text-decoration:none}
a:hover{text-decoration:underline}
button{font:inherit; cursor:pointer}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:4px}
@media (prefers-reduced-motion:reduce){ *{animation:none !important; transition:none !important} }

/* ---------- shell ---------- */
.shell{display:grid; grid-template-columns:236px 1fr; min-height:100vh}
.rail{
  border-right:1px solid var(--line); background:var(--surface);
  display:flex; flex-direction:column; position:sticky; top:0; height:100vh;
}
.brand{display:flex; align-items:center; gap:9px; padding:20px 18px 18px}
.brand .mark{
  width:26px; height:26px; border-radius:7px; background:var(--ink);
  display:grid; place-items:center; flex:none;
}
.brand .mark svg{stroke:var(--bg)}
.brand b{font-size:16px; font-weight:600; letter-spacing:-.02em}
.brand span{font-size:11px; color:var(--faint); display:block; letter-spacing:.02em; margin-top:-2px}
nav{display:flex; flex-direction:column; gap:1px; padding:6px 10px}
nav a{
  display:flex; align-items:center; gap:9px; padding:7px 10px; border-radius:var(--radius-sm);
  color:var(--ink2); font-size:13.5px; font-weight:500; transition:background .12s, color .12s;
}
nav a:hover{background:var(--surface2); text-decoration:none; color:var(--ink)}
nav a.active{background:var(--accent-soft); color:var(--accent)}
nav a svg{flex:none; opacity:.85}
.rail-foot{margin-top:auto; padding:14px 16px; border-top:1px solid var(--line2); font-size:11.5px; color:var(--faint)}
.rail-foot .stat{display:flex; justify-content:space-between; padding:2px 0; font-variant-numeric:tabular-nums}
.rail-foot .stat b{color:var(--ink2); font-weight:500}
.themebtn{
  margin-top:10px; width:100%; border:1px solid var(--line); background:var(--surface);
  color:var(--muted); border-radius:var(--radius-sm); padding:5px; font-size:11.5px;
}
.themebtn:hover{background:var(--surface2); color:var(--ink)}

main{min-width:0; display:flex; flex-direction:column}
.topbar{
  position:sticky; top:0; z-index:20; background:color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter:blur(8px); border-bottom:1px solid var(--line); padding:14px 28px;
}
.page{padding:24px 28px 80px; max-width:1180px; width:100%}
h1.title{font-size:19px; font-weight:600; letter-spacing:-.02em}
.sub{color:var(--muted); font-size:13px; margin-top:2px}

/* ---------- search ---------- */
.searchrow{display:flex; gap:8px; align-items:center}
.searchwrap{position:relative; flex:1}
.searchwrap svg{position:absolute; left:12px; top:50%; transform:translateY(-50%); stroke:var(--faint)}
input.search{
  width:100%; font:inherit; font-size:14px; padding:10px 82px 10px 36px; color:var(--ink);
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  transition:border-color .12s, box-shadow .12s;
}
input.search::placeholder{color:var(--faint)}
input.search:focus{outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.kbd{
  position:absolute; right:10px; top:50%; transform:translateY(-50%);
  font-family:var(--mono); font-size:10.5px; color:var(--faint);
  border:1px solid var(--line); border-radius:4px; padding:2px 5px; background:var(--surface2);
}
.btn{
  border:1px solid var(--line); background:var(--surface); color:var(--ink);
  border-radius:var(--radius-sm); padding:8px 13px; font-size:13px; font-weight:500;
  transition:background .12s, border-color .12s;
}
.btn:hover{background:var(--surface2)}
.btn.primary{background:var(--ink); color:var(--bg); border-color:var(--ink)}
.btn.primary:hover{opacity:.88}
.btn.sm{padding:4px 9px; font-size:12px}
.btn.danger{color:var(--danger); border-color:color-mix(in srgb, var(--danger) 30%, var(--line))}
.btn.danger:hover{background:var(--danger-soft)}
.btn:disabled{opacity:.5; cursor:default}
.btn-row{display:flex; gap:6px; flex-wrap:wrap}

.examples{display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; align-items:center}
.examples em{color:var(--faint); font-style:normal; font-size:12px; margin-right:2px}
.chipbtn{
  border:1px solid var(--line); background:var(--surface); color:var(--ink2);
  border-radius:99px; padding:3px 11px; font-size:12px;
}
.chipbtn:hover{border-color:var(--accent); color:var(--accent); background:var(--accent-soft)}

/* ---------- filters ---------- */
.filters{margin-top:14px; border:1px solid var(--line); border-radius:var(--radius); background:var(--surface)}
.filters summary{
  list-style:none; cursor:pointer; padding:10px 14px; font-size:13px; font-weight:500;
  display:flex; align-items:center; gap:8px; color:var(--ink2);
}
.filters summary::-webkit-details-marker{display:none}
.filters summary .caret{transition:transform .15s}
.filters[open] summary .caret{transform:rotate(90deg)}
.filters summary .count{
  background:var(--accent); color:var(--accent-ink); border-radius:99px;
  font-size:10.5px; padding:1px 7px; font-variant-numeric:tabular-nums;
}
.fgrid{
  display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:12px 14px;
  padding:4px 14px 14px; border-top:1px solid var(--line2);
}
.fgrid label{display:flex; flex-direction:column; gap:4px; font-size:11.5px; color:var(--muted); font-weight:500}
.fgrid label.chk{flex-direction:row; align-items:center; gap:7px; font-size:13px; color:var(--ink2); padding-top:18px}
.fgrid input, .fgrid select{
  font:inherit; font-size:13px; padding:6px 8px; color:var(--ink);
  background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-sm);
}
.fgrid input:focus, .fgrid select:focus{outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.filter-actions{display:flex; gap:8px; padding:0 14px 14px}

/* ---------- results ---------- */
.meta{display:flex; align-items:center; justify-content:space-between; gap:12px; margin:20px 0 10px; flex-wrap:wrap}
.count{font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums}
.count b{color:var(--ink); font-weight:600}
.pills{display:flex; gap:5px; flex-wrap:wrap}
.pill{
  display:inline-flex; align-items:center; gap:5px; font-size:11.5px; padding:2px 9px;
  border-radius:99px; background:var(--surface2); color:var(--ink2); border:1px solid var(--line2);
}
.pill b{color:var(--muted); font-weight:500; font-size:10px; text-transform:uppercase; letter-spacing:.04em}
.pill.warn{background:var(--warn-soft); color:var(--warn); border-color:transparent}

.card{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden}
.tablewrap{overflow-x:auto}
table.list{width:100%; border-collapse:collapse; font-size:13.5px}
table.list thead th{
  text-align:left; font-size:11px; font-weight:600; color:var(--muted); letter-spacing:.03em;
  text-transform:uppercase; padding:9px 16px; background:var(--surface2);
  border-bottom:1px solid var(--line); position:sticky; top:0; white-space:nowrap;
}
table.list td{padding:11px 16px; border-top:1px solid var(--line2); vertical-align:top}
table.list tbody tr{cursor:pointer; transition:background .1s}
table.list tbody tr:hover{background:var(--surface2)}
table.list tbody tr:first-child td{border-top:none}
td.nm{font-weight:600; color:var(--ink); white-space:nowrap}
td.nm .id{display:block; font-family:var(--mono); font-size:10.5px; color:var(--faint); font-weight:400; margin-top:1px}
td.org{color:var(--ink2)}
td.org .sub2{font-size:11.5px; color:var(--faint); margin-top:2px}
td.sk{color:var(--muted); font-size:12.5px; max-width:340px}
td.num{font-variant-numeric:tabular-nums; text-align:right; color:var(--muted)}
.vote{white-space:nowrap}
.vbtn{background:none;border:1px solid var(--line);border-radius:6px;padding:2px 6px;
  margin-right:4px;cursor:pointer;color:var(--muted);line-height:1}
.vbtn:hover{border-color:var(--fg);color:var(--fg)}
.vbtn.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.vbtn.save.on{background:#0a66c2;border-color:#0a66c2;color:#fff}
.chipbtn.muted{color:var(--faint);border-style:dashed}
.ext{display:inline-flex;align-items:center;justify-content:center;margin-left:6px;
  width:18px;height:18px;border-radius:4px;text-decoration:none;vertical-align:middle;
  color:var(--muted);border:1px solid var(--line)}
.ext:hover{color:var(--fg);border-color:var(--fg)}
.ext.li:hover{color:#0a66c2;border-color:#0a66c2}
.livetag{display:inline-block;margin-left:8px;padding:1px 6px;border-radius:999px;
  font-size:10px;font-weight:600;letter-spacing:.02em;vertical-align:middle;
  background:var(--accent-soft,#e8f0fe);color:var(--accent,#1a56db)}
.srcpill{
  display:inline-block; font-family:var(--mono); font-size:10px; padding:1px 6px; margin:1px 3px 1px 0;
  border-radius:4px; background:var(--surface2); color:var(--muted); border:1px solid var(--line2);
}
.muted{color:var(--faint)}
.loadmore{padding:12px; text-align:center; border-top:1px solid var(--line2)}

/* ---------- states ---------- */
.empty{padding:56px 24px; text-align:center}
.empty .icon{width:38px; height:38px; margin:0 auto 12px; display:grid; place-items:center;
  border-radius:10px; background:var(--surface2); color:var(--faint)}
.empty h3{font-size:15px; font-weight:600; margin-bottom:4px}
.empty p{color:var(--muted); font-size:13px; max-width:420px; margin:0 auto 14px}
.loading{padding:44px; text-align:center; color:var(--muted); font-size:13px}
.spinner{
  width:18px; height:18px; border:2px solid var(--line); border-top-color:var(--accent);
  border-radius:50%; animation:spin .7s linear infinite; margin:0 auto 10px;
}
@keyframes spin{to{transform:rotate(360deg)}}
.banner{
  padding:10px 14px; border-radius:var(--radius-sm); font-size:13px; margin-bottom:14px;
  background:var(--danger-soft); color:var(--danger); border:1px solid transparent;
}
.banner.info{background:var(--accent-soft); color:var(--accent)}
.banner.warnbar{background:var(--warn-soft); color:var(--warn); display:flex; align-items:center; gap:6px; flex-wrap:wrap}
.banner.warnbar b{font-weight:600}

/* ---------- person ---------- */
.phead{display:flex; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:6px}
.phead h1{font-size:26px; font-weight:600; letter-spacing:-.025em; line-height:1.2}
.phead .role{color:var(--muted); font-size:14px; margin-top:3px}
.badges{display:flex; gap:6px; flex-wrap:wrap; margin-top:8px}
.badge{
  font-size:11px; font-weight:500; padding:2px 9px; border-radius:99px;
  background:var(--surface2); color:var(--ink2); border:1px solid var(--line2);
}
.badge.ok{background:var(--ok-soft); color:var(--ok); border-color:transparent}
.badge.warn{background:var(--warn-soft); color:var(--warn); border-color:transparent}
.idline{font-family:var(--mono); font-size:11px; color:var(--faint); margin-top:8px}
.idline.aka{font-family:var(--sans); font-size:12px; max-width:720px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.grid2{display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; align-items:start}
section.block{margin-top:20px}
section.block > h2{
  font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:.05em;
  color:var(--muted); margin-bottom:9px; display:flex; align-items:center; gap:7px;
}
section.block > h2 .n{background:var(--surface2); border-radius:99px; padding:0 7px; font-size:10.5px; color:var(--faint)}
.card .inner{padding:14px 16px}
table.data{width:100%; border-collapse:collapse; font-size:13px}
table.data th{
  text-align:left; font-size:10.5px; font-weight:600; text-transform:uppercase; letter-spacing:.04em;
  color:var(--faint); padding:0 12px 7px 0;
}
table.data td{padding:7px 12px 7px 0; border-top:1px solid var(--line2); vertical-align:top}
table.data tr:first-child td{border-top:none}
table.data td.num{text-align:right; padding-right:0; font-variant-numeric:tabular-nums}
.vstate{font-size:10px; padding:1px 7px; border-radius:99px; font-weight:500}
.vstate.corroborated{background:var(--ok-soft); color:var(--ok)}
.vstate.unverified{background:var(--surface2); color:var(--faint)}
.conflict{border:1px solid var(--line); border-left:3px solid var(--warn); border-radius:var(--radius-sm); padding:12px 14px; margin-bottom:8px; background:var(--surface)}
.conflict .ct{font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--warn); font-weight:600; margin-bottom:7px}
.vs{display:grid; grid-template-columns:1fr auto 1fr; gap:12px; align-items:center}
.vs .side b{display:block; font-size:13.5px; font-weight:600}
.vs .side span{font-size:11.5px; color:var(--faint)}
.vs .mid{color:var(--faint); font-size:11px}

/* ---------- network ---------- */
.net{border-radius:var(--radius); overflow:hidden; background:var(--surface2); position:relative}
.net svg{display:block; width:100%; height:auto}
.net text{font-family:var(--sans); font-size:9.5px; fill:var(--ink2); pointer-events:none}
.net .edge{stroke:var(--line); stroke-width:1.2}
.net .edge.org{stroke:var(--accent); stroke-dasharray:3 3; opacity:.5}
.net .n-person{fill:var(--surface); stroke:var(--muted); stroke-width:1.4; cursor:pointer; transition:fill .12s}
.net .n-person:hover{fill:var(--accent); stroke:var(--accent)}
.net .n-self{fill:var(--ink); stroke:var(--ink)}
.net .n-org{fill:var(--accent); stroke:none; opacity:.8}
.legend{position:absolute; bottom:8px; right:12px; font-size:10.5px; color:var(--faint)}

/* ---------- gate ---------- */
.gate{min-height:100vh; display:grid; place-items:center; padding:24px}
.gatebox{width:100%; max-width:380px; background:var(--surface); border:1px solid var(--line);
  border-radius:12px; box-shadow:var(--shadow); padding:28px}
.gatebox .mark{width:34px; height:34px; border-radius:9px; background:var(--ink); display:grid; place-items:center; margin-bottom:14px}
.gatebox .mark svg{stroke:var(--bg)}
.gatebox h1{font-size:18px; font-weight:600; margin-bottom:4px}
.gatebox p{color:var(--muted); font-size:13px; margin-bottom:16px}
.gatebox input{width:100%; font:inherit; padding:9px 11px; border:1px solid var(--line);
  border-radius:var(--radius-sm); background:var(--bg); color:var(--ink); margin-bottom:10px}
.gatebox input:focus{outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.gatebox .btn{width:100%; justify-content:center}

@media (max-width:860px){
  .shell{grid-template-columns:1fr}
  .rail{position:static; height:auto; flex-direction:row; align-items:center; overflow-x:auto; border-right:none; border-bottom:1px solid var(--line)}
  .brand{padding:12px 16px}
  nav{flex-direction:row; padding:8px}
  .rail-foot{display:none}
  .page, .topbar{padding-left:16px; padding-right:16px}
}
</style>
</head>
<body>
<div id="root"></div>

<script>
const $ = (s, r=document)=>r.querySelector(s);
const esc = (s)=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (n)=>(n??0).toLocaleString();

const ICON = {
  logo:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>',
  search:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M16 16l5 5"/></svg>',
  people:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="3.2"/><path d="M22 20v-2a4 4 0 0 0-3-3.87"/></svg>',
  review:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
  plug:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2v6M15 2v6"/><path d="M6 8h12v3a6 6 0 0 1-12 0z"/><path d="M12 17v5"/></svg>',
  caret:'<svg class="caret" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
  back:'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>',
  thumbUp:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M7 22V10l5-8a2.5 2.5 0 0 1 2.4 3.2L13.5 9H19a2.5 2.5 0 0 1 2.4 3.1l-1.7 7A2.5 2.5 0 0 1 17.3 22z"/><rect x="2" y="10" width="5" height="12" rx="1"/></svg>',
  thumbDown:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M17 2v12l-5 8a2.5 2.5 0 0 1-2.4-3.2l.9-3.8H5a2.5 2.5 0 0 1-2.4-3.1l1.7-7A2.5 2.5 0 0 1 6.7 2z"/><rect x="17" y="2" width="5" height="12" rx="1"/></svg>',
  bookmark:'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>',
  linkedin:'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5M2.5 9.5h5V21h-5zM10 9.5h4.7v1.6c.7-1.2 2-1.9 3.6-1.9 3 0 4.2 1.9 4.2 5.2V21h-5v-5.6c0-1.5-.5-2.4-1.8-2.4-1 0-1.6.7-1.9 1.4-.1.2-.1.6-.1.9V21h-5z"/></svg>',
  github:'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10 10 0 0 0 12 2"/></svg>',
  empty:'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M16 16l5 5"/></svg>',
};

/* ---------------- auth ---------------- */
const token = ()=>localStorage.getItem("seekr_token") || localStorage.getItem("rip_token") || "";
async function api(path, opts={}){
  const res = await fetch(path, {...opts, headers:{...(opts.headers||{}), "Authorization":"Bearer "+token()}});
  if(res.status===401){ renderGate(); throw new Error("unauthorized"); }
  if(!res.ok){
    let detail = "request failed ("+res.status+")";
    try{ const j = await res.json(); if(j.detail) detail = typeof j.detail==="string"?j.detail:JSON.stringify(j.detail); }catch(e){}
    throw new Error(detail);
  }
  return res.json();
}
function renderGate(){
  $("#root").innerHTML = `<div class="gate"><div class="gatebox">
    <div class="mark">${ICON.logo}</div>
    <h1>Sign in to Seekr</h1>
    <p>Paste the API token (RIP_API_TOKEN). It is stored only in this browser.</p>
    <input id="tok" type="password" placeholder="Token" autocomplete="off" autofocus>
    <button class="btn primary" onclick="saveToken()">Continue</button>
  </div></div>`;
  $("#tok").addEventListener("keydown", e=>{ if(e.key==="Enter") saveToken(); });
}
function saveToken(){ localStorage.setItem("seekr_token", $("#tok").value.trim()); route(); }
function signOut(){ localStorage.removeItem("seekr_token"); localStorage.removeItem("rip_token"); renderGate(); }

/* ---------------- shell ---------------- */
const NAV = [
  ["#/search", "Search", ICON.search],
  ["#/shortlists", "Shortlists", ICON.bookmark],
  ["#/review", "Review", ICON.review],
  ["#/sources", "Sources", ICON.plug],
];
function shell(active, topbar, body){
  $("#root").innerHTML = `<div class="shell">
    <aside class="rail">
      <div class="brand">
        <div class="mark">${ICON.logo}</div>
        <div><b>Seekr</b><span>people graph</span></div>
      </div>
      <nav>${NAV.map(([href,label,icon])=>
        `<a href="${href}" class="${active===href?"active":""}">${icon}${label}</a>`).join("")}</nav>
      <div class="rail-foot" id="railstats">
        <button class="themebtn" onclick="toggleTheme()">Toggle theme</button>
        <button class="themebtn" onclick="signOut()">Sign out</button>
      </div>
    </aside>
    <main>
      <div class="topbar">${topbar}</div>
      <div class="page" id="page">${body}</div>
    </main>
  </div>`;
  loadRailStats();
}
function toggleTheme(){
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur==="dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("seekr_theme", next);
}
(function(){ const t=localStorage.getItem("seekr_theme"); if(t) document.documentElement.setAttribute("data-theme",t); })();

async function loadRailStats(){
  const el = $("#railstats"); if(!el) return;
  try{
    const [sources, countries] = await Promise.all([
      api("/v1/facets?field=source"), api("/v1/facets?field=country&limit=200"),
    ]);
    const people = sources.values.reduce((m,v)=>Math.max(m,v.people),0);
    el.insertAdjacentHTML("afterbegin",
      `<div class="stat"><span>People</span><b>${fmt(people)}</b></div>
       <div class="stat"><span>Sources</span><b>${sources.values.length}</b></div>
       <div class="stat"><span>Countries</span><b>${countries.values.length}</b></div>`);
  }catch(e){}
}

/* ---------------- search ---------------- */
const EXAMPLES = [
  "machine learning at University of Toronto",
  "deep learning, top 20",
  "product designers at Swiggy",
];
const FIELDS = {
  f_country:"country", f_source:"source", f_org:"organization",
  f_curorg:"current_organization", f_edu:"education", f_role:"role",
  f_skill:"skill", f_tech:"technology", f_loc:"location",
  f_pubs:"min_publications", f_cites:"min_citations", f_active:"active_since",
  f_srcs:"min_sources", f_sort:"sort",
};
let PAGE = {mode:"query", q:"", offset:0, rows:[]};

function searchTopbar(q){
  return `<div class="searchrow">
    <div class="searchwrap">
      ${ICON.search}
      <input class="search" id="q" placeholder="Search people, skills, organizations…" value="${esc(q||"")}">
      <span class="kbd">/</span>
    </div>
    <button class="btn primary" onclick="runQuery()">Search</button>
    <button class="btn" onclick="runQuery('true')" title="Also query live sources">Live</button>
  </div>`;
}

/* ---------------- recent searches ---------------- */
const RECENT_KEY = "seekr_recent";
const recent = ()=>{ try{ return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; }catch(e){ return []; } };
function rememberQuery(q){
  const list = [q, ...recent().filter(x=>x!==q)].slice(0, 8);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list));
}
function paintRecent(){
  const box = $("#recent"); if(!box) return;
  const list = recent();
  box.hidden = !list.length;
  box.innerHTML = `<em>Recent</em>` + list.map(x=>
    `<button class="chipbtn" onclick="useExample(this)">${esc(x)}</button>`).join("")
    + (list.length ? `<button class="chipbtn muted" onclick="clearRecent()">clear</button>` : "");
}
function clearRecent(){ localStorage.removeItem(RECENT_KEY); paintRecent(); }

/* Trending is drawn from the corpus itself — the roles and skills most people
   in Seekr actually carry, refreshed from /v1/facets on every visit. It
   reflects this graph, not an outside market index. */
async function paintTrending(){
  const box = $("#trending"); if(!box) return;
  try{
    // Roles only. Skills skew to whatever the corpus happens to hold — the
    // top ones today are particle physics topics, which is not a job anyone
    // searches for. Job titles are what people actually look for.
    const roles = await api("/v1/facets?field=role&limit=8");
    const chips = (roles.values||roles.facets||[])
      .map(v=>v.value).filter(Boolean).slice(0,7);
    if(chips.length) box.innerHTML = `<em>Trending</em>` + chips.map(x=>
      `<button class="chipbtn" onclick="useExample(this)">${esc(x)}</button>`).join("");
  }catch(e){ /* keep the static examples if facets are unavailable */ }
}

async function renderSearch(){
  const last = sessionStorage.getItem("seekr_q") || "";
  shell("#/search", searchTopbar(last), `
    <div class="examples" id="trending"><em>Trending</em>${EXAMPLES.map(x=>
      `<button class="chipbtn" onclick="useExample(this)">${esc(x)}</button>`).join("")}</div>
    <div class="examples" id="recent" hidden><em>Recent</em></div>
    <details class="filters" id="filterbox">
      <summary>${ICON.caret} Filters <span class="count" id="fcount" hidden>0</span></summary>
      <div class="fgrid">
        <label>Country<select id="f_country"><option value="">Any</option></select></label>
        <label>Source<select id="f_source"><option value="">Any</option></select></label>
        <label>Organization<input id="f_org" placeholder="Ever affiliated"></label>
        <label>Current employer<input id="f_curorg" placeholder="Present only"></label>
        <label>Studied at<input id="f_edu" placeholder="University"></label>
        <label>Role<input id="f_role" placeholder="e.g. professor"></label>
        <label>Skill<input id="f_skill" placeholder="e.g. nlp"></label>
        <label>Technology<input id="f_tech" placeholder="e.g. rust"></label>
        <label>Location<input id="f_loc" placeholder="City or region"></label>
        <label>Min publications<input id="f_pubs" type="number" min="0" placeholder="0"></label>
        <label>Min citations<input id="f_cites" type="number" min="0" placeholder="0"></label>
        <label>Active since<input id="f_active" placeholder="YYYY"></label>
        <label>Min sources<input id="f_srcs" type="number" min="1" placeholder="1"></label>
        <label>Sort<select id="f_sort">
          <option value="relevance">Default order</option>
          <option value="recent">Recently updated</option>
          <option value="name">Name A–Z</option></select></label>
        <label class="chk"><input type="checkbox" id="f_cv"> Has CV</label>
        <label class="chk"><input type="checkbox" id="f_email"> Has email</label>
      </div>
      <div class="filter-actions">
        <button class="btn primary" onclick="runFilters()">Apply filters</button>
        <button class="btn" onclick="clearFilters()">Clear</button>
      </div>
    </details>
    <div id="results"></div>`);
  bindSearchKeys();
  loadFacets();
  paintRecent();
  paintTrending();
  if(last) runQuery();
}
function useExample(el){ $("#q").value = el.textContent; runQuery(); }
function bindSearchKeys(){
  const q = $("#q");
  q.addEventListener("keydown", e=>{
    if(e.key==="Enter") runQuery();
    if(e.key==="Escape"){ q.value=""; q.blur(); }
  });
  document.addEventListener("keydown", e=>{
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if((e.key==="/" && !typing) || ((e.metaKey||e.ctrlKey) && e.key==="k")){
      e.preventDefault(); $("#q")?.focus(); $("#q")?.select();
    }
  });
}
async function loadFacets(){
  for(const [id, field] of [["f_country","country"],["f_source","source"]]){
    try{
      const d = await api("/v1/facets?field="+field+"&limit=100");
      const el = $("#"+id); if(!el) continue;
      el.innerHTML = `<option value="">Any</option>` + d.values.map(v=>
        `<option value="${esc(v.value)}">${esc(v.value)} · ${fmt(v.people)}</option>`).join("");
    }catch(e){}
  }
}
function filterParams(){
  const p = new URLSearchParams();
  for(const [id, name] of Object.entries(FIELDS)){
    const el = $("#"+id);
    if(el && el.value && el.value !== "relevance") p.set(name, el.value);
  }
  if($("#f_cv")?.checked) p.set("has_cv","true");
  if($("#f_email")?.checked) p.set("has_email","true");
  return p;
}
function syncFilterCount(){
  const n = [...filterParams().keys()].length;
  const badge = $("#fcount"); if(!badge) return;
  badge.textContent = n; badge.hidden = n===0;
}
function clearFilters(){
  Object.keys(FIELDS).forEach(id=>{ const e=$("#"+id); if(e) e.value=""; });
  ["f_cv","f_email"].forEach(id=>{ const e=$("#"+id); if(e) e.checked=false; });
  const s=$("#f_sort"); if(s) s.value="relevance";
  syncFilterCount();
  $("#results").innerHTML = "";
}

function busy(msg){ $("#results").innerHTML = `<div class="loading"><div class="spinner"></div>${esc(msg)}</div>`; }

async function runQuery(discover, offset){
  const q = $("#q").value.trim(); if(!q) return;
  sessionStorage.setItem("seekr_q", q);
  rememberQuery(q);
  paintRecent();
  const paging = typeof offset === "number" && offset > 0;
  if(!paging){ PAGE = {mode:"query", q, offset:0, rows:[]}; busy(discover?"Querying live sources…":"Searching…"); }
  try{
    const data = await api("/v1/query?q="+encodeURIComponent(q)
      + (paging?"&offset="+offset:"") + (discover?"&discover="+discover:""));
    renderResults(data, {discover});
  }catch(e){ if(e.message!=="unauthorized") $("#results").innerHTML = `<div class="banner">${esc(e.message)}</div>`; }
}
async function runFilters(offset){
  syncFilterCount();
  const params = filterParams();
  const q = $("#q").value.trim();
  if(q) params.set("q", q);
  const paging = typeof offset === "number" && offset > 0;
  if(!paging){ PAGE = {mode:"filters", q, offset:0, rows:[]}; busy("Filtering…"); }
  if(paging) params.set("offset", offset);
  params.set("limit", 50);
  try{ renderResults(await api("/v1/persons?"+params.toString()), {filtered:true}); }
  catch(e){ if(e.message!=="unauthorized") $("#results").innerHTML = `<div class="banner">${esc(e.message)}</div>`; }
}
function loadMore(){
  const b = $("#more"); if(b){ b.disabled = true; b.textContent = "Loading…"; }
  return PAGE.mode==="filters" ? runFilters(PAGE.offset) : runQuery(null, PAGE.offset);
}

function renderResults(data, opts={}){
  const f = data.applied_filters;
  const pills = f ? [
    ...(f.skills||[]).map(s=>`<span class="pill"><b>skill</b>${esc(s)}</span>`),
    ...(f.skill_patterns||[]).map(s=>`<span class="pill"><b>matches</b>${esc(s)}</span>`),
    ...(f.organizations||[]).map(o=>`<span class="pill"><b>org</b>${esc(o)}</span>`),
    ...(f.locations||[]).map(l=>`<span class="pill"><b>place</b>${esc(l)}</span>`),
    ...(f.countries||[]).map(c=>`<span class="pill"><b>country</b>${esc(c)}</span>`),
    ...(f.name_terms||[]).map(n=>`<span class="pill"><b>name</b>${esc(n)}</span>`),
  ].join("") : "";
  const um = data.unmatched_terms||[];
  const unmatched = um.length
    ? `<span class="pill warn">not applied: ${um.map(esc).join(", ")}</span>` : "";

  const rows = data.results.map(p=>{
    const skills = (p.attributes||[])
      .filter(a=>a.attribute_type==="skill"||a.attribute_type==="research_interest")
      .slice(0,3).map(a=>esc(a.value)).join(", ");
    const srcs = [...new Set((p.attributes||[]).flatMap(a=>a.sources||[]))];
    const primary = p.matched_organization || p.current_organization || "";
    const others = (p.organizations||[]).filter(o=>o!==primary);
    const orgSub = [
      p.matched_organization && p.current_organization && p.current_organization!==primary
        ? "now: "+esc(p.current_organization) : "",
      others.length ? "+"+others.length+" more" : "",
    ].filter(Boolean).join(" · ");
    // fetched live for this query rather than already in the corpus
    const liveTag = p.from_live_search ? '<span class="livetag">new</span>' : "";
    // Verified links only — never a guessed profile URL. This replaces the
    // record id, which was shown to nobody's benefit.
    const urls = p.profile_urls || [];
    const li = urls.find(u=>/linkedin\.com/i.test(u));
    const gh = urls.find(u=>/github\.com/i.test(u));
    const links = [
      li ? `<a class="ext li" href="${esc(li)}" target="_blank" rel="noopener noreferrer"
        title="LinkedIn profile" onclick="event.stopPropagation()">${ICON.linkedin}</a>` : "",
      gh ? `<a class="ext gh" href="${esc(gh)}" target="_blank" rel="noopener noreferrer"
        title="GitHub profile" onclick="event.stopPropagation()">${ICON.github}</a>` : "",
    ].join("");
    return `<tr onclick="location.hash='#/person/${p.id}'">
      <td class="nm">${esc(p.canonical_name||"Unnamed")}${liveTag}${links}</td>
      <td class="org">${primary?esc(primary):'<span class="muted">—</span>'}
        ${orgSub?`<div class="sub2">${orgSub}</div>`:""}</td>
      <td class="org">${esc(p.location||"")||'<span class="muted">—</span>'}</td>
      <td class="sk">${skills||'<span class="muted">—</span>'}</td>
      <td>${srcs.length?srcs.map(s=>`<span class="srcpill">${esc(s)}</span>`).join(""):'<span class="muted">—</span>'}</td>
      <td class="vote" onclick="event.stopPropagation()">
        <button class="vbtn" title="Good match for this query"
          onclick="vote('${p.id}','good',this)">${ICON.thumbUp}</button>
        <button class="vbtn" title="Bad match for this query"
          onclick="vote('${p.id}','bad',this)">${ICON.thumbDown}</button>
        <button class="vbtn save" title="Save to a shortlist"
          onclick="saveTo('${p.id}',this)">${ICON.bookmark}</button>
      </td>
    </tr>`;
  });
  PAGE.rows = PAGE.rows.concat(rows);
  PAGE.offset = data.next_offset ?? PAGE.rows.length;

  const total = data.total_matches ?? PAGE.rows.length;
  // A dropped constraint must be loud: results that silently ignore
  // "in Hyderabad" read as wrong answers rather than a coverage gap.
  // A corrected spelling must be visible, or the answer quietly belongs to a
  // different question than the one that was asked.
  const corr = data.corrections || [];
  const corrBanner = corr.length ? `
    <div class="banner">Showing results for ${corr.map(c=>
      `<b>${esc(c.matched)}</b>`).join(", ")} — you typed ${corr.map(c=>
      `<i>${esc(c.typed)}</i>`).join(", ")}.</div>` : "";
  // the deployed snapshot cannot be written to, so live finds are not kept
  const roBanner = (data.storage === "read-only" && data.stored_from_live === 0
                    && (data.discovery_suggestions||[]).length) ? `
    <div class="banner warnbar">This deployment reads a fixed snapshot, so people
      found live are shown but not saved. Point <code>RIP_DATABASE_URL</code> at a
      writable database to let the graph grow here.</div>` : "";
  const unmatchedBanner = um.length ? `
    <div class="banner warnbar">
      <b>${um.map(esc).join(", ")}</b> ${um.length===1?"was":"were"} not applied —
      nothing in Seekr matches ${um.length===1?"that term":"those terms"} yet${
        PAGE.rows.length
          ? `, so these ${fmt(total)} results ignore ${um.length===1?"it":"them"}`
          : ""}.
      <button class="btn sm" onclick="runQuery('true')">Search paid sources too</button>
    </div>` : "";
  const sugg = data.discovery_suggestions || [];
  const suggBlock = sugg.length ? `
    <section class="block"><h2>Live candidates <span class="n">${sugg.length}</span></h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Name</th><th>Affiliation</th><th>Role &amp; place</th><th>Source</th><th></th></tr></thead>
        <tbody>${sugg.map(x=>`<tr>
          <td class="nm">${esc(x.name||"Unnamed")}</td>
          <td class="org">${esc(x.affiliation||"")||'<span class="muted">—</span>'}</td>
          <td class="sk">${esc([x.role,x.location].filter(Boolean).join(" · "))||'<span class="muted">—</span>'}</td>
          <td><span class="srcpill">${esc(x.source)}</span></td>
          <td class="num"><button class="btn sm" onclick="event.stopPropagation();queueOne('${esc(x.source)}','${esc(x.external_id)}',this)">Add</button></td>
        </tr>`).join("")}</tbody></table></div></div></section>` : "";

  let main;
  if(PAGE.rows.length){
    main = `<div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Name</th><th>Organization</th><th>Location</th><th>Skills &amp; interests</th><th>Sources</th><th title="Tell the ranking tool whether this fits your query">Match</th></tr></thead>
        <tbody>${PAGE.rows.join("")}</tbody></table></div>
      ${data.has_more?`<div class="loadmore"><button class="btn" id="more" onclick="loadMore()">Load 50 more</button></div>`:""}
      </div>`;
  } else if(data.matched_nothing){
    main = emptyState("No filters could be applied",
      data.explanation || "None of those terms exist in the corpus yet.",
      !opts.discover ? `<button class="btn primary" onclick="runQuery('true')">Search live sources</button>` : "");
  } else if(!sugg.length){
    const why = data.empty_reason;
    main = emptyState("No matches",
      why ? why.message : "No one in the corpus matches these filters.",
      !opts.discover ? `<button class="btn primary" onclick="runQuery('true')">Search live sources</button>` : "");
  } else { main = ""; }

  $("#results").innerHTML = `
    <div class="meta">
      <div class="count">${PAGE.rows.length?`<b>${fmt(PAGE.rows.length)}</b> of ${fmt(total)} matching`:""}</div>
      <div class="pills">${pills}${unmatched}</div>
    </div>
    ${corrBanner}${roBanner}${unmatchedBanner}${main}${suggBlock}`;
}
function emptyState(title, body, action){
  return `<div class="card"><div class="empty">
    <div class="icon">${ICON.empty}</div>
    <h3>${esc(title)}</h3><p>${esc(body)}</p>${action||""}
  </div></div>`;
}
// Feedback is recorded against the query it was judged on. It is NOT used to
// reorder anything here — Seekr does not rank. It is training data for the
// separate ranking tool, readable at GET /v1/feedback.
async function vote(personId, verdict, btn){
  const cell = btn.parentElement;
  cell.querySelectorAll(".vbtn").forEach(b=>b.classList.remove("on"));
  btn.classList.add("on");
  try{
    await api("/v1/feedback", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({person_id: personId, verdict, query: PAGE.q || ""})});
    btn.title = "Recorded";
  }catch(e){ btn.classList.remove("on"); btn.title = "Could not record: "+e.message; }
}

/* ---------------- shortlists ---------------- */
async function saveTo(personId, btn){
  let lists = {shortlists: []};
  try{ lists = await api("/v1/shortlists"); }catch(e){ }
  const names = lists.shortlists.map(l=>l.name);
  const prompt_ = names.length
    ? `Save to which shortlist?\n\nExisting: ${names.join(", ")}\n\nType a name (new or existing):`
    : "Name your first shortlist:";
  const name = window.prompt(prompt_, names[0] || "Shortlist");
  if(!name) return;
  btn.disabled = true;
  try{
    const sl = await api("/v1/shortlists", {method:"POST",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify({name})});
    const r = await api(`/v1/shortlists/${sl.id}/members`, {method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({person_id: personId, query: PAGE.q || ""})});
    btn.classList.add("on");
    btn.title = r.added ? `Saved to ${sl.name}` : `Already on ${sl.name}`;
  }catch(e){ btn.title = "Could not save: "+e.message; btn.disabled = false; }
}

async function renderShortlists(){
  shell("#/shortlists", null, `<div class="loading"><div class="spinner"></div>Loading shortlists…</div>`);
  let data;
  try{ data = await api("/v1/shortlists"); }
  catch(e){ $("#results") && ($("#results").innerHTML = esc(e.message)); return; }
  if(!data.shortlists.length){
    shell("#/shortlists", null, `<div class="empty">${ICON.empty}
      <p>No shortlists yet. Save someone from a search to start one.</p></div>`);
    return;
  }
  const blocks = await Promise.all(data.shortlists.map(l=>api(`/v1/shortlists/${l.id}`)));
  shell("#/shortlists", null, blocks.map(b=>`
    <section class="block"><h2>${esc(b.name)} <span class="n">${b.count}</span></h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Name</th><th>Found by</th><th>Added</th><th></th></tr></thead>
        <tbody>${b.members.map(m=>`<tr onclick="location.hash='#/person/${m.person_id}'">
          <td class="nm">${esc(m.canonical_name||"Unnamed")}</td>
          <td class="sk">${esc(m.found_by_query||"")||'<span class="muted">—</span>'}</td>
          <td class="org">${esc(String(m.added_at||"").slice(0,10))}</td>
          <td class="num"><button class="btn sm" onclick="event.stopPropagation();
            unsave(${b.id},'${m.person_id}',this)">Remove</button></td>
        </tr>`).join("")}</tbody></table></div></div></section>`).join(""));
}

async function unsave(listId, personId, btn){
  btn.disabled = true;
  try{
    await api(`/v1/shortlists/${listId}/members/${personId}`, {method:"DELETE"});
    btn.closest("tr").remove();
  }catch(e){ btn.textContent = "Failed"; btn.disabled = false; }
}

async function queueOne(source, externalId, btn){
  btn.disabled = true; btn.textContent = "Adding…";
  try{
    const r = await api("/v1/leads", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({source, external_id: externalId, reason:"queued from Seekr UI"})});
    btn.textContent = r.status==="queued" ? "Queued" : r.status.replace(/_/g," ");
  }catch(e){ btn.textContent = "Failed"; btn.disabled = false; }
}

/* ---------------- person ---------------- */
async function renderPerson(id){
  shell(null, `<a class="btn sm" href="#/search">${ICON.back} Back to results</a>`,
    `<div class="loading"><div class="spinner"></div>Loading profile…</div>`);
  let p, ev, pubs, projs, orgs, prov, conf, graph, docs;
  try{
    [p, ev, pubs, projs, orgs, prov, conf, graph, docs] = await Promise.all([
      api("/v1/persons/"+id), api("/v1/persons/"+id+"/evidence"),
      api("/v1/persons/"+id+"/publications"), api("/v1/persons/"+id+"/projects"),
      api("/v1/persons/"+id+"/organizations"), api("/v1/persons/"+id+"/provenance"),
      api("/v1/persons/"+id+"/conflicts"), api("/v1/persons/"+id+"/graph"),
      api("/v1/persons/"+id+"/documents"),
    ]);
  }catch(e){
    if(e.message!=="unauthorized") $("#page").innerHTML = `<div class="banner">${esc(e.message)}</div>`;
    return;
  }
  const attrs = (p.attributes||[]).sort((a,b)=>b.evidence_count-a.evidence_count);
  const corroborated = attrs.some(a=>a.evidence_count>1);
  const disputed = (conf.conflicts||[]).filter(c=>c.status==="active").length;

  $("#page").innerHTML = `
    ${p.merged_into?`<div class="banner info">This record was merged; showing the canonical profile.</div>`:""}
    <div class="phead">
      <div style="flex:1; min-width:240px">
        <h1>${esc(p.canonical_name||"Unnamed")}</h1>
        <div class="role">${esc([p.current_role,p.current_organization,p.location].filter(Boolean).join(" · "))||"&nbsp;"}</div>
        <div class="badges">
          ${corroborated?`<span class="badge ok">Corroborated</span>`:""}
          ${disputed?`<span class="badge warn">${disputed} disputed</span>`:""}
          <span class="badge">${prov.sources.length} source${prov.sources.length===1?"":"s"}</span>
          ${p.country?`<span class="badge">${esc(p.country)}</span>`:""}
        </div>
        ${p.aliases?.length?`<div class="idline aka" title="${esc(p.aliases.join(" · "))}">also ${esc(p.aliases.slice(0,5).join(" · "))}${p.aliases.length>5?` +${p.aliases.length-5} more`:""}</div>`:""}
        <div class="idline">${esc(p.id)} · updated ${esc((p.updated_at||"").slice(0,10))}</div>
      </div>
    </div>

    <div class="grid2">
      <section class="block"><h2>Attributes <span class="n">${attrs.length}</span></h2>
        <div class="card"><div class="inner"><table class="data">
          <tr><th>Type</th><th>Value</th><th class="num">Sources</th></tr>
          ${attrs.slice(0,40).map(a=>`<tr>
            <td class="muted">${esc(a.attribute_type)}</td>
            <td>${esc(a.value)}<div class="idline">${a.sources.map(esc).join(", ")}</div></td>
            <td class="num">${a.evidence_count}</td></tr>`).join("")
            || `<tr><td class="muted">No attributes yet</td></tr>`}
        </table></div></div></section>

      <section class="block"><h2>Affiliations <span class="n">${orgs.affiliations.length}</span></h2>
        <div class="card"><div class="inner"><table class="data">
          <tr><th>Organization</th><th>Role</th><th>Period</th></tr>
          ${orgs.affiliations.map(a=>`<tr>
            <td>${esc(a.organization)}<div class="idline">${esc(a.relation)}</div></td>
            <td>${esc(a.role||"—")}</td>
            <td class="muted">${esc([a.start_date,a.end_date].filter(Boolean).join("–")||(a.is_current?"current":"—"))}</td>
          </tr>`).join("") || `<tr><td class="muted">None recorded</td></tr>`}
        </table></div></div></section>
    </div>

    ${disputed?`<section class="block"><h2>Disputed facts <span class="n">${conf.conflicts.length}</span></h2>
      ${conf.conflicts.map(c=>`<div class="conflict">
        <div class="ct">${esc(c.attribute)}</div>
        <div class="vs">
          <div class="side"><b>${esc(c.side_a.value)}</b><span>per ${esc(c.side_a.source||"unknown")}</span></div>
          <div class="mid">vs</div>
          <div class="side"><b>${esc(c.side_b.value)}</b><span>per ${esc(c.side_b.source||"unknown")}</span></div>
        </div></div>`).join("")}</section>`:""}

    <section class="block"><h2>Links &amp; documents</h2>
      <div class="card"><div class="inner">
        ${docs.cvs.length?`<table class="data">
          <tr><th>CV / résumé</th><th>Found on</th></tr>
          ${docs.cvs.map(c=>`<tr>
            <td><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)}</a></td>
            <td class="muted">${esc(c.evidence||c.found_on||"")}</td></tr>`).join("")}</table>`
          : `<p class="muted" style="font-size:13px">No published CV found. Seekr only links documents a person or their institution publishes.</p>`}
        ${docs.profiles.length?`<table class="data" style="margin-top:12px">
          <tr><th>Profile</th><th>Type</th></tr>
          ${docs.profiles.map(pf=>`<tr>
            <td><a href="${esc(pf.url)}" target="_blank" rel="noopener">${esc(pf.url)}</a></td>
            <td class="muted">${esc(pf.kind)}</td></tr>`).join("")}</table>`:""}
      </div></div></section>

    ${pubs.publications.length?`<section class="block"><h2>Publications <span class="n">${pubs.publications.length}</span></h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Title</th><th>Venue</th><th>Year</th><th class="num">Citations</th></tr></thead>
        <tbody>${pubs.publications.slice(0,30).map(w=>`<tr>
          <td>${w.url?`<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a>`:esc(w.title)}</td>
          <td class="muted">${esc(w.venue||"—")}</td>
          <td class="muted">${esc((w.published_date||"").slice(0,4))}</td>
          <td class="num">${w.citations??"—"}</td></tr>`).join("")}</tbody>
      </table></div></div></section>`:""}

    ${projs.projects.length?`<section class="block"><h2>Projects <span class="n">${projs.projects.length}</span></h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Name</th><th>Tech</th><th>Activity</th><th>Last active</th></tr></thead>
        <tbody>${projs.projects.map(x=>`<tr>
          <td>${x.url?`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>`:esc(x.name)}</td>
          <td class="muted">${(x.technologies||[]).map(esc).join(", ")||"—"}</td>
          <td class="muted">${esc(Object.entries(x.activity||{}).map(([k,v])=>k+" "+v).join(" · "))||"—"}</td>
          <td class="muted">${esc(x.last_active_at||"—")}</td></tr>`).join("")}</tbody>
      </table></div></div></section>`:""}

    ${graph.edges.length?`<section class="block"><h2>Network <span class="n">${graph.nodes.length-1}</span></h2>
      <div class="card"><div class="net" id="net"><svg id="netsvg"></svg>
        <span class="legend">■ organization · ● co-author</span></div></div></section>`:""}

    <section class="block"><h2>Provenance <span class="n">${prov.sources.length}</span></h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Source</th><th>Record</th><th>Matched by</th><th>Review</th><th>Seen</th></tr></thead>
        <tbody>${prov.sources.map(s=>`<tr>
          <td><span class="srcpill">${esc(s.source)}</span></td>
          <td>${s.url?`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.external_id)}</a>`:esc(s.external_id)}</td>
          <td class="muted">${esc(s.match_signals?.reason||s.match_method)}</td>
          <td>${s.review_state==="approved"?`<span class="vstate corroborated">approved</span>`
              :`<span class="vstate unverified">${esc(s.review_state||"unreviewed")}</span>`}</td>
          <td class="muted">${esc((s.last_observed||"").slice(0,10))}</td></tr>`).join("")}</tbody>
      </table></div></div></section>`;
  if(graph.edges.length) drawNetwork(graph, p.id);
}

/* radial layout with label-box separation; no external library */
const MAX_LABEL = 20;
function drawNetwork(graph, selfId){
  const svg = $("#netsvg"); if(!svg) return;
  const others = graph.nodes.filter(n=>n.id!==selfId);
  const rings = Math.max(1, Math.ceil(others.length/9));
  const W = 900, H = Math.min(700, 280 + rings*115), cx = W/2, cy = H/2;
  const label = (s)=> (s||"").length>MAX_LABEL ? s.slice(0,MAX_LABEL-1)+"…" : (s||"");
  const halfW = (s)=> Math.max(24, label(s).length*3.1 + 8);
  const nodes = graph.nodes.map(n=>{
    if(n.id===selfId) return {...n, x:cx, y:cy, fixed:true};
    const k = others.indexOf(n), ring = k % rings;
    const a = (k/Math.max(1,others.length))*Math.PI*2 - Math.PI/2;
    const base = n.type==="organization" ? 92 : 148 + ring*112;
    return {...n, x:cx+Math.cos(a)*base*(W/H)*0.78, y:cy+Math.sin(a)*base*0.72};
  });
  for(let pass=0; pass<160; pass++){
    for(const a of nodes){
      if(a.fixed) continue;
      for(const b of nodes){
        if(a===b) continue;
        const needX = halfW(a.label)+halfW(b.label)+10, needY = 30;
        const dx=a.x-b.x, dy=a.y-b.y;
        if(Math.abs(dx)<needX && Math.abs(dy)<needY){
          if(Math.abs(dx)/needX > Math.abs(dy)/needY) a.x += (needX-Math.abs(dx))*0.22*(dx<0?-1:1);
          else a.y += (needY-Math.abs(dy))*0.5*(dy<0?-1:1);
        }
      }
      a.x = Math.max(halfW(a.label)+6, Math.min(W-halfW(a.label)-6, a.x));
      a.y = Math.max(24, Math.min(H-14, a.y));
    }
  }
  const byId = Object.fromEntries(nodes.map(n=>[n.id,n]));
  const edges = graph.edges.map(e=>{
    const a=byId[e.from], b=byId[e.to]; if(!a||!b) return "";
    const t = e.type==="coauthor" ? `${e.shared_publications} shared publication(s)` : esc(e.type);
    return `<line class="edge${e.type==="coauthor"?"":" org"}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${t}</title></line>`;
  }).join("");
  const marks = nodes.map(n=>{
    const text = esc(label(n.label)), dy = n.y<cy ? -11 : 17;
    if(n.type==="organization")
      return `<g><rect class="n-org" x="${n.x-5}" y="${n.y-5}" width="10" height="10" rx="2"><title>${esc(n.label)}</title></rect>
        <text x="${n.x}" y="${n.y+dy}" text-anchor="middle">${text}</text></g>`;
    const cls = n.id===selfId ? "n-person n-self" : "n-person";
    const click = n.id===selfId ? "" : ` onclick="location.hash='#/person/${n.id}'" style="cursor:pointer"`;
    return `<g${click}><circle class="${cls}" cx="${n.x}" cy="${n.y}" r="${n.id===selfId?8:5.5}"><title>${esc(n.label)}</title></circle>
      <text x="${n.x}" y="${n.y+dy}" text-anchor="middle">${text}</text></g>`;
  }).join("");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = edges + marks;
}

/* ---------------- review ---------------- */
async function renderReview(){
  shell("#/review", `<h1 class="title">Review queue</h1>
    <div class="sub">Merges Seekr was not confident enough to make on its own. Every decision is reversible.</div>`,
    `<div class="loading"><div class="spinner"></div>Loading queue…</div>`);
  let r;
  try{ r = await api("/v1/review/merges"); }
  catch(e){ if(e.message!=="unauthorized") $("#page").innerHTML = `<div class="banner">${esc(e.message)}</div>`; return; }
  const dup = r.possible_duplicates||[], fuz = r.fuzzy_merges||[];

  $("#page").innerHTML = `
    <section class="block"><h2>Possible duplicates <span class="n">${dup.length}</span></h2>
      ${dup.length ? dup.map(d=>`<div class="conflict">
        <div class="vs">
          <div class="side"><b><a href="#/person/${d.person_id}">${esc(d.person_name)}</a></b></div>
          <div class="mid">same person?</div>
          <div class="side"><b><a href="#/person/${d.duplicate_person_id}">${esc(d.duplicate_person_name)}</a></b></div>
        </div>
        <div class="idline">${esc(d.signals?.reason||("score "+d.score))}</div>
        <div class="btn-row" style="margin-top:10px">
          <button class="btn primary sm" onclick="act('/v1/review/duplicates/${d.candidate_id}/merge')">Merge</button>
          <button class="btn danger sm" onclick="act('/v1/review/duplicates/${d.candidate_id}/reject')">Different people</button>
        </div></div>`).join("")
      : emptyState("Nothing to review", "No duplicate pairs are waiting.")}
    </section>
    <section class="block"><h2>Fuzzy merges awaiting confirmation <span class="n">${fuz.length}</span></h2>
      ${fuz.length ? fuz.map(f=>`<div class="conflict">
        <div><b><a href="#/person/${f.person_id}">${esc(f.person_name)}</a></b>
          <span class="muted">← ${esc(f.source)}:${esc(f.external_id)} (${esc(f.record_name||"")})</span></div>
        <div class="idline">${esc(f.signals?.reason||f.match_method)}</div>
        <div class="btn-row" style="margin-top:10px">
          <button class="btn primary sm" onclick="act('/v1/review/merges/${f.link_id}/approve')">Approve</button>
          <button class="btn danger sm" onclick="act('/v1/review/merges/${f.link_id}/split')">Split apart</button>
        </div></div>`).join("")
      : emptyState("All confirmed", "No fuzzy merges are waiting for a decision.")}
    </section>`;
}
async function act(path){
  try{ await api(path,{method:"POST"}); renderReview(); }
  catch(e){ alert(e.message); }
}

/* ---------------- sources ---------------- */
async function renderSources(){
  shell("#/sources", `<h1 class="title">Sources</h1>
    <div class="sub">Where the data comes from, and whether ingestion is healthy.</div>`,
    `<div class="loading"><div class="spinner"></div>Loading…</div>`);
  let facets, health, hooks;
  try{
    [facets, health, hooks] = await Promise.all([
      api("/v1/facets?field=source"), api("/v1/health/sources"),
      api("/v1/webhooks/health").catch(()=>null),
    ]);
  }catch(e){ if(e.message!=="unauthorized") $("#page").innerHTML = `<div class="banner">${esc(e.message)}</div>`; return; }

  const runs = {};
  (health.sources||[]).forEach(s=>{
    runs[s.source] = runs[s.source] || {ok:0, error:0, last:null};
    runs[s.source][s.status==="ok"?"ok":"error"] += s.runs;
    if(s.last_finished_at) runs[s.source].last = s.last_finished_at;
  });

  $("#page").innerHTML = `
    <section class="block"><h2>Coverage</h2>
      <div class="card"><div class="tablewrap"><table class="list">
        <thead><tr><th>Source</th><th class="num">People</th><th class="num">Runs OK</th><th class="num">Failed</th><th>Last run</th></tr></thead>
        <tbody>${facets.values.map(v=>{
          const r = runs[v.value]||{ok:0,error:0,last:null};
          return `<tr><td class="nm">${esc(v.value)}</td>
            <td class="num">${fmt(v.people)}</td>
            <td class="num">${fmt(r.ok)}</td>
            <td class="num">${r.error?`<span style="color:var(--danger)">${fmt(r.error)}</span>`:"0"}</td>
            <td class="muted">${esc((r.last||"").slice(0,16).replace("T"," "))||"—"}</td></tr>`;
        }).join("")}</tbody>
      </table></div></div></section>
    ${hooks?`<section class="block"><h2>Webhook delivery</h2>
      <div class="card"><div class="inner"><table class="data">
        <tr><td>Active subscriptions</td><td class="num">${fmt(hooks.active_subscriptions)}</td></tr>
        <tr><td>Pending</td><td class="num">${hooks.pending?`<span style="color:var(--warn)">${fmt(hooks.pending)}</span>`:"0"}</td></tr>
        <tr><td>Delivered</td><td class="num">${fmt(hooks.delivered)}</td></tr>
        <tr><td>Failed</td><td class="num">${hooks.failed?`<span style="color:var(--danger)">${fmt(hooks.failed)}</span>`:"0"}</td></tr>
      </table>${hooks.pending?`<p class="muted" style="font-size:12.5px;margin-top:10px">Deliveries only send when <code>deliver-webhooks</code> runs.</p>`:""}
      </div></div></section>`:""}`;
}

/* ---------------- router ---------------- */
async function route(){
  if(!token()) return renderGate();
  const h = location.hash || "#/search";
  try{
    if(h.startsWith("#/person/")) await renderPerson(h.split("/")[2]);
    else if(h==="#/shortlists") await renderShortlists();
    else if(h==="#/review") await renderReview();
    else if(h==="#/sources") await renderSources();
    else await renderSearch();
  }catch(e){
    if(e.message!=="unauthorized"){
      const page = $("#page");
      if(page) page.innerHTML = `<div class="banner">${esc(e.message)}</div>`;
    }
  }
}
window.addEventListener("hashchange", route);
route();
</script>
</body>
</html>
"""

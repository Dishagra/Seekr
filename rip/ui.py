"""Internal exploration UI, served at /ui.

One self-contained page (hash-routed) in the style of an archival card
catalog / research dossier. Talks to the /v1 API with a bearer token the
operator pastes once (stored in localStorage). Exploration and debugging
only — no ranking anywhere.
"""

UI_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seekr</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#f6f2e8; --paper2:#efe9db; --ink:#231f18; --faint:#8c8272;
  --rule:#d8cfba; --accent:#8a2f1d; --accent2:#274156; --ok:#3d6b35;
  --stamp:#8a2f1d; --card:#fbf8f0;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Mono",monospace; font-size:14px; line-height:1.55;
  background-image:radial-gradient(ellipse at 20% -10%, rgba(138,47,29,.05), transparent 50%),
    repeating-linear-gradient(0deg, transparent 0 31px, rgba(140,130,114,.07) 31px 32px);
  min-height:100vh;
}
a{color:var(--accent2)}
header{
  border-bottom:3px double var(--rule); padding:26px 32px 18px;
  display:flex; align-items:baseline; gap:24px; flex-wrap:wrap;
}
header h1{
  font-family:"Fraunces",serif; font-weight:900; font-size:30px; letter-spacing:-.5px;
}
header h1 .no{color:var(--accent); font-size:16px; vertical-align:super; margin-left:4px}
nav{display:flex; gap:2px; margin-left:auto}
nav a{
  text-decoration:none; color:var(--ink); padding:6px 14px; font-size:12px;
  text-transform:uppercase; letter-spacing:.12em; border:1px solid transparent;
}
nav a.active{border:1px solid var(--ink); background:var(--card); box-shadow:2px 2px 0 var(--rule)}
main{max-width:1060px; margin:0 auto; padding:34px 32px 90px}
.tagline{color:var(--faint); font-size:12px; letter-spacing:.08em; text-transform:uppercase}

/* search */
.searchbar{display:flex; gap:0; margin:8px 0 10px}
.searchbar input{
  flex:1; font:inherit; padding:13px 16px; background:var(--card); color:var(--ink);
  border:1.5px solid var(--ink); border-right:none; outline:none;
}
.searchbar input:focus{box-shadow:3px 3px 0 var(--rule)}
.searchbar button{
  font:inherit; font-weight:600; letter-spacing:.1em; text-transform:uppercase; font-size:12px;
  padding:0 22px; background:var(--ink); color:var(--paper); border:1.5px solid var(--ink); cursor:pointer;
}
.searchbar button:hover{background:var(--accent)}
.searchbar button.live{background:var(--card); color:var(--ink); border-left:none}
.searchbar button.live:hover{background:var(--accent2); color:var(--paper)}
.hints{color:var(--faint); font-size:12px; margin-bottom:22px}
.hints code{cursor:pointer; text-decoration:underline dotted; margin-right:12px}
.filterline{margin:14px 0 4px; font-size:12px}
.chip{
  display:inline-block; border:1px solid var(--ink); background:var(--card);
  padding:1px 9px; margin:2px 6px 2px 0; font-size:11px;
}
.chip b{color:var(--accent); font-weight:500; text-transform:uppercase; font-size:9px; letter-spacing:.1em; margin-right:5px}
.warn{color:var(--accent); font-size:12px; margin:6px 0 0}

/* results list */
.results{margin-top:22px; background:var(--card); border:1px solid var(--ink); box-shadow:3px 3px 0 var(--rule)}
table.list{width:100%; border-collapse:collapse; font-size:13px}
table.list thead th{
  font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:var(--faint);
  font-weight:500; text-align:left; padding:10px 14px; border-bottom:1.5px solid var(--ink);
  background:var(--paper2); position:sticky; top:0;
}
table.list td{padding:9px 14px; border-top:1px solid var(--rule); vertical-align:top}
table.list tbody tr{cursor:pointer}
table.list tbody tr:hover{background:var(--paper2)}
table.list tbody tr:hover td.nm{color:var(--accent)}
td.nm{font-family:"Fraunces",serif; font-weight:600; font-size:15px; white-space:nowrap}
td.org, td.loc{color:var(--ink)}
td.sk{color:var(--accent2); font-size:12px}
td.src{font-size:10px; letter-spacing:.06em; color:var(--faint); text-transform:uppercase; white-space:nowrap}
td.num{font-variant-numeric:tabular-nums; text-align:right; color:var(--faint); font-size:12px}
.muted{color:var(--faint)}
.sub{font-size:10.5px; color:var(--faint); margin-top:2px}
.filters{border:1px solid var(--rule); background:var(--card); padding:10px 14px; margin-bottom:6px}
.filters summary{cursor:pointer; font-size:11px; letter-spacing:.16em; text-transform:uppercase; color:var(--accent)}
.fgrid{display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:10px 14px; margin-top:12px}
.fgrid label{display:flex; flex-direction:column; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--faint); gap:3px}
.fgrid label.chk{flex-direction:row; align-items:center; gap:6px; text-transform:none; letter-spacing:0; font-size:12px; color:var(--ink)}
.fgrid input, .fgrid select{font:inherit; font-size:12.5px; padding:5px 7px; border:1px solid var(--rule); background:var(--paper); color:var(--ink)}
.fgrid input:focus, .fgrid select:focus{outline:none; border-color:var(--ink)}
.resultcount{font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint); margin:16px 0 0}

/* dossier */
.dossier{background:var(--card); border:1px solid var(--ink); box-shadow:4px 4px 0 var(--rule); padding:30px 34px}
.dossier h2{font-family:"Fraunces",serif; font-weight:900; font-size:34px; letter-spacing:-.5px}
.dossier .aka{color:var(--faint); font-size:12px; margin:2px 0 4px}
.dossier .meta{font-size:12px; color:var(--faint); margin-bottom:4px}
.stamp{
  display:inline-block; border:2px solid var(--stamp); color:var(--stamp); border-radius:3px;
  padding:1px 8px; font-size:10px; font-weight:600; letter-spacing:.18em; text-transform:uppercase;
  transform:rotate(-2deg); margin-left:10px; vertical-align:middle; opacity:.85;
}
.stamp.ok{border-color:var(--ok); color:var(--ok)}
section.block{margin-top:30px}
section.block>h4{
  font-size:11px; letter-spacing:.22em; text-transform:uppercase; color:var(--accent);
  border-bottom:1px solid var(--rule); padding-bottom:5px; margin-bottom:12px;
}
table{width:100%; border-collapse:collapse; font-size:12.5px}
th{
  text-align:left; font-size:10px; letter-spacing:.15em; text-transform:uppercase;
  color:var(--faint); font-weight:500; padding:4px 10px 4px 0;
}
td{padding:5px 10px 5px 0; border-top:1px solid var(--rule); vertical-align:top}
td.num{font-variant-numeric:tabular-nums; text-align:right; padding-right:18px}
.vstate{font-size:9px; letter-spacing:.12em; text-transform:uppercase; padding:1px 6px; border:1px solid}
.vstate.corroborated{color:var(--ok); border-color:var(--ok)}
.vstate.unverified{color:var(--faint); border-color:var(--faint)}
.conflict{border:1px solid var(--accent); background:rgba(138,47,29,.04); padding:12px 14px; margin-bottom:10px; font-size:12.5px}
.conflict .vs{display:grid; grid-template-columns:1fr 30px 1fr; align-items:center; gap:6px}
.conflict .vs span.v{font-weight:600}
.conflict .vs .m{text-align:center; color:var(--accent); font-family:"Fraunces",serif; font-style:italic}
.conflict .src{color:var(--faint); font-size:11px}
/* network panel */
.net{border:1px solid var(--rule); background:var(--paper2); position:relative; overflow:hidden}
.net svg{display:block; width:100%; height:auto}
.net .legend{position:absolute; bottom:6px; right:10px; font-size:10px; color:var(--faint); letter-spacing:.08em}
.net text{font-family:"IBM Plex Mono",monospace; font-size:9.5px; fill:var(--ink); pointer-events:none}
.net .edge{stroke:var(--rule); stroke-width:1}
.net .edge.org{stroke:var(--accent2); stroke-dasharray:3 3}
.net .n-person{fill:var(--card); stroke:var(--ink); stroke-width:1.2; cursor:pointer}
.net .n-person:hover{fill:var(--accent); stroke:var(--accent)}
.net .n-self{fill:var(--ink); stroke:var(--ink)}
.net .n-org{fill:var(--accent2); stroke:var(--accent2); opacity:.75}
.btn{
  font:inherit; font-size:11px; letter-spacing:.1em; text-transform:uppercase; cursor:pointer;
  border:1px solid var(--ink); background:var(--card); padding:4px 12px; margin-right:8px;
}
.btn:hover{background:var(--ink); color:var(--paper)}
.btn.danger:hover{background:var(--accent); border-color:var(--accent)}
.back{font-size:12px; display:inline-block; margin-bottom:18px}
.empty{color:var(--faint); font-style:italic; padding:30px 0; text-align:center; font-family:"Fraunces",serif; font-size:17px}
.loading{color:var(--faint); padding:40px 0; text-align:center; letter-spacing:.2em; text-transform:uppercase; font-size:11px}

/* token modal */
.tokenbox{
  max-width:520px; margin:80px auto; background:var(--card); border:1.5px solid var(--ink);
  box-shadow:5px 5px 0 var(--rule); padding:34px;
}
.tokenbox h2{font-family:"Fraunces",serif; font-size:24px; margin-bottom:8px}
.tokenbox p{font-size:12px; color:var(--faint); margin-bottom:16px}
.tokenbox input{width:100%; font:inherit; padding:10px 12px; border:1.5px solid var(--ink); background:var(--paper); margin-bottom:14px}
footer{border-top:1px solid var(--rule); color:var(--faint); font-size:11px; padding:14px 32px; letter-spacing:.06em}
@media (max-width:700px){ main{padding:20px 16px 70px} header{padding:18px 16px 12px} .dossier{padding:20px 18px} }
</style>
</head>
<body>
<header>
  <h1>Seekr</h1>
  <span class="tagline">evidence-backed people graph · worldwide · no ranking</span>
  <nav id="nav">
    <a href="#/search">Search</a>
    <a href="#/review">Review</a>
    <a href="#/health">Sources</a>
  </nav>
</header>
<main id="app"><div class="loading">opening Seekr…</div></main>
<footer>Every claim traceable to its source · conflicting records preserved, never overwritten</footer>
<script>
const $ = (s)=>document.querySelector(s);
const app = $("#app");
const esc = (s)=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function token(){ return localStorage.getItem("rip_token") || ""; }
async function api(path, opts={}){
  const res = await fetch(path, {...opts, headers:{...(opts.headers||{}), "Authorization":"Bearer "+token()}});
  if(res.status===401){ renderToken(); throw new Error("unauthorized"); }
  if(!res.ok) throw new Error("API "+res.status);
  return res.json();
}

function renderToken(){
  app.innerHTML = `<div class="tokenbox">
    <h2>Seekr access</h2>
    <p>Paste the API bearer token (RIP_API_TOKEN). Stored only in this browser.</p>
    <input id="tok" type="password" placeholder="token…" autofocus>
    <button class="btn" onclick="saveToken()">Enter</button>
  </div>`;
  $("#tok").addEventListener("keydown",e=>{ if(e.key==="Enter") saveToken(); });
}
function saveToken(){ localStorage.setItem("rip_token", $("#tok").value.trim()); route(); }

/* ---------- search ---------- */
async function renderSearch(){
  setNav("#/search");
  const last = sessionStorage.getItem("last_q") || "";
  app.innerHTML = `
    <div class="searchbar">
      <input id="q" placeholder="e.g. distributed systems researchers at University of Toronto, top 10" value="${esc(last)}">
      <button onclick="runSearch()">Consult</button>
      <button class="live" onclick="runSearch('true')" title="also query OpenAlex, Semantic Scholar and dblp live">Search live</button>
    </div>
    <div class="hints">try:
      <code onclick="fillQ(this)">deep learning at University of Toronto</code>
      <code onclick="fillQ(this)">machine learning, top 20</code>
      <code onclick="fillQ(this)">neural networks researchers in Toronto</code>
    </div>
    <details class="filters" id="filterbox">
      <summary>Filters</summary>
      <div class="fgrid">
        <label>Country<select id="f_country"><option value="">any</option></select></label>
        <label>Source<select id="f_source"><option value="">any</option></select></label>
        <label>Organization<input id="f_org" placeholder="any affiliation"></label>
        <label>Current employer<input id="f_curorg" placeholder="present only"></label>
        <label>Studied at<input id="f_edu" placeholder="university"></label>
        <label>Role / title<input id="f_role" placeholder="e.g. professor"></label>
        <label>Skill<input id="f_skill" placeholder="e.g. nlp"></label>
        <label>Technology<input id="f_tech" placeholder="e.g. rust"></label>
        <label>Location<input id="f_loc" placeholder="city / region"></label>
        <label>Min publications<input id="f_pubs" type="number" min="0" placeholder="0"></label>
        <label>Min citations<input id="f_cites" type="number" min="0" placeholder="0"></label>
        <label>Active since<input id="f_active" placeholder="YYYY"></label>
        <label>Min sources<input id="f_srcs" type="number" min="1" placeholder="1"></label>
        <label>Sort<select id="f_sort">
          <option value="relevance">insertion order</option>
          <option value="recent">recently updated</option>
          <option value="name">name A–Z</option></select></label>
        <label class="chk"><input type="checkbox" id="f_cv"> has CV / résumé</label>
        <label class="chk"><input type="checkbox" id="f_email"> has public email</label>
      </div>
      <div style="margin-top:10px">
        <button class="btn" onclick="runFilters()">Apply filters</button>
        <button class="btn" onclick="clearFilters()">Clear</button>
      </div>
    </details>
    <div id="results"></div>`;
  loadFacets();
  $("#q").addEventListener("keydown",e=>{ if(e.key==="Enter") runSearch(); });
  if(last) runSearch();
}
function fillQ(el){ $("#q").value = el.textContent; runSearch(); }

const FILTER_FIELDS = {
  f_country:"country", f_source:"source", f_org:"organization",
  f_curorg:"current_organization", f_edu:"education", f_role:"role",
  f_skill:"skill", f_tech:"technology", f_loc:"location",
  f_pubs:"min_publications", f_cites:"min_citations", f_active:"active_since",
  f_srcs:"min_sources", f_sort:"sort",
};
function filterParams(){
  const p = new URLSearchParams();
  for(const [id, name] of Object.entries(FILTER_FIELDS)){
    const el = document.getElementById(id);
    if(el && el.value && el.value !== "relevance") p.set(name, el.value);
  }
  if(document.getElementById("f_cv")?.checked) p.set("has_cv","true");
  if(document.getElementById("f_email")?.checked) p.set("has_email","true");
  return p;
}
function anyFilter(){ return [...filterParams().keys()].length > 0; }
function clearFilters(){
  Object.keys(FILTER_FIELDS).forEach(id=>{ const e=document.getElementById(id); if(e) e.value=""; });
  ["f_cv","f_email"].forEach(id=>{ const e=document.getElementById(id); if(e) e.checked=false; });
  const s=document.getElementById("f_sort"); if(s) s.value="relevance";
  runFilters();
}
async function loadFacets(){
  for(const [id, field] of [["f_country","country"],["f_source","source"]]){
    try{
      const d = await api("/v1/facets?field="+field);
      const el = document.getElementById(id);
      if(!el) continue;
      el.innerHTML = `<option value="">any</option>` + d.values.map(v=>
        `<option value="${esc(v.value)}">${esc(v.value)} (${v.people.toLocaleString()})</option>`).join("");
    }catch(e){}
  }
}
async function runFilters(offset){
  const params = filterParams();
  const q = $("#q").value.trim();
  if(q) params.set("q", q);
  const paging = typeof offset === "number" && offset > 0;
  if(!paging){ PAGE = {q:"__filters__", offset:0, rows:[]}; $("#results").innerHTML = `<div class="loading">filtering…</div>`; }
  if(paging) params.set("offset", offset);
  params.set("limit", 50);
  try{
    const data = await api("/v1/persons?"+params.toString());
    renderRows(data, {filtered:true});
  }catch(e){ $("#results").innerHTML = `<div class="warn">filter failed: ${esc(e.message)}</div>`; }
}
let PAGE = {q:"", offset:0, rows:[]};
async function loadMore(){
  const btn = document.getElementById("more");
  if(btn){ btn.disabled = true; btn.textContent = "loading…"; }
  await runSearch(null, PAGE.offset);
}
async function runSearch(discover, offset){
  const q = $("#q").value.trim(); if(!q) return;
  sessionStorage.setItem("last_q", q);
  const paging = typeof offset === "number" && offset > 0 && q === PAGE.q;
  if(!paging){ PAGE = {q, offset:0, rows:[]}; }
  if(!paging) $("#results").innerHTML = `<div class="loading">${discover?"querying live sources…":"consulting the index…"}</div>`;
  try{
    const data = await api("/v1/query?q="+encodeURIComponent(q)
      + (paging ? "&offset="+offset : "")
      + (discover ? "&discover="+discover : ""));
    const f = data.applied_filters;
    const chips = [
      ...f.skills.map(s=>`<span class="chip"><b>skill</b>${esc(s)}</span>`),
      ...f.organizations.map(o=>`<span class="chip"><b>org</b>${esc(o)}</span>`),
      ...f.locations.map(l=>`<span class="chip"><b>place</b>${esc(l)}</span>`),
      ...f.name_terms.map(n=>`<span class="chip"><b>name</b>${esc(n)}</span>`),
      `<span class="chip"><b>limit</b>${f.limit}</span>`,
    ].join("");
    const warn = data.unmatched_terms.length
      ? `<div class="warn">⚠ not applied (unknown to the archive): ${data.unmatched_terms.map(esc).join(", ")}</div>` : "";
    renderRows(data, {});
    return;
  }catch(e){ if(e.message!=="unauthorized") $("#results").innerHTML = `<div class="warn">query failed: ${esc(e.message)}</div>`; }
}

function renderRows(data, opts){
    const chips = (data.applied_filters ? [
      ...(data.applied_filters.skills||[]).map(s=>`<span class="chip"><b>skill</b>${esc(s)}</span>`),
      ...(data.applied_filters.skill_patterns||[]).map(s=>`<span class="chip"><b>matches</b>${esc(s)}</span>`),
      ...(data.applied_filters.organizations||[]).map(o=>`<span class="chip"><b>org</b>${esc(o)}</span>`),
      ...(data.applied_filters.locations||[]).map(l=>`<span class="chip"><b>place</b>${esc(l)}</span>`),
      ...(data.applied_filters.name_terms||[]).map(n=>`<span class="chip"><b>name</b>${esc(n)}</span>`),
    ].join("") : "");
    const warn = (data.unmatched_terms||[]).length
      ? `<div class="warn">⚠ not applied (unknown to Seekr): ${data.unmatched_terms.map(esc).join(", ")}</div>` : "";
    const pageRows = data.results.map(p=>{
      const skills = (p.attributes||[])
        .filter(a=>a.attribute_type==="skill"||a.attribute_type==="research_interest")
        .slice(0,3).map(a=>esc(a.value)).join(", ");
      const srcs = [...new Set((p.attributes||[]).flatMap(a=>a.sources||[]))];
      // show the affiliation that matched the filter; the current one is
      // often different, which otherwise reads as a wrong result
      const primary = p.matched_organization || p.current_organization || "";
      const others = (p.organizations||[]).filter(o=>o!==primary);
      const orgCell = primary
        ? `${esc(primary)}${p.matched_organization && p.current_organization && p.current_organization!==primary
            ? `<div class="sub">now: ${esc(p.current_organization)}</div>` : ""}`
          + (others.length ? `<div class="sub">+${others.length} more</div>` : "")
        : '<span class="muted">—</span>';
      return `<tr onclick="location.hash='#/person/${p.id}'">
        <td class="nm">${esc(p.canonical_name||"(unnamed)")}</td>
        <td class="org">${orgCell}</td>
        <td class="loc">${esc(p.location||"")||'<span class="muted">—</span>'}</td>
        <td class="sk">${skills||'<span class="muted">—</span>'}</td>
        <td class="src">${srcs.length?esc(srcs.join(" ")):'<span class="muted">—</span>'}</td>
      </tr>`;
    });
    // accumulate across pages so "Load more" appends instead of replacing
    PAGE.rows = PAGE.rows.concat(pageRows);
    PAGE.offset = (data.next_offset ?? PAGE.rows.length);
    const rows = PAGE.rows.join("");
    const filtered = opts && opts.filtered;

    const nothing = data.matched_nothing
      ? `<div class="empty">${esc(data.explanation||"No filter could be applied.")}</div>`
      : `<div class="empty">No one matches these filters.</div>`;

    const sugg = data.discovery_suggestions || [];
    const suggBlock = sugg.length ? `
      <div class="resultcount">${sugg.length} live candidates — not indexed yet</div>
      <div class="results"><table class="list">
        <thead><tr><th>Name</th><th>Affiliation</th><th>Source</th><th>Works</th><th>Add</th></tr></thead>
        <tbody>${sugg.map(x=>`<tr>
          <td class="nm">${esc(x.name||"(unnamed)")}</td>
          <td class="org">${esc(x.affiliation||"")||'<span class="muted">—</span>'}</td>
          <td class="src">${esc(x.source)}</td>
          <td class="num">${x.works_count??"—"}</td>
          <td><button class="btn" onclick="queueOne('${esc(x.source)}','${esc(x.external_id)}',this)">Queue</button></td>
        </tr>`).join("")}</tbody></table></div>` : "";

    const offerLive = (!data.count && !sugg.length && !discover)
      ? `<div class="empty">Nothing indexed yet.
           <button class="btn" style="margin-left:10px" onclick="runSearch('true')">Search live sources</button></div>`
      : "";

    $("#results").innerHTML = `
      <div class="filterline">${chips}</div>${warn}
      ${offerLive}
      ${data.count || PAGE.rows.length ? `<div class="resultcount">showing ${PAGE.rows.length} of ${(data.total_matches??PAGE.rows.length).toLocaleString()} matching records</div>
        <div class="results"><table class="list">
          <thead><tr><th>Name</th><th>Organization</th><th>Location</th>
            <th>Skills &amp; interests</th><th>Sources</th></tr></thead>
          <tbody>${rows}</tbody></table></div>
        ${data.has_more ? `<div style="text-align:center;margin-top:14px">
          <button class="btn" id="more" onclick="${filtered?`runFilters(${PAGE.offset})`:"loadMore()"}">Load 50 more</button></div>` : ""}`
      : (offerLive ? "" : nothing)}
      ${suggBlock}`;
}

/* ---------- person dossier ---------- */
async function queueOne(source, externalId, btn){
  btn.disabled = true; btn.textContent = "queuing…";
  try{
    const r = await api("/v1/leads", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({source, external_id: externalId, reason:"queued from UI live search"}),
    });
    btn.textContent = r.status === "queued" ? "queued" : r.status.replace("_"," ");
  }catch(e){ btn.textContent = "failed"; btn.disabled = false; }
}

async function renderPerson(id){
  setNav(null);
  app.innerHTML = `<div class="loading">retrieving dossier…</div>`;
  const [p, ev, pubs, projs, orgs, prov, conf, graph] = await Promise.all([
    api("/v1/persons/"+id), api("/v1/persons/"+id+"/evidence"),
    api("/v1/persons/"+id+"/publications"), api("/v1/persons/"+id+"/projects"),
    api("/v1/persons/"+id+"/organizations"), api("/v1/persons/"+id+"/provenance"),
    api("/v1/persons/"+id+"/conflicts"), api("/v1/persons/"+id+"/graph"),
  ]);
  const docs = await api("/v1/persons/"+id+"/documents");
  const merged = p.merged_into ? `<div class="warn">⚠ this record was merged; showing canonical dossier ${esc(p.id)}</div>` : "";
  const attrs = (p.attributes||[]).sort((a,b)=>b.evidence_count-a.evidence_count);
  app.innerHTML = `
    <a class="back" href="#/search">← back to results</a>${merged}
    <div class="dossier">
      <h2>${esc(p.canonical_name||"(unnamed)")}
        ${attrs.some(a=>a.evidence_count>1)?'<span class="stamp ok">corroborated</span>':""}
        ${conf.conflicts.filter(c=>c.status==="active").length?'<span class="stamp">disputed</span>':""}
      </h2>
      <div class="aka">${p.aliases?.length? "also recorded as: "+p.aliases.map(esc).join(" · "):""}</div>
      <div class="meta">${esc([p.current_role,p.current_organization,p.location].filter(Boolean).join(" · "))}</div>
      <div class="meta">file ${esc(p.id)} · updated ${esc((p.updated_at||"").slice(0,10))}</div>

      <section class="block"><h4>Attributes · evidence-backed</h4>
        <table><tr><th>type</th><th>value</th><th style="text-align:right">evidence</th><th>attested by</th></tr>
        ${attrs.map(a=>`<tr><td>${esc(a.attribute_type)}</td><td>${esc(a.value)}</td>
          <td class="num">${a.evidence_count}</td><td>${a.sources.map(esc).join(", ")}</td></tr>`).join("")}
        </table></section>

      ${conf.conflicts.length?`<section class="block"><h4>Disputed records</h4>
        ${conf.conflicts.map(c=>`<div class="conflict">
          <div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--accent);margin-bottom:6px">${esc(c.attribute)} · ${esc(c.status)}</div>
          <div class="vs"><span><span class="v">${esc(c.side_a.value)}</span><div class="src">per ${esc(c.side_a.source||"unknown")}</div></span>
          <span class="m">vs</span>
          <span><span class="v">${esc(c.side_b.value)}</span><div class="src">per ${esc(c.side_b.source||"unknown")}</div></span></div>
        </div>`).join("")}</section>`:""}

      ${orgs.affiliations.length?`<section class="block"><h4>Affiliations</h4>
        <table><tr><th>organization</th><th>relation</th><th>role</th><th>period</th></tr>
        ${orgs.affiliations.map(a=>`<tr><td>${esc(a.organization)}</td><td>${esc(a.relation)}</td>
          <td>${esc(a.role||"—")}</td><td>${esc([a.start_date,a.end_date].filter(Boolean).join("–")||(a.is_current?"current":"—"))}</td></tr>`).join("")}
        </table></section>`:""}

      ${pubs.publications.length?`<section class="block"><h4>Publications · ${pubs.publications.length}</h4>
        <table><tr><th>title</th><th>venue</th><th>year</th><th style="text-align:right">citations</th></tr>
        ${pubs.publications.slice(0,40).map(w=>`<tr><td>${w.url?`<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a>`:esc(w.title)}</td>
          <td>${esc(w.venue||"—")}</td><td>${esc((w.published_date||"").slice(0,4))}</td><td class="num">${w.citations??"—"}</td></tr>`).join("")}
        </table>${pubs.publications.length>40?`<div class="meta" style="margin-top:6px">…and ${pubs.publications.length-40} more</div>`:""}</section>`:""}

      ${projs.projects.length?`<section class="block"><h4>Projects</h4>
        <table><tr><th>name</th><th>tech</th><th>activity</th><th>last active</th></tr>
        ${projs.projects.map(x=>`<tr><td>${x.url?`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>`:esc(x.name)}</td>
          <td>${(x.technologies||[]).map(esc).join(", ")}</td>
          <td>${esc(Object.entries(x.activity||{}).map(([k,v])=>k+" "+v).join(" · "))}</td>
          <td>${esc(x.last_active_at||"—")}</td></tr>`).join("")}
        </table></section>`:""}

      <section class="block"><h4>Links &amp; documents</h4>
        ${docs.cvs.length ? `<table><tr><th>CV / résumé</th><th>found on</th><th>confidence</th></tr>
          ${docs.cvs.map(c=>`<tr>
            <td><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)}</a></td>
            <td><a href="${esc(c.found_on||"")}" target="_blank" rel="noopener">${esc(c.found_on||"—")}</a>
                <div class="sub">${esc(c.evidence||"")}</div></td>
            <td class="num">${c.confidence}</td></tr>`).join("")}</table>`
          : `<div class="sub" style="margin-bottom:10px">No published CV found. Seekr only links documents a person or institution publishes; it never creates one.</div>`}
        ${docs.profiles.length ? `<table style="margin-top:12px"><tr><th>profile</th><th>type</th></tr>
          ${docs.profiles.map(pf=>`<tr>
            <td><a href="${esc(pf.url)}" target="_blank" rel="noopener">${esc(pf.url)}</a></td>
            <td>${esc(pf.kind)}</td></tr>`).join("")}</table>` : ""}
      </section>

      ${graph.edges.length?`<section class="block"><h4>Network · ${graph.nodes.length-1} connections</h4>
        <div class="net" id="net"><svg id="netsvg"></svg>
        <span class="legend">■ organization · ● co-author · click to open</span></div></section>`:""}

      <section class="block"><h4>Provenance · where this file came from</h4>
        <table><tr><th>source</th><th>external id</th><th>attached by</th><th>confidence</th><th>last observed</th></tr>
        ${prov.sources.map(s=>`<tr><td>${esc(s.source)}</td>
          <td>${s.url?`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.external_id)}</a>`:esc(s.external_id)}</td>
          <td>${esc(s.match_signals?.reason||s.match_method)}</td><td class="num">${s.match_confidence}</td>
          <td>${esc((s.last_observed||"").slice(0,10))}</td></tr>`).join("")}
        </table></section>
    </div>`;
  if(graph.edges.length) drawNetwork(graph, id);
}

/* radial layout with label-box separation; no external library.
   Labels are wide and short, so nodes are separated as boxes rather than
   circles — otherwise names collide even when the dots don't. */
const MAX_LABEL = 20;
function drawNetwork(graph, selfId){
  const svg = document.getElementById("netsvg");
  if(!svg) return;
  const others = graph.nodes.filter(n=>n.id!==selfId);
  const rings = Math.ceil(others.length/9);
  // fixed viewBox: CSS scales it to the container, so text stays proportional
  const W = 900;
  const H = Math.min(720, 300 + rings*120);
  const cx = W/2, cy = H/2;

  const label = (s)=> (s||"").length>MAX_LABEL ? s.slice(0,MAX_LABEL-1)+"…" : (s||"");
  const halfW = (s)=> Math.max(24, label(s).length*3.1 + 8);  // label half-width
  const nodes = graph.nodes.map(n=>{
    if(n.id===selfId) return {...n, x:cx, y:cy, fixed:true};
    const k = others.indexOf(n);
    const ring = k % rings;
    const a = (k/Math.max(1,others.length))*Math.PI*2 - Math.PI/2;
    const base = n.type==="organization" ? 96 : 150 + ring*118;
    return {...n, x:cx+Math.cos(a)*base*(W/H)*0.78, y:cy+Math.sin(a)*base*0.72};
  });

  for(let pass=0; pass<160; pass++){
    for(const a of nodes){
      if(a.fixed) continue;
      for(const b of nodes){
        if(a===b) continue;
        const needX = halfW(a.label)+halfW(b.label)+10, needY = 30;
        const dx = a.x-b.x, dy = a.y-b.y;
        if(Math.abs(dx) < needX && Math.abs(dy) < needY){
          const pushX = (needX-Math.abs(dx))*0.22*(dx<0?-1:1);
          const pushY = (needY-Math.abs(dy))*0.5*(dy<0?-1:1);
          if(Math.abs(dx)/needX > Math.abs(dy)/needY) a.x += pushX; else a.y += pushY;
        }
      }
      a.x = Math.max(halfW(a.label)+6, Math.min(W-halfW(a.label)-6, a.x));
      a.y = Math.max(24, Math.min(H-14, a.y));
    }
  }

  const byId = Object.fromEntries(nodes.map(n=>[n.id,n]));
  const edges = graph.edges.map(e=>{
    const a=byId[e.from], b=byId[e.to];
    if(!a||!b) return "";
    const cls = e.type==="coauthor" ? "edge" : "edge org";
    const title = e.type==="coauthor"
      ? `${e.shared_publications} shared publication(s)` : esc(e.type);
    return `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${title}</title></line>`;
  }).join("");
  const marks = nodes.map(n=>{
    const text = esc(label(n.label));
    const dy = n.y < cy ? -12 : 18;  // label above upper nodes, below lower ones
    if(n.type==="organization")
      return `<g><rect class="n-org" x="${n.x-6}" y="${n.y-6}" width="12" height="12"><title>${esc(n.label)}</title></rect>
        <text x="${n.x}" y="${n.y+dy}" text-anchor="middle">${text}</text></g>`;
    const cls = n.id===selfId ? "n-person n-self" : "n-person";
    const click = n.id===selfId ? "" : ` onclick="location.hash='#/person/${n.id}'"`;
    return `<g${click}><circle class="${cls}" cx="${n.x}" cy="${n.y}" r="${n.id===selfId?9:6}"><title>${esc(n.label)}</title></circle>
      <text x="${n.x}" y="${n.y+dy}" text-anchor="middle">${text}</text></g>`;
  }).join("");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = edges + marks;
}

/* ---------- review ---------- */
async function renderReview(){
  setNav("#/review");
  app.innerHTML = `<div class="loading">pulling the review ledger…</div>`;
  const r = await api("/v1/review/merges");
  const dup = r.possible_duplicates||[];
  const fuz = r.fuzzy_merges||[];
  app.innerHTML = `
    <section class="block"><h4>Possible duplicates · ${dup.length}</h4>
      ${dup.length? dup.map(d=>`<div class="conflict">
        <div class="vs"><span><a href="#/person/${d.person_id}">${esc(d.person_name)}</a></span>
        <span class="m">≟</span><span><a href="#/person/${d.duplicate_person_id}">${esc(d.duplicate_person_name)}</a></span></div>
        <div class="src">${esc(d.signals?.reason||"score "+d.score)}</div>
        <div style="margin-top:8px">
          <button class="btn" onclick="act('/v1/review/duplicates/${d.candidate_id}/merge')">Merge</button>
          <button class="btn danger" onclick="act('/v1/review/duplicates/${d.candidate_id}/reject')">Distinct people</button>
        </div></div>`).join("") : `<div class="empty">No duplicates await judgement.</div>`}</section>
    <section class="block"><h4>Fuzzy merges awaiting confirmation · ${fuz.length}</h4>
      ${fuz.length? fuz.map(f=>`<div class="conflict">
        <div><a href="#/person/${f.person_id}">${esc(f.person_name)}</a> ← ${esc(f.source)}:${esc(f.external_id)} (${esc(f.record_name)})</div>
        <div class="src">${esc(f.signals?.reason||f.match_method)}</div>
        <div style="margin-top:8px">
          <button class="btn" onclick="act('/v1/review/merges/${f.link_id}/approve')">Approve</button>
          <button class="btn danger" onclick="act('/v1/review/merges/${f.link_id}/split')">Split</button>
        </div></div>`).join("") : `<div class="empty">No merges await confirmation.</div>`}</section>`;
}
async function act(path){ await api(path,{method:"POST"}); renderReview(); }

/* ---------- health ---------- */
async function renderHealth(){
  setNav("#/health");
  app.innerHTML = `<div class="loading">checking the stacks…</div>`;
  const h = await api("/v1/health/sources");
  app.innerHTML = `<section class="block"><h4>Source ledger</h4>
    <table><tr><th>source</th><th>status</th><th style="text-align:right">runs</th><th>last finished</th></tr>
    ${h.sources.map(s=>`<tr><td>${esc(s.source)}</td>
      <td><span class="vstate ${s.status==="ok"?"corroborated":"unverified"}">${esc(s.status)}</span></td>
      <td class="num">${s.runs}</td><td>${esc((s.last_finished_at||"").slice(0,16).replace("T"," "))}</td></tr>`).join("")}
    </table></section>`;
}

function setNav(hash){
  document.querySelectorAll("#nav a").forEach(a=>a.classList.toggle("active", a.getAttribute("href")===hash));
}
async function route(){
  if(!token()) return renderToken();
  const h = location.hash || "#/search";
  try{
    if(h.startsWith("#/person/")) await renderPerson(h.split("/")[2]);
    else if(h==="#/review") await renderReview();
    else if(h==="#/health") await renderHealth();
    else await renderSearch();
  }catch(e){ if(e.message!=="unauthorized") app.innerHTML = `<div class="warn">error: ${esc(e.message)}</div>`; }
}
window.addEventListener("hashchange", route);
route();
</script>
</body>
</html>
"""

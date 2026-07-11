PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>umbrelarr</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0f14;
      --surface: #11171f;
      --raised: #171e27;
      --line: #29323e;
      --line-strong: #3a4655;
      --text: #f5f7fa;
      --muted: #96a2b1;
      --brand: #67e8f9;
      --green: #4ade80;
      --amber: #fbbf24;
      --red: #fb7185;
      --blue: #60a5fa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input { font: inherit; }
    button {
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      background: var(--raised);
      color: var(--text);
      padding: 7px 12px;
      cursor: pointer;
      font-weight: 650;
    }
    button:hover { border-color: #526174; background: #1c2530; }
    button.primary { border-color: #0891b2; background: #22d3ee; color: #083344; }
    button.primary:hover { background: #67e8f9; }
    button:focus-visible, input:focus-visible, a:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
    button:disabled { cursor: not-allowed; opacity: .5; }
    main { width: min(1240px, 100%); margin: 0 auto; padding: 22px 24px 32px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 52px; }
    .identity { display: flex; align-items: center; gap: 11px; min-width: 0; }
    .logo { width: 36px; height: 36px; border: 1px solid #155e75; border-radius: 7px; display: grid; place-items: center; background: #103744; color: var(--brand); font-size: 15px; font-weight: 850; }
    h1 { margin: 0; font-size: 19px; letter-spacing: 0; }
    .sub { color: var(--muted); margin: 1px 0 0; font-size: 12px; }
    .toolbar { display: flex; gap: 8px; align-items: center; }
    .overview { margin-top: 18px; border-block: 1px solid var(--line); display: grid; grid-template-columns: minmax(260px, 1fr) auto; align-items: stretch; }
    .health-copy { display: flex; align-items: center; gap: 13px; min-width: 0; padding: 21px 20px 21px 0; }
    .health-mark { width: 13px; height: 13px; border-radius: 50%; background: var(--muted); box-shadow: 0 0 0 5px #27303b; flex: 0 0 auto; }
    .health-mark.healthy { background: var(--green); box-shadow: 0 0 0 5px #173824; }
    .health-mark.action_required { background: var(--amber); box-shadow: 0 0 0 5px #453712; }
    .health-mark.failed { background: var(--red); box-shadow: 0 0 0 5px #46202a; }
    .health-mark.waiting, .health-mark.configuring { background: var(--blue); box-shadow: 0 0 0 5px #182f4d; }
    .health-title { margin: 0; font-size: 20px; font-weight: 760; }
    .health-detail { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
    .summary { display: grid; grid-template-columns: repeat(4, minmax(82px, 1fr)); border-left: 1px solid var(--line); }
    .metric { padding: 17px 16px; border-left: 1px solid var(--line); min-width: 92px; }
    .metric:first-child { border-left: 0; }
    .metric strong { display: block; font-size: 20px; font-variant-numeric: tabular-nums; }
    .metric span { color: var(--muted); font-size: 11px; }
    .meta-row { padding: 10px 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: var(--muted); font-size: 12px; }
    .attention { margin-top: 10px; border: 1px solid #854d0e; border-left: 4px solid var(--amber); border-radius: 6px; background: #211908; padding: 15px 16px; }
    .attention h2 { margin: 0; font-size: 15px; }
    .attention p { margin: 3px 0 0; color: #e5c87d; }
    .vpn-form { margin-top: 13px; display: grid; grid-template-columns: minmax(160px, 1fr) minmax(160px, 1fr) auto; gap: 10px; align-items: end; }
    label span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 5px; }
    input { width: 100%; min-height: 38px; border: 1px solid var(--line-strong); border-radius: 6px; padding: 7px 9px; background: #0d131a; color: var(--text); }
    .storage { margin-top: 20px; padding: 18px 0; border-block: 1px solid var(--line); }
    .storage-head { display: flex; justify-content: space-between; align-items: center; gap: 18px; }
    .storage-head h2 { margin: 0; font-size: 15px; }
    .storage-head p { margin: 2px 0 0; color: var(--muted); font-size: 11px; }
    .segmented { display: inline-flex; border: 1px solid var(--line-strong); border-radius: 6px; padding: 3px; background: #0d131a; }
    .segmented input { position: absolute; opacity: 0; pointer-events: none; }
    .segmented label { min-height: 32px; display: grid; place-items: center; padding: 5px 10px; border-radius: 4px; color: var(--muted); cursor: pointer; font-weight: 650; }
    .segmented input:checked + label { background: var(--raised); color: var(--text); }
    .segmented input:focus-visible + label { outline: 2px solid var(--brand); outline-offset: 2px; }
    .path-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
    .storage-actions { margin-top: 12px; display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .workspace { display: grid; grid-template-columns: minmax(0, 1fr) 310px; gap: 24px; margin-top: 22px; align-items: start; }
    .section-head { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin: 0 0 10px; }
    .section-head h2 { margin: 0; font-size: 15px; }
    .section-head p { margin: 2px 0 0; color: var(--muted); font-size: 11px; }
    .table-wrap { border: 1px solid var(--line); border-radius: 7px; overflow: hidden; background: var(--surface); }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th { padding: 9px 12px; color: var(--muted); background: var(--raised); font-size: 10px; text-align: left; text-transform: uppercase; }
    td { padding: 11px 12px; border-top: 1px solid var(--line); vertical-align: middle; overflow-wrap: anywhere; }
    tbody tr:hover { background: #141c25; }
    th:nth-child(1), td:nth-child(1) { width: 25%; }
    th:nth-child(2), td:nth-child(2) { width: 19%; }
    th:nth-child(4), td:nth-child(4) { width: 60px; text-align: right; }
    .service { font-weight: 700; }
    .detail { color: var(--muted); font-size: 12px; }
    .status { display: inline-flex; align-items: center; gap: 7px; font-weight: 650; font-size: 12px; white-space: nowrap; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }
    .healthy .dot { background: var(--green); }
    .failed .dot { background: var(--red); }
    .waiting .dot { background: var(--blue); }
    .action_required .dot { background: var(--amber); }
    .configuring .dot { background: var(--brand); }
    a { color: var(--brand); text-decoration: none; font-weight: 650; }
    a:hover { text-decoration: underline; }
    .activity { border: 1px solid var(--line); border-radius: 7px; background: var(--surface); overflow: hidden; }
    .activity-head { padding: 13px 14px; background: var(--raised); border-bottom: 1px solid var(--line); }
    .activity-head h2 { margin: 0; font-size: 14px; }
    .activity-head p { margin: 2px 0 0; color: var(--muted); font-size: 11px; }
    .events { max-height: 590px; overflow: auto; }
    .event { display: grid; grid-template-columns: 46px 1fr; gap: 10px; padding: 11px 14px; border-bottom: 1px solid var(--line); font-size: 12px; }
    .event:last-child { border-bottom: 0; }
    .event time { color: var(--muted); font-variant-numeric: tabular-nums; }
    .empty { color: var(--muted); padding: 20px 14px; font-size: 12px; }
    .error { color: var(--red); min-height: 18px; margin-top: 7px; font-size: 12px; }
    @media (max-width: 900px) {
      .overview { grid-template-columns: 1fr; }
      .summary { border-left: 0; border-top: 1px solid var(--line); }
      .workspace { grid-template-columns: 1fr; }
      .events { max-height: 280px; }
    }
    @media (max-width: 640px) {
      main { padding: 14px 14px 24px; }
      header { align-items: flex-start; }
      .sub { display: none; }
      .toolbar button { min-height: 36px; padding-inline: 9px; }
      .health-copy { padding-right: 0; }
      .summary { grid-template-columns: repeat(2, 1fr); }
      .metric:nth-child(3) { border-left: 0; border-top: 1px solid var(--line); }
      .metric:nth-child(4) { border-top: 1px solid var(--line); }
      .meta-row { align-items: flex-start; }
      .vpn-form { grid-template-columns: 1fr; }
      .storage-head { align-items: flex-start; flex-direction: column; }
      .path-grid { grid-template-columns: 1fr; }
      .storage-actions { align-items: stretch; flex-direction: column; }
      th:nth-child(3), td:nth-child(3) { display: none; }
      th:nth-child(1), td:nth-child(1) { width: 43%; }
      th:nth-child(2), td:nth-child(2) { width: auto; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div class="identity">
      <div class="logo" aria-hidden="true">ua</div>
      <div><h1>umbrelarr</h1><p class="sub">Media stack management</p></div>
    </div>
    <div class="toolbar"><button id="refresh">Refresh</button><button class="primary" id="reconcile">Reconcile now</button></div>
  </header>

  <section class="overview" aria-label="Stack summary" aria-live="polite">
    <div class="health-copy">
      <span class="health-mark" id="healthMark"></span>
      <div><p class="health-title" id="healthTitle">Checking stack</p><p class="health-detail" id="healthDetail">Waiting for the first reconciliation.</p></div>
    </div>
    <div class="summary">
      <div class="metric"><strong id="healthy">0</strong><span>Healthy</span></div>
      <div class="metric"><strong id="attentionCount">0</strong><span>Attention</span></div>
      <div class="metric"><strong id="waiting">0</strong><span>In progress</span></div>
      <div class="metric"><strong id="failed">0</strong><span>Failed</span></div>
    </div>
  </section>
  <div class="meta-row"><span>Managed scope: this Umbrel media stack</span><span id="fresh">Not checked yet</span></div>

  <section class="attention" id="vpnPanel" hidden>
    <h2>Privado login required</h2>
    <p>Enter only your Privado login. Credentials go directly to Privado, and server selection is automatic.</p>
    <form class="vpn-form" id="vpnForm">
      <label><span>Username</span><input name="username" autocomplete="username" required></label>
      <label><span>Password</span><input name="password" type="password" autocomplete="current-password" required></label>
      <button class="primary" type="submit">Connect Privado</button>
    </form>
    <div class="error" id="formError" role="alert"></div>
  </section>

  <section class="storage" aria-labelledby="storageTitle">
    <div class="storage-head">
      <div><h2 id="storageTitle">Library locations</h2><p id="storageScope">Umbrel /downloads</p></div>
      <div class="segmented" role="radiogroup" aria-label="Storage preset">
        <input type="radio" id="modeLocal" name="storageMode" value="local" checked><label for="modeLocal">Umbrel</label>
        <input type="radio" id="modeNetwork" name="storageMode" value="network"><label for="modeNetwork">Network</label>
      </div>
    </div>
    <form id="storageForm">
      <div class="path-grid">
        <label><span>TV</span><input name="sonarr" required></label>
        <label><span>TV 4K</span><input name="sonarr-4k" required></label>
        <label><span>Movies</span><input name="radarr" required></label>
        <label><span>Movies 4K</span><input name="radarr-4k" required></label>
        <label><span>Music</span><input name="lidarr" required></label>
      </div>
      <div class="storage-actions"><span class="error" id="storageError" role="alert"></span><button class="primary" type="submit">Save locations</button></div>
    </form>
  </section>

  <div class="workspace">
    <section>
      <div class="section-head"><div><h2>Services</h2><p>Only umbrelarr-owned resources are repaired; your settings remain yours.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Service</th><th>Status</th><th>Detail</th><th></th></tr></thead><tbody id="services"></tbody></table></div>
    </section>
    <aside class="activity">
      <div class="activity-head"><h2>Recent activity</h2><p>Credential-safe reconciliation events</p></div>
      <div class="events" id="events"><div class="empty">No activity yet.</div></div>
    </aside>
  </div>
</main>
<script>
const labels={unknown:'Unknown',waiting:'Waiting',action_required:'Action required',configuring:'Configuring',healthy:'Healthy',failed:'Failed'};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let storageState=null;
function ago(epoch){if(!epoch)return'Not checked yet';const seconds=Math.max(0,Math.floor(Date.now()/1000-epoch));if(seconds<10)return'Updated just now';if(seconds<60)return`Updated ${seconds}s ago`;return`Updated ${Math.floor(seconds/60)}m ago`;}
function overall(data){const counts=data.counts||{};if(counts.failed)return['failed','Stack needs intervention',`${counts.failed} service${counts.failed===1?'':'s'} failed the last check.`];if(counts.action_required)return['action_required','Setup needs attention',`${counts.action_required} action${counts.action_required===1?'':'s'} required to finish configuration.`];if((counts.waiting||0)+(counts.configuring||0))return['configuring','Stack is configuring','Services are starting or umbrelarr is applying managed settings.'];if((counts.healthy||0)===data.services.length&&data.services.length)return['healthy','All services operational','The managed media stack is configured and responding.'];return['unknown','Checking stack','Waiting for current service health information.'];}
async function load(){
  const response=await fetch('/api/status',{cache:'no-store'});
  if(!response.ok)throw new Error('Unable to load stack status');
  const data=await response.json();
  const counts=data.counts||{};
  document.getElementById('healthy').textContent=counts.healthy||0;
  document.getElementById('attentionCount').textContent=counts.action_required||0;
  document.getElementById('waiting').textContent=(counts.waiting||0)+(counts.configuring||0);
  document.getElementById('failed').textContent=counts.failed||0;
  document.getElementById('fresh').textContent=(data.running?'Reconciliation in progress / ':'')+ago(data.lastCompletedAt);
  document.getElementById('reconcile').disabled=data.running;
  const [state,title,detail]=overall(data);
  document.getElementById('healthMark').className=`health-mark ${state}`;
  document.getElementById('healthTitle').textContent=title;
  document.getElementById('healthDetail').textContent=detail;
  const vpn=data.services.find(service=>service.id==='privado-vpn');
  document.getElementById('vpnPanel').hidden=!(vpn&&vpn.status==='action_required');
  document.getElementById('services').innerHTML=data.services.map(service=>`<tr><td class="service">${esc(service.name)}</td><td><span class="status ${esc(service.status)}"><span class="dot"></span>${esc(labels[service.status]||service.status)}</span></td><td class="detail">${esc(service.detail)}</td><td><a href="${esc(service.link)}" target="_blank" rel="noreferrer">Open</a></td></tr>`).join('');
  document.getElementById('events').innerHTML=data.events.length?data.events.map(event=>`<div class="event"><time>${new Date(event.at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time><span>${esc(event.message)}</span></div>`).join(''):'<div class="empty">No activity yet.</div>';
}
function setStorageFields(roots){for(const [name,value] of Object.entries(roots||{})){const input=document.querySelector(`[name="${name}"]`);if(input)input.value=value;}}
function selectStorageMode(mode,applyPreset=false){
  const radio=document.querySelector(`[name="storageMode"][value="${mode}"]`);
  if(radio)radio.checked=true;
  document.getElementById('storageScope').textContent=mode==='network'?'Linked /network storage':'Umbrel /downloads';
  if(applyPreset&&storageState)setStorageFields(storageState.presets[mode]);
}
async function loadStorage(){
  const response=await fetch('/api/storage',{cache:'no-store'});
  if(!response.ok)throw new Error('Unable to load library locations');
  storageState=await response.json();
  selectStorageMode(storageState.mode);
  setStorageFields(storageState.roots);
}
async function mutate(url,options={}){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},...options});if(!response.ok){const data=await response.json().catch(()=>({error:'Request failed'}));throw new Error(data.error||'Request failed');}await load();}
document.getElementById('refresh').onclick=()=>load().catch(error=>alert(error.message));
document.getElementById('reconcile').onclick=()=>mutate('/api/reconcile').catch(error=>alert(error.message));
document.getElementById('vpnForm').onsubmit=async event=>{event.preventDefault();const error=document.getElementById('formError');error.textContent='';try{await mutate('/api/vpn/login',{body:new URLSearchParams(new FormData(event.currentTarget))});event.currentTarget.reset();}catch(value){error.textContent=value.message;}};
document.querySelectorAll('[name="storageMode"]').forEach(input=>input.onchange=()=>selectStorageMode(input.value,true));
document.getElementById('storageForm').onsubmit=async event=>{event.preventDefault();const error=document.getElementById('storageError');error.textContent='';const data=new FormData(event.currentTarget);data.set('mode',document.querySelector('[name="storageMode"]:checked').value);try{await mutate('/api/storage',{body:new URLSearchParams(data)});await loadStorage();}catch(value){error.textContent=value.message;}};
Promise.all([load(),loadStorage()]).catch(error=>{document.getElementById('healthTitle').textContent='Status unavailable';document.getElementById('healthDetail').textContent=error.message;});
setInterval(()=>load().catch(()=>{}),5000);
</script>
</body></html>"""

"""NP Dashboard. Stdlib only (no install). http://localhost:5050
Reads/writes cases.json shared with intake_agent.py. Fictional data only.
"""
import json
import os
import re
import tempfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
CASES_PATH = os.path.join(BASE, "cases.json")
PORT = 5050


def load_cases():
    if not os.path.exists(CASES_PATH):
        return []
    with open(CASES_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_cases(cases):
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(cases, f, indent=2)
    os.replace(tmp, CASES_PATH)


def now_hm():
    return datetime.now().strftime("%H:%M")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NP Intake Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --lav:#D7C7ED;        /* main */
  --lav-soft:#EFE8F8;   /* tint of main */
  --white:#FFFFFF;      /* secondary */
  --ink:#1D1C1A;        /* accent / body text */
  --ink-2:#5C5A57;      /* secondary text */
  --line:#E4DEEC;
  --alert:#B42318;      /* clinical alert, kept red on purpose */
  --alert-soft:#FDECEA;
  --ok:#1F6B45;
  --display:'Bebas Neue',Impact,'Arial Narrow',sans-serif;
  --body:'Public Sans',-apple-system,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--white);color:var(--ink);font-family:var(--body);font-size:18px;line-height:1.45}
h1,h2,h3{font-family:var(--display);font-weight:400;letter-spacing:.02em;margin:0;line-height:1}
:focus-visible{outline:3px solid var(--ink);outline-offset:2px}

header{background:var(--ink);color:var(--white);display:flex;align-items:baseline;justify-content:space-between;padding:14px 28px}
header h1{font-size:34px}
header h1 span{color:var(--lav)}
header small{font-size:14px;color:var(--lav)}

.wrap{display:grid;grid-template-columns:300px 1fr;min-height:calc(100vh - 62px)}
#queue{background:var(--lav);padding:20px 0}
#queue h2{font-size:24px;padding:0 20px 10px}
.qi{display:block;width:100%;text-align:left;border:0;background:transparent;padding:14px 20px;cursor:pointer;font:inherit;color:var(--ink);border-left:6px solid transparent}
.qi:hover{background:rgba(255,255,255,.35)}
.qi.sel{background:var(--white);border-left-color:var(--ink)}
.qi .n{font-weight:700;font-size:18px;display:flex;gap:8px;align-items:center}
.qi .m{font-size:14px;color:var(--ink-2);margin-top:2px}
.tag{font-size:12px;font-weight:700;padding:2px 7px;border-radius:4px;letter-spacing:.04em}
.tag.stat{background:var(--alert);color:var(--white)}
.tag.rout{background:var(--white);color:var(--ink);border:1px solid var(--ink)}

#main{padding:28px 36px 40px;max-width:1500px}
.empty{margin-top:12vh;text-align:center;color:var(--ink-2)}
.empty h2{font-size:56px;color:var(--ink);margin-bottom:8px}

.banner{background:var(--alert);color:var(--white);font-family:var(--display);font-size:40px;letter-spacing:.04em;padding:10px 22px;border-radius:8px;margin-bottom:22px;animation:pulse 1.4s ease-in-out infinite}
@keyframes pulse{50%{opacity:.82}}
@media (prefers-reduced-motion:reduce){.banner{animation:none}}

.who h2{font-size:64px}
.who p{margin:6px 0 0;color:var(--ink-2)}

.tl{list-style:none;display:grid;grid-template-columns:repeat(5,1fr);gap:6px;padding:0;margin:22px 0 26px}
.tl li{background:var(--lav-soft);color:var(--ink-2);padding:10px 12px;border-radius:6px;font-size:15px;font-weight:600}
.tl li.on{background:var(--lav);color:var(--ink)}
.tl li .t{display:block;font-weight:400;font-size:13px;margin-top:2px;min-height:1em}

/* Vitals: the one loud element. Read like a bedside monitor. */
.vitals{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.vt{border:2px solid var(--ink);border-radius:10px;padding:14px 18px 12px;background:var(--white)}
.vt .lbl{font-size:15px;font-weight:600}
.vt .val{font-family:var(--display);font-size:84px;line-height:.95;margin-top:6px}
.vt .unit{font-size:15px;color:var(--ink-2)}
.vt.crit{border-color:var(--alert);background:var(--alert-soft);color:var(--alert)}
.vt.crit .unit{color:var(--alert)}
.vt .why{font-size:14px;font-weight:700;min-height:1.2em;margin-top:4px}
.vt.wait .val{color:var(--line)}

.flags{border-left:6px solid var(--alert);background:var(--alert-soft);color:var(--alert);padding:10px 16px;font-weight:700;margin-bottom:26px;border-radius:0 6px 6px 0}

.cols{display:grid;grid-template-columns:3fr 2fr;gap:22px;align-items:start}
.panel{border:1px solid var(--line);border-radius:10px;padding:20px 22px;background:var(--white)}
.panel h3{font-size:30px;margin-bottom:12px}
.sbar{display:grid;grid-template-columns:44px 1fr;column-gap:16px;row-gap:16px;margin:0}
.sbar dt{font-family:var(--display);font-size:34px;line-height:1;background:var(--lav);text-align:center;border-radius:6px;height:40px;padding-top:4px}
.sbar dd{margin:0;max-width:62ch}
.sbar dd small{display:block;color:var(--ink-2);font-size:14px;margin-bottom:2px}
.missing{margin-top:14px;font-size:15px;color:var(--ink-2)}

button.act{font:inherit;font-weight:700;font-size:18px;padding:12px 20px;border-radius:8px;border:2px solid var(--ink);background:var(--lav);color:var(--ink);cursor:pointer}
button.act:hover:not(:disabled){background:var(--ink);color:var(--white)}
button.act:disabled{background:var(--white);border-color:var(--line);color:var(--ink-2);cursor:default}
textarea{display:block;width:100%;min-height:120px;font:inherit;padding:12px;border:2px solid var(--line);border-radius:8px;margin:14px 0;resize:vertical}
textarea:focus{border-color:var(--ink);outline:none}
.result{margin-top:12px;font-weight:600}
.result.ok{color:var(--ok)}
.waiting{color:var(--ink-2)}

@media (max-width:1100px){
  .cols{grid-template-columns:1fr}
  .vitals{grid-template-columns:repeat(2,1fr)}
}
@media (max-width:760px){
  .wrap{grid-template-columns:1fr}
  #queue{padding:0}
  #qlist{display:flex;overflow-x:auto}
  #queue h2{display:none}
  .qi{flex:0 0 auto;width:auto;border-left:0;border-bottom:4px solid transparent}
  .qi.sel{border-bottom-color:var(--ink)}
  #main{padding:18px 16px 32px}
  .who h2{font-size:44px}
  .banner{font-size:30px}
  .tl{grid-template-columns:1fr 1fr}
  .vt .val{font-size:60px}
}
</style></head><body>
<header><h1>Telehealth intake <span>/ NP dashboard</span></h1><small>Fictional data only</small></header>
<div class="wrap">
  <nav id="queue" aria-label="Case queue"><h2>Cases</h2><div id="qlist"></div></nav>
  <main id="main">
    <div id="detail"><div class="empty"><h2>No calls yet</h2><p>New intake calls appear here as soon as a nurse dials in.</p></div></div>
  </main>
</div>
<script>
const STEPS=[["call_in_progress","Call in progress"],["summary_received","Summary received"],
 ["acknowledged","NP acknowledged"],["orders_sent","Orders sent"],["readback_confirmed","Read-back confirmed"]];
let cases=[],selected=null,lastNewest=null,draft={};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const byNew=(a,b)=>b.created_at.localeCompare(a.created_at);
const num=v=>{const m=String(v??"").match(/\d+(\.\d+)?/);return m?parseFloat(m[0]):null;};

// Same thresholds as intake_agent.assess(), so tiles match the red flags.
function vitals(f){
  const bp=String(f.bp??"").match(/\d+/g)||[];const sbp=bp.length?+bp[0]:null;
  const hr=num(f.heart_rate),t=num(f.temp_f),o2=num(f.spo2);
  return [
    {lbl:"Blood pressure",val:bp.length>=2?`${bp[0]}/${bp[1]}`:null,unit:"mmHg",
     why:sbp!=null&&sbp<90?"Low systolic":sbp!=null&&sbp>180?"High systolic":""},
    {lbl:"Heart rate",val:hr,unit:"bpm",why:hr!=null&&hr<50?"Bradycardic":hr!=null&&hr>120?"Tachycardic":""},
    {lbl:"Temperature",val:t,unit:"°F",why:t!=null&&t>=100.4?"Fever":""},
    {lbl:"Oxygen saturation",val:o2,unit:"%",why:o2!=null&&o2<90?"Low oxygen":""},
  ];
}

async function poll(){try{const r=await fetch('/api/cases');cases=await r.json();render();}catch(e){}}

function render(){
  const newest=[...cases].sort(byNew)[0];
  if(newest&&newest.id!==lastNewest){selected=newest.id;lastNewest=newest.id;}
  const list=[...cases].sort((a,b)=>((b.acuity==='stat')-(a.acuity==='stat'))||byNew(a,b));
  document.getElementById('qlist').innerHTML=list.map(c=>{
    const f=c.fields||{},n=(c.red_flags||[]).length;
    const tag=c.acuity==='stat'?'<span class="tag stat">STAT</span>':c.acuity?'<span class="tag rout">Routine</span>':'';
    return `<button class="qi ${c.id===selected?'sel':''}" data-id="${esc(c.id)}">
      <span class="n">${tag}${esc(f.resident_name||'Incoming call')}</span>
      <span class="m">${esc((c.created_at||'').slice(11,16))}, ${n} ${n===1?'flag':'flags'}, ${esc((c.status||'').replace(/_/g,' '))}</span></button>`;
  }).join('');
  document.querySelectorAll('.qi').forEach(b=>b.onclick=()=>{selected=b.dataset.id;render();});

  const c=cases.find(x=>x.id===selected);
  if(!c)return;
  const f=c.fields||{},tl=c.timeline||{};
  const ta=document.getElementById('orders');
  if(ta&&!ta.disabled)draft[selected]=ta.value;

  let h='';
  if(c.acuity==='stat')h+=`<div class="banner" role="alert">STAT: critical vitals</div>`;
  h+=`<div class="who"><h2>${esc(f.resident_name||'Incoming call')}</h2><p>Caller: ${esc(f.nurse_name||'not given yet')}, case ${esc(c.id)}</p></div>`;
  h+=`<ol class="tl">`+STEPS.map(([k,l])=>`<li class="${tl[k]?'on':''}">${l}<span class="t">${esc(tl[k]||'')}</span></li>`).join('')+`</ol>`;

  h+=`<section class="vitals" aria-label="Vital signs">`+vitals(f).map(v=>{
    const cls=v.val==null?'wait':v.why?'crit':'';
    return `<div class="vt ${cls}"><div class="lbl">${v.lbl}</div>
      <div class="val">${v.val==null?'--':esc(v.val)}</div><div class="unit">${v.unit}</div>
      <div class="why">${esc(v.why)}</div></div>`;}).join('')+`</section>`;
  if((c.red_flags||[]).length)h+=`<div class="flags">Red flags: ${c.red_flags.map(esc).join(', ')}</div>`;

  const row=(k,label,val)=>`<dt>${k}</dt><dd><small>${label}</small>${val?esc(val):'<span class="waiting">Waiting for the nurse...</span>'}</dd>`;
  h+=`<div class="cols"><section class="panel"><h3>SBAR summary</h3><dl class="sbar">
    ${row('S','Situation',f.reason_for_call)}
    ${row('B','Background',f.relevant_history)}
    ${row('A','Assessment',(c.red_flags||[]).length?c.red_flags.join(', '):(f.spo2!=null?'No critical vitals':''))}
    ${row('R','Request',f.nurse_request)}</dl>
    ${(c.missing||[]).length?`<p class="missing">Not provided: ${c.missing.map(esc).join(', ')}</p>`:''}</section>`;

  h+=`<section class="panel"><h3>Orders</h3>`;
  if(!c.sbar_text){h+=`<p class="waiting">Orders open once the intake call finishes.</p>`;}
  else{
    const sent=!!tl.orders_sent;
    h+=`<button class="act" id="ackBtn" ${c.status==='summary_received'?'':'disabled'}>${tl.acknowledged?'Acknowledged at '+esc(tl.acknowledged):'Acknowledge'}</button>
      <label for="orders" class="sr" style="position:absolute;left:-9999px">Orders for the nurse</label>
      <textarea id="orders" placeholder="Type orders for the nurse" ${sent?'disabled':''}>${esc(sent?c.orders:(draft[c.id]??''))}</textarea>
      <button class="act" id="sendBtn" ${tl.acknowledged&&!sent?'':'disabled'}>${sent?'Orders sent':'Send orders to nurse'}</button>`;
    if(tl.readback_confirmed)h+=`<p class="result ok">Read-back confirmed at ${esc(tl.readback_confirmed)}: "${esc(c.readback_text)}"</p>`;
    else if(sent)h+=`<p class="result waiting">Waiting for the nurse to call back and read the orders back.</p>`;
  }
  h+=`</section></div>`;

  const focusId=document.activeElement&&document.activeElement.id;
  const sel=focusId==='orders'?[document.activeElement.selectionStart,document.activeElement.selectionEnd]:null;
  document.getElementById('detail').innerHTML=h;
  if(focusId==='orders'){const t=document.getElementById('orders');if(t&&!t.disabled){t.focus();t.setSelectionRange(...sel);}}

  const ack=document.getElementById('ackBtn'),send=document.getElementById('sendBtn'),t2=document.getElementById('orders');
  if(ack)ack.onclick=async()=>{await fetch(`/api/cases/${selected}/ack`,{method:'POST'});poll();};
  if(t2)t2.oninput=()=>{draft[selected]=t2.value;};
  if(send)send.onclick=async()=>{const o=t2.value.trim();if(!o)return;
    await fetch(`/api/cases/${selected}/orders`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({orders:o})});poll();};
}
poll();setInterval(poll,2000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, PAGE, "text/html; charset=utf-8")
        elif self.path.startswith("/api/cases"):
            self.send(200, json.dumps(load_cases()))
        else:
            self.send(404, '{"error":"not found"}')

    def do_POST(self):
        m = re.match(r"^/api/cases/([\w-]+)/(ack|orders)$", self.path)
        if not m:
            return self.send(404, '{"error":"not found"}')
        case_id, action = m.groups()
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        cases = load_cases()
        case = next((c for c in cases if c["id"] == case_id), None)
        if not case:
            return self.send(404, '{"error":"no case"}')
        if action == "ack":
            if case["status"] != "summary_received":
                return self.send(400, '{"error":"not ready"}')
            case["status"] = "acknowledged"
            case["timeline"]["acknowledged"] = now_hm()
        else:
            orders = (body.get("orders") or "").strip()
            if "acknowledged" not in case["timeline"] or not orders:
                return self.send(400, '{"error":"acknowledge first and enter orders"}')
            case["orders"] = orders
            case["status"] = "orders_sent"
            case["timeline"]["orders_sent"] = now_hm()
        save_cases(cases)
        self.send(200, json.dumps(case))


if __name__ == "__main__":
    print(f"NP dashboard running: http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

"""NP Dashboard v2. Stdlib only (no install). http://localhost:5050
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
<html><head><meta charset="utf-8"><title>NP Intake Dashboard</title>
<style>
:root{--cer:#0284C7;--navy:#082F49;--red:#DC2626;--bg:#F1F5F9;--line:#CBD5E1}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--navy);font-size:20px}
header{background:var(--navy);color:#fff;padding:14px 24px;font-size:26px;font-weight:700;display:flex;justify-content:space-between}
header small{font-weight:400;font-size:18px;opacity:.8}
.wrap{display:flex;height:calc(100vh - 62px)}
#queue{width:320px;background:#fff;border-right:1px solid var(--line);overflow:auto}
.qi{padding:14px 16px;border-bottom:1px solid var(--line);cursor:pointer}
.qi.sel{background:#E0F2FE;border-left:6px solid var(--cer)}
.qi .n{font-weight:700}
.qi .m{font-size:16px;color:#475569;margin-top:4px}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:14px;font-weight:700;margin-right:6px}
.stat{background:var(--red);color:#fff}
.rout{background:#E2E8F0;color:var(--navy)}
#main{flex:1;overflow:auto;padding:24px 32px}
.banner{background:var(--red);color:#fff;font-size:30px;font-weight:800;padding:12px 18px;border-radius:10px;margin-bottom:16px;animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.75}}
h2{margin:0 0 6px;font-size:30px}
.sub{color:#475569;margin-bottom:16px}
.tl{display:flex;gap:8px;margin:12px 0 20px}
.step{flex:1;text-align:center;padding:10px 6px;border-radius:8px;background:#E2E8F0;color:#64748B;font-size:16px;font-weight:600}
.step.on{background:var(--cer);color:#fff}
.step .t{display:block;font-size:14px;font-weight:400;margin-top:2px}
.flags{background:#FEE2E2;border:2px solid var(--red);border-radius:10px;padding:12px 16px;margin-bottom:16px;color:#991B1B;font-weight:700}
pre{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px;font-size:20px;white-space:pre-wrap;line-height:1.4}
.actions{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px;margin-top:16px}
button{font-size:20px;padding:12px 20px;border-radius:8px;border:0;background:var(--cer);color:#fff;font-weight:700;cursor:pointer}
button:disabled{background:#94A3B8;cursor:default}
textarea{width:100%;height:110px;font-size:20px;padding:10px;border:1px solid var(--line);border-radius:8px;margin:12px 0;font-family:inherit}
.result{margin-top:10px;font-weight:600;color:#065F46}
.empty{color:#64748B;font-size:24px;margin-top:80px;text-align:center}
</style></head><body>
<header><span>Telehealth Intake | NP Dashboard v2</span><small>fictional data only</small></header>
<div class="wrap">
  <div id="queue"></div>
  <div id="main">
    <div id="detail"><div class="empty">Waiting for calls...</div></div>
    <div class="actions" id="actions" style="display:none">
      <button id="ackBtn">Acknowledge</button>
      <textarea id="orders" placeholder="Type orders here..."></textarea>
      <button id="sendBtn">Send orders to nurse</button>
      <div class="result" id="result"></div>
    </div>
  </div>
</div>
<script>
const STEPS=[["call_in_progress","Call in progress"],["summary_received","Summary received"],
 ["acknowledged","NP acknowledged"],["orders_sent","Orders sent"],["readback_confirmed","Read-back confirmed"]];
const LABELS={nurse_name:"Caller",resident_name:"Resident",reason_for_call:"Situation",bp:"BP",heart_rate:"HR",
 temp_f:"Temp F",spo2:"SpO2",relevant_history:"History",nurse_request:"Request"};
let cases=[],selected=null,lastNewest=null,ordersFor=null;
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const byNew=(a,b)=>b.created_at.localeCompare(a.created_at);

async function poll(){try{const r=await fetch('/api/cases');cases=await r.json();render();}catch(e){}}

function render(){
  const newest=[...cases].sort(byNew)[0];
  if(newest&&newest.id!==lastNewest){selected=newest.id;lastNewest=newest.id;}
  const list=[...cases].sort((a,b)=>((b.acuity==='stat')-(a.acuity==='stat'))||byNew(a,b));
  document.getElementById('queue').innerHTML=list.map(c=>{
    const f=c.fields||{};
    return `<div class="qi ${c.id===selected?'sel':''}" onclick="pick('${c.id}')">
      <div class="n">${c.acuity==='stat'?'<span class="badge stat">STAT</span>':c.acuity?'<span class="badge rout">ROUTINE</span>':''}${esc(f.resident_name||'Incoming call...')}</div>
      <div class="m">${esc((c.created_at||'').slice(11,16))} · ${(c.red_flags||[]).length} flags · ${esc((c.status||'').replace(/_/g,' '))}</div></div>`;
  }).join('');
  const c=cases.find(x=>x.id===selected);
  const acts=document.getElementById('actions');
  if(!c){acts.style.display='none';return;}
  const f=c.fields||{},tl=c.timeline||{};
  let h='';
  if(c.acuity==='stat')h+=`<div class="banner">⚠ STAT — CRITICAL VITALS</div>`;
  h+=`<h2>${esc(f.resident_name||'Incoming call...')}</h2><div class="sub">Caller: ${esc(f.nurse_name||'—')} · Case ${esc(c.id)}</div>`;
  h+=`<div class="tl">`+STEPS.map(([k,l])=>`<div class="step ${tl[k]?'on':''}">${l}<span class="t">${esc(tl[k]||'')}</span></div>`).join('')+`</div>`;
  if((c.red_flags||[]).length)h+=`<div class="flags">RED FLAGS: ${c.red_flags.map(esc).join(' · ')}</div>`;
  if(c.sbar_text)h+=`<pre>${esc(c.sbar_text)}</pre>`;
  else h+=`<pre>Intake in progress...\n\n`+Object.keys(LABELS).filter(k=>f[k]!=null).map(k=>`${LABELS[k]}: ${esc(f[k])}`).join('\n')+`</pre>`;
  document.getElementById('detail').innerHTML=h;

  acts.style.display=c.sbar_text?'block':'none';
  const ack=document.getElementById('ackBtn'),send=document.getElementById('sendBtn'),ta=document.getElementById('orders');
  ack.disabled=!(c.status==='summary_received');
  ack.textContent=tl.acknowledged?`Acknowledged ✓ ${tl.acknowledged}`:'Acknowledge';
  send.disabled=!(tl.acknowledged&&!tl.orders_sent);
  if(ordersFor!==c.id){ta.value=c.orders||'';ordersFor=c.id;}
  ta.disabled=!!tl.orders_sent;
  document.getElementById('result').textContent=
    tl.readback_confirmed?`✓ Read-back confirmed ${tl.readback_confirmed}: "${c.readback_text||''}"`:
    tl.orders_sent?`Orders queued ${tl.orders_sent}. Waiting for nurse to call back for read-back...`:'';
}
function pick(id){selected=id;render();}
document.getElementById('ackBtn').onclick=async()=>{await fetch(`/api/cases/${selected}/ack`,{method:'POST'});poll();};
document.getElementById('sendBtn').onclick=async()=>{
  const orders=document.getElementById('orders').value.trim(); if(!orders)return;
  await fetch(`/api/cases/${selected}/orders`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({orders})});poll();};
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

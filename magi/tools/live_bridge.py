"""The live NERV bridge: watch the MAGI deliberate in real time.

Architecture (deliberately boring, per the spec):

  engine emits structured events  ->  LiveState stores the latest snapshot
  a stdlib http.server serves the board HTML and /state.json
  the browser polls /state.json every ~500ms and redraws

No SSE, no websockets, no framework, no third-party dependency. Polling is
stateless, testable without a browser, and degrades gracefully — a dropped poll
just recovers on the next tick.

The seam into the engine is a single event_sink callback. The engine does not
know this module exists; it only calls sink(event). That keeps the protocol and
the UI fully decoupled — the engine is never rewritten around the view.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class LiveState:
    """Thread-safe latest-snapshot store fed by engine events.

    The engine runs on a worker thread and calls update() as events arrive; the
    HTTP handler reads snapshot() on request threads. All access is locked.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = {
            "phase": "booting",
            "proposition": "",
            "stakes": "ROUTINE",
            "members": [],
            "models": {},
            "round": 0,
            "round_name": "",
            "units": {},        # name -> {status, vote, confidence, reason, changed}
            "ireul": None,       # {categories, summary} when an attack is detected
            "decision": None,    # final decision dict
            "finished": False,
        }

    def update(self, event: dict) -> None:
        etype = event.get("type")
        with self._lock:
            s = self._state
            if etype == "run_started":
                s["phase"] = "running"
                s["proposition"] = event.get("proposition", "")
                s["stakes"] = event.get("stakes", "ROUTINE")
                s["members"] = event.get("members", [])
                s["models"] = event.get("models", {})
                s["units"] = {
                    m: {"status": "pending", "vote": None, "confidence": 0,
                        "reason": "", "changed": False}
                    for m in s["members"]
                }
            elif etype == "ireul_alert":
                s["ireul"] = {
                    "categories": event.get("categories", []),
                    "summary": event.get("summary", ""),
                }
            elif etype == "round_started":
                s["round"] = event.get("round", 0)
                s["round_name"] = event.get("name", "")
            elif etype == "member_started":
                unit = s["units"].get(event["member"])
                if unit:
                    unit["status"] = "thinking"
            elif etype == "member_resolved":
                unit = s["units"].setdefault(event["member"], {})
                unit.update({
                    "status": "resolved",
                    "vote": event.get("vote"),
                    "confidence": event.get("confidence", 0),
                    "reason": event.get("reason", ""),
                })
            elif etype == "reflection_resolved":
                unit = s["units"].setdefault(event["member"], {})
                changed = event.get("from") != event.get("to")
                unit.update({
                    "status": "reflected",
                    "vote": event.get("to"),
                    "confidence": event.get("confidence", unit.get("confidence", 0)),
                    "reason": event.get("reason", unit.get("reason", "")),
                    "changed": changed,
                })
            elif etype == "decision":
                s["decision"] = {
                    "decision": event.get("decision"),
                    "support": event.get("support", 0),
                    "oppose": event.get("oppose", 0),
                    "abstain": event.get("abstain", 0),
                    "invalid_question": event.get("invalid_question", 0),
                    "stakes": event.get("stakes", "ROUTINE"),
                    "gravity_note": event.get("gravity_note", ""),
                }
            elif etype == "run_finished":
                s["phase"] = "finished"
                s["finished"] = True

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._state))  # deep copy under lock


def make_handler(state: LiveState, board_html: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence the default request logging
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, board_html.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path.startswith("/state.json"):
                body = json.dumps(state.snapshot()).encode("utf-8")
                self._send(200, body, "application/json")
            else:
                self._send(404, b"not found", "text/plain")

    return Handler


def start_server(state: LiveState, board_html: str, host: str = "127.0.0.1",
                 port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    """Start the live server on a background thread. Returns (server, port)."""
    server = ThreadingHTTPServer((host, port), make_handler(state, board_html))
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, actual_port


# --------------------------------------------------------------------------- #
# The live board HTML. Same phosphor language as the static bridge, but the
# units start pending and flicker, then snap on resolve. All animation is in
# plain JS polling /state.json — no framework.
# --------------------------------------------------------------------------- #

LIVE_BOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAGI · NERV BRIDGE · LIVE</title>
<style>
  :root {
    --black:#05060a; --panel:#0a0d14; --amber:#ff9800; --amber-dim:#7a4d10;
    --green:#4dff7a; --red:#ff2d2d; --grey:#45505f; --line:#1c2430;
  }
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--black);color:var(--amber);
    font-family:"DejaVu Sans Mono","Courier New",monospace}
  body{min-height:100vh;padding:24px 20px 40px;overflow-x:hidden}
  body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:999;
    background:repeating-linear-gradient(0deg,rgba(0,0,0,0) 0 2px,rgba(0,0,0,.28) 2px 3px)}
  body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:998;
    background:radial-gradient(ellipse at center,rgba(0,0,0,0) 55%,rgba(0,0,0,.7) 100%)}
  .wrap{max-width:1100px;margin:0 auto;position:relative;z-index:1}
  .topbar{display:flex;justify-content:space-between;align-items:baseline;
    border-bottom:1px solid var(--line);padding-bottom:8px;letter-spacing:.18em}
  .brand{font-size:15px;font-weight:700}
  .brand small{color:var(--grey);letter-spacing:.3em;margin-left:10px;font-size:11px}
  .sys{color:var(--grey);font-size:11px;letter-spacing:.28em}
  .sys .live{color:var(--red)}
  .prop{margin:18px 0 6px;color:#cfd6de;font-size:15px;line-height:1.5;
    border-left:3px solid var(--amber-dim);padding:6px 0 6px 14px}
  .prop .q{color:var(--grey);letter-spacing:.3em;font-size:10px;display:block;margin-bottom:4px}
  .phase{margin:6px 0 0;color:var(--amber);letter-spacing:.24em;font-size:12px;min-height:16px}

  .ireul-banner{margin:14px 0;border:1px solid var(--red);background:rgba(255,45,45,.07);
    padding:10px 14px;display:flex;flex-direction:column;gap:3px;animation:flicker 1.1s infinite}
  .ireul-code{color:var(--red);font-weight:700;letter-spacing:.22em;font-size:13px}
  .ireul-detail{color:#e8a0a0;font-size:11px}
  @keyframes flicker{0%,100%{opacity:1}48%{opacity:1}50%{opacity:.55}52%{opacity:1}}

  .board{position:relative;margin:22px auto;width:100%;max-width:960px;aspect-ratio:1/0.72}
  .core{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:30%;
    aspect-ratio:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
    text-align:center;z-index:3}
  .core .kanji{font-size:clamp(52px,10vw,112px);font-weight:800;line-height:.9;color:var(--amber);
    text-shadow:0 0 24px rgba(255,152,0,.55);min-height:.9em;transition:color .4s}
  .core .en{letter-spacing:.30em;font-size:12px;margin-top:8px;color:var(--amber);min-height:14px}
  .core .split{color:var(--grey);font-size:12px;margin-top:12px;letter-spacing:.12em;white-space:nowrap}
  .core .stakes-badge{margin-top:12px;padding:3px 12px;border:1px solid var(--amber);
    font-size:11px;letter-spacing:.24em;display:none}
  .core.has-stakes .stakes-badge{display:inline-block}
  .core.grave .stakes-badge{border-color:var(--red);color:var(--red)}

  .unit{position:absolute;width:33%;z-index:2}
  .pos-top{top:0;left:50%;transform:translateX(-50%)}
  .pos-bottom{bottom:0;left:50%;transform:translateX(-50%)}
  .pos-left{top:50%;left:0;transform:translateY(-50%)}
  .pos-right{top:50%;right:0;transform:translateY(-50%)}
  .unit-frame{border:1px solid var(--amber-dim);background:var(--panel);padding:12px 14px;
    position:relative;transition:border-color .4s}
  .unit-frame::before{content:"";position:absolute;top:-1px;left:-1px;width:14px;height:14px;
    border-top:2px solid var(--amber);border-left:2px solid var(--amber)}
  .unit-frame::after{content:"";position:absolute;bottom:-1px;right:-1px;width:14px;height:14px;
    border-bottom:2px solid var(--amber);border-right:2px solid var(--amber)}
  .unit-head{display:flex;justify-content:space-between;align-items:baseline}
  .unit-name{font-weight:700;letter-spacing:.18em;font-size:15px}
  .unit-num{color:var(--grey);font-size:12px}
  .unit-title{color:var(--grey);font-size:10px;letter-spacing:.12em;margin:3px 0 10px}
  .unit-vote{font-size:22px;font-weight:800;letter-spacing:.1em;min-height:26px}
  .unit-conf{display:flex;align-items:center;gap:8px;margin:8px 0}
  .conf-bar{flex:1;height:6px;background:#10151d;border:1px solid var(--line)}
  .conf-bar span{display:block;height:100%;width:0;background:currentColor;transition:width .5s}
  .conf-num{font-size:11px;color:var(--grey)}
  .unit-reason{color:#9fb0c0;font-size:11px;line-height:1.5;margin-top:8px;max-height:5.5em;overflow:hidden}
  .tag-changed{display:none;font-size:9px;letter-spacing:.18em;color:var(--black);
    background:var(--amber);padding:1px 6px;margin-top:4px}
  .unit.changed .tag-changed{display:inline-block}

  /* pending / thinking: amber flicker + scramble */
  .unit.pending .unit-vote,.unit.thinking .unit-vote{color:var(--amber)}
  .unit.thinking .unit-frame{animation:think 0.9s steps(2) infinite;border-color:var(--amber)}
  @keyframes think{0%,100%{box-shadow:0 0 0 rgba(255,152,0,0)}50%{box-shadow:0 0 14px rgba(255,152,0,.35)}}
  .unit.pending .unit-vote::after{content:"—";color:var(--grey)}

  .unit.support .unit-vote,.unit.support .unit-name{color:var(--green)}
  .unit.support .unit-frame{border-color:rgba(77,255,122,.5)}
  .unit.support{color:var(--green)}
  .unit.oppose .unit-vote,.unit.oppose .unit-name{color:var(--red)}
  .unit.oppose .unit-frame{border-color:rgba(255,45,45,.5)}
  .unit.oppose{color:var(--red)}
  .unit.abstain .unit-vote,.unit.invalid_question .unit-vote{color:var(--grey)}
  .unit.abstain,.unit.invalid_question{color:var(--grey)}

  .board svg.links{position:absolute;inset:0;width:100%;height:100%;z-index:1}
  .board svg.links line{stroke:var(--amber);stroke-width:.5;opacity:.5;stroke-dasharray:2 2;
    filter:drop-shadow(0 0 2px rgba(255,152,0,.6))}
  .board svg.links circle{fill:var(--amber);opacity:.8}
  .footer{text-align:center;color:var(--grey);font-size:11px;letter-spacing:.12em;margin-top:16px}
  .footer .note{color:var(--amber-dim);margin-top:6px;min-height:14px}

  body.conflict{color:var(--red)}
  body.conflict .core .kanji{color:var(--red);text-shadow:0 0 26px rgba(255,45,45,.6)}
  body.conflict .core .en,body.conflict .brand{color:var(--red)}
  body.conflict .unit-frame::before,body.conflict .unit-frame::after{border-color:var(--red)}
  body.conflict .prop{border-left-color:var(--red)}
  body.conflict .phase{color:var(--red)}

  @media(max-width:680px){
    .board{aspect-ratio:auto;max-width:460px;display:flex;flex-direction:column}
    .unit,.core{position:static;width:100%;transform:none;margin-bottom:12px}
    .core{order:-1}.pos-top{order:1}.pos-left{order:2}.pos-right{order:3}.pos-bottom{order:4}
    .board svg.links{display:none}
  }
</style>
</head>
<body class="">
  <div class="wrap">
    <div class="topbar">
      <div class="brand">MAGI<small>NERV · CENTRAL DOGMA</small></div>
      <div class="sys"><span class="live">● LIVE</span> &nbsp;<span id="phase-label">BOOTING</span></div>
    </div>
    <div class="prop"><span class="q">PROPOSITION UNDER REVIEW</span><span id="prop">Awaiting query…</span></div>
    <div class="phase" id="round-label"></div>
    <div id="ireul-slot"></div>

    <div class="board">
      <svg class="links" viewBox="0 0 100 100" preserveAspectRatio="none">
        <line x1="50" y1="50" x2="50" y2="12"></line>
        <line x1="50" y1="50" x2="14" y2="50"></line>
        <line x1="50" y1="50" x2="86" y2="50"></line>
        <line x1="50" y1="50" x2="50" y2="88"></line>
        <circle cx="50" cy="50" r="1.2"></circle>
      </svg>
      <div class="core" id="core">
        <div class="kanji" id="kanji"></div>
        <div class="en" id="verdict-en"></div>
        <div class="split" id="split"></div>
        <span class="stakes-badge" id="stakes-badge"></span>
      </div>
      <div class="unit pos-top pending" id="u-MELCHIOR" data-num="1" data-title="科学者 · THE SCIENTIST"></div>
      <div class="unit pos-left pending" id="u-BALTHASAR" data-num="2" data-title="母 · THE MOTHER"></div>
      <div class="unit pos-right pending" id="u-CASPER" data-num="3" data-title="女 · THE WOMAN"></div>
      <div class="unit pos-bottom pending" id="u-ARTABAN" data-num="4" data-title="男 · THE MAN"></div>
    </div>

    <div class="footer">
      MAGI SYSTEM · MELCHIOR-1 · BALTHASAR-2 · CASPER-3 · ARTABAN-4
      <div class="note" id="gravity-note"></div>
    </div>
  </div>

<script>
const KANJI = {
  "SUPPORT":["可決","APPROVED"], "OPPOSE":["否決","REJECTED"],
  "NO CONSENSUS":["膠着","DEADLOCK"], "INVALID_QUESTION":["無効","VOID"],
  "ABSTAIN":["保留","WITHHELD"]
};
const PHASES = {0:"STANDBY",1:"ROUND 1 · INDEPENDENT ANALYSIS",2:"ROUND 2 · CROSS-EXAMINATION",
  3:"ROUND 3 · SATISFACTION",4:"ROUND 4 · REFLECTION",5:"ROUND 5 · CHAIR DOSSIER"};
const GLYPHS = "▚▞▙▟▛▜◤�థ▒░▓#%*+=-";

function scramble(el, real){
  // brief glitch text on a thinking unit
  if(el.dataset.locked) return;
  let out="";
  for(let i=0;i<8;i++) out += GLYPHS[Math.floor(Math.random()*GLYPHS.length)];
  el.textContent = out;
}

function ensureUnit(id, data){
  const el = document.getElementById("u-"+id);
  if(!el) return null;
  if(!el.dataset.built){
    el.dataset.built="1";
    el.innerHTML = `<div class="unit-frame">
      <div class="unit-head"><span class="unit-name">${id}</span><span class="unit-num">${el.dataset.num}</span></div>
      <div class="unit-title">${el.dataset.title}</div>
      <div class="unit-vote"></div>
      <div class="unit-conf"><div class="conf-bar"><span></span></div><span class="conf-num"></span></div>
      <span class="tag-changed">再考 CHANGED</span>
      <div class="unit-reason"></div>
    </div>`;
  }
  return el;
}

function setUnit(id, u){
  const el = ensureUnit(id, u);
  if(!el) return;
  const vote = el.querySelector(".unit-vote");
  const status = u.status || "pending";
  el.classList.remove("pending","thinking","support","oppose","abstain","invalid_question");
  if(status==="thinking"){
    el.classList.add("thinking");
    scramble(vote);
  } else if(status==="resolved" || status==="reflected"){
    el.dataset.locked="1";
    const v = (u.vote||"ABSTAIN");
    el.classList.add(v.toLowerCase());
    vote.textContent = v;
    el.querySelector(".conf-bar span").style.width = (u.confidence||0)+"%";
    el.querySelector(".conf-num").textContent = (u.confidence||0)+"%";
    el.querySelector(".unit-reason").textContent = u.reason||"";
    if(u.changed) el.classList.add("changed");
  } else {
    el.classList.add("pending");
    vote.textContent = "—";
  }
}

function render(s){
  document.getElementById("prop").textContent = s.proposition || "Awaiting query…";
  document.getElementById("phase-label").textContent =
    s.phase==="finished" ? "COMPLETE" : (s.phase||"booting").toUpperCase();
  document.getElementById("round-label").textContent = PHASES[s.round]||"";

  // Ireul
  const slot = document.getElementById("ireul-slot");
  if(s.ireul && !slot.dataset.shown){
    slot.dataset.shown="1";
    slot.innerHTML = `<div class="ireul-banner">
      <span class="ireul-code">使徒 IREUL // INTRUSION DETECTED</span>
      <span class="ireul-detail">${(s.ireul.categories||[]).join(", ")} — proposition neutralized, council judged the disarmed form</span></div>`;
    document.body.classList.add("conflict");
  }

  // Units
  for(const [id,u] of Object.entries(s.units||{})) setUnit(id,u);

  // Core verdict — only once decided
  if(s.decision){
    const d = s.decision;
    const [k,en] = KANJI[d.decision] || ["膠着","DEADLOCK"];
    document.getElementById("kanji").textContent = k;
    document.getElementById("verdict-en").textContent = en + " · " + d.decision;
    document.getElementById("split").textContent =
      `${d.support} 賛 / ${d.oppose} 否 / ${d.abstain} 保 / ${d.invalid_question} 無`;
    document.getElementById("gravity-note").textContent = d.gravity_note||"";
    const core = document.getElementById("core");
    if(d.stakes && d.stakes!=="ROUTINE"){
      core.classList.add("has-stakes");
      const badge = document.getElementById("stakes-badge");
      badge.textContent = d.stakes;
      if(d.stakes==="GRAVE") core.classList.add("grave");
    }
    if(d.stakes==="GRAVE" && d.decision==="NO CONSENSUS") document.body.classList.add("conflict");
  }
}

let stop=false;
async function poll(){
  if(stop) return;
  try{
    const r = await fetch("/state.json",{cache:"no-store"});
    const s = await r.json();
    render(s);
    if(s.finished){ stop=true; document.querySelector(".sys .live").textContent="● DONE"; return; }
  }catch(e){/* transient; next tick recovers */}
  setTimeout(poll, 500);
}
// keep thinking units glitching between polls
setInterval(()=>{document.querySelectorAll(".unit.thinking .unit-vote").forEach(v=>scramble(v));}, 120);
poll();
</script>
</body>
</html>"""

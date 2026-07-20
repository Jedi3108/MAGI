"""The NERV bridge: render a deliberation as the MAGI display.

This is the payoff. After the whole hardening arc, a MAGI deliberation deserves
to be *seen* the way NERV's Central Dogma sees it — the units arranged around a
core, their verdicts stamped in kanji, dissent burning a different colour,
Ireul lighting the whole board red.

Design is deliberately faithful to the source rather than a generic dashboard:
true black, a single amber phosphor that glows in isolation (no gradients), a
monospace utility face, CRT scanlines, and the canonical kanji verdict overlay.
Where the show has three units, we have four — ARTABAN, the fourth wise man —
so the layout is a diamond around the core rather than a triangle, which is our
honest extension of the canon, not a deviation from it.

Output is a single self-contained HTML string: no framework, no external asset,
no network. Pure stdlib, in keeping with the whole project.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass

# Canonical MAGI verdict overlay (the big kanji stamp).
VERDICT_KANJI = {
    "SUPPORT": ("可決", "APPROVED"),
    "OPPOSE": ("否決", "REJECTED"),
    "NO CONSENSUS": ("膠着", "DEADLOCK"),
    "INVALID_QUESTION": ("無効", "VOID"),
    "ABSTAIN": ("保留", "WITHHELD"),
}

# Per-vote phosphor. Amber is the system default; support/oppose read green/red
# only where a member has actually taken that position, so the board's colour
# tells the story at a glance.
VOTE_CLASS = {
    "SUPPORT": "v-support",
    "OPPOSE": "v-oppose",
    "ABSTAIN": "v-abstain",
    "INVALID_QUESTION": "v-void",
}

# Members in canonical order, with unit numbers and the diamond position each
# occupies around the core.
UNIT_META = {
    "MELCHIOR": {"num": "1", "title": "科学者 · THE SCIENTIST", "pos": "top"},
    "BALTHASAR": {"num": "2", "title": "母 · THE MOTHER", "pos": "left"},
    "CASPER": {"num": "3", "title": "女 · THE WOMAN", "pos": "right"},
    "ARTABAN": {"num": "4", "title": "男 · THE MAN", "pos": "bottom"},
}


@dataclass
class UnitView:
    name: str
    num: str
    title: str
    pos: str
    vote: str
    confidence: int
    reason: str
    changed: bool  # did the vote move between round 1 and reflection?


def _esc(text: object) -> str:
    return html.escape(str(text if text is not None else ""))


def _unit_views(result: dict) -> list[UnitView]:
    verdicts = {v.member_name: v for v in result.get("verdicts", [])}
    views: list[UnitView] = []
    for reflection in result.get("reflections", []):
        name = reflection.member_name
        meta = UNIT_META.get(name, {"num": "?", "title": name, "pos": "top"})
        v1 = verdicts.get(name)
        changed = bool(v1 and v1.vote != reflection.vote_after)
        views.append(UnitView(
            name=name,
            num=meta["num"],
            title=meta["title"],
            pos=meta["pos"],
            vote=reflection.vote_after,
            confidence=reflection.confidence_after,
            reason=reflection.reason or (v1.core_reason if v1 else ""),
            changed=changed,
        ))
    return views


def _unit_html(u: UnitView) -> str:
    vote_class = VOTE_CLASS.get(u.vote, "v-abstain")
    changed_tag = '<span class="tag-changed">再考 CHANGED</span>' if u.changed else ""
    return f"""
    <div class="unit pos-{u.pos} {vote_class}" data-vote="{_esc(u.vote)}">
      <div class="unit-frame">
        <div class="unit-head">
          <span class="unit-name">{_esc(u.name)}</span>
          <span class="unit-num">{_esc(u.num)}</span>
        </div>
        <div class="unit-title">{_esc(u.title)}</div>
        <div class="unit-vote">{_esc(u.vote)}</div>
        <div class="unit-conf">
          <div class="conf-bar"><span style="width:{int(u.confidence)}%"></span></div>
          <span class="conf-num">{int(u.confidence)}%</span>
        </div>
        {changed_tag}
        <div class="unit-reason">{_esc(u.reason)}</div>
      </div>
    </div>"""


def render_bridge(result: dict, title: str = "MAGI") -> str:
    decision = result.get("decision", {})
    verdict = decision.get("decision", "NO CONSENSUS")
    kanji, en = VERDICT_KANJI.get(verdict, ("膠着", "DEADLOCK"))

    ireul = result.get("ireul", {})
    under_attack = bool(ireul.get("adversarial"))
    stakes = decision.get("stakes", "ROUTINE")
    # Conflict mode: the whole board goes red on an attack or a grave stalemate.
    conflict = under_attack or (stakes == "GRAVE" and verdict == "NO CONSENSUS")

    units = _unit_views(result)
    units_html = "".join(_unit_html(u) for u in units)

    proposition = _esc(result.get("proposition", ""))
    split = (
        f"{decision.get('support', 0)} 賛 / {decision.get('oppose', 0)} 否 / "
        f"{decision.get('abstain', 0)} 保 / {decision.get('invalid_question', 0)} 無"
    )
    gravity_note = _esc(decision.get("gravity_note", ""))

    ireul_banner = ""
    if under_attack:
        cats = ", ".join(ireul.get("categories", []))
        ireul_banner = f"""
      <div class="ireul-banner">
        <span class="ireul-code">使徒 IREUL // INTRUSION DETECTED</span>
        <span class="ireul-detail">{_esc(cats)} — proposition neutralized, council judged the disarmed form</span>
      </div>"""

    stakes_badge = "" if stakes == "ROUTINE" else f'<span class="stakes-badge stakes-{_esc(stakes.lower())}">{_esc(stakes)}</span>'

    return _TEMPLATE.format(
        title=_esc(title),
        conflict="conflict" if conflict else "",
        kanji=_esc(kanji),
        verdict_en=_esc(en),
        verdict_raw=_esc(verdict),
        proposition=proposition,
        split=_esc(split),
        gravity_note=gravity_note,
        stakes_badge=stakes_badge,
        ireul_banner=ireul_banner,
        units=units_html,
    )


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · NERV BRIDGE</title>
<style>
  :root {{
    --black: #05060a;
    --panel: #0a0d14;
    --amber: #ff9800;
    --amber-dim: #7a4d10;
    --green: #4dff7a;
    --red: #ff2d2d;
    --grey: #45505f;
    --line: #1c2430;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; background: var(--black); color: var(--amber);
    font-family: "DejaVu Sans Mono", "Courier New", monospace; }}
  body {{ min-height: 100vh; padding: 28px 20px 48px; overflow-x: hidden; }}

  /* CRT scanlines + vignette */
  body::before {{ content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 999;
    background: repeating-linear-gradient(0deg, rgba(0,0,0,0) 0 2px, rgba(0,0,0,.28) 2px 3px); }}
  body::after {{ content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 998;
    background: radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,.7) 100%); }}

  .wrap {{ max-width: 1100px; margin: 0 auto; position: relative; z-index: 1; }}

  .topbar {{ display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 1px solid var(--line); padding-bottom: 8px; letter-spacing: .18em; }}
  .brand {{ font-size: 15px; font-weight: 700; }}
  .brand small {{ color: var(--grey); letter-spacing: .3em; margin-left: 10px; font-size: 11px; }}
  .sys {{ color: var(--grey); font-size: 11px; letter-spacing: .3em; }}

  .prop {{ margin: 20px 0 6px; color: #cfd6de; font-size: 15px; line-height: 1.5;
    border-left: 3px solid var(--amber-dim); padding: 6px 0 6px 14px; }}
  .prop .q {{ color: var(--grey); letter-spacing: .3em; font-size: 10px; display: block; margin-bottom: 4px; }}

  .ireul-banner {{ margin: 14px 0; border: 1px solid var(--red); background: rgba(255,45,45,.07);
    padding: 10px 14px; display: flex; flex-direction: column; gap: 3px; animation: flicker 1.1s infinite; }}
  .ireul-code {{ color: var(--red); font-weight: 700; letter-spacing: .22em; font-size: 13px; }}
  .ireul-detail {{ color: #e8a0a0; font-size: 11px; letter-spacing: .05em; }}
  @keyframes flicker {{ 0%,100%{{opacity:1}} 48%{{opacity:1}} 50%{{opacity:.55}} 52%{{opacity:1}} }}

  /* The board: diamond of four units around the central verdict core */
  .board {{ position: relative; margin: 26px auto; width: 100%; max-width: 960px;
    aspect-ratio: 1 / 0.72; }}
  .core {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
    width: 30%; aspect-ratio: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center; z-index: 3; }}
  .core .kanji {{ font-size: clamp(56px, 10vw, 116px); font-weight: 800; line-height: .9;
    color: var(--amber); text-shadow: 0 0 24px rgba(255,152,0,.55); }}
  .core .en {{ letter-spacing: .30em; font-size: 12px; margin-top: 8px; color: var(--amber); }}
  .core .split {{ color: var(--grey); font-size: 12px; margin-top: 12px; letter-spacing: .12em;
    white-space: nowrap; }}
  .core .stakes-badge {{ margin-top: 12px; padding: 3px 12px; border: 1px solid var(--amber);
    font-size: 11px; letter-spacing: .24em; }}
  .stakes-grave {{ border-color: var(--red) !important; color: var(--red) !important; }}

  .unit {{ position: absolute; width: 33%; z-index: 2; }}
  .pos-top {{ top: 0; left: 50%; transform: translateX(-50%); }}
  .pos-bottom {{ bottom: 0; left: 50%; transform: translateX(-50%); }}
  .pos-left {{ top: 50%; left: 0; transform: translateY(-50%); }}
  .pos-right {{ top: 50%; right: 0; transform: translateY(-50%); }}

  .unit-frame {{ border: 1px solid var(--amber-dim); background: var(--panel);
    padding: 12px 14px; position: relative; }}
  .unit-frame::before {{ content: ""; position: absolute; top: -1px; left: -1px; width: 14px; height: 14px;
    border-top: 2px solid var(--amber); border-left: 2px solid var(--amber); }}
  .unit-frame::after {{ content: ""; position: absolute; bottom: -1px; right: -1px; width: 14px; height: 14px;
    border-bottom: 2px solid var(--amber); border-right: 2px solid var(--amber); }}
  .unit-head {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .unit-name {{ font-weight: 700; letter-spacing: .18em; font-size: 15px; }}
  .unit-num {{ color: var(--grey); font-size: 12px; }}
  .unit-title {{ color: var(--grey); font-size: 10px; letter-spacing: .12em; margin: 3px 0 10px; }}
  .unit-vote {{ font-size: 22px; font-weight: 800; letter-spacing: .1em; }}
  .unit-conf {{ display: flex; align-items: center; gap: 8px; margin: 8px 0; }}
  .conf-bar {{ flex: 1; height: 6px; background: #10151d; border: 1px solid var(--line); }}
  .conf-bar span {{ display: block; height: 100%; background: currentColor; }}
  .conf-num {{ font-size: 11px; color: var(--grey); }}
  .unit-reason {{ color: #9fb0c0; font-size: 11px; line-height: 1.5; margin-top: 8px;
    max-height: 5.5em; overflow: hidden; }}
  .tag-changed {{ display: inline-block; font-size: 9px; letter-spacing: .18em; color: var(--black);
    background: var(--amber); padding: 1px 6px; margin-top: 4px; }}

  /* vote colours — only where a real position is taken */
  .v-support .unit-vote, .v-support .unit-name {{ color: var(--green); }}
  .v-support .unit-frame {{ border-color: rgba(77,255,122,.5); }}
  .v-support {{ color: var(--green); }}
  .v-oppose .unit-vote, .v-oppose .unit-name {{ color: var(--red); }}
  .v-oppose .unit-frame {{ border-color: rgba(255,45,45,.5); }}
  .v-oppose {{ color: var(--red); }}
  .v-abstain .unit-vote {{ color: var(--grey); }}
  .v-abstain {{ color: var(--grey); }}
  .v-void .unit-vote {{ color: var(--grey); }}

  /* connecting lines from each unit toward the core */
  .board svg.links {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; }}
  .board svg.links line {{ stroke: var(--amber); stroke-width: .5; opacity: .55;
    stroke-dasharray: 2 2; filter: drop-shadow(0 0 2px rgba(255,152,0,.6)); }}
  .board svg.links circle {{ fill: var(--amber); opacity: .8; }}

  .footer {{ text-align: center; color: var(--grey); font-size: 11px; letter-spacing: .12em;
    margin-top: 18px; }}
  .footer .note {{ color: var(--amber-dim); margin-top: 6px; }}

  /* CONFLICT MODE — Ireul / grave deadlock: the whole board burns red */
  body.conflict {{ color: var(--red); }}
  body.conflict .core .kanji {{ color: var(--red); text-shadow: 0 0 26px rgba(255,45,45,.6); }}
  body.conflict .core .en, body.conflict .brand {{ color: var(--red); }}
  body.conflict .unit-frame::before, body.conflict .unit-frame::after {{ border-color: var(--red); }}
  body.conflict .prop {{ border-left-color: var(--red); }}
  body.conflict::before {{ animation: scan 4s linear infinite; }}
  @keyframes scan {{ 0%{{transform:translateY(0)}} 100%{{transform:translateY(4px)}} }}

  @media (max-width: 680px) {{
    .board {{ aspect-ratio: auto; max-width: 460px; }}
    .unit, .core {{ position: static; width: 100%; transform: none; margin-bottom: 12px; }}
    .core {{ order: -1; }}
    .board {{ display: flex; flex-direction: column; }}
    .pos-top{{order:1}} .pos-left{{order:2}} .pos-right{{order:3}} .pos-bottom{{order:4}}
    .board svg.links {{ display: none; }}
  }}
</style>
</head>
<body class="{conflict}">
  <div class="wrap">
    <div class="topbar">
      <div class="brand">{title}<small>NERV · CENTRAL DOGMA</small></div>
      <div class="sys">DELIBERATION COMPLETE</div>
    </div>

    <div class="prop"><span class="q">PROPOSITION UNDER REVIEW</span>{proposition}</div>
    {ireul_banner}

    <div class="board">
      <svg class="links" viewBox="0 0 100 100" preserveAspectRatio="none">
        <line x1="50" y1="50" x2="50" y2="12"></line>
        <line x1="50" y1="50" x2="14" y2="50"></line>
        <line x1="50" y1="50" x2="86" y2="50"></line>
        <line x1="50" y1="50" x2="50" y2="88"></line>
        <circle cx="50" cy="50" r="1.2"></circle>
      </svg>
      <div class="core">
        <div class="kanji">{kanji}</div>
        <div class="en">{verdict_en} · {verdict_raw}</div>
        <div class="split">{split}</div>
        {stakes_badge}
      </div>
      {units}
    </div>

    <div class="footer">
      MAGI SYSTEM · MELCHIOR-1 · BALTHASAR-2 · CASPER-3 · ARTABAN-4
      <div class="note">{gravity_note}</div>
    </div>
  </div>
</body>
</html>"""


def write_bridge(result: dict, path: str, title: str = "MAGI") -> str:
    html_text = render_bridge(result, title=title)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    return path

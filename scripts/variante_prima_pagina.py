#!/usr/bin/env python3
"""
variante_prima_pagina.py — patru feluri de a așeza articolele pe prima pagină,
generate din index.html-ul curent (aceleași carduri, același CSS), ca să fie
COMPARATE pe un server local, cu butoane. Nu atinge site-ul.

Cerute de fondator pe 12 septembrie 2026: „nu prea îmi place cum sunt puse
meniurile unul sub celălalt… se pierd foarte multe articole… arată-mi și alte
variante de afișare pe local".

Rulare:
  python3 scripts/variante_prima_pagina.py        → _v0.html … _v4.html în rădăcină
  python3 -m http.server 8765                     → http://localhost:8765/_v1.html
"""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from build_site import CAT_ORDER, CAT_ID  # noqa: E402

IDX = os.path.join(ROOT, "index.html")

VARIANTE = [
    ("_v0.html", "0 · Cum e acum", "Secțiunile una sub alta, toate cardurile."),
    ("_v1.html", "1 · File pe categorii", "O singură categorie vizibilă, aleasă din file lipite sub meniu; toate cardurile ei, nimic ascuns."),
    ("_v2.html", "2 · Coloane derulabile", "Fiecare categorie e o coloană cu derulare proprie; le vezi pe toate deodată, niciuna nu se termină."),
    ("_v3.html", "3 · Flux cronologic + filtre", "Toate articolele într-un singur flux, cele mai noi întâi; apeși o categorie și rămân doar ale ei."),
    ("_v4.html", "4 · Compact: 6 carduri + lista", "Fiecare categorie: 6 carduri, apoi restul ca listă de titluri pe două coloane. Pagina e de 5 ori mai scurtă."),
]

BARA = """
<div id="varbar" style="position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#111;color:#fff;font:600 13px system-ui;padding:8px 12px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;box-shadow:0 -6px 20px rgba(0,0,0,.3)">
  <span style="opacity:.7;margin-right:6px">Variante:</span>
  {butoane}
  <span style="margin-left:auto;opacity:.75;font-weight:400">{descriere}</span>
</div>
<div style="height:52px"></div>
"""


def _bara(activ):
    b = []
    for fis, nume, _ in VARIANTE:
        st = "background:#f1a525;color:#111" if fis == activ else "background:#333;color:#fff"
        b.append(f'<a href="{fis}" style="{st};padding:6px 10px;border-radius:8px;text-decoration:none">{nume}</a>')
    desc = next(d for f, _, d in VARIANTE if f == activ)
    return BARA.format(butoane="\n  ".join(b), descriere=html.escape(desc))


def _sectiuni(s):
    """{categorie: [carduri html]} din index.html, în ordinea de acolo."""
    out = {}
    for m in re.finditer(r'<section class="cat-section" id="([^"]+)">(.*?)</section>', s, re.S):
        cid, corp = m.group(1), m.group(2)
        cat = next((c for c in CAT_ORDER if CAT_ID[c] == cid), cid)
        carduri = re.findall(r'(<a href="a/[^"]+" class="card">.*?</a>)\n', corp, re.S)
        out[cat] = carduri
    return out


def _data(card):
    m = re.search(r"<span>· (\d{4}-\d{2}-\d{2})</span>", card)
    return m.group(1) if m else ""


def _titlu(card):
    m = re.search(r"<h3>(.*?)</h3>", card, re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)) if m else ""


def _href(card):
    return re.search(r'href="([^"]+)"', card).group(1)


def _inlocuieste_main(s, corp_nou):
    """Păstrează antetul, hero-ul și coloana din dreapta; schimbă doar secțiunile."""
    start = s.index('        <section class="cat-section" id="')
    end = s.rindex("</section>", 0, s.index("<aside>")) + len("</section>")
    return s[:start] + corp_nou + s[end:]


def v1_file(sec):
    css = """<style>
.file{position:sticky;top:52px;z-index:50;background:var(--bg,#fff);display:flex;gap:6px;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--line,#ddd);margin:0 0 18px}
.file button{font:700 13px system-ui;padding:8px 12px;border-radius:999px;border:1px solid var(--line,#ccc);background:#fff;cursor:pointer}
.file button.on{background:#111;color:#fff;border-color:#111}
.pan{display:none}.pan.on{display:block}
</style>"""
    but, pan = [], []
    for i, (cat, carduri) in enumerate(sec.items()):
        cid = CAT_ID.get(cat, cat)
        but.append(f'<button class="{"on" if i == 0 else ""}" data-p="{cid}">{cat} <span style="opacity:.55;font-weight:400">{len(carduri)}</span></button>')
        pan.append(f'<section class="cat-section pan {"on" if i == 0 else ""}" id="{cid}"><div class="cards-3">\n' + "\n".join(carduri) + "\n</div></section>")
    js = """<script>
document.querySelectorAll('.file button').forEach(function(b){b.onclick=function(){
  document.querySelectorAll('.file button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
  document.querySelectorAll('.pan').forEach(function(p){p.classList.toggle('on',p.id===b.dataset.p)});
  window.scrollTo({top:document.querySelector('.file').offsetTop-60,behavior:'smooth'});}});
</script>"""
    return css + '<div class="file">' + "".join(but) + "</div>" + "".join(pan) + js


def v2_coloane(sec):
    css = """<style>
.coloane{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
@media(max-width:980px){.coloane{grid-template-columns:repeat(2,1fr)}}
@media(max-width:620px){.coloane{grid-template-columns:1fr}}
.col{border:1px solid var(--line,#ddd);border-radius:14px;background:#fff;display:flex;flex-direction:column;height:78vh;min-height:520px}
.col h2{font-size:17px;margin:0;padding:12px 14px;border-bottom:1px solid var(--line,#ddd);display:flex;justify-content:space-between;align-items:center}
.col h2 span{font:600 12px system-ui;opacity:.55}
.col .lista{overflow:auto;padding:10px;scrollbar-width:thin}
.col .cards-3{grid-template-columns:1fr;gap:12px}
.col .card .dek{display:none}
</style>"""
    cols = []
    for cat, carduri in sec.items():
        cid = CAT_ID.get(cat, cat)
        cols.append(f'<div class="col" id="{cid}"><h2>{cat}<span>{len(carduri)}</span></h2><div class="lista"><div class="cards-3">\n' + "\n".join(carduri) + "\n</div></div></div>")
    return css + '<div class="coloane">' + "".join(cols) + "</div>"


def v3_flux(sec):
    toate = []
    for cat, carduri in sec.items():
        for c in carduri:
            toate.append((_data(c), cat, c))
    toate.sort(key=lambda x: x[0], reverse=True)
    css = """<style>
.chips{position:sticky;top:52px;z-index:50;background:var(--bg,#fff);display:flex;gap:6px;flex-wrap:wrap;padding:10px 0;border-bottom:1px solid var(--line,#ddd);margin:0 0 18px}
.chips button{font:700 13px system-ui;padding:7px 12px;border-radius:999px;border:1px solid var(--line,#ccc);background:#fff;cursor:pointer}
.chips button.on{background:#111;color:#fff;border-color:#111}
.flux .card.ascuns{display:none}
.maimult{display:block;margin:22px auto 0;font:700 15px system-ui;padding:12px 22px;border-radius:999px;border:1px solid #111;background:#fff;cursor:pointer}
</style>"""
    chips = ['<button class="on" data-c="*">Toate <span style="opacity:.55;font-weight:400">' + str(len(toate)) + "</span></button>"]
    for cat, carduri in sec.items():
        chips.append(f'<button data-c="{cat}">{cat} <span style="opacity:.55;font-weight:400">{len(carduri)}</span></button>')
    carduri = []
    for i, (_, cat, c) in enumerate(toate):
        c = c.replace('class="card"', f'class="card{" ascuns" if i >= 30 else ""}" data-cat="{cat}"', 1)
        carduri.append(c)
    js = """<script>
var LOT=30, filtru='*', aratate=LOT;
function redeseneaza(){var n=0;document.querySelectorAll('.flux .card').forEach(function(c){var ok=(filtru==='*'||c.dataset.cat===filtru);if(ok){n++;c.classList.toggle('ascuns',n>aratate)}else{c.classList.add('ascuns')}});
  document.querySelector('.maimult').style.display=(n>aratate)?'block':'none';}
document.querySelectorAll('.chips button').forEach(function(b){b.onclick=function(){document.querySelectorAll('.chips button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');filtru=b.dataset.c;aratate=LOT;redeseneaza();}});
document.querySelector('.maimult').onclick=function(){aratate+=LOT;redeseneaza();};
</script>"""
    return (css + '<div class="chips">' + "".join(chips) + '</div><section class="cat-section flux" id="flux"><div class="cards-3">\n'
            + "\n".join(carduri) + '\n</div></section><button class="maimult">Încă 30 →</button>' + js)


def v4_compact(sec):
    css = """<style>
.restul{columns:2;column-gap:28px;margin:16px 0 0;padding:0;list-style:none;font-size:14.5px;line-height:1.4}
@media(max-width:620px){.restul{columns:1}}
.restul li{break-inside:avoid;padding:7px 0;border-bottom:1px solid var(--line,#eee)}
.restul a{text-decoration:none;color:inherit}
.restul span{color:var(--ink-faint,#888);font-size:12px;margin-left:6px}
details.mai summary{cursor:pointer;font:700 14px system-ui;padding:10px 0;color:var(--ink-soft,#444)}
</style>"""
    out = []
    for cat, carduri in sec.items():
        cid = CAT_ID.get(cat, cat)
        primele, restul = carduri[:6], carduri[6:]
        lista = "".join(f'<li><a href="{_href(c)}">{html.escape(_titlu(c))}</a><span>{_data(c)}</span></li>' for c in restul)
        rest_html = (f'<details class="mai"><summary>Încă {len(restul)} din {cat} ▾</summary><ul class="restul">{lista}</ul></details>' if restul else "")
        out.append(f'<section class="cat-section" id="{cid}"><div class="section-head"><h2>{cat}</h2><a class="tot" href="{cid}.html" style="font-size:13px;margin-left:auto;align-self:center">Toate din {cat} →</a></div><div class="cards-3">\n'
                   + "\n".join(primele) + "\n</div>" + rest_html + "</section>")
    return css + "".join(out)


def main():
    s = open(IDX, encoding="utf-8").read()
    sec = _sectiuni(s)
    variante = {"_v0.html": None, "_v1.html": v1_file(sec), "_v2.html": v2_coloane(sec),
                "_v3.html": v3_flux(sec), "_v4.html": v4_compact(sec)}
    for fis, corp in variante.items():
        h = s if corp is None else _inlocuieste_main(s, corp)
        h = h.replace('<meta name="robots"', '<meta name="robots" content="noindex,nofollow"><meta name="x-vechi-robots"', 1)
        h = h.replace("</body>", _bara(fis) + "</body>", 1)
        open(os.path.join(ROOT, fis), "w", encoding="utf-8").write(h)
        print("scris", fis, len(h) // 1024, "KB")
    print("categorii:", {c: len(v) for c, v in sec.items()})


if __name__ == "__main__":
    main()

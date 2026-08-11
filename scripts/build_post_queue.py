"""
Lista de postat — pentru postarea MANUALĂ pe X.

API-ul X a trecut în februarie 2026 la plată per acțiune: $0,20 pentru o
postare care conține un link. La ritmul site-ului ar fi însemnat ~$126/lună,
ca să torni conținut într-un cont pe care postările iau 1-19 vizualizări.
Fondatorul postează manual; treaba noastră e să dureze zece secunde.

Pagina stă la rădăcină ca s-o poți deschide de pe telefon, dar are noindex
și e blocată în robots.txt. Nu e secretă — conține doar articole publice.
"""

import glob
import html
import json
import os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "de-postat.html")
SITE = "https://farabaliverne.ro"

ZILE = 2           # câte zile în urmă luăm
LIMITA_X = 280     # limita clasică; conturile verificate pot mai mult

VERDICT_TEXT = {
    "probat": ("Se probează", "ok"),
    "contrazis": ("Nu se susține", "bad"),
}


def verdict(d):
    v = (d.get("mainVerdict") or "").lower()
    for cheie, (text, cls) in VERDICT_TEXT.items():
        if cheie in v:
            return text, cls
    return "Surse în dezacord", "warn"


def taie(s, n):
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def numaratoare(d):
    """„3 probate · 1 contestată" — informația proprie site-ului, scurtă."""
    np_ = len(d.get("probat") or [])
    nc_ = len(d.get("contestat") or [])
    parti = []
    if np_:
        parti.append(f"{np_} {'probată' if np_ == 1 else 'probate'}")
    if nc_:
        parti.append(f"{nc_} {'contestată' if nc_ == 1 else 'contestate'}")
    return " · ".join(parti)


def compune(d):
    """
    Titlul, apoi verdictul cu numărul de afirmații verificate, apoi linkul.

    Când titlul e scurt și mai rămâne loc, adăugăm și o frază din dek. Când nu,
    numărătoarea singură spune ceva concret — „3 probate · 1 contestată" e mai
    util decât un „Se probează" sec.

    Fără hashtag-uri: pe română aduc aproape nimic și fac postarea să arate a
    marketing, exact opusul poziționării.
    """
    link = f"{SITE}/a/{d['slug']}.html"
    vtext, _ = verdict(d)
    titlu = d.get("title", "").strip()

    nums = numaratoare(d)
    linia2 = f"{vtext} · {nums}" if nums else vtext

    # linkul ocupă 23 de caractere pe X, oricât ar fi de lung
    spatiu = LIMITA_X - 23 - 4
    ramas = spatiu - len(titlu) - len(linia2) - 2

    parti = [titlu, linia2]
    if ramas > 60:
        dek = taie(d.get("dek", ""), ramas - 2)
        if dek:
            parti.insert(1, dek)
    parti.append(link)
    return "\n\n".join(parti)


# Ordinea în care le arătăm: o demontare se dă mai departe mult mai ușor decât
# confirmarea unei știri de rutină. Fondatorul postează 2-3 pe zi, deci primele
# din listă trebuie să fie cele care merită postate.
PRIORITATE = {"bad": 0, "warn": 1, "ok": 2}


def main():
    limita = (datetime.now() - timedelta(days=ZILE)).strftime("%Y-%m-%d")
    arts = []
    for p in glob.glob(os.path.join(ROOT, "data", "*.json")):
        if os.path.basename(p).startswith("_"):
            continue
        d = json.load(open(p, encoding="utf-8"))
        if not d.get("slug") or not os.path.exists(
                os.path.join(ROOT, "a", d["slug"] + ".html")):
            continue
        if (d.get("date") or "") >= limita:
            arts.append(d)

    arts.sort(key=lambda d: (PRIORITATE.get(verdict(d)[1], 3),
                             -int((d.get("date") or "0").replace("-", "")),
                             d.get("slug", "")))

    carduri = []
    for d in arts:
        text = compune(d)
        vtext, vcls = verdict(d)
        thumb = os.path.join(ROOT, "img", "carduri", d["slug"] + ".jpg")
        poza = (f'<img src="img/carduri/{d["slug"]}.jpg" alt="" loading="lazy">'
                if os.path.exists(thumb)
                else '<div class="fara-poza">fără poză</div>')
        carduri.append(f"""      <article class="post">
        <div class="shot">{poza}</div>
        <div class="body">
          <div class="row">
            <span class="chip {vcls}">{html.escape(vtext)}</span>
            <span class="cat">{html.escape(d.get("category", ""))}</span>
            <span class="data">{html.escape(d.get("date", ""))}</span>
          </div>
          <pre class="text">{html.escape(text)}</pre>
          <div class="actiuni">
            <button class="copy" data-text="{html.escape(text)}">Copiază textul</button>
            <a class="deschide" href="{SITE}/a/{d['slug']}.html" target="_blank"
               rel="noopener">Vezi articolul</a>
            <span class="lung">{len(text) - len(SITE) - len(d['slug']) - 10 + 23} caractere</span>
          </div>
        </div>
      </article>""")

    HTML = f"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>De postat pe X — Fără Baliverne</title>
<style>
  :root{{
    --bg:#f2f3ef; --card:#fff; --ink:#1a1d1a; --soft:#5a625a; --faint:#8f978f;
    --line:#dfe3dd; --accent:#a5372a;
    --ok:#2f8a49; --warn:#c2861a; --bad:#a5372a;
  }}
  @media (prefers-color-scheme:dark){{
    :root:not([data-theme="light"]){{
      --bg:#14161a; --card:#1c2026; --ink:#e6eae6; --soft:#a8b2a8; --faint:#7c857c;
      --line:#2a3038; --accent:#e08a7a;
      --ok:#54c47c; --warn:#e0ac45; --bad:#e07a6a;
    }}
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.55 ui-serif,"Iowan Old Style",Georgia,serif}}
  .wrap{{max-width:760px;margin:0 auto;padding:28px 18px 70px}}
  header{{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:22px}}
  h1{{font-size:26px;margin:0 0 6px}}
  .sum{{color:var(--soft);font-size:14.5px;margin:0}}
  .post{{display:grid;grid-template-columns:120px 1fr;gap:14px;background:var(--card);
    border:1px solid var(--line);border-radius:4px;overflow:hidden;margin-bottom:12px}}
  .shot{{background:#0d0f12;position:relative;min-height:120px}}
  .shot img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
  .fara-poza{{position:absolute;inset:0;display:flex;align-items:center;
    justify-content:center;color:#7c857c;font:600 11px ui-monospace,Menlo,monospace}}
  .body{{padding:12px 14px 13px;min-width:0}}
  .row{{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}}
  .chip{{font:700 10.5px ui-monospace,Menlo,monospace;letter-spacing:.05em;
    text-transform:uppercase;padding:3px 7px;border-radius:3px;color:#fff}}
  .chip.ok{{background:var(--ok)}} .chip.warn{{background:var(--warn)}}
  .chip.bad{{background:var(--bad)}}
  .cat,.data{{font:600 11px ui-monospace,Menlo,monospace;color:var(--faint);
    letter-spacing:.04em;text-transform:uppercase}}
  .text{{font:14px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;
    word-break:break-word;margin:0 0 10px;color:var(--ink)}}
  .actiuni{{display:flex;gap:9px;align-items:center;flex-wrap:wrap}}
  button.copy{{font:700 13px ui-sans-serif,system-ui;padding:8px 14px;border:none;
    border-radius:8px;background:#000;color:#fff;cursor:pointer}}
  button.copy:hover{{opacity:.85}}
  button.copy.gata{{background:var(--ok)}}
  .deschide{{font:600 13px ui-sans-serif,system-ui;color:var(--accent);
    text-decoration:none;border-bottom:1px solid currentColor}}
  .lung{{font:11.5px ui-monospace,Menlo,monospace;color:var(--faint);margin-left:auto}}
  @media(max-width:560px){{.post{{grid-template-columns:1fr}}.shot{{min-height:150px}}}}
</style></head><body>
<div class="wrap">
  <header>
    <h1>De postat pe X</h1>
    <p class="sum">{len(arts)} articole din ultimele {ZILE} zile, ordonate după cât de
      bine se dau mai departe — demontările primele, confirmările de rutină la urmă.
      Copiezi, lipești, postezi. Linkul aduce singur poza și titlul; nu adăuga
      imagine separat.</p>
  </header>
{chr(10).join(carduri) if carduri else '  <p>Niciun articol nou.</p>'}
</div>
<script>
document.querySelectorAll("button.copy").forEach(function(b){{
  b.addEventListener("click", function(){{
    navigator.clipboard.writeText(b.dataset.text).then(function(){{
      var vechi = b.textContent;
      b.textContent = "Copiat";
      b.classList.add("gata");
      setTimeout(function(){{ b.textContent = vechi; b.classList.remove("gata"); }}, 1600);
    }});
  }});
}});
</script>
</body></html>
"""

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(HTML)

    print(f"{len(arts)} articole din ultimele {ZILE} zile")
    print(f"scris: {OUT}")


if __name__ == "__main__":
    main()

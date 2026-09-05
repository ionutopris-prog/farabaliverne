#!/usr/bin/env python3
"""
Generează a/<slug>.html din data/<slug>.json, după șablonul articolului etalon.

De ce există: până acum fiecare articol se scria de mână — 757 de linii de HTML
per bucată. Redactorul din CI își consuma bugetul de tururi pe HTML, nu pe
verificare, și pica. Aici HTML-ul e mecanic; redactorul scrie doar JSON-ul.

  python3 scripts/scrie_articol.py <slug> [<slug> ...]
"""
import json, re, sys, html
from pathlib import Path

ROOT = Path(__file__).parent.parent
SABLON = ROOT / "a" / "legea-integritatii-vot-final.html"
BAZA = "https://farabaliverne.ro"

# 🔴 Trebuie sa contina TOATE categoriile din build_site.CAT_ORDER. Cand am
# adaugat „Minți luminate" pe 5 septembrie 2026, am pus pictograma doar in
# build_site.py si am uitat aici — articolele au iesit cu globul de la „Extern",
# adica valoarea implicita. Se vede doar cand articolul n-are poza, deci e usor
# de ratat. Daca se mai adauga o categorie, se adauga in AMANDOUA locurile.
GLYPH = {"Politică": "🏛️", "Economie": "📊", "Extern": "🌍", "Știință": "🔬",
         "Minți luminate": "💡", "Media de stat": "📡", "Social": "👥", "Sport": "⚽"}

def e(s):
    return html.escape(str(s or ""), quote=True)

def surse(lst):
    if not lst:
        return ""
    a = "\n".join(
        f'            <a href="{e(s["url"])}" target="_blank" rel="noopener noreferrer">'
        f'<span class="fav" style="background:#556050"></span>'
        f'<span class="lbl">{e(s["name"])}</span></a>' for s in lst)
    return f'          <div class="ev-sources">\n{a}\n          </div>\n'

def itemi(lst):
    out = []
    for it in lst or []:
        out.append(f'        <div class="ev-item">\n          <p>{e(it["text"])}</p>\n'
                   f'{surse(it.get("sources"))}        </div>')
    return "\n".join(out)

def sectiune(cls, titlu, sub, corp):
    return (f'      <section class="ev-block {cls}">\n        <h2>{titlu}</h2>\n'
            f'        <p class="ev-sub">{sub}</p>\n{corp}\n      </section>\n\n')

def main_block(d):
    slug, cat = d["slug"], d.get("category", "Extern")
    np, nc, no = len(d.get("probat") or []), len(d.get("contestat") or []), len(d.get("opinie") or [])
    segs = [f'<span class="seg ok">✔ {np} probate</span>']
    if nc:
        segs.append(f'<span class="seg warn">⚠ {nc} contestate</span>')
    if no:
        segs.append(f'<span class="seg op">✎ {no} opinie</span>')
    badge = ' <span style="color:var(--line-2)">·</span> '.join(segs)

    # 🔴 Poza articolului sta in JSON, nu direct in HTML.
    # Motivul: pagina se REGENEREAZA din JSON la fiecare build. O poza lipita
    # in HTML ar disparea la prima reconstructie, tacut. Uneltele de cautare
    # (article_image.py / pick_image.py) tiparesc `img_html` si
    # `figcaption_html`; alea se salveaza aici, in campul `poza`, si supravietuiesc.
    _pz = d.get("poza") or {}
    poza_img = (_pz.get("img_html", "") + "\n              ") if _pz.get("img_html") else ""
    poza_credit = ("\n" + _pz["figcaption_html"]) if _pz.get("figcaption_html") else ""

    h = [f'''  <main>
    <div class="wrap" style="max-width:860px">

      <a href="../index.html" class="backlink">← Înapoi la prima pagină</a>

      <article>
        <div class="article-head">
            <div class="photo g-hero">
              <div class="art">
                <div class="pattern"><svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><defs><pattern id="p-{slug}" width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(25)"><path d="M0 12 H24 M12 0 V24" stroke="#fff" stroke-width="1" opacity="0.25"/></pattern></defs><rect width="100%" height="100%" fill="url(#p-{slug})"/></svg></div>
                <div class="glyph">{GLYPH.get(cat, "🌍")}</div>
              </div>
              {poza_img}<div class="grad"></div>
              <div class="imgtag">Verificare Fără Baliverne</div>
              <div class="cat-pill">{e(cat)}</div>
            </div>{poza_credit}
          <div class="abody">
            <div class="eyebrow">
              <span class="cat-tag">{e(cat)}</span>
            </div>
            <h1>{e(d["title"])}</h1>
            <p class="dek">{e(d["dek"])}</p>
            <div class="verdict-row">
              <div class="report-badge lg">{badge}</div>
              <span class="chip soft ok sm">unde bat probele: {e(d.get("mainVerdict", ""))}</span>
            </div>
            <div class="meta">
              <span class="src"><span class="fav" style="background:#1c3f66"></span> {e(d.get("source",""))}</span>
              <span>·</span>
              <span>{e(d.get("date",""))}</span>
              <span>·</span>
              <a href="{e(d.get("url",""))}" target="_blank" rel="noopener noreferrer" class="ext">Articol sursă original</a>
            </div>
          </div>
        </div>

      <a class="src-cite" href="{e(d.get("url",""))}" target="_blank" rel="noopener noreferrer" style="display:flex;gap:0;align-items:stretch;text-decoration:none;border:1px solid var(--line-2);background:var(--card);border-radius:14px;overflow:hidden;margin:2px 0 26px;box-shadow:var(--shadow);transition:box-shadow .2s,transform .2s" onmouseover="this.style.boxShadow='var(--shadow-hi)';this.style.transform='translateY(-2px)'" onmouseout="this.style.boxShadow='var(--shadow)';this.style.transform='none'"><span style="flex:0 0 8px;background:var(--accent)"></span><span style="display:flex;flex-direction:column;justify-content:center;gap:4px;padding:14px 18px;min-width:0"><span style="font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint);font-weight:800">Sursă originală · {e(d.get("source",""))}</span><span style="font-size:15.5px;color:var(--ink);line-height:1.32;font-weight:600">„{e(d["title"])}”</span><span style="font-size:13px;color:var(--accent);font-weight:800;margin-top:2px">Citește știrea originală →</span></span></a>

<!-- AUTO:titluri:start -->
<!-- AUTO:titluri:end -->

''']
    # 🔴 Traducerea integrala a textului original — camp folosit de sectiunea
    # „Minti luminate" (5 septembrie 2026, cererea fondatorului: „vreau sa
    # publici tot articolul, nu doar rezumat").
    #
    # Se pune INAINTEA verificarii, dinadins: cititorul primeste intai textul
    # intreg al celor care au facut cercetarea, si abia apoi ce am verificat noi
    # peste el. Invers ar insemna sa-i spunem ce sa creada inainte sa citeasca.
    #
    # 🔴 SE FOLOSESTE DOAR cand sursa permite EXPLICIT reproducerea. Cornell
    # Chronicle o permite, scris in nota lor de copyright: „Permission is granted
    # to excerpt or reprint any of this material in news or information media".
    # Fara o astfel de permisiune, campul ramane gol si se scrie rezumat —
    # regula veche pentru „Extern" ramane in picioare.
    # Imaginile NU se preiau niciodata: la Cornell, pozele sunt separat protejate.
    if d.get("traducere"):
        t = d["traducere"]
        cap = e(t.get("titlu", d["title"]))
        semnatura = " · ".join(x for x in (t.get("publicatie"), t.get("autor"), t.get("data")) if x)
        pars = "\n".join(f"        <p>{e(x)}</p>" for x in t.get("paragrafe", []) if str(x).strip())
        # 🔴 Fiecare publicatie are ALTE conditii de republicare, iar ele
        # se respecta la litera, nu aproximativ. Cornell cere doar sa fii
        # „news or information media". MIT News cere anume: sus titlul,
        # subtitlul, SEMNATURA AUTORULUI si mentiunea „MIT News" cu link la
        # original; jos, exact cuvintele „Reprinted with permission of MIT
        # News" plus link catre news.mit.edu. De aceea notele sunt campuri,
        # nu text fix in cod.
        url_o = e(t.get("url", d.get("url", "")))
        sus = t.get("nota_sus") or ("Text tradus în română și reprodus cu permisiunea "
                                    "din nota de copyright a publicației.")
        jos = t.get("nota_jos")
        subsol = (f'\n        <p class="nota-republicare">{e(jos)}</p>' if jos else "")
        h.append(
            '      <section class="ev-block traducere">\n'
            f'        <h2>📄 Articolul original, tradus integral</h2>\n'
            f'        <p class="ev-sub">„{cap}” — {e(semnatura)}. {e(sus)} '
            f'<a href="{url_o}" target="_blank" rel="noopener noreferrer">Originalul, în engleză →</a></p>\n'
            f'{pars}{subsol}\n      </section>\n\n')

    h.append(sectiune("probat", "✅ Se probează",
                      "Afirmații susținute de surse verificabile.", itemi(d.get("probat"))))
    if nc:
        h.append(sectiune("neverificabil", "⚠️ Contestat / neclar",
                          "Puncte unde sursele diferă sau unde formularea inițială era imprecisă.",
                          itemi(d.get("contestat"))))
    if no:
        op = "\n".join(f'        <div class="opinie-item">{e(o["text"] if isinstance(o, dict) else o)}</div>'
                       for o in d["opinie"])
        h.append(f'      <section class="ev-block opinie">\n        <h2>💬 Opinie, nu fapt</h2>\n'
                 f'        <p class="ev-sub">Interpretări, etichete și judecăți de valoare — separate explicit de fapte.</p>\n'
                 f'{op}\n      </section>\n\n')
    if d.get("aiNote"):
        par = "\n".join(f"        <p>{e(p)}</p>" for p in str(d["aiNote"]).split("\n") if p.strip())
        h.append(f'      <section class="ai-note">\n        <h2>🤖 Nota AI</h2>\n{par}\n      </section>\n\n')
    if d.get("math"):
        m = d["math"]
        t = m.get("title", "🧮 Cifrele, verificate") if isinstance(m, dict) else "🧮 Cifrele, verificate"
        b = m.get("text", "") if isinstance(m, dict) else m
        h.append(f'      <section class="math-block">\n        <h2>{e(t)}</h2>\n        <p>{e(b)}</p>\n      </section>\n\n')
    h.append('''        <div class="conclusion-box">
          <div class="glyph">💧</div>
          <h3>Noi am turnat apa... concluzia e a ta.</h3>
          <p>Am pus alături ce se probează cu surse și ce rămâne contestat, neclar sau opinie. Verifică sursele, cântărește dovezile — tragi tu linia între fapt și interpretare.</p>
          <a href="../index.html" class="backlink">← Înapoi la prima pagină</a>
        </div>
      </article>

    </div>
  </main>''')
    return "".join(h)

def scrie(slug):
    d = json.loads((ROOT / "data" / f"{slug}.json").read_text(encoding="utf-8"))
    s = SABLON.read_text(encoding="utf-8")
    url = f"{BAZA}/a/{slug}.html"
    tit = f'{d["title"]} — Fără Baliverne'
    s = re.sub(r"<title>.*?</title>", lambda _: f"<title>{e(tit)}</title>", s, count=1, flags=re.S)
    s = re.sub(r'(<link rel="canonical" href=")[^"]*(">)', lambda m: m.group(1)+url+m.group(2), s, count=1)
    s = re.sub(r'(<meta property="og:url" content=")[^"]*(">)', lambda m: m.group(1)+url+m.group(2), s, count=1)
    for k in ("og:title", "twitter:title"):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(">)',
                   lambda m: m.group(1)+e(tit)+m.group(2), s, count=1)
    for k in ("description", "og:description", "twitter:description"):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(">)',
                   lambda m: m.group(1)+e(d["dek"][:300])+m.group(2), s, count=1)
    # Poza de partajare: a articolului, nu a șablonului. build_site.py o
    # rescrie oricum, dar dacă rămâne cea a șablonului, un share făcut între
    # generare și build arată cardul altui articol.
    card = f"{BAZA}/img/share/{slug}.jpg"
    for k in ("og:image", "twitter:image"):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(">)',
                   lambda m: m.group(1)+card+m.group(2), s, count=1)
    # Datele structurate ale șablonului: le scoatem, build_site.py le regenerează
    # din JSON. Lăsate așa, ar declara pe fiecare articol nou titlul altuia.
    s = re.sub(r'\s*<script type="application/ld\+json">.*?</script>', "", s, count=1, flags=re.S)
    s = re.sub(r"  <main>.*?  </main>", lambda _: main_block(d), s, count=1, flags=re.S)
    (ROOT / "a" / f"{slug}.html").write_text(s, encoding="utf-8")
    print(f"✓ a/{slug}.html ({len(s)} octeți)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("folosire: scrie_articol.py <slug> [<slug> ...]"); sys.exit(1)
    for sl in sys.argv[1:]:
        scrie(sl)

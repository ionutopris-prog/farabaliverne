#!/usr/bin/env python3
"""
Generează câte o pagină pe farabaliverne.ro pentru fiecare parlamentar:
`parlamentar/<slug>.html`, din `data/_parlament.json` + `data/_fise.json`.

Principiul casei, aplicat la o pagină de persoană: arătăm ce e documentat, cu
sursa alături, şi NU dăm note. Cifrele de activitate stau brute — un număr mare
de iniţiative nu înseamnă nici bine, nici rău, iar noi nu clasăm oameni.

Ce lipseşte şi de ce, scris pe pagină: numărul de voturi cu care a intrat (în
România se votează pe listă de partid, nu pe om, deci nu există „voturile lui")
şi dosarele penale (cer sursă judiciară verificată, nu presă — vezi nota din
pagină).

    python3 scripts/build_parlamentari.py
"""
import html, json, os, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCURT = {"Partidului Social Democrat": "PSD", "AUR": "AUR",
         "Partidului Naţional Liberal": "PNL", "Uniunii Salvaţi România": "USR",
         "Uniunii Democrate Maghiare din România": "UDMR", "Uniţi pentru România": "UPR",
         "minorităţilor naţionale": "Minorități", "Deputaţi neafiliaţi": "Neafiliați",
         "Senatori neafiliati": "Neafiliați", "SOS România": "SOS", "PACE - Întâi Romania": "PACE"}
CULORI = {"PSD": "#c0392b", "AUR": "#1f3a63", "PNL": "#d8a72b", "USR": "#2f7fc1",
          "UDMR": "#3f8f3f", "UPR": "#7a5c9e", "Minorități": "#8a8f83",
          "Neafiliați": "#b0b6aa", "SOS": "#6d4a8f", "PACE": "#2e8b6f"}


def e(x):
    return html.escape(str(x or ""))


def fara(n):
    return "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")


def slug(n):
    return re.sub(r"[^a-z0-9]+", "-", fara(n).lower()).strip("-")


def scurt(g):
    g = g.replace("Grupul parlamentar ", "")
    for p in ("al ", "ale "):
        if g.startswith(p):
            g = g[len(p):]
    return SCURT.get(g, g[:14])


def verificari_despre(nume):
    """Articolele noastre în care apare persoana. Legătura dintre secţiunea asta
    şi produsul principal: scaunul duce la om, omul duce la ce am verificat."""
    cheie = fara(nume).lower().split()
    inv = " ".join(reversed(cheie))          # fişele au „Nume Prenume", articolele invers
    out = []
    for f in os.listdir(os.path.join(ROOT, "data")):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        try:
            d = json.load(open(os.path.join(ROOT, "data", f), encoding="utf-8"))
        except Exception:
            continue
        for p in (d.get("persoane") or []):
            if fara(p).lower() in (" ".join(cheie), inv):
                out.append({"slug": d["slug"], "titlu": d.get("title", ""),
                            "data": d.get("date", ""), "verdict": d.get("mainVerdict", ""),
                            "dek": d.get("dek", "")[:220]})
                break
    return sorted(out, key=lambda x: x["data"], reverse=True)


def lista(titlu, elemente, gol=None):
    if not elemente:
        return f'<div class="pp-gol">{e(gol)}</div>' if gol else ""
    return ("<ul class='pp-lista'>" +
            "".join(f"<li>{e(x)}</li>" for x in elemente) + "</ul>")


def pagina(om, f, art, invelis):
    grup = scurt(om["grup"])
    culoare = CULORI.get(grup, "#8a8f83")
    rol = "Deputat" if om["camera"] == "Camera Deputaților" else "Senator"
    circ = om.get("circumscriptie") or "la nivel naţional"
    a = (f or {}).get("activitate", {})
    lk = (f or {}).get("linkuri", {})

    cifre = []
    for cheie, eticheta in (("luari", "luări de cuvânt"), ("propuneri", "propuneri legislative"),
                            ("promulgate", "devenite legi"), ("intrebari", "întrebări și interpelări"),
                            ("motiuni", "moțiuni semnate")):
        if cheie in a:
            cifre.append(f'<div class="pp-cifra"><b>{a[cheie]}</b><span>{eticheta}</span></div>')

    verif = ""
    if art:
        randuri = "".join(
            f'<div class="pp-verif"><div class="pp-vr"><span class="pp-verdict">{e(x["verdict"])}</span>'
            f'<span class="pp-data">{e(x["data"])}</span></div>'
            f'<a href="../a/{e(x["slug"])}.html"><b>{e(x["titlu"])}</b></a>'
            f'<p>{e(x["dek"])}</p></div>' for x in art)
        verif = (f'<section class="pp-sec"><h2>Ce am verificat despre {e(om["nume"].split()[0])}</h2>'
                 f'<p class="pp-sub">Verdictul e despre <b>afirmație</b>, niciodată despre om.</p>'
                 f'{randuri}</section>')
    else:
        verif = ('<section class="pp-sec"><h2>Ce am verificat</h2>'
                 '<div class="pp-gol">Nicio verificare încă. Când o afirmație de-a lui ajunge '
                 'sub lupă, apare aici.</div></section>')

    m = f'''  <main>
    <div class="wrap" style="max-width:1040px">
      <a href="../parlament.html" class="backlink">← Înapoi în hemiciclu</a>

      <div class="pp-cap">
        <span class="pp-grup" style="background:{culoare}">{e(grup)}</span>
        <span class="pp-rol">{rol} · {e(circ)}</span>
        <h1>{e(om["nume"])}</h1>
        <div class="pp-meta">
          {'<span><b>Născut:</b> ' + e(f.get("nascut")) + '</span>' if f and f.get("nascut") else ''}
          {'<span><b>Mandat validat:</b> ' + e(f.get("validat")) + '</span>' if f and f.get("validat") else ''}
          {'<span><b>Contact:</b> <a href="mailto:' + e(f.get("email")) + '">' + e(f.get("email")) + '</a></span>' if f and f.get("email") else ''}
        </div>
      </div>

      <div class="pp-doua">
        <div>
          {verif}

          <section class="pp-sec">
            <h2>Activitatea în mandat</h2>
            <p class="pp-sub">Cifre luate din evidența oficială, arătate brut. Nu le interpretăm —
              multe inițiative nu înseamnă nici bine, nici rău.</p>
            <div class="pp-cifre">{"".join(cifre) or '<div class="pp-gol">Fără cifre publicate încă.</div>'}</div>
          </section>

          <section class="pp-sec">
            <h2>Comisii</h2>
            {lista("", (f or {}).get("comisii", []), "Nicio comisie permanentă listată.")}
            {('<h3 class="pp-h3">Comisii speciale</h3>' + lista("", f["comisii_speciale"])) if f and f.get("comisii_speciale") else ''}
          </section>
        </div>

        <aside>
          <section class="pp-box">
            <h2>Birou parlamentar</h2>
            {lista("", (f or {}).get("birouri", []), "Nu are birou declarat pe fișa oficială.")}
          </section>

          <section class="pp-box">
            <h2>Documente oficiale</h2>
            <ul class="pp-lista pp-lk">
              <li><a href="{e(om["fisa"])}" target="_blank" rel="noopener">Fișa pe cdep.ro ↗</a></li>
              {'<li><a href="' + e(lk.get("cv")) + '" target="_blank" rel="noopener">Curriculum Vitae ↗</a></li>' if lk.get("cv") else ''}
              {'<li><a href="' + e(lk.get("avere")) + '" target="_blank" rel="noopener">Declarația de avere ↗</a></li>' if lk.get("avere") else ''}
              {'<li><a href="' + e(lk.get("interese")) + '" target="_blank" rel="noopener">Declarația de interese ↗</a></li>' if lk.get("interese") else ''}
              {'<li><a href="' + e(lk.get("vot")) + '" target="_blank" rel="noopener">Cum a votat electronic ↗</a></li>' if lk.get("vot") else ''}
            </ul>
          </section>

          {('<section class="pp-box"><h2>Grupul parlamentar</h2><p class="pp-mic">' + e(f["grup_istoric"]) + '</p></section>') if f and f.get("grup_istoric") else ''}

          <section class="pp-box pp-lipsa">
            <h2>Ce nu găsești aici</h2>
            <p class="pp-mic"><b>Câte voturi a luat.</b> În România se votează pe listă de partid,
              nu pe persoană — nu există „voturile lui" de publicat.</p>
            <p class="pp-mic"><b>Dosare penale sau condamnări.</b> Le punem doar cu document
              judiciar verificat, nu din presă. Până atunci, tăcem — o acuzație greșită
              despre un om cu nume e exact greșeala pe care o vânăm la alții.</p>
          </section>
        </aside>
      </div>
    </div>
  </main>'''
    s = re.sub(r"(?is)  <main>.*?  </main>", lambda _: m, invelis, count=1)
    s = s.replace("</style>", STIL + "</style>", 1)
    titlu = f'{om["nume"]} — {rol} {grup}, {circ} — Fără Baliverne'
    s = re.sub(r"(?is)<title>.*?</title>", lambda _: f"<title>{e(titlu)}</title>", s, count=1)
    url = f"https://farabaliverne.ro/parlamentar/{slug(om['nume'])}.html"
    s = s.replace('<link rel="canonical" href="https://farabaliverne.ro/">',
                  f'<link rel="canonical" href="{url}">')
    s = s.replace('<meta property="og:url" content="https://farabaliverne.ro/">',
                  f'<meta property="og:url" content="{url}">')
    dek = (f'{om["nume"]}, {rol.lower()} {grup} de {circ}. Ce e documentat despre el din surse '
           f'publice: activitate în mandat, comisii, birou parlamentar, declarații de avere '
           f'— și verificările Fără Baliverne.')
    for k in ("description", "og:description", "twitter:description"):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(">)',
                   lambda mm: mm.group(1) + e(dek) + mm.group(2), s, count=1)
    # legăturile relative urcă un nivel — pagina stă în parlamentar/
    s = re.sub(r'href="(?!http|#|mailto|\.\./)([a-z0-9\-]+\.html)"', r'href="../\1"', s)
    s = re.sub(r'(src|href)="(?!http|#|data:|\.\./)(img/|assets/|favicon|apple-touch|site\.web)',
               r'\1="../\2', s)
    return s


STIL = '''
/* ─── pagina unui parlamentar ─────────────────────────────────── */
.pp-cap{margin:0 0 20px}
.pp-grup{display:inline-block;padding:4px 12px;border-radius:30px;color:#fff;font-size:12.5px;
         font-weight:800;letter-spacing:.02em}
.pp-rol{font-size:13px;color:var(--ink-faint);margin-left:10px}
.pp-cap h1{font-family:var(--serif);font-size:36px;line-height:1.1;margin:10px 0 10px;letter-spacing:-.02em}
.pp-meta{display:flex;gap:22px;flex-wrap:wrap;font-size:14px;color:var(--ink-soft)}
.pp-meta b{color:var(--ink);font-weight:700}
.pp-doua{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:16px;align-items:start}
.pp-sec,.pp-box{background:var(--card);border:1px solid var(--line);border-radius:16px;
                box-shadow:var(--shadow);padding:20px 22px;margin-bottom:16px}
.pp-sec h2{font-family:var(--serif);font-size:21px;margin:0 0 4px;letter-spacing:-.01em}
.pp-box h2{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);
           font-weight:800;margin:0 0 10px}
.pp-h3{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);
       font-weight:800;margin:14px 0 6px}
.pp-sub{margin:0 0 14px;font-size:13.5px;color:var(--ink-faint);line-height:1.5}
.pp-lista{margin:0;padding:0;list-style:none}
.pp-lista li{padding:8px 0;border-bottom:1px solid var(--line);font-size:14.5px;line-height:1.45}
.pp-lista li:last-child{border-bottom:none}
.pp-lk li{border-bottom:none;padding:5px 0}
.pp-gol{font-size:14px;color:var(--ink-faint);font-style:italic;line-height:1.5}
.pp-cifre{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px}
.pp-cifra{background:var(--paper-2);border:1px solid var(--line);border-radius:11px;padding:13px 14px}
.pp-cifra b{display:block;font-family:var(--serif);font-size:26px;line-height:1;margin-bottom:5px}
.pp-cifra span{font-size:12px;color:var(--ink-soft);line-height:1.35}
.pp-verif{border-top:1px solid var(--line);padding:13px 0}
.pp-vr{display:flex;gap:9px;align-items:center;margin-bottom:5px;flex-wrap:wrap}
.pp-verdict{padding:3px 10px;border-radius:30px;font-size:11.5px;font-weight:800;
            background:var(--paper-2);border:1px solid var(--line-2);color:var(--ink-soft)}
.pp-data{font-size:12.5px;color:var(--ink-faint)}
.pp-verif a{font-size:15.5px;line-height:1.4}
.pp-verif p{margin:4px 0 0;font-size:13.5px;color:var(--ink-soft);line-height:1.5}
.pp-mic{font-size:13.5px;line-height:1.55;color:var(--ink-soft);margin:0 0 9px}
.pp-mic:last-child{margin-bottom:0}
.pp-lipsa{background:var(--paper-2)}
@media (max-width:860px){.pp-doua{grid-template-columns:1fr}.pp-cap h1{font-size:27px}}
'''


def main():
    oameni = json.load(open(os.path.join(ROOT, "data", "_parlament.json"), encoding="utf-8"))["oameni"]
    try:
        fise = {f["id"] + f["camera"]: f for f in
                json.load(open(os.path.join(ROOT, "data", "_fise.json"), encoding="utf-8"))["fise"]}
    except Exception:
        fise = {}
    invelis = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    os.makedirs(os.path.join(ROOT, "parlamentar"), exist_ok=True)
    n_art = 0
    for om in oameni:
        art = verificari_despre(om["nume"])
        n_art += len(art)
        s = pagina(om, fise.get(om["id"] + om["camera"]), art, invelis)
        open(os.path.join(ROOT, "parlamentar", slug(om["nume"]) + ".html"), "w",
             encoding="utf-8").write(s)
    print(f"scrise: {len(oameni)} pagini în parlamentar/ · {n_art} legături către verificări")


if __name__ == "__main__":
    main()

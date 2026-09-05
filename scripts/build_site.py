#!/usr/bin/env python3
"""
Build-system Fără Baliverne — regenerează din datele articolelor:
  1. Feed-ul de pe homepage (secțiunile pe categorii) între marcajele AUTO:feed
  2. Pagina Politicieni (roster + secțiuni pe persoană)
  3. Numărul „N verificări publicate" din bara de sus (toate paginile)

Sursa de adevăr = data/<slug>.json + a/<slug>.html.
Rulare:  python3 scripts/build_site.py
Idempotent — poți rula de câte ori vrei.

Cum adaugi un articol nou (și pt agentul cloud):
  1. scrie data/<slug>.json (schema: slug,title,category,date,source,url,dek,
     mainVerdict,probat[],contestat[],opinie[],math,aiNote,persoane[])
  2. scrie a/<slug>.html (după șablonul a/legea-integritatii-vot-final.html,
     cu head meta per-slug, hero g-hero cu og:image real, card .src-cite, secțiuni)
  3. rulează: python3 scripts/build_site.py
  4. commit + push  →  GitHub urcă singur pe site
"""
import json, re, glob, os, unicodedata, subprocess, collections, html, time
from datetime import datetime, timedelta, timezone

def now_edition():
    """Data + „Ediția de X" după ora României, la momentul build-ului (când se pun articole)."""
    try:
        from zoneinfo import ZoneInfo
        n = datetime.now(ZoneInfo("Europe/Bucharest"))
    except Exception:
        n = datetime.utcnow() + timedelta(hours=3)  # EEST aproximativ
    days = ["Luni","Marți","Miercuri","Joi","Vineri","Sâmbătă","Duminică"]
    months = ["ianuarie","februarie","martie","aprilie","mai","iunie","iulie","august",
              "septembrie","octombrie","noiembrie","decembrie"]
    date_str = f"{days[n.weekday()]}, {n.day} {months[n.month-1]} {n.year}"
    h = n.hour
    if   5 <= h < 8:   ed = "Ediția de dimineață"
    elif 8 <= h < 11:  ed = "Ediția de cafeluță"
    elif 11 <= h < 14: ed = "Ediția de amiază"
    elif 14 <= h < 17: ed = "Ediția de după-amiază"
    elif 17 <= h < 20: ed = "Ediția de seară"
    elif 20 <= h < 23: ed = "Ediția de seară târzie"
    else:              ed = "Ediția de noapte"
    return f"{date_str} · {ed}"

# Semnele pentru butonul Moldova (vezi build-ul paginilor, mai jos).
HARTA_MD = '<svg viewBox="0 0 100 140" width="17" height="24" aria-hidden="true" style="vertical-align:-4px"><path d="M38 8 L62 14 L72 30 L80 52 L86 74 L88 96 L78 124 L66 134 L52 130 L40 120 L30 100 L22 78 L18 56 L24 34 Z" fill="currentColor" opacity=".9"/></svg>'
BOUR_MD = '<svg viewBox="0 0 32 32" width="19" height="19" aria-hidden="true" style="vertical-align:-4px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7c-3 0-4 3-3 5 1 2 3 2 4 1"/><path d="M25 7c3 0 4 3 3 5-1 2-3 2-4 1"/><path d="M8 13c0-4 3-6 8-6s8 2 8 6c0 5-2 8-4 10-1.5 1.5-2.5 2-4 2s-2.5-.5-4-2c-2-2-4-5-4-10z"/><circle cx="12.5" cy="15" r="1.2" fill="currentColor" stroke="none"/><circle cx="19.5" cy="15" r="1.2" fill="currentColor" stroke="none"/><path d="M16 20v3"/></svg>'
STIL_MD = (
    "  /* Butonul sta in dreapta, ca inainte, dar centrat pe verticala cu\n"
    "     titlul: aceeasi cutie ca a lui (top 28, inaltime 74), iar butonul\n"
    "     asezat la mijlocul ei. */\n"
    "  .support{top:28px;height:74px;display:flex;align-items:center;\n"
    "    justify-content:center}\n"
    "  .btn-md{\n"
    "    display:inline-flex;align-items:center;\n"
    "    padding:9px 20px;border-radius:999px;\n"
    "    font-size:13.5px;font-weight:700;letter-spacing:.01em;\n"
    "    color:var(--accent);border:1.5px solid var(--accent);\n"
    "    background:transparent;transition:.16s ease;\n"
    "  }\n"
    "  .btn-md:hover{color:#fff;background:var(--accent);\n"
    "    box-shadow:0 5px 14px rgba(165,55,42,.26)}\n")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX  = os.path.join(ROOT, "index.html")

FEATURED = "legea-integritatii-vot-final"   # articolul din hero (rămâne curatoriat manual)
# 🔴 „Minți luminate" (5 septembrie 2026, numele ales de fondator, „gen Beautiful Mind"):
# articole care pleacă de la CERCETAREA unei universități, în orice domeniu — baterii,
# istorie, ceramică, politică sau modă. Ideea lui, verbatim: „prea mulți proști se cred
# importanți tocmai pentru că îi promovează cineva, iar pe deștepți nu-i promovează nimeni
# pentru că sunt greu de citit". Secțiunea e stratul care lipsește între studiu și cititor.
# Regula ei: se pleacă de la STUDIU, nu de la comunicatul universității. Comunicatul spune
# ce vrea universitatea să crezi; studiul spune ce s-a măsurat.
CAT_ORDER = ["Politică", "Economie", "Extern", "Știință", "Minți luminate", "Media de stat", "Social", "Sport"]


# Verdictul, redus la un cuvant — DOAR pentru Google, nu pentru cititor.
#
# `mainVerdict` e text liber, si asa ramane: peste 200 de formulari distincte
# in 727 de articole, multe propozitii intregi („Probat ce a declarat X — cifra
# ramane o estimare, neverificabila independent"). Aia e nuanta, e valoarea
# noastra, si NU se atinge. Cititorul vede in continuare fraza intreaga.
#
# Dar ClaimReview — formatul prin care Google recunoaste o verificare — cere
# obligatoriu `alternateName`: „a human-readable short word or phrase".
# Un cuvant. Asta e tot ce ii dam.
#
# 🔴 NU dam `ratingValue`. E doar recomandat, nu obligatoriu (verificat in
# documentatia Google pe 4 septembrie 2026). O nota numerica ar insemna sa
# punem adevarul pe o scara de la 1 la 5 — exact ce nu facem. Cuvantul „Probat"
# e al nostru; cifra ar fi fost a altcuiva.
VERDICT_SCURT = ("Contrazis", "Neprobat", "Neverificabil", "Neconfirmat",
                 "Contestat", "Mixt", "Opinie", "În verificare",
                 "Probat parțial", "Probat")

def verdict_scurt(v):
    """Primul cuvant-cheie cu care incepe verdictul. „Mixt" daca nu incepe cu niciunul.

    Ordinea din VERDICT_SCURT conteaza: „Probat parțial" trebuie incercat
    inaintea lui „Probat", altfel toate partialele ar trece drept probate.
    Cele ~27 de verdicte care incep altfel („Cifrele oficiale: probate · …”)
    sunt chiar amestecate — „Mixt" nu e o pierdere de nuanta, e adevarul lor.
    """
    t = (v or "").strip()
    if not t:
        return None
    tl = t.lower()
    for eticheta in VERDICT_SCURT:
        if tl.startswith(eticheta.lower()):
            return "Neverificabil" if eticheta == "Neconfirmat" else eticheta
    return "Mixt"
CAT_ID = {"Politică":"politica","Economie":"economie","Extern":"extern","Știință":"stiinta","Minți luminate":"minti-luminate","Media de stat":"media-de-stat","Social":"social","Sport":"sport"}
GCLASS = {"Politică":"g-pol","Economie":"g-eco","Social":"g-soc","Sport":"g-sport","Extern":"g-ext","Știință":"g-sci","Minți luminate":"g-minti","Media de stat":"g-state"}
CATGLYPH = {"Politică":"⚖️","Economie":"💶","Social":"👥","Extern":"🌍","Sport":"⚽","Știință":"🔬","Minți luminate":"💡","Media de stat":"📡"}

# roster politicieni (echilibrat pe partide) — se pot adăuga oricând
ROSTER = [
 ("Nicușor Dan","Președinte"),("Ilie Bolojan","PNL"),("Sorin Grindeanu","PSD"),
 ("Marcel Ciolacu","PSD"),("Mihai Tudose","PSD"),("Gabriela Firea","PSD"),
 ("Alexandru Rafila","PSD"),("Paul Stănescu","PSD"),("Nicolae Ciucă","PNL"),
 ("Rareș Bogdan","PNL"),("Cătălin Predoiu","PNL"),("Alexandru Nazare","PNL"),
 ("Dominic Fritz","USR"),("Diana Buzoianu","USR"),("Cătălin Drulă","USR"),
 ("Elena Lasconi","USR"),("George Simion","AUR"),("Claudiu Târziu","AUR"),
 ("Diana Șoșoacă","SOS"),("Anamaria Gavrilă","POT"),("Călin Georgescu","Suveranist"),
 ("Kelemen Hunor","UDMR"),("Victor Ponta","independent"),("Crin Antonescu","PNL"),
 ("Ludovic Orban","independent"),("Eugen Tomac","independent"),
 ("Maia Sandu","Președinte R. Moldova"),("Traian Băsescu","fost președinte"),
]
PCOLOR = {"PSD":"#d0021b","PNL":"#e6a817","USR":"#1f6fb2","AUR":"#16407a","SOS":"#7a1f1f",
 "POT":"#6a3fa0","UDMR":"#2a8a4a","Președinte":"#444","Suveranist":"#4a4a4a",
 "independent":"#777","fost președinte":"#888","Președinte R. Moldova":"#0a4bab","—":"#777"}

CAT_NORMALIZE = {"politica":"Politică","politică":"Politică","economie":"Economie",
 "extern":"Extern","social":"Social","sport":"Sport",
 "stiinta":"Știință","știință":"Știință","stiință":"Știință",
 "media de stat":"Media de stat","media-de-stat":"Media de stat","mediadestat":"Media de stat"}
def load():
    arts = {}
    for p in glob.glob(os.path.join(ROOT, "data", "*.json")):
        if os.path.basename(p).startswith("_"): continue
        d = json.load(open(p, encoding="utf-8"))
        # plasă de siguranță: normalizează categoria (diacritice/majuscule)
        c = (d.get("category") or "").strip()
        d["category"] = CAT_NORMALIZE.get(c.lower(), c)
        slug = d.get("slug")
        # rezistent la curse: include articolul doar dacă are ȘI HTML-ul (nu doar JSON-ul)
        if slug and os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            arts[slug] = d
    return arts

def momente():
    """
    Ora exactă a publicării fiecărui articol, luată din git.

    Articolele au doar `date` (ziua), iar într-o zi cu 40 de articole asta nu
    spune nimic despre ordine. Momentul în care fișierul a intrat prima oară în
    git ESTE momentul publicării — nu trebuie inventat un câmp nou și nu depinde
    de botul care scrie articolul.

    O singură trecere prin istoric, sub o sutime de secundă.
    """
    out = {}
    try:
        r = subprocess.run(["git", "log", "--format=@%cI", "--name-only",
                            "--diff-filter=A", "--", "data/"],
                           capture_output=True, text=True, cwd=ROOT, timeout=60)
    except Exception:
        return out
    ceas = ""
    for linie in r.stdout.splitlines():
        linie = linie.strip()
        if linie.startswith("@"):
            ceas = linie[1:]
        elif linie.startswith("data/") and linie.endswith(".json"):
            slug = os.path.basename(linie)[:-5]
            # `git log` merge de la nou la vechi, deci prima apariție e cea mai
            # recentă. Noi vrem PRIMA intrare în git, deci suprascriem mereu.
            out[slug] = ceas
    return out


def cheie_timp(d, mom):
    """Sortare pe zi + oră. Fără ora din git, cade elegant pe zi."""
    return (d.get("date", ""), mom.get(d.get("slug", ""), ""))


def vcl(v):
    v = (v or "").lower()
    return ("bad","Contrazis") if "contrazis" in v else ("ok","Probat") if "probat" in v else ("warn","Mixt")

def art_html(slug):
    return open(os.path.join(ROOT, "a", f"{slug}.html"), encoding="utf-8").read()

def extract(d):
    """glyph, hero-img, srcbadge din HTML-ul articolului."""
    slug = d["slug"]; h = art_html(slug)
    m = re.search(r'<div class="glyph">(.*?)</div>', h, re.S)
    glyph = m.group(1) if m else CATGLYPH.get(d["category"], "📰")
    mi = re.search(r'<img src="([^"]+)"[^>]*z-index:1">', h)
    heroimg = mi.group(1) if mi else None
    ms = re.search(r'<div class="srcbadge">(.*?)</div>', h, re.S)
    if ms:
        sb = ms.group(1).strip()
        fav = re.search(r'(<span class="fav"[^>]*></span>)', sb)
        fav = fav.group(1) if fav else '<span class="fav" style="background:#888"></span>'
        srcname = re.sub(r'<span class="fav"[^>]*></span>\s*', '', sb).strip()
    else:
        fav = '<span class="fav" style="background:#888"></span>'; srcname = d.get("source","sursă")
    return glyph, heroimg, fav, srcname

# Câte articole din fiecare categorie primesc card cu poză pe prima pagină.
# Restul trec în lista compactă. Cu 7 categorii, imaginile se plafonează la
# ~42 — indiferent câte articole se adună în timp.
# Toate articolele primesc card cu poză, nu doar cele mai noi (decizia
# fondatorului, 21 august 2026): „vreau ca toate articolele pe pagina acasă,
# când derulezi în jos, să se vadă frumos cu poză exact cum se văd primele".
# Ce face costul suportabil: cardurile folosesc miniatura de 520px (~35 KB, nu
# ~550 KB) și `loading="lazy"`, deci browserul cere poza abia când ajunge la ea.
CARDURI_PE_CATEGORIE = 10000


def card_img(slug, heroimg):
    """
    Cardurile folosesc miniatura, nu poza mare.

    Cu poza originală în fiecare card, prima pagină ajunsese să ceară ~34 MB de
    imagini. Miniatura de 520px face ~32 KB în loc de ~550 KB.

    Dacă nu avem poză proprie, cardul NU cade înapoi pe poza hotlinkată a altei
    publicații — rămâne pe gradientul de brand. Altfel prima pagină, cea mai
    vizitată, rămânea plină de fotografii care nu sunt ale noastre.
    """
    thumb = os.path.join(ROOT, "img", "carduri", f"{slug}.jpg")
    if os.path.exists(thumb):
        return f"img/carduri/{slug}.jpg"
    if heroimg and heroimg.lstrip("./").startswith("img/"):
        return heroimg.lstrip("./")
    return None


def mini_row(d):
    """
    Rând compact, fără imagine, pentru articolele mai vechi dintr-o categorie.

    Nu pierdem niciun link — toate rămân pe prima pagină și indexabile — dar
    numărul de imagini se plafonează, iar pagina crește cu ~200 de octeți pe
    articol în loc de ~1,5 KB.
    """
    vc, vl = vcl(d.get("mainVerdict"))
    return (f'            <a href="a/{d["slug"]}.html" class="mini-row">'
            f'<span class="mini-title">{d["title"]}</span>'
            f'<span class="mini-meta"><span class="chip soft {vc} sm">{vl}</span>'
            f'<span class="mini-date">{d.get("date","")}</span></span></a>\n')


def trunc(s, n):
    return s if len(s) <= n else s[:n].rsplit(" ",1)[0].rstrip(" ,.;") + "…"

def card(d):
    glyph, heroimg, fav, srcname = extract(d)
    vc, vl = vcl(d.get("mainVerdict"))
    np_, nc_, no_ = len(d.get("probat") or []), len(d.get("contestat") or []), len(d.get("opinie") or [])
    cimg = card_img(d["slug"], heroimg)
    img = (f'<img data-cardphoto="1" src="{cimg}" alt="" loading="lazy" '
           f'onerror="this.remove()" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1">'
           if cimg else "")
    seg = f'<span class="seg ok">✔ {np_}</span><span class="seg warn">⚠ {nc_}</span><span class="seg op">✎ {no_}</span>'
    return f'''          <a href="a/{d["slug"]}.html" class="card">

            <div class="photo {GCLASS[d["category"]]}">
              <div class="art">
                <div class="pattern"><svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><defs><pattern id="p-{d["slug"]}" width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(25)"><path d="M0 12 H24 M12 0 V24" stroke="#fff" stroke-width="1" opacity="0.25"/></pattern></defs><rect width="100%" height="100%" fill="url(#p-{d["slug"]})"/></svg></div>
                <div class="glyph">{glyph}</div>
              </div>
              {img}
              <div class="grad"></div>
              <div class="imgtag">Verificare Fără Baliverne</div>
              <div class="cat-pill">{d["category"]}</div>
              <div class="srcbadge">{fav} {srcname}</div>
            </div>
            <div class="cbody">
              <div class="toprow"><span class="cat-tag">{d["category"]}</span><div class="report-badge sm">{seg}</div></div>
              <h3>{d["title"]}</h3>
              <p class="dek">{trunc(d.get("dek",""),158)}</p>
              <div class="cmeta">
                <span class="src">{fav} {srcname}</span>
                <span>· {d.get("date","")}</span>
                <span class="chip soft {vc} sm verdict-mini">unde bat probele: {vl}</span>
              </div>
            </div>
          </a>
'''

def build_feed(arts, mom=None):
    """Secțiunile pe categorii, ordonate; exclude articolul din hero."""
    mom = mom or {}
    out = []
    for cat in CAT_ORDER:
        items = [d for s,d in arts.items() if d["category"] == cat and s != FEATURED]
        if not items: continue
        # Pe ORĂ, nu doar pe zi: într-o zi cu 40 de articole, data singură nu
        # spune care e cel mai nou. Ora vine din git (vezi `momente`).
        items.sort(key=lambda d: cheie_timp(d, mom), reverse=True)
        # Doar cele mai recente primesc card cu poză; restul trec în lista
        # compactă, altfel prima pagină crește la nesfârșit — în octeți și în
        # număr de imagini cerute.
        cu_card, restul = items[:CARDURI_PE_CATEGORIE], items[CARDURI_PE_CATEGORIE:]
        cards = "".join(card(d) for d in cu_card)
        mini = ""
        if restul:
            randuri = "".join(mini_row(d) for d in restul)
            mini = ('          <div class="mini-list">\n'
                    f'            <div class="mini-head">Încă {len(restul)} din {cat}</div>\n'
                    f'{randuri.rstrip(chr(10))}\n          </div>\n')
        out.append(f'''        <section class="cat-section" id="{CAT_ID[cat]}">
          <div class="section-head">
            <h2>{cat}</h2>
          </div>
          <div class="cards-3">
{cards.rstrip(chr(10))}
          </div>
{mini.rstrip(chr(10))}
        </section>
''')
    return "\n".join(out)

def build_featured_script(arts, mom=None):
    """Hero rotativ: la fiecare refresh, JS alege aleatoriu alt articol pt „principalul"."""
    mom = mom or {}
    items = sorted(arts.values(), key=lambda d: cheie_timp(d, mom), reverse=True)[:8]  # doar cele mai noi
    data = []
    for d in items:
        glyph, heroimg, fav, srcname = extract(d)
        vc, vl = vcl(d.get("mainVerdict"))
        data.append({
            "slug": d["slug"], "title": d["title"], "dek": d.get("dek",""),
            "cat": d["category"], "g": GCLASS.get(d["category"], "g-pol"),
            "glyph": glyph, "img": heroimg or "", "fav": fav, "src": srcname,
            "vc": vc, "vl": vl,
            "np": len(d.get("probat") or []), "nc": len(d.get("contestat") or []),
            "no": len(d.get("opinie") or []),
        })
    js_data = "        <script>window.FB_FEATURED = " + json.dumps(data, ensure_ascii=False) + ";</script>\n"
    js_logic = '''        <script>
        (function(){
          var L=window.FB_FEATURED||[]; if(L.length<2) return;
          var h=document.querySelector('a.hero'); if(!h) return;
          try{
            var last=sessionStorage.getItem('fbHeroLast');
            var p; if(!last){ p=L[0]; } else { var pool=L.filter(function(a){return a.slug!==last;}); if(!pool.length) pool=L; p=pool[Math.floor(Math.random()*pool.length)]; }
            sessionStorage.setItem('fbHeroLast',p.slug);
            h.setAttribute('href','a/'+p.slug+'.html');
            var ph=h.querySelector('.photo'); if(ph) ph.className='photo '+p.g;
            var g=h.querySelector('.glyph'); if(g) g.textContent=p.glyph;
            var im=h.querySelector('img'); if(im){ if(p.img){im.src=p.img;im.style.display='';} else {im.style.display='none';} }
            var cp=h.querySelector('.cat-pill'); if(cp) cp.textContent=p.cat;
            var sb=h.querySelector('.srcbadge'); if(sb) sb.innerHTML=p.fav+' '+p.src;
            var ct=h.querySelector('.eyebrow .cat-tag'); if(ct) ct.textContent=p.cat;
            var rb=h.querySelector('.report-badge'); if(rb) rb.innerHTML='<span class="seg ok">\\u2714 '+p.np+' probate</span> <span style="color:var(--line-2)">\\u00b7</span> <span class="seg warn">\\u26a0 '+p.nc+' contestate</span> <span style="color:var(--line-2)">\\u00b7</span> <span class="seg op">\\u270e '+p.no+' opinie</span>';
            var t=h.querySelector('h1'); if(t) t.textContent=p.title;
            var dk=h.querySelector('.dek'); if(dk) dk.textContent=p.dek;
            var s2=h.querySelector('.meta .src'); if(s2) s2.innerHTML=p.fav+' '+p.src;
            var ch=h.querySelector('.meta .chip'); if(ch){ ch.className='chip soft '+p.vc+' sm'; ch.textContent='unde bat probele: '+p.vl; }
          }catch(e){}
        })();
        </script>
'''
    return js_data + js_logic

def replace_feed(html, feed):
    START, END = "<!-- AUTO:feed:start -->", "<!-- AUTO:feed:end -->"
    block = f"{START}\n{feed}        {END}\n"
    if START in html and END in html:
        return re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n", lambda m: block, html, count=1, flags=re.S)
    # bootstrap: instalează marcajele în jurul secțiunilor existente
    i = html.index('<section class="cat-section" id="politica">')
    j = html.index('      </div>\n\n      <aside>')
    return html[:i] + block + html[j:]

# ---------- politicieni ----------
def anchor(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z]+","-",s).strip("-")
def initials(name):
    p = [x for x in name.split() if x]
    return (p[0][0] + (p[-1][0] if len(p)>1 else "")).upper()

def pcard_json(d):
    cat = d["category"]; vc, vl = vcl(d.get("mainVerdict"))
    seg = f'<span class="seg ok">✔ {len(d.get("probat") or [])}</span><span class="seg warn">⚠ {len(d.get("contestat") or [])}</span><span class="seg op">✎ {len(d.get("opinie") or [])}</span>'
    return f'''          <a href="a/{d["slug"]}.html" class="card">
            <div class="photo {GCLASS.get(cat,"g-pol")}"><div class="art"><div class="glyph">{CATGLYPH.get(cat,"📰")}</div></div><div class="grad"></div><div class="cat-pill">{cat}</div></div>
            <div class="cbody"><div class="toprow"><span class="cat-tag">{cat}</span><div class="report-badge sm">{seg}</div></div>
              <h3>{d["title"]}</h3><p class="dek">{trunc(d.get("dek",""),140)}</p>
              <div class="cmeta"><span>· {d.get("date","")}</span><span class="chip soft {vc} sm verdict-mini">unde bat probele: {vl}</span></div>
            </div></a>
'''

def _fara_diacritice(t):
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def build_politicieni(arts, shell):
    byp = {}
    for d in arts.values():
        for n in (d.get("persoane") or []): byp.setdefault(n, []).append(d)

    # Dacă un politician din roster e MENȚIONAT în titlu sau în dek, articolul
    # apare și la el, chiar dacă redactorul a uitat să-l treacă în `persoane[]`.
    # Se caută numele întreg, nu prenumele — „Ilie Bolojan", nu „Ilie" — ca să nu
    # ajungă la el orice articol despre un alt om cu același prenume.
    for d in arts.values():
        txt = _fara_diacritice(d.get("title", "") + " " + d.get("dek", ""))
        deja = set(d.get("persoane") or [])
        for n, _ in ROSTER:
            if n not in deja and _fara_diacritice(n) in txt:
                byp.setdefault(n, []).append(d)
    names = [n for n,_ in ROSTER]; party = {n:pt for n,pt in ROSTER}
    for n in byp:
        if n not in party: names.append(n); party[n] = "—"
    with_a = sorted([n for n in names if byp.get(n)], key=lambda n:(-len(byp[n]), n))
    without = [n for n in names if not byp.get(n)]
    def chip(n):
        c = len(byp.get(n,[])); pt = party[n]; col = PCOLOR.get(pt,"#777")
        href = f'#{anchor(n)}' if c else 'contact.html'; op = '' if c else 'opacity:.62'
        lab = f'{c} verificări' if c else 'în curând'
        return (f'      <a href="{href}" style="display:flex;gap:11px;align-items:center;text-decoration:none;color:inherit;'
                f'border:1px solid var(--line-2);background:var(--card);border-radius:13px;padding:11px 13px;{op}">'
                f'<span style="flex:0 0 40px;height:40px;border-radius:50%;background:{col};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px">{initials(n)}</span>'
                f'<span style="min-width:0"><span style="display:block;font-weight:700;font-size:14.5px;line-height:1.2">{n}</span>'
                f'<span style="display:block;font-size:11.5px;color:var(--ink-faint);margin-top:2px"><b style="color:{col}">{pt}</b> · {lab}</span></span></a>')
    grid = "\n".join(chip(n) for n in with_a + without)
    secs = ""
    for n in with_a:
        lst = sorted(byp[n], key=lambda d:d.get("date",""), reverse=True)
        pt = party[n]; col = PCOLOR.get(pt,"#777")
        secs += (f'        <section class="cat-section" id="{anchor(n)}">\n'
                 f'          <div class="section-head"><h2>{n} <span style="font-size:12.5px;font-weight:700;color:#fff;background:{col};padding:2px 9px;border-radius:20px;vertical-align:middle">{pt}</span> '
                 f'<span style="font-size:13px;font-weight:700;color:var(--ink-faint)">· {len(lst)} verificări</span></h2></div>\n'
                 f'          <div class="cards-3">\n{"".join(pcard_json(d) for d in lst).rstrip(chr(10))}\n          </div>\n        </section>\n')
    main = (f'    <div class="wrap" style="max-width:1120px;margin:0 auto;padding:0 20px">\n'
            f'      <div style="padding:30px 0 6px">\n'
            f'        <h1 style="font-family:Georgia,serif;font-size:34px;margin:0 0 8px">Politicieni</h1>\n'
            f'        <p style="max-width:660px;color:var(--ink-faint);font-size:16px;line-height:1.5">Citește ce <b>s-a probat</b> despre fiecare — verificările noastre, grupate pe persoană. Nu decretăm „adevărat/fals"; arătăm dovezile cu surse, tu tragi concluzia. Lista crește pe măsură ce publicăm.</p>\n'
            f'      </div>\n'
            f'      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:10px;margin:14px 0 34px">\n{grid}\n      </div>\n{secs}    </div>')
    h = re.sub(r'<main>.*?</main>', "<main>\n"+main+"\n  </main>", shell, count=1, flags=re.S)
    h = h.replace("<title>Fără Baliverne — Apă, paie… Adevăr</title>", "<title>Politicieni — Fără Baliverne</title>")
    h = h.replace('<link rel="canonical" href="https://farabaliverne.ro/">', '<link rel="canonical" href="https://farabaliverne.ro/politicieni.html">')
    h = h.replace('<meta property="og:url" content="https://farabaliverne.ro/">', '<meta property="og:url" content="https://farabaliverne.ro/politicieni.html">')
    h = h.replace('<meta property="og:title" content="Fără Baliverne — Apă, paie… Adevăr">', '<meta property="og:title" content="Politicieni — Fără Baliverne">')
    h = h.replace('<meta name="twitter:title" content="Fără Baliverne — Apă, paie… Adevăr">', '<meta name="twitter:title" content="Politicieni — Fără Baliverne">')
    h = h.replace('<a href="index.html" class="active">Acasă</a>', '<a href="index.html">Acasă</a>')
    return h, len(with_a), len(without)

SHARE_VECHI_FB = ("window.shareFB=function(){window.open('https://www.facebook.com/sharer/"
                  "sharer.php?u='+e(U),'_blank','noopener,width=650,height=600');};")
SHARE_VECHI_X = ("window.shareX=function(){window.open('https://twitter.com/intent/tweet?url='"
                 "+e(U)+'&text='+e(T),'_blank','noopener,width=560,height=460');};")
# Varianta intermediară, care trimitea X tot prin foaia nativă. A stat pe site
# câteva zile; trebuie recunoscută ca să poată fi înlocuită la rândul ei.
SHARE_INTERMEDIAR_X = ("window.shareX=function(){if(window.__fbMobil&&navigator.share)"
                       "{navigator.share({title:T,url:U}).catch(function(){});return;}"
                       "window.open('https://twitter.com/intent/tweet?url='+e(U)+'&text='+e(T),"
                       "'_blank','noopener,width=560,height=460');};")

# Pe telefon, sistemul trimite linkurile `facebook.com` direct în aplicația
# Facebook, iar aplicația NU știe `sharer.php`: deschide fluxul și nu partajează
# nimic. La fel face și aplicația X cu `intent/tweet`. De-aia butoanele păreau
# că merg — se deschidea rețeaua — dar nu pleca niciun link.
#
# Singura cale care funcționează pe mobil e foaia nativă de partajare a
# sistemului (Web Share API): primește titlul și adresa, iar aplicația aleasă le
# ia corect. Pe desktop nu există așa ceva, deci acolo rămâne fereastra clasică,
# care oricum funcționa.
SHARE_NOU_FB = ("window.shareFB=function(){if(window.__fbMobil&&navigator.share)"
                "{navigator.share({title:T,url:U}).catch(function(){});return;}"
                "window.open('https://www.facebook.com/sharer/sharer.php?u='+e(U),"
                "'_blank','noopener,width=650,height=600');};")
# X e ALTĂ situație decât Facebook, iar prima reparație le-a tratat la fel —
# greșit. Facebook nu permite text precompletat de nicăieri, deci acolo foaia
# nativă de partajare chiar e singura cale. X, în schimb, acceptă `intent`, iar
# pe telefon linkul `x.com/intent/post` deschide aplicația X cu titlul și
# adresa deja scrise.
#
# Diferența, pentru omul care apasă: la Facebook primești meniul de partajare
# al sistemului și alegi tu unde; la X ajungi DIRECT în X, cu postarea începută.
# Asta aștepta fondatorul de la un buton pe care scrie X.
#
# Domeniul e `x.com`, nu `twitter.com`: cel vechi redirecționează, iar
# redirecțiile pierd uneori parametrii pe aplicațiile mobile.
SHARE_NOU_X = ("window.shareX=function(){"
               "window.open('https://x.com/intent/post?url='+e(U)+'&text='+e(T),"
               "'_blank','noopener,width=560,height=460');};")
SHARE_DETECT = ("window.__fbMobil=/Android|iPhone|iPad|iPod|Mobile|Silk/i.test("
                "navigator.userAgent||'');")


# Articolele citite dispar de pe prima pagină. Ce s-a citit nu mai e știre.
#
# Memoria e în browserul cititorului (localStorage), nu la noi: nu punem cont, nu
# urmărim pe nimeni, nu pleacă nimic spre server. Cine intră de pe alt telefon
# vede tot.
#
# Cu plasă de siguranță: dacă a citit TOT dintr-o secțiune, nu-i lăsăm un gol —
# secțiunea rămâne întreagă. Și are mereu un buton prin care le aduce înapoi.
CITITE_JS = """
<script>
(function(){
  var K='fb_citite';
  function citite(){ try{ return JSON.parse(localStorage.getItem(K)||'[]'); }catch(e){ return []; } }
  // Pe pagina articolului: reținem că a fost deschis.
  var m = location.pathname.match(/\\/a\\/([^\\/]+)\\.html$/);
  if(m){
    var L=citite(); if(L.indexOf(m[1])<0){ L.push(m[1]); try{ localStorage.setItem(K, JSON.stringify(L.slice(-400))); }catch(e){} }
    return;
  }
  // Pe prima pagină: ascundem ce s-a citit deja.
  if(!/(^\\/$|index\\.html$)/.test(location.pathname)) return;
  document.addEventListener('DOMContentLoaded', function(){
    var L=citite(); if(!L.length) return;
    var ascunse=0;
    document.querySelectorAll('main section.cat-section').forEach(function(sec){
      var tot=sec.querySelectorAll('a.card, a.mini-row');
      var deAscuns=[];
      tot.forEach(function(a){
        var h=a.getAttribute('href')||'';
        var s=(h.match(/a\\/([^\\/]+)\\.html$/)||[])[1];
        if(s && L.indexOf(s)>=0) deAscuns.push(a);
      });
      // Dacă a citit tot din secțiune, o lăsăm întreagă — mai bine ceva decât gol.
      if(deAscuns.length && deAscuns.length < tot.length){
        deAscuns.forEach(function(a){ a.style.display='none'; a.dataset.fbCitit='1'; });
        ascunse += deAscuns.length;
      }
    });
    if(!ascunse) return;
    var b=document.createElement('button');
    b.textContent = ascunse===1 ? 'Arată și articolul pe care l-ai citit'
                                : 'Arată și cele '+ascunse+' pe care le-ai citit';
    b.style.cssText='display:block;margin:18px auto 0;padding:9px 18px;border-radius:999px;border:1px solid var(--line-2);background:var(--card);color:var(--ink-soft);font:600 13px system-ui;cursor:pointer';
    b.onclick=function(){
      document.querySelectorAll('[data-fb-citit]').forEach(function(a){ a.style.display=''; });
      b.remove();
    };
    var w=document.querySelector('main .wrap'); if(w) w.appendChild(b);
  });
})();
</script>
"""


# Bara de sus arată ziua CITITORULUI, nu ziua în care a fost construită pagina.
#
# Înainte, paginile de articol rămâneau înghețate la momentul publicării: 40 de
# articole scriau „Ediția de noapte" în capul paginii, iar cine le deschidea
# marți la prânz vedea „Luni · Ediția de noapte". E o bară de ziar, nu o etichetă
# a articolului — data publicării apare oricum sub titlu.
#
# Se calculează în browser, deci e corectă mereu, indiferent când a fost
# construită pagina sau când o citește cineva.
DATA_JS = """
<script>
(function(){
  var el=document.querySelector('.topbar .date'); if(!el) return;
  var Z=['Duminică','Luni','Marți','Miercuri','Joi','Vineri','Sâmbătă'];
  var L=['ianuarie','februarie','martie','aprilie','mai','iunie','iulie','august','septembrie','octombrie','noiembrie','decembrie'];
  function scrie(){
    var n=new Date(), h=n.getHours(), e;
    if(h>=5&&h<8) e='Ediția de dimineață';
    else if(h>=8&&h<11) e='Ediția de cafeluță';
    else if(h>=11&&h<14) e='Ediția de amiază';
    else if(h>=14&&h<17) e='Ediția de după-amiază';
    else if(h>=17&&h<20) e='Ediția de seară';
    else if(h>=20&&h<23) e='Ediția de seară târzie';
    else e='Ediția de noapte';
    el.textContent=Z[n.getDay()]+', '+n.getDate()+' '+L[n.getMonth()]+' '+n.getFullYear()+' · '+e;
  }
  scrie(); setInterval(scrie, 60000);
})();
</script>
"""


VEZI_START = "<!-- AUTO:veziși:start -->"
VEZI_END = "<!-- AUTO:veziși:end -->"
_STOP = set("""si sau dar insa iar ca ce cum cand unde care cine este sunt fost fi va
a al ale ai un o unei unui de la in pe cu din pentru dupa fara intre peste prin sub
spre catre despre nu mai foarte tot toata toate mult multe putin lui ei lor sa se
isi au are avea fie ani an luna luni zi zile azi ieri maine acum apoi doar chiar
deja inca romania roman romani romaniei noua nou noi prima primul primele cat cati
cate mii milioane miliarde procente suta""".split())


def _cuvinte(t):
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{4,}", t) if w not in _STOP}


def indice_inrudite(arts):
    """
    Pregătește, o singură dată, datele pentru „Vezi și".

    Regula cere un semnal TARE: aceeași sursă citată, aceeași persoană, sau cel
    puțin trei cuvinte rare comune. Fără condiția asta, două articole fără nicio
    legătură ajungeau la 10 puncte din cuvinte banale — „SUA transferă rachete
    ATACMS" se lega de „Marea Britanie, cea mai fierbinte zi: 38,1°C". Măsurat pe
    338 de articole înainte de a fi pus pe site.
    """
    idx = {}
    for slug, d in arts.items():
        urls = set()
        for k in ("probat", "contestat"):
            for el in d.get(k) or []:
                for s in el.get("sources") or []:
                    if s.get("url"):
                        urls.add(s["url"].split("?")[0])
        idx[slug] = {"urls": urls, "pers": set(d.get("persoane") or []),
                     "cuv": _cuvinte(d.get("title", "") + " " + d.get("dek", "")),
                     "cat": d.get("category", "")}
    df = collections.Counter()
    for v in idx.values():
        for w in v["cuv"]:
            df[w] += 1
    rar = {w for w, n in df.items() if n <= 4}
    obisnuit = {w for w, n in df.items() if 4 < n <= 12}
    return idx, rar, obisnuit


PRAG_INRUDIRE = 10


def inrudite(slug, arts, idx, rar, obisnuit, cate=3):
    a = idx[slug]
    rez = []
    for alt, b in idx.items():
        if alt == slug:
            continue
        cu = a["urls"] & b["urls"]
        pe = a["pers"] & b["pers"]
        com = a["cuv"] & b["cuv"]
        r = com & rar
        if not (cu or pe or len(r) >= 3):
            continue
        s = 6 * len(cu) + 4 * len(pe) + 2 * len(r) + len(com & obisnuit)
        if a["cat"] == b["cat"]:
            s += 1
        if s >= PRAG_INRUDIRE:
            rez.append((s, alt))
    rez.sort(key=lambda x: (-x[0], x[1]))
    return [alt for _, alt in rez[:cate]]


def fire(arts, idx, rar, obisnuit):
    """
    Grupează articolele în FIRE de subiect — componente conexe ale grafului de
    înrudire.

    Un fir e o poveste care ține mai multe zile: legea salarizării de la refuzul
    PSD până la decizia CCR, sau Popovici de la „în fața unui record" până la
    dubla istorică. Astea NU sunt duplicate și nu trebuie unificate — trebuie
    puse în ordine, ca cititorul să vadă cum a evoluat.
    """
    vec = collections.defaultdict(set)
    for s in arts:
        for alt in inrudite(s, arts, idx, rar, obisnuit, cate=6):
            vec[s].add(alt)
            vec[alt].add(s)
    vazut, out = set(), {}
    for s in arts:
        if s in vazut or s not in vec:
            continue
        stiva, comp = [s], set()
        while stiva:
            x = stiva.pop()
            if x in comp:
                continue
            comp.add(x)
            vazut.add(x)
            stiva += [y for y in vec[x] if y not in comp]
        # Sub 3 articole nu e un fir, e o trimitere — rămâne pe „Vezi și".
        # Pe o singură zi nu e o desfășurare, e o zi aglomerată.
        if len(comp) >= 3 and len({arts[x].get("date") for x in comp}) >= 2:
            lista = sorted(comp, key=lambda k: (arts[k].get("date", ""), k))
            for x in comp:
                out[x] = lista
    return out


def bloc_desfasurator(slug, lista, arts):
    """Firul întreg, în ordinea zilelor, cu articolul curent marcat."""
    zile = len({arts[x].get("date") for x in lista})
    out = [VEZI_START,
           '      <section class="ev-block" style="border-left:5px solid var(--gold)">',
           f"        <h2>🧵 Desfășurător · {len(lista)} verificări în {zile} zile</h2>",
           '        <p class="ev-sub">Cum a evoluat subiectul, în ordinea în care '
           "l-am verificat. Articolul pe care îl citești e marcat.</p>"]
    for x in lista:
        d2 = arts[x]
        acum = x == slug
        vc, vl = vcl(d2.get("mainVerdict"))
        titlu = (f'<b>{d2["title"]}</b>' if acum else
                 f'<a href="{x}.html" style="text-decoration:underline;'
                 f'text-underline-offset:2px">{d2["title"]}</a>')
        out.append(
            f'        <div class="ev-item" style="padding:10px 0;'
            f'{"background:var(--paper-2);border-radius:8px;padding-left:10px" if acum else ""}">'
            f'<p style="margin:0 0 4px;font-size:12px;letter-spacing:.06em;'
            f'color:var(--ink-faint);font-weight:800">{d2.get("date","")}'
            f'{" · ESTE ARTICOLUL DE FAȚĂ" if acum else ""}</p>'
            f'<p style="margin:0 0 5px;font-size:15.5px;line-height:1.35">{titlu}</p>'
            f'<span class="chip soft {vc} sm">{vl}</span></div>')
    out += ["      </section>", VEZI_END]
    return "\n".join(out) + "\n"


def bloc_vezi_si(slug, arts, idx, rar, obisnuit):
    legate = inrudite(slug, arts, idx, rar, obisnuit)
    if not legate:
        return ""
    out = [VEZI_START,
           '      <section class="ev-block" style="border-left:5px solid var(--gold)">',
           "        <h2>🔗 Vezi și</h2>",
           '        <p class="ev-sub">Alte verificări ale noastre legate de acest subiect.</p>']
    for s2 in legate:
        d2 = arts[s2]
        vc, vl = vcl(d2.get("mainVerdict"))
        out.append(
            f'        <div class="ev-item" style="padding:11px 0">'
            f'<p style="margin:0 0 5px;font-size:15.5px;line-height:1.35">'
            f'<a href="{s2}.html" style="text-decoration:underline;text-underline-offset:2px">'
            f'{d2["title"]}</a></p>'
            f'<p style="margin:0"><span class="chip soft {vc} sm">{vl}</span> '
            f'<span style="font-size:12px;color:var(--ink-faint);margin-left:6px">'
            f'{d2.get("category","")} · {d2.get("date","")}</span></p></div>')
    out += ["      </section>", VEZI_END]
    return "\n".join(out) + "\n"


def pune_vezi_si(s, slug, arts, idx, rar, obisnuit, fire_idx=None):
    """
    Sub secțiunile de dovezi, înainte de caseta de final.

    Dacă articolul face parte dintr-un FIR (poveste pe mai multe zile), arătăm
    desfășurătorul întreg, în ordine. Altfel, doar câteva trimiteri înrudite.
    """
    fire_idx = fire_idx or {}
    bloc = (bloc_desfasurator(slug, fire_idx[slug], arts) if slug in fire_idx
            else bloc_vezi_si(slug, arts, idx, rar, obisnuit))
    if VEZI_START in s:
        return re.sub(re.escape(VEZI_START) + r".*?" + re.escape(VEZI_END) + r"\n?",
                      lambda m: bloc, s, count=1, flags=re.S)
    if not bloc:
        return s
    ancora = '        <div class="conclusion-box">'
    return s.replace(ancora, bloc + ancora, 1) if ancora in s else s


TITLURI_START = "<!-- AUTO:titluri:start -->"
TITLURI_END = "<!-- AUTO:titluri:end -->"
_SURSA_TITLU = re.compile(r"^\s*([^—]{2,40}?)\s*—\s*(.{8,})$", re.S)


def bloc_titluri(d):
    """
    „Cum a titrat fiecare" — aceeași știre, prin ochii fiecărei publicații.

    Nu punem noi etichete de orientare. Punem titlurile lor, unul lângă altul, și
    perspectiva se vede singură: aceeași hotărâre e „guvernul a cedat" la unii și
    „acord istoric" la alții. E metoda casei aplicată presei — arătăm, nu
    decretăm. Și nu se poate contesta, fiindcă sunt cuvintele lor.

    Materialul există deja: 97% din sursele citate sunt scrise „Publicație —
    titlu". Nu trebuie cules nimic nou.
    """
    vazut, randuri = {}, []
    for k in ("probat", "contestat"):
        for el in d.get(k) or []:
            for s in el.get("sources") or []:
                m = _SURSA_TITLU.match(s.get("name", ""))
                if not m or not s.get("url"):
                    continue
                pub = m.group(1).strip()
                titlu = re.sub(r"\s+", " ", m.group(2)).strip()
                # O publicație apare o singură dată, cu primul titlu citat.
                if pub.lower() in vazut:
                    continue
                vazut[pub.lower()] = True
                randuri.append((pub, titlu, s["url"]))

    # Sub două publicații nu e o comparație, e o listă.
    if len(randuri) < 2:
        return ""

    out = [TITLURI_START,
           '      <section class="ev-block neverificabil" style="border-left-color:#2265a3">',
           "        <h2>📰 Cum a titrat fiecare</h2>",
           '        <p class="ev-sub">Aceeași știre, în cuvintele fiecărei publicații. '
           "Noi nu le punem etichete de orientare — le punem titlurile alături, iar "
           "unghiul fiecăreia se vede singur.</p>"]
    for pub, titlu, url in randuri[:9]:
        out.append(
            f'        <div class="ev-item" style="padding:11px 0">'
            f'<p style="margin:0 0 4px;font-size:11.5px;letter-spacing:.08em;'
            f'text-transform:uppercase;color:var(--ink-faint);font-weight:800">{pub}</p>'
            f'<p style="margin:0;font-size:15.5px;line-height:1.4">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="text-decoration:underline;text-underline-offset:2px">{titlu}</a></p></div>')
    out += ["      </section>", TITLURI_END]
    return "\n".join(out) + "\n"


def pune_titluri(s, d):
    """Pune blocul imediat sub cardul spre sursa originală, sus în articol."""
    bloc = bloc_titluri(d)
    if TITLURI_START in s:
        return re.sub(re.escape(TITLURI_START) + r".*?" + re.escape(TITLURI_END) + r"\n?",
                      lambda m: bloc, s, count=1, flags=re.S)
    if not bloc:
        return s
    ancora = "Citește știrea originală →</span></span></a>\n"
    if ancora not in s:
        return s
    return s.replace(ancora, ancora + "\n" + bloc, 1)


def pune_data(s):
    """Injectează, o singură dată, ceasul din bara de sus."""
    if "Ediția de cafeluță'" in s or "</body>" not in s:
        return s
    return s.replace("</body>", DATA_JS + "</body>", 1)


def pune_citite(s):
    """Injectează, o singură dată, scriptul care ține minte ce s-a citit."""
    if "fb_citite" in s or "</body>" not in s:
        return s
    return s.replace("</body>", CITITE_JS + "</body>", 1)


def repara_share(s):
    """
    Pune partajarea nativă pe mobil, pe orice pagină care are butoanele.

    Se aplică la fiecare build, nu o singură dată: articolele noi le scrie botul
    după șablon, iar dacă reparația ar sta doar în șablon ar rămâne validă până
    la prima modificare a lui. Aici se autorepară.
    """
    # Atenție la ordinea verificărilor: paginile deja reparate o dată NU mai
    # conțin varianta veche, deci o ieșire devreme pe „n-are varianta veche" ar
    # fi lăsat pe loc toate articolele publicate. Exact așa a scăpat X
    # nereparat, după ce Facebook fusese rezolvat.
    if (SHARE_VECHI_FB not in s and SHARE_VECHI_X not in s
            and SHARE_INTERMEDIAR_X not in s):
        return s
    s = (s.replace(SHARE_VECHI_FB, SHARE_NOU_FB)
          .replace(SHARE_VECHI_X, SHARE_NOU_X)
          .replace(SHARE_INTERMEDIAR_X, SHARE_NOU_X))
    if "__fbMobil=/" not in s:
        s = s.replace("window.shareFB=function()", SHARE_DETECT + "window.shareFB=function()", 1)
    return s


def _verdict_normalizat(v):
    """Verdictele sunt text liber — sute de formulări. Le aducem la trei coșuri.

    Nu le standardizăm în articole: nuanța („probat, cu rezerve de cifră") e
    exact ce face site-ul util. Dar ca să poți NUMĂRA ceva, ai nevoie de
    categorii, iar prima literă a verdictului spune aproape mereu direcția.
    """
    t = _fara_diacritice((v or "").strip().lower())
    if t.startswith("probat") or t.startswith("context probat"):
        return "probat"
    if t.startswith(("contestat", "contrazis", "neconfirmat", "neverificabil",
                     "afirmatie rusa", "anunt neverificat")):
        return "contestat"
    return "mixt"


# ── Formularul de contact: îl facem să chiar trimită ────────────────────────
#
# Site-ul e static, fără backend — și rămâne așa intenționat: e ce am declarat
# și la reevaluarea de reputație, și e adevărat. Un script de mail pe server ar
# fi însemnat o țintă clasică de spam, pentru o funcție folosită de câteva ori
# pe lună.
#
# Așa că formularul compune un e-mail și deschide programul de mail al omului,
# cu totul completat. El apasă „trimite". Nimic nu pleacă fără știrea lui, iar
# adresa lui nu trece prin serverul nostru — o vedem doar când chiar ne scrie.
#
# Textul „machetă vizuală” de sub formular iese, fiindcă nu mai e adevărat.
CONTACT_JS = """<script>
(function(){
  var f = document.querySelector('form');
  if (!f) return;
  f.removeAttribute('onsubmit');
  f.addEventListener('submit', function(e){
    e.preventDefault();
    var val = function(id){ var el = document.getElementById(id); return el ? el.value.trim() : ''; };
    var nume = val('nume'), email = val('email'), mesaj = val('mesaj');
    var sel = document.getElementById('subiect');
    var tip = sel ? sel.options[sel.selectedIndex].text : 'Mesaj';
    if (!mesaj) {
      alert('Scrie un mesaj înainte de a trimite.');
      return;
    }
    var corp = mesaj + '\\n\\n— — —\\n';
    if (nume)  corp += 'Nume: ' + nume + '\\n';
    if (email) corp += 'Email: ' + email + '\\n';
    corp += 'Trimis din formularul de pe farabaliverne.ro';
    var adr = 'mailto:contact@farabaliverne.ro'
            + '?subject=' + encodeURIComponent('[' + tip + '] farabaliverne.ro')
            + '&body=' + encodeURIComponent(corp);
    window.location.href = adr;
    var n = document.getElementById('fb-trimis');
    if (n) n.style.display = 'block';
  });
})();
</script>"""

CONTACT_NOTA = ('<div id="fb-trimis" style="display:none;margin-top:14px;padding:12px 14px;'
                'border:1px solid var(--line-2);border-radius:10px;background:var(--card)">'
                'Ți s-a deschis programul de e-mail, cu mesajul completat. '
                'Apasă <b>trimite</b> acolo și ajunge la noi. Dacă nu s-a deschis nimic, '
                'scrie-ne direct la <b>contact@farabaliverne.ro</b>.</div>')


def pune_card_share(s, slug):
    """og:image → cardul de partajare, dacă a fost generat pentru articolul ăsta.

    Cardul CONȚINE fotografia articolului ca fundal, deci nu pierdem nimic din
    ce atrăgea privirea — doar punem peste ea afirmația și verdictul. Cine
    derulează pe telefon vede întâi imaginea; acum imaginea îi spune ceva.

    Dacă fișierul lipsește (articol foarte nou, cardurile se generează după),
    lăsăm og:image cum era. Mai bine poza veche decât o adresă care dă 404 —
    Facebook ține minte prima imagine pe care o vede pentru un link.
    """
    if not os.path.exists(os.path.join(ROOT, "img", "share", slug + ".jpg")):
        return s
    url = f"https://farabaliverne.ro/img/share/{slug}.jpg"
    s = re.sub(r'(<meta property="og:image" content=")[^"]+(")', r"\1" + url + r"\2", s, count=1)
    s = re.sub(r'(<meta name="twitter:image" content=")[^"]+(")', r"\1" + url + r"\2", s, count=1)
    return s


def pune_contact(s):
    """Face formularul de contact să funcționeze, oriunde ar fi el."""
    if "<form" not in s or "CONTACT-JS" in s:
        return s
    s = re.sub(r'Acest formular este momentan o machetă vizuală[^<]*',
               'Formularul deschide programul tău de e-mail, cu mesajul gata scris — '
               'îl trimiți tu, de la adresa ta. Sau scrie-ne direct la ', s)
    s = s.replace('</form>', '</form>\n' + CONTACT_NOTA, 1)
    s = s.replace('</body>', '<!--CONTACT-JS-->' + CONTACT_JS + '\n</body>', 1)
    return s


def build_cifre(arts, shell):
    """Pagina cu cifrele proprii — transparență numerică, nu declarații.

    Un site care spune „verificăm riguros" e un blog. Unul care arată câte
    afirmații a verificat, câte s-au probat, câte nu, și din câte publicații a
    citit, e verificabil el însuși. E singura pagină de pe site care se dă mai
    departe fără să fie un articol anume.

    Toate cifrele se calculează din `data/` la fiecare build. Nu există nicio
    valoare scrisă de mână aici — dacă scade ceva, se vede.
    """
    verd = collections.Counter()
    cat = collections.Counter()
    zile = collections.Counter()
    npr = nco = nop = 0
    surse_domenii = set()
    surse_total = 0

    for d in arts.values():
        verd[_verdict_normalizat(d.get("mainVerdict"))] += 1
        cat[d.get("category") or "—"] += 1
        if d.get("date"):
            zile[d["date"]] += 1
        npr += len(d.get("probat") or [])
        nco += len(d.get("contestat") or [])
        nop += len(d.get("opinie") or [])
        for lst in ("probat", "contestat", "opinie"):
            for x in (d.get(lst) or []):
                # Schema nu e uniformă: unele afirmații sunt obiecte cu `sources`,
                # altele doar text. Cele vechi, dinainte de a fixa forma.
                if not isinstance(x, dict):
                    continue
                for src in (x.get("sources") or []):
                    if not isinstance(src, dict):
                        continue
                    u = (src.get("url") or "")
                    if "://" in u and len(u.split("/")) > 2:
                        surse_total += 1
                        surse_domenii.add(u.split("/")[2].replace("www.", ""))

    total = len(arts)
    afirm = npr + nco + nop
    nzile = len(zile) or 1
    pe_zi = total / nzile

    def cutie(nr, eticheta, sub=""):
        return (f'<div style="flex:1 1 190px;background:var(--card);border:1px solid var(--line-2);'
                f'border-radius:14px;padding:18px 20px">'
                f'<div style="font-size:34px;font-weight:700;line-height:1.1">{nr}</div>'
                f'<div style="font-weight:600;margin-top:4px">{eticheta}</div>'
                + (f'<div style="opacity:.65;font-size:14px;margin-top:2px">{sub}</div>' if sub else "")
                + '</div>')

    def bara(nume, n, maxn, culoare):
        lat = max(2, round(100 * n / max(1, maxn)))
        return (f'<div style="margin:9px 0"><div style="display:flex;justify-content:space-between;'
                f'font-size:15px"><span>{html.escape(nume)}</span><b>{n}</b></div>'
                f'<div style="height:9px;background:var(--line-2);border-radius:6px;overflow:hidden;margin-top:4px">'
                f'<div style="width:{lat}%;height:100%;background:{culoare}"></div></div></div>')

    maxcat = max(cat.values()) if cat else 1
    culori = ["#4a7c59", "#6b8e5a", "#8a9a5b", "#a3a86b", "#b8ae7c", "#c9bb8e", "#d8caa2"]
    bare_cat = "".join(bara(k, v, maxcat, culori[i % len(culori)])
                       for i, (k, v) in enumerate(cat.most_common()))

    mv = max(verd.values()) if verd else 1
    bare_verd = (bara("Se probează", verd["probat"], mv, "#4a7c59")
                 + bara("Nu se susține / contestat", verd["contestat"], mv, "#b4553f")
                 + bara("Mixt — parte probată, parte nu", verd["mixt"], mv, "#b8912f"))

    main = f'''<div class="wrap">
      <h1 style="margin-bottom:6px">Cifrele noastre</h1>
      <p class="sum" style="max-width:70ch">Un site care spune despre sine că verifică riguros e
      doar un site. Aici sunt cifrele, calculate automat din arhivă la fiecare
      actualizare — nimic scris de mână. Dacă ceva scade, se vede.</p>

      <div style="display:flex;flex-wrap:wrap;gap:14px;margin:26px 0">
        {cutie(total, "verificări publicate", f"în {nzile} zile · ~{pe_zi:.0f} pe zi")}
        {cutie(afirm, "afirmații analizate", "fiecare cu sursele ei")}
        {cutie(len(surse_domenii), "publicații citate", f"{surse_total} linkuri către surse")}
      </div>

      <h2 style="margin-top:30px">Ce am găsit</h2>
      <p class="sum" style="max-width:70ch">Nu decretăm „adevărat” sau „fals”. Spunem ce se
      probează cu surse și ce nu, iar cititorul trage concluzia. Verdictele reale
      sunt nuanțate („probat, cu rezerve de cifră”); aici sunt strânse în trei
      coșuri, doar ca să poată fi numărate.</p>
      <div style="margin:18px 0;max-width:560px">{bare_verd}</div>

      <div style="display:flex;flex-wrap:wrap;gap:14px;margin:22px 0">
        {cutie(npr, "afirmații care se probează")}
        {cutie(nco, "afirmații contestate")}
        {cutie(nop, "marcate ca opinie", "nu se verifică, se semnalează")}
      </div>

      <h2 style="margin-top:30px">Despre ce scriem</h2>
      <div style="margin:18px 0;max-width:560px">{bare_cat}</div>

      <h2 style="margin-top:30px">Ce nu spun cifrele astea</h2>
      <p class="sum" style="max-width:70ch">Că avem dreptate. Numărul de verificări nu e o dovadă
      de calitate, iar o publicație citată de o sută de ori nu devine mai
      adevărată. Cifrele arată <b>cât</b> și <b>ce</b> am făcut — dacă am făcut
      bine se vede doar deschizând articolele și urmărind sursele. De-aia sunt
      linkurile acolo: ca să nu ne credeți pe cuvânt.</p>
      <p class="sum" style="max-width:70ch">Greșelile pe care le găsim le scriem
      la <a href="corectari.html">Corectări</a>. Cum lucrăm, la
      <a href="metodologie.html">Metodologie</a>.</p>
    </div>'''

    h = re.sub(r'<main>.*?</main>', lambda m: "<main>\n" + main + "\n  </main>", shell, count=1, flags=re.S)
    h = h.replace("<title>Fără Baliverne — Apă, paie… Adevăr</title>",
                  "<title>Cifrele noastre — Fără Baliverne</title>")
    for a, b in (('<link rel="canonical" href="https://farabaliverne.ro/">',
                  '<link rel="canonical" href="https://farabaliverne.ro/cifre.html">'),
                 ('<meta property="og:url" content="https://farabaliverne.ro/">',
                  '<meta property="og:url" content="https://farabaliverne.ro/cifre.html">'),
                 ('<meta property="og:title" content="Fără Baliverne — Apă, paie… Adevăr">',
                  '<meta property="og:title" content="Cifrele noastre — Fără Baliverne">'),
                 ('<meta name="twitter:title" content="Fără Baliverne — Apă, paie… Adevăr">',
                  '<meta name="twitter:title" content="Cifrele noastre — Fără Baliverne">'),
                 ('<a href="index.html" class="active">Acasă</a>', '<a href="index.html">Acasă</a>')):
        h = h.replace(a, b)
    return h


# „Cloșcu cu Puii de AUR" — SCOASĂ DEFINITIV, 5 septembrie 2026.
#
# Motivul e al fondatorului și e mai important decât secțiunea: o pagină
# construită în jurul unor oameni numiți arată ca o listă de vinovați, oricât
# de corecte ar fi verificările din ea. În cuvintele lui: „pare că site-ul e
# făcut să fie împotriva AUR, iar site-ul e făcut să prezinte adevărul ușor de
# înțeles". Cititorul nu vede metoda, vede ținta.
#
# Regula care rămâne: verificările se adună după AFIRMAȚII, nu după PERSOANE
# VIZATE. Codul și fișele sunt în istoricul git dacă vreodată e nevoie de ele.

# ---------- Letopisețul Planetei Pământ ----------
LETOPISET = os.path.join(ROOT, "data", "_letopiset.json")
LUNI_RO = ("ianuarie","februarie","martie","aprilie","mai","iunie",
           "iulie","august","septembrie","octombrie","noiembrie","decembrie")

LETOPISET_CSS = """
  .letopiset{border-top:1px solid rgba(255,255,255,.10);margin-top:26px;padding-top:22px}
  .letopiset h5{margin:0 0 4px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;
    color:rgba(255,255,255,.55)}
  .letopiset .sub{margin:0 0 14px;font-size:12.5px;color:rgba(255,255,255,.38);
    font-style:italic}
  .letopiset ol{list-style:none;margin:0;padding:0;display:grid;gap:9px}
  .letopiset li{font-size:13.5px;line-height:1.5;color:rgba(255,255,255,.72)}
  .letopiset .zi{display:inline-block;min-width:132px;color:rgba(255,255,255,.40);
    font-variant-numeric:tabular-nums}
  .letopiset a.s{color:rgba(255,255,255,.40);text-decoration:none;font-size:11.5px;
    border-bottom:1px dotted rgba(255,255,255,.25)}
  .letopiset a.s:hover{color:#fff;border-bottom-color:#fff}
  .letopiset .tot{display:inline-block;margin-top:14px;font-size:13px;
    color:rgba(255,255,255,.62);text-decoration:none;border-bottom:1px solid rgba(255,255,255,.22)}
  .letopiset .tot:hover{color:#fff;border-bottom-color:#fff}
  @media(max-width:640px){.letopiset .zi{display:block;min-width:0;margin-bottom:2px}}
"""


def _data_ro(zi):
    a, l, z = zi.split("-")
    return f"{int(z)} {LUNI_RO[int(l) - 1]} {a}"


def letopiset_incarca():
    if not os.path.exists(LETOPISET):
        return {}
    with open(LETOPISET, encoding="utf-8") as fh:
        return json.load(fh)


def letopiset_subsol(pref=""):
    """
    Blocul din subsol, sub «Cum stau probele». Ideea fondatorului: o secțiune
    în josul paginii, nu ușor vizibilă — o găsești dacă îți petreci timpul pe
    site. Arată ultima zi cu evenimente, atât.

    Regula lui: „câteva rânduri, nu multe povești... link dacă găsim, dar fără
    explicații. Mai bine fără decât cu." De-aia nu e nicio propoziție de context
    aici, doar fapta, locul, cifra și sursa.
    """
    d = letopiset_incarca()
    if not d:
        return ""
    zi = sorted(d)[-1]
    ev = d[zi][:6]
    if not ev:
        return ""
    randuri = []
    for e in ev:
        link = (f' <a class="s" href="{e["link"]}" target="_blank" rel="noopener">'
                f'{e.get("sursa","sursă")}</a>') if e.get("link") else ""
        randuri.append(f'          <li><span class="zi">{_data_ro(zi)}</span>'
                       f'<span class="fapt">{e["text"]}{link}</span></li>')
    return ('      <div class="letopiset">\n'
            '        <h5>Letopisețul Planetei Pământ</h5>\n'
            '        <p class="sub">Ce s-a întâmplat pe Pământ, zi de zi.</p>\n'
            '        <ol>\n' + "\n".join(randuri) + '\n        </ol>\n'
            f'        <a class="tot" href="{pref}letopiset.html">Tot letopisețul →</a>\n'
            '      </div>\n')


def pune_letopiset(s, pref=""):
    """Injectează blocul între marcaje, în subsol, înainte de rândul de copyright."""
    START, END = "<!-- AUTO:letopiset:start -->", "<!-- AUTO:letopiset:end -->"
    bloc = letopiset_subsol(pref)
    corp = f"{START}\n{bloc}      {END}\n"
    if START in s and END in s:
        return re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?",
                      lambda m: corp, s, count=1, flags=re.S)
    if LETOPISET_CSS.strip() not in s:
        s = s.replace("</style>", LETOPISET_CSS + "</style>", 1)
    i = s.find('<div class="foot-bottom">')
    if i < 0:
        return s
    return s[:i] + corp + "      " + s[i:]


def build_letopiset(shell):
    """Pagina întreagă: toate zilele, cea mai nouă sus."""
    d = letopiset_incarca()
    zile = sorted(d, reverse=True)
    if not zile:
        return None
    blocuri = []
    for zi in zile:
        ev = d[zi]
        if not ev:
            continue
        randuri = []
        for e in ev:
            link = (f' <a href="{e["link"]}" target="_blank" rel="noopener" '
                    f'style="color:var(--ink-faint);font-size:12px;text-decoration:none;'
                    f'border-bottom:1px dotted var(--line-2)">{e.get("sursa","sursă")}</a>'
                    ) if e.get("link") else ""
            randuri.append(
                f'          <li style="margin:0 0 8px;line-height:1.6">{e["text"]}{link}</li>')
        blocuri.append(
            '        <section style="margin:0 0 30px">\n'
            f'          <h2 style="font-family:Georgia,serif;font-size:19px;margin:0 0 10px;'
            f'padding-bottom:7px;border-bottom:1px solid var(--line)">{_data_ro(zi)}</h2>\n'
            '          <ul style="list-style:none;margin:0;padding:0;color:var(--ink-soft);'
            'font-size:15px">\n' + "\n".join(randuri) + '\n          </ul>\n'
            '        </section>')
    total = sum(len(v) for v in d.values())
    main = ('    <div class="wrap" style="max-width:760px;margin:0 auto;padding:0 20px">\n'
            '      <div style="padding:30px 0 10px">\n'
            '        <h1 style="font-family:Georgia,serif;font-size:34px;margin:0 0 10px">'
            'Letopisețul Planetei Pământ</h1>\n'
            '        <p style="color:var(--ink-soft);font-size:16px;line-height:1.6;max-width:64ch">'
            'Ce s-a întâmplat pe Pământ, zi de zi: cutremure, erupții, inundații, cicloane. '
            'Fapta, locul, cifra și sursa — fără explicații și fără comentariu. '
            'Un letopiseț nu interpretează, doar ține minte.</p>\n'
            f'        <p style="color:var(--ink-faint);font-size:13px;margin-top:10px">'
            f'{total} de evenimente, din {len(zile)} '
            f'{"zi" if len(zile) == 1 else "zile"}. Se completează zilnic, la 23:59 UTC. '
            f'Surse: <a href="https://earthquake.usgs.gov" target="_blank" rel="noopener" '
            f'style="color:inherit">USGS</a> și <a href="https://www.gdacs.org" target="_blank" '
            f'rel="noopener" style="color:inherit">GDACS</a>.</p>\n'
            '      </div>\n'
            '      <div style="margin:24px 0 50px">\n' + "\n".join(blocuri) + '\n      </div>\n'
            '    </div>')
    h = re.sub(r'<main>.*?</main>', lambda m: "<main>\n" + main + "\n  </main>",
               shell, count=1, flags=re.S)
    for a, b in (
        ("<title>Fără Baliverne — Apă, paie… Adevăr</title>",
         "<title>Letopisețul Planetei Pământ — Fără Baliverne</title>"),
        ('<link rel="canonical" href="https://farabaliverne.ro/">',
         '<link rel="canonical" href="https://farabaliverne.ro/letopiset.html">'),
        ('<meta property="og:url" content="https://farabaliverne.ro/">',
         '<meta property="og:url" content="https://farabaliverne.ro/letopiset.html">'),
        ('<meta property="og:title" content="Fără Baliverne — Apă, paie… Adevăr">',
         '<meta property="og:title" content="Letopisețul Planetei Pământ — Fără Baliverne">'),
        ('<meta name="twitter:title" content="Fără Baliverne — Apă, paie… Adevăr">',
         '<meta name="twitter:title" content="Letopisețul Planetei Pământ — Fără Baliverne">'),
        ('<a href="index.html" class="active">Acasă</a>', '<a href="index.html">Acasă</a>'),
    ):
        h = h.replace(a, b)
    return h


def build_search_page(arts, shell):
    """Pagină de căutare client-side (filtrează toate articolele după cuvinte)."""
    idx = []
    for d in sorted(arts.values(), key=lambda d: d.get("date",""), reverse=True):
        idx.append({"slug": d["slug"], "title": d["title"], "cat": d["category"],
                    "dek": trunc(d.get("dek",""), 150), "persoane": d.get("persoane") or []})
    main_html = ('    <div class="wrap" style="max-width:760px;margin:0 auto;padding:0 20px">\n'
        '      <div style="padding:30px 0 6px">\n'
        '        <h1 style="font-family:Georgia,serif;font-size:34px;margin:0 0 8px">Caută o afirmație</h1>\n'
        '        <p style="color:var(--ink-faint);font-size:16px">Scrie un cuvânt — nume, subiect, țară — și-ți arătăm verificările potrivite.</p>\n'
        '        <input id="q" type="search" placeholder="ex: Georgescu, inflație, China, eclipsă…" autofocus '
        'style="width:100%;padding:14px 16px;font-size:17px;border:1px solid var(--line-2);border-radius:12px;background:var(--card);color:inherit;margin-top:14px;font-family:inherit">\n'
        '      </div>\n'
        '      <div id="res" style="display:grid;gap:10px;margin:14px 0 40px"></div>\n'
        '    </div>\n'
        '    <script>window.FB_SEARCH = ' + json.dumps(idx, ensure_ascii=False) + ';</script>\n'
        '''    <script>
    (function(){
      var D=window.FB_SEARCH||[],q=document.getElementById('q'),r=document.getElementById('res');
      function nrm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');}
      function esc(s){return (s||'').replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
      function render(l){ if(!l.length){r.innerHTML='<div style="color:var(--ink-faint);padding:12px">Nimic încă — încearcă alt cuvânt.</div>';return;}
        r.innerHTML=l.map(function(a){return '<a href="a/'+a.slug+'.html" style="display:block;text-decoration:none;color:inherit;border:1px solid var(--line-2);background:var(--card);border-radius:12px;padding:14px 16px"><div style="font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)">'+esc(a.cat)+'</div><div style="font-weight:700;margin:3px 0 4px">'+esc(a.title)+'</div><div style="font-size:13.5px;color:var(--ink-faint)">'+esc(a.dek)+'</div></a>';}).join('');}
      function run(){var v=nrm(q.value).trim(); if(!v){render(D.slice(0,8));return;} var t=v.split(/\\s+/);
        render(D.filter(function(a){var h=nrm(a.title+' '+a.dek+' '+a.cat+' '+(a.persoane||[]).join(' ')); return t.every(function(x){return h.indexOf(x)>-1;});}).slice(0,30));}
      q.addEventListener('input',run); run();
    })();
    </script>''')
    _new = "<main>\n"+main_html+"\n  </main>"
    h = re.sub(r'<main>.*?</main>', lambda m: _new, shell, count=1, flags=re.S)
    h = h.replace("<title>Fără Baliverne — Apă, paie… Adevăr</title>", "<title>Caută o afirmație — Fără Baliverne</title>")
    h = h.replace('<link rel="canonical" href="https://farabaliverne.ro/">', '<link rel="canonical" href="https://farabaliverne.ro/cauta.html">')
    h = h.replace('<meta property="og:url" content="https://farabaliverne.ro/">', '<meta property="og:url" content="https://farabaliverne.ro/cauta.html">')
    h = h.replace('<a href="index.html" class="active">Acasă</a>', '<a href="index.html">Acasă</a>')
    return h

def build_rss(arts, momente_pub):
    """feed.xml — RSS 2.0 cu ultimele articole.

    Un site de știri fără feed e invizibil pentru jumătate din infrastructura
    web: agregatoarele, cititoarele de știri, Google News, boții care
    redistribuie. Costă o funcție și se regenerează singur, ca sitemap-ul.

    Punem ultimele 50, nu tot: un feed cu 362 de intrări e greu de digerat
    pentru cititoare și nimeni nu derulează atât.
    """
    from email.utils import format_datetime
    from zoneinfo import ZoneInfo
    B = "https://farabaliverne.ro/"

    def esc(t):
        return html.escape((t or "").strip(), quote=False)

    # cele mai noi întâi, după momentul publicării (din git), cu data ca rezervă
    lista = [d for slug, d in arts.items()
             if os.path.exists(os.path.join(ROOT, "a", slug + ".html"))]
    lista.sort(key=lambda d: (momente_pub.get(d["slug"], ""), d.get("date", "")),
               reverse=True)

    items = []
    for d in lista[:50]:
        link = f"{B}a/{d['slug']}.html"
        cand = momente_pub.get(d["slug"]) or (d.get("date") or "")
        try:
            dt = datetime.fromisoformat(cand)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("Europe/Bucharest"))
            pub = format_datetime(dt)
        except ValueError:
            pub = ""
        verdict = (d.get("mainVerdict") or "").strip()
        np_, nc_ = len(d.get("probat") or []), len(d.get("contestat") or [])
        rezumat = (d.get("dek") or "").strip()
        if verdict:
            rezumat += f"\n\nUnde bat probele: {verdict}."
        if np_ or nc_:
            rezumat += f" Verificate: {np_} probate, {nc_} contestate."
        items.append(
            "    <item>\n"
            f"      <title>{esc(d.get('title'))}</title>\n"
            f"      <link>{link}</link>\n"
            f"      <guid isPermaLink=\"true\">{link}</guid>\n"
            + (f"      <pubDate>{pub}</pubDate>\n" if pub else "")
            + f"      <category>{esc(d.get('category'))}</category>\n"
            f"      <description>{esc(rezumat)}</description>\n"
            "    </item>")

    acum = format_datetime(datetime.now(ZoneInfo("Europe/Bucharest")))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
           '  <channel>\n'
           '    <title>Fără Baliverne</title>\n'
           f'    <link>{B}</link>\n'
           '    <description>Agregăm știrile din presa românească și internațională, '
           'verificăm ce se probează cu surse și lăsăm cititorul să tragă concluzia.</description>\n'
           '    <language>ro</language>\n'
           f'    <lastBuildDate>{acum}</lastBuildDate>\n'
           f'    <atom:link href="{B}feed.xml" rel="self" type="application/rss+xml"/>\n'
           + "\n".join(items) + "\n  </channel>\n</rss>\n")
    open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8").write(xml)
    return len(items)


def build_sitemap(arts):
    """Regenerează sitemap.xml cu TOATE articolele + paginile-hub (SEO Google)."""
    from zoneinfo import ZoneInfo
    B = "https://farabaliverne.ro/"
    today = datetime.now(ZoneInfo("Europe/Bucharest")).strftime("%Y-%m-%d")
    rows = ['<url><loc>%s</loc><lastmod>%s</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>' % (B, today)]
    # articolele (cel mai nou lastmod = data articolului dacă există)
    for slug in sorted(arts.keys()):
        if not os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            continue
        d = arts[slug]
        lm = (d.get("date") or today)[:10]
        rows.append('<url><loc>%sa/%s.html</loc><lastmod>%s</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>' % (B, slug, lm))
    # paginile-hub + credibilitate
    # Verificarea
    # `os.path.exists` de mai jos o sare singură când secțiunea e stinsă, deci
    # sitemap-ul nu trimite niciodată Google spre un 404.
    # Paginile de parlamentar — dar numai cele care au măcar o verificare.
    # Fără ele în sitemap, Google le-ar găsi doar prin linkurile din hemiciclu,
    # care sunt puse de JavaScript.
    #
    # 🔴 Pe 4 septembrie 2026, 451 din 464 erau schelet gol: nume, partid, cifre
    # de activitate, nicio verificare. Le ceream lui Google să le viziteze pe
    # toate, în timp ce bugetul lui de crawl era ~60 de pagini pe zi și noi
    # publicam ~23 de articole pe zi. Rezultatul: 566 de pagini rămase
    # „descoperite, neindexate" — și restanța creștea, nu scădea.
    # Fișele goale poartă și `noindex` (vezi build_parlamentari.py); aici doar
    # nu le mai cerem. Când omul primește prima verificare, intră singură înapoi.
    _pdir = os.path.join(ROOT, "parlamentar")
    if os.path.isdir(_pdir):
        for _f in sorted(os.listdir(_pdir)):
            if not _f.endswith(".html"):
                continue
            try:
                _h = open(os.path.join(_pdir, _f), encoding="utf-8").read()
            except OSError:
                continue
            if 'href="../a/' not in _h:      # fișă fără nicio verificare
                continue
            rows.append('<url><loc>%sparlamentar/%s</loc><lastmod>%s</lastmod>'
                        '<changefreq>monthly</changefreq><priority>0.5</priority></url>'
                        % (B, _f, time.strftime("%Y-%m-%d")))

    for pg in ("politicieni.html","parlament.html","cauta.html","cifre.html","letopiset.html","publicitate.html","metodologie.html",
               "cine-suntem.html","corectari.html","contact.html","termeni.html","confidentialitate.html"):
        if os.path.exists(os.path.join(ROOT, pg)):
            pr = "0.6" if pg in ("politicieni.html","parlament.html","cauta.html","cifre.html") else "0.4"
            rows.append('<url><loc>%s%s</loc><lastmod>%s</lastmod><changefreq>monthly</changefreq><priority>%s</priority></url>' % (B, pg, today, pr))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  '
           + "\n  ".join(rows) + "\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(xml)
    build_sitemap_news(arts)
    return len(rows)


def build_sitemap_news(arts):
    """
    Sitemap separat pentru Google News, cu articolele din ultimele 48 de ore.

    Google News nu se uită în sitemap-ul mare — vrea unul dedicat, cu schema
    `news`, care conține DOAR ce e proaspăt. Ăsta e canalul gratuit prin care
    o știre poate ajunge la cititori în ziua în care contează, nu peste o
    săptămână, când Google ajunge la ea prin sitemap-ul obișnuit.

    Regula lui Google: maximum 1.000 de URL-uri și doar articole mai noi de
    48 de ore. Ce e mai vechi trebuie scos, altfel sitemap-ul e respins.
    """
    from datetime import datetime, timedelta, timezone
    B = "https://farabaliverne.ro/"
    limita = datetime.now(timezone.utc) - timedelta(hours=48)
    rows = []
    for slug in sorted(arts.keys()):
        if not os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            continue
        a = arts[slug]
        d = (a.get("date") or "")[:10]
        if not d:
            continue
        try:
            cand = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if cand < limita:
            continue
        titlu = (a.get("title") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append(
            '<url><loc>%sa/%s.html</loc>'
            '<news:news><news:publication>'
            '<news:name>Fără Baliverne</news:name><news:language>ro</news:language>'
            '</news:publication>'
            '<news:publication_date>%s</news:publication_date>'
            '<news:title>%s</news:title></news:news></url>' % (B, slug, d, titlu))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
           '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n  '
           + "\n  ".join(rows) + "\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap-news.xml"), "w", encoding="utf-8").write(xml)
    return len(rows)


def build_stare(arts):
    """
    Pulsul site-ului: un fișier mic, citibil de afară, care spune când a fost
    construit ultima dată și câte articole avem.

    Rostul e că nu putem afla altfel dacă publicarea chiar a ajuns pe server.
    Pe 12 august, git-ul era la zi și site-ul rămăsese în urmă 18 ore — nimic
    din afară nu putea deosebi cele două stări. Fișierul ăsta poate: dacă
    deploy-ul nu ajunge, el rămâne vechi pe farabaliverne.ro.

    E `.txt`, nu `.json`, fiindcă `.htaccess` refuză toate fișierele `.json`
    ca să nu se vadă sursele de build. Regula aia e bună și nu merită atinsă
    pentru un fișier — un `.htaccess` stricat pică tot site-ul. Conținutul e
    tot JSON.

    Îl citește `scripts/veghe.py`.
    """
    ultim = max(arts.values(), key=lambda a: a.get("date") or "", default={})
    stare = {
        "construit": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "articole": len(arts),
        "ultimul": ultim.get("slug", ""),
        "ultima_data": ultim.get("date", ""),
    }
    open(os.path.join(ROOT, "stare.txt"), "w", encoding="utf-8").write(
        json.dumps(stare, ensure_ascii=False, indent=1) + "\n")


def main():
    arts = load()
    total = len(arts)
    # 1. feed
    html = open(IDX, encoding="utf-8").read()
    mom = momente()
    _idx, _rar, _obis = indice_inrudite(arts)
    _fire = fire(arts, _idx, _rar, _obis)
    html = replace_feed(html, build_feed(arts, mom) + build_featured_script(arts, mom))
    open(IDX, "w", encoding="utf-8").write(html)
    # 2. politicieni (clonează shell-ul din index)
    shell = open(IDX, encoding="utf-8").read()
    pol, nwith, nwithout = build_politicieni(arts, shell)
    open(os.path.join(ROOT, "politicieni.html"), "w", encoding="utf-8").write(pol)
    open(os.path.join(ROOT, "cauta.html"), "w", encoding="utf-8").write(build_search_page(arts, shell))
    open(os.path.join(ROOT, "cifre.html"), "w", encoding="utf-8").write(build_cifre(arts, shell))
    _leto = build_letopiset(shell)
    if _leto:
        open(os.path.join(ROOT, "letopiset.html"), "w", encoding="utf-8").write(_leto)
    # 2b. sitemap.xml (toate articolele + hub) pentru Google
    nsitemap = build_sitemap(arts)
    # 2c. feed.xml — RSS, ca site-ul sa fie citibil de agregatoare si cititoare
    nfeed = build_rss(arts, momente())
    # 3. count pe toate paginile
    # Toate paginile, nu doar cele generate: și cele statice (termeni, contact,
    # metodologie, 404…) au butoanele de partajare, deci și ele au nevoie de
    # reparația pentru mobil. Înainte rămâneau pe varianta veche, care pe telefon
    # deschidea Facebook fără să trimită nimic.
    pages = [IDX] + glob.glob(os.path.join(ROOT,"a","*.html")) + \
            [os.path.join(ROOT,x) for x in ("politicieni.html","publicitate.html","cauta.html",
                                            "cifre.html","letopiset.html","metodologie.html","cine-suntem.html",
                                            "corectari.html","contact.html","termeni.html",
                                            "confidentialitate.html","404.html")]
    tb = now_edition()
    date_re = re.compile(r'(<div class="date">).*?(</div>)', re.S)
    hub = {IDX, os.path.join(ROOT,"politicieni.html"), os.path.join(ROOT,"publicitate.html"),
           os.path.join(ROOT,"cauta.html")}
    for f in pages:
        if not os.path.exists(f): continue
        s = open(f, encoding="utf-8").read(); orig = s
        s = re.sub(r'\d+ verificări publicate', f'{total} verificări publicate', s)
        s = repara_share(s)
        s = pune_data(s)
        s = pune_citite(s)
        s = pune_contact(s)
        if "/a/" in f.replace(os.sep, "/") or os.sep + "a" + os.sep in f:
            s = pune_card_share(s, os.path.basename(f)[:-5])
        # „Cum a titrat fiecare" — doar pe paginile de articol, din datele lor.
        if os.sep + "a" + os.sep in f:
            _slug = os.path.basename(f)[:-5]
            if _slug in arts:
                s = pune_titluri(s, arts[_slug])
                s = pune_vezi_si(s, _slug, arts, _idx, _rar, _obis, _fire)
        # Linkul spre Parlament, pe TOATE paginile. Se injectează aici, nu în
        # şablon: articolele noi se scriu după
        # `a/legea-integritatii...`, care n-are linkul.
        if os.path.exists(os.path.join(ROOT, "parlament.html")) and 'parlament.html">Parlament' not in s:
            for pref in ("", "../"):
                s = s.replace(
                    f'<a href="{pref}politicieni.html">Politicieni</a>',
                    f'<a href="{pref}politicieni.html">Politicieni</a>\n'
                    f'      <a href="{pref}parlament.html">Parlament</a>')

        # Letopisețul, în subsolul fiecărei pagini. Articolele stau în `a/`,
        # deci au nevoie de prefix `../` pentru link.
        s = pune_letopiset(s, "../" if os.sep + "a" + os.sep in f else "")
        # Cloșcu a fost scoasă definitiv. Curățarea rămâne pentru totdeauna,
        # necondiționat: linkul se propagă prin șablonul articolelor, deci fără
        # ea ar reapărea la primul articol scris după un fișier vechi.
        s = re.sub(r'\n?\s*<a href="(?:\.\./)?closcu\.html">Cloșcu cu Puii de AUR</a>', "", s)
        if f in hub:  # data + „ediția de X" pe paginile-hub (după momentul publicării)
            s = date_re.sub(lambda m: m.group(1) + tb + m.group(2), s)
        # Articol: poza proprie la share (og:image) + date structurate (SEO)
        if os.sep + "a" + os.sep in f:
            mh = re.search(r'<img src="([^"]+)"[^>]*object-fit:cover;z-index:1', s)
            img = mh.group(1) if mh else "https://farabaliverne.ro/og-cover.png"
            if img.startswith("../"):  # cale locală relativă -> URL absolut (og:image nu poate fi relativ)
                img = "https://farabaliverne.ro/" + img[len("../"):]
            # Cardul de partajare are prioritate: conține deja fotografia ca
            # fundal, plus afirmația și verdictul. Poza singură rămâne doar
            # pentru articolele fără card (foarte noi, cardul se face după).
            slug_f = os.path.splitext(os.path.basename(f))[0]
            are_card = os.path.exists(os.path.join(ROOT, "img", "share", slug_f + ".jpg"))
            if mh and not are_card:
                s = re.sub(r'(<meta property="og:image" content=")[^"]*(">)', lambda m: m.group(1)+img+m.group(2), s, count=1)
                s = re.sub(r'(<meta name="twitter:image" content=")[^"]*(">)', lambda m: m.group(1)+img+m.group(2), s, count=1)
            slug = os.path.splitext(os.path.basename(f))[0]
            d = arts.get(slug)
            if d:
                ld = {"@context":"https://schema.org","@type":"NewsArticle","headline":d["title"],
                      "image":[img],"datePublished":d.get("date",""),"dateModified":d.get("date",""),
                      "author":{"@type":"Organization","name":"Fără Baliverne","url":"https://farabaliverne.ro"},
                      "publisher":{"@type":"Organization","name":"Fără Baliverne","logo":{"@type":"ImageObject","url":"https://farabaliverne.ro/apple-touch-icon.png"}},
                      "mainEntityOfPage":"https://farabaliverne.ro/a/"+slug+".html","description":d.get("dek","")}
                # ClaimReview: cardul de identitate al unei verificari. Fara el,
                # Google nu stie ca pagina e un fact-check si nu intra in Fact
                # Check Explorer, unde cauta jurnalistii. Vezi `verdict_scurt`.
                blocuri = [ld]
                eticheta = verdict_scurt(d.get("mainVerdict"))
                if eticheta:
                    cr = {"@context":"https://schema.org","@type":"ClaimReview",
                          "url":"https://farabaliverne.ro/a/"+slug+".html",
                          "claimReviewed":d["title"],
                          "datePublished":d.get("date",""),
                          "author":{"@type":"Organization","name":"Fără Baliverne",
                                    "url":"https://farabaliverne.ro"},
                          "reviewRating":{"@type":"Rating","alternateName":eticheta}}
                    sursa = d.get("url")
                    if sursa:
                        cr["itemReviewed"] = {"@type":"Claim",
                            "appearance":{"@type":"CreativeWork","url":sursa}}
                    blocuri.append(cr)
                lds = '<script type="application/ld+json">' + json.dumps(blocuri if len(blocuri) > 1 else ld, ensure_ascii=False) + '</script>'
                if 'application/ld+json' in s:
                    s = re.sub(r'<script type="application/ld\+json">.*?</script>', lambda m: lds, s, count=1, flags=re.S)
                elif '</head>' in s:
                    s = s.replace('</head>', '  ' + lds + '\n</head>', 1)
        # Linkul catre pagina de cifre, langa Metodologie in subsol: acolo stau
        # paginile de credibilitate, si acolo se uita cineva care vrea sa stie
        # daca ne poate crede.
        if 'href="cifre.html"' not in s and '<a href="metodologie.html">Metodologie</a>' in s:
            s = s.replace('<a href="metodologie.html">Metodologie</a>',
                          '<a href="metodologie.html">Metodologie</a>\n'
                          '            <a href="cifre.html">Cifrele noastre</a>', 1)

        # In fruntea paginii ramane UN SINGUR buton: cel catre Moldova.
        # „Gabe it" a fost scos de aici pe 27 august, la cererea fondatorului —
        # ramane doar in cutia din dreapta, langa Facebook si X, unde e locul lui.
        s = re.sub(r'\s*<a href="#" onclick="gabeIt\(\);return false" '
                   r'class="btn-support">[^<]*</a>', "", s, count=1)
        if 'class="btn-md"' not in s and '<div class="support">' in s:
            s = s.replace('<div class="support">',
                          '<div class="support">\n        '
                          '<a href="/moldova/" class="btn-md" '
                          'title="Fara Scorneli — verificarile din Republica Moldova">'
                          'Fără Scorneli · Moldova</a>', 1)
        if ".btn-md{" not in s and ".btn-support{" in s:
            s = s.replace("  .btn-support{", STIL_MD + "  .btn-support{", 1)

        # Butonul mic din meniu, pe fiecare pagina. Cerut de fondator
        # pe 27 august. Se pune dupa Parlament, fiindca e sectiune, nu categorie.
        # Are stil propriu (chenar, nu pastila plina) ca sa se vada ca duce in
        # alta casa — Fara Scorneli — nu la o rubrica de-a noastra.
        # Paginile de articol au meniul cu legaturi relative („../parlament.html"),
        # cele din radacina fara. Butonul insa duce mereu la adresa absoluta.
        if 'href="/moldova/"' not in s:
            for tinta in ('<a href="parlament.html">Parlament</a>',
                          '<a href="../parlament.html">Parlament</a>'):
                if tinta in s:
                    s = s.replace(tinta, tinta + '\n'
                                  '            <a href="/moldova/" class="md" '
                                  'title="Fără Scorneli — verificările din Republica Moldova">'
                                  '🇲🇩 Moldova</a>', 1)
                    break
        if ".nav .md{" not in s and ".nav .search{" in s:
            s = s.replace("  .nav .search{",
                          "  .nav .md{\n"
                          "    color:var(--accent);border:1px solid var(--accent);\n"
                          "    background:transparent;\n"
                          "  }\n"
                          "  .nav .md:hover{color:#fff;background:var(--accent)}\n"
                          "  .nav .search{", 1)

        # Linkul catre RSS, pe fiecare pagina: asa il gasesc cititoarele de
        # stiri si extensiile de browser, fara sa stie adresa pe de rost.
        if "application/rss+xml" not in s and "</head>" in s:
            s = s.replace('</head>',
                          '  <link rel="alternate" type="application/rss+xml" '
                          'title="Fără Baliverne — articole noi" '
                          'href="https://farabaliverne.ro/feed.xml">\n</head>', 1)
        if s != orig: open(f, "w", encoding="utf-8").write(s)
    build_stare(arts)
    print(f"✅ build: {total} articole | RSS {nfeed} | politicieni {nwith} cu verificări + {nwithout} în curând | sitemap {nsitemap} URL-uri")

    # Fără Scorneli — Moldova. Se reface AICI, nu separat: pagina se croiește
    # din index.html abia construit, iar cine uită s-o cheme lasă secțiunea
    # moldovenească înghețată în timp ce acasă-ul merge înainte. S-a întâmplat
    # pe 29 august 2026 — două articole moldovenești publicate, dar /moldova/
    # arăta încă ediția de acum trei zile. Rulează după build_site, niciodată
    # înainte, și nu doboară ediția dacă pică.
    md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_moldova.py")
    r = subprocess.run(["python3", md], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip() or "⚠️ moldova: fără răspuns")

    # Fișele parlamentarilor. Aceeași poveste, descoperită pe 4 septembrie 2026:
    # nimic nu chema `build_parlamentari.py`, așa că toate cele 464 de pagini
    # înghețaseră pe 23 august — scriau „521 de verificări" când site-ul avea
    # deja 719, și încă purtau un buton scos de atunci. Douăsprezece zile în
    # care nimeni n-a observat, fiindcă restul site-ului mergea impecabil.
    #
    # Rulează DUPĂ build_site (își croiește pagina din index.html abia făcut) și
    # ÎNAINTE de sitemap-ul final de mai jos, fiindcă sitemap-ul se uită în
    # fișiere ca să afle cine are verificări și cine e schelet gol.
    pl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_parlamentari.py")
    r = subprocess.run(["python3", pl], capture_output=True, text=True)
    print((r.stdout or r.stderr).strip() or "⚠️ parlamentari: fără răspuns")

    # Sitemap-ul, încă o dată: prima rulare l-a scris pe baza fișelor VECHI.
    # Dacă un parlamentar tocmai și-a primit prima verificare, abia acum se știe.
    if r.returncode == 0:
        print(f"✅ sitemap refăcut: {build_sitemap(arts)} URL-uri")

if __name__ == "__main__":
    main()

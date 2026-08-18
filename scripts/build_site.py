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
import json, re, glob, os, unicodedata, subprocess
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX  = os.path.join(ROOT, "index.html")

FEATURED = "legea-integritatii-vot-final"   # articolul din hero (rămâne curatoriat manual)
CAT_ORDER = ["Politică", "Economie", "Extern", "Știință", "Media de stat", "Social", "Sport"]
CAT_ID = {"Politică":"politica","Economie":"economie","Extern":"extern","Știință":"stiinta","Media de stat":"media-de-stat","Social":"social","Sport":"sport"}
GCLASS = {"Politică":"g-pol","Economie":"g-eco","Social":"g-soc","Sport":"g-sport","Extern":"g-ext","Știință":"g-sci","Media de stat":"g-state"}
CATGLYPH = {"Politică":"⚖️","Economie":"💶","Social":"👥","Extern":"🌍","Sport":"⚽","Știință":"🔬","Media de stat":"📡"}

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
CARDURI_PE_CATEGORIE = 6


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

def build_politicieni(arts, shell):
    byp = {}
    for d in arts.values():
        for n in (d.get("persoane") or []): byp.setdefault(n, []).append(d)
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
SHARE_NOU_X = ("window.shareX=function(){if(window.__fbMobil&&navigator.share)"
               "{navigator.share({title:T,url:U}).catch(function(){});return;}"
               "window.open('https://twitter.com/intent/tweet?url='+e(U)+'&text='+e(T),"
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
    if SHARE_VECHI_FB not in s and SHARE_VECHI_X not in s:
        return s
    s = s.replace(SHARE_VECHI_FB, SHARE_NOU_FB).replace(SHARE_VECHI_X, SHARE_NOU_X)
    if "__fbMobil=/" not in s:
        s = s.replace("window.shareFB=function()", SHARE_DETECT + "window.shareFB=function()", 1)
    return s


def build_closcu(arts, shell):
    """
    „Cloșcu cu Puii de AUR" — fișe de persoană + verificările fiecăruia.

    E pagină-hub, NU categorie: un articol despre procesul lui Georgescu e
    legitim la Politică și trebuie să rămână acolo. Aici e adunat după
    `persoane[]`, exact ca pagina Politicieni — deci un articol apare în ambele
    locuri fără să fie mutat.
    """
    # Comutator, ca la Debate pe GABE: secțiunea se construiește doar când e
    # pornită explicit. E cel mai sensibil conținut de pe site — vizează oameni
    # numiți — deci publicarea rămâne o decizie luată o dată, în clar, nu ceva
    # care se întâmplă fiindcă a rulat botul.
    #     CLOSCU_ENABLED=1 python3 scripts/build_site.py
    if os.environ.get("CLOSCU_ENABLED", "").strip() not in ("1", "true", "da"):
        return None
    fise_path = os.path.join(ROOT, "data", "_fise-closcu.json")
    if not os.path.exists(fise_path):
        return None
    F = json.load(open(fise_path, encoding="utf-8"))

    byp = {}
    for d in arts.values():
        for p in (d.get("persoane") or []):
            byp.setdefault(p, []).append(d)

    def fisa(o):
        col = o.get("culoare", "#8a6b1f")
        lst = sorted(byp.get(o["nume"], []), key=lambda d: d.get("date", ""), reverse=True)
        rows = ""
        for c in o.get("cv", []):
            srcs = "".join(
                f'<a href="{s["url"]}" target="_blank" rel="noopener noreferrer">'
                f'<span class="fav" style="background:#556050"></span>'
                f'<span class="lbl">{s["name"]}</span></a>' for s in c.get("surse", []))
            rows += (f'            <div class="ev-item">\n'
                     f'              <p><b style="color:{col}">{c["k"]}.</b> {c["v"]}</p>\n'
                     f'              <div class="ev-sources">{srcs}</div>\n'
                     f'            </div>\n')
        # Afirmațiile publice — miezul secțiunii. NU numărăm cât au muncit:
        # o sută de proiecte co-semnate nu spun nimic despre om. Ce spune ceva e
        # ce a susținut în public și dacă se susține când pui documentele lângă.
        afirm = ""
        for a in o.get("afirmatii", []):
            srcs = "".join(
                f'<a href="{s["url"]}" target="_blank" rel="noopener noreferrer">'
                f'<span class="fav" style="background:#556050"></span>'
                f'<span class="lbl">{s["name"]}</span></a>' for s in a.get("surse", []))
            afirm += (
                f'            <div class="ev-item">\n'
                f'              <p style="font-size:17px;line-height:1.45"><b>{a["afirmatie"]}</b></p>\n'
                f'              <p style="font-size:13px;color:var(--ink-faint);margin:-4px 0 10px">'
                f'{a["unde"]}</p>\n'
                f'              <p>{a["dovezi"]}</p>\n'
                f'              <p style="margin:0 0 10px"><span class="chip soft bad sm">'
                f'unde bat probele: {a["unde_bat"]}</span></p>\n'
                f'              <div class="ev-sources">{srcs}</div>\n'
                f'            </div>\n')
        if afirm:
            afirm = (f'          <section class="ev-block contestat" style="border-left-color:#c23b2e">\n'
                     f'            <h2>🗣️ Ce a susținut public</h2>\n'
                     f'            <p class="ev-sub">Afirmația, unde a spus-o, și ce arată documentele. '
                     f'Nu spunem că a mințit — arătăm de ce nu se susține.</p>\n{afirm}'
                     f'          </section>\n')

        # Citate din propriile cărți. Cea mai solidă dovadă care există: nu e
        # „scos din context" și nu i-a fost atribuit de altcineva — a scris-o,
        # a publicat-o sub numele lui, se poate cumpăra și verifica.
        c = o.get("carte")
        if c:
            cit = ""
            for q in c["citate"]:
                cit += (f'            <div class="ev-item">\n'
                        f'              <p style="font-family:Georgia,serif;font-size:17.5px;'
                        f'line-height:1.5">{q["text"]}</p>\n'
                        f'              <p style="font-size:13.5px;color:var(--ink-soft);margin:0">'
                        f'↳ {q["nota"]}</p>\n'
                        f'            </div>\n')
            srcs = "".join(
                f'<a href="{s["url"]}" target="_blank" rel="noopener noreferrer">'
                f'<span class="fav" style="background:#556050"></span>'
                f'<span class="lbl">{s["name"]}</span></a>'
                for s in c["surse"] + [c["catalog"]])
            afirm += (f'          <section class="ev-block neverificabil">\n'
                      f'            <h2>📕 Din cartea lui: {c["titlu"]}</h2>\n'
                      f'            <p class="ev-sub">{c["detalii"]}</p>\n{cit}'
                      f'            <div class="ev-sources" style="margin-top:14px">{srcs}</div>\n'
                      f'          </section>\n')

        # Convingerile se ARATĂ, nu se notează. „România e o poartă între
        # dimensiuni" nu se poate infirma — e credință, nu afirmație verificabilă.
        # Dacă am pune ștampila „Contrazis" pe ea, ne-am pierde dreptul de a o
        # pune acolo unde chiar contează: pe cifre.
        for c in o.get("credinte", []):
            afirm += (f'          <section class="ev-block opinie">\n'
                      f'            <h2>💬 Convingeri, nu afirmații verificabile</h2>\n'
                      f'            <div class="opinie-item">{c["text"]}</div>\n'
                      f'          </section>\n')

        carduri = ("".join(pcard_json(d) for d in lst).rstrip("\n")
                   if lst else
                   '          <p style="color:var(--ink-faint);font-size:14px">'
                   'Încă nu avem o verificare publicată despre această persoană. '
                   'Când apare una, se adaugă automat aici.</p>')
        return (
            f'        <section class="cat-section" id="{anchor(o["nume"])}">\n'
            f'          <div class="section-head"><h2>{o["nume"]} '
            f'<span style="font-size:12.5px;font-weight:700;color:#fff;background:{col};'
            f'padding:2px 9px;border-radius:20px;vertical-align:middle">{o["rol"]}</span> '
            f'<span style="font-size:13px;font-weight:700;color:var(--ink-faint)">· '
            f'{len(lst)} verificări</span></h2></div>\n'
            f'          <p style="max-width:70ch;color:var(--ink-soft);font-size:15px;'
            f'margin:0 0 16px">{o["sumar"]}</p>\n'
            f'          <section class="ev-block probat" style="border-left-color:{col}">\n'
            f'            <h2>📋 Fișa</h2>\n'
            f'            <p class="ev-sub">Numai fapte cu sursă. Fără viață privată.</p>\n{rows}'
            f'          </section>\n{afirm}'
            f'          <div class="cards-3">\n{carduri}\n          </div>\n'
            f'        </section>\n')

    def chip(o):
        col = o.get("culoare", "#8a6b1f"); c = len(byp.get(o["nume"], []))
        return (f'      <a href="#{anchor(o["nume"])}" style="display:flex;gap:11px;align-items:center;'
                f'text-decoration:none;color:inherit;border:1px solid var(--line-2);background:var(--card);'
                f'border-radius:13px;padding:11px 13px">'
                f'<span style="flex:0 0 40px;height:40px;border-radius:50%;background:{col};color:#fff;'
                f'display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px">'
                f'{initials(o["nume"])}</span>'
                f'<span style="min-width:0"><span style="display:block;font-weight:700;font-size:14.5px;'
                f'line-height:1.2">{o["nume"]}</span>'
                f'<span style="display:block;font-size:11.5px;color:var(--ink-faint);margin-top:2px">'
                f'<b style="color:{col}">{o["rol"]}</b> · {c} verificări</span></span></a>')

    grid = "\n".join(chip(o) for o in F["oameni"])
    secs = "".join(fisa(o) for o in F["oameni"])
    main = (
        f'    <div class="wrap" style="max-width:1120px;margin:0 auto;padding:0 20px">\n'
        f'      <div style="padding:30px 0 6px">\n'
        f'        <h1 style="font-family:Georgia,serif;font-size:34px;margin:0 0 4px">{F["titlu"]}</h1>\n'
        f'        <p style="font-family:Georgia,serif;font-style:italic;color:var(--accent);'
        f'font-size:17px;margin:0 0 14px">{F["subtitlu"]}</p>\n'
        f'        <p style="max-width:70ch;color:var(--ink-soft);font-size:16px;line-height:1.55">'
        f'{F["intro"]}</p>\n'
        f'      </div>\n'
        f'      <section class="ai-note" style="margin:18px 0 8px">\n'
        f'        <h2>⚖️ Cum lucrăm aici</h2>\n'
        f'        <p>{F["metoda"]}</p>\n'
        f'      </section>\n'
        f'      <p style="max-width:70ch;color:var(--ink-faint);font-size:13.5px;'
        f'margin:0 0 20px">{F["denumire"]}</p>\n'
        f'      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));'
        f'gap:10px;margin:14px 0 34px">\n{grid}\n      </div>\n{secs}    </div>')

    h = re.sub(r'<main>.*?</main>', lambda m: "<main>\n" + main + "\n  </main>", shell, count=1, flags=re.S)
    h = h.replace("<title>Fără Baliverne — Apă, paie… Adevăr</title>",
                  f'<title>{F["titlu"]} — Fără Baliverne</title>')
    for a, b in (('<link rel="canonical" href="https://farabaliverne.ro/">',
                  '<link rel="canonical" href="https://farabaliverne.ro/closcu.html">'),
                 ('<meta property="og:url" content="https://farabaliverne.ro/">',
                  '<meta property="og:url" content="https://farabaliverne.ro/closcu.html">'),
                 ('<meta property="og:title" content="Fără Baliverne — Apă, paie… Adevăr">',
                  f'<meta property="og:title" content="{F["titlu"]} — Fără Baliverne">'),
                 ('<meta name="twitter:title" content="Fără Baliverne — Apă, paie… Adevăr">',
                  f'<meta name="twitter:title" content="{F["titlu"]} — Fără Baliverne">'),
                 ('<a href="index.html" class="active">Acasă</a>', '<a href="index.html">Acasă</a>')):
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
    # `closcu.html` apare doar dacă a fost generată (CLOSCU_ENABLED). Verificarea
    # `os.path.exists` de mai jos o sare singură când secțiunea e stinsă, deci
    # sitemap-ul nu trimite niciodată Google spre un 404.
    for pg in ("politicieni.html","cauta.html","closcu.html","publicitate.html","metodologie.html",
               "cine-suntem.html","corectari.html","contact.html","termeni.html","confidentialitate.html"):
        if os.path.exists(os.path.join(ROOT, pg)):
            pr = "0.6" if pg in ("politicieni.html","cauta.html","closcu.html") else "0.4"
            rows.append('<url><loc>%s%s</loc><lastmod>%s</lastmod><changefreq>monthly</changefreq><priority>%s</priority></url>' % (B, pg, today, pr))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  '
           + "\n  ".join(rows) + "\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(xml)
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
    html = replace_feed(html, build_feed(arts, mom) + build_featured_script(arts, mom))
    open(IDX, "w", encoding="utf-8").write(html)
    # 2. politicieni (clonează shell-ul din index)
    shell = open(IDX, encoding="utf-8").read()
    pol, nwith, nwithout = build_politicieni(arts, shell)
    open(os.path.join(ROOT, "politicieni.html"), "w", encoding="utf-8").write(pol)
    open(os.path.join(ROOT, "cauta.html"), "w", encoding="utf-8").write(build_search_page(arts, shell))
    # 2c. Cloșcu cu Puii de AUR (fișe + verificări pe persoană)
    closcu = build_closcu(arts, shell)
    if closcu:
        open(os.path.join(ROOT, "closcu.html"), "w", encoding="utf-8").write(closcu)
    # 2b. sitemap.xml (toate articolele + hub) pentru Google
    nsitemap = build_sitemap(arts)
    # 3. count pe toate paginile
    # Toate paginile, nu doar cele generate: și cele statice (termeni, contact,
    # metodologie, 404…) au butoanele de partajare, deci și ele au nevoie de
    # reparația pentru mobil. Înainte rămâneau pe varianta veche, care pe telefon
    # deschidea Facebook fără să trimită nimic.
    pages = [IDX] + glob.glob(os.path.join(ROOT,"a","*.html")) + \
            [os.path.join(ROOT,x) for x in ("politicieni.html","publicitate.html","cauta.html",
                                            "closcu.html","metodologie.html","cine-suntem.html",
                                            "corectari.html","contact.html","termeni.html",
                                            "confidentialitate.html","404.html")]
    tb = now_edition()
    date_re = re.compile(r'(<div class="date">).*?(</div>)', re.S)
    hub = {IDX, os.path.join(ROOT,"politicieni.html"), os.path.join(ROOT,"publicitate.html"),
           os.path.join(ROOT,"cauta.html"), os.path.join(ROOT,"closcu.html")}
    for f in pages:
        if not os.path.exists(f): continue
        s = open(f, encoding="utf-8").read(); orig = s
        s = re.sub(r'\d+ verificări publicate', f'{total} verificări publicate', s)
        s = repara_share(s)
        s = pune_data(s)
        s = pune_citite(s)
        # Linkul spre Cloșcu, pe TOATE paginile. Se injectează aici, nu în
        # șablon: articolele noi le scrie botul după `a/legea-integritatii...`,
        # care n-are linkul — altfel ar lipsi de pe tot ce se publică de acum.
        # Garda caută LINKUL, nu numele fișierului: pe closcu.html numele apare
        # deja în canonical + og:url, deci un test pe „closcu.html" ar sări
        # exact pagina care are cea mai mare nevoie de link în navigație.
        if closcu and 'closcu.html">Cloșcu' not in s:
            for pref in ("", "../"):
                s = s.replace(
                    f'<a href="{pref}politicieni.html">Politicieni</a>',
                    f'<a href="{pref}politicieni.html">Politicieni</a>\n'
                    f'      <a href="{pref}closcu.html">Cloșcu cu Puii de AUR</a>')
        elif not closcu:
            # Comutatorul e stins: scoatem linkul, altfel rămâne din build-urile
            # anterioare și trimite cititorii într-un 404.
            s = re.sub(r'\n?\s*<a href="(?:\.\./)?closcu\.html">Cloșcu cu Puii de AUR</a>', "", s)
        if f in hub:  # data + „ediția de X" pe paginile-hub (după momentul publicării)
            s = date_re.sub(lambda m: m.group(1) + tb + m.group(2), s)
        # Articol: poza proprie la share (og:image) + date structurate (SEO)
        if os.sep + "a" + os.sep in f:
            mh = re.search(r'<img src="([^"]+)"[^>]*object-fit:cover;z-index:1', s)
            img = mh.group(1) if mh else "https://farabaliverne.ro/og-cover.png"
            if img.startswith("../"):  # cale locală relativă -> URL absolut (og:image nu poate fi relativ)
                img = "https://farabaliverne.ro/" + img[len("../"):]
            if mh:
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
                lds = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + '</script>'
                if 'application/ld+json' in s:
                    s = re.sub(r'<script type="application/ld\+json">.*?</script>', lambda m: lds, s, count=1, flags=re.S)
                elif '</head>' in s:
                    s = s.replace('</head>', '  ' + lds + '\n</head>', 1)
        if s != orig: open(f, "w", encoding="utf-8").write(s)
    build_stare(arts)
    print(f"✅ build: {total} articole | feed regenerat | politicieni {nwith} cu verificări + {nwithout} în curând | sitemap {nsitemap} URL-uri")

if __name__ == "__main__":
    main()

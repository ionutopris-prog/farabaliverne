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
import json, re, glob, os, unicodedata

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
        if d.get("slug"): arts[d["slug"]] = d
    return arts

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

def trunc(s, n):
    return s if len(s) <= n else s[:n].rsplit(" ",1)[0].rstrip(" ,.;") + "…"

def card(d):
    glyph, heroimg, fav, srcname = extract(d)
    vc, vl = vcl(d.get("mainVerdict"))
    np_, nc_, no_ = len(d.get("probat") or []), len(d.get("contestat") or []), len(d.get("opinie") or [])
    img = (f'<img data-cardphoto="1" src="{heroimg}" alt="" loading="lazy" referrerpolicy="no-referrer" '
           f'onerror="this.remove()" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1">'
           if heroimg else "")
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

def build_feed(arts):
    """Secțiunile pe categorii, ordonate; exclude articolul din hero."""
    out = []
    for cat in CAT_ORDER:
        items = [d for s,d in arts.items() if d["category"] == cat and s != FEATURED]
        if not items: continue
        items.sort(key=lambda d: d.get("date",""), reverse=True)
        cards = "".join(card(d) for d in items)
        out.append(f'''        <section class="cat-section" id="{CAT_ID[cat]}">
          <div class="section-head">
            <h2>{cat}</h2>
          </div>
          <div class="cards-3">
{cards.rstrip(chr(10))}
          </div>
        </section>
''')
    return "\n".join(out)

def build_featured_script(arts):
    """Hero rotativ: la fiecare refresh, JS alege aleatoriu alt articol pt „principalul"."""
    items = sorted(arts.values(), key=lambda d: d.get("date",""), reverse=True)[:20]
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
            var pool=L.filter(function(a){return a.slug!==last;}); if(!pool.length) pool=L;
            var p=pool[Math.floor(Math.random()*pool.length)];
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

def main():
    arts = load()
    total = len(arts)
    # 1. feed
    html = open(IDX, encoding="utf-8").read()
    html = replace_feed(html, build_feed(arts) + build_featured_script(arts))
    open(IDX, "w", encoding="utf-8").write(html)
    # 2. politicieni (clonează shell-ul din index)
    shell = open(IDX, encoding="utf-8").read()
    pol, nwith, nwithout = build_politicieni(arts, shell)
    open(os.path.join(ROOT, "politicieni.html"), "w", encoding="utf-8").write(pol)
    # 3. count pe toate paginile
    pages = [IDX] + glob.glob(os.path.join(ROOT,"a","*.html")) + \
            [os.path.join(ROOT,x) for x in ("politicieni.html","publicitate.html")]
    for f in pages:
        if not os.path.exists(f): continue
        s = open(f, encoding="utf-8").read()
        s2 = re.sub(r'\d+ verificări publicate', f'{total} verificări publicate', s)
        if s2 != s: open(f,"w",encoding="utf-8").write(s2)
    print(f"✅ build: {total} articole | feed regenerat | politicieni {nwith} cu verificări + {nwithout} în curând")

if __name__ == "__main__":
    main()

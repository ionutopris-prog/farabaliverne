"""
seo.py — ce pune generatorul în <head>, în datele structurate și în paginile de
categorie, după auditul SEO din 12 septembrie 2026 (site live, Lighthouse,
Search Console: 514 indexate / 247 nu; CTR 1,9 % la poziția 10,5).

Ce repară, în ordinea impactului:
  1. Titluri de căutare scurte (≤ 58 de caractere + marcă) — titlurile
     articolelor au mediana 126 de caractere, Google le tăia sau le rescria.
     H1-ul de pe pagină rămâne cel lung; se scurtează DOAR <title> și og:title.
  2. Meta description ≤ 155 de caractere, tăiată la capăt de propoziție, fără
     emoji în față (înainte: dek[:300], tăiat la jumătate de cuvânt).
  3. NewsArticle corect: headline ≤ 110, datePublished/dateModified cu ora și
     fusul (din git), autor persoană (răspunderea editorială e a lui Ionuț
     Opriș, scris pe cine-suntem.html), articleSection, inLanguage, poza de
     partajare 1200×630 prima; BreadcrumbList; Organization + WebSite pe prima
     pagină.
  4. ClaimReview doar unde chiar se verifică o afirmație (Politică, Economie,
     Extern, Social, Media de stat), cu ratingValue numeric; nu pe Știință,
     Minți luminate, Sport — acolo nu e un fact-check și Google îl respinge.
  5. Semnătură vizibilă + <time datetime> pe articol.
  6. Pagini de categorie (politica.html, economie.html…) cu toate articolele,
     paginate: 606 din 898 articole nu erau legate din nicio pagină în afară de
     prima (898 de linkuri într-un singur HTML de 2 MB). Ăsta e drumul pe care
     Google nu-l avea spre cele 223 „descoperite, neindexate".
  7. lastmod real în sitemap (din git), nu „azi" la fiecare build.
"""
import html
import os
import re
import subprocess
from datetime import datetime

BAZA = "https://farabaliverne.ro"
AUTOR = {"@type": "Person", "name": "Ionuț Opriș", "url": f"{BAZA}/cine-suntem.html"}
PUBLISHER = {"@type": "Organization", "name": "Fără Baliverne", "url": BAZA,
             "logo": {"@type": "ImageObject", "url": f"{BAZA}/apple-touch-icon.png", "width": 180, "height": 180}}
SAME_AS = ["https://www.facebook.com/profile.php?id=61593641722625", "https://x.com/farabaliverne"]
CU_CLAIMREVIEW = {"Politică", "Economie", "Extern", "Social", "Media de stat"}
LUNI = ("ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
        "septembrie", "octombrie", "noiembrie", "decembrie")
_EMOJI_FATA = re.compile(r"^[\W_]+", re.U)


def e(s):
    return html.escape(s or "", quote=True)


# ─── 1–2. titlu și descriere de căutare ─────────────────────────────────────
def seo_titlu(titlu, maxim=64):
    """Titlul de căutare: prima propoziție / primul segment, ≤ `maxim` caractere.
    O propoziție întreagă de până la `maxim`+16 e mai bună decât un ciot de
    `maxim` (Google tot o taie la ~60, dar taie la capăt de cuvânt, cu sens).
    Dacă nici prima propoziție nu e scurtă, tăiem la ultimul spațiu și punem „…"."""
    t = re.sub(r"\s+", " ", (titlu or "")).strip()
    if len(t) <= maxim:
        return t
    # capăt natural: „. ", „: ", „? ", „! ", „ — ", „; "
    cel_mai_bun = None
    for m in re.finditer(r"[.!?;]\s|\s[—–-]\s|:\s", t):
        if 28 <= m.start() <= maxim + 16:
            cel_mai_bun = m.start()
            break
    if cel_mai_bun:
        return t[:cel_mai_bun].rstrip(" ,;:—–-")
    taiat = t[:maxim - 1]
    if " " in taiat:
        taiat = taiat[:taiat.rfind(" ")]
    return taiat.rstrip(" ,;:—–-") + "…"


def seo_descriere(dek, maxim=155):
    """Meta description: propoziții întregi din dek, ≤ `maxim`, fără emoji în față."""
    t = re.sub(r"\s+", " ", (dek or "")).strip()
    t = _EMOJI_FATA.sub("", t)
    if len(t) <= maxim:
        return t
    out = ""
    for m in re.finditer(r".+?[.!?](?=\s|$)", t):
        cand = (out + " " + m.group(0)).strip()
        if len(cand) > maxim:
            break
        out = cand
    if len(out) >= 60:
        return out
    taiat = t[:maxim - 1]
    if " " in taiat:
        taiat = taiat[:taiat.rfind(" ")]
    return taiat.rstrip(" ,;:") + "…"


def data_ro(iso, cu_ora=True):
    """'2026-09-12T12:08:17+02:00' → '12 septembrie 2026, 12:08' (sau fără oră)."""
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    s = f"{dt.day} {LUNI[dt.month - 1]} {dt.year}"
    if cu_ora and ("T" in iso):
        s += f", {dt:%H:%M}"
    return s


def moment_iso(d, mom):
    """Momentul publicării: din git dacă există (cu ora și fusul), altfel ziua."""
    m = (mom or {}).get(d.get("slug") or "", "")
    if m:
        return m
    return (d.get("date") or "")[:10]


# ─── 3–5. <head> + date structurate + semnătură pe articol ──────────────────
def _meta(s, k, val, prop=True):
    """Pune sau înlocuiește un <meta>; `prop` = property (og/article) sau name."""
    attr = "property" if prop else "name"
    tag = f'<meta {attr}="{k}" content="{e(val)}">'
    rx = re.compile(rf'<meta {attr}="{re.escape(k)}" content="[^"]*">')
    if rx.search(s):
        return rx.sub(lambda m: tag, s, count=1)
    return s.replace("</head>", "  " + tag + "\n</head>", 1)


def cap_articol(s, d, slug, mom, cat_id):
    """Rescrie <title>, descrierile, og/article meta pe pagina unui articol."""
    titlu = seo_titlu(d.get("title", ""))
    desc = seo_descriere(d.get("dek", ""))
    pub = moment_iso(d, mom)
    s = re.sub(r"<title>.*?</title>", lambda _: f"<title>{e(titlu)} — Fără Baliverne</title>", s, count=1, flags=re.S)
    s = _meta(s, "og:title", titlu)
    s = _meta(s, "twitter:title", titlu, prop=False)
    s = _meta(s, "description", desc, prop=False)
    s = _meta(s, "og:description", desc)
    s = _meta(s, "twitter:description", desc, prop=False)
    s = _meta(s, "og:type", "article")
    s = _meta(s, "og:locale", "ro_RO")
    s = _meta(s, "article:published_time", pub)
    s = _meta(s, "article:modified_time", pub)
    s = _meta(s, "article:section", d.get("category", ""))
    s = _meta(s, "article:author", AUTOR["url"])
    s = _meta(s, "og:image:alt", titlu)
    s = _meta(s, "twitter:site", "@farabaliverne", prop=False)
    s = _meta(s, "twitter:card", "summary_large_image", prop=False)
    # eticheta de categorie din articol devine link spre pagina categoriei
    s = re.sub(r'<span class="cat-tag">([^<]*)</span>',
               lambda m: f'<a class="cat-tag" href="../{cat_id}.html" style="text-decoration:none;color:inherit">{m.group(1)}</a>',
               s, count=1)
    # semnătura + <time>: înlocuiește data seacă „2026-09-12" din rândul .meta
    zi = (d.get("date") or "")[:10]
    if zi:
        semn = (f'<span class="byline">Verificat de <a href="../cine-suntem.html" style="color:inherit">Ionuț Opriș</a> · '
                f'<time datetime="{e(pub)}">{data_ro(pub)}</time></span>')
        s = re.sub(rf'<span>{re.escape(zi)}</span>', lambda m: semn, s, count=1)
    return s


def rating(eticheta):
    """Eticheta scurtă a verdictului → notă numerică (1 = contrazis … 5 = probat)."""
    t = (eticheta or "").lower()
    if t.startswith("probat parțial") or t.startswith("mixt") or t.startswith("parțial"):
        return 3
    if t.startswith("probat") or t.startswith("confirmat"):
        return 5
    if t.startswith("contrazis") or t.startswith("fals") or t.startswith("infirmat"):
        return 1
    if t.startswith("contestat"):
        return 2
    if t.startswith("neverificabil") or t.startswith("neconfirmat") or t.startswith("neprobat"):
        return 3
    return None


def date_structurate(d, slug, img, card_url, mom, eticheta, cat_id):
    """Lista blocurilor JSON-LD pentru un articol: NewsArticle, BreadcrumbList,
    (ClaimReview doar la categoriile unde se verifică o afirmație)."""
    url = f"{BAZA}/a/{slug}.html"
    pub = moment_iso(d, mom)
    imagini = [x for x in (card_url, img) if x]
    ld = {"@context": "https://schema.org", "@type": "NewsArticle",
          "headline": seo_titlu(d.get("title", ""), 110),
          "alternativeHeadline": d.get("title", ""),
          "description": seo_descriere(d.get("dek", ""), 300),
          "image": imagini,
          "datePublished": pub, "dateModified": pub,
          "author": AUTOR, "publisher": PUBLISHER,
          "mainEntityOfPage": {"@type": "WebPage", "@id": url},
          "articleSection": d.get("category", ""),
          "inLanguage": "ro",
          "isAccessibleForFree": True}
    if d.get("url"):
        ld["citation"] = d["url"]
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Acasă", "item": BAZA + "/"},
        {"@type": "ListItem", "position": 2, "name": d.get("category", ""), "item": f"{BAZA}/{cat_id}.html"},
        {"@type": "ListItem", "position": 3, "name": seo_titlu(d.get("title", ""), 110), "item": url}]}
    blocuri = [ld, crumbs]
    if eticheta and d.get("category") in CU_CLAIMREVIEW:
        cr = {"@context": "https://schema.org", "@type": "ClaimReview",
              "url": url, "claimReviewed": d.get("title", ""), "datePublished": pub,
              "author": PUBLISHER,
              "reviewRating": {"@type": "Rating", "alternateName": eticheta}}
        nota = rating(eticheta)
        if nota is not None:
            cr["reviewRating"].update({"ratingValue": nota, "bestRating": 5, "worstRating": 1})
        if d.get("url"):
            cr["itemReviewed"] = {"@type": "Claim", "appearance": {"@type": "CreativeWork", "url": d["url"]}}
        blocuri.append(cr)
    return blocuri


def organizatie_ld():
    return [{"@context": "https://schema.org", "@type": "NewsMediaOrganization", "name": "Fără Baliverne",
             "url": BAZA + "/", "logo": PUBLISHER["logo"], "sameAs": SAME_AS,
             "foundingDate": "2026-08-08", "foundingLocation": "Danemarca",
             "correctionsPolicy": f"{BAZA}/corectari.html", "ethicsPolicy": f"{BAZA}/metodologie.html",
             "founder": AUTOR, "email": "contact@farabaliverne.ro"},
            {"@context": "https://schema.org", "@type": "WebSite", "name": "Fără Baliverne", "url": BAZA + "/",
             "inLanguage": "ro", "publisher": {"@type": "Organization", "name": "Fără Baliverne"},
             "potentialAction": {"@type": "SearchAction",
                                 "target": {"@type": "EntryPoint", "urlTemplate": f"{BAZA}/cauta.html?q={{search_term_string}}"},
                                 "query-input": "required name=search_term_string"}}]


# ─── 6. paginile de categorie ───────────────────────────────────────────────
PE_PAGINA = 60
DESCRIERI = {
    "Politică": "Toate verificările Fără Baliverne din politica românească: ce se probează, ce nu, cu surse la fiecare afirmație.",
    "Economie": "Toate verificările Fără Baliverne din economie: cifre oficiale, bugete, prețuri, salarii — cu sursele lângă fiecare afirmație.",
    "Extern": "Toate verificările Fără Baliverne despre lumea de dincolo de graniță, cu surse din mai multe părți.",
    "Știință": "Toate articolele Fără Baliverne despre știință: studii, descoperiri, limitele recunoscute de autori.",
    "Minți luminate": "Cercetare universitară din orice domeniu, explicată pe înțelesul tuturor, cu link la studiul original.",
    "Media de stat": "Ce spun mediile de stat ale altor țări și ce se probează din ce spun, etichetat corect.",
    "Social": "Toate verificările Fără Baliverne din viața socială: sănătate, educație, comunități, cu surse.",
    "Sport": "Toate articolele Fără Baliverne din sport: rezultate, cifre și afirmații verificate.",
}


def _nume_fisier(cat_id, nr):
    return f"{cat_id}.html" if nr == 1 else f"{cat_id}-{nr}.html"


def build_categorii(arts, shell, mom, cat_order, cat_id, card, cheie_timp, root):
    """Scrie <categorie>.html (+ -2, -3 …) cu TOATE articolele categoriei, cele
    mai noi întâi, `PE_PAGINA` pe pagină. Întoarce lista fișierelor scrise."""
    scrise = []
    for cat in cat_order:
        items = [d for d in arts.values() if d.get("category") == cat
                 and os.path.exists(os.path.join(root, "a", d["slug"] + ".html"))]
        if not items:
            continue
        items.sort(key=lambda d: cheie_timp(d, mom), reverse=True)
        cid = cat_id[cat]
        pagini = [items[i:i + PE_PAGINA] for i in range(0, len(items), PE_PAGINA)]
        for nr, lot in enumerate(pagini, 1):
            fis = _nume_fisier(cid, nr)
            titlu = f"{cat} — toate verificările" + (f" (pagina {nr})" if nr > 1 else "")
            desc = DESCRIERI.get(cat, f"Toate articolele Fără Baliverne din {cat}.")
            if nr > 1:
                desc = f"Pagina {nr} din {len(pagini)}. " + desc
            cards = "".join(card(d) for d in lot)
            pager = ""
            if len(pagini) > 1:
                leg = []
                for k in range(1, len(pagini) + 1):
                    if k == nr:
                        leg.append(f'<strong style="padding:6px 10px">{k}</strong>')
                    else:
                        leg.append(f'<a href="{_nume_fisier(cid, k)}" style="padding:6px 10px;text-decoration:none;'
                                   f'border:1px solid var(--line);border-radius:8px;color:inherit">{k}</a>')
                pager = ('        <nav class="pager" aria-label="Pagini" style="display:flex;gap:8px;flex-wrap:wrap;'
                         'justify-content:center;margin:26px 0 40px;font-size:15px">' + "\n".join(leg) + "</nav>\n")
            main = (f'''    <div class="wrap">
      <nav aria-label="Ești aici" style="font-size:13px;color:var(--ink-faint);padding:18px 0 0">
        <a href="index.html" style="color:inherit">Acasă</a> › <span>{e(cat)}</span></nav>
      <div style="padding:10px 0 6px">
        <h1 style="font-family:Georgia,serif;font-size:34px;margin:0 0 8px">{e(cat)}</h1>
        <p style="color:var(--ink-soft);font-size:16px;line-height:1.6;max-width:64ch">{e(desc)}</p>
        <p style="color:var(--ink-faint);font-size:13px">{len(items)} articole, cele mai noi întâi.</p>
      </div>
      <section class="cat-section" id="{cid}">
        <div class="cards-3">
{cards.rstrip(chr(10))}
        </div>
      </section>
{pager}    </div>''')
            h = re.sub(r"<main>.*?</main>", lambda m: "<main>\n" + main + "\n  </main>", shell, count=1, flags=re.S)
            url = f"{BAZA}/{fis}"
            h = re.sub(r"<title>.*?</title>", lambda _: f"<title>{e(titlu)} — Fără Baliverne</title>", h, count=1, flags=re.S)
            h = re.sub(r'(<link rel="canonical" href=")[^"]*(">)', lambda m: m.group(1) + url + m.group(2), h, count=1)
            h = _meta(h, "og:url", url)
            h = _meta(h, "og:title", titlu)
            h = _meta(h, "twitter:title", titlu, prop=False)
            h = _meta(h, "description", desc, prop=False)
            h = _meta(h, "og:description", desc)
            h = _meta(h, "twitter:description", desc, prop=False)
            h = _meta(h, "og:type", "website")
            if nr > 1:
                h = h.replace("</head>", f'  <link rel="prev" href="{BAZA}/{_nume_fisier(cid, nr - 1)}">\n</head>', 1)
            if nr < len(pagini):
                h = h.replace("</head>", f'  <link rel="next" href="{BAZA}/{_nume_fisier(cid, nr + 1)}">\n</head>', 1)
            # prima pagină are scripturi/ancore proprii (hero, featured) — pe pagina de
            # categorie nu au sens; ce nu găsește, nu rulează, dar tăiem JSON-LD-ul ei
            h = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", h, flags=re.S)
            crumbs = {"@context": "https://schema.org", "@type": "CollectionPage", "name": titlu,
                      "url": url, "inLanguage": "ro", "isPartOf": {"@type": "WebSite", "url": BAZA + "/"},
                      "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
                          {"@type": "ListItem", "position": 1, "name": "Acasă", "item": BAZA + "/"},
                          {"@type": "ListItem", "position": 2, "name": cat, "item": f"{BAZA}/{cid}.html"}]}}
            import json
            h = h.replace("</head>", '  <script type="application/ld+json">' + json.dumps(crumbs, ensure_ascii=False) + "</script>\n</head>", 1)
            open(os.path.join(root, fis), "w", encoding="utf-8").write(h)
            scrise.append((fis, (lot[0].get("date") or "")[:10]))
    return scrise


def link_toate(s, cat_order, cat_id):
    """Pe prima pagină: sub titlul fiecărei secțiuni, „Toate din X →" spre pagina categoriei."""
    for cat in cat_order:
        cid = cat_id[cat]
        vechi = f'<h2>{cat}</h2>\n          </div>'
        nou = (f'<h2>{cat}</h2>\n            <a class="tot" href="{cid}.html" '
               f'style="font-size:13px;margin-left:auto;align-self:center">Toate din {cat} →</a>\n          </div>')
        if vechi in s and f'href="{cid}.html"' not in s:
            s = s.replace(vechi, nou, 1)
    return s


# ─── 7. lastmod din git ─────────────────────────────────────────────────────
_GIT_CACHE = {}


def git_lastmod(root, rel, fallback):
    """Data ultimei modificări a fișierului în git (YYYY-MM-DD); `fallback` dacă nu e în git."""
    if rel in _GIT_CACHE:
        return _GIT_CACHE[rel]
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], capture_output=True,
                           text=True, cwd=root, timeout=20)
        v = r.stdout.strip() or fallback
    except Exception:
        v = fallback
    _GIT_CACHE[rel] = v
    return v

#!/usr/bin/env python3
"""
Construiește secțiunea **Fără Scorneli — Moldova**: `moldova/index.html`.

Aceeași casă, alt nume la poartă. Trăiește la o singură adresă:
  • https://farabaliverne.ro/moldova/            (folderul, urcat de deploy-ul obișnuit)

🔴 Subdomeniul `moldova.farabaliverne.ro` NU există și nu se cumpără. A fost plănuit
cândva, dar pagina a rămas cu canonical, og:url, sigla și „Acasă" arătând spre el —
patru trimiteri spre NXDOMAIN. Google citea canonical-ul și înțelegea că adevărata
pagină e la o adresă moartă, deci putea scoate toată secțiunea din căutări; cine
dădea pe siglă ajungea în gol. Reparat pe 4 septembrie 2026. Dacă adresa asta se
mai scrie vreodată undeva, e greșeală.

🔴 De ce `<base href="https://farabaliverne.ro/">` în cap: pagina stă în folderul
`/moldova/`, dar linkurile spre articole sunt relative (`a/x.html`), moștenite din
index-ul mare. Fără `base` s-ar căuta `farabaliverne.ro/moldova/a/x.html`, care nu
există. Cu `base`, toate legăturile relative — articole, poze — se duc la rădăcină.

Rulare:  python3 scripts/build_moldova.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site as B
from moldova import este_moldova

# Adresa paginii. Scrisă o dată, ca să nu se mai împrăștie prin fișier.
#
# 🔴 Toate ancorele din meniu se construiesc PORNIND de la ea, absolute, și nu
# ca simple `#sectiune`. Motivul e `<base href="https://farabaliverne.ro/">` din
# cap: după standard, până și un link care are doar diez se socotește față de
# `base`. Deci `#politica` ajungea la `farabaliverne.ro/#politica` — adică pe
# prima pagină a României. Meniul Moldovei te scotea din Moldova. Reparat pe
# 4 septembrie 2026. Dacă cineva scurtează linkurile înapoi la `#ceva`, se strică
# la loc, tăcut, fiindcă pagina se încarcă perfect — doar că altundeva.
ACASA = "https://farabaliverne.ro/moldova/"


def ANCORA(cat):
    """Ancora unei categorii — aceeași ca pe site-ul mare.

    Înainte se făcea cu `cat.lower()`, ceea ce dădea `id="media de stat"`
    (cu spații!) în timp ce meniul trimitea la `#media-de-stat`. Butonul nu
    ducea nicăieri. `B.CAT_ID` e harta pe care o folosește deja index-ul mare,
    deci acum cele două pagini vorbesc aceeași limbă.
    """
    return B.CAT_ID.get(cat, cat.lower().replace(" ", "-"))

ROOT = B.ROOT
IESIRE = os.path.join(ROOT, "moldova", "index.html")

NUME = "Fără Scorneli"
SUBLINE = "Moldova · de la Fără Baliverne"
DESCRIERE = ("Verificăm ce se spune în Republica Moldova: declarații, cifre, "
             "propagandă. Arătăm ce se probează și ce nu, cu surse. Concluzia o tragi tu.")


def articole():
    toate = B.load()
    return {s: d for s, d in toate.items() if este_moldova(d)}


# Câte articole se arată în fiecare dintre secțiunile de jos.
CATE_JOS = 12

# Ce se întâmplă în lume nu aparține niciunui mal — se pune în AMBELE case.
# Ce e despre România se pune ca vecinătate, nu ca știre proprie.
CATEGORII_LUMII = {"Extern", "Știință", "Media de stat"}


def _restul():
    """Articolele care NU sunt despre Moldova, de la cel mai nou."""
    toate = B.load()
    rest = [d for s, d in toate.items() if not este_moldova(d)]
    mom = B.momente()
    rest.sort(key=lambda d: B.cheie_timp(d, mom), reverse=True)
    return rest


def din_lume(n=CATE_JOS):
    """Internaționalul — apare și aici, și pe prima pagină românească."""
    return [d for d in _restul() if d.get("category") in CATEGORII_LUMII][:n]


def din_romania(n=CATE_JOS):
    """Ce ține de România: politică, economie, social, sport de dincolo de Prut."""
    return [d for d in _restul() if d.get("category") not in CATEGORII_LUMII][:n]


def feed(arts):
    if not arts:
        return ('<section class="wrap" style="padding:40px 0">'
                '<p class="dek">Încă nu avem verificări despre Moldova. '
                'Prima ediție dedicată vine în curând.</p></section>')
    mom = B.momente()
    bucati = []
    for cat in B.CAT_ORDER:
        items = [d for d in arts.values() if d["category"] == cat]
        if not items:
            continue
        items.sort(key=lambda d: B.cheie_timp(d, mom), reverse=True)
        ancora = ANCORA(cat)
        bucati.append(
            f'<section class="sec" id="{ancora}">\n'
            f'  <div class="wrap">\n'
            f'    <h2 class="sec-title">{cat}</h2>\n'
            f'    <div class="grid">\n{"".join(B.card(d) for d in items)}    </div>\n'
            f'  </div>\n</section>\n')
    return "".join(bucati)


def main():
    arts = articole()
    coaja = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()

    # --- capul paginii -----------------------------------------------------
    coaja = re.sub(r"<title>.*?</title>",
                   f"<title>{NUME} — Moldova · Apă, paie… Adevăr</title>", coaja, count=1, flags=re.S)
    coaja = re.sub(r'<meta name="description" content=".*?">',
                   f'<meta name="description" content="{DESCRIERE}">', coaja, count=1, flags=re.S)
    coaja = re.sub(r'<link rel="canonical"[^>]*>',
                   '<link rel="canonical" href="https://farabaliverne.ro/moldova/">', coaja, count=1)
    for prop, val in [("og:title", f"{NUME} — Moldova"), ("og:description", DESCRIERE),
                      ("og:url", "https://farabaliverne.ro/moldova/"),
                      ("og:site_name", f"{NUME} Moldova")]:
        coaja = re.sub(rf'<meta property="{prop}" content=".*?">',
                       f'<meta property="{prop}" content="{val}">', coaja, count=1, flags=re.S)
    for name, val in [("twitter:title", f"{NUME} — Moldova"), ("twitter:description", DESCRIERE)]:
        coaja = re.sub(rf'<meta name="{name}" content=".*?">',
                       f'<meta name="{name}" content="{val}">', coaja, count=1, flags=re.S)
    if "<base " not in coaja:
        coaja = coaja.replace("<head>", '<head>\n<base href="https://farabaliverne.ro/">', 1)

    # --- fruntea paginii ---------------------------------------------------
    coaja = re.sub(r'<h1 class="brand">.*?</h1>',
                   f'<h1 class="brand"><a href="https://farabaliverne.ro/moldova/">'
                   f'Fără&nbsp;Scorneli</a></h1>', coaja, count=1, flags=re.S)
    coaja = re.sub(r'<div class="subline">.*?</div>',
                   f'<div class="subline">{SUBLINE}</div>', coaja, count=1, flags=re.S)
    coaja = re.sub(r'<div class="live">.*?</div>',
                   f'<div class="live"><span class="dot"></span> '
                   f'{len(arts)} verificări despre Moldova</div>', coaja, count=1, flags=re.S)

    # --- meniul ------------------------------------------------------------
    linkuri = ['<a href="https://farabaliverne.ro/moldova/" class="active">Acasă</a>']
    for cat in B.CAT_ORDER:
        if any(d["category"] == cat for d in arts.values()):
            linkuri.append(f'<a href="{ACASA}#{ANCORA(cat)}">{cat}</a>')
    if din_lume(1):
        linkuri.append(f'<a href="{ACASA}#din-lume">Din lume</a>')
    if din_romania(1):
        linkuri.append(f'<a href="{ACASA}#din-romania">Din România</a>')
    linkuri += ['<span class="sep"></span>',
                '<a href="https://farabaliverne.ro/">← Fără Baliverne (România)</a>',
                '<a href="https://farabaliverne.ro/cauta.html" class="search">🔍 Caută o afirmație</a>']
    coaja = re.sub(r'(<nav class="nav">\s*<div class="wrap">).*?(</div>\s*</nav>)',
                   lambda m: m.group(1) + "\n      " + "\n      ".join(linkuri) + "\n    " + m.group(2),
                   coaja, count=1, flags=re.S)

    # --- conținutul --------------------------------------------------------
    def bloc(titlu, ancora, explicatie, articole):
        if not articole:
            return ""
        return (f'<section class="sec" id="{ancora}">\n  <div class="wrap">\n'
                f'    <h2 class="sec-title">{titlu}</h2>\n'
                f'    <p class="dek" style="margin:-6px 0 18px">{explicatie}</p>\n'
                f'    <div class="grid">\n{"".join(B.card(d) for d in articole)}    </div>\n'
                '    <p style="margin-top:18px"><a href="https://farabaliverne.ro/">'
                'Vezi tot la Fără Baliverne →</a></p>\n  </div>\n</section>\n')

    sectiunea_ro = (
        bloc("Din lume", "din-lume",
             "Ce se verifică în afară — aceleași articole ca la Fără Baliverne. "
             "Lumea nu e nici a unui mal, nici a celuilalt.", din_lume())
        + bloc("Din România", "din-romania",
               "Ce se verifică dincolo de Prut, la Fără Baliverne.", din_romania()))

    corp = f'''
  <section class="wrap" style="padding:28px 0 6px">
    <p class="dek" style="max-width:70ch">{DESCRIERE}</p>
  </section>
{feed(arts)}{sectiunea_ro}'''
    coaja = re.sub(r"<main.*?</main>", f"<main>{corp}</main>", coaja, count=1, flags=re.S)

    os.makedirs(os.path.dirname(IESIRE), exist_ok=True)
    open(IESIRE, "w", encoding="utf-8").write(coaja)
    print(f"✅ moldova/index.html — {len(arts)} articole")


if __name__ == "__main__":
    main()

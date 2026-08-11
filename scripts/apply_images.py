"""
Aplică pozele propuse pe articolele existente.

Pentru fiecare articol cu propunere acceptată:
  - descarcă poza și o găzduiește la noi (img/articole/<slug>.jpg)
  - înlocuiește poza hotlinkată din hero
  - scoate badge-ul de sursă de PE poză (e sursa știrii, nu a pozei)
  - adaugă legenda cu atribuire completă CC
  - scoate `no-referrer` (vrem ca sursa să vadă traficul care vine de la noi)
  - mută og:image / twitter:image pe poza noastră

Articolele fără propunere rămân neatinse.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick_image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROP = os.path.join(ROOT, "preview", "propuneri.json")

# Eticheta în română pentru legendă. Fără ea, ar scrie utilizatorului
# „National Bank of Romania building" sub poză.
ETICHETE = {
    "National Bank of Romania building": "sediul Băncii Naționale a României",
    "Cernavodă Nuclear Power Plant": "Centrala Nucleară de la Cernavodă",
    "Autostrada A3 Romania motorway": "Autostrada A3",
    "Autostrada Romania motorway": "autostradă din România",
    "Palace of the Parliament Chamber of Deputies Romania": "Camera Deputaților",
    "Palace of the Parliament Bucharest": "Palatul Parlamentului",
    "Cotroceni Palace": "Palatul Cotroceni",
    "Victoria Palace Bucharest": "Palatul Victoria",
    "Bucharest government building": "clădire administrativă din București",
    "High Court of Cassation and Justice Romania": "Înalta Curte de Casație și Justiție",
    "Court of Justice of the European Union building": "Curtea de Justiție a UE",
    "Danube river Romania": "Dunărea",
    "Henri Coandă International Airport": "Aeroportul Henri Coandă",
    "Air China Airbus A330": "aeronavă Airbus A330 Air China",
    "TAROM aircraft": "aeronavă TAROM",
    "Stadionul Steaua Bucharest": "Stadionul Steaua",
    "football stadium Romania": "stadion de fotbal din România",
    "Stadionul Ion Oblemenco": "Stadionul Ion Oblemenco",
    "Alternative für Deutschland": "Alternative für Deutschland",
    "Reichstag building Berlin": "Reichstag, Berlin",
    "United States Senate chamber": "Senatul Statelor Unite",
    "White House": "Casa Albă",
    "Gaza Strip": "Fâșia Gaza",
    "Ukraine flag": "drapelul Ucrainei",
    "World Health Organization headquarters": "sediul OMS",
    "Moody's headquarters": "sediul Moody's",
    "NASA logo": "NASA",
    "call centre office": "centru de apeluri",
    "drought dry ground": "secetă",
    "heat wave sun": "caniculă",
    "vaccine vial syringe": "vaccin",
    "artificial intelligence computer screen": "inteligență artificială",
    "Romanian leu banknotes": "bancnote în lei",
}

CREDIT_CSS = """
  .foto-credit{
    display:flex;gap:9px;align-items:flex-start;
    padding:10px 18px 12px;background:var(--card,#fff);
    border-bottom:1px solid var(--line,#e5e7eb);
  }
  .foto-credit svg{flex:none;margin-top:2px;opacity:.45}
  .foto-credit .txt{min-width:0}
  .foto-credit .lead{display:block;font-size:12.5px;line-height:1.45;color:var(--ink-soft,#4b5563)}
  .foto-credit .lead b{font-weight:700;color:var(--ink,#111827)}
  .foto-credit .attrib{display:block;margin-top:3px;font-size:11px;line-height:1.45;color:var(--ink-faint,#9ca3af)}
  .foto-credit a{color:inherit;text-decoration:underline;text-underline-offset:2px}
  .foto-credit a:hover{color:var(--accent,#a5372a)}
"""

CAM = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
       'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
       'stroke-linejoin="round" aria-hidden="true">'
       '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
       '<circle cx="12" cy="13" r="4"/></svg>')


def legenda(item, photo):
    """Portret de persoană -> «foto de arhivă». Loc/instituție -> «ilustrativă»."""
    if item["query_type"] == "persoană":
        lead = (f'<b>Foto de arhivă</b> — {item["query"]}. '
                "Nu este o imagine de la evenimentul relatat.")
    else:
        eticheta = ETICHETE.get(item["query"], item["query"])
        lead = (f'<b>Foto ilustrativă</b> — {eticheta}. '
                "Nu este o imagine de la evenimentul relatat.")

    lic = (f'<a href="{photo["license_url"]}" rel="license nofollow noopener" '
           f'target="_blank">{photo["license"]}</a>'
           if photo.get("license_url") else photo["license"])

    return (
        '<figcaption class="foto-credit">' + CAM + '<span class="txt">'
        f'<span class="lead">{lead}</span>'
        '<span class="attrib">'
        f'„<a href="{photo["descriptionurl"]}" rel="nofollow noopener" target="_blank">'
        f'{photo["title"]}</a>" de {photo["author"]}, via Wikimedia Commons · '
        f'{lic} · decupată'
        "</span></span></figcaption>"
    )


def aplica(item):
    slug = item["slug"]
    path = os.path.join(ROOT, "a", slug + ".html")
    if not os.path.exists(path):
        return "lipsește fișierul"

    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    if "<figcaption class=\"foto-credit\"" in html:
        return "deja aplicat"

    photo = dict(item["photo"])
    try:
        photo = pick_image.download(photo, slug)
    except Exception as exc:
        return f"descărcare eșuată: {exc}"

    local_url = "../" + photo["local"].replace(os.sep, "/")
    alt = (item["query"] or "imagine ilustrativă").replace('"', "")

    # hero-ul: orice <img> extern din blocul .photo devine poza noastră
    nou = (f'<img src="{local_url}" alt="{alt}" loading="eager" '
           'style="position:absolute;inset:0;width:100%;height:100%;'
           'object-fit:cover;z-index:1">')
    html, n = re.subn(
        r'<img src="https?://(?!farabaliverne\.ro)[^"]+"[^>]*?z-index:1[^>]*>',
        nou, html, count=1)
    if n == 0:
        # articolele fără poză hotlinkată au doar gradientul cu emoticon
        html, n = re.subn(r'(<div class="glyph">.*?</div>\s*</div>)',
                          r"\1\n              " + nou, html, count=1, flags=re.S)
    if n == 0:
        return "n-am găsit unde să pun poza"

    # badge-ul de sursă de pe poză iese — sursa rămâne citată în corp
    html = re.sub(r'\s*<div class="srcbadge">.*?</div>\n?', "\n", html,
                  count=1, flags=re.S)

    # legenda cu atribuire
    html = html.replace('            </div>\n          <div class="abody">',
                        '            </div>\n' + legenda(item, photo) +
                        '\n          <div class="abody">', 1)

    # stilul, o singură dată
    if ".foto-credit{" not in html:
        html = html.replace("  .g-hero{", CREDIT_CSS + "  .g-hero{", 1)

    # referrer cinstit spre sursă
    html = html.replace(' referrerpolicy="no-referrer"', "")

    # cardurile sociale arată poza noastră
    abs_url = "https://farabaliverne.ro/" + photo["local"].replace(os.sep, "/")
    html = re.sub(r'(<meta property="og:image" content=")[^"]+(")',
                  r"\1" + abs_url + r"\2", html)
    html = re.sub(r'(<meta name="twitter:image" content=")[^"]+(")',
                  r"\1" + abs_url + r"\2", html)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return f"OK ({photo['bytes']//1024} KB)"


def main():
    with open(PROP, encoding="utf-8") as fh:
        items = json.load(fh)

    aplicate, sarite = 0, 0
    for it in items:
        if not it["photo"]:
            sarite += 1
            continue
        rezultat = aplica(it)
        marca = "OK " if rezultat.startswith("OK") else "!! "
        print(f"  {marca} {it['slug'][:46]:46} {rezultat}")
        if rezultat.startswith("OK"):
            aplicate += 1

    print(f"\naplicate: {aplicate} · fără propunere: {sarite}")


if __name__ == "__main__":
    main()

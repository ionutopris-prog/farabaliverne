"""
Construiește o PREVIZUALIZARE locală a unui articol cu poză proprie,
ca fondatorul să vadă cum ar arăta înainte să schimbăm ceva pe live.

Nu atinge articolul original. Scrie în preview/.
"""

import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick_image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW = os.path.join(ROOT, "preview")

SLUG = "air-china-zbor-direct-bucuresti-beijing"
QUERY = "Air China Airbus A330"
CONTEXT = "zbor direct bucuresti beijing airbus a330-200 pasageri ruta aeriana"
PREFER = "B-5933 MUC 2015 01"     # A330-243 = varianta A330-200 din articol

CREDIT_CSS = """
  .foto-credit{
    display:flex;gap:9px;align-items:flex-start;
    padding:10px 18px 12px;background:var(--card,#fff);
    border-bottom:1px solid var(--line,#e5e7eb);
  }
  .foto-credit svg{flex:none;margin-top:2px;opacity:.45}
  .foto-credit .txt{min-width:0}
  .foto-credit .lead{
    display:block;font-size:12.5px;line-height:1.45;color:var(--ink-soft,#4b5563);
  }
  .foto-credit .lead b{font-weight:700;color:var(--ink,#111827)}
  .foto-credit .attrib{
    display:block;margin-top:3px;font-size:11px;line-height:1.45;
    color:var(--ink-faint,#9ca3af);
  }
  .foto-credit a{color:inherit;text-decoration:underline;text-underline-offset:2px}
  .foto-credit a:hover{color:var(--accent,#a5372a)}
"""


def main():
    candidates = pick_image.search(QUERY, CONTEXT)
    if not candidates:
        sys.exit("niciun candidat acceptat")

    chosen = next((c for c in candidates if PREFER in c["title"]), candidates[0])
    chosen = pick_image.download(chosen, SLUG)
    print(f"poză: {chosen['title']}")
    print(f"  {chosen['width']}x{chosen['height']} · {chosen['license']} · {chosen['author']}")
    print(f"  salvată: {chosen['local']} ({chosen['bytes']//1024} KB)")

    src = os.path.join(ROOT, "a", SLUG + ".html")
    with open(src, encoding="utf-8") as fh:
        html = fh.read()

    # 1. poza hotlinkată -> poza noastră (căile urcă un nivel, articolul e în a/)
    local_url = "../" + chosen["local"].replace(os.sep, "/")
    html = re.sub(
        r'<img src="https://www\.antena3\.ro/[^"]+"[^>]*>',
        f'<img src="{local_url}" alt="Aeronavă Airbus A330-200 a companiei Air China" '
        'loading="eager" style="position:absolute;inset:0;width:100%;height:100%;'
        'object-fit:cover;z-index:1">',
        html,
        count=1,
    )

    # 2. Badge-ul „Antena3 CNN" de PE poză iese: e sursa ȘTIRII, nu a POZEI, iar
    #    așezat peste o fotografie de la Wikimedia lăsa impresia că poza e a lor.
    #    Sursa rămâne citată în corp, cu card dedicat și link — acolo e locul ei.
    html = re.sub(r'\s*<div class="srcbadge">.*?</div>\n?', "\n", html, count=1, flags=re.S)

    # 3. Atribuire completă. CC BY cere toate patru: titlu, autor, sursă,
    #    licență cu link — plus menționarea modificărilor (noi decupăm prin
    #    object-fit:cover). Fără ele, licența nu e respectată.
    lic_link = (
        f'<a href="{chosen["license_url"]}" rel="license nofollow noopener" '
        f'target="_blank">{chosen["license"]}</a>'
        if chosen["license_url"] else chosen["license"]
    )
    cam = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
           'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
           'stroke-linejoin="round" aria-hidden="true">'
           '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
           '<circle cx="12" cy="13" r="4"/></svg>')
    credit = (
        '<figcaption class="foto-credit">' + cam + '<span class="txt">'
        '<span class="lead"><b>Foto ilustrativă</b> — aeronavă Airbus A330 '
        'a companiei Air China. Nu este o imagine de la evenimentul relatat.</span>'
        '<span class="attrib">'
        f'„<a href="{chosen["descriptionurl"]}" rel="nofollow noopener" target="_blank">'
        f'{chosen["title"]}</a>" de {chosen["author"]}, via Wikimedia Commons · '
        f'{lic_link} · decupată'
        "</span></span></figcaption>"
    )
    html = html.replace('            </div>\n          <div class="abody">',
                        f'            </div>\n{credit}\n          <div class="abody">', 1)

    # 4. Miniatura din cardul de sursă rămâne (e o previzualizare spre sursă,
    #    cea mai apărabilă folosire), dar fără no-referrer: vrem ca Antena3 să
    #    vadă în statistici că traficul vine de la noi. Ăsta era chiar
    #    argumentul fondatorului — „eu le fac trafic".
    html = html.replace(' referrerpolicy="no-referrer"', "")

    # 5. stilul creditului
    html = html.replace("  .g-hero{", CREDIT_CSS + "  .g-hero{", 1)

    # 6. og:image -> a noastră (absolut, pentru social)
    html = re.sub(
        r'(<meta property="og:image" content=")[^"]+(")',
        r"\1https://farabaliverne.ro/" + chosen["local"].replace(os.sep, "/") + r"\2",
        html,
    )
    html = re.sub(
        r'(<meta name="twitter:image" content=")[^"]+(")',
        r"\1https://farabaliverne.ro/" + chosen["local"].replace(os.sep, "/") + r"\2",
        html,
    )

    os.makedirs(os.path.join(PREVIEW, "a"), exist_ok=True)
    out = os.path.join(PREVIEW, "a", SLUG + ".html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)

    # copiem doar ce-i trebuie previzualizării ca să arate identic cu live-ul
    for folder in ("img",):
        dst = os.path.join(PREVIEW, folder)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(os.path.join(ROOT, folder), dst)

    print(f"\npreviuzualizare: {out}")


if __name__ == "__main__":
    main()

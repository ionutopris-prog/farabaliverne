"""
Unealta pe care o cheamă redactorul automat pentru poza unui articol.

    python3 scripts/article_image.py <slug> "<ce căutăm>" "<context articol>" [persoana]

Caută pe Wikimedia Commons, verifică licența și contextul, descarcă, comprimă
și tipărește HTML-ul gata de lipit. Dacă nu găsește nimic potrivit, tipărește
„NIMIC" — și atunci articolul rămâne pe cardul de brand. Mai bine fără poză
decât cu una greșită.

Ce să pui la <ce căutăm>:
  - persoană numită în articol  -> numele ei („Ilie Bolojan")
  - instituție sau loc          -> denumirea în engleză, stabilă pe Commons
                                   („National Bank of Romania building")
  NU pune cuvinte extrase din titlu. „Puterea de cumpărare" -> „Puterea" a dat
  o locomotivă cu abur pe o știre despre inflație.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick_image  # noqa: E402

CAM = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" '
       'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
       'stroke-linejoin="round" aria-hidden="true">'
       '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
       '<circle cx="12" cy="13" r="4"/></svg>')


# 🔴 Cuvinte care, luate singure, caută cu totul altceva decât articolul.
#
# Găsite pe 5 septembrie 2026, când fondatorul a trimis o captură de pe site:
# „PNL și USR boicotează CAMERA Deputaților" avea în locul pozei un aparat foto
# Konica. Căutarea fusese literalmente `alt="Camera"`. O măturare a găsit încă
# 18 la fel: „CASA Albă" -> o casă în ruină, „CURTEA Constituțională" -> o casă
# țărănească, „GUVERNUL anunță" -> un drum din Țara Galilor, iar „MAREA
# Britanie" -> o coastă italiană, pe patru articole diferite.
#
# Toate sunt substantive comune care în română fac parte dintr-un nume propriu
# format din două cuvinte. Rupte de al doilea cuvânt, nu mai înseamnă nimic —
# sau, mai rău, înseamnă altceva foarte fotogenic.
#
# Regula: dacă întrebarea e UN SINGUR cuvânt din lista asta, o refuzăm. Cine
# cheamă scriptul (redactorul sau garda pozelor) încearcă oricum mai multe
# întrebări la rând, deci refuzul îl împinge spre următoarea, nu îl blochează.
CUVINTE_TRUNCHIATE = {
    "camera", "curtea", "casa", "guvernul", "senatul", "banca", "parchetul",
    "garda", "consiliul", "ministerul", "primaria", "primăria", "instanta",
    "instanța", "comisia", "biroul", "partidul", "presedintele", "președintele",
    "premierul", "ministrul", "judecatorul", "judecătorul", "procurorul",
    "politia", "poliția", "armata", "scoala", "școala", "spitalul",
    "universitatea", "academia", "fabrica", "uzina", "gara", "portul",
    "aeroportul", "piata", "piața", "strada", "podul", "turnul", "muntele",
    "raul", "râul", "lacul", "marea", "insula", "satul", "orasul", "orașul",
    "judetul", "județul", "tara", "țara", "legea", "proiectul", "raportul",
    "acordul", "tratatul", "planul", "programul", "bugetul", "fondul",
}


def intrebare_trunchiata(q):
    """Un singur cuvânt dintr-un nume propriu rupt în două. Vezi nota de sus."""
    cuv = q.strip().strip(".,;:").split()
    return len(cuv) == 1 and cuv[0].lower() in CUVINTE_TRUNCHIATE



def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    slug = sys.argv[1]
    query = sys.argv[2]
    context = sys.argv[3] if len(sys.argv) > 3 else ""
    este_persoana = len(sys.argv) > 4 and sys.argv[4].startswith("pers")

    if intrebare_trunchiata(query):
        print("NIMIC")
        print(f'(refuzat: "{query}" e un cuvant rupt dintr-un nume propriu; '
              f'cauta numele intreg)', file=sys.stderr)
        return

    candidati = pick_image.search(query, context,
                                  nume_persoana=query if este_persoana else None)
    if not candidati:
        print("NIMIC")
        return

    foto = pick_image.download(candidati[0], slug)

    eticheta = "Foto de arhivă" if este_persoana else "Foto ilustrativă"
    lic = (f'<a href="{foto["license_url"]}" rel="license nofollow noopener" '
           f'target="_blank">{foto["license"]}</a>'
           if foto.get("license_url") else foto["license"])

    img = (f'<img src="../{foto["local"]}" alt="{query}" loading="eager" '
           'style="position:absolute;inset:0;width:100%;height:100%;'
           'object-fit:cover;z-index:1">')

    caption = (
        '<figcaption class="foto-credit">' + CAM + '<span class="txt">'
        f'<span class="lead"><b>{eticheta}</b> — {query}. '
        'Nu este o imagine de la evenimentul relatat.</span>'
        '<span class="attrib">'
        f'„<a href="{foto["descriptionurl"]}" rel="nofollow noopener" target="_blank">'
        f'{foto["title"]}</a>" de {foto["author"]}, via Wikimedia Commons · '
        f'{lic} · decupată'
        "</span></span></figcaption>"
    )

    print(json.dumps({
        "gasit": True,
        "fisier": foto["local"],
        "kb": foto["bytes"] // 1024,
        "licenta": foto["license"],
        "autor": foto["author"],
        "og_image": "https://farabaliverne.ro/" + foto["local"],
        "img_html": img,
        "figcaption_html": caption,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

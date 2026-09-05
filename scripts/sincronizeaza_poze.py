# -*- coding: utf-8 -*-
"""
Aduce pagina la zi cu JSON-ul: <img> și creditul de sub poză.

    python3 scripts/sincronizeaza_poze.py            # repară
    python3 scripts/sincronizeaza_poze.py --raport   # doar numără

DE CE EXISTĂ. Când se înlocuiește poza unui articol, `article_image.py` scrie
fișierul nou și câmpul `poza` din JSON. Dar PAGINA nu se atinge: rămâne cu
`<img alt="...">` vechi și, mai grav, cu FIGCAPTION-ul vechi — adică pe site
scrie alt autor și altă licență decât cei ai pozei care se vede.

Găsit pe 5 septembrie 2026, după ce fondatorul a cerut o verificare a tot ce
s-a stabilit în ziua aia: 144 de pagini aveau poza nouă și creditul vechi.
Nu se vedea din nimic — poza era corectă, doar semnătura de sub ea mințea.

E o problemă de licență, nu de estetică: CC BY cere atribuirea autorului
CORECT. Un credit greșit e mai rău decât niciun credit, fiindcă arată ca o
atribuire făcută.

Regula: JSON-ul e sursa adevărului. Pagina se aliniază după el, niciodată
invers — pagina se regenerează, JSON-ul se scrie de unelte.
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = re.compile(r'<img src="[^"]+"[^>]*z-index:1">')
FIG = re.compile(r'<figcaption class="foto-credit">.*?</figcaption>', re.S)


def main():
    doar_raport = "--raport" in sys.argv
    reparate, sarite = 0, 0
    for j in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(j).startswith("_"):
            continue
        with open(j, encoding="utf-8") as fh:
            d = json.load(fh)
        pz = d.get("poza") or {}
        if not pz.get("img_html"):
            continue
        slug = d.get("slug") or os.path.basename(j)[:-5]
        p = os.path.join(ROOT, "a", slug + ".html")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            h = fh.read()
        nou = h
        mi = IMG.search(nou)
        if mi and mi.group(0) != pz["img_html"]:
            nou = nou[:mi.start()] + pz["img_html"] + nou[mi.end():]
        if pz.get("figcaption_html"):
            mf = FIG.search(nou)
            if mf and mf.group(0) != pz["figcaption_html"]:
                nou = nou[:mf.start()] + pz["figcaption_html"] + nou[mf.end():]
        if nou == h:
            sarite += 1
            continue
        reparate += 1
        if not doar_raport:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(nou)
        print(("ar fi reparat: " if doar_raport else "reparat: ") + slug)
    print(f"\n{'de reparat' if doar_raport else 'reparate'}: {reparate} · deja la zi: {sarite}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Panoul „Ține adevărul viu" apare pe toate paginile. Pe un articol, share-ul
dă mai departe articolul — corect. Pe homepage și pe celelalte pagini de
listă nu există „articol curent", deci dă mai departe site-ul — tot corect,
DAR butonul scria „Postează", ceea ce te lăsa să crezi că postezi știrea pe
care tocmai o citeai în listă.

Aici doar clarificăm eticheta pe paginile care NU sunt articole, plus un
îndemn scurt spre calea corectă. Fără butoane noi.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["index.html", "cauta.html", "politicieni.html", "publicitate.html"]

OLD_BTN = ">𝕏  Postează</button>"
NEW_BTN = ">𝕏  Postează site-ul</button>"

ANCHOR = "<small>Fără abonament. Fără paywall. Doar adevăr.</small>"
HINT = (
    '<small style="display:block;margin-top:6px;opacity:.85">'
    "Vrei să dai mai departe o <b>știre anume</b>? Deschide-o — butoanele din "
    "colțul articolului postează exact acea știre, cu poza și titlul ei."
    "</small>"
)

changed = []
skipped = []

for name in PAGES:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        skipped.append(f"{name}: lipsește")
        continue

    with open(path, encoding="utf-8") as fh:
        html = fh.read()

    original = html

    if OLD_BTN in html:
        html = html.replace(OLD_BTN, NEW_BTN)
    elif NEW_BTN not in html:
        skipped.append(f"{name}: butonul 𝕏 nu are forma așteptată")
        continue

    if HINT not in html:
        if ANCHOR not in html:
            skipped.append(f"{name}: nu găsesc ancora pentru îndemn")
        else:
            html = html.replace(ANCHOR, ANCHOR + "\n          " + HINT, 1)

    if html != original:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        changed.append(name)
    else:
        skipped.append(f"{name}: deja aplicat")

print("modificate:", ", ".join(changed) if changed else "(niciuna)")
for s in skipped:
    print("  sărit —", s)

# Verificare: articolele NU trebuie atinse.
art_dir = os.path.join(ROOT, "a")
leaked = [
    f for f in os.listdir(art_dir)
    if f.endswith(".html")
    and NEW_BTN in open(os.path.join(art_dir, f), encoding="utf-8").read()
]
if leaked:
    print(f"EROARE: eticheta de site a ajuns în {len(leaked)} articole")
    sys.exit(1)
print("verificat: articolele au rămas cu share pe articol")

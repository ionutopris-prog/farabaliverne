"""
Înlocuiește poza unui articol care are deja poză proprie, dar greșită.

`apply_images.py` face migrarea de la hotlink la poză proprie. Asta e altceva:
articolul are deja o poză găzduită de noi, doar că e nepotrivită — și trebuie
schimbate deodată fotografia, legenda de atribuire, textul alt și og:image.
Dacă uiți unul, share-ul arată tot poza veche.

A apărut pe 12 august, când patru articole despre Ucraina, Serbia și Bulgaria
purtau toate `Flag_of_Turkey.svg`, iar articolul despre eclipsă avea sigla NASA.

Folosire:
    python3 scripts/replace_image.py <slug> "<ce căutăm>" "<context articol>" [persoana]
    python3 scripts/replace_image.py <slug> --scoate      # înapoi la cardul de brand
"""

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

# Coperta site-ului, aceeași pe care o folosește homepage-ul. Scoțând poza unui
# articol, share-ul lui trebuie să cadă pe ceva care CHIAR există — altfel
# previzualizarea rămâne goală, adică exact bug-ul reparat pe 11 august.
OG_IMPLICIT = "https://farabaliverne.ro/og-cover.png"

IMG = re.compile(r'<img src="\.\./img/articole/[^"]+"[^>]*z-index:1">')
FIGCAP = re.compile(r'<figcaption class="foto-credit">.*?</figcaption>', re.S)
META_IMG = re.compile(
    r'(<meta (?:property="og:image"|name="twitter:image") content=")[^"]+(">)')


def articol(slug):
    path = os.path.join(ROOT, "a", slug + ".html")
    if not os.path.exists(path):
        sys.exit(f"nu există a/{slug}.html")
    return path


def poza_veche(html):
    m = re.search(r'<img src="\.\./img/articole/([^"]+)"', html)
    return m.group(1) if m else None


def scoate(path, html):
    """Înapoi la cardul de brand: mai bine fără poză decât cu una greșită."""
    html = IMG.sub("", html)
    html = FIGCAP.sub("", html)
    html = META_IMG.sub(r"\1" + OG_IMPLICIT + r"\2", html)
    open(path, "w", encoding="utf-8").write(html)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    slug = sys.argv[1]
    path = articol(slug)
    html = open(path, encoding="utf-8").read()
    veche = poza_veche(html)

    if not IMG.search(html):
        sys.exit(f"{slug}: nu are poză proprie în hero — folosește article_image.py")

    if sys.argv[2] == "--scoate":
        scoate(path, html)
        print(f"{slug}: poză scoasă, rămâne cardul de brand")
        _sterge(veche, slug)
        return

    cauta, context = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "")
    cmd = [sys.executable, os.path.join(SCRIPTS, "article_image.py"),
           slug, cauta, context] + sys.argv[4:5]
    rezultat = subprocess.run(cmd, capture_output=True, text=True)
    if rezultat.returncode != 0:
        sys.exit(rezultat.stderr or rezultat.stdout)

    try:
        prop = json.loads(rezultat.stdout)
    except json.JSONDecodeError:
        sys.exit(f"{slug}: nu am găsit nimic potrivit — "
                 f"{rezultat.stdout.strip() or 'NIMIC'}")
    if not prop.get("gasit"):
        sys.exit(f"{slug}: nu am găsit nimic potrivit; articolul rămâne "
                 f"cum e (sau rulează cu --scoate)")

    html = IMG.sub(lambda _: prop["img_html"], html, count=1)
    html = FIGCAP.sub(lambda _: prop["figcaption_html"], html, count=1)
    html = META_IMG.sub(r"\g<1>" + prop["og_image"] + r"\g<2>", html)
    open(path, "w", encoding="utf-8").write(html)

    noua = os.path.basename(prop["fisier"])
    if veche and veche != noua:
        _sterge(veche, slug)
    print(f"{slug}: {veche} → {noua} ({prop['kb']} KB, {prop['licenta']}, "
          f"{prop['autor']})")


def _sterge(fisier, slug):
    """Scoatem și poza veche, și miniatura ei — altfel rămân în repo degeaba."""
    if not fisier:
        return
    for d in ("articole", "carduri"):
        p = os.path.join(ROOT, "img", d, fisier)
        if os.path.exists(p):
            os.remove(p)


if __name__ == "__main__":
    main()

"""
Repară pozele prea grele: le redimensionează și recomprimă până sub limită.

Rulează în ediție ÎNAINTE de `verify_images.py`. Rostul e ca verificarea să
redevină plasă de siguranță, nu blocaj de rutină: o poză de 400 KB e o problemă
de greutate a paginii, nu de legalitate, și n-are de ce să țină site-ul nepublicat
ore întregi. Ce e legal (hotlink, atribuire lipsă) rămâne blocant în verificare.

Pe 12 august a ținut site-ul neactualizat ~18 ore, prin 10 ediții la rând.
Cauza n-a fost greutatea în sine, ci că unealta de compresie lipsea și
`comprima()` renunța TĂCUT — al treilea eșec al proiectului care arată ca succes.
De-aia scriptul ăsta **pică zgomotos** dacă nu găsește nici sips, nici Pillow,
în loc să raporteze că n-a avut ce repara.

Folosire:
    python3 scripts/shrink_images.py           # repară
    python3 scripts/shrink_images.py --dry-run # doar arată ce ar face
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pick_image import IMG_DIR, ROOT, comprima, unealta_compresie  # noqa: E402

# Limita verificării (300 KB) e mai largă decât ținta compresiei (KB_MAX = 260),
# ca o poză care nu coboară perfect la țintă să nu pice totuși verificarea.
KB_LIMITA = 300
EXTENSII = (".jpg", ".jpeg", ".png", ".webp")


def prea_grele():
    fisiere = []
    for path in sorted(glob.glob(os.path.join(IMG_DIR, "*"))):
        if not path.lower().endswith(EXTENSII):
            continue
        kb = os.path.getsize(path) // 1024
        if kb > KB_LIMITA:
            fisiere.append((path, kb))
    return fisiere


def _releaga(vechi, nou):
    """Schimbă numele pozei în articolele care o folosesc, după redenumire."""
    for path in glob.glob(os.path.join(ROOT, "a", "*.html")):
        html = open(path, encoding="utf-8").read()
        if vechi not in html:
            continue
        open(path, "w", encoding="utf-8").write(html.replace(vechi, nou))
        print(f"  relegat în {os.path.basename(path)}: {vechi} → {nou}")


def main():
    dry = "--dry-run" in sys.argv

    unealta = unealta_compresie()
    if not unealta:
        print("::error::Nu există nicio unealtă de compresie (nici sips, nici "
              "Pillow). Instalează Pillow: pip install Pillow")
        sys.exit(1)
    print(f"unealtă de compresie: {unealta}")

    tinta = prea_grele()
    if not tinta:
        print("nicio poză peste limită")
        return

    ramase = []
    for path, kb in tinta:
        nume = os.path.basename(path)
        if dry:
            print(f"  ar repara {nume} ({kb} KB)")
            continue

        nou = comprima(path)
        acum = os.path.getsize(nou) // 1024
        # Compresia scoate JPEG, deci un .png poate fi redenumit .jpg. Articolul
        # trimite spre numele vechi, așa că îl mutăm și pe el.
        if nou != path:
            _releaga(os.path.basename(path), os.path.basename(nou))

        if acum > KB_LIMITA:
            ramase.append(f"{nume}: {kb} KB → {acum} KB, tot peste {KB_LIMITA} KB")
        else:
            print(f"  {nume}: {kb} KB → {acum} KB")

    if dry:
        return

    for r in ramase:
        print(f"::warning::{r}")
    print(f"\n{len(tinta) - len(ramase)}/{len(tinta)} poze aduse sub limită")


if __name__ == "__main__":
    main()

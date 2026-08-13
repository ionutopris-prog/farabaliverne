"""
Verifică pozele articolelor. Rulează după fiecare ediție, în GitHub Actions.

Ce oprește:
  - articol NOU care hotlinkează poza altei publicații în hero
  - poză găzduită de noi fără legendă completă (autor + licență + link)
  - poză peste limita de greutate
  - `referrerpolicy="no-referrer"` — ascunde de sursă traficul pe care i-l trimitem

Articolele vechi rămase pe hotlink sunt tolerate și doar raportate: sunt cele
pentru care nu există fotografie potrivită pe Commons. Lista lor e fixă; dacă
apare unul nou pe listă, ceva s-a stricat și rularea pică.
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_MAX = 300

# Articole de dinaintea trecerii la poze proprii, pentru care Commons n-are
# nimic potrivit. Tolerate, dar numărate. Nu adăuga aici fără motiv.
HOTLINK_TOLERAT = {
    "ancpi-eterra-cadastru-blocaj", "berlin-csd-atac-terorist",
    "boe-dobanda-mentinuta-3-75", "cfr-cluj-tromso-0-5-conference-league",
    "china-ev-cota-piata-europa-vest", "fantana-zece-ani-inchisoare",
    "franta-control-investitii-straine-10-la-suta",
    "inflatie-10-9-putere-cumparare", "iunie-2026-record-caldura-copernicus-omm",
    "media-de-stat-china-marea-chinei-de-sud", "popovici-europene-paris-record",
    "romania-deficit-comercial-s1-2026", "schengen-italia-spania-ceuta",
    "sosoaca-clip-ai-penitenciar", "statine-efecte-secundare-studiu-lancet-2026",
    "trump-iran-compensatie-hormuz", "uk-interzice-capcanele-abonament-burnham",
    "apia-inmatriculari-auto-scadere-iulie-2026", "burnete-avertisment-recesiune-2026",
}

HERO_EXTERN = re.compile(
    r'<img\s+src="https?://(?!farabaliverne\.ro)[^"]+"[^>]*?z-index:1', re.I)
HERO_LOCAL = re.compile(r'<img\s+src="\.\./img/articole/([^"]+)"', re.I)
CREDIT = re.compile(r'<figcaption class="foto-credit">(.*?)</figcaption>', re.S)


def main():
    erori, avertismente = [], []
    cu_poza = hotlink_vechi = 0

    for path in sorted(glob.glob(os.path.join(ROOT, "a", "*.html"))):
        slug = os.path.basename(path)[:-5]
        html = open(path, encoding="utf-8").read()

        if "no-referrer" in html:
            erori.append(f"{slug}: are referrerpolicy=no-referrer — "
                         "ascunde de sursă traficul pe care i-l trimitem")

        local = HERO_LOCAL.search(html)
        extern = HERO_EXTERN.search(html)

        if extern and not local:
            hotlink_vechi += 1
            if slug not in HOTLINK_TOLERAT:
                erori.append(f"{slug}: hotlinkează poza altei publicații în hero. "
                             "Folosește scripts/article_image.py sau lasă cardul de brand.")
            continue

        if not local:
            continue

        cu_poza += 1

        credit = CREDIT.search(html)
        if not credit:
            erori.append(f"{slug}: poză găzduită de noi, fără legendă de atribuire")
            continue

        text = credit.group(1)
        if "Wikimedia Commons" not in text:
            erori.append(f"{slug}: legenda nu spune sursa")
        # Domeniul public n-are text de licență de linkat — atribuirea e completă
        # fără link. Commons întoarce eticheta când în engleză („Public domain"),
        # când tradusă („Domeniu public"), în funcție de șablonul fișierului, iar
        # verificarea știa doar varianta engleză. O singură poză cu eticheta în
        # română a oprit deploy-ul 4 ore și jumătate pe 13 august, blocând 11
        # articole care n-aveau nicio problemă.
        pd = ("public domain" in text.lower() or "domeniu public" in text.lower())
        if "creativecommons.org" not in text and not pd:
            erori.append(f"{slug}: legenda nu are link către licență")
        if "de autor necunoscut" in text:
            avertismente.append(f"{slug}: autor neidentificat")

        fisier = os.path.join(ROOT, "img", "articole", local.group(1))
        if not os.path.exists(fisier):
            erori.append(f"{slug}: poza lipsește de pe disc ({local.group(1)})")
        else:
            kb = os.path.getsize(fisier) // 1024
            if kb > KB_MAX:
                erori.append(f"{slug}: poza are {kb} KB, peste limita de {KB_MAX} KB")

    print(f"articole cu poză proprie: {cu_poza}")
    print(f"articole vechi rămase pe hotlink: {hotlink_vechi}")

    for a in avertismente:
        print(f"::warning::{a}")
    for e in erori:
        print(f"::error::{e}")

    if erori:
        print(f"\n{len(erori)} probleme de rezolvat")
        sys.exit(1)
    print("\nverificare trecută")


if __name__ == "__main__":
    main()

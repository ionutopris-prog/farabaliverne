"""
Scoate din articole toate pozele luate de pe serverul altei publicații.

Sunt două locuri, cu tratament diferit:

1. POZA HERO. Cardul de brand (dungile + emoji) e deja acolo, dedesubt — poza
   hotlinkată doar stă suprapusă peste el, absolut poziționată. Ștergem `<img>`
   și cardul se dezvelește singur. Nu e nimic de reconstruit.

2. MINIATURA din cardul de link către sursă. Acolo `<span>`-ul are 132px lățime
   și fundal deschis, ca să încapă poza. Fără poză ar rămâne o gaură, așa că
   îi aplicăm exact ce făcea deja `onerror`-ul lui: bară de 8px în culoarea de
   accent. Adică forma pe care articolele o luau oricum când poza sursei nu se
   încărca — nimic nou vizual.

De ce le scoatem: e banda de trafic a altcuiva, folosită fără voie, iar o
pagină care încarcă imagini de la ~50 de domenii străine arată suspect pentru
orice scaner de reputație. Pozele de presă NU pot fi descărcate la noi — au
drepturi. Singurul răspuns corect e să nu le mai afișăm.

Rulare:
    python3 scripts/scoate_hotlink.py            # arată ce ar face
    python3 scripts/scoate_hotlink.py --chiar    # o face
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# <img> care trage de pe alt domeniu decât al nostru
IMG_STRAIN = re.compile(
    r'<img[^>]+src="https://(?!farabaliverne\.ro)[^"]*"[^>]*>')

# <span>-ul miniaturii din cardul de sursă, cu tot cu poza dinăuntru
MINIATURA = re.compile(
    r'<span style="flex:0 0 132px;[^"]*">\s*'
    r'<img[^>]+src="https://(?!farabaliverne\.ro)[^"]*"[^>]*>\s*</span>')

# Ce punea `onerror` când poza sursei nu se încărca. Păstrăm exact aceeași
# formă, ca articolele reparate să arate ca cele care oricum n-aveau miniatură.
BARA = '<span style="flex:0 0 8px;background:var(--accent)"></span>'


def repara(text):
    text, n_mini = MINIATURA.subn(BARA, text)
    text, n_hero = IMG_STRAIN.subn("", text)
    return text, n_mini, n_hero


def main():
    chiar = "--chiar" in sys.argv
    t_mini = t_hero = t_fis = 0

    for path in sorted(glob.glob(os.path.join(ROOT, "a", "*.html"))):
        with open(path, encoding="utf-8") as fh:
            vechi = fh.read()
        nou, n_mini, n_hero = repara(vechi)
        if nou == vechi:
            continue
        t_fis += 1
        t_mini += n_mini
        t_hero += n_hero
        print(f"  {os.path.basename(path)[:-5][:52]:<52} "
              f"miniaturi: {n_mini}  hero: {n_hero}")
        if chiar:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(nou)

    print(f"\n{t_fis} articole · {t_mini} miniaturi · {t_hero} poze hero")
    if not chiar:
        print("(nimic n-a fost modificat — rulează cu --chiar)")


if __name__ == "__main__":
    main()

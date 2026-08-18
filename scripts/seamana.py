"""
„Am mai scris asta?" — de rulat ÎNAINTE de a publica un articol nou.

De ce există: botul verifica doar slug-urile, iar același subiect scris cu alt
slug trecea nedetectat. Așa au ajuns pe site trei perechi de duplicate — între
ele, același meci FC Argeș–Craiova publicat de două ori, o dată cu scorul „0-1"
și o dată „1-0".

Folosește exact regula măsurată pe toate articolele: un semnal TARE (aceeași
sursă citată, aceeași persoană, sau minimum trei cuvinte rare comune), nu
firimituri adunate.

Rulare:
    python3 scripts/seamana.py "Titlul propus" "dek-ul propus, opțional"
    python3 scripts/seamana.py "Titlu" --surse https://a.ro/x https://b.ro/y

Ce faci cu rezultatul:
    ≥ 20  Aproape sigur ACELAȘI eveniment. NU publica un articol nou.
    12-19 Aceeași poveste, alt moment. Publică, dar leagă-te de firul existent.
    < 12  Subiect nou. Publică normal.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site as B   # noqa: E402

PRAG_ACELASI = 20
PRAG_ACEEASI_POVESTE = 12


def main():
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not arg:
        print(__doc__)
        sys.exit(1)
    titlu = arg[0]
    dek = arg[1] if len(arg) > 1 else ""
    surse = set()
    if "--surse" in sys.argv:
        for u in sys.argv[sys.argv.index("--surse") + 1:]:
            if u.startswith("http"):
                surse.add(u.split("?")[0])

    arts = B.load()
    idx, rar, obisnuit = B.indice_inrudite(arts)
    cuv = B._cuvinte(titlu + " " + dek)

    rez = []
    for slug, b in idx.items():
        cu = surse & b["urls"]
        com = cuv & b["cuv"]
        r = com & rar
        # Suprapunerea titlului, ca semnal de sine stătător. Fără ea, două titluri
        # aproape identice scapă dacă vorbesc despre lucruri des pomenite:
        # „FC Argeș învinge Universitatea Craiova, 0-1" vs „…, 1-0" nu are trei
        # cuvinte RARE comune, fiindcă „Craiova" și „SuperLiga" apar peste tot.
        # Exact perechea asta a ajuns publicată de două ori.
        acoperire = len(com) / max(1, min(len(cuv), len(b["cuv"])))
        if not (cu or len(r) >= 3 or acoperire >= 0.55):
            continue
        s = 6 * len(cu) + 2 * len(r) + len(com & obisnuit) + int(20 * acoperire)
        rez.append((s, slug))
    rez.sort(reverse=True)
    rez = [x for x in rez if x[0] >= 8][:5]

    if not rez:
        print("SUBIECT NOU — nu am găsit nimic asemănător. Publică normal.")
        return

    top = rez[0][0]
    if top >= PRAG_ACELASI:
        print("⛔ ACELAȘI EVENIMENT — NU publica un articol nou.")
        print("   Actualizează articolul de mai jos: adaugă-i sursele noi și, dacă e cazul,")
        print("   încă o afirmație în `probat`. Nu crea alt slug pentru aceeași știre.")
    elif top >= PRAG_ACEEASI_POVESTE:
        print("⚠️  ACEEAȘI POVESTE, ALT MOMENT — poți publica, dar e o etapă nouă,")
        print("   nu un subiect nou. Scrie titlul ca atare (ce s-a schimbat azi).")
    else:
        print("✅ Înrudit, dar distinct — publică normal.")

    print()
    for s, slug in rez:
        d = arts[slug]
        print(f"  [{s:>3}] {d.get('date','')}  {d['title'][:78]}")
        print(f"        a/{slug}.html")


if __name__ == "__main__":
    main()

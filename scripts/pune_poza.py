#!/usr/bin/env python3
"""
pune_poza.py — pune pe un articol o poză anume de pe Wikimedia Commons, aleasă
de om, nu ghicită după numele autorilor (garda_poze a pus „Langa Township" pe
cuptorul de la Ursoaia și o carte de genealogie pe studiul din Copenhaga,
12 sept 2026, fiindcă articolele „Minți luminate" n-au persoane cunoscute).

Rulare:
    python3 scripts/pune_poza.py <slug> "<căutare pe Commons>" "<context în română>"
Scrie `poza` în data/<slug>.json, regenerează pagina (scrie_articol) și lasă
build_site / sincronizeaza_poze să facă restul.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import garda_poze as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    slug, q = sys.argv[1], sys.argv[2]
    ctx = sys.argv[3] if len(sys.argv) > 3 else q
    j = os.path.join(ROOT, "data", slug + ".json")
    d = json.load(open(j, encoding="utf-8"))
    gasit = G.cauta(slug, q, ctx)
    if not gasit:
        print(f"⚪ {slug}: nimic pentru „{q}”"); return 1
    d["poza"] = {k: gasit[k] for k in ("img_html", "figcaption_html", "fisier", "licenta", "autor") if k in gasit}
    json.dump(d, open(j, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "scrie_articol.py"), slug], cwd=ROOT, check=False)
    print(f"✅ {slug}: {gasit.get('licenta','')} · {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

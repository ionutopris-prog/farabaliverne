"""
Postează automat articolele noi pe pagina de Facebook „Fără Baliverne".

Textul NU se inventează aici — îl ia din `build_post_queue.compune_fb()`, exact
varianta pe care fondatorul o copia manual până acum. Un singur loc unde se
scrie postarea, ca să nu ajungă cele două forme să se contrazică.

Ce cere ca să funcționeze (variabile de mediu / secrete GitHub):
    FB_ENABLED     = 1            poarta. Fără ea, scriptul doar ARATĂ ce ar posta.
    FB_PAGE_ID     = <id pagină>
    FB_PAGE_TOKEN  = <token de pagină, de lungă durată>

Rulare:
    python3 scripts/posteaza_facebook.py              # arată, nu postează
    python3 scripts/posteaza_facebook.py --publica    # postează (dacă FB_ENABLED=1)
    python3 scripts/posteaza_facebook.py --cate 2     # câte cel mult, într-o rulare

Ce a fost postat se ține minte în `data/_postate-fb.json`, care se comite. Fără
fișierul ăsta, fiecare rulare de CI ar reposta tot — runnerul e curat de fiecare
dată, nu are altă memorie.

De ce cel mult 1-2 pe rulare: pagina publică 10-14 articole pe zi. Turnate toate
pe Facebook, pagina arată a robot și distribuția scade. Postăm puține și pe cele
care merită — demontările întâi, ca în lista manuală.
"""

import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_post_queue import PRIORITATE, compune_fb, verdict  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARE = os.path.join(ROOT, "data", "_postate-fb.json")
API = "https://graph.facebook.com/v21.0"
SITE = "https://farabaliverne.ro"
ZILE = 2       # nu postăm articole mai vechi de-atât; pe Facebook n-au sens
PE_ZI = 4      # plafon zilnic (se poate schimba din FB_MAX_PE_ZI)


def stare_citeste():
    if not os.path.exists(STARE):
        return {}
    try:
        return json.load(open(STARE, encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def stare_scrie(s):
    with open(STARE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def candidate(postate):
    """Articolele din ultimele ZILE zile care n-au fost încă postate."""
    limita = (datetime.now() - timedelta(days=ZILE)).strftime("%Y-%m-%d")
    out = []
    for p in glob.glob(os.path.join(ROOT, "data", "*.json")):
        if os.path.basename(p).startswith("_"):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except ValueError:
            continue
        slug = d.get("slug")
        if not slug or slug in postate:
            continue
        # articol real, cu pagină generată — altfel linkul ar duce în 404
        if not os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            continue
        if (d.get("date") or "") < limita:
            continue
        out.append(d)
    # aceeași ordine ca în lista manuală: demontările primele, apoi cele noi
    out.sort(key=lambda d: (PRIORITATE.get(verdict(d)[1], 3),
                            -int((d.get("date") or "0").replace("-", "")),
                            d.get("slug", "")))
    return out


def postate_azi(postate):
    """Câte au ieșit deja azi. Contorul stă în starea comisă, nu în runner."""
    azi = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(1 for v in postate.values()
               if isinstance(v, dict) and (v.get("cand") or "").startswith(azi))


def posteaza(page_id, token, mesaj, link):
    date = urllib.parse.urlencode({
        "message": mesaj,
        "link": link,
        "access_token": token,
    }).encode()
    cerere = urllib.request.Request(f"{API}/{page_id}/feed", data=date)
    with urllib.request.urlopen(cerere, timeout=45) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publica", action="store_true",
                    help="chiar postează; fără el, doar arată")
    ap.add_argument("--cate", type=int, default=1,
                    help="cel mult atâtea postări într-o rulare (implicit 1)")
    ap.add_argument("--de-acum", action="store_true", dest="de_acum",
                    help="marchează tot ce există ACUM ca postat, fără să posteze; "
                         "de rulat o singură dată, la pornire, ca să nu se reverse "
                         "pe pagină arhiva ultimelor două zile")
    a = ap.parse_args()

    postate = stare_citeste()

    if a.de_acum:
        n = 0
        for d in candidate(postate):
            postate[d["slug"]] = {"id": "", "cand": "sarit-la-pornire"}
            n += 1
        stare_scrie(postate)
        print(f"Am marcat {n} articole ca deja tratate. De acum se postează doar ce apare nou.")
        return 0

    lista = candidate(postate)
    if not lista:
        print("Nimic nou de postat.")
        return 0

    pornit = os.environ.get("FB_ENABLED", "").strip() in ("1", "true", "da")
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    chiar = a.publica and pornit and page_id and token

    if a.publica and not chiar:
        lipsa = [n for n, v in (("FB_ENABLED", pornit), ("FB_PAGE_ID", page_id),
                                ("FB_PAGE_TOKEN", token)) if not v]
        print(f"Nu postez: lipsește {', '.join(lipsa)}. Arăt doar ce-ar fi ieșit.\n")

    # Plafonul zilnic. Site-ul scoate 10-14 articole pe zi; turnate toate pe
    # pagină, ar arăta a robot, iar fondatorul posta manual 2-3. Ținem ritmul
    # ăla — automatizăm gestul, nu schimbăm ce vede omul în feed.
    try:
        pe_zi = int(os.environ.get("FB_MAX_PE_ZI", "") or PE_ZI)
    except ValueError:
        pe_zi = PE_ZI
    ramase = max(0, pe_zi - postate_azi(postate))
    if chiar and ramase == 0:
        print(f"Plafonul zilnic ({pe_zi}) e atins. Restul așteaptă mâine.")
        return 0

    n = max(1, a.cate)
    if chiar:
        n = min(n, ramase)
    ales = lista[:n]
    for d in ales:
        link = f"{SITE}/a/{d['slug']}.html"
        mesaj = compune_fb(d)
        if not chiar:
            print("─" * 70)
            print(f"[{verdict(d)[0]}]  {d['slug']}")
            print("─" * 70)
            print(mesaj)
            print()
            continue
        try:
            r = posteaza(page_id, token, mesaj, link)
        except urllib.error.HTTPError as e:
            corp = e.read().decode("utf-8", "replace")[:500]
            print(f"::error::Facebook a refuzat {d['slug']}: {e.code} {corp}")
            return 1
        except urllib.error.URLError as e:
            print(f"::warning::Facebook inaccesibil pentru {d['slug']}: {e.reason}")
            return 0   # nu e vina noastră; reîncercăm la rularea următoare
        postate[d["slug"]] = {
            "id": r.get("id", ""),
            "cand": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        print(f"Postat: {d['slug']} → {r.get('id','')}")

    if chiar:
        stare_scrie(postate)
    print(f"\nÎn coadă mai sunt {max(0, len(lista) - len(ales))} articole nepostate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

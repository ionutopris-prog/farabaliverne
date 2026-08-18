"""
Postează articolele pe pagina de Facebook „Fără Baliverne". Nu renunță.

Textul NU se inventează aici — îl ia din `build_post_queue.compune_fb()`, exact
varianta pe care fondatorul o copia manual până acum. Un singur loc unde se
scrie postarea, ca să nu ajungă cele două forme să se contrazică.

REGULA: un articol iese de pe listă DOAR când Facebook a confirmat postarea.
Orice altceva — token expirat, Facebook picat, rețea moartă, plafon de cereri —
înseamnă că rămâne în coadă și se reîncearcă. Nu se pierde nimic.

Rulează separat de ediție (`.github/workflows/facebook.yml`, la 30 de minute),
tocmai ca să meargă și când redactorul n-a publicat nimic. Dacă ar sta în
workflow-ul ediției, o zi în care redactorul dă greș ar fi și o zi în care
articolele rămase în coadă nu s-ar mai reîncerca niciodată.

Ce cere ca să funcționeze (secrete GitHub):
    FB_ENABLED     = 1            poarta. Fără ea, scriptul doar ARATĂ ce ar posta.
    FB_PAGE_ID     = <id pagină>
    FB_PAGE_TOKEN  = <token de pagină, de lungă durată>
    FB_MAX_PE_ZI   = <număr>      opțional; gol sau 0 = fără plafon

Rulare:
    python3 scripts/posteaza_facebook.py              # arată, nu postează
    python3 scripts/posteaza_facebook.py --publica    # postează (dacă FB_ENABLED=1)
    python3 scripts/posteaza_facebook.py --de-acum    # o dată, la pornire
    python3 scripts/posteaza_facebook.py --coada      # ce așteaptă și de ce
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

# Fereastra din care luăm articole. Șapte zile, nu două: un articol care dă
# greș câteva zile la rând trebuie să apuce să iasă, nu să expire în tăcere.
ZILE = 7

# Așteptarea după eșecuri repetate, în minute. Primele două reîncercări vin la
# rularea următoare (30 de minute). Apoi rărim, ca un articol pe care Facebook
# îl refuză constant să nu consume fiecare rulare. Ultima valoare se repetă la
# infinit — e plafon de AȘTEPTARE, nu de renunțare.
ASTEPTARE = [0, 0, 0, 60, 120, 240, 360]

# Câte articole încercăm cel mult într-o rulare. Fără limita asta, o eroare
# trecătoare (rate limit, Facebook picat 30 de secunde) ne punea să încercăm
# toată coada la rând — 291 de cereri într-un minut, exact felul de purtare
# pentru care Facebook îți suspendă aplicația. Măsurat pe coada reală.
MAX_INCERCARI = 3

# După atâtea eșecuri strigăm cu ::error::, ca să apară roșu în Actions. Până
# acolo sunt warning-uri: un Facebook picat zece minute nu e o urgență.
PRAG_ALARMA = 4


def acum():
    return datetime.now(timezone.utc)


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


def e_postat(v):
    """Postat = Facebook a confirmat, sau l-am sărit intenționat la pornire."""
    if v is None:
        return False
    if not isinstance(v, dict):
        return True   # format vechi, necunoscut: mai bine nu-l repostăm
    return v.get("stare") in ("postat", "sarit") or bool(v.get("id"))


def de_asteptat(v):
    """Câte minute mai are de așteptat un articol care a dat greș."""
    if not isinstance(v, dict) or not v.get("esecuri"):
        return 0
    n = int(v["esecuri"])
    pauza = ASTEPTARE[min(n, len(ASTEPTARE) - 1)]
    if pauza == 0:
        return 0
    try:
        ultima = datetime.fromisoformat(v.get("ultima", ""))
    except ValueError:
        return 0
    trecut = (acum() - ultima).total_seconds() / 60
    return max(0, int(pauza - trecut))


def candidate(postate, toate=False):
    """Articolele din fereastră pe care Facebook nu le-a confirmat încă."""
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
        if not slug or e_postat(postate.get(slug)):
            continue
        # articol real, cu pagină generată — altfel linkul ar duce în 404
        if not os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            continue
        if (d.get("date") or "") < limita:
            continue
        if not toate and de_asteptat(postate.get(slug)) > 0:
            continue   # e în pauză după eșecuri; îl luăm la rularea următoare
        out.append(d)
    # aceeași ordine ca în lista manuală: demontările primele, apoi cele noi
    out.sort(key=lambda d: (PRIORITATE.get(verdict(d)[1], 3),
                            -int((d.get("date") or "0").replace("-", "")),
                            d.get("slug", "")))
    return out


def postate_azi(postate):
    """Câte au ieșit CHIAR azi. Contorul stă în starea comisă, nu în runner."""
    azi = acum().strftime("%Y-%m-%d")
    return sum(1 for v in postate.values()
               if isinstance(v, dict) and v.get("stare") == "postat"
               and (v.get("cand") or "").startswith(azi))


def trimite(page_id, token, mesaj, link):
    date = urllib.parse.urlencode({
        "message": mesaj,
        "link": link,
        "access_token": token,
    }).encode()
    cerere = urllib.request.Request(f"{API}/{page_id}/feed", data=date)
    with urllib.request.urlopen(cerere, timeout=45) as r:
        return json.loads(r.read().decode())


def noteaza_esec(postate, slug, motiv):
    v = postate.get(slug) if isinstance(postate.get(slug), dict) else {}
    n = int(v.get("esecuri", 0)) + 1
    postate[slug] = {
        "stare": "asteapta",
        "esecuri": n,
        "ultima": acum().isoformat(timespec="seconds"),
        "motiv": motiv[:300],
    }
    return n


def arata_coada(postate):
    lista = candidate(postate, toate=True)
    if not lista:
        print("Coada e goală.")
        return
    print(f"{len(lista)} articole în coadă:\n")
    for d in lista:
        v = postate.get(d["slug"]) or {}
        pauza = de_asteptat(v)
        if v.get("esecuri"):
            stare = f"{v['esecuri']} eșecuri, " + (
                f"reîncearcă peste {pauza} min" if pauza else "gata de reîncercare")
            stare += f" — {(v.get('motiv') or '')[:80]}"
        else:
            stare = "neîncercat"
        print(f"  {d.get('date','')}  {d['slug'][:52]:<52}  {stare}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publica", action="store_true",
                    help="chiar postează; fără el, doar arată")
    ap.add_argument("--cate", type=int, default=1,
                    help="cel mult atâtea postări REUȘITE într-o rulare (implicit 1)")
    ap.add_argument("--de-acum", action="store_true", dest="de_acum",
                    help="marchează tot ce există ACUM ca tratat, fără să posteze; "
                         "de rulat o singură dată, la pornire")
    ap.add_argument("--coada", action="store_true",
                    help="arată ce așteaptă și de ce, fără să atingă nimic")
    a = ap.parse_args()

    postate = stare_citeste()

    if a.coada:
        arata_coada(postate)
        return 0

    if a.de_acum:
        n = 0
        for d in candidate(postate, toate=True):
            postate[d["slug"]] = {"stare": "sarit", "cand": "la-pornire"}
            n += 1
        stare_scrie(postate)
        print(f"Am marcat {n} articole ca deja tratate. De acum se postează doar ce apare nou.")
        return 0

    pornit = os.environ.get("FB_ENABLED", "").strip() in ("1", "true", "da")
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    chiar = a.publica and pornit and page_id and token

    if a.publica and not chiar:
        lipsa = [n for n, v in (("FB_ENABLED", pornit), ("FB_PAGE_ID", page_id),
                                ("FB_PAGE_TOKEN", token)) if not v]
        print(f"Nu postez: lipsește {', '.join(lipsa)}. Arăt doar ce-ar fi ieșit.\n")

    lista = candidate(postate)
    if not lista:
        in_pauza = len(candidate(postate, toate=True))
        if in_pauza:
            print(f"Nimic de postat acum — {in_pauza} articole sunt în pauză după eșecuri.")
        else:
            print("Nimic nou de postat.")
        return 0

    # Plafon zilnic, dacă îl vrei. Gol sau 0 = fără plafon, adică tot ce apare
    # ajunge pe pagină. E alegerea fondatorului: mai bine tot, decât o selecție
    # făcută de un scor.
    try:
        pe_zi = int(os.environ.get("FB_MAX_PE_ZI", "") or 0)
    except ValueError:
        pe_zi = 0
    tinta = max(1, a.cate)
    if chiar and pe_zi > 0:
        ramase = max(0, pe_zi - postate_azi(postate))
        if ramase == 0:
            print(f"Plafonul zilnic ({pe_zi}) e atins. Restul așteaptă mâine.")
            return 0
        tinta = min(tinta, ramase)

    if not chiar:
        for d in lista[:tinta]:
            print("─" * 70)
            print(f"[{verdict(d)[0]}]  {d['slug']}")
            print("─" * 70)
            print(compune_fb(d))
            print()
        print(f"\nÎn coadă mai sunt {max(0, len(lista) - tinta)} articole.")
        return 0

    reusite = 0
    incercari = 0
    cheie_stricata = False
    # Mergem mai departe pe listă când unul dă greș: altfel un singur articol pe
    # care Facebook îl refuză ar bloca coada la nesfârșit.
    for d in lista:
        if reusite >= tinta or incercari >= MAX_INCERCARI:
            break
        incercari += 1
        slug = d["slug"]
        try:
            r = trimite(page_id, token, compune_fb(d), f"{SITE}/a/{slug}.html")
        except urllib.error.HTTPError as e:
            corp = e.read().decode("utf-8", "replace")
            n = noteaza_esec(postate, slug, f"HTTP {e.code}: {corp}")
            stare_scrie(postate)   # scriem IMEDIAT, altfel o cădere ulterioară pierde contorul
            nivel = "error" if n >= PRAG_ALARMA else "warning"
            print(f"::{nivel}::Facebook a refuzat {slug} (eșecul {n}): {e.code} {corp[:300]}")
            # 190 = token invalid/expirat, 102 = sesiune. Nu e vina articolului;
            # următoarele ar da exact aceeași eroare, deci ne oprim aici.
            if '"code":190' in corp or '"code":102' in corp:
                cheie_stricata = True
                print("::error::Tokenul de pagină nu mai e valid. Regenerează-l și "
                      "actualizează secretul FB_PAGE_TOKEN. Articolele rămân în coadă.")
                break
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            n = noteaza_esec(postate, slug, f"retea: {e}")
            stare_scrie(postate)
            print(f"::warning::Facebook inaccesibil pentru {slug} (eșecul {n}): {e}")
            break   # rețeaua e picată pentru toate, nu doar pentru ăsta
        postate[slug] = {
            "stare": "postat",
            "id": r.get("id", ""),
            "cand": acum().isoformat(timespec="seconds"),
        }
        stare_scrie(postate)   # după FIECARE reușită, nu la final
        reusite += 1
        print(f"Postat: {slug} → {r.get('id','')}")

    ramase = len(candidate(postate, toate=True))
    print(f"\nReușite acum: {reusite}. În coadă rămân {ramase} articole "
          f"(se reîncearcă la rulările următoare).")
    # Ieșim cu 0 chiar și după eșecuri trecătoare: coada e salvată, reîncercarea
    # e garantată de cron. Roșu punem doar când chiar trebuie umblat la chei.
    return 1 if cheie_stricata else 0


if __name__ == "__main__":
    sys.exit(main())

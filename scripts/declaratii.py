"""
Recoltează TOT ce e documentat oficial despre fiecare parlamentar AUR / POT / SOS.

Ce se poate lua, și de ce astea:
  CV            (pag=0)  — biografia depusă chiar de el la Cameră
  interpelări   (pag=3)  — întrebări și interpelări: cuvintele lui, în scris, datate
  inițiative    (pag=2)  — ce a propus efectiv, nu ce a declarat că propune
  moțiuni       (pag=11) — ce a semnat

Ce NU se poate lua, și trebuie spus pe față: filmulețele, interviurile TV și
postările de pe rețele. Nu există arhivă publică a lor și nu pot fi transcrise
la scară. Deci „toate declarațiile" înseamnă aici: tot ce e în arhiva oficială a
Parlamentului — care e completă pentru ce s-a spus ACOLO, și atât.

Fiecare element păstrează linkul spre pagina oficială, ca cititorul să verifice
singur. Fără interpretare la recoltare: aici doar adunăm, verificarea vine după.

Rulare:
    python3 scripts/declaratii.py            # toți din data/_parlamentari.json
    python3 scripts/declaratii.py --limita 5 # doar primii 5 (probă)
"""

import html
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROSTER = os.path.join(ROOT, "data", "_parlamentari.json")
DIR = os.path.join(ROOT, "data", "declaratii")
CDEP = "https://www.cdep.ro"
UA = {"User-Agent": "Mozilla/5.0 (farabaliverne; contact@farabaliverne.ro)"}

PAGINI = {"cv": 0, "initiative": 2, "interpelari": 3, "motiuni": 11}
PAUZA = 0.7   # politețe față de serverul Camerei; nu-l batem la uși


def ia(url, incercari=3):
    for i in range(incercari):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=35) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if i == incercari - 1:
                return ""
            time.sleep(2 * (i + 1))
    return ""


def curata(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def _corp(s):
    """
    Doar conținutul, fără meniul și subsolul care se repetă pe toate paginile.

    Ancora e `<div class="mp-content2025">` — containerul propriu al fișei. Fără
    el, un `Legislatura 2024-prezent(.*)` prinde tot meniul lateral, iar CV-urile
    ies identice pentru toți: „Structuri parlamentare, Biroul permanent...".
    """
    i = s.find('mp-content2025')
    if i > 0:
        s = s[i:]
    m = re.search(r"(.*?)(?:Adresa postala|webmaster@cdep\.ro|footer2025)", s, re.S)
    return m.group(1) if m else s


def randuri(s):
    """Un rând de tabel = un element (o interpelare, o inițiativă...)."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", _corp(s), re.S | re.I):
        celule = [curata(td) for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        celule = [c for c in celule if c]
        if not celule:
            continue
        link = re.search(r'href=[\'"]([^\'"]+)[\'"]', tr)
        el = {"text": " · ".join(celule)[:900]}
        d = re.search(r"\b(\d{2})[-.](\d{2})[-.](\d{4})\b", el["text"])
        if d:
            el["data"] = f"{d.group(3)}-{d.group(2)}-{d.group(1)}"
        if link:
            u = html.unescape(link.group(1))
            el["url"] = u if u.startswith("http") else CDEP + u
        out.append(el)
    return out


def recolteaza(om):
    idm = om["id"]
    rez = {"nume": om["nume"], "partid": om["partid"], "camera": om["camera"],
           "fisa": om["fisa"], "id": idm}
    for eticheta, pag in PAGINI.items():
        s = ia(f"{CDEP}/ords/pls/parlam/structura2015.mp?idm={idm}&cam=2&leg=2024&pag={pag}")
        time.sleep(PAUZA)
        if not s:
            rez[eticheta] = []
            continue
        if eticheta == "cv":
            t = curata(_corp(s))
            rez["cv"] = t[:4000]
        else:
            rez[eticheta] = randuri(s)
    return rez


def main():
    if not os.path.exists(ROSTER):
        print("::error::lipsește data/_parlamentari.json — rulează întâi scripts/parlamentari.py")
        sys.exit(1)
    os.makedirs(DIR, exist_ok=True)
    oameni = json.load(open(ROSTER, encoding="utf-8"))["oameni"]
    oameni = [o for o in oameni if o["camera"] != "Senat"]   # senat.ro are altă structură

    if "--limita" in sys.argv:
        oameni = oameni[:int(sys.argv[sys.argv.index("--limita") + 1])]

    total_el = 0
    for i, om in enumerate(oameni, 1):
        cale = os.path.join(DIR, f"{om['id']}.json")
        if os.path.exists(cale):
            print(f"[{i}/{len(oameni)}] {om['nume'][:34]:<34} deja luat")
            continue
        r = recolteaza(om)
        n = sum(len(r.get(k, [])) for k in ("initiative", "interpelari", "motiuni"))
        total_el += n
        json.dump(r, open(cale, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[{i}/{len(oameni)}] {om['nume'][:34]:<34} {om['partid']:<4} "
              f"{n:>4} elemente · CV {len(r.get('cv','')):>4} car.")

    print(f"\ngata: {len(oameni)} parlamentari, {total_el} elemente noi în {DIR}")


if __name__ == "__main__":
    main()

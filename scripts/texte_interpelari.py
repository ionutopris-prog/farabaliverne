"""
Textul INTEGRAL al interpelărilor și întrebărilor — plus răspunsul ministerului.

De ce contează: pe pagina de listă nu vezi decât titlul. Ce a AFIRMAT efectiv
parlamentarul stă într-un PDF (`i<nr>.pdf`), iar răspunsul instituției în alt
PDF (`r<nr>.pdf`). Perechea asta e cel mai bun material de verificare care
există: afirmația lui și răspunsul documentat al statului, una lângă alta, ambele
oficiale și datate.

NU măsurăm cât au muncit. Numărătorile de inițiative sunt material brut, nu
rezultat publicabil — un om poate co-semna o sută de proiecte fără să fi scris
niciunul. Ce ne interesează e ce au SUSȚINUT și dacă se susține.

Rulare (cere .venv cu pypdf):
    .venv/bin/python scripts/texte_interpelari.py --limita 20
    .venv/bin/python scripts/texte_interpelari.py
"""

import glob
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURSA = os.path.join(ROOT, "data", "declaratii")
DIR = os.path.join(ROOT, "data", "texte")
CDEP = "https://www.cdep.ro"
UA = {"User-Agent": "Mozilla/5.0 (farabaliverne; contact@farabaliverne.ro)"}
PAUZA = 0.5

# „Interpelarea nr.631B/07.10.2025" / „Întrebarea nr.4891A/16.04.2026"
NR = re.compile(r"(?:Interpelarea|Întrebarea|Intrebarea)\s+nr\.?\s*(\d+[A-Z])\s*/\s*(\d{2})\.(\d{2})\.(\d{4})")


def ia_binar(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read()
    except Exception:
        return None


def pdf_text(octeti):
    import io
    import pypdf
    try:
        r = pypdf.PdfReader(io.BytesIO(octeti))
        return "\n".join(p.extract_text() or "" for p in r.pages)
    except Exception:
        return ""


def curata(t):
    # Antetul grupului se repetă pe fiecare pagină a PDF-ului; scoatem zgomotul.
    t = re.sub(r"Palatul Parlamentului[^\n]*", " ", t)
    t = re.sub(r"e-mail:\s*\S+@\S+", " ", t)
    t = re.sub(r"Grupul Parlamentar[^\n]*", " ", t)
    t = re.sub(r"\b[A-Z]/[A-Z]{2,4}/\d+/\d{2}\.\d{2}\.\d{4}\b", " ", t)
    return re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t]{2,}", " ", t)).strip()


def main():
    os.makedirs(DIR, exist_ok=True)
    lucru = []
    for f in sorted(glob.glob(os.path.join(SURSA, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for it in d.get("interpelari", []):
            m = NR.search(it["text"])
            if m:
                lucru.append((d["nume"], d["partid"], m.group(1), m.group(4), it["text"]))

    if "--limita" in sys.argv:
        lucru = lucru[:int(sys.argv[sys.argv.index("--limita") + 1])]

    print(f"de recoltat: {len(lucru)} texte\n")
    luate = cu_raspuns = 0
    for i, (nume, partid, nr, an, titlu) in enumerate(lucru, 1):
        cale = os.path.join(DIR, f"{an}-{nr}.json")
        if os.path.exists(cale):
            continue
        b = ia_binar(f"{CDEP}/interpel/{an}/i{nr}.pdf")
        time.sleep(PAUZA)
        if not b:
            continue
        txt = curata(pdf_text(b))
        if len(txt) < 120:
            continue
        rb = ia_binar(f"{CDEP}/interpel/{an}/r{nr}.pdf")
        time.sleep(PAUZA)
        rasp = curata(pdf_text(rb)) if rb else ""
        if rasp:
            cu_raspuns += 1
        json.dump({"nr": nr, "an": an, "autor": nume, "partid": partid,
                   "titlu": titlu, "text": txt, "raspuns": rasp,
                   "sursa": f"{CDEP}/interpel/{an}/i{nr}.pdf"},
                  open(cale, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        luate += 1
        if luate % 10 == 0 or i == len(lucru):
            print(f"[{i}/{len(lucru)}] luate={luate} cu răspuns={cu_raspuns}")

    print(f"\ngata: {luate} texte, din care {cu_raspuns} au și răspunsul instituției")


if __name__ == "__main__":
    main()

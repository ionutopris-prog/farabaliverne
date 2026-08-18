"""
Dă un PDF modelului local și pune-i o întrebare despre el.

De ce e nevoie de unealta asta: **niciun model nu citește PDF direct.** Ollama
primește text sau imagini. PDF-ul e doar un container — trebuie despachetat
înainte. Aici se face despachetarea, automat, în funcție de ce fel de PDF e.

Două feluri de PDF, două drumuri:

1. **PDF cu text** (aproape tot ce e generat de un calculator: legi, facturi,
   rapoarte, Monitorul Oficial). Textul e deja înăuntru, îl scoatem și îl dăm
   modelului. Rapid și ieftin.

2. **PDF scanat** (o poză a unei hârtii — nu conține niciun text). Aici textul
   nu există, deci nu are ce extrage. Dar `gemma3:12b` e multimodal: randăm
   fiecare pagină ca imagine și i-o dăm să se uite la ea. Mai lent, dar merge
   fără OCR și fără unelte externe.

Unealta decide singură pe care drum să meargă, uitându-se cât text real a găsit
pe pagină.

Rulare:
    python3 local/citeste_pdf.py fisier.pdf "Despre ce e vorba?"
    python3 local/citeste_pdf.py lege.pdf "Ce pedepse prevede?" --pagini 1-12
    python3 local/citeste_pdf.py scan.pdf "Ce scrie în tabel?" --imagini
    python3 local/citeste_pdf.py fisier.pdf --doar-text > text.txt

Cere: `pip install pymupdf` (e deja în .venv-ul proiectului).
"""

import argparse
import base64
import io
import json
import os
import sys
import urllib.request

import pymupdf

OLLAMA = "http://localhost:11434/api/generate"
MODEL = "gemma3:12b"      # multimodal — poate primi și imagini
DPI = 150                 # cât de mare randăm pagina; 150 e citibil fără să fie uriaș

# 🔴 Fără asta, Ollama folosește un context implicit de câteva mii de tokeni și
# ARUNCĂ restul în tăcere. Modelul primea un sfert de document și răspundea cu
# toată încrederea. gemma3:12b suportă 131.072, dar contextul mănâncă memorie:
# măsurat pe o mașină cu 16 GB, 32.768 merge lejer (Ollama ajunge la ~9 GB).
# Dacă ai mai multă memorie, urcă-l; dacă mașina începe să înghețe, coboară-l.
NUM_CTX = 32_768

# Cât text îi dăm modelului dintr-o dată. Peste asta, contextul se umple și
# modelul începe să uite începutul. Nu tăiem în tăcere: spunem cât am tăiat.
# ~3 caractere pe token în română (mai „scumpă" decât engleza), din care lăsăm
# loc pentru prompt și răspuns. La 32k context ies vreo 85.000 de caractere.
BUGET = 85_000

# Sub atâtea caractere pe pagină considerăm că pagina e o poză, nu text.
# O pagină de carte are 1500-3000 de caractere; una scanată întoarce 0-20
# (uneori câteva resturi din antet).
PRAG_SCANAT = 60


def pagini_cerute(spec, total):
    """„1-12" sau „3" sau gol → lista de indici (de la 0)."""
    if not spec:
        return list(range(total))
    out = set()
    for bucata in spec.split(","):
        bucata = bucata.strip()
        if "-" in bucata:
            a, b = bucata.split("-", 1)
            out.update(range(int(a) - 1, min(int(b), total)))
        elif bucata:
            out.add(int(bucata) - 1)
    return sorted(i for i in out if 0 <= i < total)


def scoate_text(doc, indici):
    bucati = []
    goale = 0
    for i in indici:
        t = doc[i].get_text().strip()
        if len(t) < PRAG_SCANAT:
            goale += 1
        if t:
            bucati.append(f"--- pagina {i + 1} ---\n{t}")
    return "\n\n".join(bucati), goale


def randeaza(doc, indici):
    """Paginile ca PNG-uri, pentru cazul în care nu există text de scos."""
    poze = []
    for i in indici:
        pix = doc[i].get_pixmap(dpi=DPI)
        poze.append(base64.b64encode(pix.tobytes("png")).decode())
    return poze


def intreaba(prompt, imagini=None, model=MODEL):
    corp = {"model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.2, "num_ctx": NUM_CTX}}
    if imagini:
        corp["images"] = imagini
    cerere = urllib.request.Request(
        OLLAMA, data=json.dumps(corp).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(cerere, timeout=900) as r:
        return json.loads(r.read().decode()).get("response", "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("intrebare", nargs="?", default="Rezumă documentul în românește.")
    ap.add_argument("--pagini", default="", help="ex: 1-12 sau 3,5,9 (implicit: toate)")
    ap.add_argument("--imagini", action="store_true",
                    help="forțează drumul cu imagini, chiar dacă există text")
    ap.add_argument("--doar-text", action="store_true",
                    help="scoate doar textul, nu întreabă modelul")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()

    if not os.path.exists(a.pdf):
        print(f"Nu găsesc {a.pdf}", file=sys.stderr)
        return 1

    doc = pymupdf.open(a.pdf)
    indici = pagini_cerute(a.pagini, doc.page_count)
    if not indici:
        print("Intervalul de pagini nu selectează nimic.", file=sys.stderr)
        return 1

    text, goale = scoate_text(doc, indici)
    scanat = goale > len(indici) * 0.6      # peste 60% pagini fără text = scanat

    if a.doar_text:
        print(text)
        if scanat:
            print(f"\n[{goale} din {len(indici)} pagini n-au text — PDF-ul pare "
                  f"scanat. Folosește --imagini.]", file=sys.stderr)
        return 0

    if a.imagini or scanat:
        motiv = ("ai cerut-o" if a.imagini else
                 f"{goale} din {len(indici)} pagini n-au text — pare scanat")
        print(f"[drumul cu imagini: {motiv}. Randez {len(indici)} pagini la {DPI} DPI, "
              f"durează.]", file=sys.stderr)
        poze = randeaza(doc, indici)
        prompt = (f"Ești un asistent care citește documente în românește.\n"
                  f"Mai jos sunt {len(poze)} pagini dintr-un document, ca imagini.\n\n"
                  f"Întrebarea: {a.intrebare}\n\n"
                  f"Răspunde în românește. Dacă ceva nu se distinge clar în imagine, "
                  f"spune că nu se distinge — nu ghici.")
        print(intreaba(prompt, imagini=poze, model=a.model))
        return 0

    taiat = 0
    if len(text) > BUGET:
        taiat = len(text) - BUGET
        text = text[:BUGET]
        print(f"[Documentul are {taiat + BUGET} caractere; îi dau primele {BUGET}. "
              f"Am tăiat {taiat}. Folosește --pagini ca să alegi tu ce citește.]",
              file=sys.stderr)

    prompt = (f"Ești un asistent care citește documente în românește.\n\n"
              f"=== DOCUMENT ===\n{text}\n=== SFÂRȘIT DOCUMENT ===\n\n"
              f"Întrebarea: {a.intrebare}\n\n"
              f"Răspunde în românește, pe baza documentului. Dacă răspunsul nu e în "
              f"document, spune asta explicit — nu completa din memorie."
              + (f"\n\nAtenție: ai primit doar o parte din document ({taiat} caractere "
                 f"lipsesc de la final)." if taiat else ""))
    print(intreaba(prompt, model=a.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())

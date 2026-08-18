"""
Biblioteca modelului local: îi dai documente o dată, le ține minte pentru totdeauna.

═══ Ce înseamnă, de fapt, „să învețe" ═══

Un model NU învață din conversație. Când închizi fereastra, uită tot. Iar
antrenarea lui pe date noi (fine-tuning) cere plăci video, zile de calcul și
mii de exemple — nu e ce vrei tu acum.

Ce se poate, și e aproape la fel de bun în practică: **îi dai o bibliotecă**.
Tu îi bagi documente înăuntru; ele rămân acolo pe disc. Când îl întrebi ceva,
căutăm întâi în bibliotecă bucățile care au legătură cu întrebarea și i le
punem în față, apoi îl lăsăm să răspundă.

Efectul din afară e că „a citit tot și ține minte". Modelul nu devine mai
deștept — dar nu mai răspunde din burtă, ci din ce i-ai dat, și îți spune din
ce document a luat fiecare lucru.

Se numește RAG. Rezolvă și problema „să citească tot": nu-i mai îndesăm o mie
de pagini în cap deodată (nici nu încap), ci îi dăm exact paginile care contează
pentru întrebarea pusă. O bibliotecă de mii de pagini merge la fel de bine ca una
de zece.

═══ Cum se folosește ═══

    python3 local/biblioteca.py adauga document.pdf raport.pdf notite.md
    python3 local/biblioteca.py adauga ~/Documents/dosar/        (tot folderul)
    python3 local/biblioteca.py intreaba "Ce pedepse prevede legea?"
    python3 local/biblioteca.py lista
    python3 local/biblioteca.py uita document.pdf

Citește PDF, TXT, MD și HTML. Pentru PDF-urile scanate (fără text) folosește
`citeste_pdf.py --imagini` — acolo trebuie ochi, nu căutare.

Totul stă local, pe discul tău. Nimic nu pleacă nicăieri.
"""

import argparse
import glob
import html
import json
import math
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "local", "biblioteca")
INDEX = os.path.join(DIR, "index.jsonl")

OLLAMA = "http://localhost:11434"
MODEL_EMB = "nomic-embed-text"    # 768 dimensiuni, rapid, rulează pe CPU
MODEL_RASPUNS = "gemma3:12b"
NUM_CTX = 32_768                  # vezi nota din citeste_pdf.py — fără el, Ollama taie în tăcere

BUCATA = 1200      # caractere per bucată; cât un paragraf lung
SUPRAPUNERE = 200  # ca o frază tăiată la mijloc să apară întreagă într-una din bucăți
VECINI = 8         # câte bucăți îi punem în față la fiecare întrebare
LOT = 32           # câte bucăți embeddăm dintr-o cerere


# ───────────────────────── citire documente ─────────────────────────

def text_din(cale):
    """Întoarce [(pagina, text)]. Pagina e 0 pentru fișierele fără pagini."""
    ext = os.path.splitext(cale)[1].lower()
    if ext == ".pdf":
        import pymupdf
        doc = pymupdf.open(cale)
        out = [(i + 1, doc[i].get_text().strip()) for i in range(doc.page_count)]
        return [(p, t) for p, t in out if t]
    if ext in (".html", ".htm"):
        brut = open(cale, encoding="utf-8", errors="replace").read()
        brut = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", brut, flags=re.S | re.I)
        brut = re.sub(r"<[^>]+>", " ", brut)
        return [(0, re.sub(r"\s+", " ", html.unescape(brut)).strip())]
    if ext in (".txt", ".md", ".json", ".jsonl", ".csv"):
        return [(0, open(cale, encoding="utf-8", errors="replace").read())]
    return []


def taie(text, pagina, doc):
    """Bucăți cu suprapunere, tăiate pe cât posibil la sfârșit de frază."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        sfarsit = min(i + BUCATA, n)
        if sfarsit < n:
            # dăm înapoi până la ultimul punct, ca să nu rupem o frază
            felie = text[i:sfarsit]
            taietura = max(felie.rfind(". "), felie.rfind(".\n"), felie.rfind("\n\n"))
            if taietura > BUCATA * 0.5:
                sfarsit = i + taietura + 1
        felie = text[i:sfarsit].strip()
        if len(felie) > 80:      # bucățile foarte scurte nu ajută la nimic
            out.append({"doc": doc, "pagina": pagina, "text": felie})
        if sfarsit >= n:
            break
        # Avansul se calculează din POZIȚIA consumată, nu din lungimea feliei
        # după strip. Varianta greșită avansa cu 1 caracter când felia era mai
        # scurtă decât suprapunerea: un PDF de două pagini scotea 129 de bucăți
        # în loc de 2, iar biblioteca s-ar fi umflat de douăzeci de ori.
        i = max(i + 1, sfarsit - SUPRAPUNERE)
    return out


# ───────────────────────── vectori ─────────────────────────

def _post(cale, corp, timeout=600):
    cerere = urllib.request.Request(
        OLLAMA + cale, data=json.dumps(corp).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(cerere, timeout=timeout) as r:
        return json.loads(r.read().decode())


def vectori(texte):
    """Embeddings, normalizate — ca asemănarea să fie o simplă înmulțire."""
    out = []
    for i in range(0, len(texte), LOT):
        lot = texte[i:i + LOT]
        r = _post("/api/embed", {"model": MODEL_EMB, "input": lot})
        for v in r.get("embeddings", []):
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
    return out


def asemanare(a, b):
    return sum(x * y for x, y in zip(a, b))


# ───────────────────────── biblioteca ─────────────────────────

def citeste_index():
    if not os.path.exists(INDEX):
        return []
    with open(INDEX, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def scrie_index(intrari):
    os.makedirs(DIR, exist_ok=True)
    with open(INDEX, "w", encoding="utf-8") as f:
        for x in intrari:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


def desfa(caile):
    """Fișiere din argumente, cu foldere desfăcute recursiv."""
    out = []
    for c in caile:
        c = os.path.expanduser(c)
        if os.path.isdir(c):
            for ext in ("pdf", "txt", "md", "html", "htm"):
                out += glob.glob(os.path.join(c, "**", f"*.{ext}"), recursive=True)
        elif os.path.exists(c):
            out.append(c)
        else:
            print(f"  ! nu găsesc {c}", file=sys.stderr)
    return sorted(set(out))


def adauga(caile):
    index = citeste_index()
    deja = {x["doc"] for x in index}
    fisiere = desfa(caile)
    if not fisiere:
        print("Niciun fișier de adăugat.")
        return 1

    noi_total = 0
    for cale in fisiere:
        nume = os.path.basename(cale)
        if nume in deja:
            print(f"  = {nume} — e deja în bibliotecă (scoate-l cu „uita” dacă s-a schimbat)")
            continue
        try:
            pagini = text_din(cale)
        except Exception as e:
            print(f"  ! {nume}: {type(e).__name__}: {e}")
            continue
        if not pagini:
            print(f"  ! {nume}: n-am scos niciun text. Dacă e PDF scanat, "
                  f"foloseşte citeste_pdf.py --imagini")
            continue

        bucati = []
        for pag, t in pagini:
            bucati += taie(t, pag, nume)
        if not bucati:
            print(f"  ! {nume}: prea puțin text")
            continue

        print(f"  + {nume}: {len(pagini)} pagini → {len(bucati)} bucăți, calculez vectorii…")
        vecs = vectori([b["text"] for b in bucati])
        if len(vecs) != len(bucati):
            print(f"  ! {nume}: am primit {len(vecs)} vectori pentru {len(bucati)} bucăți — sar")
            continue
        for b, v in zip(bucati, vecs):
            b["vec"] = v
        index += bucati
        noi_total += len(bucati)

    scrie_index(index)
    print(f"\nBiblioteca are acum {len(index)} bucăți din "
          f"{len({x['doc'] for x in index})} documente (+{noi_total} acum).")
    return 0


def lista():
    index = citeste_index()
    if not index:
        print("Biblioteca e goală. Adaugă ceva cu „adauga”.")
        return 0
    dupa_doc = {}
    for x in index:
        dupa_doc.setdefault(x["doc"], 0)
        dupa_doc[x["doc"]] += 1
    print(f"{len(dupa_doc)} documente, {len(index)} bucăți:\n")
    for d, n in sorted(dupa_doc.items()):
        print(f"  {n:>5} bucăți  {d}")
    return 0


def uita(nume):
    index = citeste_index()
    ramase = [x for x in index if x["doc"] != nume and x["doc"] != os.path.basename(nume)]
    sterse = len(index) - len(ramase)
    if not sterse:
        print(f"Nu găsesc „{nume}” în bibliotecă.")
        return 1
    scrie_index(ramase)
    print(f"Am scos {sterse} bucăți din „{nume}”.")
    return 0


def intreaba(intrebare, k=VECINI, model=MODEL_RASPUNS, arata=False):
    index = citeste_index()
    if not index:
        print("Biblioteca e goală — n-am din ce răspunde. Adaugă documente întâi.")
        return 1

    qv = vectori([intrebare])[0]
    scoruri = sorted(((asemanare(qv, x["vec"]), x) for x in index),
                     key=lambda t: t[0], reverse=True)[:k]

    bucati = []
    for s, x in scoruri:
        unde = f"{x['doc']}" + (f", pagina {x['pagina']}" if x["pagina"] else "")
        bucati.append(f"[{unde}]\n{x['text']}")
        if arata:
            print(f"  {s:.3f}  {unde}", file=sys.stderr)

    context = "\n\n".join(bucati)
    prompt = (
        "Ești un asistent care răspunde STRICT pe baza fragmentelor de mai jos, "
        "extrase din biblioteca de documente a utilizatorului.\n\n"
        f"=== FRAGMENTE ===\n{context}\n=== SFÂRȘIT FRAGMENTE ===\n\n"
        f"Întrebarea: {intrebare}\n\n"
        "Reguli:\n"
        "- Răspunde în românește.\n"
        "- Foloseşte DOAR ce scrie în fragmente. Nu completa din memorie.\n"
        "- Dacă fragmentele nu conțin răspunsul, spune exact asta: „Nu găsesc "
        "răspunsul în documentele pe care mi le-ai dat.” Nu inventa.\n"
        "- La fiecare afirmație, spune din ce document ai luat-o, în paranteză.")

    r = _post("/api/generate", {"model": model, "prompt": prompt, "stream": False,
                                "options": {"temperature": 0.2, "num_ctx": NUM_CTX}},
              timeout=900)
    print(r.get("response", "").strip())
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("═══")[0].strip())
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("adauga", help="bagă documente în bibliotecă")
    p.add_argument("caile", nargs="+")

    p = sub.add_parser("intreaba", help="întreabă din ce e în bibliotecă")
    p.add_argument("intrebare")
    p.add_argument("--bucati", type=int, default=VECINI,
                   help=f"câte fragmente îi punem în față (implicit {VECINI})")
    p.add_argument("--arata", action="store_true",
                   help="arată ce fragmente a folosit și cât de bine se potrivesc")
    p.add_argument("--model", default=MODEL_RASPUNS)

    sub.add_parser("lista", help="ce documente sunt înăuntru")
    p = sub.add_parser("uita", help="scoate un document din bibliotecă")
    p.add_argument("nume")

    a = ap.parse_args()
    if a.cmd == "adauga":
        return adauga(a.caile)
    if a.cmd == "intreaba":
        return intreaba(a.intrebare, a.bucati, a.model, a.arata)
    if a.cmd == "lista":
        return lista()
    if a.cmd == "uita":
        return uita(a.nume)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

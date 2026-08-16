"""
Redactorul local: dă-i un subiect și niște surse, îți propune un articol.

Rulează pe Mac, prin Ollama. Nu publică nimic și nu atinge site-ul — scrie în
`local/propuneri/`, ca să te uiți tu. Bucla e: rulezi, citești, păstrezi sau
retușezi promptul, rulezi iar. Așa se învață, nu dintr-o singură reglare.

Ce face modelul local: scrie în vocea casei, structurează, formulează dek-ul și
verdictul.
Ce NU face: nu caută pe internet, nu decide dacă o sursă e credibilă, nu
verifică adversarial. Alea rămân la modelul din cloud sau la tine. Un model de
12B pe Mac e bun la formă, nu la cercetare — și e mai cinstit s-o spunem decât
s-o aflăm dintr-un articol greșit.

Folosire:
    python3 local/scrie.py "Subiectul articolului" sursa1.md
    python3 local/scrie.py --din-fisier brief.txt
    python3 local/scrie.py "Subiect" --exemple 3      # câte exemple din corpus
"""

import json
import os
import random
import subprocess
import sys
import unicodedata
import re

AICI = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(AICI, "corpus.jsonl")
PROPUNERI = os.path.join(AICI, "propuneri")
MODEL = os.environ.get("MODEL_REDACTOR", "redactor")
EXEMPLE_IMPLICIT = 2


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "propunere"


def exemple(n):
    """
    Few-shot din articolele publicate. Alegem exemple SCURTE: intră mai multe în
    context și tiparul se vede la fel de bine ca într-unul lung.
    """
    if not os.path.exists(CORPUS):
        print("::warning:: lipsește local/corpus.jsonl — rulează scripts/corpus_local.py")
        return []
    linii = [json.loads(l) for l in open(CORPUS, encoding="utf-8") if l.strip()]
    linii = [x for x in linii if len(json.dumps(x, ensure_ascii=False)) < 4500]
    random.shuffle(linii)
    return linii[:n]


def prompt(subiect, material, n_ex):
    p = ["Scrie articolul pentru subiectul de mai jos, în structura casei.",
         "Folosește DOAR ce e în material. Nu inventa surse, cifre sau citate.",
         ""]
    for ex in exemple(n_ex):
        p.append("EXEMPLU DE ARTICOL PUBLICAT:")
        p.append("intrare: " + json.dumps(ex["intrare"], ensure_ascii=False))
        p.append("ieșire: " + json.dumps(ex["iesire"], ensure_ascii=False))
        p.append("")
    p.append("ACUM SCRIE TU.")
    p.append(f"SUBIECT: {subiect}")
    p.append("MATERIAL ȘI SURSE:")
    p.append(material.strip() or "(nu s-a dat material — spune asta în aiNote)")
    p.append("")
    p.append("Întoarce DOAR obiectul JSON, fără text în jur.")
    return "\n".join(p)


def curata_json(t):
    """Modelele mai pun ```json în jur; scoatem gardul înainte de parse."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip(), flags=re.M)
    i, j = t.find("{"), t.rfind("}")
    return t[i:j + 1] if i >= 0 and j > i else t


def main():
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    n_ex = EXEMPLE_IMPLICIT
    if "--exemple" in sys.argv:
        n_ex = int(sys.argv[sys.argv.index("--exemple") + 1])

    if "--din-fisier" in sys.argv:
        cale = sys.argv[sys.argv.index("--din-fisier") + 1]
        brief = open(cale, encoding="utf-8").read()
        subiect = brief.strip().splitlines()[0][:200]
        material = brief
    else:
        if not arg:
            print(__doc__)
            sys.exit(1)
        subiect = arg[0]
        material = ""
        for f in arg[1:]:
            if os.path.exists(f):
                material += open(f, encoding="utf-8").read() + "\n\n"
            else:
                material += f + "\n"

    os.makedirs(PROPUNERI, exist_ok=True)
    print(f"model: {MODEL} · exemple din corpus: {n_ex}")
    print("scrie… (prima rulare încarcă modelul, poate dura un minut)\n")

    # API-ul HTTP, nu `ollama run`: comanda din terminal își desenează progresul
    # cu coduri ANSI (\x1b[3D\x1b[K) care ajung în ieșire și strică JSON-ul.
    # În plus, aici putem cere format=json, deci modelul e obligat să întoarcă
    # un obiect valid — nu mai depindem de noroc și de scos gardul de ```.
    import urllib.request
    cerere = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": MODEL, "prompt": prompt(subiect, material, n_ex),
                         "stream": False, "format": "json"}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(cerere, timeout=600) as r:
            brut = json.loads(r.read().decode())["response"].strip()
    except Exception as e:
        print(f"::error:: Ollama nu răspunde ({type(e).__name__}). "
              f"Pornit? Încearcă: ollama serve")
        sys.exit(1)
    cale = os.path.join(PROPUNERI, slug(subiect) + ".json")
    try:
        d = json.loads(curata_json(brut))
        json.dump(d, open(cale, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"✅ {cale}\n")
        print(f"   titlu:   {d.get('title','—')}")
        print(f"   verdict: {d.get('mainVerdict','—')}")
        print(f"   probate: {len(d.get('probat') or [])} · "
              f"contestate: {len(d.get('contestat') or [])} · "
              f"opinii: {len(d.get('opinie') or [])}")
        surse = sum(len(p.get("sources") or []) for k in ("probat", "contestat")
                    for p in d.get(k) or [])
        print(f"   surse:   {surse}")
        if not surse:
            print("\n   ⚠️  Zero surse. Fără sursă nu se publică — asta e regula casei.")
    except Exception as e:
        cale = cale.replace(".json", ".txt")
        open(cale, "w", encoding="utf-8").write(brut)
        print(f"⚠️  n-a ieșit JSON valid ({type(e).__name__}); text brut în {cale}")


if __name__ == "__main__":
    main()

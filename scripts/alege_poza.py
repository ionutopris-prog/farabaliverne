"""
Alege poza uitându-se la ea, nu ghicind din titlul fișierului.

De ce există: varianta „ia primul candidat, verifică după ce l-ai pus" a dat,
măsurat pe 38 de articole, 19 poze nepotrivite — jumătate. Printre ele,
parlamentul Republicii Moldova pus pe trei articole românești și un bărbat
necunoscut pus drept Nicușor Dan, de două ori. Toate au fost prinse la
verificarea vizuală și scoase, dar munca era deja făcută degeaba.

Aici ordinea e inversată: strângem mai mulți candidați, îi arătăm pe toți
odată, iar AI-ul alege care se potrivește — sau spune că niciunul nu merge.
„Niciunul" e un răspuns bun: cardul de brand e mai onest decât o poză care
induce în eroare.

Scrie `preview/propuneri.json`, exact formatul pe care îl citește
`apply_images.py`. Nu atinge niciun articol.

Rulare:
    python3 scripts/alege_poza.py --fara-poza          # toate cele fără poză
    python3 scripts/alege_poza.py <slug> [<slug>...]   # doar astea
    python3 scripts/alege_poza.py --fara-poza --cate 20
"""

import concurrent.futures
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batch_images as B  # noqa: E402
import pick_image as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview", "propuneri.json")
TMP = os.path.join(ROOT, "preview", "candidati")

MODEL = "sonnet"       # destul pentru „care poză se potriveşte"; cota rămâne redactorului
CANDIDATI = 5          # câţi îi arătăm deodată
DEODATA = 3            # câte articole în paralel
RABDARE = 240

PROMPT = """Ești redactorul foto al unui site de fact-checking în limba română.

Articolul se numește: «{titlu}»
{dek}

Ai mai jos {n} fotografii candidate. Citește fiecare fișier:
{lista}

Alege UNA care ilustrează onest subiectul articolului, sau niciuna.

Poza apare sub eticheta «Foto ilustrativă»: NU trebuie să fie de la
evenimentul relatat. Are voie să fie generică — clădirea unei instituții, un
oraș, un stadion, un tip de echipament, o situație de acelaşi fel.

Respinge o poză dacă: arată altă țară decât cea din articol, altă persoană
decât cea numită în titlu, alt tip de obiect, sau dacă nu e fotografie
(drapel, siglă, hartă, grafic, desen).

Dacă niciuna nu se potrivește, răspunde 0. Un card grafic e mult mai bun
decât o poză care induce cititorul în eroare — nu forța o alegere.

Răspunde EXACT o singură linie:
NUMĂR | motiv scurt

unde NUMĂR e 1..{n} sau 0."""


def candidati(art):
    """Până la CANDIDATI poze, strânse din toate interogările articolului."""
    context = (art.get("title", "") + " " + art.get("dek", "")).lower()
    out, vazute = [], set()
    for q, tip in B.interogari(art):
        try:
            gasit = P.search_tot(q, context, limit=8,
                                 nume_persoana=q if tip == "persoană" else None,
                                 strict=False)
        except Exception:
            continue
        for c in gasit:
            if c["url"] in vazute:
                continue
            vazute.add(c["url"])
            c = dict(c)
            c["_query"] = q
            c["_tip"] = tip
            out.append(c)
            if len(out) >= CANDIDATI:
                return out
    return out


def descarca(c, dest):
    cerere = urllib.request.Request(c["url"], headers={"User-Agent": P.UA})
    with urllib.request.urlopen(cerere, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


def alege(art, cands, folder):
    fisiere = []
    for i, c in enumerate(cands, 1):
        cale = os.path.join(folder, f"{i}.jpg")
        try:
            descarca(c, cale)
        except Exception:
            continue
        fisiere.append((i, cale, c))
    if not fisiere:
        return None, "niciun candidat descărcabil"

    lista = "\n".join(f"  {i}. {cale}" for i, cale, _ in fisiere)
    prompt = PROMPT.format(titlu=art.get("title", ""),
                           dek=(art.get("dek") or "")[:300],
                           n=len(fisiere), lista=lista)
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", MODEL,
                            "--allowedTools", "Read"],
                           capture_output=True, text=True,
                           timeout=RABDARE, cwd=ROOT)
        linie = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
    except Exception as e:
        return None, f"alegerea n-a putut rula ({type(e).__name__})"

    m = re.match(r"\s*(\d+)", linie)
    if not m:
        return None, f"răspuns neînțeles: {linie[:70]}"
    nr = int(m.group(1))
    motiv = linie.split("|", 1)[1].strip() if "|" in linie else ""
    if nr == 0:
        return None, motiv or "niciuna nu se potrivește"
    for i, _, c in fisiere:
        if i == nr:
            return c, motiv
    return None, f"a ales {nr}, care nu există"


def trateaza(slug):
    dpath = os.path.join(ROOT, "data", slug + ".json")
    if not os.path.exists(dpath):
        return {"slug": slug, "photo": None, "motiv": "fără fișier în data/"}
    art = json.load(open(dpath, encoding="utf-8"))

    cands = candidati(art)
    if not cands:
        return {"slug": slug, "title": art.get("title", ""),
                "category": art.get("category", ""), "query": None,
                "query_type": None, "photo": None, "motiv": "niciun candidat găsit"}

    folder = os.path.join(TMP, slug)
    os.makedirs(folder, exist_ok=True)
    ales, motiv = alege(art, cands, folder)
    return {"slug": slug, "title": art.get("title", ""),
            "category": art.get("category", ""),
            "query": ales["_query"] if ales else None,
            "query_type": ales["_tip"] if ales else None,
            "photo": ales, "motiv": motiv}


def main():
    arg = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--fara-poza" in sys.argv:
        sluguri = sorted(B.fara_poza())
    else:
        sluguri = [a for a in arg if not a.isdigit()]
    if "--cate" in sys.argv:
        n = int(sys.argv[sys.argv.index("--cate") + 1])
        sluguri = sluguri[:n]
    if not sluguri:
        print(__doc__)
        return 1

    print(f"{len(sluguri)} articole, până la {CANDIDATI} candidați fiecare\n")
    rezultate = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEODATA) as ex:
        for i, r in enumerate(ex.map(trateaza, sluguri), 1):
            rezultate.append(r)
            marca = "OK " if r["photo"] else "—  "
            print(f"  [{i:3}/{len(sluguri)}] {marca} {r['slug'][:46]:46} "
                  f"{(r.get('motiv') or '')[:60]}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rezultate, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    gasite = sum(1 for r in rezultate if r["photo"])
    print(f"\n{gasite}/{len(rezultate)} au o poză aleasă · scris: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

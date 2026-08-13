"""
Se uită la fotografii și spune dacă se potrivesc cu articolul.

`verify_images.py` verifică ce e măsurabil: hotlink, atribuire, greutate. Toate
greșelile care au ajuns pe site au trecut de el fără o vorbă — drapelul Turciei
pe patru articole despre Ucraina, Kievul sub o știre despre Dnipro, obuze cu
iperită sub o uzină convențională de muniție. Nimic din ele nu se vede din
metadate.

Am încercat întâi varianta ieftină: să cer ca numele fișierului de pe Commons
să aibă un cuvânt comun cu ce am căutat. Măsurat pe 82 de poze reale, marca 13,
din care ~11 erau bune — „National Bank of Romania" venise ca
`Banco_Nacional_de_Rumanía`, „Ambulanță" ca `AMBULANCE_IN_ROMENIA`. Numele de
pe Commons sunt în zeci de limbi sau sunt coduri de arhivă. O alarmă care sună
degeaba se învață să fie ignorată, deci regula a fost aruncată.

Rămâne singurul lucru care chiar prinde clasa asta de greșeli: cineva se uită
la poză. Folosește abonamentul Max, la fel ca redactorul — consumă din cotă,
nu bani.

Folosire:
    python3 scripts/verifica_poza.py <slug> [<slug>...]
    python3 scripts/verifica_poza.py --noi          # pozele din ultimul commit
    python3 scripts/verifica_poza.py --toate        # tot ce e publicat
    python3 scripts/verifica_poza.py --noi --repara # scoate pozele nepotrivite
"""

import concurrent.futures
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Sonnet e destul pentru „se potrivește poza asta cu titlul ăsta" și lasă cota
# pentru redactor, care are nevoie de ea la cercetare.
MODEL = "sonnet"
DEODATA = 4          # câte poze verificăm în paralel
RABDARE = 180        # secunde per poză


def _cere(slug):
    """Titlul și rezumatul articolului, plus calea pozei proprii."""
    dpath = os.path.join(ROOT, "data", slug + ".json")
    apath = os.path.join(ROOT, "a", slug + ".html")
    if not (os.path.exists(dpath) and os.path.exists(apath)):
        return None
    html = open(apath, encoding="utf-8").read()
    m = re.search(r'<img src="\.\./img/articole/([^"]+)"', html)
    if not m:
        return None
    poza = os.path.join(ROOT, "img", "articole", m.group(1))
    if not os.path.exists(poza):
        return None
    d = json.load(open(dpath, encoding="utf-8"))
    return {"slug": slug, "poza": poza,
            "titlu": d.get("title", ""), "dek": d.get("dek", "")}


PROMPT = """Ești verificatorul de fotografii al unui site de fact-checking.

Citește fișierul {poza}

Articolul se numește: «{titlu}»
{dek}

Poza apare sub eticheta «Foto ilustrativă» — NU trebuie să fie de la
evenimentul relatat, și are voie să fie generică (o clădire a instituției, un
oraș, un stadion, un tip de echipament). Trebuie doar să ilustreze ONEST
subiectul.

Răspunde EXACT o singură linie, în formatul:
VERDICT | motiv scurt

VERDICT poate fi doar: POTRIVIT, NEPOTRIVIT sau NESIGUR.

Pune NEPOTRIVIT doar dacă un cititor ar fi indus în eroare: altă țară, alt
oraș, altă persoană, alt tip de obiect decât cel din articol, sau dacă nu e
deloc o fotografie (drapel, siglă, hartă, desen). Pune NESIGUR dacă nu poți
stabili ce arată poza. În rest, POTRIVIT."""


def verifica_una(art):
    prompt = PROMPT.format(poza=art["poza"], titlu=art["titlu"],
                           dek=(art["dek"] or "")[:300])
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--model", MODEL,
             "--allowedTools", "Read"],
            capture_output=True, text=True, timeout=RABDARE, cwd=ROOT)
        linie = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
    except Exception as e:
        linie = f"NESIGUR | verificarea n-a putut rula ({type(e).__name__})"

    m = re.search(r"\b(POTRIVIT|NEPOTRIVIT|NESIGUR)\b", linie)
    verdict = m.group(1) if m else "NESIGUR"
    motiv = linie.split("|", 1)[1].strip() if "|" in linie else linie.strip()
    return {"slug": art["slug"], "verdict": verdict,
            "motiv": motiv or "fără motiv dat",
            "poza": os.path.basename(art["poza"])}


def sluguri_noi(de_la="HEAD~1"):
    """
    Articolele ale căror poze s-au schimbat de la un punct încoace.

    În ediție, `de_la` e commitul de dinaintea redactorului, nu `HEAD~1`:
    redactorul face mai multe commituri, așa că „ultimul commit" ar rata
    aproape toate pozele noi.
    """
    r = subprocess.run(["git", "diff", "--name-only", de_la, "HEAD"],
                       capture_output=True, text=True, cwd=ROOT)
    sluguri = set()
    for f in r.stdout.splitlines():
        m = re.match(r"img/articole/(.+)\.[a-zA-Z]+$", f.strip())
        if m:
            sluguri.add(m.group(1))
    return sorted(sluguri)


def main():
    repara = "--repara" in sys.argv
    argumente = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--toate" in sys.argv:
        sluguri = sorted(os.path.basename(p)[:-5]
                         for p in glob.glob(os.path.join(ROOT, "a", "*.html")))
    elif "--noi" in sys.argv:
        sluguri = sluguri_noi(os.environ.get("DE_LA") or "HEAD~1")
    else:
        sluguri = argumente

    articole = [a for a in (_cere(s) for s in sluguri) if a]
    if not articole:
        print("nicio poză proprie de verificat")
        return

    print(f"mă uit la {len(articole)} poze...\n")
    rele = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEODATA) as tp:
        for rez in tp.map(verifica_una, articole):
            semn = {"POTRIVIT": "  ok", "NESIGUR": "  ?", "NEPOTRIVIT": "  ✗"}[rez["verdict"]]
            print(f"{semn} {rez['slug']}")
            if rez["verdict"] != "POTRIVIT":
                print(f"      {rez['motiv']}")
            if rez["verdict"] == "NEPOTRIVIT":
                rele.append(rez)

    if not rele:
        print(f"\ntoate cele {len(articole)} se potrivesc")
        return

    print(f"\n{len(rele)} poze nepotrivite:")
    for r in rele:
        print(f"::warning::{r['slug']}: {r['motiv']}")

    if not repara:
        return

    # Scoatem poza, rămâne cardul de brand. NU blocăm publicarea: o poză
    # greșită e o problemă de credibilitate, dar un site care nu mai publică
    # deloc e mai rău — asta ne-a costat 18 ore pe 12 august.
    for r in rele:
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "replace_image.py"),
                        r["slug"], "--scoate"], cwd=ROOT)


if __name__ == "__main__":
    main()

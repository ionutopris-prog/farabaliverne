#!/usr/bin/env python3
"""
Chat cu redactorul Fără Baliverne — vorbești cu arhiva, nu cu un model gol.

Modelul rulează LOCAL, pe MLX (motorul Apple), prin serverul din `mlx-lab`.
Zero cloud, zero tokeni de abonament, zero costuri.

Ce știe:
  • toate articolele publicate (data/*.json) — le caută semantic, nu după cuvinte
  • regulile casei: principiul roșu, regula cuvintelor, fapt ≠ opinie
  • ce s-a scris despre o persoană, ce s-a acoperit deja dintr-un subiect

🔴 NU PUBLICĂ NIMIC. Ciornele se scriu în `data/_ciorna-<slug>.json`, iar
`build_site.py` sare peste tot ce începe cu „_". Nu comite, nu urcă, nu
declanșează deploy. Ca să ajungă pe site, un articol trebuie mutat de mână,
după ce i-ai citit sursele. Regula fondatorului, 27 august.

Comenzi:
  /caut <text>        articolele cele mai apropiate de text
  /despre <nume>      ce am scris despre o persoană
  /subiect <titlu>    am mai scris asta? (rulează seamana.py)
  /azi                ce s-a publicat azi
  /scrie <subiect>    ciornă de articol, scrisă de modelul local
  /invata <slug>      păstrează ce ai corectat, ca material de antrenare
  /model              ce model e la manetă
  /reindex            reface indexul (după ce apar articole noi)
  gata                ieși

Rulare:  ./redactor
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
LAB = Path(os.environ.get("MLX_LAB", Path.home() / "Projects" / "mlx-lab"))
INDEX = ROOT / "data" / "_index_chat.jsonl"      # „_" = build_site.py îl ignoră

URL_MODEL = "http://127.0.0.1:8899/v1/chat/completions"
URL_VECTORI = "http://127.0.0.1:8898/embed"

# 🔴 Se schimbă AICI, într-un singur loc, când vine mini-ul cu 32 GB:
#   12B  ≈ 8 GB  — încape pe Air-ul de 16 GB
#   27B  ≈ 17 GB — NU încape pe 16 GB; merge de la 32 GB în sus
MODEL = os.environ.get("MODEL_CHAT", "mlx-community/gemma-3-12b-it-4bit")
MODEL_MARE = "mlx-community/gemma-3-27b-it-4bit"

CATE_ARTICOLE = 6      # câte articole din arhivă intră în prompt


# ─── temelia: serverele din mlx-lab ────────────────────────────────────────
def _post(url, corp, timeout=900):
    cerere = urllib.request.Request(url, data=json.dumps(corp).encode(),
                                    headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(cerere, timeout=timeout) as r:
        return json.load(r)


def _sus(url_test, lansator, rabdare=120):
    """Ridică un server din mlx-lab dacă nu răspunde."""
    try:
        urllib.request.urlopen(url_test, timeout=2)
        return True
    except Exception:
        pass
    cale = LAB / lansator
    if not cale.exists():
        return False
    subprocess.Popen([str(cale)], cwd=str(LAB), stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    plecare = time.time()
    while time.time() - plecare < rabdare:
        try:
            urllib.request.urlopen(url_test, timeout=2)
            return True
        except Exception:
            time.sleep(2)
    return False


def vector(text, rol="document"):
    if not _sus("http://127.0.0.1:8898/sanatate", "vectori"):
        sys.exit("Nu pornește serverul de vectori din mlx-lab.")
    return _post(URL_VECTORI, {"text": text, "rol": rol}, timeout=120)["vector"]


def intreaba_modelul(prompt, max_tokens=1400, temp=0.6):
    if not _sus("http://127.0.0.1:8899/v1/models", "slujba"):
        sys.exit("Nu pornește serverul de limbaj din mlx-lab.")
    r = _post(URL_MODEL, {"model": MODEL, "max_tokens": max_tokens,
                          "temperature": temp,
                          "messages": [{"role": "user", "content": prompt}]})
    return r["choices"][0]["message"]["content"].strip()


# ─── arhiva ────────────────────────────────────────────────────────────────
def articole():
    for f in sorted((ROOT / "data").glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            yield json.load(open(f, encoding="utf-8"))
        except Exception:
            continue


def construieste_index(tacut=False):
    """Un vector pentru fiecare articol. Durează o dată, pe urmă e instant."""
    toate = list(articole())
    if not tacut:
        print(f"Indexez {len(toate)} articole… (o singură dată)")
    plecare = time.time()
    with open(INDEX, "w", encoding="utf-8") as f:
        for i, d in enumerate(toate, 1):
            text = f"{d.get('title','')} {d.get('dek','')}"
            f.write(json.dumps({
                "slug": d.get("slug"), "title": d.get("title"),
                "date": d.get("date"), "category": d.get("category"),
                "tara": d.get("tara", ""), "dek": (d.get("dek") or "")[:400],
                "persoane": d.get("persoane") or [],
                "vec": vector(text),
            }, ensure_ascii=False) + "\n")
            if not tacut and (i % 100 == 0 or i == len(toate)):
                print(f"  {i}/{len(toate)}")
    if not tacut:
        print(f"Gata în {(time.time()-plecare)/60:.1f} minute.")


def incarca_index():
    if not INDEX.exists():
        construieste_index()
    elif len(list((ROOT / "data").glob("*.json"))) - 1 > sum(1 for _ in open(INDEX)) + 5:
        print("Au apărut articole noi — refac indexul.")
        construieste_index()
    return [json.loads(l) for l in open(INDEX, encoding="utf-8")]


def cauta(index, intrebare, k=CATE_ARTICOLE):
    qv = vector(intrebare, rol="intrebare")
    qn = sum(x * x for x in qv) ** 0.5 or 1e-9
    scoruri = []
    for d in index:
        v = d["vec"]
        n = sum(x * x for x in v) ** 0.5 or 1e-9
        scoruri.append((sum(a * b for a, b in zip(qv, v)) / (qn * n), d))
    scoruri.sort(key=lambda x: -x[0])
    return scoruri[:k]


# ─── promptul ──────────────────────────────────────────────────────────────
def reguli():
    """Regulile casei, luate din CLAUDE.md ca să nu existe două adevăruri."""
    f = LAB / "prompturi" / "redactor.txt"
    if f.exists():
        return f.read_text().strip()
    return ("Ești redactorul site-ului de fact-checking „Fără Baliverne”. "
            "NU decreta „adevărat” sau „fals”. Arată CE se probează, cu surse, "
            "și CE nu se probează. Nu scrie niciodată că cineva „a mințit”.")


def construieste_prompt(intrebare, gasite, istoric):
    arhiva = "\n\n".join(
        f"[{i+1}] {d['title']}\n    {d['date']} · {d['category']}"
        f"{' · Moldova' if d.get('tara') else ''}\n    {d['dek']}\n"
        f"    https://farabaliverne.ro/a/{d['slug']}.html"
        for i, (_, d) in enumerate(gasite))
    ist = ""
    if istoric:
        ist = "DISCUȚIA DE PÂNĂ ACUM:\n" + "\n".join(
            f"{'Eu' if r=='user' else 'Tu'}: {t}" for r, t in istoric[-6:]) + "\n\n"
    return f"""{reguli()}

Vorbești acum cu fondatorul site-ului, în privat. Nu scrii un articol — răspunzi
la o întrebare. Fii scurt și la obiect.

DIN ARHIVA NOASTRĂ (cele mai apropiate {len(gasite)} articole publicate):
{arhiva}

Reguli pentru răspuns:
- Folosește arhiva când se potrivește și trimite la articol prin numărul lui, [1], [2].
- Dacă arhiva nu răspunde la întrebare, spune limpede că nu avem articol pe tema asta.
- NU inventa titluri, date, cifre sau linkuri care nu sunt mai sus.
- Aceleași reguli ca la publicare: nu decreta adevărat/fals, nu spune că cineva a mințit.

{ist}ÎNTREBAREA: {intrebare}"""


# ─── comenzi ───────────────────────────────────────────────────────────────
def cmd_caut(index, text):
    for s, d in cauta(index, text, 8):
        tara = " · Moldova" if d.get("tara") else ""
        print(f"  {s:.3f}  {d['date']} · {d['category']}{tara}\n         {d['title'][:88]}")


def cmd_despre(index, nume):
    n = nume.strip().lower()
    gasite = [d for d in index
              if any(n in (p or "").lower() for p in d["persoane"])
              or n in (d["title"] or "").lower()]
    if not gasite:
        print(f"  Nicio verificare despre „{nume}”.")
        return
    gasite.sort(key=lambda d: d["date"] or "", reverse=True)
    print(f"  {len(gasite)} verificări despre „{nume}”:")
    for d in gasite[:15]:
        print(f"   {d['date']} · {d['category']} — {d['title'][:82]}")


def cmd_subiect(titlu):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "seamana.py"), titlu],
                       capture_output=True, text=True, cwd=str(ROOT))
    print((r.stdout or r.stderr).rstrip())


SCHEMA = """{
  "slug": "cuvinte-cu-liniuta-fara-diacritice",
  "title": "titlul, concret, cu cifra sau numele in el",
  "category": "una din: Politică, Economie, Extern, Știință, Media de stat, Social, Sport",
  "date": "AAAA-LL-ZZ",
  "source": "numele surselor, separate cu /",
  "url": "linkul sursei principale",
  "dek": "3-5 propozitii care spun ce s-a intamplat si ce se verifica",
  "mainVerdict": "una din: Probat, Probat parțial, Neprobat, Contrazis",
  "probat": [{"text": "afirmatia care SE probeaza, cu cifre concrete",
              "sources": [{"name": "cine spune", "url": "linkul"}]}],
  "contestat": [{"text": "ce NU se probeaza si DE CE nu se poate proba",
                 "sources": [{"name": "cine spune", "url": "linkul"}]}],
  "opinie": [],
  "aiNote": "observatia ta, 4-6 propozitii: ce se vede in cifre si ce nu se spune",
  "persoane": ["Nume Prenume"]
}"""


def cmd_scrie(index, subiect):
    """Ciorna o scrie modelul local. Faptele i le dai tu — el nu are internet."""
    print("  Verific întâi dacă am mai scris despre asta…")
    cmd_subiect(subiect.split("\n")[0][:120])

    print("\n  Lipește sursele și faptele (linkuri, citate, cifre).")
    print("  Termini cu o linie care are doar un punct, apoi Enter.")
    linii = []
    while True:
        try:
            l = input()
        except (EOFError, KeyboardInterrupt):
            break
        if l.strip() == ".":
            break
        linii.append(l)
    material = "\n".join(linii).strip()
    if not material:
        print("  Fără surse nu se scrie nimic. Regula casei.")
        return

    from datetime import date
    apropiate = "\n".join(f"- {d['title']}" for _, d in cauta(index, subiect, 4))
    prompt = f"""{reguli()}

Scrie o CIORNĂ de articol, ca obiect JSON, după schema de mai jos.

🔴 NU inventa NIMIC. Folosește doar faptele și linkurile din materialul primit.
Dacă o cifră sau o sursă nu e în material, nu o scrie. Dacă ceva lipsește, pune-l
la „contestat” ca lucru care nu se poate proba deocamdată.
Data de azi: {date.today().isoformat()}

SCHEMA (răspunde DOAR cu JSON, fără text înainte sau după):
{SCHEMA}

ARTICOLE APROPIATE deja publicate (ca să nu repeți, ci să continui firul):
{apropiate}

SUBIECTUL: {subiect}

MATERIALUL (surse, citate, cifre):
{material}"""

    print("\n  Scrie modelul local… (poate dura un minut)")
    brut = intreaba_modelul(prompt, max_tokens=3000, temp=0.4)
    curat = brut.strip()
    if curat.startswith("```"):
        curat = curat.split("```")[1]
        curat = curat[4:] if curat.startswith("json") else curat
    try:
        d = json.loads(curat)
    except Exception as e:
        cale = ROOT / "data" / "_ciorna-nereusita.txt"
        cale.write_text(brut, encoding="utf-8")
        print(f"  Modelul n-a scos JSON valid ({str(e)[:70]}).")
        print(f"  Textul brut: {cale}")
        return

    # Plasă: modelul inventează verdicte („Anunț neverificat independent”) și
    # categorii. Le aducem la valorile permise, altfel build_site.py se împiedică.
    VERDICTE = ["Probat", "Probat parțial", "Neprobat", "Contrazis"]
    CATEGORII = ["Politică", "Economie", "Extern", "Știință", "Media de stat",
                 "Social", "Sport"]

    def apropie(val, permise, implicit):
        v = (val or "").strip()
        for x in permise:
            if v.lower() == x.lower():
                return x
        for x in permise:                      # potrivire pe bucată
            if x.lower() in v.lower() or v.lower() in x.lower():
                return x
        return implicit

    v_brut, c_brut = d.get("mainVerdict"), d.get("category")
    d["mainVerdict"] = apropie(v_brut, VERDICTE, "Neprobat")
    d["category"] = apropie(c_brut, CATEGORII, "Extern")
    for camp, brut, curat in (("verdict", v_brut, d["mainVerdict"]),
                              ("categorie", c_brut, d["category"])):
        if (brut or "").strip() != curat:
            print(f"  ⚠️  {camp} inventat: „{brut}” → „{curat}” (verifică-l)")

    slug = d.get("slug") or "ciorna-fara-slug"
    d["slug"] = slug
    cale = ROOT / "data" / f"_ciorna-{slug}.json"
    cale.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  ✍️  {d.get('title','(fără titlu)')}")
    print(f"      {d.get('category','?')} · {d.get('mainVerdict','?')} · "
          f"{len(d.get('probat',[]))} probate, {len(d.get('contestat',[]))} contestate")
    print(f"      ciornă: {cale.name}")
    print("      Nu e publicată. Se verifică întâi sursele, apoi:")
    print(f"      mv data/_ciorna-{slug}.json data/{slug}.json && "
          f"python3 scripts/scrie_articol.py {slug}")


LECTII = ROOT / "local" / "lectii_redactor.jsonl"


def cmd_invata(slug):
    """Diferența dintre ciornă și articolul final = cel mai bun material de învățat.

    Nu antrenează nimic acum. Strânge perechile, iar când vine mini-ul cu 32 GB
    se face un LoRA din ele (vezi ~/Projects/mlx-lab). Un exemplu în care
    modelul a greșit și a fost corectat valorează cât zece în care a nimerit.
    """
    slug = slug.strip().replace(".json", "")
    ciorna = ROOT / "data" / f"_ciorna-{slug}.json"
    final = ROOT / "data" / f"{slug}.json"
    if not final.exists():
        print(f"  Nu găsesc data/{slug}.json — articolul final trebuie să existe.")
        return
    LECTII.parent.mkdir(exist_ok=True)
    intrare = {
        "slug": slug,
        "final": json.load(open(final, encoding="utf-8")),
        "ciorna": json.load(open(ciorna, encoding="utf-8")) if ciorna.exists() else None,
    }
    with open(LECTII, "a", encoding="utf-8") as f:
        f.write(json.dumps(intrare, ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(LECTII, encoding="utf-8"))
    if intrare["ciorna"]:
        dif = [k for k in intrare["final"]
               if json.dumps(intrare["final"].get(k), ensure_ascii=False)
               != json.dumps(intrare["ciorna"].get(k), ensure_ascii=False)]
        print(f"  Păstrat. Ai corectat: {', '.join(dif) or 'nimic'}")
    else:
        print("  Păstrat (fără ciornă de comparat — doar articolul bun).")
    print(f"  {n} lecții strânse până acum, în local/lectii_redactor.jsonl")


def cmd_azi(index):
    from datetime import date
    azi = date.today().isoformat()
    de_azi = [d for d in index if d["date"] == azi]
    print(f"  {len(de_azi)} articole publicate azi:")
    for d in sorted(de_azi, key=lambda d: d["title"]):
        tara = " · Moldova" if d.get("tara") else ""
        print(f"   {d['category']}{tara} — {d['title'][:84]}")


# ─── bucla ─────────────────────────────────────────────────────────────────
def main():
    global MODEL
    if "--reindex" in sys.argv:
        construieste_index()
        return
    index = incarca_index()
    print(f"\nRedactorul Fără Baliverne · {len(index)} articole în arhivă · "
          f"{MODEL.split('/')[-1]}")
    print("Nu publică nimic — ciornele rămân locale, tu decizi ce urcă.")
    print("Comenzi: /caut /despre /subiect /scrie /invata /azi /model /reindex"
          " · ieși cu „gata”\n")

    istoric = []
    intrebare = " ".join(a for a in sys.argv[1:] if not a.startswith("--")).strip()
    while True:
        if not intrebare:
            try:
                intrebare = input("tu> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if intrebare in ("gata", "ieși", "iesi", "exit", "quit"):
            break
        if not intrebare:
            continue

        c = intrebare.split(maxsplit=1)
        if c[0] == "/caut" and len(c) > 1:
            cmd_caut(index, c[1])
        elif c[0] == "/despre" and len(c) > 1:
            cmd_despre(index, c[1])
        elif c[0] == "/subiect" and len(c) > 1:
            cmd_subiect(c[1])
        elif c[0] == "/scrie" and len(c) > 1:
            cmd_scrie(index, c[1])
        elif c[0] == "/invata" and len(c) > 1:
            cmd_invata(c[1])
        elif c[0] == "/azi":
            cmd_azi(index)
        elif c[0] == "/model":
            if len(c) > 1 and c[1].strip() in ("27", "27b", "mare"):
                MODEL = MODEL_MARE
                print(f"  → {MODEL}  (⚠️ cere ~17 GB; pe 16 GB nu încape)")
            else:
                print(f"  {MODEL}\n  „/model 27” trece pe Gemma 3 27B (de la 32 GB în sus)")
        elif c[0] == "/reindex":
            construieste_index()
            index = incarca_index()
        else:
            gasite = cauta(index, intrebare)
            raspuns = intreaba_modelul(construieste_prompt(intrebare, gasite, istoric))
            print(f"\n{raspuns}\n")
            istoric += [("user", intrebare), ("assistant", raspuns)]
        intrebare = ""


if __name__ == "__main__":
    main()

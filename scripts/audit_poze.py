"""
audit_poze.py — listează articolele unde poza pare să n-aibă legătură cu textul.

De ce există: pe 13 septembrie 2026 am găsit, pe rând, un pește pe un articol
despre o condamnare în Madagascar, o benzinărie pe unul despre Gaza, un tractor
pe unul despre gripa aviară şi un sat polonez pe unul despre un deputat român.
Toate veneau din aceeaşi cauză — `garda_poze` întreba Commons cu un singur
cuvânt din titlu. Cauza e reparată, dar arhiva a rămas cu poze vechi.

🔴 Unealta asta NU schimbă nimic. Doar arată. Poza se alege de om, fiindcă
măsurătoarea automată dă multe alarme false: legenda de pe Commons e adesea în
altă limbă („Banco Nacional de Rumanía" pe un articol despre BNR e corectă,
deşi n-are niciun cuvânt comun cu titlul românesc).

Folosire:
    python3 scripts/audit_poze.py              # doar cele cu întrebare de un cuvânt
    python3 scripts/audit_poze.py --tot        # şi cele fără cuvinte comune
    python3 scripts/audit_poze.py --comenzi    # tipăreşte comenzile de reparat
"""
import glob, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = set("foto ilustrativa nu este o imagine de la evenimentul relatat din the of and in".split())


def fd(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def articole():
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        slug = os.path.basename(f)[:-5]
        if not os.path.exists(os.path.join(ROOT, "a", slug + ".html")):
            continue
        yield slug, d


def main():
    tot = "--tot" in sys.argv
    comenzi = "--comenzi" in sys.argv
    gasite = []
    for slug, d in articole():
        p = d.get("poza") or {}
        if not p:
            continue
        m = re.search(r'alt="([^"]*)"', p.get("img_html", "") or "")
        alt = (m.group(1) if m else "").strip()
        if not alt:
            continue
        persoane = [fd(x) for x in (d.get("persoane") or [])]
        if fd(alt) in persoane:
            continue                      # portretul persoanei verificate: corect
        un_cuvant = len(alt.split()) < 2
        if not (un_cuvant or tot):
            continue
        fig = re.sub(r"<[^>]+>", " ", p.get("figcaption_html", "") or "")
        fig = re.sub(r"\s+", " ", fig).strip()
        gasite.append((slug, d.get("title", ""), alt, fig))

    print(f"articole de privit: {len(gasite)}\n")
    for slug, titlu, alt, fig in gasite:
        if comenzi:
            print(f'python3 scripts/pune_poza.py {slug} "<căutare engleză>" "<context>"')
            print(f'#   {titlu[:78]}')
            print(f'#   acum: „{alt}" → {fig[:78]}')
        else:
            print(f"  {slug[:52]}")
            print(f"     {titlu[:74]}")
            print(f"     „{alt}\" → {fig[:74]}")


if __name__ == "__main__":
    main()

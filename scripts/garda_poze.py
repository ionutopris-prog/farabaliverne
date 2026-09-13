# -*- coding: utf-8 -*-
"""
Garda pozelor — niciun articol nu iese cu emoji pe gradient.

    python3 scripts/garda_poze.py            # tot ce e publicat
    python3 scripts/garda_poze.py --noi      # doar articolele din ultimul commit
    python3 scripts/garda_poze.py --raport   # doar numără, nu schimbă nimic

DE CE EXISTĂ. Pe 5 septembrie 2026, fondatorul a cerut, cu poza în față:
„să nu mai văd așa ceva pe site". Am reparat atunci toate cele 757 de articole
existente. Dar reparația nu ținea, fiindcă erau DOUĂ scurgeri, nu una:

  1. Redactorul automat scrie articole noi în fiecare zi. Când
     `article_image.py` nu găsește nimic, articolul iese cu gradientul și
     emoji-ul categoriei.
  2. `verifica_poza.py --repara` scoate pozele nepotrivite — corect — dar NU
     pune alta în loc. Deci fiecare poză scoasă readucea emoji-ul.

Garda asta se pune DUPĂ verificator: ia fiecare articol rămas fără poză și îi
caută una. Dacă nu găsește, o spune în raport — nu inventează și nu lasă
lucrurile pe jumătate.

Ce NU face: nu atinge articolele care au deja poză. Nu șterge nimic niciodată.
"""

import glob
import json
import os
import re
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

ARE_POZA = re.compile(r'<img src="[^"]+"[^>]*z-index:1">')
# sfârșitul blocului .art (după glyph), înainte de voalul .grad
ANCORA = re.compile(r'(<div class="glyph">.*?</div>\s*\n\s*)(</div>\s*\n\s*<div class="grad">)', re.S)
FIG_ANCORA = re.compile(r'(<div class="cat-pill">[^<]*</div>\s*\n\s*</div>\s*\n)')

# Cuvinte care nu spun nimic într-o căutare de imagini. Fără lista asta,
# „Guvernul a aprobat" devine o căutare după „Guvernul", care întoarce clădiri
# la întâmplare din toată lumea.
GOALE = {
    "a", "ai", "al", "ale", "au", "că", "ca", "care", "cu", "de", "din", "după",
    "e", "este", "eu", "fi", "fost", "i", "în", "îl", "își", "la", "lui", "mai",
    "nu", "o", "pe", "pentru", "prin", "s", "sa", "să", "se", "sunt", "și", "un",
    "una", "unei", "unor", "va", "vor", "the", "of", "and", "for",
}


def fara_diacritice(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def nume_proprii(d):
    """
    Numele proprii din titlu și din persoanele articolului, în ordinea în care
    merită încercate. Numele de oameni întâi — Commons are portrete de oameni
    publici și denumiri stabile de instituții, deci alea dau cele mai bune
    rezultate.
    """
    ies = []
    for p in (d.get("persoane") or []):
        if p and p not in ies:
            ies.append(fara_diacritice(p))
    text = (d.get("title") or "")
    # 🔴 Prima majusculă din titlu e început de propoziție, NU nume propriu.
    # Fără tăietura asta a ieșit „Incendiul de" ca întrebare pentru Commons, pe
    # articolul despre feribotul din Filipine — iar Commons a răspuns cu un plan
    # de etaj în rusă (13 septembrie 2026).
    text = re.sub(r"^\s*\S+\s*", "", text, count=1)

    # grupuri de cuvinte cu majusculă, lipite (ex. „Banca Națională a României")
    for grup in re.findall(r"(?:[A-ZĂÂÎȘȚ][\w\-]+(?:\s+(?:a|al|ale|de|din)\s+)?)+", text):
        g = fara_diacritice(grup).strip()
        g = re.sub(r"\s+(a|al|ale|de|din)$", "", g)   # nu lăsăm prepoziția la coadă
        if len(g) < 4:
            continue
        if g.lower() in GOALE:
            continue
        # 🔴 Un singur cuvânt e prea larg ca întrebare: „Chile" a adus peșterile
        # de marmură pe un articol despre banca centrală. Un nume de țară sau un
        # cuvânt izolat nu spune NIMIC despre subiectul articolului. Lăsăm doar
        # numele din mai multe cuvinte (instituții, oameni), care chiar
        # identifică ceva.
        if len(g.split()) < 2:
            continue
        if g not in ies:
            ies.append(g)
    return ies[:4]


# 🔴 Categoriile unde numele de oameni NU se caută pe Commons.
# La „Minți luminate" persoanele din articol sunt cercetători, nu oameni publici
# fotografiați. Commons nu-i are, dar are pe altcineva cu nume asemănător — și
# atunci pune poza aia. S-a întâmplat pe 13 septembrie 2026: articolul despre
# studiul BJPsych din București a ieșit ilustrat cu Barack Obama ținând un tricou
# de baseball, fiindcă unul dintre autori se numea Albert Rizzo, iar Commons are
# poze cu jucătorul Anthony Rizzo. Înainte: „Langa Township" pe articolul despre
# Ursoaia și o carte de genealogie pe cel despre Copenhaga.
#
# Regula fondatorului, după ce a văzut poza: la „Minți luminate" poza se alege
# de mână, după SUBIECT, cu `scripts/pune_poza.py <slug> "<căutare>" "<context>"`.
FARA_NUME = {"Minți luminate"}


# 🔴 Ce e articolul DESPRE, nu unde se petrece. Numele proprii spun locul;
# astea spun subiectul, care e ce vrea cititorul să vadă în poză.
#
# De ce există: pe 13 septembrie 2026 articolul despre incendiul de pe feribotul
# din Filipine, cu 76 de morți, a primit plasa de siguranță a categoriei Extern,
# adică „steaguri la un summit". Corect din punct de vedere tehnic, nepotrivit
# ca ton. Cuvintele de mai jos se caută în titlu ŞI în dek, iar primul potrivit
# dă întrebarea. Se completează pe măsură ce apar cazuri noi.
SUBIECTE = [
    (("feribot", "navă", "nava", "vapor", "ambarcaţiune", "ambarcatiune"), "passenger ferry ship at sea"),
    (("incendiu", "flăcări", "flacari", "ardere"), "firefighters extinguishing fire"),
    (("cutremur", "seism", "replici"), "earthquake damaged building"),
    (("inundaţi", "inundati", "viitur"), "flooded street high water"),
    (("banca centrală", "banca centrala", "dobând", "doband", "inflaţi", "inflati"), "central bank building facade"),
    (("prognoz", "creştere economică", "crestere economica", "pib", "recesiune"), "economic growth chart graph"),
    (("bursă", "bursa", "acţiuni", "actiuni"), "stock exchange trading floor"),
    (("avion", "aerian", "aeroport", "zbor"), "commercial airplane airport"),
    (("tren", "feroviar", "cale ferată", "cale ferata"), "passenger train railway"),
    (("spital", "pacient", "medic", "urgenţe", "urgente"), "hospital corridor medical"),
    (("vaccin", "epidemi", "virus", "infecţi", "infecti"), "laboratory vaccine vial"),
    (("alegeri", "vot", "scrutin", "urne"), "ballot box voting station"),
    (("protest", "manifestaţi", "manifestati", "grevă", "greva"), "street protest crowd"),
    (("instanţ", "instant", "judecăt", "judecat", "tribunal", "proces"), "courtroom judge gavel"),
    (("armat", "militar", "război", "razboi", "rachet", "dron"), "military vehicles convoy"),
    (("migraţi", "migrati", "refugiaţi", "refugiati", "azil"), "refugees temporary shelter"),
    (("gaz", "petrol", "conduct", "energie"), "gas pipeline industrial"),
    (("pădur", "padur", "defrişă", "defrisa"), "forest trees canopy"),
    (("şcoal", "scoal", "elev", "profesor", "educaţi", "educati"), "school classroom desks"),
    (("fotbal", "meci", "campionat"), "football stadium match"),
    (("autostrad", "tronson", "şosea", "sosea", "drum naţional", "drum national"), "highway motorway road"),
    (("turişti", "turisti", "litoral", "plaj", "staţiun", "statiun"), "beach seaside tourists"),
    (("asteroid", "cometă", "cometa", "telescop", "satelit", "orbit"), "telescope night sky astronomy"),
    (("ploşniţ", "plosnit", "focar", "infestare"), "hospital ward beds"),
    (("defrişă", "defrisa", "despădur", "despadur"), "deforestation cleared forest"),
]


def subiect(d):
    """Întrebarea după SUBIECT, dacă îl recunoaştem. Altfel None.

    🔴 Potrivirea e pe ÎNCEPUT DE CUVÂNT, nu oriunde în text. Prima versiune
    căuta naiv cu `in` şi a dat „refugees temporary shelter" pe articolul despre
    defrişarea Amazonului: cheia „azil" se potriveşte în interiorul lui
    „br-azil-ian". Cu `\b` la început, rădăcina prinde formele flexionate
    („incendiu", „incendii", „incendiul") fără să sară în alt cuvânt.
    """
    t = ((d.get("title") or "") + " " + (d.get("dek") or "")).lower()
    for chei, intrebare in SUBIECTE:
        for k in chei:
            if re.search(r"\b" + re.escape(k), t):
                return intrebare
    return None


def intrebari(d):
    """Întrebările de încercat, în ordine. Ultima e categoria — plasa de siguranță."""
    q = [] if d.get("category") in FARA_NUME else nume_proprii(d)
    # subiectul bate numele proprii: „feribot" spune mai mult decât „Filipine"
    sub = subiect(d)
    if sub:
        q.insert(0, sub)
    CAT = {
        "Politică": "parliament building government",
        "Economie": "stock exchange trading floor",
        "Extern": "flags international summit",
        "Social": "city street people",
        "Sport": "stadium sport",
        "Știință": "laboratory research science",
        "Media de stat": "television studio broadcast",
        "Minți luminate": "university library research",
    }
    c = CAT.get(d.get("category"))
    if c:
        q.append(c)
    return q


def fara_poza():
    """Articolele care n-au poză nici în pagină, nici în JSON."""
    ies = []
    for j in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(j).startswith("_"):
            continue
        with open(j, encoding="utf-8") as fh:
            d = json.load(fh)
        slug = d.get("slug") or os.path.basename(j)[:-5]
        pagina = os.path.join(ROOT, "a", slug + ".html")
        if not os.path.exists(pagina):
            continue
        pz = d.get("poza") or {}
        fisier = pz.get("fisier")
        are_fisier = bool(fisier) and os.path.exists(os.path.join(ROOT, fisier.lstrip("./")))
        with open(pagina, encoding="utf-8") as fh:
            html = fh.read()
        if ARE_POZA.search(html) and are_fisier:
            continue
        ies.append((slug, j, d, pagina, html))
    return ies


def doar_noi(lista):
    """Doar articolele atinse de ultimul commit."""
    de_la = os.environ.get("DE_LA") or "HEAD~1"
    try:
        out = subprocess.run(["git", "diff", "--name-only", de_la, "HEAD"],
                             cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return lista
    atinse = {os.path.basename(x)[:-5] for x in out.split()
              if x.startswith("data/") and x.endswith(".json")}
    return [x for x in lista if x[0] in atinse] if atinse else []


def cauta(slug, q, context):
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", "article_image.py"),
                        slug, q, context],
                       cwd=ROOT, capture_output=True, text=True, timeout=240)
    o = r.stdout.strip()
    if "{" not in o:
        return None
    try:
        j = json.loads(o[o.index("{"):o.rindex("}") + 1])
    except Exception:
        return None
    return j if j.get("gasit") else None


def pune_in_pagina(html, pz):
    """Injectează <img> + creditul, exact unde stau la articolele care au poză."""
    m = ANCORA.search(html)
    if not m:
        return None
    html = html[:m.end(1)] + m.group(2).split("<div class=\"grad\">")[0] \
        + pz["img_html"] + "\n              " \
        + "<div class=\"grad\">" + html[m.end(2):]
    if pz.get("figcaption_html") and 'class="foto-credit">' not in html:
        m2 = FIG_ANCORA.search(html)
        if m2:
            html = html[:m2.end()] + pz["figcaption_html"] + "\n" + html[m2.end():]
    return html


def main():
    lista = fara_poza()
    if "--noi" in sys.argv:
        lista = doar_noi(lista)
    print(f"articole fără poză: {len(lista)}")
    if "--raport" in sys.argv or not lista:
        for slug, *_ in lista:
            print("   ", slug)
        return 0

    # Minți luminate nu se rezolvă automat: poza se alege de mână, după subiect.
    de_mana = [x for x in lista if x[2].get("category") in FARA_NUME]
    if de_mana and "--si-minti" not in sys.argv:
        lista = [x for x in lista if x[2].get("category") not in FARA_NUME]
        print(f'\n✋ {len(de_mana)} articole din „Minți luminate": poza se alege de mână,')
        print("   fiindcă numele cercetătorilor dau potriviri greșite pe Commons:")
        for slug, *_ in de_mana:
            print(f'   python3 scripts/pune_poza.py {slug} "<căutare în engleză>" "<context>"')
        print()

    reparate, ramase = 0, []
    for slug, j, d, pagina, html in lista:
        context = ((d.get("title") or "") + ". " + (d.get("dek") or ""))[:400]
        gasit = None
        for q in intrebari(d):
            gasit = cauta(slug, q, context)
            if gasit:
                break
        if not gasit:
            ramase.append(slug)
            print(f"⚪ {slug[:60]:<60} n-am găsit nimic potrivit")
            continue
        pz = {k: gasit[k] for k in ("img_html", "figcaption_html", "fisier",
                                    "licenta", "autor") if k in gasit}
        d["poza"] = pz
        with open(j, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
        nou = pune_in_pagina(html, pz)
        if nou:
            with open(pagina, "w", encoding="utf-8") as fh:
                fh.write(nou)
        reparate += 1
        print(f"✅ {slug[:60]:<60} {gasit.get('licenta','')[:16]} · {q[:26]}")

    print(f"\nreparate: {reparate} · rămase fără: {len(ramase)}")
    if ramase:
        print("::warning::articole rămase fără poză: " + ", ".join(ramase[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

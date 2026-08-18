"""
Caută o fotografie potrivită pentru fiecare articol existent.

NU descarcă și NU modifică nimic. Produce doar propuneri, ca fondatorul să le
vadă într-o foaie de verificare înainte să atingem live-ul. Ochiul omului prinde
asocierile nefericite pe care niciun filtru nu le prinde.

Cum alegem ce căutăm, în ordinea încrederii:
Caută în Wikimedia Commons, iar unde Commons n-are nimic, în Openverse
(Flickr/muzee/arhive, tot CC). Commons e bun la oameni și instituții, Openverse
la restul — peisaje, obiecte, situații.

  1. `persoane[]` — Commons are portrete bune de politicieni.
  2. Instituții/locuri recunoscute din titlu — au denumiri stabile pe Commons.
  3. Substantive proprii din titlu — ultima variantă, cea mai puțin sigură.
"""

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pick_image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "preview", "propuneri.json")

# Entități cu denumire stabilă pe Commons. Cheia se caută în titlu+dek.
ENTITATI = {
    "bnr": "National Bank of Romania building",
    "banca națională": "National Bank of Romania building",
    "cernavodă": "Cernavodă Nuclear Power Plant",
    "cnair": "Autostrada A3 Romania motorway",
    "autostrad": "Autostrada Romania motorway",
    "camera deputaților": "Palace of the Parliament Chamber of Deputies Romania",
    "parlament": "Palace of the Parliament Bucharest",
    "cotroceni": "Cotroceni Palace",
    "guvern": "Victoria Palace Bucharest",
    "anaf": "Bucharest government building",
    "aep": "Bucharest government building",
    "înalta curte": "High Court of Cassation and Justice Romania",
    "iccj": "High Court of Cassation and Justice Romania",
    "tribunalul ue": "Court of Justice of the European Union building",
    "dunăre": "Danube river Romania",
    "otopeni": "Henri Coandă International Airport",
    "aeroport": "Henri Coandă International Airport",
    "air china": "Air China Airbus A330",
    "tarom": "TAROM aircraft",
    "fcsb": "Stadionul Steaua Bucharest",
    "superliga": "football stadium Romania",
    "craiova": "Stadionul Ion Oblemenco",
    "afd": "Alternative für Deutschland",
    "bundestag": "Reichstag building Berlin",
    "senatul sua": "United States Senate chamber",
    "casa albă": "White House",
    "gaza": "Gaza Strip",
    # „ucraina": „Ukraine flag" — SCOS pe 18 august. Producea acelasi drapel pe
    # opt articole diferite, doua dintre ele despre Bulgaria si Polonia. Un
    # drapel nu spune nimic despre stire, si opt articole identice vizual arata
    # a site facut de robot. Cardul de brand e mai onest.
    "oms": "World Health Organization headquarters",
    "moody": "Moody's headquarters",
    "nasa": "NASA logo",
    "telemarketing": "call centre office",
    "secetă": "drought dry ground",
    "caniculă": "heat wave sun",
    "vaccin": "vaccine vial syringe",
    "deepfake": "artificial intelligence computer screen",
    "inflaț": "Romanian leu banknotes",
    "pilonul ii": "Romanian leu banknotes",
    "deficit": "Romanian leu banknotes",
    "subvenți": "Romanian leu banknotes",
}

STOP = set("""
a al ale la si și în din de pe cu care ce nu mai o un una unui unei este e sunt
au fost va vor s-a s-au se fara fără dupa după prin peste intre între pentru
primul prima primele noi noua nou anul ani zile luna ora ore miliarde milioane
sut sută la suta procente ce cum cand când unde cine
""".split())


def entitati_din_titlu(text):
    """Substantive proprii, ca ultimă soluție."""
    words = re.findall(r"\b[A-ZȘȚĂÎÂ][\wșțăîâ-]{2,}", text)
    keep = [w for w in words if w.lower() not in STOP]
    return " ".join(keep[:3])


# Entitățile românești nu au ce căuta pe o știre din altă țară. „Guvern" a pus
# Palatul Victoria pe alegeri din Carolina de Sud până am adăugat garda asta.
ROMANESTI = {
    "National Bank of Romania building", "Cernavodă Nuclear Power Plant",
    "Autostrada A3 Romania motorway", "Autostrada Romania motorway",
    "Palace of the Parliament Chamber of Deputies Romania",
    "Palace of the Parliament Bucharest", "Cotroceni Palace",
    "Victoria Palace Bucharest", "Bucharest government building",
    "High Court of Cassation and Justice Romania", "Danube river Romania",
    "Henri Coandă International Airport", "TAROM aircraft",
    "Stadionul Steaua Bucharest", "football stadium Romania",
    "Stadionul Ion Oblemenco", "Romanian leu banknotes",
}

STRAINE = [
    "sua", "statele unite", "washington", "carolina", "franț", "franta",
    "marea britanie", "uk", "londra", "germania", "berlin", "italia", "spania",
    "bulgaria", "ucraina", "rusia", "china", "japonia", "india", "israel",
    "gaza", "iran", "turcia", "moldova", "ungaria", "polonia", "grecia",
    "olanda", "belgia", "austria", "elveția", "suedia", "norvegia", "danemarca",
]


def _incepe_cuvant(hay, cheie):
    """Potrivire pe ÎNCEPUT de cuvânt: «dobând» prinde «dobânda-cheie».

    Cheile temelor sunt rădăcini, nu cuvinte întregi — româna le declină în
    toate felurile («incendiu/incendii», «maşină/maşini», «dobândă/dobânzi»).
    Cu potrivire pe cuvânt întreg, aproape niciun nivel tematic nu se
    declanşa: „incendi" nu prindea „incendiu", „dobând" nu prindea
    „dobânda-cheie", şi articolele rămâneau fără poză degeaba.

    Ancorăm la început, NU şi la sfârşit. Subşirul liber ar fi fost mai rău:
    „port" ar fi prins „raport" şi „important", „tren" ar fi prins
    „antrenament".
    """
    return re.search(r"(?<![\wăâîșț])" + re.escape(cheie), hay) is not None


def _contine_cuvant(hay, cheie):
    """Potrivire pe cuvinte întregi. Pe subșiruri, «oms» prindea «Tromsø»."""
    return re.search(r"(?<![\wăâîșț])" + re.escape(cheie) + r"(?![\wăâîșț])",
                     hay) is not None


# Nivelul TEMATIC, pentru Openverse. Commons e bun la oameni și instituții cu
# nume; Openverse e bun la ce se vede într-o fotografie oarecare — o rafinărie,
# o sală de spital, un teren de fotbal. Legăm subiectul articolului de o
# interogare generică în engleză, fiindcă acolo e fondul de poze.
#
# Cheia se caută în titlu+dek. Interogarea NU se compune din cuvintele
# titlului — regula asta a fost învățată pe 11 august, când „Puterea de
# cumpărare" a întors o locomotivă cu abur.
TEME = {
    # sport
    "superliga": "football stadium match", "fotbal": "football stadium match",
    "conference league": "football stadium match", "europa league": "football stadium match",
    "champions league": "football stadium match", "super cup": "football stadium match",
    "cupa româniei": "football stadium match",
    "haltere": "weightlifting barbell", "greutate": "weightlifting barbell",
    "înot": "swimming pool lane", "natație": "swimming pool lane",
    "tenis": "tennis court player", "atletism": "athletics running track",
    "gimnastică": "gymnastics competition", "canotaj": "rowing boat race",
    "handbal": "handball court", "baschet": "basketball court",
    # economie / finanțe
    "inflaţie": "supermarket shelves shopping", "inflație": "supermarket shelves shopping",
    "preţuri": "supermarket shelves shopping", "prețuri": "supermarket shelves shopping",
    "consum": "supermarket shelves shopping", "coş de cumpărături": "supermarket shelves shopping",
    "bursă": "stock exchange trading floor", "acţiuni": "stock exchange trading floor",
    "acțiuni": "stock exchange trading floor", "randament": "stock exchange trading floor",
    "obligaţiuni": "stock exchange trading floor", "obligațiuni": "stock exchange trading floor",
    "dobând": "bank building finance", "credit": "bank building finance",
    "salari": "office workers desk", "pensi": "elderly people bench",
    "deficit comercial": "cargo containers port", "export": "cargo containers port",
    "import": "cargo containers port", "comerţ": "cargo containers port",
    "buget": "calculator money desk", "taxe": "calculator money desk",
    "impozit": "calculator money desk", "accize": "fuel station pump",
    "carburant": "fuel station pump", "motorină": "fuel station pump",
    "benzin": "fuel station pump", "petrol": "oil refinery industrial",
    "rafinări": "oil refinery industrial", "gaze naturale": "gas pipeline industrial",
    "energie": "electricity pylons power lines", "electricitate": "electricity pylons power lines",
    "cărbune": "coal power plant", "nuclear": "nuclear power plant cooling",
    "eolian": "wind turbines field", "fotovoltaic": "solar panels field",
    # sănătate
    "spital": "hospital corridor beds", "medic": "hospital corridor beds",
    "pacien": "hospital corridor beds", "vaccin": "vaccination syringe vial",
    "rujeol": "vaccination syringe vial", "gripă": "vaccination syringe vial",
    "medicament": "pills medication pharmacy", "statine": "pills medication pharmacy",
    "farmac": "pills medication pharmacy", "studiu clinic": "laboratory research microscope",
    # mediu / vreme
    "secetă": "drought dry cracked ground", "caniculă": "hot sun summer heat",
    "inundaţi": "flooded street water", "inundați": "flooded street water",
    "incendi": "forest landscape trees", "pădur": "forest landscape trees",
    "climă": "clouds sky landscape", "temperatur": "thermometer hot weather",
    "dunăre": "danube river landscape", "fluviu": "river landscape water",
    "poluare": "industrial smokestack pollution",
    # transport / infrastructură
    "autostrad": "highway motorway road", "şosea": "highway motorway road",
    "drum naţional": "highway motorway road", "cale ferată": "railway tracks train",
    "tren": "railway tracks train", "cfr": "railway tracks train",
    "aeroport": "airport terminal aircraft", "zbor": "airport terminal aircraft",
    "avion": "airport terminal aircraft", "autocar": "coach bus road",
    "autobuz": "city bus street", "metrou": "metro subway station",
    "port": "cargo containers port", "navă": "cargo ship sea",
    "maşin": "car factory assembly line", "mașin": "car factory assembly line",
    "vehicul": "car factory assembly line", "automobil": "car factory assembly line",
    "electric": "electric car charging station",
    # stat / justiție / educație
    "penitenciar": "prison building fence", "închisoare": "prison building fence",
    "instanţ": "courtroom bench justice", "instanț": "courtroom bench justice",
    "tribunal": "courtroom bench justice", "judecător": "courtroom bench justice",
    "proces": "courtroom bench justice", "poliţi": "police car street",
    "poliți": "police car street", "şcoal": "school classroom desks",
    "şcol": "school classroom desks", "școal": "school classroom desks",
    "elev": "school classroom desks", "bacalaureat": "school classroom desks",
    "universit": "university campus building", "student": "university campus building",
    "cadastru": "land surveying field", "teren agricol": "wheat field farmland",
    "agricultur": "wheat field farmland", "fermier": "wheat field farmland",
    "recolt": "wheat field farmland",
    # apărare / frontieră
    "militar": "soldiers military exercise", "armat": "soldiers military exercise",
    "nato": "soldiers military exercise", "dron": "drone flying sky",
    "frontier": "border fence crossing", "graniţ": "border fence crossing",
    "graniț": "border fence crossing", "schengen": "border fence crossing",
    "migran": "border fence crossing", "azil": "border fence crossing",
    # tehnologie
    "telemarketing": "call centre office headset", "call center": "call centre office headset",
    "abonament": "credit card online payment", "plat[ăa] online": "credit card online payment",
    "internet": "server room data centre", "date personale": "server room data centre",
    "inteligenţ[ăa] artificial": "computer server room", "algoritm": "computer server room",
    "satelit": "satellite orbit space", "spaţiu": "satellite orbit space",
    # adăugate după ce au picat pe cazuri reale, 18 august
    "auto": "car dealership showroom", "înmatricul": "car dealership showroom",
    "piaţa auto": "car dealership showroom", "piața auto": "car dealership showroom",
    "banca angliei": "bank of england building", "banca centrală": "bank building finance",
    "bce": "european central bank building", "rezerva federal": "federal reserve building",
    "hectare": "forest landscape trees", "pompier": "firefighters equipment",
    "cibernetic": "computer server room", "atac cibernetic": "computer server room",
    "apă": "water tap drinking", "canalizare": "water pipes infrastructure",
    "gunoi": "waste containers recycling", "deşeuri": "waste containers recycling",
    "deșeuri": "waste containers recycling", "turism": "tourists city street",
    "hotel": "hotel building facade", "restaurant": "restaurant interior tables",
    "chirie": "apartment buildings housing", "locuinţ": "apartment buildings housing",
    "locuinț": "apartment buildings housing", "imobiliar": "apartment buildings housing",
    "construcţi": "construction site crane", "construcți": "construction site crane",
}

# Subiecte la care NU căutăm poză deloc: morţi, violenţă, tragedii. Nicio
# fotografie de stoc nu e potrivită acolo, iar una nepotrivită e mai rea decât
# cardul de brand. Filtrul de risc al uneltei prinde poza; ăsta opreşte
# căutarea din start.
FARA_POZA = [
    "mort", "morţi", "morți", "ucis", "uciși", "deces", "victim", "înjunghi",
    "împuşc", "împușc", "atac terorist", "accident", "prăbuş", "prăbuș",
    "explozie", "funeral", "funerar", "sinucid", "viol ", "pedofil", "abuz",
]


def _fara_diacritice(t):
    for a, b in (("ăâ", "a"), ("î", "i"), ("șş", "s"), ("țţ", "t")):
        for ch in a:
            t = t.replace(ch, b)
    return t


def interogari(art):
    """Întoarce lista de interogări de încercat, cea mai bună prima."""
    hay_brut = _fara_diacritice(
        (art.get("title", "") + " " + art.get("dek", "")).lower())

    # Morţi, violenţă, tragedii: nu căutăm poză deloc. Nicio fotografie de
    # stoc nu e potrivită lângă cinci răniţi prin împuşcare, iar una
    # nepotrivită e mai rea decât cardul de brand. Potrivirea e pe fragment,
    # nu pe cuvânt întreg: „impusc" trebuie să prindă şi „împuşcare".
    if any(_incepe_cuvant(hay_brut, _fara_diacritice(c)) for c in FARA_POZA):
        return []

    qs = []

    persoane = art.get("persoane") or []
    for p in persoane[:1]:
        nume = p if isinstance(p, str) else (p.get("nume") or p.get("name") or "")
        if nume:
            qs.append((nume, "persoană"))

    hay = (art.get("title", "") + " " + art.get("dek", "")).lower()
    despre_strainatate = any(_contine_cuvant(hay, t) for t in STRAINE)

    # cheile lungi primele: „camera deputaților" bate „parlament"
    for cheie in sorted(ENTITATI, key=len, reverse=True):
        if not _contine_cuvant(hay, cheie):
            continue
        q = ENTITATI[cheie]
        if despre_strainatate and q in ROMANESTI:
            continue
        qs.append((q, "entitate"))
        break

    # Nivelul TEMATIC. Intră ultimul, după ce nume și instituții n-au dat nimic.
    # Sărim complet subiectele grele: acolo cardul de brand e singurul răspuns
    # decent.
    for cheie in sorted(TEME, key=len, reverse=True):
        if _incepe_cuvant(hay, cheie):
            qs.append((TEME[cheie], "temă"))
            break

    # Nivelul „substantive proprii din titlu" a fost scos după verificarea din
    # 11 august 2026. Producea numai gunoi, cu încredere: „Puterea de cumpărare"
    # -> căutare „Puterea" -> o locomotivă cu abur în zăpadă, pe o știre despre
    # inflație. „Franța" -> un tunel. Un card de brand e mult mai bun decât o
    # poză sigură pe ea și complet greșită.
    return qs


def cu_hotlink():
    """Slug-urile ale căror articole încă trag poza de pe alt site.

    Le găsim uitându-ne în HTML-ul publicat, nu în `data/`: hotlinkul stă în
    pagină, nu în schemă. Sunt cele rămase din perioada dinainte ca poza să
    treacă obligatoriu prin unealtă.
    """
    rx = re.compile(r'<img[^>]+src="(https://(?!farabaliverne\.ro)[^"]+)"')
    out = set()
    for p in glob.glob(os.path.join(ROOT, "a", "*.html")):
        with open(p, encoding="utf-8") as fh:
            if rx.search(fh.read()):
                out.add(os.path.basename(p)[:-5])
    return out


def fara_poza():
    """Articolele care încă stau pe cardul de brand, fără fotografie proprie."""
    rx = re.compile(r'<img[^>]+src="(?:\.\./)?img/articole/')
    out = set()
    for p in glob.glob(os.path.join(ROOT, "a", "*.html")):
        with open(p, encoding="utf-8") as fh:
            if not rx.search(fh.read()):
                out.add(os.path.basename(p)[:-5])
    return out


def main():
    fisiere = sorted(glob.glob(os.path.join(ROOT, "data", "*.json")))

    # Fără argumente, mătură tot. Cu `--hotlink`, doar articolele care încă
    # trag poza de pe alt site. Cu slug-uri, exact alea.
    arg = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--fara-poza" in sys.argv:
        vrem = fara_poza()
        print(f"Doar articolele fără poză proprie: {len(vrem)}")
    elif "--hotlink" in sys.argv:
        vrem = cu_hotlink()
        print(f"Doar articolele cu hotlink: {len(vrem)}")
    elif arg:
        vrem = set(arg)
    else:
        vrem = None
    if vrem is not None:
        fisiere = [f for f in fisiere if os.path.basename(f)[:-5] in vrem]
    rezultate = []

    for i, path in enumerate(fisiere, 1):
        with open(path, encoding="utf-8") as fh:
            art = json.load(fh)

        slug = art.get("slug") or os.path.basename(path)[:-5]
        context = (art.get("title", "") + " " + art.get("dek", "")).lower()

        ales = None
        folosit = None
        for q, tip in interogari(art):
            try:
                cand = pick_image.search_tot(
                    q, context, limit=10,
                    nume_persoana=q if tip == "persoană" else None)
            except Exception as exc:
                print(f"  [{i}/{len(fisiere)}] {slug}: eroare căutare — {exc}")
                continue
            if cand:
                ales = cand[0]
                folosit = (q, tip)
                break

        rezultate.append({
            "slug": slug,
            "title": art.get("title", ""),
            "category": art.get("category", ""),
            "query": folosit[0] if folosit else None,
            "query_type": folosit[1] if folosit else None,
            "photo": ales,
        })

        stare = "OK " if ales else "—  "
        print(f"  [{i:2}/{len(fisiere)}] {stare} {slug[:48]:48} "
              f"{(folosit[0][:34] if folosit else 'niciun candidat')}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rezultate, fh, ensure_ascii=False, indent=1)

    gasite = sum(1 for r in rezultate if r["photo"])
    print(f"\n{gasite}/{len(rezultate)} articole au o propunere de poză")
    print(f"scris: {OUT}")


if __name__ == "__main__":
    main()

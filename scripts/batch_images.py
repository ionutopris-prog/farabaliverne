"""
Caută o fotografie potrivită pentru fiecare articol existent.

NU descarcă și NU modifică nimic. Produce doar propuneri, ca fondatorul să le
vadă într-o foaie de verificare înainte să atingem live-ul. Ochiul omului prinde
asocierile nefericite pe care niciun filtru nu le prinde.

Cum alegem ce căutăm, în ordinea încrederii:
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
    "ucraina": "Ukraine flag",
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


def _contine_cuvant(hay, cheie):
    """Potrivire pe cuvinte întregi. Pe subșiruri, «oms» prindea «Tromsø»."""
    return re.search(r"(?<![\wăâîșț])" + re.escape(cheie) + r"(?![\wăâîșț])",
                     hay) is not None


def interogari(art):
    """Întoarce lista de interogări de încercat, cea mai bună prima."""
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

    # Nivelul „substantive proprii din titlu" a fost scos după verificarea din
    # 11 august 2026. Producea numai gunoi, cu încredere: „Puterea de cumpărare"
    # -> căutare „Puterea" -> o locomotivă cu abur în zăpadă, pe o știre despre
    # inflație. „Franța" -> un tunel. Un card de brand e mult mai bun decât o
    # poză sigură pe ea și complet greșită.
    return qs


def main():
    fisiere = sorted(glob.glob(os.path.join(ROOT, "data", "*.json")))
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
                cand = pick_image.search(
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

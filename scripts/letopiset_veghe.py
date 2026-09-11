#!/usr/bin/env python3
"""
VEGHEA LETOPISEȚULUI — presa vorbește despre un dezastru natural care lipsește din jurnal?

De ce există: pe 4–6 septembrie 2026 Anak Krakatau a aruncat cenușă la 15 km și a
închis aeroporturile din Jakarta (2.300 de zboruri anulate), iar Letopisețul n-a
scris nimic. Fluxul GDACS „curent" nu-l avea, iar codul lua evenimentele doar în
ziua în care încep. Fondatorul a aflat din altă parte și a întrebat: „cum de poți
omite un eveniment așa important? trebuie eu să aflu". Răspunsul corect nu e „am
reparat cele două bug-uri" (le-am reparat), ci un mecanism care să prindă
URMĂTORUL bug: o comparație zilnică, independentă de surse, cu ce scrie presa.

Cum: pentru fiecare tip de dezastru cere titlurile din ultimele 2 zile de la
Google News (gratuit, fără cheie), scoate numele proprii din ele (vulcani,
furtuni, țări, orașe) și le caută în jurnalul ultimelor 3 zile. Ce nu se
regăsește ajunge în data/_letopiset_de_verificat.json și într-o problemă pe
GitHub, ca să se uite un om. Nu adaugă nimic singur în Letopiseț: un titlu de
presă nu e o sursă primară — e un semnal că trebuie căutată una.

Rulare: python3 scripts/letopiset_veghe.py [2026-09-09]
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import letopiset as L  # noqa: E402

DE_VERIFICAT = os.path.join(L.ROOT, "data", "_letopiset_de_verificat.json")
UA = "Mozilla/5.0 (farabaliverne.ro letopiset-veghe)"

INTREBARI = {
    "erupție vulcanică": "volcano eruption",
    "cutremur": "earthquake magnitude",
    "furtună tropicală": "hurricane OR typhoon OR cyclone landfall",
    "tsunami": "tsunami",
    "incendiu de vegetație": "wildfire evacuated",
    "inundații": "floods dead OR flooding killed",
    "alunecare de teren": "landslide OR mudslide",
    "tornadă": "tornado",
    "caniculă": "heatwave record temperature",
    "secetă": "drought emergency",
    "focar": "outbreak WHO cholera OR ebola OR mpox OR measles",
}
# titluri care nu sunt evenimente (verificări de fapte, aniversări, studii, opinii)
NU_E_EVENIMENT = re.compile(r"fact.?check|falsely|years?-old|anniversary|study|explain|opinion|what to know|"
                            r"how to|why |could |might |warns? of|forecast|season", re.I)
# nume proprii care nu-s locuri: surse de presă, zile, luni, cuvinte de titlu
STOP = {"AP", "News", "BBC", "CNN", "Reuters", "AFP", "Al", "Jazeera", "The", "Guardian", "NPR", "ABC", "CBS", "NBC",
        "Bloomberg", "Times", "Post", "Yahoo", "Euronews", "DW", "France", "24", "Sky", "Fox", "USA", "Today", "Live",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
        "April", "May", "June", "July", "August", "September", "October", "November", "December", "Volcano", "Volcanic",
        "Earthquake", "Hurricane", "Typhoon", "Cyclone", "Tsunami", "Wildfire", "Wildfires", "Flood", "Floods", "Flooding",
        "Landslide", "Tornado", "Tornadoes", "Heat", "Heatwave", "Drought", "Outbreak", "WHO", "Mount", "Mt", "Storm",
        "Tropical", "Category", "National", "Weather", "Service", "Center", "Centre", "Watch", "Warning", "Update",
        "Video", "Photos", "Live", "Breaking", "New", "North", "South", "East", "West", "Central", "Northern", "Southern",
        "Eastern", "Western", "Island", "Islands", "Coast", "Bay", "Gulf", "Sea", "Ocean", "River", "Lake", "Valley",
        "City", "County", "State", "Province", "Region", "Airport", "Flights", "Officials", "Authorities", "Residents",
        "Death", "Toll", "People", "Thousands", "Hundreds", "Dozens", "Millions", "Emergency", "Rescue", "Evacuation",
        "Ash", "Lava", "Magnitude", "Richter", "USGS", "NOAA", "NASA", "FEMA", "UN", "EU", "US", "UK", "Fact", "Check",
        "After", "Before", "Updates", "Eruption", "Eruptions", "Erupts", "Quake", "Alert", "Latest", "Strikes", "Hits",
        "Kills", "Killed", "Dead", "Missing", "Airports", "Reopen", "Reopens", "Closed", "Stranded", "Travel", "Safe",
        "Amid", "Over", "Near", "Into", "From", "With", "Still", "Remains", "Continues", "Sends", "Leaves", "Cancels",
        "Canceled", "Cancelled", "Braces", "Slams", "Makes", "Landfall", "Powerful", "Strong", "Major", "Massive",
        "Deadly", "Historic", "Record", "Highest", "Lowest", "Meters", "Feet", "Miles", "Hour", "Hours", "Days", "Week",
        "Weeks", "Month", "Year", "Years", "First", "Second", "Third", "Hundreds", "Everything", "Here", "What", "When",
        "Where", "This", "That", "These", "Those", "Their", "There", "Than", "Then", "Some", "More", "Most", "Many",
        "Just", "Also", "Only", "Even", "Ever", "Never", "Again", "Back", "Down", "Away", "Toward", "Towards", "Along",
        "Across", "Around", "Through", "Under", "Against", "Between", "Without", "Within", "Unusual", "Extreme",
        "Threat", "Threatens", "Impact", "Impacts", "Damage", "Disaster", "Disasters", "Crisis", "Response", "Relief",
        "Government", "President", "Minister", "Ministry", "Agency", "Department", "Prevention", "Control", "Health",
        "Disease", "Cases", "Deaths", "Spread", "Spreads", "Rises", "Climbs", "Reaches", "Tops", "Passes", "Surges", "Moderate", "Labor", "Shallow", "Mudslide", "Mudslides", "Water", "Costa", "Rica", "Sierra", "Santa", "Puerto", "Saint", "Cape", "Fire", "Fires", "Smoke", "Rain", "Rains", "Snow", "Wind", "Winds", "Light", "Minor", "Small", "Large", "Huge", "Fresh", "Another", "Latest"}


def titluri(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d")
           + "&hl=en-US&gl=US&ceid=US:en")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        xml = r.read().decode("utf-8", "ignore")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        l = re.search(r"<link>(.*?)</link>", it, re.S)
        if t:
            titlu = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).strip()
            titlu = re.sub(r"\s+-\s+[^-]{2,40}$", "", titlu)   # „… - AP News”
            out.append((titlu, (l.group(1).strip() if l else "")))
    return out


def nume_proprii(titlu):
    """Cuvintele cu majusculă (≥ 4 litere) care nu-s din lista de stop, cu țările traduse în română."""
    cuv = re.findall(r"\b[A-Z][a-zA-Z'’\-]{3,}\b", titlu)
    ies = set()
    for c in cuv:
        c = re.sub(r"['’]s$", "", c)
        if c in STOP or c.upper() == c:
            continue
        # bolile: jurnalul e în română („rujeolă”), presa în engleză („measles”)
        if c.lower() in L.BOLI:
            ies.add(L.BOLI[c.lower()]); continue
        ies.add(L.TARI.get(c, c))
    return ies


CUVANT_CHEIE = re.compile(r"volcan|erupt|earthquake|quake|tremor|hurricane|typhoon|cyclone|tsunami|wildfire|"
                          r"bushfire|flood|landslide|mudslide|tornado|heat ?wave|drought|outbreak|cholera|ebola|mpox", re.I)


def veghe(zi):
    """Numele proprii care apar în ≥ 5 titluri diferite despre dezastre (deci un eveniment
    acoperit de mai multe redacții, nu un titlu rătăcit) și care lipsesc din jurnalul
    ultimelor 7 zile."""
    tot = L.incarca()
    d0 = datetime.strptime(zi, "%Y-%m-%d")
    zile = [(d0 - timedelta(days=k)).strftime("%Y-%m-%d") for k in range(0, 7)]
    jurnal = " ".join(e.get("text", "") for z in zile for e in tot.get(z, [])).lower()
    stiri = {}                                   # titlu -> (tip, link)
    for tip, q in INTREBARI.items():
        try:
            for titlu, link in titluri(q):
                if NU_E_EVENIMENT.search(titlu) or not CUVANT_CHEIE.search(titlu):
                    continue
                stiri.setdefault(titlu, (tip, link))
        except Exception as e:
            print(f"  {tip}: {e}", file=sys.stderr)
    aparitii = {}                                # nume -> [titluri]
    for titlu in stiri:
        for n in nume_proprii(titlu):
            aparitii.setdefault(n, []).append(titlu)
    gasite = {}
    for n, tl in aparitii.items():
        if len(tl) < 5 or n.lower() in jurnal:
            continue
        # țară scrisă ca adjectiv („Indonesian”) — încercăm rădăcina
        radacini = {n[:-1], n[:-2], n[:-3]}
        if any(L.TARI.get(r, r).lower() in jurnal for r in radacini if len(r) >= 4):
            continue
        tip = stiri[tl[0]][0]
        gasite[n] = {"tip": tip, "nume": [n], "titluri": [{"titlu": t, "link": stiri[t][1]} for t in tl[:3]],
                     "aparitii": len(tl)}
    # ordonăm după cât de tare vorbește presa
    # cel mult 12 — ce e sub, e zgomot; un om nu verifică 80 de nume pe noapte
    return dict(sorted(gasite.items(), key=lambda kv: -kv[1]["aparitii"])[:12])


def main():
    zi = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    gasite = veghe(zi)
    try:
        toate = json.load(open(DE_VERIFICAT, encoding="utf-8")) if os.path.exists(DE_VERIFICAT) else {}
    except Exception:
        toate = {}
    # Un nume anunțat o dată nu se mai anunță 7 zile: altfel fondatorul primea
    # același „Nepal” de două ori pe zi, la fiecare rulare (10–11 sept 2026).
    anuntate = {n for z, g in toate.items() if z != zi and z >= (datetime.strptime(zi, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d") for n in g}
    anuntate |= set(toate.get(zi, {}))
    noi = {n: g for n, g in gasite.items() if n not in anuntate}
    toate.setdefault(zi, {}).update(gasite)
    # ținem doar ultimele 14 zile
    for k in sorted(toate)[:-14]:
        toate.pop(k, None)
    with open(DE_VERIFICAT, "w", encoding="utf-8") as f:
        json.dump(toate, f, ensure_ascii=False, indent=1)
    if not noi:
        print(f"{zi}: nimic nou față de ce am anunțat deja ({len(gasite)} nume, toate văzute).")
        return
    print(f"{zi}: {len(noi)} posibile evenimente ratate — de verificat de un om:")
    for cheie, g in noi.items():
        print(f"   · [{g['tip']}] {', '.join(g['nume'])} — în {g['aparitii']} titluri")
        for t in g["titluri"]:
            print(f"        „{t['titlu']}”")


if __name__ == "__main__":
    main()

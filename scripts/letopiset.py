# -*- coding: utf-8 -*-
"""
Letopisețul Planetei Pământ — ce s-a întâmplat azi pe Pământ.

    python3 scripts/letopiset.py            # ziua curentă (UTC)
    python3 scripts/letopiset.py 2026-09-05 # o zi anume

Ideea fondatorului, 5 septembrie 2026: o secțiune în josul paginii, nu ușor
vizibilă, unde se adună cronologic ce s-a întâmplat pe Pământ — „a fost
cutremur acolo, s-a întâmplat avalanșă, a fost accident, s-a scufundat un
vapor, s-a prăbușit avionul ăla; în principiu undeva pe Pământ se întâmplă
ceva în fiecare zi".

REGULILE LUI, care dau și forma codului:
  - se completează în fiecare zi la 23:59 UTC, pentru ziua încheiată
  - câteva rânduri, nu multe povești
  - link către sursă dacă avem, dar FĂRĂ explicații. Mai bine fără decât cu.
  - începe de azi. Nu se reconstruiește trecutul.

De-aia intrările sunt telegrafice — dată, faptă, loc, cifră, link — în tradiția
letopisețelor. Fără adjective, fără interpretare. Un letopiseț nu comentează.

SURSE, amândouă publice și fără cheie de API:
  - USGS: cutremurele lumii, în timp real
  - GDACS: sistemul european de alertă — cicloane, inundații, vulcani,
    incendii, secete. Deja folosit de Comisia Europeană, deci e o sursă pe
    care o putem cita fără ezitare.

Ce NU face: nu inventează, nu rezumă, nu completează golurile. O zi fără
evenimente rămâne o zi fără evenimente.
"""

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FISIER = os.path.join(ROOT, "data", "_letopiset.json")
UA = "farabaliverne.ro/1.0 (letopiset; contact@farabaliverne.ro)"

# Praguri. Fără ele, letopisețul ar fi o listă de seismograf: USGS raportează
# sute de cutremure pe zi, majoritatea nesimțite de nimeni. M5.0 e pragul de la
# care un cutremur se simte serios și intră în presă.
PRAG_MAGNITUDINE = 5.0
# GDACS dă trei niveluri: verde (fără impact), portocaliu, roșu. Verdele ar
# umple pagina cu evenimente pe care nu le-a observat nimeni.
NIVELURI = ("Orange", "Red")

TIPURI = {
    "EQ": "Cutremur", "TC": "Ciclon tropical", "FL": "Inundație",
    "VO": "Erupție vulcanică", "DR": "Secetă", "WF": "Incendiu de vegetație",
    "TS": "Tsunami",
}


# Numele de țări vin în engleză de la ambele surse. Traducem ce știm sigur și
# lăsăm restul cum e — un nume englezesc e mai bun decât o traducere greșită.
TARI = {
 "Afghanistan":"Afganistan","Albania":"Albania","Algeria":"Algeria","Argentina":"Argentina",
 "Armenia":"Armenia","Australia":"Australia","Austria":"Austria","Azerbaijan":"Azerbaidjan",
 "Bangladesh":"Bangladesh","Belarus":"Belarus","Belgium":"Belgia","Belize":"Belize",
 "Bolivia":"Bolivia","Bosnia & Herzegovina":"Bosnia și Herțegovina","Brazil":"Brazilia",
 "Bulgaria":"Bulgaria","Cambodia":"Cambodgia","Cameroon":"Camerun","Canada":"Canada",
 "Chile":"Chile","China":"China","Colombia":"Columbia","Costa Rica":"Costa Rica",
 "Croatia":"Croația","Cuba":"Cuba","Cyprus":"Cipru","Czech Republic":"Cehia",
 "Czechia":"Cehia","Denmark":"Danemarca","Dominican Republic":"Republica Dominicană",
 "Ecuador":"Ecuador","Egypt":"Egipt","El Salvador":"El Salvador","Estonia":"Estonia",
 "Ethiopia":"Etiopia","Fiji":"Fiji","Finland":"Finlanda","France":"Franța",
 "Georgia":"Georgia","Germany":"Germania","Greece":"Grecia","Guatemala":"Guatemala",
 "Haiti":"Haiti","Honduras":"Honduras","Hungary":"Ungaria","Iceland":"Islanda",
 "India":"India","Indonesia":"Indonezia","Iran":"Iran","Iraq":"Irak","Ireland":"Irlanda",
 "Israel":"Israel","Italy":"Italia","Jamaica":"Jamaica","Japan":"Japonia","Jordan":"Iordania",
 "Kazakhstan":"Kazahstan","Kenya":"Kenya","Kyrgyzstan":"Kârgâzstan","Laos":"Laos",
 "Latvia":"Letonia","Lebanon":"Liban","Libya":"Libia","Lithuania":"Lituania",
 "Luxembourg":"Luxemburg","Madagascar":"Madagascar","Malaysia":"Malaezia","Mali":"Mali",
 "Mexico":"Mexic","Moldova":"Republica Moldova","Mongolia":"Mongolia","Montenegro":"Muntenegru",
 "Morocco":"Maroc","Mozambique":"Mozambic","Myanmar":"Myanmar","Nepal":"Nepal",
 "Netherlands":"Țările de Jos","New Zealand":"Noua Zeelandă","Nicaragua":"Nicaragua",
 "Nigeria":"Nigeria","North Macedonia":"Macedonia de Nord","Norway":"Norvegia",
 "Pakistan":"Pakistan","Panama":"Panama","Papua New Guinea":"Papua-Noua Guinee",
 "Paraguay":"Paraguay","Peru":"Peru","Philippines":"Filipine","Poland":"Polonia",
 "Portugal":"Portugalia","Romania":"România","Russia":"Rusia","Saudi Arabia":"Arabia Saudită",
 "Serbia":"Serbia","Slovakia":"Slovacia","Slovenia":"Slovenia","Somalia":"Somalia",
 "South Africa":"Africa de Sud","South Korea":"Coreea de Sud","Spain":"Spania",
 "Sri Lanka":"Sri Lanka","Sudan":"Sudan","Sweden":"Suedia","Switzerland":"Elveția",
 "Syria":"Siria","Taiwan":"Taiwan","Tajikistan":"Tadjikistan","Tanzania":"Tanzania",
 "Thailand":"Thailanda","The Bahamas":"Bahamas","Tonga":"Tonga","Tunisia":"Tunisia",
 "Turkey":"Turcia","Türkiye":"Turcia","Turkmenistan":"Turkmenistan","Uganda":"Uganda",
 "Ukraine":"Ucraina","United Kingdom":"Regatul Unit","United States":"Statele Unite",
 "Uruguay":"Uruguay","Uzbekistan":"Uzbekistan","Vanuatu":"Vanuatu","Venezuela":"Venezuela",
 "Vietnam":"Vietnam","Yemen":"Yemen","Zambia":"Zambia","Zimbabwe":"Zimbabwe",
}


def ro_tari(text):
    """«Japan, China» -> «Japonia, China». Listele lungi se scurtează."""
    if not text:
        return ""
    parti = [TARI.get(x.strip(), x.strip()) for x in text.split(",") if x.strip()]
    if len(parti) > 3:
        return ", ".join(parti[:3]) + f" și încă {len(parti) - 3} țări"
    if len(parti) == 2:
        return f"{parti[0]} și {parti[1]}"
    return ", ".join(parti)


def _ia(url, timeout=40):
    cerere = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(cerere, timeout=timeout) as r:
        return r.read()


def cutremure(zi):
    """Cutremurele zilei, de la USGS, peste pragul de magnitudine."""
    url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
           f"&starttime={zi}&endtime={zi}T23:59:59&minmagnitude={PRAG_MAGNITUDINE}"
           "&orderby=magnitude")
    try:
        d = json.loads(_ia(url))
    except Exception as e:
        print(f"  USGS a dat greș: {e}", file=sys.stderr)
        return []
    ies = []
    for f in d.get("features", []):
        p = f.get("properties") or {}
        mag, loc = p.get("mag"), p.get("place")
        if mag is None or not loc:
            continue
        ies.append({
            "tip": "Cutremur",
            "text": ("Cutremur de magnitudine "
                     + f"{mag:.1f}".replace(".", ",")
                     + f", {_ro_loc(loc)}."),
            "sursa": "USGS",
            "link": p.get("url") or "",
            "cheie": f.get("id") or f"eq-{mag}-{loc}",
        })
    return ies


def gdacs(zi):
    """Dezastrele zilei din fluxul GDACS, doar nivel portocaliu și roșu."""
    try:
        brut = _ia("https://www.gdacs.org/xml/rss.xml")
        radacina = ET.fromstring(brut)
    except Exception as e:
        print(f"  GDACS a dat greș: {e}", file=sys.stderr)
        return []
    NS = {"gdacs": "http://www.gdacs.org"}
    ies = []
    for it in radacina.findall(".//item"):
        nivel = (it.findtext("gdacs:alertlevel", default="", namespaces=NS) or "").strip()
        if nivel not in NIVELURI:
            continue
        de_la = (it.findtext("gdacs:fromdate", default="", namespaces=NS) or "")
        if not _in_zi(de_la, zi):
            continue
        cod = (it.findtext("gdacs:eventtype", default="", namespaces=NS) or "").strip()
        text = _fraza(it, cod, NS)
        if not text:
            continue
        ies.append({
            "tip": TIPURI.get(cod, "Eveniment"),
            "text": text,
            "sursa": "GDACS",
            "link": (it.findtext("link") or "").strip(),
            "cheie": (it.findtext("gdacs:eventid", default="", namespaces=NS)
                      or text),
        })
    return ies


def _in_zi(data_text, zi):
    """GDACS scrie datele în format RFC 2822. Ne interesează doar ziua."""
    if not data_text:
        return False
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(data_text.strip()).strftime("%Y-%m-%d") == zi
    except Exception:
        return zi in data_text


def _fraza(it, cod, NS):
    """
    Construiește rândul în română din câmpurile GDACS, nu din titlul englezesc.

    Titlurile lor sunt telegrame tehnice („Orange notification for tropical
    cyclone SAUDEL-26. Population affected by…"). Câmpurile structurate —
    tip, nume, țară, bilanț — dau o propoziție curată fără să traducem nimic
    aproximativ. Iar bilanțul (morți, strămutați) NU e o explicație: e faptul
    însuși, exact ce ține un letopiseț.
    """
    tara = ro_tari(it.findtext("gdacs:country", default="", namespaces=NS))
    nume = (it.findtext("gdacs:eventname", default="", namespaces=NS) or "").strip()
    pop = (it.findtext("gdacs:population", default="", namespaces=NS) or "").strip()

    if cod == "VO":
        loc = f"{nume}, {tara}" if nume and tara else (nume or tara)
        baza = f"Erupție vulcanică la {loc}" if loc else "Erupție vulcanică"
    elif cod == "FL":
        baza = f"Inundații în {tara}" if tara else "Inundații"
    elif cod == "TC":
        baza = f"Ciclonul tropical {nume}" if nume else "Ciclon tropical"
        if tara:
            baza += f", peste {tara}"
    elif cod == "DR":
        baza = f"Secetă în {tara}" if tara else "Secetă"
    elif cod == "WF":
        baza = f"Incendiu de vegetație în {tara}" if tara else "Incendiu de vegetație"
    elif cod == "TS":
        baza = f"Tsunami în {tara}" if tara else "Tsunami"
    elif cod == "EQ":
        baza = f"Cutremur în {tara}" if tara else "Cutremur"
    else:
        return ""

    bilant = _bilant(pop)
    return f"{baza} — {bilant}." if bilant else f"{baza}."


def _bilant(pop):
    """«955 deaths and 3458 displaced» -> «955 de morți și 3.458 de strămutați»."""
    if not pop:
        return ""
    m_morti = re.search(r"([\d,\.]+)\s+deaths?", pop)
    m_stram = re.search(r"([\d,\.]+)\s+displaced", pop)
    def n(x):
        return f"{int(x.replace(',', '').replace('.', '')):,}".replace(",", ".")
    buc = []
    if m_morti:
        buc.append(f"{n(m_morti.group(1))} de morți")
    if m_stram:
        buc.append(f"{n(m_stram.group(1))} de strămutați")
    return " și ".join(buc)


def _curata(t):
    """Titlurile GDACS vin cu paranteze tehnice și spații duble."""
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(Green|Orange|Red)\s+", "", t)
    return t if t.endswith(".") else t + "."


def _ro_loc(loc):
    """«157 km E of Kokopo, Papua New Guinea» -> «la 157 km est de Kokopo…»"""
    P = {" N of ": " nord de ", " S of ": " sud de ", " E of ": " est de ",
         " W of ": " vest de ", " NE of ": " nord-est de ", " NW of ": " nord-vest de ",
         " SE of ": " sud-est de ", " SW of ": " sud-vest de ",
         " NNE of ": " nord-nord-est de ", " NNW of ": " nord-nord-vest de ",
         " SSE of ": " sud-sud-est de ", " SSW of ": " sud-sud-vest de ",
         " ENE of ": " est-nord-est de ", " ESE of ": " est-sud-est de ",
         " WNW of ": " vest-nord-vest de ", " WSW of ": " vest-sud-vest de "}
    for a, b in P.items():
        if a in loc:
            loc = loc.replace(a, b, 1)
            return "la " + _tara_din_coada(loc)
    # „off the coast of X" ar cere genitiv („în largul Americii Centrale"), iar
    # genitivul românesc nu se poate automatiza fără să iasă caraghios. Ocolim
    # construcția: „în larg, America Centrală" e corect pentru orice nume.
    if loc.lower().startswith("off the coast of"):
        return "în larg, " + _tara_din_coada(loc[16:].strip())
    if loc.lower().startswith("off "):
        return "în larg, " + _tara_din_coada(loc[4:].strip())
    return "în " + _tara_din_coada(loc)


# Regiunile oceanice și lanțurile de insule nu sunt țări, dar apar des la USGS
# — jumătate din cutremurele lumii se întâmplă în locuri fără nimeni în ele.
REGIUNI = {
 "Kermadec Islands region": "regiunea Insulelor Kermadec",
 "South Sandwich Islands region": "regiunea Insulelor Sandwich de Sud",
 "central Mid-Atlantic Ridge": "Dorsala Medio-Atlantică centrală",
 "northern Mid-Atlantic Ridge": "Dorsala Medio-Atlantică nordică",
 "southern Mid-Atlantic Ridge": "Dorsala Medio-Atlantică sudică",
 "Central America": "America Centrală",
 "Pacific-Antarctic Ridge": "Dorsala Pacific-Antarctica",
 "Southeast Indian Ridge": "Dorsala Indiană de Sud-Est",
 "Southwest Indian Ridge": "Dorsala Indiană de Sud-Vest",
 "Mid-Indian Ridge": "Dorsala Medio-Indiană",
 "Carlsberg Ridge": "Dorsala Carlsberg",
 "Owen Fracture Zone region": "zona de fractură Owen",
 "Balleny Islands region": "regiunea Insulelor Balleny",
 "Fiji region": "regiunea Fiji",
 "Tonga region": "regiunea Tonga",
 "Vanuatu region": "regiunea Vanuatu",
 "Bougainville region, Papua New Guinea": "regiunea Bougainville, Papua-Noua Guinee",
 "New Britain region, Papua New Guinea": "regiunea New Britain, Papua-Noua Guinee",
 "Santa Cruz Islands": "Insulele Santa Cruz",
 "Solomon Islands": "Insulele Solomon",
 "Andreanof Islands, Aleutian Islands, Alaska": "Insulele Andreanof, Aleutine, Alaska",
 "Rat Islands, Aleutian Islands, Alaska": "Insulele Rat, Aleutine, Alaska",
 "Fox Islands, Aleutian Islands, Alaska": "Insulele Fox, Aleutine, Alaska",
 "Alaska": "Alaska", "Hawaii": "Hawaii", "Puerto Rico": "Puerto Rico",
 "Greenland Sea": "Marea Groenlandei", "Sea of Okhotsk": "Marea Ohotsk",
 "Bering Sea": "Marea Bering", "Banda Sea": "Marea Banda",
 "Molucca Sea": "Marea Moluccelor", "Celebes Sea": "Marea Celebes",
 "Java Sea": "Marea Java", "Philippine Islands region": "regiunea Insulelor Filipine",
 "Kuril Islands": "Insulele Kurile", "Sakhalin, Russia": "Sahalin, Rusia",
 "Svalbard and Jan Mayen Region": "Svalbard și Jan Mayen",
 "off the west coast of northern Sumatra": "coasta de vest a Sumatrei de Nord",
 "South of the Fiji Islands": "sud de Insulele Fiji",
}


def _tara_din_coada(loc):
    """Ultimul segment după virgulă e țara — pe aceea o traducem."""
    loc = loc.strip()
    if loc in REGIUNI:
        return REGIUNI[loc]
    if "," in loc:
        cap, coada = loc.rsplit(",", 1)
        return f"{cap}, {TARI.get(coada.strip(), REGIUNI.get(coada.strip(), coada.strip()))}"
    return TARI.get(loc, REGIUNI.get(loc, loc))


def incarca():
    if not os.path.exists(FISIER):
        return {}
    with open(FISIER, encoding="utf-8") as fh:
        return json.load(fh)


def salveaza(d):
    os.makedirs(os.path.dirname(FISIER), exist_ok=True)
    with open(FISIER, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2, sort_keys=True)


def main():
    zi = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", zi):
        sys.exit("data se scrie 2026-09-05")

    tot = incarca()
    deja = {e.get("cheie") for e in tot.get(zi, [])}

    noi = []
    for e in cutremure(zi) + gdacs(zi):
        if e["cheie"] in deja:
            continue
        deja.add(e["cheie"])
        noi.append(e)

    if not noi:
        print(f"{zi}: nimic nou")
        return

    # Zilele nu se rescriu niciodată — se adaugă la coadă. Un letopiseț care
    # își corectează trecutul nu mai e letopiseț.
    tot.setdefault(zi, []).extend(noi)
    salveaza(tot)
    print(f"{zi}: {len(noi)} evenimente adăugate (total în zi: {len(tot[zi])})")
    for e in noi:
        print(f"   · {e['text'][:96]}")


if __name__ == "__main__":
    main()

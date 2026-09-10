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
# umple pagina cu evenimente pe care nu le-a observat nimeni — pentru inundații
# și secetă. Dar un uragan, un vulcan, un tsunami sau un incendiu mare sunt
# evenimente și când GDACS le dă verde (8 sept 2026, cerința fondatorului:
# „tot ce e natural": vulcani, tsunami, tornade, uragane, alunecări, incendii,
# temperaturi extreme, epidemii, El Niño / La Niña).
NIVELURI = ("Orange", "Red")                 # cu impact confirmat — intră întotdeauna
VERDE_OK = ("TC", "VO", "TS", "WF", "FL", "DR")   # toate tipurile intră și pe verde (9 sept 2026: „toate dezastrele naturale”)
PRAG_HECTARE = 5_000                          # incendiu: sub 5.000 ha e fum, nu dezastru
PRAG_VANT = 63                                # km/h: sub asta e depresiune tropicală, nu furtună

TIPURI = {
    "EQ": "Cutremur", "TC": "Ciclon tropical", "FL": "Inundație",
    "VO": "Erupție vulcanică", "DR": "Secetă", "WF": "Incendiu de vegetație",
    "TS": "Tsunami", "LS": "Alunecare de teren", "TE": "Temperaturi extreme",
}


# Numele de țări vin în engleză de la ambele surse. Traducem ce știm sigur și
# lăsăm restul cum e — un nume englezesc e mai bun decât o traducere greșită.
TARI = {
    "Democratic Republic of the Congo": "Republica Democrată Congo", "The Democratic Republic of Congo": "Republica Democrată Congo",
    "The Democratic Republic of the Congo": "Republica Democrată Congo", "Congo": "Congo", "Timor Leste": "Timor de Est", "Guam": "Guam",
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


STARE = os.path.join(ROOT, "data", "_letopiset_stare.json")   # per eveniment GDACS: vântul maxim și morții consemnați
CATEGORII = [(252, 5), (209, 4), (178, 3), (154, 2), (119, 1)]  # km/h → categoria Saffir-Simpson


def _categoria(kmh):
    for prag, cat in CATEGORII:
        if kmh >= prag:
            return cat
    return 0


def _stare():
    try:
        return json.load(open(STARE, encoding="utf-8")) if os.path.exists(STARE) else {}
    except Exception:
        return {}


def _salveaza_stare(st):
    with open(STARE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def escaladari(zi, toate_cheile=frozenset()):
    """Un letopiseț ține și CE SE ÎNTÂMPLĂ cu un eveniment, nu doar că a început:
    uraganul Lowell a lovit Hawaii la categoria 4 la zile după ce a apărut, iar
    bilanțul unei inundații crește de la o zi la alta. Intră: o furtună când atinge
    o categorie nouă (1–5) și orice eveniment când bilanțul morților crește cu ≥ 10
    sau depășește 100. Starea per eveniment se ține în data/_letopiset_stare.json."""
    try:
        radacina = ET.fromstring(_ia("https://www.gdacs.org/xml/rss_7d.xml"))
    except Exception as e:
        print(f"  GDACS (escaladări) a dat greș: {e}", file=sys.stderr)
        return []
    NS = {"gdacs": "http://www.gdacs.org"}
    st = _stare(); ies = []
    for it in radacina.findall(".//item"):
        cod = (it.findtext("gdacs:eventtype", default="", namespaces=NS) or "").strip()
        eid = (it.findtext("gdacs:eventid", default="", namespaces=NS) or "").strip()
        modificat = (it.findtext("gdacs:datemodified", default="", namespaces=NS) or "")
        if not eid or not _in_zi(modificat, zi):
            continue
        s_ev = st.setdefault(eid, {})
        tara = ro_tari(it.findtext("gdacs:country", default="", namespaces=NS))
        nume = re.sub(r"-\d+$", "", (it.findtext("gdacs:eventname", default="", namespaces=NS) or "").strip()).title()
        link = (it.findtext("link") or "").strip()
        if cod == "TC":
            m = re.search(r"(\d+)\s*km/h", it.findtext("gdacs:severity", default="", namespaces=NS) or "")
            kmh = int(m.group(1)) if m else 0
            cat = _categoria(kmh)
            if cat > s_ev.get("categoria", 0):
                s_ev["categoria"] = cat; s_ev["kmh"] = kmh
                cheie = f"{eid}-cat{cat}"
                if cheie not in toate_cheile:
                    text = f"Uraganul {nume} a atins categoria {cat} — vânt de {kmh} km/h" + (f", peste {tara}" if tara else "") + "."
                    ies.append({"tip": "Ciclon tropical", "text": text, "sursa": "GDACS", "link": link, "cheie": cheie})
        pop = it.findtext("gdacs:population", default="", namespaces=NS) or ""
        m = re.search(r"([\d,\.]+)\s+deaths?", pop)
        if m:
            morti = int(re.sub(r"[^\d]", "", m.group(1)) or 0)
            vechi = s_ev.get("morti", 0)
            if morti > vechi and (morti - vechi >= 10 or (morti >= 100 and vechi < 100)):
                s_ev["morti"] = morti
                cheie = f"{eid}-morti{morti}"
                if cheie not in toate_cheile:
                    ce = TIPURI.get(cod, "Dezastru")
                    text = f"{ce}{' ' + nume if nume and cod == 'TC' else ''}{', ' + tara if tara else ''}: bilanțul urcă la {morti:,} de morți.".replace(",", ".")
                    ies.append({"tip": ce, "text": text, "sursa": "GDACS", "link": link, "cheie": cheie})
            elif morti > vechi:
                s_ev["morti"] = morti
    _salveaza_stare(st)
    return ies


def gdacs(zi, toate_cheile=frozenset()):
    """Dezastrele zilei din fluxul GDACS (`toate_cheile` = ce e deja în jurnal, din orice zi)."""
    try:
        # rss_7d, nu rss: fluxul „curent” NU conținea erupția Krakatau (portocaliu, 4 sept 2026),
        # cel pe 7 zile da. Am aflat-o de la fondator, nu de la flux.
        brut = _ia("https://www.gdacs.org/xml/rss_7d.xml")
        radacina = ET.fromstring(brut)
    except Exception as e:
        print(f"  GDACS a dat greș: {e}", file=sys.stderr)
        return []
    NS = {"gdacs": "http://www.gdacs.org"}
    ies = []
    for it in radacina.findall(".//item"):
        nivel = (it.findtext("gdacs:alertlevel", default="", namespaces=NS) or "").strip()
        cod = (it.findtext("gdacs:eventtype", default="", namespaces=NS) or "").strip()
        sever = (it.findtext("gdacs:severity", default="", namespaces=NS) or "").strip()
        if nivel not in NIVELURI:
            if cod not in VERDE_OK:
                continue
            if cod == "WF":
                m = re.search(r"([\d,\.]+)\s*ha", sever)
                if not m or int(re.sub(r"[^\d]", "", m.group(1)) or 0) < PRAG_HECTARE:
                    continue
            if cod == "TC":
                m = re.search(r"(\d+)\s*km/h", sever)
                if m and int(m.group(1)) < PRAG_VANT:
                    continue
        de_la = (it.findtext("gdacs:fromdate", default="", namespaces=NS) or "")
        modificat = (it.findtext("gdacs:datemodified", default="", namespaces=NS) or "")
        cheie = (it.findtext("gdacs:eventid", default="", namespaces=NS) or "").strip()
        # Intră în ziua în care ÎNCEPE. Dar un eveniment început înainte, care abia acum
        # ajunge la portocaliu/roșu (erupția Krakatau: a început pe 4 sept, alerta a
        # urcat pe 8), intră în ziua în care GDACS l-a actualizat — dacă nu e deja în jurnal.
        if not _in_zi(de_la, zi):
            if not (nivel in NIVELURI and _in_zi(modificat, zi) and cheie and cheie not in toate_cheile):
                continue
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
        nivel = (it.findtext("gdacs:alertlevel", default="", namespaces=NS) or "").strip()
        if nivel in ("Orange", "Red"):
            baza += f" (alertă {'portocalie' if nivel == 'Orange' else 'roșie'})"
    elif cod == "FL":
        baza = f"Inundații în {tara}" if tara else "Inundații"
    elif cod == "TC":
        sever = (it.findtext("gdacs:severity", default="", namespaces=NS) or "")
        vant = re.search(r"(\d+)\s*km/h", sever)
        kmh = int(vant.group(1)) if vant else 0
        nume_curat = re.sub(r"-\d+$", "", nume).title() if nume else ""
        fel = "Uraganul" if kmh >= 119 else ("Furtuna tropicală" if kmh >= 63 else "Ciclonul tropical")
        baza = f"{fel} {nume_curat}" if nume_curat else fel
        if tara:
            baza += f", peste {tara}"
        if kmh:
            baza += f" — vânt de {kmh} km/h"
    elif cod == "DR":
        baza = f"Secetă în {tara}" if tara else "Secetă"
    elif cod == "WF":
        baza = f"Incendiu de vegetație în {tara}" if tara else "Incendiu de vegetație"
        sever = (it.findtext("gdacs:severity", default="", namespaces=NS) or "")
        m = re.search(r"([\d,\.]+)\s*ha", sever)
        if m:
            ha = int(re.sub(r"[^\d]", "", m.group(1)) or 0)
            baza += f" — {ha:,} de hectare".replace(",", ".")
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
    m_raza = re.search(r"About\s+([\d,\.]+)\s+people\s+within\s+(\d+)\s*km", pop, re.I)
    if not buc and m_raza:
        buc.append(f"circa {n(m_raza.group(1))} de oameni pe o rază de {m_raza.group(2)} km")
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
    "southern East Pacific Rise": "sudul Dorsalei Est-Pacifice", "East Pacific Rise": "Dorsala Est-Pacifică",
    "southeast of the Loyalty Islands": "sud-estul Insulelor Loyalty", "Loyalty Islands": "Insulele Loyalty",
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


# ─── NASA EONET: vulcani, incendii, furtuni, alunecări, temperaturi extreme ──
EONET_CAT = {
    "volcanoes": ("VO", "Activitate vulcanică"), "wildfires": ("WF", "Incendiu de vegetație"),
    "severeStorms": ("TC", "Furtună"), "landslides": ("LS", "Alunecare de teren"),
    "floods": ("FL", "Inundații"), "drought": ("DR", "Secetă"),
    "tempExtremes": ("TE", "Temperaturi extreme"), "earthquakes": ("EQ", "Cutremur"),
}


def eonet(zi):
    """Evenimentele NASA EONET care au avut o observație în ziua dată."""
    try:
        d = json.loads(_ia("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=3&limit=200"))
    except Exception as e:
        print(f"  NASA EONET a dat greș: {e}", file=sys.stderr)
        return []
    ies = []
    for ev in d.get("events", []):
        cat = (ev.get("categories") or [{}])[0].get("id", "")
        if cat not in EONET_CAT:
            continue
        geo = ev.get("geometry") or []
        zile = {g.get("date", "")[:10] for g in geo}
        # intră în ziua în care a APĂRUT (prima observație), ca să nu se repete zilnic
        if not geo or min(zile) != zi:
            continue
        cod, eticheta = EONET_CAT[cat]
        titlu = _ro_titlu_eonet(ev.get("title", ""), cod)
        ies.append({"tip": TIPURI.get(cod, eticheta), "text": f"{eticheta}: {titlu}. NASA EONET",
                    "sursa": "NASA EONET", "link": (ev.get("sources") or [{}])[0].get("url") or ev.get("link", ""),
                    "cheie": "eonet:" + str(ev.get("id"))})
    return ies


def _ro_titlu_eonet(t, cod):
    """Titlurile EONET sunt englezești și scurte: le curățăm, nu le traducem aproximativ."""
    t = re.sub(r"^(Wildfire|Wildfires|Volcano|Flood|Flooding|Landslide|Drought)\s*[-–:]\s*", "", t, flags=re.I)
    t = re.sub(r"\bHurricane\b", "Uraganul", t); t = re.sub(r"\bTyphoon\b", "Taifunul", t)
    t = re.sub(r"\bTropical Storm\b", "Furtuna tropicală", t); t = re.sub(r"\bCyclone\b", "Ciclonul", t)
    t = re.sub(r"\bTropical Depression\b", "Depresiunea tropicală", t)
    t = re.sub(r"\bTornado(es)?\b", "Tornadă", t)
    return ro_tari(t.strip())


# ─── OMS: focare și epidemii (Disease Outbreak News) ─────────────────────────
BOLI = {
    "ebola": "Ebola", "cholera": "holeră", "measles": "rujeolă", "mpox": "mpox", "marburg": "Marburg",
    "dengue": "dengue", "yellow fever": "febră galbenă", "avian influenza": "gripă aviară",
    "influenza": "gripă", "polio": "poliomielită", "poliovirus": "poliovirus", "plague": "ciumă",
    "nipah": "Nipah", "lassa": "Lassa", "mers": "MERS", "covid-19": "COVID-19", "meningitis": "meningită",
    "diphtheria": "difterie", "anthrax": "antrax", "rift valley fever": "febra Văii Rift",
    "chikungunya": "chikungunya", "zika": "Zika", "hepatitis": "hepatită", "malaria": "malarie",
    "oropouche": "Oropouche", "monkeypox": "mpox", "rabies": "rabie",
}


def oms(zi):
    """Comunicatele OMS de focar publicate în ziua dată."""
    try:
        d = json.loads(_ia("https://www.who.int/api/news/diseaseoutbreaknews?$top=20&$orderby=PublicationDate%20desc"))
    except Exception as e:
        print(f"  OMS a dat greș: {e}", file=sys.stderr)
        return []
    ies = []
    for x in d.get("value", []):
        if (x.get("PublicationDate") or "")[:10] != zi:
            continue
        titlu = (x.get("Title") or "").strip()
        boala = next((ro for en, ro in BOLI.items() if en in titlu.lower()), "")
        # „Ebola disease caused by Bundibugyo virus - Democratic Republic of the Congo”
        loc = ro_tari(titlu.split(" - ")[-1].split(", ")[-1].strip()) if (" - " in titlu or ", " in titlu) else ""
        text = f"Focar de {boala}" if boala else "Focar semnalat de OMS"
        if loc and loc.lower() not in text.lower():
            text += f", {loc}"
        text += f" — comunicat OMS: {titlu}."
        slug = x.get("UrlName") or x.get("ItemDefaultUrl") or ""
        ies.append({"tip": "Epidemie", "text": text, "sursa": "OMS",
                    "link": f"https://www.who.int/emergencies/disease-outbreak-news/item/{slug}" if slug and not slug.startswith("http") else slug,
                    "cheie": "oms:" + str(x.get("Id") or titlu)})
    return ies


# ─── NOAA: starea El Niño / La Niña — se consemnează doar când se SCHIMBĂ ────
ENSO_FISIER = os.path.join(ROOT, "data", "_letopiset_enso.txt")


def enso(zi):
    try:
        import html as _html
        t = _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
             _ia("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml").decode("utf-8", "ignore"))))
    except Exception as e:
        print(f"  NOAA ENSO a dat greș: {e}", file=sys.stderr)
        return []
    m = re.search(r"ENSO Alert System Status:\s*([A-Za-z\u00f1 \-]+?)\s+(?:Synopsis|$)", t)
    if not m:
        return []
    stare = m.group(1).strip()
    veche = open(ENSO_FISIER, encoding="utf-8").read().strip() if os.path.exists(ENSO_FISIER) else ""
    if stare == veche:
        return []
    with open(ENSO_FISIER, "w", encoding="utf-8") as f:
        f.write(stare)
    RO = {"El Niño Advisory": "El Niño în desfășurare (aviz NOAA)", "La Niña Advisory": "La Niña în desfășurare (aviz NOAA)",
          "El Niño Watch": "El Niño posibil în lunile următoare (NOAA)", "La Niña Watch": "La Niña posibilă în lunile următoare (NOAA)",
          "Not Active": "nici El Niño, nici La Niña (NOAA)", "Final El Niño Advisory": "El Niño s-a încheiat (NOAA)",
          "Final La Niña Advisory": "La Niña s-a încheiat (NOAA)"}
    return [{"tip": "El Niño / La Niña", "text": f"Starea Pacificului: {RO.get(stare, stare)}.", "sursa": "NOAA",
             "link": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
             "cheie": "enso:" + stare}]


# ─── NOAA SPC: tornadele zilei (SUA — singura sursă zilnică gratuită) ────────
def tornade(zi):
    yymmdd = zi[2:4] + zi[5:7] + zi[8:10]
    try:
        brut = _ia(f"https://www.spc.noaa.gov/climo/reports/{yymmdd}_rpts_torn.csv").decode("utf-8", "ignore")
    except Exception as e:
        if "404" not in str(e):          # 404 = raportul zilei nu e încă publicat; normal la 23:50
            print(f"  SPC tornade a dat greș: {e}", file=sys.stderr)
        return []
    import csv, io, collections
    randuri = [r for r in csv.DictReader(io.StringIO(brut)) if r.get("State")]
    if not randuri:
        return []
    state = collections.Counter(r["State"].strip() for r in randuri)
    lista = ", ".join(f"{st} ({n})" if n > 1 else st for st, n in state.most_common())
    n = len(randuri)
    text = f"{n} tornad{'ă' if n == 1 else 'e'} raportat{'ă' if n == 1 else 'e'} în SUA — {lista}."
    return [{"tip": "Tornadă", "text": text, "sursa": "NOAA SPC",
             "link": f"https://www.spc.noaa.gov/climo/reports/{yymmdd}_rpts.html", "cheie": f"spc:{zi}"}]


# ─── Temperaturi neobișnuite pentru perioadă (Open-Meteo: azi vs. media 1991–2020) ──
ORASE = [
    ("București", 44.43, 26.10), ("Cluj-Napoca", 46.77, 23.59), ("Iași", 47.16, 27.59), ("Timișoara", 45.75, 21.23),
    ("Constanța", 44.18, 28.63), ("Chișinău", 47.01, 28.86), ("Copenhaga", 55.68, 12.57), ("Oslo", 59.91, 10.75),
    ("Stockholm", 59.33, 18.07), ("Helsinki", 60.17, 24.94), ("Londra", 51.51, -0.13), ("Paris", 48.86, 2.35),
    ("Berlin", 52.52, 13.41), ("Varșovia", 52.23, 21.01), ("Viena", 48.21, 16.37), ("Roma", 41.90, 12.50),
    ("Madrid", 40.42, -3.70), ("Lisabona", 38.72, -9.14), ("Atena", 37.98, 23.73), ("Istanbul", 41.01, 28.98),
    ("Kiev", 50.45, 30.52), ("Moscova", 55.76, 37.62), ("Reykjavik", 64.15, -21.94), ("Cairo", 30.04, 31.24),
    ("Lagos", 6.52, 3.38), ("Nairobi", -1.29, 36.82), ("Johannesburg", -26.20, 28.05), ("Casablanca", 33.57, -7.59),
    ("Riad", 24.71, 46.68), ("Dubai", 25.20, 55.27), ("Teheran", 35.69, 51.39), ("Karachi", 24.86, 67.01),
    ("Delhi", 28.61, 77.21), ("Mumbai", 19.08, 72.88), ("Dhaka", 23.81, 90.41), ("Bangkok", 13.76, 100.50),
    ("Jakarta", -6.21, 106.85), ("Manila", 14.60, 120.98), ("Hanoi", 21.03, 105.85), ("Beijing", 39.90, 116.40),
    ("Shanghai", 31.23, 121.47), ("Hong Kong", 22.32, 114.17), ("Tokyo", 35.68, 139.69), ("Seul", 37.57, 126.98),
    ("Ulan Bator", 47.89, 106.91), ("Novosibirsk", 55.03, 82.92), ("Iakutsk", 62.03, 129.73), ("Sydney", -33.87, 151.21),
    ("Melbourne", -37.81, 144.96), ("Perth", -31.95, 115.86), ("Auckland", -36.85, 174.76), ("Anchorage", 61.22, -149.90),
    ("Vancouver", 49.28, -123.12), ("Toronto", 43.65, -79.38), ("New York", 40.71, -74.01), ("Chicago", 41.88, -87.63),
    ("Phoenix", 33.45, -112.07), ("Los Angeles", 34.05, -118.24), ("Houston", 29.76, -95.37), ("Miami", 25.76, -80.19),
    ("Ciudad de México", 19.43, -99.13), ("Bogotá", 4.71, -74.07), ("Lima", -12.05, -77.04), ("São Paulo", -23.55, -46.63),
    ("Buenos Aires", -34.60, -58.38), ("Santiago de Chile", -33.45, -70.67), ("Nuuk", 64.18, -51.72), ("Longyearbyen", 78.22, 15.63),
    # lumea, mai des decât acasă (9 sept 2026: „mă interesează mai mult în lume”)
    ("Denver", 39.74, -104.99), ("Dallas", 32.78, -96.80), ("Seattle", 47.61, -122.33), ("Montreal", 45.50, -73.57),
    ("Havana", 23.11, -82.37), ("Panama", 8.98, -79.52), ("Caracas", 10.48, -66.90), ("Quito", -0.18, -78.47),
    ("La Paz", -16.50, -68.15), ("Asunción", -25.26, -57.58), ("Montevideo", -34.90, -56.16), ("Brasília", -15.79, -47.88),
    ("Rio de Janeiro", -22.91, -43.17), ("Manaus", -3.12, -60.02), ("Accra", 5.60, -0.19), ("Dakar", 14.72, -17.47),
    ("Addis Abeba", 9.02, 38.75), ("Khartoum", 15.50, 32.56), ("Kinshasa", -4.44, 15.27), ("Dar es Salaam", -6.79, 39.28),
    ("Luanda", -8.84, 13.23), ("Antananarivo", -18.88, 47.51), ("Cape Town", -33.92, 18.42), ("Alger", 36.75, 3.06),
    ("Tunis", 36.81, 10.18), ("Tripoli", 32.89, 13.19), ("Bagdad", 33.34, 44.40), ("Kabul", 34.53, 69.17),
    ("Tașkent", 41.30, 69.24), ("Astana", 51.17, 71.43), ("Almaty", 43.24, 76.89), ("Kathmandu", 27.72, 85.32),
    ("Yangon", 16.87, 96.20), ("Kuala Lumpur", 3.14, 101.69), ("Singapore", 1.35, 103.82), ("Taipei", 25.03, 121.57),
    ("Osaka", 34.69, 135.50), ("Vladivostok", 43.12, 131.89), ("Brisbane", -27.47, 153.03), ("Darwin", -12.46, 130.84),
    ("Port Moresby", -9.44, 147.18), ("Suva", -18.14, 178.44), ("Honolulu", 21.31, -157.86), ("Murmansk", 68.97, 33.08),
    ("Tromsø", 69.65, 18.96), ("Utqiagvik (Barrow)", 71.29, -156.79), ("Yellowknife", 62.45, -114.37), ("Fairbanks", 64.84, -147.72),
    ("Punta Arenas", -53.16, -70.91), ("Ushuaia", -54.80, -68.30), ("Stația McMurdo (Antarctica)", -77.85, 166.67),
    ("Dublin", 53.35, -6.26), ("Amsterdam", 52.37, 4.90), ("Zürich", 47.38, 8.54), ("Praga", 50.08, 14.44),
    ("Budapesta", 47.50, 19.04), ("Belgrad", 44.79, 20.45), ("Sofia", 42.70, 23.32), ("Tbilisi", 41.72, 44.79),
    ("Ankara", 39.93, 32.86), ("Tel Aviv", 32.08, 34.78), ("Jeddah", 21.49, 39.19), ("Muscat", 23.59, 58.41),
    ("Colombo", 6.93, 79.85), ("Chennai", 13.08, 80.27), ("Lahore", 31.55, 74.34), ("Chongqing", 29.56, 106.55),
    ("Harbin", 45.80, 126.53), ("Sapporo", 43.06, 141.35), ("Adelaide", -34.93, 138.60),
    ("Wellington", -41.29, 174.78), ("Nouméa", -22.28, 166.46), ("Papeete", -17.54, -149.57), ("Tórshavn", 62.01, -6.77),
]
ACASA = {"București", "Cluj-Napoca", "Iași", "Timișoara", "Constanța", "Chișinău"}
MAX_ACASA_PE_ZI = 2
NORMALE = os.path.join(ROOT, "data", "_letopiset_normale.json")
PRAG_ANOMALIE = 8.0        # °C peste/sub media zilei (1991–2020) ca să fie „neobișnuit”
MAX_ORASE_PE_ZI = 8


def _normale():
    """Per oraș și zi a anului: [media maximelor 1991–2020, maxima și minima din 2016–2025],
    pe o fereastră de ±3 zile. Un singur apel la arhiva ERA5 per oraș, apoi pe disc.
    Cele două extreme din ultimii 10 ani sunt testul de „ieșit din comun” (9 sept 2026):
    o zi care arată ca ultimii zece ani nu e nimic special, oricât ar fi peste media
    pe 30 de ani."""
    try:
        cache = json.load(open(NORMALE, encoding="utf-8")) if os.path.exists(NORMALE) else {}
    except Exception:
        cache = {}
    # formatul vechi (doar media) se aruncă și se reface
    cache = {k: v for k, v in cache.items() if v and isinstance(next(iter(v.values())), list)}
    schimbat = False
    # Arhiva Open-Meteo limitează cererile grele (30 de ani de date = o cerere „scumpă”):
    # peste ~8 într-un minut dă 429. Umplem cache-ul treptat, câteva orașe pe rulare,
    # cu pauză între ele — în câteva zile sunt toate, și nu mai cerem niciodată.
    import time
    noi_pe_rulare, PAUZA = 6, 4
    for nume, lat, lon in sorted(ORASE, key=lambda o: o[0] in ACASA):
        if nume in cache:
            continue
        if noi_pe_rulare <= 0:
            break
        d = None
        for incercare in (1, 2):
            try:
                d = json.loads(_ia(f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
                                   f"&start_date=1991-01-01&end_date=2025-12-31&daily=temperature_2m_max&timezone=UTC", timeout=90))
                break
            except Exception as e:
                if "429" in str(e) and incercare == 1:
                    time.sleep(30); continue
                print(f"  normale {nume}: {e}", file=sys.stderr)
        if not d:
            break          # limita e atinsă; restul orașelor intră la rulările următoare
        noi_pe_rulare -= 1
        time.sleep(PAUZA)
        try:
            zile = d["daily"]["time"]; val = d["daily"]["temperature_2m_max"]
        except Exception as e:
            print(f"  normale {nume}: {e}", file=sys.stderr)
            continue
        from datetime import date, timedelta
        baza_pe_zi, recent_pe_zi = {}, {}
        for z, v in zip(zile, val):
            if v is None:
                continue
            an = int(z[:4])
            if 1991 <= an <= 2020:
                baza_pe_zi.setdefault(z[5:], []).append(v)
            if 2016 <= an <= 2025:
                recent_pe_zi.setdefault(z[5:], []).append(v)
        # fereastră de ±3 zile în jurul fiecărei zile, ca să nu depindă de o singură dată
        med = {}
        for k in sorted(baza_pe_zi):
            m, dd = int(k[:2]), int(k[3:])
            try:
                b = date(2020, m, dd)
            except ValueError:
                continue
            vb, vr = [], []
            for off in range(-3, 4):
                kk = (b + timedelta(days=off)).strftime("%m-%d")
                vb += baza_pe_zi.get(kk, []); vr += recent_pe_zi.get(kk, [])
            if vb and vr:
                med[k] = [round(sum(vb) / len(vb), 1), round(max(vr), 1), round(min(vr), 1)]
        cache[nume] = med
        schimbat = True
    if schimbat:
        with open(NORMALE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    return cache


def temperaturi(zi):
    """Orașele unde maxima zilei a fost cu ≥ PRAG_ANOMALIE °C peste sau sub media zilei (1991–2020)."""
    normale = _normale()
    try:
        lat = ",".join(str(o[1]) for o in ORASE); lon = ",".join(str(o[2]) for o in ORASE)
        d = json.loads(_ia(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                           f"&daily=temperature_2m_max&timezone=UTC&start_date={zi}&end_date={zi}", timeout=90))
    except Exception as e:
        print(f"  Open-Meteo a dat greș: {e}", file=sys.stderr)
        return []
    if isinstance(d, dict):
        d = [d]
    gasite = []
    for (nume, _, _), x in zip(ORASE, d):
        try:
            azi_max = x["daily"]["temperature_2m_max"][0]
        except Exception:
            continue
        n = normale.get(nume, {}).get(zi[5:])
        if azi_max is None or not n:
            continue
        med, max10, min10 = n
        dif = azi_max - med
        # ieșit din comun = și departe de media pe 30 de ani, ȘI dincolo de extremele
        # ultimilor 10 ani pentru perioada asta. Dacă ultimii zece ani au mai avut așa
        # ceva, nu e nimic special — nu intră.
        if dif >= PRAG_ANOMALIE and azi_max > max10:
            gasite.append((abs(dif), dif, nume, azi_max, med, max10))
        elif dif <= -PRAG_ANOMALIE and azi_max < min10:
            gasite.append((abs(dif), dif, nume, azi_max, med, min10))
    gasite.sort(reverse=True)
    ies, acasa = [], 0
    for _, dif, nume, azi_max, med, extrem10 in gasite:
        if len(ies) >= MAX_ORASE_PE_ZI:
            break
        if nume in ACASA:
            if acasa >= MAX_ACASA_PE_ZI:
                continue
            acasa += 1
        if dif > 0:
            t = (f"Căldură ieșită din comun la {nume}: maximă de {azi_max:.0f} °C — cu {dif:.0f} °C peste media "
                 f"zilei (1991–2020: {med:.0f} °C) și peste orice maximă din ultimii 10 ani în perioada asta ({extrem10:.0f} °C).")
        else:
            t = (f"Frig ieșit din comun la {nume}: maximă de doar {azi_max:.0f} °C — cu {abs(dif):.0f} °C sub media "
                 f"zilei (1991–2020: {med:.0f} °C) și sub orice maximă din ultimii 10 ani în perioada asta ({extrem10:.0f} °C).")
        ies.append({"tip": "Temperaturi extreme", "text": t, "sursa": "Open-Meteo / ERA5",
                    "link": "https://open-meteo.com/", "cheie": f"temp:{zi}:{nume}"})
    return ies


# ─── NOAA: indicele Niño 3.4, săptămânal — cifra din spatele lui El Niño / La Niña ──
def nino34(zi):
    try:
        t = _ia("https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for").decode("utf-8", "ignore")
    except Exception as e:
        print(f"  NOAA Niño 3.4 a dat greș: {e}", file=sys.stderr)
        return []
    ultimul = [l for l in t.splitlines() if re.match(r"\s*\d{2}[A-Z]{3}\d{4}", l)]
    if not ultimul:
        return []
    l = ultimul[-1]
    m = re.match(r"\s*(\d{2}[A-Z]{3}\d{4})\s+([\d.]+)\s*(-?[\d.]+)\s+([\d.]+)\s*(-?[\d.]+)\s+([\d.]+)\s*(-?[\d.]+)\s+([\d.]+)\s*(-?[\d.]+)", l)
    if not m:
        return []
    saptamana, anom34 = m.group(1), float(m.group(7))     # a treia coloană = Niño 3.4
    stare_f = ENSO_FISIER + ".nino34"
    veche = open(stare_f, encoding="utf-8").read().strip() if os.path.exists(stare_f) else ""
    if saptamana == veche:
        return []
    with open(stare_f, "w", encoding="utf-8") as f:
        f.write(saptamana)
    fel = "El Niño" if anom34 >= 0.5 else ("La Niña" if anom34 <= -0.5 else "neutru")
    from datetime import datetime as _dt
    try:
        cand = _dt.strptime(saptamana, "%d%b%Y").strftime("%d.%m.%Y")
    except ValueError:
        cand = saptamana
    semn = "+" if anom34 >= 0 else "−"
    text = (f"Indicele Niño 3.4 (Pacificul ecuatorial), săptămâna din {cand}: {semn}{abs(anom34):.1f} °C față de normal "
            f"— {fel}.").replace(".0 °C", " °C")
    return [{"tip": "El Niño / La Niña", "text": text, "sursa": "NOAA CPC",
             "link": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
             "cheie": "nino34:" + saptamana}]


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
    toate_cheile = frozenset(str(e.get("cheie")) for z in tot for e in tot[z])

    noi = []
    # Dedupare între surse: furtuna „Lowell” vine și de la GDACS, și de la NASA.
    for e in cutremure(zi) + gdacs(zi, toate_cheile) + escaladari(zi, toate_cheile) + eonet(zi) + tornade(zi) + temperaturi(zi) + oms(zi) + enso(zi) + nino34(zi):
        nume_furtuna = re.search(r"(?:Uraganul|Furtuna tropicală|Taifunul|Ciclonul)\s+([A-Z][a-z]+)", e["text"])
        if nume_furtuna and any(nume_furtuna.group(1) in x["text"] for x in noi + tot.get(zi, [])):
            continue
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

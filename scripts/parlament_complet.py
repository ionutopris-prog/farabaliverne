#!/usr/bin/env python3
"""
Rosterul COMPLET al Parlamentului — toți deputații și senatorii, din sursă oficială.

Diferit de `parlamentari.py`, care ia doar câteva grupuri pentru secțiunea
„Cloșcu". Ăsta nu se uită la partid: ia pe toată lumea, pentru secțiunea
„Parlamentul României". Un parlamentar cu multe intervenții și unul cu zero
apar la fel — datele sunt datele.

Sursa: indexul pe circumscripție electorală de pe cdep.ro,
`structura2015.ce?cir=N`, plus echivalentul de la Senat.

Capcană numerotare: parametrul `cir` e decalat cu 1 față de numărul afișat al
circumscripției — `cir=31` întoarce „Circumscripţia electorală nr.32". Numărul
real se citește din pagină, nu se deduce din parametru.

    python3 scripts/parlament_complet.py            # scrie data/_parlament.json
    python3 scripts/parlament_complet.py --arata    # doar afișează
"""
import html, json, os, re, sys, time, urllib.request

CDEP = "https://www.cdep.ro"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FaraBaliverne/1.0)"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ia(url, incercari=3):
    for i in range(incercari):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == incercari - 1:
                print(f"  ⚠️  {url}: {e}")
                return ""
            time.sleep(2 * (i + 1))
    return ""


def curata(s):
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def grup(cam, idg):
    """Toți membrii unui grup parlamentar. Sursa completă: indexul pe
    circumscripție NU conține deputații minorităților (aleși la nivel național)
    și nu are deloc Senatul — de-aia numărătoarea pe județe dădea 316 în loc de
    330. Grupurile îi conțin pe toți, inclusiv neafiliații."""
    s = ia(f"{CDEP}/ords/pls/parlam/structura2015.gp?leg=2024&cam={cam}&idg={idg}")
    if not s:
        return "", []
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", s) or re.search(r"(?i)Grupul parlamentar[^<]{0,70}", s)
    nume_grup = curata(re.sub(r"<[^>]+>", " ", m.group(0))) if m else f"grup {idg}"
    # Pagina are DOUĂ tabele: membrii de ACUM și foștii membri, al doilea având
    # în antet coloana „până". Numărând ambele ieșeau 557 de parlamentari în loc
    # de 464. Filtrul pe număr de celule NU merge — și tabelul curent are uneori
    # o coloană în plus (funcția în grup). Ne uităm la ANTET.
    oameni = []
    for tab in re.findall(r"(?is)<table[^>]*>(.*?)</table>", s):
        if "structura2015.mp" not in tab:
            continue
        antet = curata(re.sub(r"<[^>]+>", " ", tab[:1200])).lower()
        if "până" in antet or "pana" in antet:
            continue                      # tabelul foștilor membri
        for idm, txt in re.findall(
                rf'structura2015\.mp\?idm=(\d+)(?:&amp;|&)cam={cam}(?:&amp;|&)leg=2024"[^>]*>(.*?)</a>',
                tab, re.S):
            nume = curata(re.sub(r"<[^>]+>", " ", txt))
            if nume and not any(o["id"] == idm for o in oameni):
                oameni.append({
                    "nume": nume, "id": idm,
                    "camera": "Camera Deputaților" if cam == 2 else "Senat",
                    "grup": nume_grup,
                    "fisa": f"{CDEP}/ords/pls/parlam/structura2015.mp?idm={idm}&cam={cam}&leg=2024",
                })
    return nume_grup, oameni


def circumscriptii(cam):
    """id parlamentar -> (numar, nume județ), din indexul pe circumscripție."""
    harta = {}
    for cir in range(1, 45):
        s = ia(f"{CDEP}/ords/pls/parlam/structura2015.ce?cir={cir}&leg=2024&cam={cam}")
        if not s:
            continue
        m = re.search(r"Circumscrip[^<]*?nr\.(\d+)\s*-\s*([^<]+)", html.unescape(s))
        if not m:
            continue
        numar, jud = int(m.group(1)), curata(m.group(2))
        for idm in re.findall(rf'structura2015\.mp\?idm=(\d+)(?:&amp;|&)cam={cam}', s):
            harta[idm] = (numar, jud)
        time.sleep(0.25)
    return harta


# ─── completare + așezare în sală ──────────────────────────────────────────
def completeaza_din_fise(oameni):
    """Circumscripţia de pe fişa proprie, pentru cine n-a prins-o din index.

    Indexul pe circumscripţie acoperă bine Camera, dar Senatul doar parţial.
    Fişa fiecăruia o are scrisă în clar: „ales senator în circumscriptia
    electorala nr.33 SĂLAJ".
    """
    lipsa = [o for o in oameni if "circumscriptie" not in o]
    print(f"completez {len(lipsa)} fişe individuale…")
    gasite = 0
    for i, o in enumerate(lipsa, 1):
        s = ia(o["fisa"])
        m = re.search(r"circumscriptia electorala nr\.(\d+)\s*([A-ZĂÂÎŞŢSȘȚ\- ]+)",
                      html.unescape(s))
        if m:
            o["circumscriptie_nr"] = int(m.group(1))
            o["circumscriptie"] = curata(m.group(2)).title()
            gasite += 1
        else:
            o["circumscriptie_nr"] = None
            o["circumscriptie"] = "la nivel naţional"
        if i % 20 == 0:
            print(f"  {i}/{len(lipsa)}")
        time.sleep(0.25)
    print(f"  găsite: {gasite} · rămase la nivel naţional: {len(lipsa) - gasite}")


def aseaza(oameni):
    """Locul fiecăruia în hemiciclu.

    Regula, din regulamente: locurile se dau PE GRUP — Art. 18 din Regulamentul
    Camerei (preşedintele împreună cu liderii de grup), Art. 20 din Regulamentul
    Senatului (prin negociere între lideri, în ordinea descrescătoare a mărimii
    grupurilor). Blocurile respectă deci ordinea de mărime.

    Poziţia fiecărui om ÎN INTERIORUL blocului nu o publică nimeni. E alfabetică
    aici, şi asta scrie şi pe pagină — o ordine inventată prezentată ca oficială
    ar fi exact minciuna pe care site-ul o vânează la alţii.
    """
    import unicodedata
    def cheie(n):
        return "".join(c for c in unicodedata.normalize("NFD", n.lower())
                       if unicodedata.category(c) != "Mn")

    for camera in ("Camera Deputaților", "Senat"):
        ai_camerei = [o for o in oameni if o["camera"] == camera]
        pe_grup = {}
        for o in ai_camerei:
            pe_grup.setdefault(o["grup"], []).append(o)
        ordine = sorted(pe_grup, key=lambda g: (-len(pe_grup[g]), g))
        loc = 0
        for rang, g in enumerate(ordine, 1):
            for i, o in enumerate(sorted(pe_grup[g], key=lambda x: cheie(x["nume"])), 1):
                loc += 1
                o["bloc"] = rang
                o["loc_in_bloc"] = i
                o["loc"] = loc
        print(f"  {camera}: {len(ai_camerei)} locuri, {len(ordine)} blocuri")


def main():
    arata = "--arata" in sys.argv
    toti = []
    for cam, eticheta in ((2, "Camera Deputaților"), (1, "Senat")):
        print(f"\n═══ {eticheta} ═══")
        for idg in list(range(0, 12)):
            nume_grup, oameni = grup(cam, idg)
            if oameni:
                print(f"  {len(oameni):>3}  {nume_grup[:58]}")
                toti.extend(oameni)
            time.sleep(0.3)
        print(f"  ── subtotal: {sum(1 for o in toti if o['camera'] == eticheta)}")

    print("\nataşez circumscripţiile…")
    for cam in (2, 1):
        h = circumscriptii(cam)
        for o in toti:
            if o["id"] in h and (o["camera"] == "Camera Deputaților") == (cam == 2):
                o["circumscriptie_nr"], o["circumscriptie"] = h[o["id"]]
    fara = [o for o in toti if "circumscriptie" not in o]
    print(f"  fără circumscripţie: {len(fara)} (normal: deputaţii minorităţilor, aleşi naţional)")

    completeaza_din_fise(toti)
    print("\naşez în sală…")
    aseaza(toti)

    print(f"\nTOTAL: {len(toti)} parlamentari")
    if arata:
        return
    out = {
        "sursa": [f"{CDEP}/ords/pls/parlam/structura2015.gp",
                  f"{CDEP}/ords/pls/parlam/structura2015.ce"],
        "legislatura": "2024-2028",
        "actualizat": time.strftime("%Y-%m-%d"),
        "oameni": toti,
    }
    with open(os.path.join(ROOT, "data", "_parlament.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("scris: data/_parlament.json")


if __name__ == "__main__":
    main()



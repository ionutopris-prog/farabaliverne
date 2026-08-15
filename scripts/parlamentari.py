"""
Rosterul oficial: toți deputații și senatorii AUR / POT / SOS, din sursă primară.

De ce din sursele oficiale și nu din presă: numele, partidul și mandatul trebuie
să fie de necontestat. cdep.ro și senat.ro sunt publice, gratuite și verificabile
de oricine — exact ce cere regula casei („fără sursă reală, nu publicăm").

Atenție la o capcană: cdep.ro a mutat totul sub `/ords/`. Vechile adrese
`/pls/parlam/...` întorc 404, nu redirect — deci un scraper scris după memorie
pare că „nu găsește nimic", când de fapt bate la ușa greșită.

Rulare:
    python3 scripts/parlamentari.py            # scrie data/parlamentari.json
    python3 scripts/parlamentari.py --arata    # doar afișează, nu scrie
"""

import html
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IESIRE = os.path.join(ROOT, "data", "parlamentari.json")

CDEP = "https://www.cdep.ro"
SENAT = "https://www.senat.ro"
UA = {"User-Agent": "Mozilla/5.0 (farabaliverne roster; contact@farabaliverne.ro)"}

# Partidele urmărite în secțiunea „Cloșcu cu Puii de AUR".
TINTE = {
    "AUR": ("aur", "alianța pentru unirea românilor", "alianta pentru unirea romanilor"),
    "POT": ("partidul oamenilor tineri", "p.o.t.", "pot"),
    "SOS": ("s.o.s.", "sos românia", "sos romania"),
}


def ia(url, incercari=3):
    for i in range(incercari):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if i == incercari - 1:
                print(f"::warning::n-am putut lua {url} ({type(e).__name__})")
                return ""
            time.sleep(2 * (i + 1))
    return ""


def text(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def partid_din(titlu):
    t = titlu.lower()
    for cod, chei in TINTE.items():
        for k in chei:
            # „aur" e și cuvânt obișnuit (medalie de aur), deci pentru codul scurt
            # cerem potrivire pe cuvânt întreg, nu pe subșir.
            if re.search(rf"(?<![a-zăâîșț]){re.escape(k)}(?![a-zăâîșț])", t):
                return cod
    return None


# Grupuri pe care cdep.ro NU le afișează cu nume în pagină (headingul e gol).
# idg=6 îl conține pe liderul POT, Anamaria Gavrilă, și are 24 de membri — dar
# fiindcă site-ul nu confirmă denumirea, îl marcăm ca atare și NU îl prezentăm
# public drept POT până nu confirmăm din altă sursă oficială.
GRUPURI_FARA_NUME = {6: "POT?"}


def deputati():
    """Grupurile din Camera Deputaților (idg necunoscut → le încercăm pe toate)."""
    out = []
    for idg in range(0, 14):
        url = f"{CDEP}/ords/pls/parlam/structura2015.gp?leg=2024&cam=2&idg={idg}"
        s = ia(url)
        if not s:
            continue
        m = re.search(r"<title>(.*?)</title>", s, re.S)
        titlu = text(m.group(1)) if m else ""
        # Titlul paginii e generic; numele grupului apare în corp.
        cap = text(s)[:600]
        cod = partid_din(titlu) or partid_din(cap)
        membri = re.findall(
            r'structura2015\.mp\?idm=(\d+)&amp;cam=2&amp;leg=2024[^>]*>\s*([^<]+?)\s*</a>', s)
        if not membri:
            membri = re.findall(
                r'structura2015\.mp\?idm=(\d+)[^>]*>\s*([^<]+?)\s*</a>', s)
        print(f"  idg={idg:<3} {cod or '—':<4} {len(membri):>3} membri · {cap[:70]}")
        if cod and membri:
            vazut = set()
            for idm, nume in membri:
                if idm in vazut:
                    continue
                vazut.add(idm)
                out.append({"nume": html.unescape(nume).strip(), "partid": cod,
                            "camera": "Camera Deputaților", "id": idm,
                            "fisa": f"{CDEP}/ords/pls/parlam/structura2015.mp?idm={idm}&cam=2&leg=2024"})
    return out


def senatori():
    out = []
    s = ia(f"{SENAT}/EnumGrupuri.aspx")
    grupuri = re.findall(r"ComponentaGrupuri\.aspx\?Zi&GrupID=([0-9a-fA-F-]+)'[^>]*>([^<]+)<", s)
    for gid, titlu in grupuri:
        cod = partid_din(html.unescape(titlu))
        if not cod:
            continue
        g = ia(f"{SENAT}/ComponentaGrupuri.aspx?Zi&GrupID={gid}")
        membri = re.findall(
            r"FisaSenator\.aspx\?ParlamentarID=([0-9a-fA-F-]+)'[^>]*>\s*([^<]+?)\s*</a>", g)
        vazut = set()
        for pid, nume in membri:
            if pid.upper() in vazut:
                continue
            vazut.add(pid.upper())
            out.append({"nume": html.unescape(nume).strip(), "partid": cod,
                        "camera": "Senat", "id": pid,
                        "fisa": f"{SENAT}/FisaSenator.aspx?ParlamentarID={pid}"})
        print(f"  {cod:<4} {len(vazut):>3} senatori · {html.unescape(titlu)[:60]}")
    return out


def main():
    print("Camera Deputaților:")
    d = deputati()
    print("\nSenat:")
    s = senatori()
    toti = d + s

    print(f"\n{'='*54}")
    for cod in TINTE:
        dep = sum(1 for x in toti if x["partid"] == cod and x["camera"] != "Senat")
        sen = sum(1 for x in toti if x["partid"] == cod and x["camera"] == "Senat")
        print(f"  {cod:<4} {dep:>3} deputați + {sen:>3} senatori = {dep+sen}")
    print(f"  {'TOTAL':<4} {len(toti)}")

    if "--arata" in sys.argv:
        return
    json.dump({"sursa": [CDEP, SENAT], "legislatura": "2024-2028", "oameni": toti},
              open(IESIRE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nscris {IESIRE}")


if __name__ == "__main__":
    main()

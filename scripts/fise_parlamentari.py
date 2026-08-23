#!/usr/bin/env python3
"""
Extrage fişa completă a fiecărui parlamentar de pe cdep.ro → data/_fise.json.

Ce ia (tot ce publică sursa oficială): data naşterii, e-mail, formaţiunea,
grupul cu istoricul lui, comisiile permanente şi speciale cu funcţia deţinută,
grupurile de prietenie, activitatea în cifre (luări de cuvânt, propuneri
legislative iniţiate şi câte au devenit legi, întrebări şi interpelări),
BIROURILE PARLAMENTARE cu adresele lor, şi legăturile spre CV, declaraţia de
avere, declaraţia de interese şi votul electronic.

Notă de corectat o afirmaţie anterioară: biroul parlamentar NU lipseşte. Lista
de contacte de pe cdep.ro are coloana goală, dar fişa individuală conţine
adresele reale — uneori două, în localităţi diferite din circumscripţie.

    python3 scripts/fise_parlamentari.py          # toţi
    python3 scripts/fise_parlamentari.py 20       # primii 20, pentru probă
"""
import html, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Mozilla/5.0 (compatible; FaraBaliverne/1.0)"}


def ia(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == 2:
                return ""
            time.sleep(1.5 * (i + 1))
    return ""


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


def intre(t, de_la, pana_la):
    """Bucata dintre două repere. Reperele de sfârşit sunt mai multe fiindcă
    fişele diferă: cine n-are grupuri de prietenie sare direct la activitate."""
    i = t.find(de_la)
    if i < 0:
        return ""
    i += len(de_la)
    j = len(t)
    for p in pana_la:
        if de_la.startswith(p) or p.startswith(de_la.rstrip(":")):
            continue                      # reperul de start nu e şi reper de stop
        k = t.find(p, i)
        if 0 <= k < j:
            j = k
    return t[i:j].strip(" ·:-")


REPERE = ["Comisii permanente", "Comisii speciale", "Grupuri de prietenie",
          "Activitatea parlamentară în cifre", "Biroul parlamentar", "Contact",
          "Formaţiunea politică", "Grupul parlamentar"]


def fisa(om):
    s = ia(om["fisa"])
    if not s:
        return None
    t_tot = text(s)
    # Blocul personal începe la „Informatii personale" şi ţine până la Contact.
    # Fără tăietura asta, e-mailul extras era webmaster@cdep.ro, din subsolul
    # site-ului — adresa Camerei, nu a omului.
    i0 = t_tot.find("Informatii personale")
    i1 = t_tot.find("Adresa poştală")
    t = t_tot[i0 if i0 >= 0 else 0: i1 if i1 > 0 else len(t_tot)]
    d = {"id": om["id"], "nume": om["nume"], "camera": om["camera"], "fisa": om["fisa"]}

    m = re.search(r"n\.\s*(\d{1,2}\s+\w+\.?\s+\d{4})", t)
    d["nascut"] = m.group(1) if m else ""
    m = re.search(r"data validării:\s*(.{5,60}?)(?=\s+n\.\s|\s+[a-z0-9._-]+@|\s+Forma)", t)
    d["validat"] = m.group(1).strip() if m else ""
    m = re.search(r"([a-z0-9._-]+@cdep\.ro)", t)
    d["email"] = m.group(1) if m else ""
    d["formatiune"] = intre(t, "Formaţiunea politică:", REPERE)[:90]
    d["grup_istoric"] = intre(t, "Grupul parlamentar:", REPERE)[:400]

    com = intre(t, "Comisii permanente", REPERE)
    d["comisii"] = [c.strip(" -") for c in re.split(r"(?=Comisia )", com) if c.strip(" -")][:6]
    sp = intre(t, "Comisii speciale comune", REPERE)
    d["comisii_speciale"] = [c.strip(" -") for c in re.split(r"(?=Comisia )", sp) if c.strip(" -")][:4]
    pri = intre(t, "Grupuri de prietenie cu Parlamentele altor state:", REPERE)
    d["prietenie"] = [c.strip(" -") for c in re.split(r"(?=Grupul parlamentar de prietenie)", pri) if c.strip(" -")][:8]

    cifre = intre(t, "Activitatea parlamentară în cifre:", REPERE)
    d["activitate"] = {}
    m = re.search(r"Luări de cuvânt:\s*la\s*(\d+)\s*puncte[^(]*\(în\s*(\d+)", cifre)
    if m:
        d["activitate"]["luari"] = int(m.group(1)); d["activitate"]["sedinte"] = int(m.group(2))
    m = re.search(r"Propuneri legislative iniţiate:\s*(\d+)(?:\s*,\s*din care\s*(\d+)\s*promulgate)?", cifre)
    if m:
        d["activitate"]["propuneri"] = int(m.group(1))
        d["activitate"]["promulgate"] = int(m.group(2) or 0)
    m = re.search(r"Întreb[aă]ri şi interpelări:\s*(\d+)", cifre)
    if m:
        d["activitate"]["intrebari"] = int(m.group(1))
    m = re.search(r"Moţiuni[^:]*:\s*(\d+)", cifre)
    if m:
        d["activitate"]["motiuni"] = int(m.group(1))

    birou = intre(t, "Biroul parlamentar", ["Contact", "Adresa poştală", "Preşedintele României"])
    # Împărţim DOAR pe punct-şi-virgulă. Tăierea pe „majusculă după spaţiu" rupea
    # „Nicolae Bălcescu" în două adrese. Mai bine o adresă lungă decât două
    # inventate — pe un site de fact-checking, mai ales.
    d["birouri"] = [b.strip(" ;.,") for b in birou.split(";") if len(b.strip(" ;.,")) > 8][:3]

    d["linkuri"] = {}
    for eticheta, cheie in (("Curriculum Vitae", "cv"), ("Declaraţia de avere", "avere"),
                            ("Declaraţia de interese", "interese"), ("Votul electronic", "vot")):
        m = re.search(rf'href="([^"]+)"[^>]*>\s*{re.escape(eticheta)}', s)
        if m:
            u = m.group(1)
            d["linkuri"][cheie] = ("https://www.cdep.ro" + u) if u.startswith("/") else u
    return d


def main():
    oameni = json.load(open(os.path.join(ROOT, "data", "_parlament.json"), encoding="utf-8"))["oameni"]
    cale = os.path.join(ROOT, "data", "_fise.json")
    # RELUARE: procesele lungi mor, iar o extragere care o ia de la zero de
    # fiecare dată nu se termină niciodată. Ce e deja luat, se sare.
    out = []
    if os.path.exists(cale):
        try:
            out = json.load(open(cale, encoding="utf-8"))["fise"]
        except Exception:
            out = []
    gata = {f["id"] + f["camera"] for f in out}
    ramase = [o for o in oameni if o["id"] + o["camera"] not in gata]
    lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else len(ramase)
    print(f"deja luate: {len(gata)} · de luat acum: {min(lim, len(ramase))} din {len(ramase)}", flush=True)
    esec = 0
    for i, om in enumerate(ramase[:lim], 1):
        f = fisa(om)
        if f:
            out.append(f)
        else:
            esec += 1
        if i % 40 == 0:
            print(f"  {i}/{lim}", flush=True)
        time.sleep(0.12)
    json.dump({"actualizat": time.strftime("%Y-%m-%d"), "fise": out},
              open(cale, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cu_birou = sum(1 for f in out if f["birouri"])
    print(f"\ntotal {len(out)}/464 fişe · {esec} eşecuri acum · cu birou: {cu_birou} · scris data/_fise.json")


if __name__ == "__main__":
    main()

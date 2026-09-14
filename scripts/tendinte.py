"""
tendinte.py — ce caută românii ACUM, din Google Trends, pentru redactorul automat.

De ce există (14 septembrie 2026): Search Console arăta 514 pagini indexate care
aduceau 47 de clicuri. Scriem despre ce se întâmplă, nu despre ce caută lumea.
Site-urile care au trafic din Google scriu ce caută lumea AZI. Aici nu vânăm
subiecte de dragul lor: dacă o căutare din top are în spate o AFIRMAȚIE
verificabilă, aia are prioritate în ediție, iar `seoTitle` trebuie să conțină
formularea pe care o tastează omul.

Sursa e RSS-ul public al Google Trends, gratis, fără cont:
    https://trends.google.com/trending/rss?geo=RO
Fiecare tendință vine cu titlurile știrilor pe care Google le leagă de ea —
adică exact afirmațiile care circulă.

Folosire:
    python3 scripts/tendinte.py            # tipărește blocul pentru prompt
    python3 scripts/tendinte.py --json     # scrie data/_tendinte.json și tipărește
"""
import json, os, re, sys, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSS = "https://trends.google.com/trending/rss?geo=RO"
CATE = 12


def ia():
    req = urllib.request.Request(RSS, headers={"User-Agent": "Mozilla/5.0 farabaliverne.ro"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def parseaza(xml):
    """Fără dependențe: RSS-ul e simplu, regex ajunge."""
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        t = re.search(r"<title>(.*?)</title>", item, re.S)
        if not t:
            continue
        titlu = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).strip()
        trafic = re.search(r"<ht:approx_traffic>(.*?)</ht:approx_traffic>", item)
        stiri = []
        for st in re.findall(r"<ht:news_item>(.*?)</ht:news_item>", item, re.S):
            nt = re.search(r"<ht:news_item_title>(.*?)</ht:news_item_title>", st, re.S)
            nu = re.search(r"<ht:news_item_url>(.*?)</ht:news_item_url>", st, re.S)
            ns = re.search(r"<ht:news_item_source>(.*?)</ht:news_item_source>", st, re.S)
            if nt:
                stiri.append({
                    "titlu": re.sub(r"<!\[CDATA\[|\]\]>", "", nt.group(1)).strip(),
                    "url": (nu.group(1).strip() if nu else ""),
                    "sursa": (ns.group(1).strip() if ns else ""),
                })
        out.append({"cautare": titlu,
                    "trafic": (trafic.group(1).strip() if trafic else ""),
                    "stiri": stiri[:3]})
    return out[:CATE]


def bloc(tend):
    linii = ["CE CAUTĂ ROMÂNII ACUM (Google Trends RO, %s UTC):" %
             datetime.now(timezone.utc).strftime("%d.%m %H:%M")]
    for i, t in enumerate(tend, 1):
        tr = f" · ~{t['trafic']}" if t["trafic"] else ""
        linii.append(f"{i}. „{t['cautare']}\"{tr}")
        for s in t["stiri"]:
            src = f" ({s['sursa']})" if s["sursa"] else ""
            linii.append(f"     - {s['titlu']}{src}")
    return "\n".join(linii)


def main():
    try:
        tend = parseaza(ia())
    except Exception as e:
        print(f"(tendințele nu s-au putut lua: {e})")
        return 0
    if "--json" in sys.argv:
        with open(os.path.join(ROOT, "data", "_tendinte.json"), "w", encoding="utf-8") as fh:
            json.dump({"luat": datetime.now(timezone.utc).isoformat(), "tendinte": tend},
                      fh, ensure_ascii=False, indent=2)
    print(bloc(tend))
    return 0


if __name__ == "__main__":
    sys.exit(main())

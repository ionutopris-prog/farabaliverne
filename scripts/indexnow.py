#!/usr/bin/env python3
"""
IndexNow — îi spune lui Bing (și Yandex, Seznam, Naver) că avem pagini noi, în
secunda în care sunt urcate. Protocol gratuit, fără cont; Google nu-l folosește.

Cum funcționează: o cheie publică stă într-un fișier la rădăcina site-ului
(<cheie>.txt). Trimitem POST la api.indexnow.org cu lista de URL-uri + cheia; ei
verifică fișierul și programează citirea. Fără asta, Bing ajunge la un articol
nou când apucă — zile, uneori săptămâni. Cu asta, de obicei în ore.

Ce trimitem: URL-urile din sitemap-news.xml (articolele din ultimele 48h) plus
prima pagină și feed-ul. Se rulează la finalul deploy-ului (deploy.yml), după ce
fișierele sunt deja pe server — altfel Bing găsește 404.

Rulare manuală:  python3 scripts/indexnow.py            (tot sitemap-news)
                 python3 scripts/indexnow.py <url> ...  (doar acelea)
"""
import json, os, re, sys, urllib.request

HOST = "farabaliverne.ro"
CHEIE = "996701042db0c2860590b11f16295141"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def urluri_proaspete():
    try:
        xml = open(os.path.join(ROOT, "sitemap-news.xml"), encoding="utf-8").read()
    except FileNotFoundError:
        return []
    return re.findall(r"<loc>(.*?)</loc>", xml)


def trimite(urluri):
    urluri = list(dict.fromkeys(u for u in urluri if u.startswith(f"https://{HOST}/")))
    if not urluri:
        print("IndexNow: nimic de trimis.")
        return 0
    corp = json.dumps({"host": HOST, "key": CHEIE,
                       "keyLocation": f"https://{HOST}/{CHEIE}.txt",
                       "urlList": urluri[:10000]}).encode("utf-8")
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=corp,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cod = r.status
    except urllib.error.HTTPError as e:
        cod = e.code
    # 200 = primit, 202 = primit, cheia se verifică mai târziu. Restul = problemă.
    print(f"IndexNow: {len(urluri)} URL-uri → HTTP {cod}" + ("" if cod in (200, 202) else "  ⚠️"))
    return 0 if cod in (200, 202) else 1


if __name__ == "__main__":
    lista = sys.argv[1:] or (urluri_proaspete() + [f"https://{HOST}/", f"https://{HOST}/feed.xml"])
    sys.exit(trimite(lista))

#!/usr/bin/env python3
"""
webp.py — face o copie .webp lângă fiecare poză din img/articole și img/carduri.

De ce (auditul SEO din 12 sept 2026): 0 poze WebP pe site, LCP-ul primei pagini
4,5 s, Lighthouse „modern formats" -174 KB doar pe primul ecran. WebP la
calitate 80 e cu 30–50 % mai mic decât JPEG la aceeași calitate vizibilă.

Ce rămâne JPEG: img/share (cardurile de partajare, og:image — Facebook și X le
vor JPEG). Paginile aleg singure .webp când există (vezi build_site.prefera_webp).

Rulare: python3 scripts/webp.py   (are nevoie de Pillow; fără el, spune și iese 0)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERE = ("img/articole", "img/carduri")
LAT_MAX = {"img/articole": 1600, "img/carduri": 520}


def main():
    try:
        from PIL import Image
    except ImportError:
        print("webp: Pillow lipsește, sar peste (paginile rămân pe JPEG)")
        return 0
    facute = sarite = 0
    for rel in FOLDERE:
        d = os.path.join(ROOT, rel)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            baza, ext = os.path.splitext(f)
            if ext.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            src = os.path.join(d, f)
            dst = os.path.join(d, baza + ".webp")
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                sarite += 1
                continue
            try:
                im = Image.open(src)
                im.load()
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGB")
                lat = LAT_MAX[rel]
                if im.width > lat:
                    im = im.resize((lat, round(im.height * lat / im.width)), Image.LANCZOS)
                im.save(dst, "WEBP", quality=80, method=4)
                # dacă WebP-ul a ieșit mai mare decât originalul, nu-l ținem
                if os.path.getsize(dst) >= os.path.getsize(src):
                    os.remove(dst)
                    sarite += 1
                else:
                    facute += 1
            except Exception as e:
                print(f"webp: {rel}/{f}: {e}")
    print(f"webp: {facute} făcute, {sarite} deja la zi / nerentabile")
    return 0


if __name__ == "__main__":
    sys.exit(main())

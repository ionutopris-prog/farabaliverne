"""
Cardul de partajare — imaginea care apare când cineva dă share pe Facebook sau WhatsApp.

Până acum, la share apărea fotografia articolului: o clădire, un politician, un
stadion. Frumoasă, dar mută — nu spune nimic despre ce am verificat. Iar cine
derulează pe telefon vede întâi imaginea, nu titlul.

Cardul ăsta spune singur povestea: afirmația verificată, unde bat probele, câte
afirmații s-au probat și câte nu. Cine îl vede în feed a aflat deja ceva, chiar
dacă nu dă click. Iar dacă dă, știe la ce.

Fotografia articolului rămâne, ca fundal întunecat — deci nu pierdem nimic din
ce atrăgea ochiul, doar punem înțelesul peste.

Rulare:
    python3 scripts/card_share.py                 # doar cele care lipsesc
    python3 scripts/card_share.py <slug> [<slug>] # anume
    python3 scripts/card_share.py --toate         # reface tot
"""

import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "img", "share")

# Facebook, WhatsApp, X și LinkedIn taie toate la 1,91:1. 1200×630 e formatul
# pe care nu-l retează niciunul.
LAT, INAL = 1200, 630

# Culorile site-ului, luate din CSS ca să nu arate a altcineva.
FUNDAL = (231, 240, 228)      # verde celadon
CERNEALA = (34, 39, 31)
ACCENT = (165, 55, 42)
VERDE = (74, 124, 89)
GALBEN = (184, 145, 47)

# Georgia pe Mac, Liberation/DejaVu pe serverul de build. Le încercăm în
# ordine — dacă niciunul nu există, Pillow ne dă fontul lui implicit, urât dar
# funcțional: mai bine un card modest decât niciun card.
FONTURI_SERIF = [
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
]
FONTURI_SANS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(candidati, marime):
    for c in candidati:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, marime)
            except OSError:
                continue
    return ImageFont.load_default(marime)


def _rupe(text, font, latime, desen, max_randuri):
    """Împarte textul în rânduri care încap. Taie cu „…" dacă nu încape tot."""
    cuvinte = (text or "").split()
    randuri, curent = [], ""
    for c in cuvinte:
        proba = (curent + " " + c).strip()
        if desen.textlength(proba, font=font) <= latime:
            curent = proba
        else:
            if curent:
                randuri.append(curent)
            curent = c
            if len(randuri) == max_randuri:
                break
    if curent and len(randuri) < max_randuri:
        randuri.append(curent)
    if len(randuri) == max_randuri and len(" ".join(randuri)) < len(text or ""):
        ultim = randuri[-1]
        while ultim and desen.textlength(ultim + "…", font=font) > latime:
            ultim = ultim[:-1]
        randuri[-1] = ultim.rstrip(" ,.;:—-") + "…"
    return randuri


def _verdict_scurt(v):
    """Verdictele sunt fraze întregi. Pe card încape o etichetă, nu un paragraf."""
    t = (v or "").strip().lower()
    for ch in "ăâ":
        t = t.replace(ch, "a")
    t = t.replace("î", "i").replace("ș", "s").replace("ş", "s").replace("ț", "t").replace("ţ", "t")
    if t.startswith("probat") or t.startswith("context probat"):
        return "SE PROBEAZĂ", VERDE
    if t.startswith(("contrazis", "nu se sustine")):
        return "NU SE SUSȚINE", ACCENT
    if t.startswith(("contestat", "neconfirmat", "neverificabil", "afirmatie rusa",
                     "anunt neverificat")):
        return "CONTESTAT", ACCENT
    return "SURSE ÎN DEZACORD", GALBEN


def fundal_din_poza(slug):
    """Fotografia articolului, întunecată, ca fundal. None dacă nu există."""
    for ext in ("jpg", "jpeg", "png"):
        p = os.path.join(ROOT, "img", "articole", f"{slug}.{ext}")
        if not os.path.exists(p):
            continue
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            return None
        # umplem tot cardul, tăind ce prisosește (nu deformăm poza)
        r = max(LAT / im.width, INAL / im.height)
        im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))),
                       Image.LANCZOS)
        st = ((im.width - LAT) // 2, (im.height - INAL) // 2)
        im = im.crop((st[0], st[1], st[0] + LAT, st[1] + INAL))
        im = im.filter(ImageFilter.GaussianBlur(3))

        # Voal întunecat, ca textul alb să se citească peste orice fotografie.
        # Uniform nu ajunge: o poză luminoasă în colțul de jos înghițea deviza.
        # Deci întunecăm în DEGRADEU, mai tare spre bază, unde stă textul mic.
        voal = Image.new("RGB", (LAT, INAL), (12, 16, 11))
        masca = Image.new("L", (1, INAL))
        for y in range(INAL):
            t = y / (INAL - 1)
            masca.putpixel((0, y), int(255 * (0.52 + 0.34 * t * t)))
        masca = masca.resize((LAT, INAL))
        return Image.composite(voal, im, masca)
    return None


def card(slug, d):
    poza = fundal_din_poza(slug)
    pe_poza = poza is not None
    im = poza or Image.new("RGB", (LAT, INAL), FUNDAL)
    dr = ImageDraw.Draw(im)

    cerneala = (255, 255, 255) if pe_poza else CERNEALA
    sters = (214, 226, 208) if pe_poza else (85, 96, 80)

    if not pe_poza:
        # dungi discrete, ca pe cardul de brand din articole
        for x in range(-INAL, LAT, 26):
            dr.line([(x, INAL), (x + INAL, 0)], fill=(222, 233, 219), width=9)

    M = 64                       # margine
    f_titlu = _font(FONTURI_SERIF, 54)
    f_mic = _font(FONTURI_SANS, 25)
    f_eticheta = _font(FONTURI_SANS, 27)
    f_brand = _font(FONTURI_SERIF, 31)

    # ── verdictul, sus, ca pastilă ──
    et, cul = _verdict_scurt(d.get("mainVerdict"))
    w = dr.textlength(et, font=f_eticheta)
    dr.rounded_rectangle([M, M, M + w + 44, M + 52], radius=26, fill=cul)
    dr.text((M + 22, M + 12), et, font=f_eticheta, fill=(255, 255, 255))

    # ── titlul ──
    randuri = _rupe(d.get("title", ""), f_titlu, LAT - 2 * M, dr, 5)
    y = M + 96
    for r in randuri:
        dr.text((M, y), r, font=f_titlu, fill=cerneala)
        y += 66

    # ── numărătoarea, jos ──
    np_, nc_ = len(d.get("probat") or []), len(d.get("contestat") or [])
    parti = []
    if np_:
        parti.append(f"{np_} {'afirmație probată' if np_ == 1 else 'afirmații probate'}")
    if nc_:
        parti.append(f"{nc_} {'contestată' if nc_ == 1 else 'contestate'}")
    if parti:
        dr.text((M, INAL - M - 78), " · ".join(parti), font=f_mic, fill=sters)

    # ── brandul ──
    dr.text((M, INAL - M - 40), "Fără Baliverne", font=f_brand, fill=cerneala)
    dev = "farabaliverne.ro · Apă, paie… Adevăr"
    dr.text((LAT - M - dr.textlength(dev, font=f_mic), INAL - M - 34),
            dev, font=f_mic, fill=sters)

    os.makedirs(OUT_DIR, exist_ok=True)
    cale = os.path.join(OUT_DIR, f"{slug}.jpg")
    im.save(cale, "JPEG", quality=86, optimize=True)
    return cale, os.path.getsize(cale)


def main():
    arg = [a for a in sys.argv[1:] if not a.startswith("-")]
    toate = "--toate" in sys.argv

    sluguri = arg
    if not sluguri:
        sluguri = []
        for p in glob.glob(os.path.join(ROOT, "data", "*.json")):
            s = os.path.basename(p)[:-5]
            if s.startswith("_"):
                continue
            if not os.path.exists(os.path.join(ROOT, "a", s + ".html")):
                continue
            if toate or not os.path.exists(os.path.join(OUT_DIR, s + ".jpg")):
                sluguri.append(s)

    if not sluguri:
        print("Toate cardurile există deja. (--toate ca să le refac)")
        return 0

    n = octeti = 0
    for s in sorted(sluguri):
        dp = os.path.join(ROOT, "data", s + ".json")
        if not os.path.exists(dp):
            print(f"  ! {s}: fără fișier în data/")
            continue
        try:
            d = json.load(open(dp, encoding="utf-8"))
        except ValueError:
            continue
        try:
            _, b = card(s, d)
        except Exception as e:
            print(f"  ! {s}: {type(e).__name__}: {e}")
            continue
        n += 1
        octeti += b
    print(f"✅ {n} carduri de partajare · {octeti // 1024} KB total "
          f"(~{octeti // max(1, n) // 1024} KB bucata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Alege o fotografie REALĂ, liberă de drepturi, pentru un articol.

Surse, în ordine: Wikimedia Commons, apoi Openverse (agregatorul Fundației
Wikimedia peste Flickr, muzee și arhive CC). Amândouă fără cheie de API și fără
cont, cu licența scrisă pe fiecare fișier. Commons e prima fiindcă are portrete
de oameni publici și denumiri stabile de instituții; Openverse intră când
Commons n-are nimic — peisaje, obiecte, situații generice, care sunt exact
lipsurile lui.
Poza se DESCARCĂ și se găzduiește la noi — nu mai atârnăm de serverul altcuiva.

Trei protecții, în ordinea importanței:

1. FILTRU DE CONTEXT. O căutare naivă după „Air China" întoarce pe locul doi
   fotografii de la locul unui accident aviatic. Pentru o știre despre
   redeschiderea unei rute, aia ar fi fost o catastrofă editorială — mult mai
   grav decât orice problemă de drepturi. Cuvintele de risc sunt respinse dacă
   articolul nu e chiar despre asta.

2. FILTRU DE LICENȚĂ. Acceptăm doar domeniu public, CC0, CC-BY, CC-BY-SA.
   Respingem GFDL (cere textul integral al licenței lângă poză) și orice
   licență necomercială — noi avem pagină de publicitate, deci suntem comerciali.

3. CREDIT OBLIGATORIU. Fiecare poză pleacă cu autor + licență + link. Fără
   credit complet, poza nu e folosită.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "img", "articole")

UA = "farabaliverne.ro/1.0 (contact@farabaliverne.ro)"

# Wikimedia ne-a dat 429 când am tras 26 de poze la rând. Sunt oaspeți amabili,
# nu abuzăm de ei: o pauză între cereri și reîncercare cu așteptare crescândă.
PAUZA = 1.2
_ultima_cerere = [0.0]

# 1200px e suficient pentru un hero. La 1600 ieșeau fișiere de 700KB-1MB, ceea
# ce ar fi transformat un articol de 51KB într-unul de peste un megaoctet.
LATIME_MAX = 1200
KB_MAX = 260

# Licențe pe care le putem folosi comercial, cu atribuire.
LICENSE_OK = re.compile(
    r"^(public domain|cc0|cc[ -]by(?:[ -]sa)?(?:[ -][\d.]+)?)",
    re.IGNORECASE,
)
LICENSE_BAD = re.compile(r"gfdl|non[- ]commercial|\bnc\b|fair use|no derivat", re.IGNORECASE)

# Cuvinte care fac o poză nepotrivită dacă articolul NU e despre asta.
# Fișiere care nu sunt fotografii. Sub ele scriem „Foto ilustrativă", ceea ce e
# neadevărat, și arată exact ca un site care n-a găsit nimic.
#
# Pe 12 august, patru articole — Zelenski/Kosovo, depozitul OMS din Dnipro,
# teritoriul ocupat după ISW, explozia din Bulgaria — aveau TOATE același
# `Flag_of_Turkey.svg`. Pe Commons drapelele și siglele sunt printre cele mai
# bine cotate fișiere, deci ies primele la orice căutare vagă. Un al cincilea
# articol, despre eclipsă, avea sigla NASA.
NEPHOTO = re.compile(
    r"\b(flags?|drapeau|bandera|bandiera|logos?|logotype|wordmark|emblem|"
    r"insignia|coat of arms|escudo|wappen|seal|crest|icon|symbol|"
    r"maps?|karte|mapa|carte|diagram|chart|graph|schematic|banner)\b",
    re.IGNORECASE)

# Multe fotografii de pe Commons sunt în domeniul public tocmai fiindcă sunt
# vechi de un secol. Legal, impecabil; jurnalistic, nu: „Foto ilustrativă" sub
# o știre de azi înseamnă că așa arată lucrul despre care scriem ACUM.
# Căutarea după Dnipro a întors o fotografie aeriană alb-negru din Primul
# Război Mondial, iar cea după uzina de muniție, un depozit de obuze britanic
# din 1917, cu filigranul muzeului pe el.
# Respingem doar când chiar știm anul — multe poze bune n-au dată deloc.
AN_MINIM = 2000

# Cuvinte care fac o poză nepotrivită dacă articolul NU e chiar despre asta.
# Filtrul respinge poza doar când cuvântul apare în titlul ei și NU apare în
# textul articolului — deci lista poate fi generoasă fără să blocheze pozele
# corecte (un articol despre un incendiu conține cuvântul „incendiu").
#
# 🔴 Adăugat pe 5 septembrie 2026, după o scăpare reală: pentru un articol
# despre un MODEL STATISTIC de prognoză electorală de la Cornell, căutarea
# „United States Capitol building Washington" a întors, și a trecut de filtru,
# fotografia „2021 storming of the United States Capitol". O poză de la asaltul
# din 6 ianuarie pe un text despre matematică electorală ar fi sugerat violență
# și insurecție acolo unde nu era nimic de felul ăsta. Lista acoperea accidente,
# incendii și înmormântări — dar nu VIOLENȚA POLITICĂ. Acum o acoperă.
RISKY = [
    # accidente și dezastre
    "crash", "wreck", "accident", "disaster", "burning", "fire", "explosion",
    "funeral", "memorial", "victim", "casualt", "debris", "collision",
    "flood", "earthquake", "wildfire", "destroy", "destruct", "ruins", "rubble",
    "prăbuș", "accident", "incendi", "explozie", "funerar", "inundaț",
    "cutremur", "distrus", "ruine", "victim",
    # violență politică și conflict — lipseau cu totul
    "storming", "riot", "insurrection", "unrest", "uprising", "clash",
    "protest", "demonstration", "siege", "attack", "assault", "war",
    "battle", "shooting", "gunman", "bomb", "terror", "arrest", "police",
    "refugee", "massacre", "killed", "corpse", "wounded", "injured",
    "asalt", "revolt", "răscoal", "atac", "război", "razboi", "protest",
    "arestare", "împușc", "impusc", "bombă", "bomba", "atentat", "refugiat",
    "mort", "rănit", "ranit",
]


def _get(url, incercari=4):
    """Cerere politicoasă: pauză între apeluri, reîncercare la 429."""
    for i in range(incercari):
        de_asteptat = PAUZA - (time.time() - _ultima_cerere[0])
        if de_asteptat > 0:
            time.sleep(de_asteptat)
        _ultima_cerere[0] = time.time()

        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or i == incercari - 1:
                raise
            time.sleep(5 * (i + 1))
    raise RuntimeError("cereri epuizate")


def _clean(html):
    """extmetadata întoarce HTML; ne trebuie text simplu pentru credit."""
    text = re.sub(r"<[^>]+>", "", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _nume_in_titlu(nume, titlu):
    """
    La portrete, numele persoanei TREBUIE să apară în titlul fișierului.

    Fără verificarea asta, o căutare după „David Popovici" a întors o fotografie
    intitulată „Bianca Costea, STEAUA TV" — poza altei persoane, care ar fi ajuns
    pe site sub eticheta „Foto de arhivă — David Popovici". Pe un site de
    fact-checking, aia e o greșeală mult mai gravă decât lipsa unei poze.
    """
    t = titlu.lower()
    parti = [p for p in re.split(r"\s+", nume.lower()) if len(p) > 2]
    if not parti:
        return False
    return all(p in t for p in parti)


def _an_pozei(meta):
    """Anul fotografiei, dacă Commons îl știe. None = nu putem ști."""
    brut = (_clean(meta.get("DateTimeOriginal", {}).get("value", "")) or
            _clean(meta.get("DateTime", {}).get("value", "")))
    m = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", brut)
    return int(m.group(1)) if m else None


def search(query, article_text="", limit=12, nume_persoana=None):
    """
    Întoarce candidați ordonați, cel mai potrivit primul.

    `nume_persoana` pornește verificarea strictă de identitate de mai sus.
    """
    api = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6&gsrlimit=%d&gsrsearch=%s"
        "&prop=imageinfo&iiprop=url|size|mime|extmetadata&iiurlwidth=1200"
        % (limit, urllib.parse.quote(query))
    )
    data = json.loads(_get(api))
    pages = (data.get("query") or {}).get("pages", {})

    article_low = article_text.lower()
    out = []

    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        title = page.get("title", "")

        if nume_persoana and not _nume_in_titlu(nume_persoana, title):
            continue

        if info.get("mime") == "image/svg+xml" or NEPHOTO.search(title):
            continue

        an = _an_pozei(meta)
        if an and an < AN_MINIM:
            continue

        lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
        if LICENSE_BAD.search(lic) or not LICENSE_OK.match(lic):
            continue

        # Filtrul de context: dacă titlul pozei conține un cuvânt de risc, iar
        # articolul nu vorbește despre asta, poza e respinsă.
        low = title.lower()
        risky_hit = next((w for w in RISKY if w in low), None)
        if risky_hit and risky_hit not in article_low:
            continue

        width = info.get("thumbwidth") or info.get("width") or 0
        height = info.get("thumbheight") or info.get("height") or 0
        if width < 900:
            continue
        if height and width / height < 1.15:      # vrem peisaj, nu portret
            continue

        # Preferăm portretele singulare. „Konferencja Karola Nawrockiego i
        # Nicușor Dan" e chiar Nicușor Dan, dar apar doi oameni sub o legendă
        # care numește unul singur. Nu e greșit, doar neglijent — așa că astea
        # coboară în clasament, fără să fie eliminate.
        insotit = bool(re.search(r"\b(i|cu|și|and|with|meets|receives)\b|&",
                                 title, re.IGNORECASE))

        author = _clean(meta.get("Artist", {}).get("value", "")) or "autor necunoscut"
        out.append({
            "_insotit": insotit,
            "title": title.replace("File:", "").rsplit(".", 1)[0],
            "url": info.get("thumburl") or info.get("url"),
            "descriptionurl": info.get("descriptionurl", ""),
            "license": lic,
            "license_url": _clean(meta.get("LicenseUrl", {}).get("value", "")) or license_url(lic),
            "author": author[:80],
            "width": width,
            "height": height,
        })

    out.sort(key=lambda c: c["_insotit"])
    return out


# Openverse acceptă și licențe pe care noi nu le vrem, deci cerem din capul
# locului doar ce se poate folosi comercial și modifica — noi avem pagină de
# publicitate, deci suntem comerciali, iar poza o tăiem la formatul nostru.
OPENVERSE = ("https://api.openverse.org/v1/images/?q=%s"
             "&license_type=commercial,modification&page_size=%d"
             "&mature=false")


def search_openverse(query, article_text="", limit=20, nume_persoana=None,
                     strict=True):
    """Aceiași candidați, aceeași structură, altă sursă.

    Nu caută persoane: pentru portrete Commons e mai de încredere, iar aici
    n-avem cum verifica dacă omul din poză e chiar cel din titlu. Când se cere
    o persoană, întoarcem gol și lăsăm Commons să decidă.
    """
    if nume_persoana:
        return []
    try:
        data = json.loads(_get(OPENVERSE % (urllib.parse.quote(query), limit)))
    except Exception:
        return []

    article_low = article_text.lower()
    out = []
    for r in data.get("results", []):
        titlu = (r.get("title") or "").strip()
        lic = (r.get("license") or "").lower()
        if lic not in ("by", "by-sa", "cc0", "pdm"):
            continue
        if NEPHOTO.search(titlu):
            continue

        low = titlu.lower()
        risky_hit = next((w for w in RISKY if w in low), None)
        if risky_hit and risky_hit not in article_low:
            continue

        # Openverse caută și în descriere, nu doar în titlu, așa că întoarce
        # lucruri fără legătură: la „swimming pool competition" a dat „Dive in
        # Movies - White Night", o proiecție de film lângă o piscină. Cerem ca
        # titlul să conțină măcar un cuvânt din ce căutăm. Commons n-are nevoie
        # de filtrul ăsta — acolo titlul fișierului chiar descrie fișierul.
        # `strict` e pentru fluxul vechi, unde luam orbeşte primul candidat şi
        # aveam nevoie de o cârjă. Când alege cineva uitându-se la poze
        # (`alege_poza.py`), cârja doar ne sărăceşte lista: multe poze bune au
        # titluri care nu repetă cuvintele căutării.
        if strict:
            cuvinte = [c for c in re.findall(r"\w{4,}", query.lower())]
            if cuvinte and not any(c in low for c in cuvinte):
                continue

        w = r.get("width") or 0
        h = r.get("height") or 0
        if w < 900:
            continue
        if h and w / h < 1.15:      # vrem peisaj, nu portret
            continue

        vers = r.get("license_version") or ""
        scurt = f"CC {lic.upper()} {vers}".strip() if lic not in ("cc0", "pdm") else (
            "CC0" if lic == "cc0" else "Public domain")
        out.append({
            "_insotit": False,
            "title": titlu or query,
            "url": r.get("url"),
            "descriptionurl": r.get("foreign_landing_url") or r.get("detail_url", ""),
            "license": scurt,
            "license_url": r.get("license_url") or license_url(scurt),
            "author": (r.get("creator") or "autor necunoscut")[:80],
            "width": w,
            "height": h,
        })
    return out


def search_tot(query, article_text="", limit=12, nume_persoana=None, strict=True):
    """Commons întâi, Openverse pe post de plasă. Prima sursă care dă ceva câștigă."""
    gasit = search(query, article_text, limit=limit, nume_persoana=nume_persoana)
    if gasit:
        return gasit
    return search_openverse(query, article_text, nume_persoana=nume_persoana,
                            strict=strict)


def license_url(short_name):
    """Linkul către textul licenței — obligatoriu pentru atribuirea CC."""
    s = (short_name or "").lower().replace(" ", "-")
    if "cc0" in s:
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    m = re.match(r"cc-?by(-sa)?-?([\d.]+)?", s)
    if m:
        kind = "by-sa" if m.group(1) else "by"
        version = m.group(2) or "4.0"
        return f"https://creativecommons.org/licenses/{kind}/{version}/"
    return ""


def _comprima_sips(path, tmp):
    """sips e nativ pe macOS — fără dependențe de instalat."""
    if not shutil.which("sips"):
        return None
    cel_mai_bun = None
    for calitate in ("high", "medium", "low"):
        subprocess.run(
            ["sips", "-Z", str(LATIME_MAX), "-s", "format", "jpeg",
             "-s", "formatOptions", calitate, path, "--out", tmp],
            capture_output=True, check=False,
        )
        if not os.path.exists(tmp):
            continue
        marime = os.path.getsize(tmp)
        if cel_mai_bun is None or marime < cel_mai_bun[1]:
            cel_mai_bun = (open(tmp, "rb").read(), marime)
        os.remove(tmp)
        if marime <= KB_MAX * 1024:
            break
    return cel_mai_bun


def _comprima_pil(path, tmp):
    """Fallback portabil (Linux/CI, fără sips) — Pillow, dacă e instalat."""
    try:
        from PIL import Image, ImageFile
    except ImportError:
        return None
    # Pozele de pe Commons vin des cu ultimii octeți lipsă. `sips` trece peste
    # și comprimă normal; Pillow ridică „image file is truncated" și refuză să
    # deschidă fișierul. De-aia mergea pe Mac și pica pe runner: aceeași poză,
    # două comportamente. Pe 16 august, doi octeți lipsă dintr-un JPEG au ținut
    # site-ul pe loc șapte ore și jumătate.
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    cel_mai_bun = None
    # Scara merge în DOUĂ dimensiuni: întâi calitatea, apoi lățimea. Numai
    # calitatea nu ajunge — o poză deja la LATIME_MAX nu se redimensionează
    # deloc, iar recodarea JPEG a unui JPEG poate ieși mai MARE decât
    # originalul. Pe 23 august, o poză de 311 KB la exact 1200px a dat 399 KB
    # la q85, 349 la q70 și fix 311 la q55 — ultima treaptă a scării vechi.
    # Fiind „nu mai mică decât originalul", a fost respinsă, iar verificarea a
    # picat trei ediții la rând pe 11 KB. Aceeași poză: 296 KB la q45, 268 la
    # q35, și 212 KB la 1000px/q55. Treptele lipseau, nu unealta.
    trepte = [(LATIME_MAX, q) for q in (85, 70, 55, 45, 35)]
    trepte += [(l, q) for l in (1000, 800) for q in (70, 55, 45, 35)]
    for latime, calitate in trepte:
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                if im.width > latime:
                    h = round(im.height * latime / im.width)
                    im = im.resize((latime, h), Image.LANCZOS)
                im.save(tmp, "JPEG", quality=calitate, optimize=True)
        except Exception as e:
            # Niciodată tăcut: o compresie care eșuează fără urmă arată exact ca
            # una care a reușit, iar pasul următor blochează publicarea.
            print(f"::warning::Pillow n-a putut comprima {os.path.basename(path)} "
                  f"la {latime}px/calitate {calitate}: {type(e).__name__}: {e}")
            continue
        if not os.path.exists(tmp):
            continue
        marime = os.path.getsize(tmp)
        if cel_mai_bun is None or marime < cel_mai_bun[1]:
            cel_mai_bun = (open(tmp, "rb").read(), marime)
        os.remove(tmp)
        if marime <= KB_MAX * 1024:
            break
    return cel_mai_bun


def unealta_compresie():
    """
    Ce unealtă de compresie avem. None = niciuna, și atunci pozele rămân la
    mărimea descărcată (600 KB-1 MB de pe Commons).

    Există fiindcă lipsa uneleia era invizibilă: `_comprima_pil` întorcea None
    pe ImportError, `comprima` renunța fără un cuvânt, iar ediția raporta
    succes. Pe 12 august asta a blocat publicarea 18 ore.
    """
    if shutil.which("sips"):
        return "sips"
    try:
        import PIL  # noqa: F401
        return "Pillow"
    except ImportError:
        return None


def comprima(path):
    """
    Scriem într-un fișier temporar și păstrăm rezultatul doar dacă e mai mic
    decât ce aveam. Fără verificarea asta, o recodare poate ieși mai MARE decât
    originalul, ceea ce s-a și întâmplat la prima rulare.

    Încearcă sips (macOS) întâi, apoi Pillow (Linux/CI). Dacă nu e niciuna,
    păstrăm fișierul necomprimat — dar o SPUNEM.

    Întoarce calea finală, care poate să difere de cea primită: compresia
    scoate JPEG, deci un .png comprimat e redenumit .jpg. Altfel am servi
    octeți JPEG sub antet image/png — browserele ghicesc, dar unii clienți de
    share nu, și tocmai previzualizările ne interesează.
    """
    initial = os.path.getsize(path)
    if initial <= KB_MAX * 1024:
        return path

    if not unealta_compresie():
        print(f"::warning::nici sips, nici Pillow — {os.path.basename(path)} "
              f"rămâne la {initial // 1024} KB")
        return path

    tmp = path + ".tmp.jpg"
    cel_mai_bun = _comprima_sips(path, tmp) or _comprima_pil(path, tmp)
    if not cel_mai_bun or cel_mai_bun[1] >= initial:
        return path

    # Ștergem ÎNTÂI, scriem după. Invers, un fișier `.JPG` (majuscule, cum vin
    # unele de pe Commons) ar fi șters chiar după ce l-am rescris ca `.jpg`:
    # macOS nu deosebește cele două nume, deci `os.remove` lua exact fișierul
    # nou. Octeții sunt deja în memorie, așa că ordinea asta e sigură.
    final = os.path.splitext(path)[0] + ".jpg"
    os.remove(path)
    with open(final, "wb") as fh:
        fh.write(cel_mai_bun[0])
    return final


def download(candidate, slug):
    os.makedirs(IMG_DIR, exist_ok=True)
    ext = os.path.splitext(urllib.parse.urlparse(candidate["url"]).path)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    path = os.path.join(IMG_DIR, slug + ext)
    with open(path, "wb") as fh:
        fh.write(_get(candidate["url"]))
    path = comprima(path)
    candidate["local"] = os.path.relpath(path, ROOT)
    candidate["bytes"] = os.path.getsize(path)
    return candidate


def credit_html(c, illustrative=True):
    eticheta = "Foto ilustrativă" if illustrative else "Foto"
    return (
        '<figcaption class="foto-credit">'
        f'{eticheta}: {c["author"]} · '
        f'<a href="{c["descriptionurl"]}" rel="nofollow noopener" target="_blank">'
        f'{c["license"]}</a> · via Wikimedia Commons'
        "</figcaption>"
    )


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Air China Boeing aircraft"
    ctx = sys.argv[2] if len(sys.argv) > 2 else ""
    found = search(q, ctx)
    print(f"query: {q}\ncandidați acceptați: {len(found)}\n")
    for c in found[:6]:
        print(f"  {c['title'][:60]}")
        print(f"    {c['width']}x{c['height']} · {c['license']} · {c['author'][:40]}")

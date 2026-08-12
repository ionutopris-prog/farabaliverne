"""
Alege o fotografie REALĂ, liberă de drepturi, pentru un articol.

Sursa: Wikimedia Commons (fără cheie de API, licențe explicite pe fiecare fișier).
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
RISKY = [
    "crash", "wreck", "accident", "disaster", "burning", "fire", "explosion",
    "funeral", "memorial", "victim", "casualt", "debris", "collision",
    "prăbuș", "accident", "incendi", "explozie", "funerar",
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


def search(query, article_text="", limit=12, nume_persoana=None):
    """
    Întoarce candidați ordonați, cel mai potrivit primul.

    `nume_persoana` pornește verificarea strictă de identitate de mai sus.
    """
    api = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&generator=search&gsrnamespace=6&gsrlimit=%d&gsrsearch=%s"
        "&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1200"
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
        from PIL import Image
    except ImportError:
        return None
    cel_mai_bun = None
    for calitate in (85, 70, 55):
        try:
            with Image.open(path) as im:
                im = im.convert("RGB")
                if im.width > LATIME_MAX:
                    h = round(im.height * LATIME_MAX / im.width)
                    im = im.resize((LATIME_MAX, h), Image.LANCZOS)
                im.save(tmp, "JPEG", quality=calitate, optimize=True)
        except Exception:
            return cel_mai_bun
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
    comprima(path)
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

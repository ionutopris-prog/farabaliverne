"""
icoana.py — dintr-o poză cu o picătură, scoate icoana aplicației.

De ce există: picăturile frumoase vin din Image Playground, dar vin cu fundal,
cu ramă desenată în poză și uneori cu text peste. Aici se curăță toate, se pune
ziarul înăuntru (cu adresa pe frontispiciu, ca orice ziar) și iese fișierul de
1024 px pe care-l cere Apple.

Folosire:
    python3 scripts/unelte/icoana.py <poza.png> [--fundal verde|crem|inchis]
                                     [--lat 0.86] [--iesire icoana.png]
                                     [--pune-in-aplicatie]

Regula fondatorului (13 septembrie 2026): adresa trebuie să se distingă dacă
te uiți atent, dar să nu fie eticheta principală. De-aia stă pe frontispiciu.
"""
import argparse, os, subprocess, sys, tempfile
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
except ImportError:
    sys.exit("lipsesc Pillow și numpy: foloseşte venv-ul din ~/Projects/marketing-ai")

N = 1024
FUNDALURI = {
    "verde":  ((47, 138, 73), (19, 76, 40)),
    "crem":   ((250, 248, 243), (222, 230, 223)),
    "inchis": ((24, 30, 27), (8, 12, 10)),
}

ZIAR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="1536" height="1536">
 <g transform="translate(8,13)">
  <rect x="0.5" y="0.5" width="47" height="37" rx="2.2" fill="#ffffff" stroke="#dfe6e0" stroke-width="1"/>
  <rect x="3.6" y="3.4" width="40.8" height="6.2" rx="1.2" fill="#17532b"/>
  <text x="24" y="7.9" font-family="Helvetica,Arial,sans-serif" font-size="3.45"
        font-weight="700" fill="#ffffff" text-anchor="middle">farabaliverne.ro</text>
  <rect x="3.6" y="12.4" width="16.5" height="12.6" rx="1" fill="#cfe8d6"/>
  <rect x="22.4" y="12.4" width="22" height="2.3" rx="1.15" fill="#a8c6b2"/>
  <rect x="22.4" y="16.6" width="22" height="2.3" rx="1.15" fill="#a8c6b2"/>
  <rect x="22.4" y="20.8" width="15" height="2.3" rx="1.15" fill="#a8c6b2"/>
  <rect x="3.6" y="28" width="40.8" height="2.3" rx="1.15" fill="#a8c6b2"/>
  <rect x="3.6" y="32" width="27" height="2.3" rx="1.15" fill="#a8c6b2"/>
 </g>
</svg>"""


def ziarul():
    """Ziarul cu adresa pe frontispiciu, cu fundal transparent."""
    d = tempfile.mkdtemp()
    svg = os.path.join(d, "z.svg")
    open(svg, "w").write(ZIAR_SVG)
    subprocess.run(["qlmanage", "-t", "-s", "1536", "-o", d, svg], capture_output=True)
    z = Image.open(os.path.join(d, "z.svg.png")).convert("RGBA")
    # qlmanage randează pe alb: decupăm după geometria din SVG
    z = z.crop((int(8 / 64 * 1536), int(13 / 64 * 1536),
                int(56 / 64 * 1536), int(51 / 64 * 1536)))
    m = Image.new("L", z.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, z.width - 1, z.height - 1],
                                        radius=int(2.2 / 48 * z.width), fill=255)
    z.putalpha(m)
    return z


def curata(cale):
    """Scoate fundalul, umple golurile din sticlă, păstrează doar picătura."""
    im = Image.open(cale).convert("RGB")
    w0, h0 = im.size
    # tăiem rama desenată în poză (Image Playground pune des un chenar)
    im = im.crop((int(w0 * .13), int(h0 * .13), int(w0 * .87), int(h0 * .90)))
    a = np.asarray(im).astype(float)
    lum = a.mean(axis=2)
    bl = a[:, :, 2] - a[:, :, 0]
    h, w = lum.shape
    nefundal = (lum < 208) | (bl > 14)

    # 🔴 Fără pasul ăsta picătura iese găurită: interiorul ei strălucitor e la
    # fel de deschis ca fundalul. Fundalul adevărat e doar ce atinge marginea.
    fundal = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not nefundal[y, x] and not fundal[y, x]:
                fundal[y, x] = True; q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if not nefundal[y, x] and not fundal[y, x]:
                fundal[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not fundal[ny, nx] and not nefundal[ny, nx]:
                fundal[ny, nx] = True; q.append((ny, nx))

    alfa = (~fundal).astype(np.uint8) * 255
    im = im.copy()
    im.putalpha(Image.fromarray(alfa).filter(ImageFilter.GaussianBlur(1.4)))

    # doar bucata cea mai mare: scapă de petele şi umbrele răzleţe
    A = np.asarray(im)[:, :, 3] > 60
    vaz = np.zeros_like(A); mare = None; maxn = 0
    for sy in range(0, h, 4):
        for sx in range(0, w, 4):
            if A[sy, sx] and not vaz[sy, sx]:
                q = deque([(sy, sx)]); vaz[sy, sx] = True; cell = []
                while q:
                    y, x = q.popleft(); cell.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and A[ny, nx] and not vaz[ny, nx]:
                            vaz[ny, nx] = True; q.append((ny, nx))
                if len(cell) > maxn:
                    maxn = len(cell); mare = cell
    if mare:
        keep = np.zeros_like(A)
        for y, x in mare:
            keep[y, x] = True
        arr = np.asarray(im).copy()
        arr[:, :, 3] = np.where(keep, arr[:, :, 3], 0)
        im = Image.fromarray(arr)
    return im.crop(im.getbbox())


def fundal_gradient(sus, jos):
    g = Image.new("RGB", (N, N)); d = ImageDraw.Draw(g)
    for y in range(N):
        t = y / (N - 1)
        d.line([(0, y), (N, y)],
               fill=tuple(int(sus[i] + (jos[i] - sus[i]) * t) for i in range(3)))
    return g.convert("RGBA")


def compune(drop, ziar, culoare, lat_rel, dy, ocupa=.84):
    DW, DH = drop.size
    al = np.asarray(drop)[:, :, 3]
    lat, ybulb = max([(np.count_nonzero(al[y] > 60), y)
                      for y in range(int(DH * .45), int(DH * .92))])
    xs = np.where(al[ybulb] > 60)[0]
    xc = (xs.min() + xs.max()) // 2

    d = drop.copy()
    lw = int(lat * lat_rel); lh = int(lw * ziar.height / ziar.width)
    zz = ziar.resize((lw, lh), Image.LANCZOS)
    x = xc - lw // 2; y = int(ybulb + DH * dy) - lh // 2
    aura = Image.new("RGBA", (DW, DH), (0, 0, 0, 0))
    ImageDraw.Draw(aura).ellipse([x - 45, y - 35, x + lw + 45, y + lh + 35],
                                 fill=(255, 255, 255, 95))
    d.alpha_composite(aura.filter(ImageFilter.GaussianBlur(48)))
    d.alpha_composite(zz, (x, y))

    im = fundal_gradient(*FUNDALURI[culoare])
    q = d.copy(); q.thumbnail((int(N * ocupa), int(N * ocupa)), Image.LANCZOS)
    im.alpha_composite(q, ((N - q.width) // 2, (N - q.height) // 2))
    return im.convert("RGB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("poza")
    p.add_argument("--fundal", default="verde", choices=list(FUNDALURI))
    p.add_argument("--lat", type=float, default=.86)
    p.add_argument("--sus", type=float, default=-.01, help="urcă sau coboară ziarul")
    p.add_argument("--iesire", default="icoana-1024.png")
    p.add_argument("--pune-in-aplicatie", action="store_true")
    a = p.parse_args()

    print("curăţ picătura…")
    drop = curata(a.poza)
    print(f"   picătura: {drop.size[0]}×{drop.size[1]}")
    icoana = compune(drop, ziarul(), a.fundal, a.lat, a.sus)
    icoana.save(a.iesire)
    print(f"✅ {a.iesire}")

    if a.pune_in_aplicatie:
        dest = os.path.expanduser(
            "~/Projects/farabaliverne-ios/Sources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        icoana.save(dest)
        print(f"✅ pusă în aplicaţie: {dest}")
        print("   acum: cd ~/Projects/farabaliverne-ios && xcodegen generate && xcodebuild …")


if __name__ == "__main__":
    main()

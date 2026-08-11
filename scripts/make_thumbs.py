"""
Miniaturi pentru cardurile de pe homepage.

Cardurile cereau poza la mărimea originală. Cu 63 de carduri, prima pagină
ajunsese să tragă ~34 MB de imagini — de pe telefon, pe 4G, omul pleacă
înainte să se încarce. Miniatura de 520px face ~40 KB în loc de ~550 KB.
"""

import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "img", "articole")
DST = os.path.join(ROOT, "img", "carduri")

LATIME = 520
KB_MAX = 60


def thumb(src_path):
    """Întoarce calea miniaturii, relativă la rădăcină."""
    os.makedirs(DST, exist_ok=True)
    slug = os.path.splitext(os.path.basename(src_path))[0]
    out = os.path.join(DST, slug + ".jpg")

    if (os.path.exists(out)
            and os.path.getmtime(out) >= os.path.getmtime(src_path)):
        return os.path.relpath(out, ROOT)

    cel_mai_bun = None
    for calitate in ("high", "medium", "low"):
        subprocess.run(
            ["sips", "-Z", str(LATIME), "-s", "format", "jpeg",
             "-s", "formatOptions", calitate, src_path, "--out", out],
            capture_output=True, check=False,
        )
        if not os.path.exists(out):
            continue
        marime = os.path.getsize(out)
        if cel_mai_bun is None or marime < cel_mai_bun:
            cel_mai_bun = marime
        if marime <= KB_MAX * 1024:
            break

    return os.path.relpath(out, ROOT) if os.path.exists(out) else None


def main():
    surse = [p for p in sorted(glob.glob(os.path.join(SRC, "*")))
             if not p.endswith(".tmp.jpg")]
    if not surse:
        print("nicio poză de procesat")
        return

    total_src = total_dst = 0
    facute = 0
    for p in surse:
        total_src += os.path.getsize(p)
        rel = thumb(p)
        if rel:
            total_dst += os.path.getsize(os.path.join(ROOT, rel))
            facute += 1

    print(f"miniaturi: {facute}/{len(surse)}")
    print(f"  original: {total_src // 1024} KB")
    print(f"  miniaturi: {total_dst // 1024} KB "
          f"({total_dst * 100 // max(total_src, 1)}%)")
    if facute:
        print(f"  medie: {total_dst // facute // 1024} KB")


if __name__ == "__main__":
    main()

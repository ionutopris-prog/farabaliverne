"""
Foaia de verificare: fiecare articol lângă poza propusă pentru el.

Rostul ei e ca fondatorul să prindă din ochi asocierile pe care niciun filtru
nu le prinde. Nivelul de încredere e marcat, pentru că nu toate propunerile
sunt la fel de sigure:

  persoană — Commons are portrete bune; aproape sigur corect
  entitate — instituție/loc recunoscut din titlu; de obicei bun
  titlu    — substantive proprii, ultima soluție; aici sunt greșelile
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "preview", "propuneri.json")
OUT = os.path.join(ROOT, "preview", "verificare.html")

with open(SRC, encoding="utf-8") as fh:
    items = json.load(fh)

TIER = {
    "persoană": ("sigur", "Portret de pe Commons — aproape sigur corect"),
    "entitate": ("bun", "Instituție sau loc recunoscut din titlu"),
    "titlu": ("slab", "Derivat din cuvintele titlului — aici apar greșelile"),
}

cards = []
for it in sorted(items, key=lambda x: ({"titlu": 0, "entitate": 1, "persoană": 2,
                                        None: -1}.get(x["query_type"], 3),
                                       x["slug"])):
    photo = it["photo"]
    tier, tip = TIER.get(it["query_type"], ("lipsa", "Nicio poză potrivită găsită"))

    if photo:
        media = (f'<img src="{photo["url"]}" alt="" loading="lazy" '
                 f'referrerpolicy="no-referrer">')
        meta = (f'<div class="ph-meta">{photo["author"]} · {photo["license"]}<br>'
                f'<span class="ph-title">{photo["title"][:70]}</span></div>')
    else:
        media = '<div class="nophoto">fără poză<br><span>rămâne cardul actual</span></div>'
        meta = '<div class="ph-meta">—</div>'

    cards.append(f"""    <article class="card t-{tier}">
      <div class="shot">{media}</div>
      <div class="body">
        <div class="row">
          <span class="badge b-{tier}">{it["query_type"] or "fără"}</span>
          <span class="cat">{it["category"]}</span>
        </div>
        <h2>{it["title"]}</h2>
        <div class="q">căutat: <code>{it["query"] or "—"}</code></div>
        {meta}
      </div>
    </article>""")

n_total = len(items)
n_photo = sum(1 for i in items if i["photo"])
n_weak = sum(1 for i in items if i["query_type"] == "titlu")

HTML = f"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verificare poze — Fără Baliverne</title>
<style>
  :root{{
    --bg:#f2f3ef; --card:#fff; --ink:#1a1d1a; --soft:#5a625a; --faint:#8f978f;
    --line:#dfe3dd; --sigur:#2f8a49; --bun:#c2861a; --slab:#a5372a; --lipsa:#8f978f;
  }}
  @media (prefers-color-scheme:dark){{
    :root:not([data-theme="light"]){{
      --bg:#14161a; --card:#1c2026; --ink:#e6eae6; --soft:#a8b2a8; --faint:#7c857c;
      --line:#2a3038; --sigur:#54c47c; --bun:#e0ac45; --slab:#e07a6a; --lipsa:#7c857c;
    }}
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.55 ui-serif,"Iowan Old Style",Georgia,serif}}
  .wrap{{max-width:1180px;margin:0 auto;padding:34px 22px 80px}}
  header{{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:26px}}
  h1{{font-size:30px;margin:0 0 8px;letter-spacing:-.01em}}
  .sum{{color:var(--soft);font-size:15px;margin:0}}
  .legend{{display:flex;flex-wrap:wrap;gap:16px;margin-top:16px;
    font:600 12px/1.4 ui-monospace,Menlo,monospace}}
  .legend span{{display:flex;gap:6px;align-items:center}}
  .dot{{width:10px;height:10px;border-radius:2px;display:block}}
  .grid{{display:grid;gap:14px}}
  .card{{display:grid;grid-template-columns:210px 1fr;gap:16px;background:var(--card);
    border:1px solid var(--line);border-left:4px solid var(--lipsa);
    border-radius:4px;overflow:hidden}}
  .card.t-sigur{{border-left-color:var(--sigur)}}
  .card.t-bun{{border-left-color:var(--bun)}}
  .card.t-slab{{border-left-color:var(--slab)}}
  .shot{{background:#0d0f12;position:relative;min-height:132px}}
  .shot img{{width:100%;height:100%;object-fit:cover;display:block;position:absolute;inset:0}}
  .nophoto{{position:absolute;inset:0;display:flex;flex-direction:column;
    align-items:center;justify-content:center;color:#7c857c;
    font:700 12px/1.5 ui-monospace,Menlo,monospace;text-align:center}}
  .nophoto span{{font-weight:400;opacity:.7}}
  .body{{padding:14px 16px 15px;min-width:0}}
  .row{{display:flex;gap:8px;align-items:center;margin-bottom:7px}}
  .badge{{font:700 10.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.06em;
    text-transform:uppercase;padding:4px 7px;border-radius:3px;color:#fff}}
  .b-sigur{{background:var(--sigur)}} .b-bun{{background:var(--bun)}}
  .b-slab{{background:var(--slab)}} .b-lipsa{{background:var(--lipsa)}}
  .cat{{font:600 11px/1 ui-monospace,Menlo,monospace;color:var(--faint);
    letter-spacing:.05em;text-transform:uppercase}}
  h2{{font-size:16.5px;line-height:1.35;margin:0 0 7px;font-weight:600}}
  .q{{font:12px/1.5 ui-monospace,Menlo,monospace;color:var(--soft);margin-bottom:5px}}
  .q code{{background:rgba(127,127,127,.13);padding:1px 5px;border-radius:3px}}
  .ph-meta{{font:11.5px/1.5 ui-monospace,Menlo,monospace;color:var(--faint)}}
  .ph-title{{opacity:.75}}
  @media(max-width:640px){{.card{{grid-template-columns:1fr}}.shot{{min-height:180px}}}}
</style></head><body>
<div class="wrap">
  <header>
    <h1>Ce poză primește fiecare articol</h1>
    <p class="sum">{n_photo} din {n_total} articole au o propunere.
      {n_weak} dintre ele vin din nivelul slab — alea merită privite întâi.
      Nimic nu s-a aplicat încă pe site.</p>
    <div class="legend">
      <span><i class="dot" style="background:var(--slab)"></i> derivat din titlu — verifică</span>
      <span><i class="dot" style="background:var(--bun)"></i> instituție sau loc</span>
      <span><i class="dot" style="background:var(--sigur)"></i> portret de persoană</span>
      <span><i class="dot" style="background:var(--lipsa)"></i> fără poză</span>
    </div>
  </header>
  <div class="grid">
{chr(10).join(cards)}
  </div>
</div>
</body></html>
"""

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(HTML)

print(f"scris: {OUT}")
print(f"{n_photo}/{n_total} cu propunere · {n_weak} din nivelul slab")

#!/usr/bin/env python3
"""
Pagină locală de verificare a rosterului: preview/parlament.html

Nu e pagina de site — e unealta prin care fondatorul se uită peste toți cei 464,
unul câte unul, înainte ca ceva să ajungă public. Fiecare rând are linkul spre
fișa oficială de pe cdep.ro, ca verificarea să dureze o secundă, nu un minut.
"""
import html, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "data", "_parlament.json"), encoding="utf-8"))
oameni = d["oameni"]

def scurt(g):
    """Numele grupului, pe scurt. Atenţie la `.replace("al ", "")` naiv: mânca
    litere din interiorul cuvintelor („Naţional" → „Naţion"). Tăiem doar
    prefixul, nu oriunde în şir."""
    g = g.replace("Grupul parlamentar ", "")
    for pref in ("al ", "ale "):
        if g.startswith(pref):
            g = g[len(pref):]
    return g


def e(x):
    return html.escape(str(x if x is not None else ""))

randuri = []
for o in sorted(oameni, key=lambda x: (x["camera"] != "Camera Deputaților",
                                       x.get("bloc", 99), x.get("loc_in_bloc", 0))):
    fara = "" if o.get("circumscriptie_nr") else ' class="fara"'
    randuri.append(
        f'<tr data-c="{e(o["camera"])}" data-g="{e(o["grup"])}">'
        f'<td class="n">{e(o.get("loc",""))}</td>'
        f'<td><b>{e(o["nume"])}</b></td>'
        f'<td>{e(scurt(o["grup"]))}</td>'
        f'<td>{e(o["camera"])}</td>'
        f'<td{fara}>{e(o.get("circumscriptie") or "—")}'
        f'{" · nr." + str(o["circumscriptie_nr"]) if o.get("circumscriptie_nr") else ""}</td>'
        f'<td class="n">bloc {e(o.get("bloc",""))} / {e(o.get("loc_in_bloc",""))}</td>'
        f'<td><a href="{e(o["fisa"])}" target="_blank" rel="noopener">fișa ↗</a></td></tr>')

grupuri = sorted({o["grup"] for o in oameni})
optiuni = "".join(f'<option value="{e(g)}">{e(g[:50])}</option>' for g in grupuri)
nd = sum(1 for o in oameni if o["camera"] == "Camera Deputaților")
ns = len(oameni) - nd
fara_c = sum(1 for o in oameni if not o.get("circumscriptie_nr"))

pagina = f"""<!doctype html><html lang="ro"><head><meta charset="utf-8">
<title>Roster Parlament — verificare locală</title>
<style>
 :root{{--ink:#22271f;--soft:#556050;--faint:#87907c;--paper:#e7f0e4;--card:#fff;
        --line:#d6e2d0;--accent:#a5372a}}
 body{{margin:0;background:var(--paper);color:var(--ink);
      font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}}
 .wrap{{max-width:1180px;margin:0 auto;padding:26px 22px 60px}}
 h1{{font-family:Georgia,serif;font-size:28px;margin:0 0 4px;letter-spacing:-.02em}}
 .sub{{color:var(--soft);margin:0 0 18px}}
 .bara{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;position:sticky;top:0;
        background:var(--paper);padding:10px 0;z-index:2;border-bottom:1px solid var(--line)}}
 input,select{{padding:8px 12px;border:1px solid #bfd2b7;border-radius:30px;font-size:14px;
               background:var(--card);color:var(--ink)}}
 input{{min-width:260px}}
 table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);
        border-radius:12px;overflow:hidden}}
 th{{text-align:left;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);
     padding:11px 12px;border-bottom:1px solid var(--line);background:#f1f7ef}}
 td{{padding:9px 12px;border-bottom:1px solid #eef4ec;vertical-align:top}}
 tr:hover td{{background:#f7fbf6}}
 .n{{color:var(--faint);white-space:nowrap;font-variant-numeric:tabular-nums}}
 .fara{{color:#a8710b;background:#fbf0d6}}
 a{{color:var(--accent)}}
 .stat{{display:flex;gap:22px;flex-wrap:wrap;margin-bottom:16px;color:var(--soft);font-size:13.5px}}
 .stat b{{color:var(--ink)}}
</style></head><body><div class="wrap">
<h1>Roster Parlament — verificare</h1>
<p class="sub">Sursa: cdep.ro, indexul de grupuri + circumscripții. Actualizat {e(d.get('actualizat',''))}.
Fiecare rând duce la fișa oficială. Nimic de aici nu e public încă.</p>
<div class="stat">
  <span><b>{len(oameni)}</b> parlamentari</span>
  <span><b>{nd}</b> deputați</span>
  <span><b>{ns}</b> senatori</span>
  <span><b>{fara_c}</b> fără circumscripție <span style="color:var(--faint)">(minorități, aleși național)</span></span>
</div>
<div class="bara">
  <input id="q" placeholder="caută nume, județ, grup…" autofocus>
  <select id="cam"><option value="">ambele camere</option>
    <option>Camera Deputaților</option><option>Senat</option></select>
  <select id="gr"><option value="">toate grupurile</option>{optiuni}</select>
  <span id="nr" style="align-self:center;color:var(--faint)"></span>
</div>
<table><thead><tr><th>loc</th><th>nume</th><th>grup</th><th>cameră</th>
<th>circumscripție</th><th>poziție</th><th></th></tr></thead>
<tbody id="t">{''.join(randuri)}</tbody></table>
<script>
 const q=document.getElementById('q'),cam=document.getElementById('cam'),
       gr=document.getElementById('gr'),nr=document.getElementById('nr'),
       randuri=[...document.querySelectorAll('#t tr')];
 function filtreaza(){{
   const s=q.value.toLowerCase().trim(), c=cam.value, g=gr.value; let n=0;
   for(const r of randuri){{
     const ok=(!s||r.textContent.toLowerCase().includes(s))
            &&(!c||r.dataset.c===c)&&(!g||r.dataset.g===g);
     r.style.display=ok?'':'none'; if(ok)n++;
   }}
   nr.textContent=n+' din {len(oameni)}';
 }}
 [q,cam,gr].forEach(el=>el.addEventListener('input',filtreaza)); filtreaza();
</script></div></body></html>"""

os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
cale = os.path.join(ROOT, "preview", "parlament.html")
open(cale, "w", encoding="utf-8").write(pagina)
print(f"scris: preview/parlament.html · {len(oameni)} parlamentari")

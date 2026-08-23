#!/usr/bin/env python3
"""
Generează `parlament.html` — hemiciclul plenului reunit, din `data/_parlament.json`.

Aceeaşi metodă ca la `politicieni.html`: ia `index.html` ca înveliş (cap, meniu,
subsol) şi înlocuieşte doar `<main>`. Aşa pagina moşteneşte automat orice
schimbare de stil sau de navigaţie, fără să fie întreţinută separat.

Numele duc la fişa oficială de pe cdep.ro. Paginile noastre per parlamentar nu
există încă — un link către o pagină inexistentă e o promisiune încălcată, iar
fişa oficială e oricum sursa primară.

    python3 scripts/build_parlament.py
"""
import html, json, os, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCURT = {"Partidului Social Democrat": "PSD", "AUR": "AUR",
         "Partidului Naţional Liberal": "PNL", "Uniunii Salvaţi România": "USR",
         "Uniunii Democrate Maghiare din România": "UDMR", "Uniţi pentru România": "UPR",
         "minorităţilor naţionale": "Minorități", "Deputaţi neafiliaţi": "Neafiliați",
         "Senatori neafiliati": "Neafiliați", "SOS România": "SOS",
         "PACE - Întâi Romania": "PACE"}
CULORI = {"PSD": "#c0392b", "AUR": "#1f3a63", "PNL": "#d8a72b", "USR": "#2f7fc1",
          "UDMR": "#3f8f3f", "UPR": "#7a5c9e", "Minorități": "#8a8f83",
          "Neafiliați": "#b0b6aa", "SOS": "#6d4a8f", "PACE": "#2e8b6f"}


def scurt(g):
    g = g.replace("Grupul parlamentar ", "")
    for p in ("al ", "ale "):
        if g.startswith(p):
            g = g[len(p):]
    return SCURT.get(g, g[:14])


def fara_diacritice(n):
    return "".join(c for c in unicodedata.normalize("NFD", n)
                   if unicodedata.category(c) != "Mn")


def date():
    d = json.load(open(os.path.join(ROOT, "data", "_parlament.json"), encoding="utf-8"))
    pe = {}
    for x in d["oameni"]:
        pe.setdefault(scurt(x["grup"]), []).append(x)
    ordine = sorted(pe, key=lambda g: -len(pe[g]))
    oameni, legenda = [], []
    for gi, g in enumerate(ordine):
        lista = sorted(pe[g], key=lambda x: fara_diacritice(x["nume"]).lower())
        legenda.append({"nume": g, "n": len(lista), "culoare": CULORI.get(g, "#8a8f83")})
        for x in lista:
            oameni.append([x["nume"], gi,
                           "D" if x["camera"] == "Camera Deputaților" else "S",
                           x.get("circumscriptie") or "la nivel naţional",
                           x["fisa"]])
    return oameni, legenda, d.get("actualizat", "")


def main_html(oameni, legenda, actualizat):
    leg = "".join(
        f'<span class="pl-leg"><i style="background:{l["culoare"]}"></i>'
        f'<b>{html.escape(l["nume"])}</b> {l["n"]}</span>' for l in legenda)
    return f'''  <main>
    <div class="wrap" style="max-width:1180px">
      <a href="index.html" class="backlink">← Înapoi la prima pagină</a>
      <div class="pl-cap">
        <h1>Parlamentul României</h1>
        <span class="pl-sub">Plen reunit · {len(oameni)} de locuri · 2024–2028</span>
      </div>
      <p class="pl-intro">Fiecare scaun e un om cu nume. Treci cu degetul sau cu cursorul peste sală.
        <b>Nu dăm note și nu ținem scor</b> — arătăm ce e documentat, tragi tu linia.</p>

      <div class="pl-card">
        <div class="pl-bara" id="plBara">
          <i id="plPunct"></i>
          <div class="pl-txt">
            <div class="pl-nume" id="plNume">Plimbă degetul sau cursorul peste sală</div>
            <div class="pl-det" id="plDet">Fiecare scaun e un om cu nume — apare aici.</div>
          </div>
          <div class="pl-dr" id="plDr">{len(oameni)} de locuri</div>
        </div>
        <div class="pl-sala" id="plSala"><div class="pl-prezidiu">Prezidiu</div></div>
        <div class="pl-legenda">{leg}</div>
      </div>

      <div class="pl-note">
        <div class="pl-nota">
          <h2>De ce stau așa</h2>
          <p>Locurile se dau <b>pe grup, nu pe om</b>. Art. 18 din Regulamentul Camerei: președintele
          împreună cu liderii de grup repartizează locurile pentru fiecare grup parlamentar. Art. 20 din
          Regulamentul Senatului: prin negociere între lideri, în ordinea descrescătoare a mărimii grupurilor.
          <b>Poziția fiecăruia în interiorul blocului nu o publică nimeni</b> — aici e alfabetică, și spunem asta.</p>
        </div>
        <div class="pl-nota">
          <h2>Ce NU găsești aici</h2>
          <p>Note, clasamente, „cei mai buni / cei mai slabi". Un scor ar fi opinia noastră îmbrăcată în cifre.
          Arătăm ce e documentat și lăsăm cititorul să judece. Un parlamentar cu multe intervenții și unul
          cu zero apar la fel — datele sunt datele.</p>
        </div>
        <div class="pl-nota pl-sursa">
          <h2>Sursa</h2>
          <p>cdep.ro — indexul grupurilor parlamentare și cel pe circumscripții electorale.
          Verificat {html.escape(actualizat)}: <b>330 de deputați, 134 de senatori, 43 de circumscripții</b>.
          Fiecare nume duce la fișa lui oficială.</p>
        </div>
      </div>
    </div>
  </main>
  <script id="plDate" type="application/json">{json.dumps({"o": oameni, "l": legenda}, ensure_ascii=False)}</script>'''


STIL = '''
/* ─── Parlamentul României ─────────────────────────────────────── */
.pl-cap{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap;margin:0 0 6px}
.pl-cap h1{font-family:var(--serif);font-size:38px;line-height:1.08;margin:0;letter-spacing:-.02em}
.pl-sub{padding-bottom:7px;font-size:12.5px;color:var(--ink-faint);letter-spacing:.06em;
        text-transform:uppercase;font-weight:800}
.pl-intro{max-width:740px;margin:0 0 22px;font-size:16px;line-height:1.55;color:var(--ink-soft)}
.pl-card{background:var(--card);border:1px solid var(--line);border-radius:16px;
         box-shadow:var(--shadow);padding:22px}
.pl-bara{display:flex;align-items:center;gap:14px;min-height:62px;margin-bottom:12px;
         background:var(--paper-2);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
.pl-bara i{width:16px;height:16px;border-radius:50%;background:var(--line-2);
           border:1px solid rgba(34,39,31,.2);flex:0 0 auto}
.pl-txt{min-width:0}
.pl-nume{font-family:var(--serif);font-size:19px;line-height:1.2;letter-spacing:-.01em}
.pl-nume a{color:var(--accent);text-underline-offset:3px}
.pl-det{font-size:13.5px;color:var(--ink-soft);margin-top:2px}
.pl-dr{margin-left:auto;text-align:right;flex:0 0 auto;font-size:12.5px;color:var(--ink-faint)}
.pl-sala{position:relative;height:420px;max-width:1060px;margin:0 auto}
.pl-scaun{position:absolute;border-radius:50%;border:1px solid rgba(34,39,31,.18);
          box-sizing:border-box;cursor:pointer;transition:transform .08s}
.pl-scaun:hover,.pl-scaun.pl-sel{transform:scale(1.8);z-index:5;
          box-shadow:0 0 0 2px var(--card),0 0 0 3.5px var(--ink)}
.pl-prezidiu{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:190px;height:26px;
   border-radius:6px;background:var(--paper-2);border:1px solid var(--line-2);display:flex;
   align-items:center;justify-content:center;font-size:11px;letter-spacing:.1em;
   text-transform:uppercase;color:var(--ink-faint);font-weight:800}
.pl-legenda{display:flex;gap:20px;flex-wrap:wrap;align-items:center;border-top:1px solid var(--line);
            margin-top:16px;padding-top:15px}
.pl-leg{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--ink-soft)}
.pl-leg i{width:12px;height:12px;border-radius:50%;border:1px solid rgba(34,39,31,.18);display:inline-block}
.pl-leg b{color:var(--ink)}
.pl-note{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:16px}
.pl-nota{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}
.pl-nota h2{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);
            font-weight:800;margin:0 0 7px}
.pl-nota p{margin:0;font-size:14px;line-height:1.5;color:var(--ink-soft)}
.pl-sursa{background:var(--accent-soft);border-color:#eccfc4}
.pl-sursa h2,.pl-sursa p{color:var(--accent-deep)}
@media (max-width:900px){
  .pl-note{grid-template-columns:1fr}
  .pl-cap h1{font-size:28px}
  .pl-sala{height:300px}
  .pl-bara{flex-wrap:wrap}
  .pl-dr{margin-left:0;width:100%;text-align:left}
}
'''

SCRIPT = '''
(function(){
  var el=document.getElementById("plDate"); if(!el) return;
  var D=JSON.parse(el.textContent), O=D.o, L=D.l;
  var sala=document.getElementById("plSala");
  var lat=sala.clientWidth||1060, inalt=sala.clientHeight||420;
  var cx=lat/2, cy=inalt-24, r0=inalt*0.26, randuri=10, d=Math.max(8,Math.round(lat/82));
  var dr=(Math.min(cx,cy)-r0-d)/(randuri-1);
  var g=[],sg=0,i,j; for(i=0;i<randuri;i++){g.push(r0+i*dr);sg+=r0+i*dr;}
  var per=[],ram=O.length;
  for(i=0;i<randuri;i++){var n=(i===randuri-1)?ram:Math.round(O.length*g[i]/sg);per.push(n);ram-=n;}
  var k=0,poz=[];
  for(i=0;i<randuri;i++){
    var r=g[i];
    for(j=0;j<per[i]&&k<O.length;j++,k++){
      var t=per[i]===1?0.5:j/(per[i]-1), a=Math.PI-t*Math.PI;
      var s=document.createElement("div");
      s.className="pl-scaun"; s.dataset.i=k;
      s.style.left=Math.round(cx+r*Math.cos(a)-d/2)+"px";
      s.style.top=Math.round(cy-r*Math.sin(a)-d/2)+"px";
      s.style.width=d+"px"; s.style.height=d+"px";
      s.style.background=L[O[k][1]].culoare;
      s.setAttribute("aria-label",O[k][0]);
      sala.appendChild(s); poz.push(s);
    }
  }
  var nume=document.getElementById("plNume"), det=document.getElementById("plDet"),
      dr2=document.getElementById("plDr"), punct=document.getElementById("plPunct"), sel=-1;
  function arata(idx){
    var o=O[idx]; if(!o) return;
    if(sel>=0&&poz[sel]) poz[sel].classList.remove("pl-sel");
    sel=idx; poz[idx].classList.add("pl-sel");
    nume.innerHTML='<a href="'+o[4]+'" target="_blank" rel="noopener noreferrer">'+o[0]+'</a>';
    det.textContent=L[o[1]].nume+" · "+(o[2]==="D"?"Camera Deputaților":"Senat");
    dr2.textContent="Circumscripția "+o[3];
    punct.style.background=L[o[1]].culoare;
  }
  sala.addEventListener("mouseover",function(e){
    var s=e.target.closest(".pl-scaun"); if(s) arata(+s.dataset.i);
  });
  sala.addEventListener("click",function(e){
    var s=e.target.closest(".pl-scaun"); if(!s) return;
    var idx=+s.dataset.i;
    // A doua atingere pe acelaşi scaun deschide fişa. Prima doar selectează:
    // pe telefon degetul trece peste zeci de scaune, iar deschiderea din prima
    // te-ar scoate de pe pagină din greşeală.
    if(idx===sel) window.open(O[idx][4],"_blank","noopener");
    else arata(idx);
  },{passive:true});
})();
'''


def main():
    invelis = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    oameni, legenda, actualizat = date()

    s = re.sub(r"(?is)  <main>.*?  </main>", lambda _: main_html(oameni, legenda, actualizat),
               invelis, count=1)
    s = s.replace("</style>", STIL + "</style>", 1)
    s = s.replace("</body>", f"<script>{SCRIPT}</script>\n</body>", 1)

    titlu = "Parlamentul României — toți cei 464 de parlamentari — Fără Baliverne"
    s = re.sub(r"(?is)<title>.*?</title>", lambda _: f"<title>{titlu}</title>", s, count=1)
    for a, b in (("https://farabaliverne.ro/", "https://farabaliverne.ro/parlament.html"),):
        s = s.replace(f'<link rel="canonical" href="{a}">', f'<link rel="canonical" href="{b}">')
        s = s.replace(f'<meta property="og:url" content="{a}">', f'<meta property="og:url" content="{b}">')
    dek = ("Toți cei 464 de parlamentari ai legislaturii 2024–2028, așezați în plenul reunit. "
           "Treci peste un scaun și vezi cine îl ocupă, din ce grup e și ce circumscripție reprezintă.")
    for k in ("description", "og:description", "twitter:description"):
        s = re.sub(rf'(<meta (?:property|name)="{k}" content=")[^"]*(">)',
                   lambda m: m.group(1) + dek + m.group(2), s, count=1)

    cale = os.path.join(ROOT, "parlament.html")
    open(cale, "w", encoding="utf-8").write(s)
    print(f"scris: parlament.html · {len(oameni)} parlamentari · {len(s)//1024} KB")


if __name__ == "__main__":
    main()

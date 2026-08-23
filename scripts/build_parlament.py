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


def slug(n):
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", fara_diacritice(n).lower()).strip("-")


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
                           "parlamentar/" + slug(x["nume"]) + ".html",   # pagina noastră
                           x["fisa"],                                     # sursa oficială
                           x.get("circumscriptie_nr") or 0])              # pentru „Parlamentarul tău"
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
          <div class="pl-dreapta">
            <div class="pl-dr" id="plDr">{len(oameni)} de locuri</div>
            <div class="pl-cauta">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.4" stroke-linecap="round" aria-hidden="true">
                <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/></svg>
              <input id="plQ" type="search" placeholder="Parlamentarul tău" autocomplete="off"
                     aria-label="Caută parlamentarul tău după localitate sau nume">
            </div>
          </div>
        </div>
        <div class="pl-sala" id="plSala"><div class="pl-prezidiu">Prezidiu</div></div>
        <div class="pl-rezultat" id="plRez" hidden></div>
        <div class="pl-legenda">{leg}</div>
      </div>

      <section class="pl-prez">
        <h2>Prezidiul — cine conduce și de ce</h2>
        <p class="pl-prez-sub">Locurile din prezidiu nu se ocupă din obicei, ci după regulament.
          Fiecare poziție are articolul care o impune.</p>

        <div class="pl-masa">
          <div class="pl-loc"><span>Secretar · Camera Deputaților</span><b>un secretar al Camerei</b></div>
          <div class="pl-loc pl-loc-mare"><span>Prezidează, alternativ</span>
            <b>Președintele Camerei Deputaților / Președintele Senatului</b></div>
          <div class="pl-loc"><span>Secretar · Senat</span><b>un secretar al Senatului</b></div>
        </div>
        <p class="pl-temei"><b>Art. 30, Regulamentul activităților comune:</b>
          „Lucrările ședințelor comune sunt conduse, <b>alternativ</b>, de președintele Camerei
          Deputaților și de președintele Senatului, <b>asistați de 2 secretari, câte unul de la
          fiecare Cameră</b>."</p>

        <div class="pl-prez-doua">
          <div class="pl-nota">
            <h3>Ședință obișnuită, o singură Cameră</h3>
            <p>Președintele Camerei conduce lucrările plenului, <b>asistat obligatoriu de 2 secretari</b>.
              Tot el acordă cuvântul, stabilește ordinea votării și precizează semnificația votului.
              <span class="pl-art">Art. 34 lit. b), Regulamentul Camerei Deputaților</span></p>
          </div>
          <div class="pl-nota pl-ceremonie">
            <h3>Ședința de constituire — ceremonia</h3>
            <p>Până la alegerea Biroului permanent, lucrările sunt conduse de deputatul cu
              <b>cel mai mare număr de mandate</b>, ca <b>președinte senior</b>, asistat de
              <b>cei mai tineri 4 deputați</b>, în calitate de secretari. La egalitate de mandate,
              conduce cel mai în vârstă.
              <span class="pl-art">Art. 2 alin. (1), Regulamentul Camerei Deputaților</span></p>
          </div>
        </div>

        <div class="pl-comune">
          <h3>Ce se face doar în ședință comună</h3>
          <div class="pl-comune-g">
            <span>Depunerea jurământului de către Președintele României</span>
            <span>Punerea sub acuzare a Președintelui pentru înaltă trădare</span>
            <span>Suspendarea din funcție a Președintelui</span>
            <span>Numirea Avocatului Poporului</span>
            <span>Reexaminarea Legii bugetului de stat</span>
            <span>Revizuirea Constituției, când Camerele nu se înțeleg</span>
          </div>
          <p class="pl-art">Art. 13, Regulamentul activităților comune</p>
        </div>
      </section>

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
.pl-dreapta{margin-left:auto;text-align:right;flex:0 0 auto;display:flex;flex-direction:column;
            align-items:flex-end;gap:7px}
.pl-dr{font-size:12.5px;color:var(--ink-faint)}
.pl-cauta{display:flex;align-items:center;gap:6px;width:190px;height:26px;box-sizing:border-box;
          padding:0 11px;border:1px solid var(--line-2);border-radius:30px;background:var(--paper-2);
          color:var(--ink-faint);transition:border-color .15s,background .15s}
.pl-cauta:focus-within{border-color:var(--accent);background:var(--card);color:var(--accent)}
.pl-cauta svg{flex:0 0 auto}
.pl-cauta input{border:0;background:transparent;outline:0;width:100%;font:inherit;font-size:12.5px;
                color:var(--ink);padding:0}
.pl-cauta input::placeholder{color:var(--ink-faint);font-weight:700}
.pl-cauta input::-webkit-search-cancel-button{-webkit-appearance:none}
.pl-rezultat{margin-top:14px;border-top:1px solid var(--line);padding-top:15px}
.pl-rez-cap{font-family:var(--serif);font-size:20px;margin:0 0 3px;letter-spacing:-.01em}
.pl-rez-sub{margin:0 0 14px;font-size:13.5px;color:var(--ink-soft);line-height:1.55}
.pl-rez-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:10px}
.pl-om{display:flex;gap:10px;align-items:flex-start;background:var(--paper-2);border:1px solid var(--line);
       border-radius:11px;padding:11px 13px;text-decoration:none}
.pl-om:hover{border-color:var(--line-2);background:var(--card)}
.pl-om i{width:10px;height:10px;border-radius:50%;flex:0 0 auto;margin-top:5px;
         border:1px solid rgba(34,39,31,.2)}
.pl-om b{display:block;font-size:14.5px;line-height:1.35;color:var(--ink)}
.pl-om span{font-size:12.5px;color:var(--ink-faint)}
.pl-optiuni{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.pl-optiuni button{padding:6px 13px;border:1px solid var(--line-2);border-radius:30px;
                   background:var(--card);font:inherit;font-size:13px;color:var(--ink);cursor:pointer}
.pl-optiuni button:hover{border-color:var(--accent);color:var(--accent)}
@media (max-width:900px){
  .pl-dreapta{margin-left:0;width:100%;align-items:stretch;text-align:left}
  .pl-cauta{width:100%;height:34px}
}

.pl-prez{background:var(--card);border:1px solid var(--line);border-radius:16px;
         box-shadow:var(--shadow);padding:24px;margin:16px 0 0}
.pl-prez h2{font-family:var(--serif);font-size:24px;margin:0 0 5px;letter-spacing:-.01em}
.pl-prez-sub{margin:0 0 18px;font-size:14.5px;color:var(--ink-soft);line-height:1.55;max-width:760px}
.pl-masa{display:flex;gap:12px;align-items:stretch;margin-bottom:12px;flex-wrap:wrap}
.pl-loc{flex:1 1 180px;background:var(--paper-2);border:1px solid var(--line);border-radius:11px;padding:14px 16px}
.pl-loc span{display:block;font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;
             font-weight:800;color:var(--ink-faint);margin-bottom:5px}
.pl-loc b{font-size:14.5px;line-height:1.4;font-weight:600}
.pl-loc-mare{flex:2 1 320px;background:var(--ink);border-color:var(--ink)}
.pl-loc-mare span{color:#c9d3c2}
.pl-loc-mare b{color:#fff}
.pl-temei{background:var(--paper-2);border:1px solid var(--line);border-radius:11px;
          padding:13px 16px;font-size:14px;line-height:1.55;color:var(--ink-soft);margin:0 0 16px}
.pl-temei b{color:var(--ink)}
.pl-prez-doua{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
.pl-prez h3{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);
            font-weight:800;margin:0 0 8px}
.pl-prez .pl-nota p{font-size:14.5px;line-height:1.6}
.pl-ceremonie{background:#fdfaf1;border-color:#e6d9b8}
.pl-ceremonie h3{color:#8a6a15}
.pl-ceremonie p{color:#5f4d1e}
.pl-art{display:block;margin-top:8px;font-size:12.5px;color:var(--ink-faint);font-style:italic}
.pl-comune{border-top:1px solid var(--line);padding-top:16px}
.pl-comune-g{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 22px}
.pl-comune-g span{font-size:14px;line-height:1.45;padding:7px 0;border-bottom:1px solid var(--line);
                  color:var(--ink-soft)}
@media (max-width:900px){
  .pl-prez-doua{grid-template-columns:1fr}
  .pl-comune-g{grid-template-columns:1fr}
  .pl-prez h2{font-size:20px}
}

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
.pl-sep{color:var(--line-2)}
.pl-src{font-size:12.5px}
.pl-det{font-size:13.5px;color:var(--ink-soft);margin-top:2px}
.pl-dr{margin-left:auto;text-align:right;flex:0 0 auto;font-size:12.5px;color:var(--ink-faint)}
.pl-sala{position:relative;height:560px;max-width:1000px;margin:0 auto}
.pl-scaun{position:absolute;border-radius:50%;border:1px solid rgba(34,39,31,.18);padding:0;
          box-sizing:border-box;cursor:pointer;transition:transform .1s;appearance:none}
.pl-prezidiu{position:absolute;left:50%;top:0;transform:translateX(-50%);width:200px;height:26px;
   border-radius:6px;background:var(--paper-2);border:1px solid var(--line-2);display:flex;
   align-items:center;justify-content:center;font-size:11px;letter-spacing:.1em;
   text-transform:uppercase;color:var(--ink-faint);font-weight:800;z-index:2}
.pl-scaun:hover,.pl-scaun.pl-sel,.pl-scaun:focus-visible{transform:scale(1.45);z-index:5;outline:0;
          box-shadow:0 0 0 2px var(--card),0 0 0 3.5px var(--ink)}
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
  .pl-sala{height:400px}
  .pl-bara{flex-wrap:wrap}
  .pl-dr{margin-left:0;width:100%;text-align:left}
}
'''

SCRIPT = '''
(function(){
  var el=document.getElementById("plDate"); if(!el) return;
  var D=JSON.parse(el.textContent), O=D.o, L=D.l;
  var sala=document.getElementById("plSala");
  // Semicerc cu prezidiul SUS, iar oamenii aşezaţi PE COLOANE: fiecare coloană
  // se umple de jos în sus, apoi trecem la următoarea. Aşa fiecare partid ocupă
  // o FELIE continuă a sălii, cum arată în realitate.
  // (Varianta pe rânduri împrăştia acelaşi partid pe toată lăţimea — se vedea
  // ca dungi orizontale, nu ca grupuri aşezate împreună.)
  var lat=sala.clientWidth||1000, inalt=sala.clientHeight||470;
  // Fiecare PARTID începe pe coloană nouă. Altfel coloana de la graniţă avea
  // două culori (7 roşii + 3 bleumarin), iar blocurile arătau murdare.
  // Ultima coloană a unui partid poate fi mai scurtă — spaţiul gol e cinstit,
  // amestecul nu.
  var randuri=10, total=O.length;
  var col=[], gAct=-1;                     // câţi oameni intră în fiecare coloană
  for(var q=0;q<O.length;q++){
    if(O[q][1]!==gAct){ gAct=O[q][1]; col.push(0); }        // partid nou → coloană nouă
    else if(col[col.length-1]===randuri){ col.push(0); }    // coloana s-a umplut
    col[col.length-1]++;
  }
  var coloane=col.length;
  // Ca să NU se înghesuie: raza rândului interior se calculează din câte
  // coloane trebuie să încapă pe el. Lungimea arcului interior e π·r0, deci
  // r0 = coloane × (diametru + spaţiu) / π. Înainte r0 era o fracţiune fixă
  // din înălţime, iar rândurile de sus ieşeau lipite unul de altul.
  var d=Math.max(9,Math.min(15,Math.round(lat/78)));
  var spatiu=Math.max(3,Math.round(d*0.28));
  var cx=lat/2, cy=d*1.7;
  var r0=coloane*(d+spatiu)/Math.PI;
  var rMax=Math.min(cx-d, inalt-cy-d);
  var dr=Math.max(d+spatiu, (rMax-r0)/(randuri-1));

  var poz=[], k=0;
  for(var c=0;c<coloane && k<total;c++){
    var t=coloane===1?0.5:c/(coloane-1);
    var a=t*Math.PI;                       // 0 = stânga, π = dreapta
    for(var rr=randuri-1;rr>=randuri-col[c] && k<total;rr--){  // de JOS în SUS, câţi încap
      var r=r0+rr*dr;
      var s=document.createElement("button");
      s.type="button"; s.className="pl-scaun"; s.dataset.i=k;
      s.style.left=Math.round(cx-r*Math.cos(a)-d/2)+"px";
      s.style.top=Math.round(cy+r*Math.sin(a)-d/2)+"px";
      s.style.width=d+"px"; s.style.height=d+"px";
      s.style.background=L[O[k][1]].culoare;
      s.setAttribute("aria-label",O[k][0]+" — "+L[O[k][1]].nume);
      sala.appendChild(s); poz.push(s); k++;
    }
  }

  var nume=document.getElementById("plNume"), det=document.getElementById("plDet"),
      dr2=document.getElementById("plDr"), punct=document.getElementById("plPunct"), sel=-1;
  function arata(idx){
    var o=O[idx]; if(!o) return;
    if(sel>=0&&poz[sel]) poz[sel].classList.remove("pl-sel");
    sel=idx; poz[idx].classList.add("pl-sel");
    nume.innerHTML='<a href="'+o[4]+'">'+o[0]+'</a>';
    det.innerHTML=L[o[1]].nume+" · "+(o[2]==="D"?"Camera Deputaților":"Senat")
      +' <span class="pl-sep">·</span> <a class="pl-src" href="'+o[5]
      +'" target="_blank" rel="noopener noreferrer">fișa oficială cdep.ro ↗</a>';
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
    if(idx===sel) window.location.href=O[idx][4];   // a doua atingere: pagina noastră
    else arata(idx);
  },{passive:true});

  // ─── „Parlamentarul tău" ────────────────────────────────────────
  // Caută după localitate (10.217, din SIRUTA publicat de INS) sau după nume.
  // Tabelul se încarcă abia la prima tastare — 299 KB pe care nu-i plăteşte
  // nimeni care doar se uită la hemiciclu.
  var q=document.getElementById("plQ"), rez=document.getElementById("plRez"), LOC=null, CIRC=null;
  function curat(s){return s.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase()
                     .replace(/[-\\s]+/g," ").trim();}
  function delegatie(nrCirc){
    var d=[],sn=[];
    for(var i=0;i<O.length;i++){
      if(String(O[i][6])===String(nrCirc)) (O[i][2]==="D"?d:sn).push(i);
    }
    return {dep:d,sen:sn};
  }
  function card(i){
    var o=O[i];
    return '<a class="pl-om" href="'+o[4]+'"><i style="background:'+L[o[1]].culoare+'"></i>'
      +'<span><b>'+o[0]+'</b>'+L[o[1]].nume+' · '+(o[2]==="D"?"Deputat":"Senator")+'</span></a>';
  }
  function arataCirc(nr,eticheta){
    var g=delegatie(nr), tot=g.dep.length+g.sen.length;
    if(!tot){rez.hidden=true;return;}
    rez.innerHTML='<h3 class="pl-rez-cap">'+eticheta+'</h3>'
      +'<p class="pl-rez-sub">În România nu ai <b>un</b> parlamentar, ai o <b>delegație</b>: toți cei aleși '
      +'pe lista județului te reprezintă deopotrivă. Aici sunt <b>'+g.dep.length+' deputați și '
      +g.sen.length+' senatori</b>.</p>'
      +'<div class="pl-rez-grid">'+g.dep.concat(g.sen).map(card).join("")+'</div>';
    rez.hidden=false; rez.scrollIntoView({behavior:"smooth",block:"nearest"});
  }
  function cautaNume(t){
    var g=[];
    for(var i=0;i<O.length && g.length<12;i++) if(curat(O[i][0]).indexOf(t)>=0) g.push(i);
    if(!g.length) return false;
    rez.innerHTML='<h3 class="pl-rez-cap">'+g.length+' potriviri după nume</h3>'
      +'<div class="pl-rez-grid">'+g.map(card).join("")+'</div>';
    rez.hidden=false; return true;
  }
  function cauta(){
    var t=curat(q.value);
    if(t.length<2){rez.hidden=true;return;}
    if(!LOC){
      // Livrat ca .js, nu .json: .htaccess blochează deliberat fişierele .json,
      // ca să nu se servească sursele de build. Regula e bună — schimbăm doar
      // ambalajul, nu protecţia. Se încarcă o singură dată, la prima căutare.
      rez.hidden=false; rez.innerHTML='<p class="pl-rez-sub">Se încarcă lista localităților…</p>';
      var sc=document.createElement("script");
      sc.src="date/localitati.js";
      sc.onload=function(){ if(window.FB_LOC){LOC=window.FB_LOC.loc;CIRC=window.FB_LOC.circ;cauta();} };
      sc.onerror=function(){rez.innerHTML='<p class="pl-rez-sub">Nu am putut încărca lista localităților. '
        +'Caută după numele parlamentarului.</p>';};
      document.head.appendChild(sc);
      return;}
    var l=LOC[t];
    if(!l){ // potrivire pe început de nume, dacă nu e exactă
      for(var k in LOC){ if(k.indexOf(t)===0){l=LOC[k];break;} }
    }
    if(l){
      var jud=l.slice(1);
      if(jud.length===1){arataCirc(jud[0],l[0]+" ține de circumscripția "+CIRC[jud[0]]);return;}
      rez.innerHTML='<h3 class="pl-rez-cap">„'+l[0]+'" există în '+jud.length+' județe</h3>'
        +'<p class="pl-rez-sub">Alege-l pe al tău:</p><div class="pl-optiuni">'
        +jud.map(function(n){return '<button data-nr="'+n+'" data-e="'+l[0]+', '+CIRC[n]+'">'
          +CIRC[n]+'</button>';}).join("")+'</div>';
      rez.hidden=false; return;
    }
    if(!cautaNume(t)){
      rez.innerHTML='<p class="pl-rez-sub">Nu găsesc „'+q.value+'". Încearcă numele localității '
        +'(ex. <i>Zalău</i>) sau al parlamentarului.</p>'; rez.hidden=false;
    }
  }
  if(q){
    var timp; q.addEventListener("input",function(){clearTimeout(timp);timp=setTimeout(cauta,180);});
    rez.addEventListener("click",function(ev){
      var b=ev.target.closest("button[data-nr]"); if(b) arataCirc(b.dataset.nr,b.dataset.e);
    });
  }
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

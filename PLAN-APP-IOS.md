# Fără Baliverne — aplicația de iPhone. Plan de lucru

> Scris pe 13 septembrie 2026, la cererea fondatorului. Se ține la zi aici, ca
> WORKLOG-ul. Ce nu e scris aici nu s-a decis.

---

## 1. Ce este și ce NU este aplicația

**NU e site-ul împachetat.** Apple respinge sistematic aplicațiile care sunt doar
un site pus într-o fereastră (regula 4.2, „Minimum Functionality"), iar
aplicațiile de presă sunt exact categoria pe care o verifică cel mai atent. GABE
a trecut fiindcă e o rețea socială cu funcții proprii; un site de știri
împachetat nu trece.

**Este o aplicație de citit verificări, care face patru lucruri pe care
site-ul nu le poate face:**

1. **Citit fără internet.** Descarcă verificările zilei și le citești în metrou,
   în avion, la țară. Site-ul nu poate.
2. **Notificare când se schimbă ceva.** „Afirmația pe care ai urmărit-o are
   acum verdict." Sau ediția zilei, dacă vrei. Singurul canal pe care îl deținem
   noi, nu Facebook și nu Google.
3. **Căutare instant în toate cele 920 de verificări**, local, fără să aștepte
   serverul.
4. **Salvate și urmărite**, pe telefon, fără cont și fără parolă.

**Argumentul care ne scoate din zona de respingere:** articolele noastre sunt
structurate (`probat`, `contestat`, `opinie`, fiecare cu sursele lui), nu text
brut. O aplicație nativă le poate arăta **mai bine decât pagina web**: dovezile
într-o parte, contestările în alta, sursele ca butoane, verdictul ca element de
interfață. Asta e o funcție proprie, nu o împachetare.

---

## 2. Arhitectura

```
build_site.py  ──emite──►  api/index.json        (lista, ~920 de articole)
(deja există)              api/a/<slug>.json     (articolul întreg)
                           api/letopiset.json    (letopisețul)
                           api/stare.json        (când s-a generat, câte sunt)
                                   │
                                   ▼  fișiere statice pe Datahost, prin FTP
                           aplicația iOS (SwiftUI, nativă)
                                   │
                                   ▼  doar pentru notificări
                           serverul GABE (findgabe.app) — deja există
```

**De ce așa:**
- Nu costă nimic în plus: aceleași fișiere statice, același FTP, același deploy.
- Nu avem nevoie de server pentru conținut. Serverul GABE intră doar la
  notificări, iar el știe deja să trimită notificări (APNs direct, făcut pentru
  GABE).
- Aceleași fișiere servesc mai târziu și aplicația de Android, fără muncă în plus.

## 2.1 🔴 REGULA CARE NU SE NEGOCIAZĂ: nativ, de la prima linie

Fondatorul, 13 septembrie 2026, verbatim: *„Aplicația nativă iOS, nu povești cum
ai făcut cu primul GABE și nu am mai avut timp să facem cum trebuie noul GABE."*

**Ce înseamnă, concret:**
- **Swift + SwiftUI. Zero Capacitor, zero Cordova, zero `WKWebView`** ca schelet
  al aplicației. Nicio ecranizare nu e „site pus în fereastră".
- Lecția din GABE: prima versiune s-a făcut cu Capacitor ca să iasă repede,
  rescrierea nativă a rămas mereu „după lansare" și n-a venit niciodată. Aici nu
  se repetă: dacă ceva durează mai mult, se face mai târziu, dar se face nativ.
- Ce e permis: `SafariViewController` DOAR ca să deschidem **sursa externă**
  când omul apasă pe un link de sursă. Asta nu e aplicația, e browserul.
- Articolele se desenează din JSON, nativ. Avem `probat`, `contestat`, `opinie`
  cu surse separate, deci se pot arăta mai bine decât în pagina web.

**Tehnologia: SwiftUI nativ.** Trei motive: trece la aprobare, cititul fără
internet chiar funcționează, iar notificările funcționează cum trebuie. E
aceeași alegere pe care ai făcut-o la Android pentru GABE („s-o facem cum
trebuie").

## 2.2 Widgeturi și personalizare (cerute pe 13 septembrie)

**Widgeturi (WidgetKit, tot Swift, nativ):**
- **Mic:** ultimul verdict, cu eticheta colorată (Probat / Contestat /
  Contrazis) și titlul scurt.
- **Mediu:** trei verificări recente, cu eticheta fiecăreia.
- **Mare:** ziua în verificări — câte probate, câte contestate, câte contrazise,
  plus primele trei titluri.
- **Pe ecranul blocat:** un rând, „ultima verificare", ca să se vadă fără să
  deschizi telefonul.
- **Widget configurabil** (`AppIntent`): omul alege ce vede în el — toate,
  doar categoria lui, sau **doar cele contrazise**.
- Actualizare prin `TimelineProvider`, alimentat din același `api/index.json`.

**Personalizare în aplicație:**
- Ce categorii vede pe prima pagină și în ce ordine.
- Ce îl notifică: tot, doar contrazise, doar categoriile alese, sau nimic.
- Mărimea literei (respectă Dynamic Type din sistem, nu o inventăm noi).
- Temă: după sistem, deschisă sau întunecată.
- Citit fără internet: descărcare automată pe wi-fi, pornit sau oprit.

## 2.3 Ecrane mari și iPhone Duo

Cerut: să meargă și pe **iPhone Duo**. Nu cunosc dimensiunile exacte ale acestui
model (a apărut după ce s-a încheiat pregătirea mea și nu am putut verifica
acum), și nici nu contează pentru felul în care se construiește: **regula e să
NU codificăm niciodată o dimensiune de ecran**.

- Aranjare adaptivă prin `horizontalSizeClass` / `verticalSizeClass`, nu prin
  „dacă lățimea e 390".
- `NavigationSplitView` pentru ecrane late: lista într-o parte, articolul în
  cealaltă. Asta acoperă din start ecranul desfăcut, iPad și Mac.
- `ViewThatFits` și `containerRelativeFrame` pentru blocurile care trebuie să se
  rearanjeze singure.
- Aplicația trebuie să suporte redimensionarea în timpul rulării (pliere și
  depliere în timp ce omul citește), fără să piardă locul din articol.
- Verificat pe simulator la toate mărimile, înainte de trimitere.

Dacă modelul are particularități proprii, se citesc din documentația Apple la
Etapa 1 și se trec aici.

---

## 2.4 Cum arată: „un loc unde să-ți placă să citești" (cerut pe 13 septembrie)

Cererea fondatorului, verbatim: *„Vreau să arate modern, un loc unde să-ți placă
să citești știri."*

**Principii, nu decorațiuni:**
1. **Textul e produsul.** Ecranul de articol se proiectează primul, nu ultimul.
   Serif pentru corp (ca pe site, e identitatea noastră), rânduri de 60–70 de
   semne, spațiere generoasă, diacritice corecte. Respectă mărimea de literă
   aleasă de om în sistem (Dynamic Type), nu o impunem noi.
2. **Verdictul e semnătura vizuală.** Pastila colorată — verde probat, chihlimbar
   contestat, roșu contrazis — e elementul care organizează tot: în listă, în
   articol, în widget, în căutare. Se vede dintr-o privire unde bat probele.
3. **Dovezile ca interfață, nu ca text.** `probat` și `contestat` sunt două
   coloane vizuale distincte, iar sursele sunt butoane pe care apeși, nu linkuri
   albastre subliniate. Asta e ce nu poate face pagina web.
4. **Liniște.** Zero ferestre care sar, zero video care pornește singur, zero
   reclamă în ecranul de citit. Publicitatea, dacă apare vreodată, stă în listă,
   etichetată, niciodată între paragrafe.
5. **Întuneric adevărat.** Modul întunecat e proiectat separat, nu e albul
   inversat. Se citește noaptea fără să ardă ochii.
6. **Mișcare cu rost.** Tranziții scurte, trageri fluide. O singură licență
   poetică: la tragerea în jos pentru reîmprospătare, „apă, paie… adevăr".
7. **Fotografia respiră.** Imagine mare sus, colțuri rotunjite, creditul vizibil
   dedesubt — onestitatea se vede, nu se ascunde în subsol.

### Ecranul de pornire, așa cum l-a cerut fondatorul (13 septembrie)

*„Vreau să se vadă știrile, poza și titlul, iar unde poți să derulezi la dreapta
sunt știrile cu cele mai mari interacțiuni din ultimele 24 de ore."*

```
┌──────────────────────────────────────┐
│  Fără Baliverne        [caută] [eu]  │
│  ┌────────┐ ┌─────────┐ ┌──────────┐ │  file lipite sus
│  │ Toate  │ │ Pt. tine│ │ Contrazis│ │
│  └────────┘ └─────────┘ └──────────┘ │
│                                      │
│  CITITE ACUM · ultimele 24 de ore    │  ← carusel, se derulează la dreapta
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │     alimentat din contorul nostru
│  │ poză│ │ poză│ │ poză│ │ poză│ ... │     (câți oameni le-au deschis)
│  │titlu│ │titlu│ │titlu│ │titlu│     │
│  └─────┘ └─────┘ └─────┘ └─────┘     │
│                                      │
│  ────────────────────────────────    │
│  ┌──────────────────────────────┐    │  ← lista, una sub alta
│  │        poză mare             │    │     tragi cardul stânga/dreapta
│  │ ▓▓▓▓▓▓▓░░░  4 probate·3 cont.│    │     bara dovezilor
│  │ Titlul verificării           │    │
│  │ dek-ul, două rânduri         │    │
│  │ Politică · azi · Digi24      │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│           ...                        │
│ ─────────────────────────────────    │
│  Știri   Caută   Alerte   Eu         │  bară jos
└──────────────────────────────────────┘
```

**De unde vin „cele mai citite din ultimele 24 de ore":** din contorul nostru,
făcut pe 13 septembrie. Serverul GABE are punctul
`GET /api/stats/farabaliverne/top?ore=24&limita=10`, care întoarce slug-urile
celor mai deschise articole, cu câți oameni le-au deschis. Aplicația le leagă
de `api/index.json` și are poza și titlul. Fără cont, fără urmărirea nimănui:
se numără deschiderile, nu oamenii.

⚠️ **Cinstit:** azi site-ul are ~20 de cititori pe zi, deci „cele mai citite"
se calculează pe cifre mici și poate arăta ciudat la început. Regula în
aplicație: dacă în 24 de ore nu sunt cel puțin 5 articole cu cel puțin 3
cititori fiecare, caruselul arată „Cele mai noi" în loc de „Citite acum", fără
să spună nimănui că n-avem trafic. Se trece automat pe cifre reale când vin.

### Referința vizuală: Ground News (arătată de fondator pe 13 septembrie)

Ce facem cu ea: luăm **tiparele**, nu înfățișarea. Tiparele sunt oricum
standardul iOS (selector sus, carduri, bară de file jos), iar identitatea
noastră rămâne a noastră: serif pentru titluri, paleta petrol și alb, „Apă,
paie… Adevăr".

**Ce iau de la ei, cu echivalentul nostru:**

| La ei | La noi |
|---|---|
| „43 Sources • 3h ago" pus mare, ca măsură a știrii | **„4 probate · 3 contestate"** — numărul de dovezi e măsura noastră, și e mai bună decât a lor, fiindcă spune ce s-a verificat, nu doar câți au scris |
| Bara colorată L 25 % / C 50 % / R 25 % (orientarea politică a presei) | **Bara dovezilor:** cât din articol e probat, cât contestat, cât contrazis. Se vede dintr-o privire unde bat probele, fără să citești. NU copiem bara stânga-dreapta: noi nu clasificăm presa politic, asta e chiar decizia ta din 5 septembrie |
| „Blindspot" — ce nu acoperă o tabără | **„Cum a titrat fiecare"** — pe care îl avem deja pe site: aceeași știre, prin titlurile fiecărei publicații, fără etichete puse de noi. E cel mai apropiat lucru de ce vinde Ground News, și e deja scris |
| File sus: Top / For You / Blindspot | File sus: **Toate / Pentru tine / Contrazise** |
| „Daily Briefing — stories you may have missed", carusel | **„Ediția de azi"** și **„Ce ai ratat"**, carusel orizontal |
| Bară jos: News / Discover / Alerts / Profile | **Știri / Caută / Alerte / Eu** |
| Fotografie mare, colțuri rotunjite, rezumat scurt sub titlu | La fel, cu dek-ul nostru, care e deja scris pentru asta |

**Ce NU luăm:** bara de abonament peste conținut, clasificarea presei pe
stânga-dreapta, și insistența pe „câte surse" ca scop în sine. Noi numărăm
dovezi, nu surse.

🔴 **Cum se aleg culorile și așezarea: NU din descrieri, ci văzându-le.** Regula
lui, din 11 septembrie: deciziile vizuale se iau pe un ecran cu butoane de
comparat, nu din argumente scrise. La Etapa 1 fac două-trei variante de ecran de
articol și le pui una lângă alta pe telefon, prin TestFlight sau prin cablu.
Alegi tu, apoi se scrie în plan și nu se mai redeschide.

## 2.5 Swipe, „îmi place", partajare (cerute pe 13 septembrie)

Cererea: *„swipe de la stânga la dreapta ca la Tinder, dacă vrei să mai primești
știri în genul; cu posibilitatea de a da like, share în știre direct; și
eventual să posteze pe Facebook în contul tău știrea care ți-a plăcut; sau să
țină evidența câte like-uri."*

**A. Tragerea cu degetul — DA, și se face fără cont.**
- Dreapta = „mai vreau așa", stânga = „nu mă interesează".
- **Merge în două locuri** (precizarea fondatorului, 13 septembrie): pe cardul
  din listă, cât vezi doar titlul, ȘI în articolul deschis, trăgând de toată
  pagina. Același gest, aceeași învățare, ca omul să nu fie nevoit să se
  întoarcă în listă ca să spună ce a crezut.
- Cât tragi, apare sub deget semnul: verde cu „mai vreau așa" la dreapta, gri cu
  „nu mă interesează" la stânga. Se poate lăsa la jumătate, fără efect.
- Semnalul stă **doar pe telefonul tău**, în memoria aplicației. Din el se
  învață categoriile, sursele și subiectele care te interesează, iar lista se
  rearanjează. Fără server, fără cont, fără date personale plecate nicăieri.
- Se poate anula oricând dintr-un buton („uită ce ai învățat despre mine").
- Atenție la conflict: în articolul deschis, tragerea de la marginea din stânga
  e gestul iOS de întoarcere înapoi. Deci gestul nostru pornește din mijlocul
  ecranului, nu de pe margine, altfel îi stricăm omului navigarea.

**B. Partajarea din articol — DA, nativ.**
Butonul de partajare al iPhone-ului (`ShareLink` în SwiftUI): de acolo omul
alege singur Facebook, WhatsApp, Messenger, mesaj sau copiere. Trimitem titlul
scurt, linkul și cardul nostru de partajare. E o linie de cod și merge peste tot.

**C. 🔴 Postarea automată pe Facebook, în contul omului — NU SE POATE.**
Nu e o alegere de-a mea, e o limitare a Facebook: posibilitatea ca o aplicație
să publice în numele unui om pe profilul lui personal a fost desființată de Meta
în 2018 (permisiunea `publish_actions`). Rămâne doar pentru PAGINI, cu aprobare
și verificare de firmă. Exact în zidul ăsta ne-am lovit azi-dimineață, la
butoanele de partajare de pe site.
**Ce se poate, și e la o atingere distanță:** butonul de partajare deschide
Facebook cu articolul pregătit, iar omul apasă „Postează". Asta e tot ce
permite Facebook oricui, inclusiv ziarelor mari.

**D. Numărătoarea de „îmi place" — aici îți pun o obiecție, nu un refuz.**

Un contor public de „îmi place" pe o verificare transformă adevărul în vot. Dacă
un articol care infirmă o minciună strânge o mie de „nu-mi place" de la oameni
care cred minciuna, cititorul nou vede un scor, nu dovezile. E fix mecanismul
care face ca adevărul să pară o părere, adică opusul motivului pentru care
există site-ul (vezi principiul roșu din `CLAUDE.md`).

**Ce propun în loc, și îți dă tot ce vrei:**
1. **„Mi-a folosit / nu mi-a folosit"** în loc de „îmi place / nu-mi place".
   Se referă la calitatea verificării, nu la acordul cu realitatea. Un om poate
   spune „mi-a folosit" chiar dacă adevărul nu-i convine.
2. **Cifra o vedem noi, nu se afișează pe articol.** Intră în panoul de
   statistici, lângă contorul de vizite, și ne spune ce verificări ajută cu
   adevărat. Fără scor public, fără gamificare, fără brigadă de voturi.
3. **Semnalul personal rămâne al lui**, pe telefon, și hrănește recomandările.

Dacă totuși vrei contorul public, o fac — dar scriu aici, cu data, că ți-am
spus riscul. Deocamdată se construiește varianta de mai sus.

## 3. Etape

### Etapa 0 — API-ul din generator (NU are nevoie de Mac mini)
Scoatem `api/*.json` din `build_site.py`. Se poate face acum, e util oricum
(aplicația de Android, orice altceva), și nu schimbă nimic pe site.
**Rezultat:** `farabaliverne.ro/api/index.json` răspunde.

### Etapa 1 — Scheletul aplicației (după Mac mini, ~22 septembrie)
Proiect Xcode nou, identificator `ro.farabaliverne.app` (NU cel de la GABE),
sub același cont Apple Developer, deja plătit. Trei ecrane: lista, articolul,
căutarea. Citesc din API. Fără notificări, fără cont.
**Rezultat:** aplicația rulează pe telefonul tău, prin cablu.

### Etapa 2 — Ce o face să merite instalată
Citit fără internet (descarcă și ține local), salvate, urmărirea unei afirmații,
letopisețul ca linie de timp, partajare cu cardul nostru.
**Rezultat:** aplicația e utilă și fără semnal.

### Etapa 3 — Notificări
Serverul GABE capătă un punct nou: `/api/fb/push`. Când ediția publică ceva ce
te interesează, primești o notificare. Cu setare, ca omul să aleagă: toate,
doar contrazise, doar categoria lui.
**Rezultat:** canalul nostru propriu, independent de Facebook și de Google.

### Etapa 4 — TestFlight, apoi App Store
Întâi la tine și la câțiva oameni, prin TestFlight. Apoi trimis la aprobare, cu
textul de prezentare scris pe funcțiile de mai sus, nu pe „citește site-ul".
**Rezultat:** în App Store.

---

## 4. Costuri

| Ce | Cât |
|---|---|
| Cont Apple Developer | 0 lei în plus, e plătit pentru GABE |
| Găzduire API | 0 lei, aceleași fișiere statice |
| Notificări | 0 lei, serverul GABE există |
| Mac pentru compilare | Mac mini, comandat, sosește de la 22 septembrie |

---

## 5. Contrapondere cinstită, ca s-o ai pe masă

**Aplicația nu aduce cititori noi.** Nimeni nu instalează aplicația unui site pe
care nu-l citește. Cu 20 de vizitatori pe zi, instalările vor fi aproape zero la
început. O aplicație e o unealtă de PĂSTRARE a cititorilor, nu de aducere.

**De ce merită totuși pornită acum, și nu peste un an:** durează săptămâni, Mac
mini-ul vine peste nouă zile, iar notificările sunt **singurul canal pe care îl
deținem**. Facebook poate schimba algoritmul mâine, Google poate să nu ne
indexeze. Omul care are aplicația instalată rămâne al nostru. Pentru un site a
cărui idee întreagă e independența, asta contează.

**Ce NU rezolvă:** problema de audiență. Aia se rezolvă prin distribuție, iar
măsurat pe 13 septembrie, o postare potrivită într-un grup a adus 16 cititori în
câteva ore, față de 44 în 28 de zile din Google. Aplicația nu înlocuiește asta.

---

## 6. Stare

- [x] Plan scris (13 septembrie 2026)
- [ ] Etapa 0 — API-ul din generator
- [ ] Etapa 1 — schelet Xcode
- [ ] Etapa 2 — offline, salvate, letopiseț
- [ ] Etapa 3 — notificări
- [ ] Etapa 4 — TestFlight → App Store

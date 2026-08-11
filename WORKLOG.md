# WORKLOG — Fără Baliverne

> Jurnalul proiectului: ce facem, zi de zi, + evidența articolelor promovate pe prima pagină.
> Principiul roșu rămâne fundația: **NU decretăm „adevărat/fals" — arătăm dovezile cu surse, cititorul concluzionează.**
> (Vezi și `CLAUDE.md` pentru principiu + poziționare.)

---

## 🔵 11 august 2026 — Automatizarea nu mai pierde ediții; poze proprii, legale

**Ediția automată se pierdea, în tăcere.** Din ~09:00 UTC, o rulare din trei nu
publica nimic, dar GitHub raporta *success*. Cauza: ținta a urcat la 3-4 articole
+ fallback internațional, dar `--max-turns` a rămas 50; redactorul lovea plafonul
în timpul cercetării și murea **înainte** de PASUL 5 (commit + push). Eroarea era
înghițită de `|| echo "::warning::"`.
- buget 50 → **120 tururi**, timeout 30 → 40 min
- rularea **pică explicit** dacă redactorul moare fără să publice; „niciun subiect
  nou" rămâne warning (e un rezultat legitim)
- deploy-ul se declanșează doar când există commit nou

**Pozele: de la hotlink la fotografii proprii.** 60 din 64 de articole afișau
fotografiile altor publicații (Agerpres, Gândul, HotNews, G4Media, Euronews,
Al Jazeera) **de pe serverele lor**, cu `referrerpolicy="no-referrer"` pe
deasupra — adică ocolind chiar mecanismul prin care ei blochează hotlinking-ul.
Pentru un site de fact-checking, a fi atacabil pe drepturi de autor e fix
expunerea pe care nu și-o permite.
- **47 de articole** au acum fotografie de pe Wikimedia Commons, descărcată și
  găzduită la noi, medie 135 KB (1200px + compresie)
- atribuire completă CC: titlu, autor, sursă, licență cu link, mențiunea decupării
- 19 fără fotografie potrivită rămân pe hotlink, dar **fără `no-referrer`** —
  sursa vede acum traficul pe care i-l trimitem
- badge-ul de sursă scos de **pe** poză (era sursa știrii, nu a pozei)

**Trei capcane prinse la verificare, toate grave:**
1. Căutarea naivă după „Air China" întorcea, pe locul doi, fotografii de la
   **locul unui accident aviatic**. Filtru de context adăugat.
2. Căutarea după „David Popovici" a întors o poză intitulată „Bianca Costea,
   STEAUA TV" — **poza altei persoane**, care ar fi ajuns sub eticheta „Foto de
   arhivă — David Popovici". La portrete, numele trebuie acum să apară în titlul
   fișierului. *(Audit pe cele 18 portrete deja publicate: zero greșeli.)*
3. Derivarea căutării din cuvintele titlului producea numai gunoi, cu încredere:
   „Puterea de cumpărare" → căutare „Puterea" → **o locomotivă cu abur în zăpadă**,
   pe o știre despre inflație. Nivelul a fost scos complet. Mai bine cardul de
   brand decât o poză sigură pe ea și complet greșită.

**Butonul de share.** Panoul „Ține adevărul viu" apare și pe homepage, și pe
articole. Pe articol dă mai departe articolul (corect); pe homepage dă mai
departe site-ul — dar butonul scria doar „Postează", așa că puteai crede că
postezi știrea din listă. *(S-a și întâmplat: pe X a ajuns `index.html` în loc de
articolul Air China.)* Pe homepage scrie acum „Postează site-ul", cu îndemn spre
calea corectă. Fără butoane noi.

**Verificare automată** (`scripts/verify_images.py`) rulează după fiecare ediție,
nu pe un ceas. Oprește publicarea la hotlink într-un articol nou, legendă
incompletă, poză peste 300 KB sau reapariția lui `no-referrer`.

**De rezolvat:**
- Homepage-ul crește nelimitat — listează toate articolele; +23 KB doar pe 11 aug,
  ~66 KB/zi în ritmul actual, peste 2 MB într-o lună. De plafonat/paginat.
- Distribuție: 7+ ediții/zi care nu ajung nicăieri. Zero automatizare de social.
- Cadența (din oră-n-oră, publicare directă) contrazice `CLAUDE.md`, care spune
  „fondatorul aprobă înainte de publicare, cel puțin la început". Ori se
  actualizează regula, ori se repune omul în circuit.
- Cele 19 articole fără fotografie: de găsit altă sursă liberă sau card de brand
  mai bun decât gradientul cu emoticon.

---

## 🟢 8 august 2026 — Lansare + primul val mare de conținut

**Site LIVE:** `https://farabaliverne.ro` publicat (7 aug, prin cPanel Datahost → File Manager → `public_html`). HTTPS+SSL activ, redirect www/http→https, 404 propriu, `.htaccess`.

**Adăugat azi (val 1 — 6 articole noi, verificate, surse 200 live):**
- Politică: `georgescu-iccj-proces-fond`, `nicusor-dan-decrete-magistrati`
- Economie: `anaf-diaspora-confiscare` (demontare)
- Social: `sosoaca-clip-ai-penitenciar` (clip generat cu AI)
- Sport (secțiune NOUĂ): `kups-craiova-1-1-europa-league`, `popovici-europene-paris-record`

**Funcționalități noi:**
- **Secțiune Sport** în meniu (peste tot) + pe homepage.
- **Pagina „Politicieni"** — verificări grupate pe persoană (hub + jump-links). Framing: „ce s-a probat despre X", nu fan-page.
- **Cutia de implicare** (înlocuiește donația care nu mergea): **⚡ Gabe it** (share) + ♥ Îmi place + 🔔 Notificări. Buton „Gabe it" flotant pe articole + în header.
- **Pagina „Publicitate"** + slot în sidebar — primul partener: **normandmobilier.ro**.
- Slogan actualizat: „presa românească **și internațională**".
- Tag-uri `persoane` pe articolele vechi (pt pagina Politicieni). *(Horațiu Potra scos — nu e politician.)*

**În lucru (agent, val 2):** articol Sorin Grindeanu (salarizare) + seria de verificări pe declarațiile lui Călin Georgescu (în cadrul principiului: dovezi + „unde bat probele", nu verdict-oracol).

**De rezolvat / decis:**
- Notificări push reale + like-count persistent → au nevoie de serviciu (OneSignal) sau mic backend. Momentan: share complet + like local.
- Autonomie „de oriunde": cont FTP + agent cloud programat (de setat).
- Google Search Console (trimis sitemap) — după.
- Actualizare articol Popovici după finalele de la Paris (12 & 14 aug).
- Secretizare cod: minificare + repo privat + blocare surse pe server.

---

## Articole promovate pe prima pagină (evidență)

| Slug | Categorie | Persoane | Unde bat probele |
|---|---|---|---|
| legea-integritatii-vot-final | Politică | Dominic Fritz | Probat, cu rezerve |
| georgescu-iccj-proces-fond | Politică | Călin Georgescu | Probat |
| nicusor-dan-decrete-magistrati | Politică | Nicușor Dan | Probat (rezerve cifră) |
| bolojan-deepfake-razboi-septembrie | Politică | Ilie Bolojan | Contrazis |
| fantana-zece-ani-inchisoare | Politică | — | Contrazis |
| sosoaca-tribunal-ue-imunitate | Politică | Diana Șoșoacă | Probat |
| anaf-diaspora-confiscare | Economie | — | Contrazis |
| moody-rating-baa3-romania | Economie | — | Probat |
| inflatie-10-9-putere-cumparare | Economie | — | Probat |
| moldova-delegatie-talibani-sandu | Extern | Maia Sandu | Probat |
| trump-ordine-cetatenie-nastere | Extern | Donald Trump | Probat |
| cod-rosu-canicula-vest | Social | — | Probat |
| sosoaca-clip-ai-penitenciar | Social | Diana Șoșoacă, Ilie Bolojan, Nicușor Dan | Probat (conținut AI) |
| kups-craiova-1-1-europa-league | Sport | — | Probat |
| popovici-europene-paris-record | Sport | — | Context probat, rezultat în viitor |

*(Se actualizează la fiecare articol nou promovat.)*

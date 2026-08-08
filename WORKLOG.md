# WORKLOG — Fără Baliverne

> Jurnalul proiectului: ce facem, zi de zi, + evidența articolelor promovate pe prima pagină.
> Principiul roșu rămâne fundația: **NU decretăm „adevărat/fals" — arătăm dovezile cu surse, cititorul concluzionează.**
> (Vezi și `CLAUDE.md` pentru principiu + poziționare.)

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

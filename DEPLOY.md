# Deploy — Fără Baliverne

Site **static** (HTML + CSS/JS inline, zero backend, zero bază de date). Se urcă orice fișiere,
oriunde. Pachetul gata de urcat = `dist/` (sau arhiva `farabaliverne-deploy.zip`).

## Ce e în pachet (`dist/`)
- `index.html` — prima pagină
- `a/` — 10 articole (8 verificări + 2 demontări)
- `metodologie / cine-suntem / corectari / contact / termeni / confidentialitate .html`
- `404.html` — pagină de eroare proprie
- `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png`, `og-cover.png` (imaginea de share)
- `robots.txt`, `sitemap.xml`, `site.webmanifest`
- `.htaccess` — HTTPS + www→non-www + 404 + compresie + cache (pentru hosting Apache, ca Datahost)

**NU** se urcă: `data/` (surse de build), `preview/` (mockup-uri), `CLAUDE.md`, `DEPLOY.md`, `.git/`.
(Sunt deja excluse din `dist/`.)

## Înainte de deploy (lucruri care depind de tine)
1. **Domeniul `farabaliverne.ro`** — cumpărat + activ la Datahost, cu DNS care pointează la hosting.
2. **Cont de hosting** (cPanel sau FTP) — user + parolă. (Eu NU manipulez parole — le pui tu.)
3. **Aprobarea conținutului** — citește articolele cu persoane numite (Șoșoacă, Bolojan, Târziu)
   și confirmă că îți asumi publicarea. Principiul: fondatorul aprobă înainte de publicare.

## Varianta A — cPanel File Manager (cel mai simplu)
1. Intră în cPanel Datahost → **File Manager** → folderul `public_html/`.
2. Șterge fișierele vechi din `public_html/` (dacă e ceva de test).
3. **Upload** `farabaliverne-deploy.zip` în `public_html/`.
4. Click dreapta pe zip → **Extract** (extrage direct în `public_html/`).
5. Șterge arhiva după extragere.
6. Verifică: `public_html/index.html` și `public_html/.htaccess` există.
   (În File Manager: Settings → bifează **Show Hidden Files** ca să vezi `.htaccess`.)

## Varianta B — FTP (FileZilla)
1. Conectează-te cu host `ftp.farabaliverne.ro`, user + parola de hosting.
2. Intră în `public_html/`.
3. Urcă **tot conținutul din `dist/`** (nu folderul `dist` în sine — conținutul lui).
4. Asigură-te că se urcă și `.htaccess` (FileZilla: Server → Force showing hidden files).

## După deploy — verificări
- [ ] `https://farabaliverne.ro` se încarcă cu lacăt (HTTPS).
- [ ] `http://` și `www.` redirecționează spre `https://farabaliverne.ro`.
- [ ] Un articol se deschide, pozele se văd, „Citește știrea originală" duce la sursă.
- [ ] O adresă greșită (ex. `/xyz`) arată pagina 404 proprie.
- [ ] `https://farabaliverne.ro/sitemap.xml` se deschide.
- [ ] Google **Search Console**: adaugă proprietatea `farabaliverne.ro`, trimite `sitemap.xml`.

## Cum se reconstruiește pachetul (după ce mai adaugi articole)
Din `~/Projects/farabaliverne/`:
```
rm -rf dist && mkdir dist
rsync -a --exclude='.git' --exclude='dist' --exclude='preview' --exclude='data' \
  --exclude='CLAUDE.md' --exclude='DEPLOY.md' --exclude='og-cover.svg' --exclude='.gitignore' \
  ./ dist/
( cd dist && zip -rq ../farabaliverne-deploy.zip . -x '.DS_Store' )
```

## De reținut
- **Pozele articolelor** sunt „hotlink" de la sursă (Digi24, HotNews, Agerpres etc.), cu atribuire
  + link la original (citare). Dacă o sursă cere scoaterea unei poze → o scoți; e un `<img>` cu
  `onerror` care revine automat la fundal-gradient, deci nimic nu se rupe.
- Site fiind static, e imun la majoritatea atacurilor (n-are login, n-are DB).

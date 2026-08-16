# Redactorul local — „Fără Baliverne" pe Mac

Rulează pe calculatorul tău, prin Ollama. Nu costă nimic, nu consumă minute de
GitHub Actions și nu trimite nimic în afară.

## De ce există

Ediția automată de pe GitHub consumă ~16,5 minute de rulare, de 19 ori pe zi —
în jur de **10.300 de minute pe lună**, la o cotă de 2.000 pe repo privat. Mutând
redactarea aici, pe GitHub rămâne doar deploy-ul (~800 de minute), sub cotă.

## Ce face și ce NU face

**Face:** scrie articolul în vocea casei, îl structurează, formulează titlul,
dek-ul și verdictul, separă probat / contestat / opinie, atașează sursele care
i s-au dat.

**Nu face:** nu caută pe internet, nu decide dacă o sursă e credibilă, nu
verifică adversarial, nu publică. Un model de 12B pe Mac e bun la **formă**, nu
la **cercetare**. Cercetarea rămâne la modelul din cloud sau la tine.

Asta nu e o limitare temporară de reglat mai târziu — e diferența reală dintre
un model local și unul care poate căuta și cântări surse. Cine spune altceva îți
vinde ceva.

## Pornire

```bash
ollama create redactor -f local/redactor.Modelfile   # o singură dată
python3 scripts/corpus_local.py                      # reface materialul din articole
```

## Bucla de lucru

```bash
# 1. scrii un brief: subiectul pe primul rând, apoi materialul și sursele
python3 local/scrie.py --din-fisier brief.txt

# 2. te uiți la ce a ieșit
open local/propuneri/<slug>.json

# 3. îți place → îl duci mai departe. Nu-ți place → retușezi SYSTEM-ul din
#    redactor.Modelfile, rulezi `ollama create redactor -f ...` din nou, și reiei.
```

Propunerile stau în `local/propuneri/` și **nu ating site-ul**. Nimic nu se
publică de aici.

## Ce să urmărești când citești o propunere

1. **Are surse la fiecare afirmație?** Zero surse = nu se publică, fără discuție.
2. **A inventat vreun link sau vreo cifră?** Cel mai grav lucru posibil. La proba
   din 16 august a trecut testul: a scris „lipsă" unde nu avea linkul și a spus
   în `aiNote` ce n-a putut verifica.
3. **A zis undeva „a mințit"?** Nu are voie. Trebuie să explice DE CE nu se
   susține, cu mecanismul.
4. **A pus ștampilă pe o credință?** Misticismul nu se notează, se arată.
5. **Diacriticele.** Încă mai scapă „dobanzii" în loc de „dobânzii" — de întărit
   în prompt.

## Reglaje

- Modelul: `MODEL_REDACTOR=alt-model python3 local/scrie.py ...`
- Câte exemple din corpus intră în context: `--exemple 4` (implicit 2). Mai multe
  exemple = tipar mai bun, dar context mai plin și rulare mai lentă.
- Temperatura e 0,3 în Modelfile. Aici nu vrem creativitate, vrem consecvență.

## Materialul

`corpus.jsonl` — 281 de articole publicate, cu 1.069 de afirmații probate, 468
contestate și 1.875 de surse. Fiecare linie: ce a avut la intrare (subiect +
surse) și ce a produs (articolul). E munca ta de două luni, în forma pe care un
model o poate învăța.

`stil.md` — extras de voce: titluri, dek-uri și formulări reale. Modelele prind
tonul mai bine din exemple dese decât dintr-o descriere a tonului.

Ambele se regenerează cu `python3 scripts/corpus_local.py` — deci cresc singure
pe măsură ce publici.

## Ce urmează, dacă merită

Fine-tuning cu LoRA pe `corpus.jsonl`. **Dar nu acum:** cu 281 de exemple în
prompt și un system prompt bun, iei vreo 80% din rezultat gratis. Fine-tuning-ul
are sens abia dacă, după câteva runde de retușat promptul, tot rămâne o diferență
de calitate — și oricum cere mai multă memorie decât are un Air.

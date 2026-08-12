"""
Veghea: verifică din afară dacă site-ul chiar publică, și spune UNDE s-a rupt.

De ce din afară: pe 12 august, git-ul era la zi, iar farabaliverne.ro rămăsese
în urmă 18 ore. Din interiorul GitHub-ului cele două stări arată identic. De-aia
verificarea pornește de la `stare.txt`, pulsul pe care îl scrie
`build_site.py` și care ajunge pe server DOAR dacă deploy-ul a reușit.

Trei stări de alarmă, fiecare cu altă cauză și alt lucru de făcut:

  🔴 SITE CĂZUT        farabaliverne.ro nu răspunde       → gazda (Datahost)
  🟠 NEPUBLICAT        git are articole, site-ul nu le are → deploy.yml
  🟡 TĂCERE            nici git n-a mai primit nimic       → edition.yml / redactorul

Rulare:
    python3 scripts/veghe.py            # cod 0 = e bine, 1 = alarmă
    python3 scripts/veghe.py --json     # pentru workflow

Ieșirea normală e o singură linie. Alarma explică în română ce s-a rupt.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE = "https://farabaliverne.ro"
# `.txt`, nu `.json`: .htaccess refuză toate fișierele .json.
PULS = "stare.txt"
REPO = "ionutopris-prog/farabaliverne"

# Cât poate rămâne site-ul în urma git-ului. Un deploy durează ~3 minute, deci
# orice peste o oră și jumătate înseamnă că lanțul e rupt, nu lent.
PRAG_DEPLOY_MIN = 90

# Cât poate trece fără NICIUN articol nou. Edițiile merg din oră-n-oră între
# 04 și 20 UTC, dar noaptea sunt pauze programate de 3 ore (20→22→01→04), iar
# o ediție care nu găsește subiecte noi e un rezultat legitim, nu o defecțiune.
# 7 ore acoperă pauza cea mai lungă plus câteva ediții goale la rând.
PRAG_TACERE_ORE = 7

ACUM = datetime.now(timezone.utc)


def _cere(url, token=None, timeout=20):
    cerere = urllib.request.Request(url, headers={
        "User-Agent": "farabaliverne-veghe",
        "Cache-Control": "no-cache",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(cerere, timeout=timeout) as r:
        return r.read().decode("utf-8")


def _ceas(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _de_cat(delta):
    ore, rest = divmod(int(delta.total_seconds()), 3600)
    minute = rest // 60
    if ore >= 24:
        return f"{ore // 24} zile și {ore % 24} ore"
    return f"{ore} ore și {minute} minute" if ore else f"{minute} minute"


def stare_site():
    """
    Pulsul de pe server.

    Întoarce (puls, site_raspunde). Lipsa pulsului NU înseamnă site căzut:
    poate fi doar o versiune publicată înainte ca `stare.txt` să existe. Cele
    două cazuri cer lucruri complet diferite, deci nu le amestecăm.
    """
    try:
        return json.loads(_cere(f"{SITE}/{PULS}")), True
    except Exception:
        pass
    try:
        _cere(f"{SITE}/", timeout=15)
        return None, True
    except Exception:
        return None, False


def ultim_commit(token):
    """Când a primit git ultimul articol. None dacă nu putem întreba."""
    try:
        date = json.loads(_cere(
            f"https://api.github.com/repos/{REPO}/commits/main", token))
        return _ceas(date["commit"]["committer"]["date"].replace("+00:00", "Z"))
    except Exception:
        return None


def verifica(token):
    # Probă cerută manual. Există ca să putem vedea măcar o dată alarma
    # mergând pe tot lanțul — problemă deschisă, mail, apoi închisă singură.
    # O alertă pe care n-ai văzut-o niciodată pornind nu e o alertă.
    # Nu se poate declanșa de la sine: cere pornirea manuală a workflow-ului.
    if os.environ.get("VEGHE_PROBA"):
        return ("PROBĂ", "Probă cerută manual — nu e nimic stricat. "
                         "Dacă vezi mailul ăsta, veghea funcționează. "
                         "Se închide singură la următoarea verificare.")

    stare, raspunde = stare_site()
    commit = ultim_commit(token)

    if not raspunde:
        return ("SITE CĂZUT",
                f"{SITE} nu răspunde. Nu e o problemă de automatizare — "
                f"verifică gazda (Datahost) și domeniul.")

    if stare is None:
        return ("FĂRĂ PULS",
                f"Site-ul răspunde, dar n-are `stare.txt`. Înseamnă că ce e "
                f"publicat acum a fost construit înainte să existe pulsul — "
                f"deci deploy-ul n-a mai ajuns de atunci. Declanșează "
                f"`deploy.yml` și veghea se liniștește singură.")

    construit = _ceas(stare["construit"])
    vechime_site = ACUM - construit

    if commit and commit > construit:
        ramas = commit - construit
        if ramas.total_seconds() > PRAG_DEPLOY_MIN * 60:
            return ("NEPUBLICAT",
                    f"Articolele sunt scrise, dar nu ajung pe site. Ultimul "
                    f"commit e cu {_de_cat(ramas)} mai nou decât ce e publicat "
                    f"pe farabaliverne.ro (site: {stare['articole']} articole, "
                    f"construit acum {_de_cat(vechime_site)}).\n\n"
                    f"Se rupe între `edition.yml` și `deploy.yml`: fie un pas "
                    f"al ediției pică înainte să declanșeze deploy-ul, fie "
                    f"deploy-ul însuși dă greș. Verifică ultimele rulări.")

    referinta = commit or construit
    tacere = ACUM - referinta
    if tacere.total_seconds() > PRAG_TACERE_ORE * 3600:
        return ("TĂCERE",
                f"Nu s-a mai publicat nimic de {_de_cat(tacere)}. Site-ul "
                f"merge și e la zi cu ce există, dar redactorul nu mai adaugă "
                f"articole.\n\n"
                f"Cauze de verificat, în ordine: a expirat tokenul Claude, "
                f"s-a atins cota abonamentului, sau redactorul lovește "
                f"plafonul de tururi. Toate trei s-au mai întâmplat.")

    return (None,
            f"e bine · site construit acum {_de_cat(vechime_site)} · "
            f"{stare['articole']} articole · ultimul: {stare.get('ultimul', '?')}")


def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    alarma, mesaj = verifica(token)

    if "--json" in sys.argv:
        print(json.dumps({"alarma": alarma or "", "mesaj": mesaj},
                         ensure_ascii=False))
    else:
        print(f"{alarma}: {mesaj}" if alarma else mesaj)

    sys.exit(1 if alarma else 0)


if __name__ == "__main__":
    main()

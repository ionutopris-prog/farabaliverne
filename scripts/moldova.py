#!/usr/bin/env python3
"""
Recunoaște articolele despre **Republica Moldova** — un singur loc, ca să nu
se împrăștie regula prin cod.

🔴 Capcana pe care o ocolește: „Moldova" înseamnă și regiunea din România
(Iași, Bacău, Suceava). Un articol despre drumurile din Vaslui NU e Moldova
de peste Prut. De-aia nu căutăm niciodată cuvântul singur — cerem semne care
nu pot apărea decât dincolo de Prut: Chișinău, Transnistria, Maia Sandu, leu
moldovenesc, „Republica Moldova" scris întreg.

Sursa de adevăr rămâne câmpul `tara` din JSON, pus de redactor. Ghicitul de
mai jos e doar plasa pentru articolele scrise înainte să existe câmpul.
"""
import re
import unicodedata


def _fara_diacritice(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


# semne care nu pot fi despre Moldova românească
SEMNE = [
    r"republica moldova", r"\br\.? moldova\b", r"chisinau", r"basarabia",
    r"transnistria", r"tiraspol", r"gagauzia", r"comrat", r"\bbalti\b",
    r"maia sandu", r"igor dodon", r"dorin recean", r"ion ceban", r"vlad plahotniuc",
    r"ilan shor", r"\bpas\b(?=.{0,40}(chisinau|moldov))",
    r"leu moldovenesc", r"lei moldovenesti", r"moldovagaz", r"energocom",
    r"promo-?lex", r"ziarul de garda", r"newsmaker", r"\btv8\b",
    r"parlamentul republicii moldova", r"guvernul republicii moldova",
    r"presedinta moldovei", r"presedintele moldovei",
]
_RX = [re.compile(s) for s in SEMNE]


def este_moldova(d: dict) -> bool:
    """True dacă articolul e despre Republica Moldova."""
    if (d.get("tara") or "").strip().lower() in ("moldova", "republica moldova", "md"):
        return True
    if (d.get("tara") or "").strip():
        return False                      # redactorul a spus explicit altceva
    # DOAR titlu + dek + sursă. Nu căutăm în corpul articolului: dacă hoții de
    # tablouri din Italia erau cetățeni moldoveni, aia nu face o știre despre
    # Moldova. Subiectul se vede în titlu, nu într-o propoziție de la mijloc.
    text = " ".join([d.get("title", ""), d.get("dek", ""),
                     d.get("source", ""), d.get("url", "")])
    t = _fara_diacritice(text)
    return any(r.search(t) for r in _RX)


def de_ce(d: dict) -> str:
    """Ce anume l-a prins — util când verifici lista cu ochii."""
    t = _fara_diacritice(" ".join([d.get("title", ""), d.get("dek", ""), d.get("url", "")]))
    for r in _RX:
        m = r.search(t)
        if m:
            return m.group(0)
    return "câmpul tara"

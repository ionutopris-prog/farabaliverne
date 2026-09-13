"""
api.py — scoate din generator fișierele JSON din care citește aplicația de
telefon. Etapa 0 din `PLAN-APP-IOS.md`.

De ce JSON și nu pagina web: aplicația e NATIVĂ (regula fondatorului, 13
septembrie 2026 — „nu povești cum ai făcut cu primul GABE"), deci desenează
singură articolul. Ca să poată face asta, are nevoie de dovezi structurate
(`probat`, `contestat`, `opinie`, fiecare cu sursele lui), nu de HTML.

Ce scrie, toate fișiere statice, urcate pe același FTP, cost zero:

    api/stare.json        cand s-a generat, cate articole, versiunea formatului
    api/index.json        lista intreaga (titlu, verdict, poza, dek) — pentru
                          lista, cautare locala si widgeturi
    api/a/<slug>.json     articolul intreg, cu dovezi si surse
    api/letopiset.json    letopisetul, pentru linia de timp

Formatul are `versiune`. Daca se schimba ceva incompatibil, creste numarul si
aplicatia veche stie ca trebuie actualizata.
"""
import json
import os
import re
from datetime import datetime, timezone

BAZA = "https://farabaliverne.ro"
VERSIUNE = 1


def _absolut(cale):
    """`../img/articole/x.jpg` sau `img/articole/x.jpg` → URL întreg."""
    if not cale:
        return None
    cale = cale.lstrip("./")
    if cale.startswith("http"):
        return cale
    return BAZA + "/" + cale


def _poza(d):
    """Din blocul `poza` (care e HTML, pentru site) scoatem ce-i trebuie
    aplicației: adresa imaginii, textul alternativ și creditul, ca text simplu."""
    p = d.get("poza") or {}
    if not p:
        return None
    img = _absolut(p.get("fisier"))
    if not img:
        m = re.search(r'src="([^"]+)"', p.get("img_html", "") or "")
        img = _absolut(m.group(1)) if m else None
    if not img:
        return None
    fig = p.get("figcaption_html", "") or ""
    credit = re.sub(r"<[^>]+>", " ", fig)
    credit = re.sub(r"\s+", " ", credit).strip()
    alt = ""
    m = re.search(r'alt="([^"]*)"', p.get("img_html", "") or "")
    if m:
        alt = m.group(1)
    return {"imagine": img, "alt": alt, "credit": credit,
            "licenta": p.get("licenta", ""), "autor": p.get("autor", "")}


def _dovezi(lista):
    """probat / contestat → listă curată de {text, surse:[{nume,url}]}."""
    out = []
    for x in lista or []:
        if not isinstance(x, dict):
            continue
        out.append({
            "text": x.get("text", ""),
            "surse": [{"nume": s.get("name", ""), "url": s.get("url", "")}
                      for s in (x.get("sources") or []) if isinstance(s, dict)],
        })
    return out


def _rezumat(d, verdict_scurt, mom, moment_iso):
    """Intrarea din `index.json`: tot ce trebuie pentru listă, căutare și widget,
    fără corpul articolului."""
    return {
        "slug": d["slug"],
        "titlu": d.get("title", ""),
        "titluScurt": d.get("seoTitle") or "",
        "categorie": d.get("category", ""),
        "tara": d.get("tara", ""),
        "data": (d.get("date") or "")[:10],
        "publicat": moment_iso(d, mom),
        "sursa": d.get("source", ""),
        "dek": d.get("dek", ""),
        "verdict": verdict_scurt(d.get("mainVerdict")) or "",
        "verdictLung": d.get("mainVerdict", ""),
        "nrProbat": len(d.get("probat") or []),
        "nrContestat": len(d.get("contestat") or []),
        "nrOpinie": len(d.get("opinie") or []),
        "poza": _poza(d),
        "web": f"{BAZA}/a/{d['slug']}.html",
    }


def _intreg(d, rez):
    """Articolul complet: rezumatul + dovezile + nota + traducerea."""
    a = dict(rez)
    a.update({
        "probat": _dovezi(d.get("probat")),
        "contestat": _dovezi(d.get("contestat")),
        "opinie": [{"text": x.get("text", "")} for x in (d.get("opinie") or []) if isinstance(x, dict)],
        "notaAI": d.get("aiNote", ""),
        "persoane": d.get("persoane") or [],
        "sursaOriginala": d.get("url", ""),
    })
    t = d.get("traducere")
    if isinstance(t, dict):
        a["traducere"] = {
            "titlu": t.get("titlu", ""),
            "publicatie": t.get("publicatie", ""),
            "autor": t.get("autor", ""),
            "data": t.get("data", ""),
            "url": t.get("url", ""),
            "notaSus": t.get("nota_sus", ""),
            "notaJos": t.get("nota_jos", ""),
            "paragrafe": t.get("paragrafe") or [],
        }
    return a


def scrie(arts, root, verdict_scurt, mom, moment_iso, letopiset=None):
    """Scrie tot ce are nevoie aplicația. Întoarce câte fișiere a scris."""
    api = os.path.join(root, "api")
    os.makedirs(os.path.join(api, "a"), exist_ok=True)

    lista, scrise = [], 0
    for slug in sorted(arts):
        d = arts[slug]
        if not os.path.exists(os.path.join(root, "a", slug + ".html")):
            continue  # nepublicat încă: nu-l dăm aplicației
        rez = _rezumat(d, verdict_scurt, mom, moment_iso)
        lista.append(rez)
        cale = os.path.join(api, "a", slug + ".json")
        nou = json.dumps(_intreg(d, rez), ensure_ascii=False, separators=(",", ":"))
        vechi = None
        if os.path.exists(cale):
            try:
                vechi = open(cale, encoding="utf-8").read()
            except OSError:
                vechi = None
        if vechi != nou:  # scriem doar ce s-a schimbat, ca FTP-ul să nu urce tot
            open(cale, "w", encoding="utf-8").write(nou)
            scrise += 1

    lista.sort(key=lambda x: (x["publicat"] or x["data"], x["slug"]), reverse=True)
    _pune(os.path.join(api, "index.json"),
          {"versiune": VERSIUNE, "total": len(lista), "articole": lista})

    if letopiset:
        _pune(os.path.join(api, "letopiset.json"),
              {"versiune": VERSIUNE, "zile": letopiset})

    # numărătoarea pe verdicte, ca widgetul „ziua în verificări" să n-o calculeze el
    pe_verdict = {}
    for x in lista:
        if x["verdict"]:
            pe_verdict[x["verdict"]] = pe_verdict.get(x["verdict"], 0) + 1
    _pune(os.path.join(api, "stare.json"), {
        "versiune": VERSIUNE,
        "generat": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(lista),
        "peVerdict": pe_verdict,
        "peCategorie": _numara(lista, "categorie"),
        "site": BAZA,
    })
    return scrise, len(lista)


def _numara(lista, camp):
    out = {}
    for x in lista:
        k = x.get(camp) or ""
        if k:
            out[k] = out.get(k, 0) + 1
    return out


def _pune(cale, obiect):
    nou = json.dumps(obiect, ensure_ascii=False, separators=(",", ":"))
    try:
        if open(cale, encoding="utf-8").read() == nou:
            return
    except OSError:
        pass
    open(cale, "w", encoding="utf-8").write(nou)

"""
Transformă articolele publicate în material de învățare pentru modelul local.

De ce merită: cele 281 de articole nu sunt doar text, sunt exemple ETICHETATE —
fiecare afirmație e deja clasificată (probat / contestat / opinie) și are sursele
atașate. Asta e exact forma pe care o vrea un model ca să prindă tiparul, și
puțini o au: e munca ta de două luni, în vocea ta.

Scrie două fișiere:
  local/corpus.jsonl   — un exemplu pe linie: intrare (subiect + surse) → ieșire
                         (articolul, în structura casei). Pentru few-shot sau,
                         mai târziu, pentru fine-tuning.
  local/stil.md        — extras de voce: titluri, dek-uri și formulări reale,
                         ca modelul să aibă tonul sub ochi, nu doar reguli.

NU conține: chei, adrese, nimic din CLAUDE.md sau WORKLOG. Doar ce e deja public
pe site.

Rulare:  python3 scripts/corpus_local.py
"""

import json
import os
import glob
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IES = os.path.join(ROOT, "local")


def articole():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        if d.get("slug") and d.get("probat"):
            out.append(d)
    return out


def surse_din(d):
    """Sursele articolului — intrarea pe care o va avea și modelul în producție."""
    s = []
    for k in ("probat", "contestat"):
        for el in d.get(k) or []:
            for src in el.get("sources") or []:
                if src.get("name") and src["name"] not in [x["name"] for x in s]:
                    s.append({"name": src["name"], "url": src.get("url", "")})
    return s[:8]


def exemplu(d):
    """Un exemplu = ce ARE modelul la intrare, și ce trebuie să producă."""
    intrare = {
        "subiect": d["title"],
        "categorie": d["category"],
        "sursa_principala": d.get("source", ""),
        "surse_disponibile": surse_din(d),
    }
    iesire = {
        "title": d["title"],
        "dek": d.get("dek", ""),
        "mainVerdict": d.get("mainVerdict", ""),
        "probat": [{"text": p["text"], "sources": p.get("sources", [])}
                   for p in d.get("probat") or []],
        "contestat": [{"text": p["text"], "sources": p.get("sources", [])}
                      for p in d.get("contestat") or []],
        "opinie": d.get("opinie") or [],
        "math": d.get("math") or {},
        "aiNote": d.get("aiNote", ""),
    }
    return {"intrare": intrare, "iesire": iesire}


def main():
    os.makedirs(IES, exist_ok=True)
    arts = articole()

    cale = os.path.join(IES, "corpus.jsonl")
    with open(cale, "w", encoding="utf-8") as fh:
        for d in arts:
            fh.write(json.dumps(exemplu(d), ensure_ascii=False) + "\n")

    # Extras de stil: modelul învață tonul mai bine din exemple scurte și dese
    # decât dintr-o descriere a tonului.
    random.seed(7)
    esantion = random.sample(arts, min(40, len(arts)))
    st = ["# Vocea „Fără Baliverne” — exemple reale\n",
          "> Extras automat din articolele publicate. Nu edita — se regenerează.\n"]
    st.append("\n## Titluri\n")
    for d in esantion:
        st.append(f"- {d['title']}\n")
    st.append("\n## Dek-uri (primele 2 propoziții)\n")
    for d in esantion[:20]:
        st.append(f"- {d.get('dek','')[:260]}\n")
    st.append("\n## Formulări de verdict folosite\n")
    for v in sorted({d.get("mainVerdict", "") for d in arts if d.get("mainVerdict")}):
        st.append(f"- {v}\n")
    st.append("\n## Cum arată o afirmație probată\n")
    for d in esantion[:8]:
        p = (d.get("probat") or [{}])[0]
        if p.get("text"):
            st.append(f"- {p['text'][:300]}\n")
    st.append("\n## Cum arată o rezervă (contestat)\n")
    for d in arts:
        if d.get("contestat"):
            st.append(f"- {d['contestat'][0]['text'][:300]}\n")
        if len(st) > 100:
            break
    open(os.path.join(IES, "stil.md"), "w", encoding="utf-8").write("".join(st))

    nc = sum(len(a.get("contestat") or []) for a in arts)
    np = sum(len(a.get("probat") or []) for a in arts)
    ns = sum(len(surse_din(a)) for a in arts)
    print(f"articole folosite: {len(arts)}")
    print(f"  afirmații probate: {np} · contestate: {nc} · surse: {ns}")
    print(f"scris {cale} ({os.path.getsize(cale)//1024} KB)")
    print(f"scris {os.path.join(IES,'stil.md')}")


if __name__ == "__main__":
    main()

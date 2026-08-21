#!/usr/bin/env python3
"""Ce a parcat poarta de siguranță, adunat într-o singură problemă pe GitHub.

Poarta oprea corect articolele sensibile și le trimitea pe ramuri `pending/`,
dar nu anunța pe nimeni. Între 11 și 21 august 2026 s-au adunat acolo 67 de
articole nepublicate, dintre care 49 de politică internă — adică exact
subiectele care lipseau de pe site. Scriptul ăsta face ca tăcerea aia să nu
mai fie posibilă: o problemă, actualizată zilnic, cu tot ce așteaptă.
"""
import json, os, subprocess, sys

TITLU = "📝 Articole care așteaptă aprobarea ta"

def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k).stdout.strip()

def main():
    sh("git", "fetch", "-q", "origin", "+refs/heads/pending/*:refs/remotes/origin/pending/*")
    branches = sh("git", "for-each-ref", "--format=%(refname:short)",
                  "refs/remotes/origin/pending").split()
    asteapta = []
    for b in branches:
        slug = b.split("pending/")[-1]
        if os.path.exists(f"a/{slug}.html"):
            continue                      # deja publicat; ramura e reziduu
        titlu, cat, data = slug, "?", "?"
        raw = sh("git", "show", f"{b}:data/{slug}.json")
        if raw:
            try:
                d = json.loads(raw)
                titlu, cat, data = d.get("title", slug), d.get("category", "?"), d.get("date", "?")
            except Exception:
                pass
        asteapta.append((data, cat, titlu, slug))

    numar = sh("gh", "issue", "list", "--state", "open", "--search", TITLU,
               "--json", "number,title", "--limit", "5")
    existent = None
    try:
        for it in json.loads(numar or "[]"):
            if it["title"] == TITLU:
                existent = str(it["number"]); break
    except Exception:
        pass

    if not asteapta:
        if existent:
            subprocess.run(["gh", "issue", "close", existent, "--comment",
                            "Nu mai așteaptă nimic — toate articolele parcate au fost publicate."])
            print("închis: nu mai e nimic parcat")
        else:
            print("nimic parcat")
        return

    asteapta.sort(reverse=True)
    pe_cat = {}
    for _, cat, _, _ in asteapta:
        pe_cat[cat] = pe_cat.get(cat, 0) + 1
    rezumat = " · ".join(f"{c}: {n}" for c, n in sorted(pe_cat.items(), key=lambda x: -x[1]))
    linii = "\n".join(f"- **{d}** · `{c}` — {t}  \n  `{s}`" for d, c, t, s in asteapta)
    corp = (f"**{len(asteapta)} articole** scrise și oprite de poarta de siguranță "
            f"(politică internă sau persoană numită). Nu sunt pe site.\n\n"
            f"{rezumat}\n\n---\n\n{linii}\n\n---\n\n"
            f"Ca să le publici: dă-i lui Claude lista de slug-uri pe care le vrei, "
            f"sau spune „toate”.")

    if existent:
        subprocess.run(["gh", "issue", "edit", existent, "--body", corp])
        print(f"actualizat #{existent}: {len(asteapta)} parcate")
    else:
        subprocess.run(["gh", "issue", "create", "--title", TITLU, "--body", corp])
        print(f"deschis: {len(asteapta)} parcate")

if __name__ == "__main__":
    main()

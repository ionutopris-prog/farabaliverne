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
# Fondatorul NU e abonat explicit la repo (API-ul de subscription dă 404), deci
# o problemă deschisă de bot poate să nu-i trimită niciun email. Atribuirea și
# mențiunea @ notifică ÎNTOTDEAUNA, indiferent de setările de notificare — de
# aia le punem pe amândouă, nu ne bazăm pe „watching".
FONDATOR = "ionutopris-prog"

def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k).stdout.strip()


def rezumat_articol(b, fisier, d):
    """Articolul, în formă citibilă — ca să-l poți judeca direct din email,
    fără să intri pe GitHub. Fondatorul nu poate aproba ce nu vede."""
    r = [f"### {d.get('title','(fără titlu)')}",
         f"`{d.get('category','?')}` · {d.get('date','?')} · **{d.get('mainVerdict','?')}**",
         f"Sursă: {d.get('source','?')} — {d.get('url','')}",
         "", f"**Rezumat:** {d.get('dek','')}", ""]
    for cheie, et in (("probat", "✅ Se probează"), ("contestat", "⚠️ Contestat / neclar"),
                      ("opinie", "💬 Opinie, nu fapt")):
        it = d.get(cheie) or []
        if not it:
            continue
        r.append(f"**{et}** ({len(it)}):")
        for x in it:
            t = x.get("text", "") if isinstance(x, dict) else str(x)
            r.append(f"- {t[:600]}{'…' if len(t) > 600 else ''}")
            for sr in (x.get("sources") or [] if isinstance(x, dict) else []):
                r.append(f"  - [{sr.get('name','sursă')[:90]}]({sr.get('url','')})")
        r.append("")
    nota = str(d.get("aiNote", ""))
    if nota:
        r.append(f"**🤖 Nota AI:** {nota[:900]}{'…' if len(nota) > 900 else ''}")
    r.append(f"\n<sub>Ramura: `{b.split('origin/')[-1]}` · slug: `{fisier}`</sub>")
    return "\n".join(r)


def main():
    sh("git", "fetch", "-q", "origin", "+refs/heads/pending/*:refs/remotes/origin/pending/*")
    branches = sh("git", "for-each-ref", "--format=%(refname:short)",
                  "refs/remotes/origin/pending").split()
    asteapta = []
    for b in branches:
        # Citim ce articole are RAMURA, nu ce ne spune numele ei. Ramura
        # `pending/nazare-si-contracte-ilfov-pnl` conținea articolul
        # `nazare-premier-polymarket-crin-antonescu` — nume diferit, fiindcă
        # redactorul redenumește slug-ul după ce alege titlul final. Vechea
        # variantă căuta `data/<nume-ramură>.json`, nu-l găsea, și raporta
        # titlul, categoria și data ca „?”. Fondatorul vedea o listă de
        # semne de întrebare și nu putea decide nimic din ea.
        # DIFF față de main, nu listarea ramurii. O ramură `pending/` conține
        # ÎNTREG repo-ul, deci `ls-tree` întoarce toate cele ~500 de articole
        # publicate, nu pe cel adăugat de ea. Prima încercare a raportat 3581
        # de articole „parcate" — 71 de ramuri × tot ce era pe fiecare.
        # Ne interesează exclusiv fișierele ADĂUGATE de ramură față de main.
        fisiere = [f for f in sh("git", "diff", "--name-only", "--diff-filter=A",
                                 f"origin/main...{b}", "--", "data/").split()
                   if f.endswith(".json")]
        for f in fisiere:
            slug = os.path.basename(f)[:-5]
            if os.path.exists(f"a/{slug}.html"):
                continue                  # deja publicat; ramura e reziduu
            titlu, cat, data = slug, "?", "?"
            raw = sh("git", "show", f"{b}:{f}")
            if raw:
                try:
                    d = json.loads(raw)
                    titlu, cat, data = d.get("title", slug), d.get("category", "?"), d.get("date", "?")
                except Exception:
                    pass
            asteapta.append((data, cat, titlu, slug, rezumat_articol(b, slug, d) if raw else ""))

    # Căutăm în TOATE stările, nu doar „open". Problema se închide singură când
    # nu mai e nimic parcat; dacă am căuta doar printre cele deschise, la
    # următorul articol oprit s-ar deschide una nouă — și ai ajunge cu zece
    # probleme identice în loc de una reluată.
    numar = sh("gh", "issue", "list", "--state", "all", "--search", TITLU,
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
    for _, cat, _, _, _ in asteapta:
        pe_cat[cat] = pe_cat.get(cat, 0) + 1
    rezumat = " · ".join(f"{c}: {n}" for c, n in sorted(pe_cat.items(), key=lambda x: -x[1]))
    linii = "\n".join(f"- **{d}** · `{c}` — {t}  \n  `{s}`" for d, c, t, s, _ in asteapta)
    corp = (f"**{len(asteapta)} articole** scrise și oprite de poarta de siguranță "
            f"(politică internă sau persoană numită). Nu sunt pe site.\n\n"
            f"{rezumat}\n\n---\n\n{linii}\n\n---\n\n"
            f"---\n\n"
            f"### Ce poți face — direct din email\n\n"
            f"**Răspunde la mailul ăsta** (sau comentează aici) cu una dintre:\n\n"
            f"| Comandă | Ce face |\n|---|---|\n"
            f"| `publica toate` | publică tot ce e în listă |\n"
            f"| `publica <slug>` | publică doar articolul ăla |\n"
            f"| `respinge <slug>` | șterge definitiv, nu se publică |\n\n"
            f"Diacriticele și majusculele nu contează. Textul citat din mail e ignorat, "
            f"deci poți răspunde normal, fără să ștergi nimic.\n\n"
            f"**Vrei să MODIFICI un articol înainte de publicare?** Comenzile de mai sus "
            f"doar publică sau resping. Pentru schimbări de conținut, spune-i lui Claude "
            f"ce anume să schimbe — el editează, apoi publici.")

    if existent:
        # O problemă închisă („nu mai e nimic parcat") trebuie REDESCHISĂ când
        # apare ceva nou. Altfel `gh issue list --state open` n-o mai găsește,
        # se deschide una nouă la fiecare ediție, și ajungi cu zece probleme.
        subprocess.run(["gh", "issue", "reopen", existent], capture_output=True)
        # Corpul problemei se actualizează mereu, ca să fie lista completă
        # într-un singur loc. Dar GitHub NU trimite notificare la editarea
        # corpului — doar la deschidere și la comentarii. Între 21 și 23
        # august, lista s-a schimbat de mai multe ori fără ca fondatorul să
        # primească un cuvânt: tăcerea pe care scriptul ăsta trebuia s-o
        # elimine se mutase, pur și simplu, în altă parte.
        # De-aia: corpul se editează întotdeauna, dar când apar articole NOI
        # față de ce era acolo, lăsăm și un comentariu — ăla ajunge pe email.
        vechi_corp = sh("gh", "issue", "view", existent, "--json", "body", "--jq", ".body")
        noi = [(d, c, t, sl, txt) for d, c, t, sl, txt in asteapta if f"`{sl}`" not in vechi_corp]
        subprocess.run(["gh", "issue", "edit", existent, "--body", corp])
        if noi:
            lista = "\n\n---\n\n".join(txt for *_, txt in noi)
            subprocess.run(["gh", "issue", "edit", existent, "--add-assignee", FONDATOR],
                           capture_output=True)
            subprocess.run(["gh", "issue", "comment", existent, "--body",
                            f"@{FONDATOR} — **{len(noi)} articol(e) nou(i)** parcate de la ultima "
                            f"verificare (total în așteptare: {len(asteapta)}):\n\n{lista}"])
            print(f"actualizat #{existent} + comentariu: {len(noi)} noi din {len(asteapta)} parcate")
        else:
            print(f"actualizat #{existent}: {len(asteapta)} parcate, niciunul nou")
    else:
        subprocess.run(["gh", "issue", "create", "--title", TITLU,
                        "--assignee", FONDATOR,
                        "--body", f"@{FONDATOR}\n\n{corp}"])
        print(f"deschis: {len(asteapta)} parcate")

if __name__ == "__main__":
    main()

#!/bin/bash
# Copie de siguranţă zilnică a documentelor INTERNE — cele care nu sunt în git.
#
# De ce există: WORKLOG.md şi CLAUDE.md sunt intenţionat în .gitignore, fiindcă
# repo-ul e public. Consecinţa e că opt luni de jurnal şi regulile proiectului
# trăiesc într-un singur loc: discul Mac-ului.
#
# Pe 23 august scriptul s-a pierdut el însuşi, la un `git reset --hard` care a
# aruncat commitul în care era. Launchd a continuat să-l caute în gol, fără să
# se plângă. De-aia scrie acum în log ŞI când reuşeşte, ŞI când nu găseşte ce
# trebuie — un backup care tace poate să nu existe.
set -u
REPO="$HOME/Projects/farabaliverne"
DEST="$HOME/Documents/Backup-farabaliverne"
cd "$REPO" || { echo "$(date '+%F %H:%M') · EROARE: nu găsesc $REPO" >> "$DEST/backup.log"; exit 1; }
mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M)"

LIPSA=""
for f in WORKLOG.md CLAUDE.md local/corpus.jsonl local/stil.md .env; do
  if [ -f "$f" ]; then cp "$f" "$DEST/$(basename "$f")"; else LIPSA="$LIPSA $f"; fi
done

git bundle create "$DEST/farabaliverne-backup-$STAMP.bundle" --all >/dev/null 2>&1

# Păstrăm ultimele 7 arhive. Fără curăţenie, ~200 MB pe zi umple discul.
ls -t "$DEST"/*.bundle 2>/dev/null | tail -n +8 | xargs -r rm -f

N=$(ls "$DEST"/*.bundle 2>/dev/null | wc -l | tr -d ' ')
echo "$(date '+%F %H:%M') · backup ok · $N arhive${LIPSA:+ · lipsă:$LIPSA}" >> "$DEST/backup.log"

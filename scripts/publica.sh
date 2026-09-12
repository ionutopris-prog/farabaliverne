#!/bin/bash
# publica.sh — commit + push cu rezolvarea automată a conflictelor pe fișierele
# GENERATE (a/*.html, parlamentar/, *.html din rădăcină, feed.xml, sitemap*,
# stare.txt), care apar când ediția automată de pe GitHub a regenerat site-ul
# între timp. Regula: fișierele generate se iau de la upstream și se
# regenerează local; ce e scris de mână (data/, scripts/, img/) se păstrează.
#   scripts/publica.sh "mesaj de commit"
set -u
cd "$(dirname "$0")/.."
MSG="${1:-Regenerare}"
TRAILER="Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EQLxvUvUXRnYo7GLRtvd62"
git add -A . && git commit -q -m "$MSG

$TRAILER" 2>/dev/null
for i in 1 2 3 4 5; do
  if git pull -q --rebase origin main 2>/dev/null; then
    :
  else
    # conflicte: doar pe generate → ours (upstream), apoi continuăm
    C=$(git diff --name-only --diff-filter=U)
    if [ -n "$C" ]; then
      echo "$C" | xargs git checkout --ours -- 2>/dev/null
      echo "$C" | xargs git add -- 2>/dev/null
      GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || { git rebase --abort; echo "rebase abandonat"; exit 1; }
    fi
    python3 scripts/build_site.py >/dev/null 2>&1
    git add -A . && git commit -q -m "Regenerare după rebase

$TRAILER" 2>/dev/null
  fi
  if git push -q origin main 2>/dev/null; then
    echo "✅ push: $(git log --oneline -1)"; exit 0
  fi
  sleep $((i*10))
done
echo "❌ push nereușit după 5 încercări"; exit 1

#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

for f in *.mmd; do
  echo "→ ${f%.mmd}.png"
  npx --yes @mermaid-js/mermaid-cli@11.4.0 \
    -i "$f" \
    -o "${f%.mmd}.png" \
    -b white \
    -w 1400 \
    -H 900
done

echo "Done: $(ls -1 *.png | wc -l) PNG files"

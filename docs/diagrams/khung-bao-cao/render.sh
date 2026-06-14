#!/usr/bin/env bash
# Render diagram sources → PNG (Word-ready, 300 DPI).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=== PlantUML (UML chuẩn — khuyến nghị cho Word) ==="
for f in *.puml; do
  [[ -f "$f" ]] || continue
  echo "→ ${f%.puml}.png"
  plantuml -tpng -SDPI=300 "$f"
done

echo "Done: $(ls -1 *.png 2>/dev/null | wc -l) PNG files"

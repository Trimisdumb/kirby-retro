#!/bin/bash
# Rapatrie le bundle EmulatorJS (loader, UI, localisation, compression, sources)
# ainsi que les cores listés dans config/cores.txt, depuis le CDN officiel.
#
#   bash scripts/fetch-ejs.sh /srv/docker/retro/ejs
#
# EJS_VERSION=stable|latest|nightly (défaut : stable)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="${EJS_VERSION:-stable}"
BASE="https://cdn.emulatorjs.org/${VERSION}/data"
DEST="${1:-$HERE/../ejs}"
CORES_FILE="${CORES_FILE:-$HERE/../config/cores.txt}"

mkdir -p "$DEST/data"

mapfile -t CORES < <(grep -vE '^[[:space:]]*#' "$CORES_FILE" | sed -E 's/[[:space:]]*#.*$//' | tr -d ' \r' | grep -v '^$')
if [ "${#CORES[@]}" -eq 0 ]; then echo "Aucun core dans $CORES_FILE"; exit 1; fi
echo "Cores demandés : ${CORES[*]}"

# fceumm-thread-legacy-wasm.data -> fceumm
core_of() {
  local n="${1%.data}"
  while true; do
    case "$n" in
      *-wasm)   n="${n%-wasm}" ;;
      *-thread) n="${n%-thread}" ;;
      *-legacy) n="${n%-legacy}" ;;
      *) break ;;
    esac
  done
  printf '%s' "$n"
}

mirror() {
  local rel="$1" name core
  curl -fsSL --retry 3 --max-time 60 "$BASE/$rel" \
    | grep -oE 'href="[^"]+"' | sed -E 's/^href="//; s/"$//' \
    | while IFS= read -r name; do
        # liste blanche : ignore ../ ./, les chemins absolus et .theme/... du listing lighttpd
        case "$name" in
          */)  [[ "$name" =~ ^[A-Za-z0-9_-]+/$ ]] || continue ;;
          *)   [[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]] || continue ;;
        esac
        if [ "$rel" = "cores/" ]; then
          # On garde les 4 variantes des cores choisis :
          #   <core>-wasm.data            mono-thread (repli)
          #   <core>-thread-wasm.data     multi-thread (SharedArrayBuffer) ← perf
          #   <core>-legacy-wasm.data     WebGL1
          #   <core>-thread-legacy-wasm.data
          # …et on descend dans les sous-dossiers (cores/reports/…).
          case "$name" in
            */) ;;
            *.data) core="$(core_of "$name")"
                    case " ${CORES[*]} " in *" $core "*) ;; *) continue ;; esac ;;
            *) continue ;;
          esac
        fi
        case "$name" in
          */) mkdir -p "$DEST/data/$rel$name"; mirror "$rel$name" ;;
          *)  mkdir -p "$DEST/data/$rel"
              # relance rapide : on ne retélécharge pas ce qui est déjà là (EJS_REFETCH=1 pour forcer)
              if [ -s "$DEST/data/$rel$name" ] && [ "${EJS_REFETCH:-0}" != "1" ]; then
                continue
              fi
              if ! curl -fsSL --retry 3 --max-time 900 "$BASE/$rel$name" -o "$DEST/data/$rel$name"; then
                rm -f "$DEST/data/$rel$name"
                echo "   ! échec du téléchargement : $rel$name" >&2
              fi ;;
        esac
      done
}

mirror ""

cp -f "$CORES_FILE" "$DEST/cores.txt" 2>/dev/null || true
printf '{"version":"%s","fetchedAt":"%s"}\n' "$VERSION" "$(date -Iseconds)" > "$DEST/data/version-local.json"

echo ""
echo "=== EmulatorJS $VERSION → $DEST/data ==="
echo "fichiers : $(find "$DEST/data" -type f | wc -l)"
echo "cores    : $(find "$DEST/data/cores" -type f | wc -l)"
du -sh "$DEST/data"

#!/usr/bin/env bash
set -euo pipefail

IMAGE="localhost/ptxprint:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${WORK:-$SCRIPT_DIR}"

usage() {
  cat <<'EOF'
Usage: run.sh COMMAND [ARGUMENTS...]

Lance PTXprint (interface graphique ou batch) dans un conteneur podman.

COMMAND :
  gui [args...]    Lance l'interface graphique (X11 ou Wayland).
  cli [args...]    Lance PTXprint en mode batch/cli (sans affichage).
  build            Reconstruit l'image podman "ptxprint".
  help             Affiche cette aide.

Variables d'environnement :
  WORK   Dossier monté dans /work du conteneur (défaut: répertoire courant).

Exemples :
  ./run.sh gui
  ./run.sh cli -P -p /work/monProjet
  ./run.sh cli -h
  WORK=/chemin/vers/dossier ./run.sh gui
EOF
}

BASE_ARGS=()
common_args() {
  BASE_ARGS=(
    --rm
    --interactive --tty
    --user 0:0
    -e LANG=fr_FR.UTF-8
    -e LC_ALL=fr_FR.UTF-8
    -v "${WORK}:/work"
    -v "${WORK}/.ptxhome:/home/ptxuser"
  )
}

cli() {
  common_args
  exec podman run "${BASE_ARGS[@]}" "${IMAGE}" ptxprint --nox11 -p /work/projects "$@"
}

gui() {
  local -a args=()

  if [[ -n "${WAYLAND_DISPLAY:-}" && -n "${XDG_RUNTIME_DIR:-}" ]]; then
    # Wayland
    args+=(
      -e WAYLAND_DISPLAY="$WAYLAND_DISPLAY"
      -e 'XDG_RUNTIME_DIR=/tmp/xdg'
      -e 'DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/xdg/bus'
      -v "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}:/tmp/xdg/${WAYLAND_DISPLAY}"
      -v "${XDG_RUNTIME_DIR}/bus:/tmp/xdg/bus"
    )
  elif [[ -n "${DISPLAY:-}" ]]; then
    # X11 (ptxprint enveloppe sa session dbus via dbus-run / XDG_RUNTIME_DIR)
    args+=(
      -e DISPLAY="$DISPLAY"
      -v /tmp/.X11-unix:/tmp/.X11-unix
    )
  else
    echo "Aucun affichage détecté (DISPLAY / WAYLAND_DISPLAY)." >&2
    exit 1
  fi

  common_args
  exec podman run "${BASE_ARGS[@]}" "${args[@]}" "${IMAGE}" ptxprint -p /work/projects "$@"
}

build() {
  local tag="${IMAGE%%:*}"
  podman build -t "$tag:latest" .
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    gui)   gui "$@";;
    cli)   cli "$@";;
    build) build;;
    ""|help|-h|--help) usage; exit 0;;
    *) echo "Commande inconnue : $cmd" >&2; usage; exit 1;;
  esac
}

main "$@"
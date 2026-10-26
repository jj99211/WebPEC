#!/bin/sh
# Arranca WebPEC en Linux (o macOS). Si se abre con doble clic, sin terminal, abre una
# para que se vea que la aplicación está en marcha y se pueda cerrar.
cd "$(dirname "$0")" || exit 1
if [ ! -t 1 ] && [ -z "$WEBPEC_EN_TERMINAL" ]; then
    export WEBPEC_EN_TERMINAL=1
    for t in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal xterm; do
        command -v "$t" >/dev/null 2>&1 || continue
        case "$t" in
            gnome-terminal|mate-terminal) exec "$t" -- python3 webpec.py "$@" ;;
            xfce4-terminal) exec "$t" -x python3 webpec.py "$@" ;;
            *) exec "$t" -e python3 webpec.py "$@" ;;
        esac
    done
fi
exec python3 webpec.py "$@"

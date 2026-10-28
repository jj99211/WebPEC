#!/bin/sh
# Arranca WebPEC en Linux (o macOS). Si se abre con doble clic, sin terminal, abre una
# para que se vea que la aplicación está en marcha y se pueda cerrar.
cd "$(dirname "$0")" || exit 1
if [ ! -t 1 ] && [ -z "$WEBPEC_EN_TERMINAL" ]; then
    export WEBPEC_EN_TERMINAL=1
    for t in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal xterm; do
        command -v "$t" >/dev/null 2>&1 || continue
        case "$t" in
            gnome-terminal|mate-terminal) exec "$t" -- "$PWD/WebPEC.sh" "$@" ;;
            xfce4-terminal) exec "$t" -x "$PWD/WebPEC.sh" "$@" ;;
            *) exec "$t" -e "$PWD/WebPEC.sh" "$@" ;;
        esac
    done
fi

# Si algo falla, la terminal espera para que se pueda leer el mensaje
esperar() {
    if [ -t 0 ]; then
        printf '\nPulsa Intro para cerrar... '
        read -r _
    fi
}

if ! command -v python3 >/dev/null 2>&1; then
    echo "No se encuentra Python 3. Instálalo (paquete python3) y vuelve a intentarlo."
    esperar
    exit 1
fi
python3 webpec.py "$@" || { esperar; exit 1; }

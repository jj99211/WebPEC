#!/bin/sh
# Crea el icono de WebPEC en el escritorio y en el menú de aplicaciones
cd "$(dirname "$0")" || exit 1
python3 webpec.py --crear-acceso-directo
# Si se ha abierto en una terminal, espera para que se pueda leer el resultado
if [ -t 0 ]; then
    printf '\nPulsa Intro para cerrar... '
    read -r _
fi

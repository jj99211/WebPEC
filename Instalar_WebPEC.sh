#!/bin/sh
# Instala WebPEC en este ordenador: comprueba Python, crea el icono del escritorio y del menú,
# prepara los datos (también los de una versión anterior) y arranca la aplicación.
# Se puede repetir sin riesgo, por ejemplo después de mover la carpeta.
cd "$(dirname "$0")" || exit 1
exec ./WebPEC.sh --instalar

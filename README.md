# WebPEC — Avisos de pérdida de evaluación continua

Aplicación web local que genera los **avisos del 7,5 %** y las **confirmaciones de pérdida del 15 %** de la
evaluación continua (Formación Profesional) a partir de los listados de faltas de Raíces.

> **Uso interno del IES Rosa Chacel (Madrid).** WebPEC está hecha para el profesorado de este instituto: usa
> sus modelos de documentos, sus cargos y sus criterios. No está pensada ni preparada para otros centros, y
> no se ofrece soporte fuera de él.

## Descargar

La última versión está siempre en **[Releases → Latest](../../releases/latest)**: descarga el fichero
`WebPEC_vX.YY.zip` (no el «Source code»). Desde la versión 3.31, WebPEC avisa sola cuando hay una versión nueva.

## Instalar o actualizar

1. Necesita **Python 3.9 o posterior** ([python.org](https://www.python.org); en Windows, marcar
   «Add Python to PATH»). Todo lo demás va incluido.
2. Descomprimir el ZIP en cualquier sitio.
3. Doble clic en `Instalar_WebPEC.bat` (Windows) o `Instalar_WebPEC.sh` (Linux) y seguir las preguntas.
   Si ya hay un WebPEC instalado, elegir «Actualizar»: los datos se conservan.

Para pasar los avisos a PDF hace falta LibreOffice o Microsoft Word. Las instrucciones completas están en
[`LEEME.txt`](LEEME.txt) y en el [manual de usuario](MANUAL_USUARIO.md); los cambios de cada versión, en
[`CAMBIOS.md`](CAMBIOS.md).

## Privacidad

WebPEC funciona en el propio ordenador (`http://localhost`). Los informes, los avisos y los datos del alumnado
se quedan en la carpeta `DATOS/` de cada instalación: no se envían a ningún sitio ni forman parte de este
repositorio.

## Licencia

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es) — Departamento de Informática del
IES Rosa Chacel. Las librerías de `lib/` conservan sus licencias, y el escudo del centro y las plantillas no se
licencian con WebPEC. Detalle en [`LICENCIA.txt`](LICENCIA.txt).

# Historial de cambios de WebPEC

Numeración **X.YY**:
- cambios pequeños suben las centésimas (2.00 → 2.01);
- si una versión trae muchos cambios, se salta a la décima siguiente (2.07 → 2.10);
- los cambios realmente grandes cambian la unidad (2.xx → 3.00).

La versión en uso está en el fichero `VERSION` y se ve junto al nombre de la aplicación.
Cada versión queda guardada en git con su etiqueta (`git tag` las muestra).

## 2.02 — 2026-10-26

- Icono en el escritorio con un doble clic: `Crear_acceso_directo.bat` (Windows) y
  `Crear_acceso_directo.sh` (Linux), o `webpec.py --crear-acceso-directo`.
  - Windows: acceso directo «WebPEC» con el escudo; la ventana del servidor arranca minimizada.
  - Linux: icono en el escritorio y en el menú de aplicaciones.
- Escudo en formato `.ico` (`web/escudo.ico`).

## 2.01 — 2026-10-26

- El escudo del IES Rosa Chacel sustituye al logo anterior (cabecera, icono de la pestaña
  y pantalla de cierre).

## 2.00 — 2026-10-26

- El procesado ya no empieza solo: la pantalla de Informes muestra los informes pendientes
  (con el nombre que recibirán) y todo se hace al pulsar **Procesar informes**: renombrado,
  petición de datos de módulos y profesores nuevos y generación de los avisos. Al guardar los
  datos que faltan, el procesado continúa solo.
- Botón **Borrar todos los informes procesados** en la pantalla de Informes.
- Botón **Borrar avisos…** en la pestaña Avisos: pendientes, entregados o todos.
- Botón **Vaciar registro** en la pestaña Registro.
- Botón **Borrar todos los módulos y profesores** en la pestaña Módulos, para empezar con
  una hoja limpia (por ejemplo, en otro departamento).
- Antes de vaciar el registro o la hoja de módulos se guarda una copia en `COPIAS_SEGURIDAD/`.
- Control de versiones: fichero `VERSION`, este historial y repositorio git.

## 1.00 — 2026-10-26

- Primera versión publicada: aplicación web local (Windows y Linux) para subir los informes
  de faltas de Raíces, registrar módulos y profesores, generar los avisos del 7,5 % y las
  pérdidas del 15 %, imprimirlos, descargarlos y marcarlos como entregados.

# Historial de cambios de WebPEC

Numeración **X.YY**:
- cambios pequeños suben las centésimas (2.00 → 2.01);
- si una versión trae muchos cambios, se salta a la décima siguiente (2.07 → 2.10);
- los cambios realmente grandes cambian la unidad (2.xx → 3.00).

La versión en uso está en el fichero `VERSION` y se ve junto al nombre de la aplicación.
Cada versión queda guardada en git con su etiqueta (`git tag` las muestra).

## 3.20 — 2026-10-28

- **Dar de baja a un alumno/a** (pestaña Alumnado, enlace «Baja»): para quien ha dejado el centro pero sigue en los
  informes de Raíces. Desaparece de la lista y no vuelve a recibir avisos en ningún módulo de su grupo. Sus avisos ya
  generados y el registro se conservan (si tiene avisos en Pendientes, WebPEC lo indica para anularlos). Las bajas
  se ven al final de la pestaña, en «Alumnado dado de baja», donde se pueden **recuperar** si fueron un error.
- **Editar un alumno/a** (enlace «Editar»): corregir a mano su nombre o su correo. El nombre corregido se usa en los
  listados, en los correos y en los avisos nuevos; los informes de Raíces se siguen reconociendo por el original.
- Formato de datos 5: `correos_alumnado.csv` pasa a `alumnado.csv` (se migra solo al arrancar, con copia previa).

## 3.12 — 2026-10-28

- Avisos: la barra de selección (Imprimir, Descargar ZIP, Enviar por correo, Entregados, Anular…) se ve en una sola
  línea cuando cabe; antes se partía en tres y los botones se montaban unos sobre otros.

## 3.11 — 2026-10-28

- **Enviar por correo** (botón en cada aviso y en la barra de selección): Thunderbird abre un correo por aviso con
  la dirección del alumno/a (si se importó), el asunto, un texto explicativo y el PDF adjunto, listo para revisar y
  enviar. Sin Thunderbird (o eligiéndolo en Configuración), se descarga un borrador `.eml` por aviso. Los adjuntos se
  copian a `~/WebPEC_correo` (Thunderbird instalado como snap no puede leer otros discos); se limpia sola.
- **Profesor/a con el nombre escrito de otra forma**: si el nombre de un informe se parece al de alguien de la lista
  (p. ej. dado de alta a mano sin el segundo nombre), al procesar se pregunta si es la misma persona; al confirmarlo
  se guarda con el nombre de Raíces y conserva su firma.
- La pestaña Avisos muestra el correo de cada alumno/a.

## 3.10 — 2026-10-28

- **El instalador instala y actualiza solo.** Pregunta dónde instalar: si ya hay un WebPEC en el ordenador (lo
  reconoce por el icono del escritorio), ofrece **actualizarlo** conservando sus datos; si no, propone
  `Documentos/WebPEC`; también se puede dejar donde está o escribir otra carpeta. Copia el programa (nunca los
  datos), quita los ficheros que ya no se usan, pide cerrar WebPEC si está abierto, rehace el icono y arranca.
  Ya no hace falta copiar carpetas a mano: basta con descomprimir el ZIP y hacer doble clic en el instalador.
- **¿Quién eres?** Al abrir WebPEC se elige el propio nombre (bajo el título se ve y se cambia). Quien aún no tiene
  informes procesados elige «Soy nuevo/a» y escribe nombre y apellidos como en Raíces: así su primer informe ya lo
  reconoce. También desde Módulos → **Añadir profesor/a…** (y **Borrar** en cada fila).
- **Quién hace cada acción**: el registro anota quién genera, entrega (y cuándo) y anula cada aviso, y la nueva
  sección **Actividad** (en Registro) lista todas las acciones con fecha y persona (`DATOS/actividad.csv`).
- Nueva pestaña **Alumnado**: situación de cada alumno/a en cada módulo según el último informe procesado (faltas,
  porcentaje, umbrales, aviso o pérdida, y quién supera el 7,5 % sin aviso vigente), con filtros.
- **Importar correos del alumnado** desde un CSV o Excel (columnas reconocidas solas). Solo como dato: WebPEC no
  envía nada.
- **Exportar e importar todos los datos** en un ZIP (Configuración), con copia previa al importar. Sirve como copia
  de seguridad o para llevar los datos a otro ordenador; admite datos de versiones anteriores.
- Pestaña **Ayuda**: el manual de usuario en el navegador, con botón para imprimirlo o guardarlo en PDF. El paquete
  incluye `MANUAL_USUARIO.pdf`.
- Formato de datos 4 (se migra solo al arrancar, con copia previa).

## 3.00 — 2026-10-28

- **Datos separados del programa**, en la carpeta `DATOS/`. Actualizar WebPEC es descomprimir la versión nueva
  encima: los datos no se tocan.
- **Migración automática de datos.** Al arrancar, si los datos son de una versión anterior (también los de la 2.x,
  sueltos en la carpeta del programa), WebPEC guarda antes un ZIP con todos ellos en
  `DATOS/COPIAS_SEGURIDAD/`, los pone al día y muestra un aviso con lo que ha hecho (queda anotado en
  `DATOS/migraciones.log`). Si algo falla a medias (p. ej. un fichero abierto en Excel), basta con cerrarlo y volver a
  arrancar.
- **Anular avisos**, en lugar de borrarlos. Desde Avisos (botón «Anular…») o desde el Registro (enlace «Anular»),
  con motivo obligatorio: el aviso queda tachado en el registro con fecha y motivo, su documento pasa a la nueva
  bandeja **Anulados** y el siguiente informe puede volver a generarlo. Una pérdida del 15 % hay que anularla antes
  que su aviso del 7,5 % (o las dos a la vez). Sirve también para los avisos cuyo documento se borró en la 2.x.
- Desaparece el «Borrar» de avisos sueltos (y de la pregunta tras imprimir). «Borrar avisos…» se mantiene para
  limpiar documentos al terminar el curso.
- **Instalador**: `Instalar_WebPEC.bat` (Windows) e `Instalar_WebPEC.sh` (Linux) comprueban Python, crean el icono
  del escritorio (y del menú en Linux), preparan los datos y arrancan. Sustituyen a `Crear_acceso_directo.*`.
- **Licencia Creative Commons BY-NC-SA 4.0** (Departamento de Informática del IES Rosa Chacel): en el pie de la
  pantalla principal, en la pantalla de cierre y en `LICENCIA.txt`.
- Manual de usuario (`MANUAL_USUARIO.md`) y `LEEME.txt` al día.
- Linux: si falta Python 3 o WebPEC no puede arrancar, la terminal espera para que se pueda leer el mensaje.

## 2.04 — 2026-10-26

- Avisos: confirmación de entrega. Antes de pasar avisos a **Entregados**, WebPEC recuerda que la entrega la hace
  el profesor en persona o por correo electrónico y pide marcar «Confirmo que se han entregado» (el botón no se
  activa hasta marcarla). Vale para la barra de selección, para la pregunta tras imprimir/descargar y para el
  nuevo enlace «Entregado» de cada fila.
- Texto de ayuda sobre la tabla de pendientes explicando las casillas de selección.

## 2.03 — 2026-10-26

- Corregido: en el ZIP de instalación, `WebPEC.sh`, `Crear_acceso_directo.sh` y `webpec.py` no
  tenían permiso de ejecución, y en Linux el doble clic no los arrancaba.

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

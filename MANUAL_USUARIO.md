# WebPEC — Manual de usuario

*Avisos de pérdida de evaluación continua · Departamento de Informática · IES Rosa Chacel (Madrid) ·
Manual de la versión 3.11*

---

## 1. Para qué sirve

WebPEC prepara los documentos de **pérdida de evaluación continua** del alumnado de FP a partir de los
listados de faltas que se descargan de Raíces. El profesorado solo tiene que subir los informes: la aplicación
calcula quién ha superado los límites de faltas y rellena los documentos oficiales.

Genera dos tipos de documento:

| Documento | Cuándo se genera |
|---|---|
| **Aviso (7,5 %)** | El alumno/a tiene faltas injustificadas por encima del 7,5 % de las horas del módulo y todavía no se le había avisado. |
| **Confirmación de pérdida (15 %)** | El alumno/a supera el 15 %, ya recibió el aviso en un informe anterior y desde entonces ha acumulado más faltas. |

Los documentos salen rellenos con el nombre del alumno/a, el grupo, el módulo, la fecha del informe y las firmas
del profesor/a y de Jefatura de Estudios. WebPEC **no entrega** nada: la entrega la hace cada profesor/a, en
persona o por correo, y después la anota en la aplicación.

Todo el departamento usa la misma instalación y ve los avisos de todos.

## 2. Instalación y puesta en marcha

**Requisitos:** Python 3.9 o posterior (en Windows, al instalarlo, marcar «Add Python to PATH»). Para que los
avisos salgan en PDF hace falta LibreOffice o Microsoft Word; sin ninguno de los dos se generan en Word (.docx).

**Instalar o actualizar** (lo mismo en los dos casos):

1. Descomprimir el ZIP de WebPEC en cualquier sitio, por ejemplo en Descargas (en Windows: botón derecho →
   «Extraer todo»; el instalador no funciona abriéndolo desde dentro del ZIP).
2. Doble clic en el instalador: `Instalar_WebPEC.bat` (Windows) o `Instalar_WebPEC.sh` (Linux; si el
   explorador pregunta, elegir «Ejecutar»).
3. El instalador pregunta **dónde instalar**. Basta con pulsar Intro para la opción recomendada:
   - si en el ordenador ya hay un WebPEC (lo reconoce por el icono del escritorio): **actualizar esa
     instalación**, conservando todos sus datos;
   - si no lo hay: instalar en la carpeta **Documentos/WebPEC**;
   - también se puede dejar donde está o escribir otra carpeta.

El instalador comprueba Python, copia el programa (nunca los datos), crea el icono «WebPEC» con el escudo del
instituto en el escritorio (en Linux, también en el menú de aplicaciones) y arranca la aplicación. Si WebPEC está
abierto, pide cerrarlo antes. Después, la carpeta descomprimida ya no hace falta y se puede borrar. Se puede
repetir sin riesgo, por ejemplo para rehacer el icono si se mueve la carpeta.

Para **actualizar a una versión nueva** se hace lo mismo: descomprimir el ZIP nuevo en cualquier sitio y ejecutar
su instalador; con Intro elige «Actualizar la instalación que ya hay». Si WebPEC está abierto, el instalador pide
cerrarlo (botón de apagado) antes de copiar nada.

**Arrancar** (cada día): doble clic en el icono «WebPEC» del escritorio (o en `WebPEC.bat` / `WebPEC.sh`).

Se abre una ventana de terminal y el navegador con la aplicación (`http://localhost:8765`). **La ventana de
terminal tiene que seguir abierta** mientras se usa WebPEC; en Windows queda minimizada en la barra de tareas.

> Abrir `web/index.html` con doble clic **no funciona**: hay que entrar siempre con el lanzador o el icono.

**Cerrar:** botón de apagado (arriba a la derecha). Aparece la pantalla «WebPEC se ha cerrado» y ya se puede
cerrar la pestaña.

**Datos de una versión anterior:** si los datos son de una versión anterior, al arrancar WebPEC guarda una copia
de seguridad, los pone al día y muestra un aviso con lo que ha hecho. No se pierde nada.

**¿Quién eres?** Al abrir WebPEC hay que elegir el propio nombre en la lista del profesorado: WebPEC anota quién
procesa, entrega y anula cada aviso. Quien todavía no está en la lista (porque aún no se ha procesado ningún informe
suyo) elige «Soy nuevo/a» y escribe su **nombre** y sus **apellidos** como aparecen en Raíces (las tildes no
importan): así, cuando llegue su primer informe, WebPEC ya lo reconoce. El nombre elegido se ve bajo el título;
haciendo clic en él se cambia.

**Ayuda:** la pestaña **Ayuda** abre este manual en otra pestaña del navegador, con un botón para imprimirlo o
guardarlo en PDF. El manual también va en PDF en la carpeta de WebPEC (`MANUAL_USUARIO.pdf`).

## 3. Uso habitual paso a paso

1. **Descargar de Raíces** el «Listado de faltas totales» de cada grupo y módulo, en PDF. El nombre del fichero
   da igual.
2. Abrir WebPEC, elegir el propio nombre en «¿Quién eres?» y, en la pestaña **Informes**, **arrastrar los PDF** a la zona de subida (o hacer clic en ella
   para elegirlos).
3. Revisar la lista de *Informes pendientes de procesar*: muestra el nombre que recibirá cada informe
   (`FECHA_GRUPO_MÓDULO_Faltas.pdf`).
4. Pulsar **Procesar informes**. Si es la primera vez que aparece un módulo o un profesor/a, WebPEC pide los datos
   que le faltan (horas totales y siglas del módulo, nombre del profesor/a tal y como debe ir en la firma) y
   después continúa sola. Si el nombre del profesor/a del informe se parece al de alguien que ya está en la lista
   (por ejemplo, dado de alta sin su segundo nombre), WebPEC pregunta si es la misma persona: al confirmarlo, se
   guarda con el nombre que trae Raíces y conserva su firma.
5. Ir a **Avisos → Pendientes de entregar**, marcar los avisos e **Imprimir** (salen todos juntos en un PDF),
   **Descargar ZIP** o **Enviar por correo**.
6. Entregar los documentos al alumnado y, cuando estén entregados, pasarlos a **Entregados** confirmando la
   entrega.

## 4. Menús

### Informes

- **Zona de subida:** arrastrar aquí los PDF de faltas de Raíces.
- **Informes pendientes de procesar:** lo que se ha subido y todavía no se ha procesado. Nada se renombra ni se
  genera hasta pulsar el botón. **Actualizar** vuelve a leer la lista.
- **Procesar informes:** renombra los informes, pide los datos que falten y genera los avisos. Al terminar
  muestra un resumen con los avisos creados.
- **Informes ya procesados** (desplegable): histórico de informes.
- **Borrar todos los informes procesados:** borra los PDF de Raíces ya procesados (no afecta a los avisos ni al
  registro).

### Avisos

- **Pendientes de entregar / Entregados / Anulados:** cambia entre las tres bandejas. En Entregados y Anulados
  se ve cuándo y quién lo hizo.
- **Filtros:** por profesor/a, por tipo (7,5 % o 15 %) y búsqueda por alumno, grupo o módulo.
- **Casillas de selección:** al marcar uno o varios avisos aparece una barra inferior con:
  - **Imprimir:** une los avisos marcados en un solo PDF y abre la impresión.
  - **Descargar ZIP:** descarga los documentos marcados.
  - **Marcar como entregados** (en la bandeja de entregados, **Volver a pendientes**).
  - **Enviar por correo:** prepara un correo por aviso (ver más abajo).
  - **Anular…:** para avisos emitidos por error (ver más abajo).
- **Correo** (en cada fila): prepara el correo de ese aviso.
- **Entregado** (en cada fila): pasa ese aviso a la bandeja de entregados.
- Al pasar avisos a Entregados, WebPEC pide marcar «Confirmo que se han entregado».
- **Borrar avisos…:** borra de una vez los documentos pendientes, los entregados o todos. Está pensado para
  limpiar al terminar el curso: el Registro los conserva y no se vuelven a generar.

**Enviar por correo.** WebPEC abre **Thunderbird** con un correo por aviso ya preparado: la dirección del
alumno/a (si se importó en la pestaña Alumnado; si no, queda vacía para escribirla), el asunto, un texto que explica
el documento y pide confirmar la recepción, y el **PDF adjunto**. Solo hay que revisarlo y pulsar **Enviar**:
WebPEC no envía nada por sí mismo. Después, pasar el aviso a Entregados. Si no se usa Thunderbird, en
Configuración se puede elegir «Fichero .eml»: se descarga un borrador por aviso que se abre con el programa de correo.
Para que Thunderbird pueda leer los adjuntos, WebPEC deja una copia en la carpeta personal, en `WebPEC_correo`
(se vacía sola de lo que tenga más de dos días).

**Anular un aviso.** Si un aviso se emitió por error (horas del módulo mal puestas, faltas que después se
justificaron…), se marca y se pulsa **Anular…**. WebPEC pide el **motivo** (obligatorio) y entonces:

- el aviso queda **tachado en el Registro**, con la fecha y el motivo;
- su documento pasa a la bandeja **Anulados** (se puede seguir viendo y descargando);
- como ya no cuenta, si el alumno/a sigue por encima del límite, **el siguiente informe que se procese lo vuelve a
  generar** con los datos correctos.

Una pérdida del 15 % se apoya en su aviso del 7,5 %: para anular el aviso hay que anular antes la pérdida, o las
dos a la vez.

### Alumnado

La situación de cada alumno/a en cada módulo, según el **último informe procesado** de ese módulo: faltas (FI),
porcentaje de horas, umbrales y situación:

- **Sin avisos**: no llega al 7,5 %.
- **Supera el 7,5 % sin aviso**: le corresponde un aviso que no tiene vigente (por ejemplo, porque se anuló); el
  siguiente informe lo generará.
- **Aviso 7,5 %** (con su fecha; indica si ya supera el 15 %) y **Pérdida 15 %**.

Se puede filtrar por grupo, módulo, profesor/a y situación, y buscar por nombre. Se calcula con los informes que se
conservan en «Informes ya procesados»: si se borran, sus módulos desaparecen de esta vista.

**Importar correos…** guarda el correo electrónico de cada alumno/a desde un fichero CSV o Excel (por ejemplo, una
exportación de Raíces o de EducaMadrid) con su nombre y su correo; si el fichero tiene columna de grupo o unidad,
también se usa. Las columnas se reconocen solas y los correos que ya había se actualizan. Los correos se ven en esta
pestaña; **WebPEC no envía nada**.

### Registro

Lista de todos los avisos emitidos: informe, tipo, alumno/a, grupo, módulo, faltas (FI), umbral, profesor/a,
fecha de generación y quién lo generó (y, si se entregó o anuló, cuándo y quién). Tiene un buscador.
Gracias al registro **un aviso nunca se repite**, salvo que se anule. Los avisos anulados aparecen tachados, con
la fecha y el motivo. El enlace **Anular** de cada fila sirve también para avisos cuyo documento ya no existe.
**Vaciar registro** lo deja en blanco (por ejemplo, al empezar un curso nuevo); antes guarda una copia de
seguridad.

**Actividad: quién ha hecho qué** (desplegable al final): cada acción con su fecha y la persona que la hizo
(subir y procesar informes, entregar, anular, cambiar módulos o configuración, importar o exportar datos…).

### Módulos

- **Módulos:** unidad, siglas, nombre del módulo en el informe y en los avisos, horas totales y los umbrales del
  7,5 % y del 15 %. Los módulos nuevos se registran solos al subir su primer informe. Las siglas de un módulo con
  avisos no se pueden cambiar.
- **Profesorado:** nombre tal y como viene en el informe (Raíces lo escribe sin tildes) y nombre correcto para la
  firma. **Añadir profesor/a…** da de alta a alguien que aún no tiene informes (con su nombre y apellidos como en
  Raíces); **Borrar** quita a alguien de la lista (sus avisos no se tocan).
- **Borrar todos los módulos y profesores:** deja la hoja en blanco, con copia de seguridad previa.

### Configuración

- **Centro:** nombre del centro, localidad, Jefatura de Estudios y Dirección (aparecen en los documentos).
- **Documentos:** formato de la fecha en los nombres de fichero (AAAAMMDD, que ordena por fecha, o DDMMAAAA) y
  programa para pasar a PDF (automático, LibreOffice, Word o ninguno) y programa para **enviar por correo**
  (automático, Thunderbird o fichero .eml).
- **Aplicación:** puerto y acceso desde otros ordenadores de la red del centro (se aplican al volver a arrancar).
- **Guardar configuración** para aplicar los cambios.
- **Copia de los datos:**
  - **Exportar datos (ZIP):** descarga todos los datos (registro, módulos, profesorado, informes, avisos, correos y
    actividad) en un solo ZIP. Sirve como copia de seguridad o para llevarlos a otro ordenador.
  - **Importar datos…:** sustituye los datos por los de un ZIP exportado (también de una versión anterior). Antes
    guarda una copia de los datos actuales en `COPIAS_SEGURIDAD`.

### Botón de apagado

Cierra WebPEC de forma ordenada.

## 5. Reglas que aplica WebPEC

- Se cuenta la columna **FI** (faltas injustificadas) del informe.
- Los umbrales son el 7,5 % y el 15 % de las horas lectivas totales del módulo.
- **FI ≥ 7,5 %** y sin aviso previo → **Aviso**, aunque ya supere el 15 %.
- **FI ≥ 15 %**, con aviso en un informe anterior y con más faltas que entonces → **Confirmación de pérdida**.
  Si no ha acumulado más faltas desde el aviso, se espera al siguiente informe.
- Ningún documento se genera dos veces para el mismo alumno, grupo, módulo y tipo.

## 6. Dónde se guardan los datos

Los datos están en la carpeta `DATOS`, dentro de `WebPEC` (fuera de ella solo está el programa):

| Carpeta o fichero | Contenido |
|---|---|
| `INFORMES_NUEVOS/` | PDF subidos a los que aún les faltan datos |
| `INFORMES_FALTAS_PROCESAR/` | Informes listos para procesar, ya renombrados |
| `INFORMES_FALTAS_PROCESADOS/` | Informes ya procesados |
| `AVISOS_PENDIENTES/<profesor>/` | Avisos generados y sin entregar |
| `AVISOS_REALIZADOS/<profesor>/` | Avisos entregados |
| `AVISOS_ANULADOS/<profesor>/` | Avisos anulados |
| `PEC_MODULOS.xlsx` | Módulos y profesorado (si se abre con Excel, cerrarlo antes de usar WebPEC) |
| `registro_avisos.csv` | Registro de avisos emitidos (no borrar filas a mano) |
| `configuracion.ini` | Configuración |
| `COPIAS_SEGURIDAD/` | Copias automáticas antes de vaciar el registro o la hoja de módulos y antes de poner al día los datos de una versión anterior |
| `correos_alumnado.csv` | Correos del alumnado importados |
| `actividad.csv` | Quién ha hecho cada acción y cuándo |
| `VERSION_DATOS`, `migraciones.log` | Formato de los datos e historial de sus actualizaciones |

**Copia de seguridad:** «Exportar datos» (en Configuración) o copiar la carpeta `DATOS` entera.

## 7. Problemas frecuentes

| Problema | Solución |
|---|---|
| No se abre nada al hacer doble clic en `index.html` | Hay que arrancar con `WebPEC.bat` / `WebPEC.sh` o el icono. |
| El navegador dice que no puede conectar | La ventana de terminal se ha cerrado: volver a arrancar WebPEC. |
| Los avisos salen en .docx en lugar de PDF | No hay LibreOffice ni Word, o el conversor elegido en Configuración no está instalado. |
| Error al guardar módulos o profesores | `PEC_MODULOS.xlsx` está abierto en Excel: cerrarlo y repetir. |
| Un alumno no recibe el aviso del 15 % | Necesita el aviso del 7,5 % en un informe anterior y haber acumulado más faltas desde entonces. |
| El icono del escritorio ya no funciona | La carpeta se ha movido: volver a ejecutar el instalador. |
| El instalador se cierra enseguida (Windows) | Se ha abierto desde dentro del ZIP: descomprimirlo antes («Extraer todo»). |
| «Indica quién eres antes de hacer cambios» | Elegir el propio nombre haciendo clic bajo el título de WebPEC. |
| No aparezco en la lista de «¿Quién eres?» | Elegir «Soy nuevo/a» y escribir nombre y apellidos como en Raíces. |
| Al arrancar dice que no puede actualizar los datos | Hay un fichero de datos abierto (Excel, LibreOffice): cerrarlo y volver a arrancar. |
| Un aviso se emitió por error | Anularlo (pestaña Avisos o Registro), indicando el motivo. |
| «Enviar por correo» no abre Thunderbird, o el correo sale sin adjunto | En Configuración, elegir «Fichero .eml» para enviar por correo. |

## 8. Contacto

Dudas, errores o propuestas de mejora: **jose.jimenezcastillo@educa.madrid.org**

## 9. Licencia

WebPEC © 2026 Departamento de Informática del IES Rosa Chacel (Madrid).

Se distribuye con la licencia **Creative Commons Reconocimiento-NoComercial-CompartirIgual 4.0 Internacional
(CC BY-NC-SA 4.0)**: se puede usar, copiar y modificar libremente, citando al autor, sin fines comerciales y
compartiendo las versiones modificadas con la misma licencia.
Resumen: <https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es> · Detalles en `LICENCIA.txt`.

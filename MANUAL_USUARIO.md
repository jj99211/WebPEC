# WebPEC — Manual de usuario

*Avisos de pérdida de evaluación continua · Departamento de Informática · IES Rosa Chacel (Madrid) ·
Manual de la versión 3.40*

---

## 1. Para qué sirve

WebPEC prepara los documentos de **pérdida de evaluación continua** del alumnado de FP a partir de los
listados de faltas que se descargan de Raíces. El profesorado solo tiene que subir los informes: la aplicación
calcula quién ha superado los límites de faltas y rellena los documentos oficiales.

Genera dos tipos de documento:

| Documento | Cuándo se genera |
|---|---|
| **Aviso (7,5 %)** | El alumno/a tiene faltas por encima del 7,5 % de las horas del módulo y todavía no se le había avisado. |
| **Confirmación de pérdida (15 %)** | El alumno/a supera el 15 %, ya recibió el aviso en un informe anterior y desde entonces ha acumulado más faltas. |

Los documentos salen rellenos con el nombre del alumno/a, el grupo, el módulo, la fecha del informe y las firmas
del profesor/a y de Jefatura de Estudios. WebPEC **no entrega** nada: la entrega la hace cada profesor/a, en
persona o por correo, y después la anota en la aplicación.

Qué faltas cuentan lo decide cada módulo: la normativa suma las **injustificadas y las justificadas** (FI + FJ), y
un módulo puede contar **solo las injustificadas** (FI). Ver «Faltas que cuentan», en el apartado 5.

Todo el departamento usa la misma instalación y ve los avisos de todos.

> **Uso interno del IES Rosa Chacel.** WebPEC está hecha para el profesorado de este instituto, con sus modelos de
> documentos, sus cargos y sus criterios. No está pensada ni preparada para otros centros.

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

**Descargar WebPEC:** la última versión está siempre en <https://github.com/jj99211/WebPEC/releases/latest>
(fichero `WebPEC_vX.YY.zip`, no el «Source code»).

**Actualizar a una versión nueva.** Al abrir WebPEC, si hay una versión más moderna publicada, aparece un aviso
arriba: **«Hay una versión nueva de WebPEC»**, con un enlace a sus novedades y dos botones:

- **Actualizar ahora:** WebPEC descarga la versión nueva, se cierra unos segundos, la instala en su misma carpeta
  (el icono no cambia) y vuelve a abrirse en la misma pestaña. Los datos no se tocan; antes se guarda una copia del
  programa actual en `DATOS/COPIAS_SEGURIDAD/programa_vX.YY_…`, por si hubiera que volver atrás. Mientras tanto no
  hay que cerrar la ventana de terminal. Si algo falla, sigue funcionando la versión que había y WebPEC lo explica.
- **Más tarde:** el aviso desaparece hasta la próxima vez que se abra WebPEC.

También se puede actualizar a mano, como se instala: descomprimir el ZIP nuevo en cualquier sitio y ejecutar su
instalador; con Intro elige «Actualizar la instalación que ya hay». Si WebPEC está abierto, el instalador pide
cerrarlo (botón de apagado) antes de copiar nada.

Para saber si hay versión nueva, WebPEC solo consulta en GitHub cuál es la última publicada: **no envía ningún
dato**. Sin Internet, simplemente no avisa. Se puede desactivar en Configuración.

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
   que le faltan (horas totales, siglas y **faltas que cuentan** del módulo, nombre del profesor/a tal y como debe
   ir en la firma) y
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
  muestra un resumen con los avisos creados y las faltas de cada alumno/a (FI y FJ; entre paréntesis, las FJ
  que en ese módulo no cuentan).
- **Informes ya procesados** (desplegable): histórico de informes.
- **Borrar todos los informes procesados:** borra los PDF de Raíces ya procesados (no afecta a los avisos ni al
  registro).

### Avisos

- **Pendientes de entregar / Entregados / Anulados:** cambia entre las tres bandejas. En Entregados y Anulados
  se ve cuándo y quién lo hizo.
- **Filtros:** por profesor/a, por tipo (7,5 % o 15 %) y búsqueda por alumno, grupo o módulo.
- **Faltas:** las faltas injustificadas (FI) y justificadas (FJ) con las que se generó cada aviso.
- **Simular con el otro criterio:** ver «Faltas que cuentan», en el apartado 5.
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

La situación de cada alumno/a en cada módulo, según el **último informe procesado** de ese módulo: faltas
injustificadas (FI) y justificadas (FJ; entre paréntesis si en ese módulo no cuentan), porcentaje de horas (con las
faltas que cuentan en el módulo), umbrales y situación:

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

En cada fila:

- **Editar**: corrige a mano el nombre (apellidos y nombre) o el correo del alumno/a. El nombre corregido se usa en
  los listados, en los correos y en los avisos que se generen a partir de entonces (los ya generados no cambian);
  los informes de Raíces se siguen reconociendo con el nombre original.
- **Baja**: para quien sigue saliendo en los informes de Raíces pero ya no cursa uno o varios módulos (baja en el
  centro, anulación de matrícula, convalidación…). Se marcan los módulos (el de la fila viene marcado) o **Todos sus
  módulos del grupo**, que vale también para los módulos de informes futuros (baja en el centro). En esos módulos
  desaparece de la lista y **no vuelve a recibir avisos**, aunque siga en los informes; en los demás, todo sigue
  igual. Se puede anotar el motivo. Sus avisos ya generados y el registro se conservan: si le quedan avisos de esos
  módulos en Pendientes, WebPEC lo indica para anularlos si ya no se van a entregar.

**Informe para la evaluación…** prepara el listado para llevar a la **sesión de evaluación**: se elige un grupo (o
todos, uno por página) y sale una tabla con cada alumno/a en filas y cada módulo en columnas. En cada casilla, las
faltas injustificadas y justificadas, el porcentaje de horas y la situación (aviso del 7,5 % o pérdida del 15 % con su fecha, «≥ 7,5 %
sin aviso» o baja en ese módulo), coloreada para verla de un vistazo; al final de cada fila, cuántos avisos y pérdidas
tiene. Encima, el resumen del grupo, y debajo, los módulos (profesor/a, horas, umbrales, fecha del último informe y
faltas que cuentan) y
el alumnado dado de baja. Dos formatos:

- **Ver e imprimir**: se abre en otra pestaña del navegador, lista para **imprimir o guardar en PDF** (en horizontal).
- **Descargar Excel**: un fichero `.xlsx` con una hoja por grupo, para retocarlo o añadir columnas.

Se calcula con el último informe procesado de cada módulo: conviene procesar antes los informes más recientes.

Al final de la pestaña, **Alumnado dado de baja** lista las bajas (módulo o «Todos los módulos», fecha, quién la dio y
motivo); **Recuperar** deshace una baja dada por error.

### Registro

Lista de todos los avisos emitidos: informe, tipo, alumno/a, grupo, módulo, faltas (FI y FJ; en los avisos de
antes de la 3.40 no se guardaban las FJ), umbral, profesor/a,
fecha de generación y quién lo generó (y, si se entregó o anuló, cuándo y quién). Tiene un buscador.
Gracias al registro **un aviso nunca se repite**, salvo que se anule. Los avisos anulados aparecen tachados, con
la fecha y el motivo. El enlace **Anular** de cada fila sirve también para avisos cuyo documento ya no existe.
**Vaciar registro** lo deja en blanco (por ejemplo, al empezar un curso nuevo); antes guarda una copia de
seguridad.

**Actividad: quién ha hecho qué** (desplegable al final): cada acción con su fecha y la persona que la hizo
(subir y procesar informes, entregar, anular, cambiar módulos o configuración, importar o exportar datos…).

### Módulos

- **Módulos:** unidad, siglas, nombre del módulo en el informe y en los avisos, horas totales, los umbrales del
  7,5 % y del 15 % y las **faltas que cuentan** («Solo FI» o «FI + FJ»). Los módulos nuevos se registran solos al
  subir su primer informe. Las siglas de un módulo con avisos no se pueden cambiar. Al cambiar las faltas que
  cuentan y pulsar **Guardar**, WebPEC dice antes cuántos avisos nuevos saldrían con el último informe.
- **Profesorado:** nombre tal y como viene en el informe (Raíces lo escribe sin tildes) y nombre correcto para la
  firma. **Añadir profesor/a…** da de alta a alguien que aún no tiene informes (con su nombre y apellidos como en
  Raíces); **Borrar** quita a alguien de la lista (sus avisos no se tocan).
- **Borrar todos los módulos y profesores:** deja la hoja en blanco, con copia de seguridad previa.

### Configuración

- **Centro:** nombre del centro, localidad, Jefatura de Estudios y Dirección (aparecen en los documentos).
- **Documentos:** formato de la fecha en los nombres de fichero (AAAAMMDD, que ordena por fecha, o DDMMAAAA) y
  programa para pasar a PDF (automático, LibreOffice, Word o ninguno) y programa para **enviar por correo**
  (automático, Thunderbird o fichero .eml).
- **Aplicación:** puerto y acceso desde otros ordenadores de la red del centro (se aplican al volver a arrancar) y
  **buscar versiones nuevas al abrir** (sí o no). **Comprobar ahora** mira en ese momento si hay versión nueva.
- **Guardar configuración** para aplicar los cambios.
- **Copia de los datos:**
  - **Exportar datos (ZIP):** descarga todos los datos (registro, módulos, profesorado, informes, avisos, correos y
    actividad) en un solo ZIP. Sirve como copia de seguridad o para llevarlos a otro ordenador.
  - **Importar datos…:** sustituye los datos por los de un ZIP exportado (también de una versión anterior). Antes
    guarda una copia de los datos actuales en `COPIAS_SEGURIDAD`.

### Botón de apagado

Cierra WebPEC de forma ordenada.

## 5. Reglas que aplica WebPEC

- Se cuentan las faltas del informe de Raíces según el criterio del módulo: **FI + FJ** (injustificadas más
  justificadas, como pide la normativa) o **solo FI** (injustificadas).
- Los umbrales son el 7,5 % y el 15 % de las horas lectivas totales del módulo.
- **Faltas ≥ 7,5 %** y sin aviso previo → **Aviso**, aunque ya supere el 15 %.
- **Faltas ≥ 15 %**, con aviso en un informe anterior y con más faltas que entonces (contadas con el mismo
  criterio) → **Confirmación de pérdida**. Si no ha acumulado más faltas desde el aviso, se espera al siguiente
  informe.
- Ningún documento se genera dos veces para el mismo alumno, grupo, módulo y tipo.
- El alumnado dado de baja en un módulo (pestaña Alumnado) no recibe avisos nuevos en ese módulo.

### Faltas que cuentan

La normativa dice que, para la pérdida de la evaluación continua, cuentan **todas las faltas**: las injustificadas
(FI) y las justificadas (FJ). Algunos profesores prefieren ser más flexibles y contar solo las injustificadas. Por
eso cada módulo tiene su criterio:

- **FI + FJ** (el de la normativa): es el que viene marcado al dar de alta un módulo nuevo.
- **Solo FI**: el que usaban todos los módulos hasta la versión 3.40. Los módulos que ya existían conservan este
  criterio al actualizar, para que nada cambie hasta que su profesor/a lo decida.

**Simular antes de decidir.** En la pestaña **Avisos**, la casilla **Simular con el otro criterio** muestra, para cada
módulo, cómo quedarían los porcentajes con el otro criterio y qué avisos saldrían, con el último informe procesado y
como si llegara un informe nuevo con las mismas faltas. **No genera ni guarda nada.** El alumnado al que le cambia el
resultado sale resaltado en azul. Desde ahí mismo, **Pasar a «…»** cambia el criterio de ese módulo (también se puede
hacer en la pestaña Módulos).

**Qué pasa al cambiar el criterio:**

- Los avisos ya emitidos **no cambian**; cada uno guarda las FI y FJ y el criterio con el que se hizo.
- El criterio nuevo se aplica desde el **siguiente informe que se procese**; antes de cambiarlo, WebPEC dice cuántos
  avisos nuevos saldrían.
- Al pasar a FI + FJ pueden salir avisos nuevos del 7,5 %: alumnado que, según la normativa, ya supera el límite.
- La pérdida del 15 % **sigue exigiendo** un aviso del 7,5 % en un informe anterior y más faltas desde entonces:
  nadie pierde la evaluación continua solo por cambiar el criterio. Si el aviso es de antes de la 3.40 (cuando no se
  guardaban las FJ), se comparan solo las faltas injustificadas.
- Al pasar a «solo FI», un alumno/a avisado puede quedar por debajo del 15 %: su aviso sigue siendo válido, pero la
  pérdida solo saldrá si supera el 15 % con el criterio nuevo.

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
| `PEC_MODULOS.xlsx` | Módulos (con las faltas que cuentan en cada uno) y profesorado (si se abre con Excel, cerrarlo antes de usar WebPEC) |
| `registro_avisos.csv` | Registro de avisos emitidos (no borrar filas a mano) |
| `configuracion.ini` | Configuración |
| `COPIAS_SEGURIDAD/` | Copias automáticas antes de vaciar el registro o la hoja de módulos, antes de poner al día los datos de una versión anterior y del programa antes de actualizarlo (`programa_vX.YY_…`, las tres últimas) |
| `alumnado.csv` | Correos del alumnado y nombres corregidos a mano |
| `bajas_alumnado.csv` | Alumnado dado de baja (por módulo o en todos los de su grupo) |
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
| «Actualizar ahora» dice que no puede descargar | Sin Internet o con un proxy que lo impide: descargar el ZIP a mano desde GitHub y ejecutar su instalador. |
| Tras actualizar hay que volver a la versión anterior | La copia del programa anterior está en `DATOS/COPIAS_SEGURIDAD/programa_vX.YY_…`: copiar su contenido sobre la carpeta de WebPEC (con WebPEC cerrado). Si la versión nueva puso al día los datos, sus datos anteriores están en el ZIP `…_antes_de_migrar_datos_…` de la misma carpeta. |
| Un módulo cuenta faltas que no quiero (o no cuenta las justificadas) | Pestaña Módulos, columna «Faltas»: «Solo FI» o «FI + FJ». Antes, «Simular con el otro criterio» en Avisos. |

## 8. Contacto

Dudas, errores o propuestas de mejora: **jose.jimenezcastillo@educa.madrid.org**

## 9. Licencia

WebPEC © 2026 Departamento de Informática del IES Rosa Chacel (Madrid).

Se distribuye con la licencia **Creative Commons Reconocimiento-NoComercial-CompartirIgual 4.0 Internacional
(CC BY-NC-SA 4.0)**: se puede usar, copiar y modificar libremente, citando al autor, sin fines comerciales y
compartiendo las versiones modificadas con la misma licencia.
Resumen: <https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es> · Detalles en `LICENCIA.txt`.

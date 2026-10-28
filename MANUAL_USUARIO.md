# WebPEC — Manual de usuario

*Avisos de pérdida de evaluación continua · Departamento de Informática · IES Rosa Chacel (Madrid)*
*Manual de la versión 2.04*

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

## 2. Puesta en marcha

**Requisitos:** Python 3.9 o posterior (en Windows, al instalarlo, marcar «Add Python to PATH»). Para que los
avisos salgan en PDF hace falta LibreOffice o Microsoft Word; sin ninguno de los dos se generan en Word (.docx).

**Arrancar:**

- **Windows:** doble clic en `WebPEC.bat`.
- **Linux:** doble clic en `WebPEC.sh` (si el explorador pregunta, elegir «Ejecutar»).
- **Icono en el escritorio** (solo la primera vez): doble clic en `Crear_acceso_directo.bat` (Windows) o
  `Crear_acceso_directo.sh` (Linux). Después basta con el icono «WebPEC» con el escudo del instituto.

Se abre una ventana de terminal y el navegador con la aplicación (`http://localhost:8765`). **La ventana de
terminal tiene que seguir abierta** mientras se usa WebPEC; en Windows queda minimizada en la barra de tareas.

> Abrir `web/index.html` con doble clic **no funciona**: hay que entrar siempre con el lanzador o el icono.

**Cerrar:** botón de apagado (arriba a la derecha). Aparece la pantalla «WebPEC se ha cerrado» y ya se puede
cerrar la pestaña.

## 3. Uso habitual paso a paso

1. **Descargar de Raíces** el «Listado de faltas totales» de cada grupo y módulo, en PDF. El nombre del fichero
   da igual.
2. Abrir WebPEC y, en la pestaña **Informes**, **arrastrar los PDF** a la zona de subida (o hacer clic en ella
   para elegirlos).
3. Revisar la lista de *Informes pendientes de procesar*: muestra el nombre que recibirá cada informe
   (`FECHA_GRUPO_MÓDULO_Faltas.pdf`).
4. Pulsar **Procesar informes**. Si es la primera vez que aparece un módulo o un profesor/a, WebPEC pide los datos
   que le faltan (horas totales y siglas del módulo, nombre del profesor/a tal y como debe ir en la firma) y
   después continúa sola.
5. Ir a **Avisos → Pendientes de entregar**, marcar los avisos e **Imprimir** (salen todos juntos en un PDF) o
   **Descargar ZIP**.
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

- **Pendientes de entregar / Entregados:** cambia entre las dos bandejas.
- **Filtros:** por profesor/a, por tipo (7,5 % o 15 %) y búsqueda por alumno, grupo o módulo.
- **Casillas de selección:** al marcar uno o varios avisos aparece una barra inferior con:
  - **Imprimir:** une los avisos marcados en un solo PDF y abre la impresión.
  - **Descargar ZIP:** descarga los documentos marcados.
  - **Marcar como entregados** (en la bandeja de entregados, **Volver a pendientes**).
  - **Borrar:** elimina los documentos marcados.
- **Entregado** (en cada fila): pasa ese aviso a la bandeja de entregados.
- Al pasar avisos a Entregados, WebPEC pide marcar «Confirmo que se han entregado».
- **Borrar avisos…:** borra de una vez los pendientes, los entregados o todos.

> **Importante:** borrar un aviso elimina el documento, pero el aviso **sigue anotado en el Registro** y WebPEC no
> lo vuelve a generar. Usar «Borrar» solo para pruebas o duplicados.

### Registro

Lista de todos los avisos emitidos: informe, tipo, alumno/a, grupo, módulo, faltas (FI), umbral, profesor/a y
fecha de generación. Tiene un buscador.
Gracias al registro **un aviso nunca se repite**.
**Vaciar registro** lo deja en blanco (por ejemplo, al empezar un curso nuevo); antes guarda una copia de
seguridad.

### Módulos

- **Módulos:** unidad, siglas, nombre del módulo en el informe y en los avisos, horas totales y los umbrales del
  7,5 % y del 15 %. Los módulos nuevos se registran solos al subir su primer informe. Las siglas de un módulo con
  avisos no se pueden cambiar.
- **Profesorado:** nombre tal y como viene en el informe (Raíces lo escribe sin tildes) y nombre correcto para la
  firma.
- **Borrar todos los módulos y profesores:** deja la hoja en blanco, con copia de seguridad previa.

### Configuración

- **Centro:** nombre del centro, localidad, Jefatura de Estudios y Dirección (aparecen en los documentos).
- **Documentos:** formato de la fecha en los nombres de fichero (AAAAMMDD, que ordena por fecha, o DDMMAAAA) y
  programa para pasar a PDF (automático, LibreOffice, Word o ninguno).
- **Aplicación:** puerto y acceso desde otros ordenadores de la red del centro (se aplican al volver a arrancar).
- **Guardar configuración** para aplicar los cambios.

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

Todo queda dentro de la carpeta `WebPEC`:

| Carpeta o fichero | Contenido |
|---|---|
| `INFORMES_NUEVOS/` | PDF subidos a los que aún les faltan datos |
| `INFORMES_FALTAS_PROCESAR/` | Informes listos para procesar, ya renombrados |
| `INFORMES_FALTAS_PROCESADOS/` | Informes ya procesados |
| `AVISOS_PENDIENTES/<profesor>/` | Avisos generados y sin entregar |
| `AVISOS_REALIZADOS/<profesor>/` | Avisos entregados |
| `PEC_MODULOS.xlsx` | Módulos y profesorado (si se abre con Excel, cerrarlo antes de usar WebPEC) |
| `registro_avisos.csv` | Registro de avisos emitidos (no borrar filas a mano) |
| `configuracion.ini` | Configuración |
| `COPIAS_SEGURIDAD/` | Copias automáticas antes de vaciar el registro o la hoja de módulos |

**Copia de seguridad:** basta con copiar la carpeta `WebPEC` entera.

## 7. Problemas frecuentes

| Problema | Solución |
|---|---|
| No se abre nada al hacer doble clic en `index.html` | Hay que arrancar con `WebPEC.bat` / `WebPEC.sh` o el icono. |
| El navegador dice que no puede conectar | La ventana de terminal se ha cerrado: volver a arrancar WebPEC. |
| Los avisos salen en .docx en lugar de PDF | No hay LibreOffice ni Word, o el conversor elegido en Configuración no está instalado. |
| Error al guardar módulos o profesores | `PEC_MODULOS.xlsx` está abierto en Excel: cerrarlo y repetir. |
| Un alumno no recibe el aviso del 15 % | Necesita el aviso del 7,5 % en un informe anterior y haber acumulado más faltas desde entonces. |
| El icono del escritorio ya no funciona | La carpeta se ha movido: volver a ejecutar `Crear_acceso_directo`. |

## 8. Contacto

Dudas, errores o propuestas de mejora: **jose.jimenezcastillo@educa.madrid.org**

(c) Departamento de Informática · IES Rosa Chacel · Madrid

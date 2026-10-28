"""
Motor de WebPEC: lectura de los informes de faltas, hoja de módulos, registro de avisos y
generación de los documentos de pérdida de evaluación continua (PEC).

Es la lógica de avisos_PEC.py sin preguntas por teclado: lo que falta (horas de un módulo,
firma de un profesor) se devuelve como dato pendiente para que lo pida la interfaz web.

Datos (en DATOS/, dentro de la carpeta del programa; se crean solos si no existen):
  INFORMES_NUEVOS/               PDF subidos, con cualquier nombre
  INFORMES_FALTAS_PROCESAR/      informes con todos los datos, renombrados a FECHA_GRUPO_MODULO_Faltas.pdf
  INFORMES_FALTAS_PROCESADOS/    informes ya procesados
  AVISOS_PENDIENTES/<profesor>/  documentos generados
  AVISOS_REALIZADOS/<profesor>/  documentos ya entregados
  AVISOS_ANULADOS/<profesor>/    documentos anulados
  COPIAS_SEGURIDAD/              copias antes de vaciar el registro o la hoja y antes de migrar los datos
  VERSION_DATOS                  formato de los datos (lo pone al día migrar_datos al arrancar)
  actividad.csv                  quién ha hecho cada acción y cuándo
  alumnado.csv                   correos del alumnado y nombres corregidos a mano
  bajas_alumnado.csv             alumnado dado de baja en un módulo o en todos los de su grupo

Reglas (valor de referencia: columna FI, faltas injustificadas):
  - FI >= 7,5 % de las horas y sin aviso previo -> FECHA_AVISO_PEC_GRUPO_MOD_Apellido_Nombre.pdf
    (aunque ya supere el 15 %: primero siempre se avisa).
  - FI >= 15 %, con aviso emitido en un informe anterior y con más faltas que
    cuando se avisó                            -> FECHA_PEC_GRUPO_MOD_Apellido_Nombre.pdf
"""

import configparser
import csv
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path, PurePosixPath
from xml.sax.saxutils import escape

PROGRAMA = Path(__file__).resolve().parent

# Librerías incluidas en la carpeta lib/; si no están, se usan las instaladas en el sistema
sys.path.insert(0, str(PROGRAMA / "lib"))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

logging.getLogger("pypdf").setLevel(logging.ERROR)

CONFIGURACION = "configuracion.ini"
HOJA_MODULOS = "PEC_MODULOS.xlsx"
REGISTRO = "registro_avisos.csv"
PLANTILLAS = "plantillas"
PLANTILLA_AVISO = "Aviso_perdida_evaluacion_continua_GM_y_GS__7_5_.docx"
PLANTILLA_PEC = "Confirmacion_perdida_evaluacion_continua_15_.docx"
NUEVOS = "INFORMES_NUEVOS"
PROCESAR = "INFORMES_FALTAS_PROCESAR"
PROCESADOS = "INFORMES_FALTAS_PROCESADOS"
PENDIENTES = "AVISOS_PENDIENTES"
REALIZADOS = "AVISOS_REALIZADOS"
ANULADOS = "AVISOS_ANULADOS"
COPIAS = "COPIAS_SEGURIDAD"
DATOS = "DATOS"
VERSION_DATOS = "VERSION_DATOS"
LOG_MIGRACIONES = "migraciones.log"
ACTIVIDAD = "actividad.csv"
ALUMNADO = "alumnado.csv"
BAJAS = "bajas_alumnado.csv"
CORREOS_4 = "correos_alumnado.csv"  # el fichero de correos del formato de datos 4

# Formato de los datos. 2: WebPEC 2.x (datos sueltos en la carpeta del programa);
# 3: carpeta DATOS/ y registro con anulaciones; 4: registro con quién genera, entrega y anula.
FORMATO_DATOS = 6
# Lo que en la 2.x estaba en la carpeta del programa y en la 3 va dentro de DATOS/
DATOS_2X = [CONFIGURACION, HOJA_MODULOS, REGISTRO, NUEVOS, PROCESAR, PROCESADOS,
            PENDIENTES, REALIZADOS, COPIAS]

# Nombres que vienen escritos en las plantillas y se sustituyen por los de configuracion.ini
JEFATURA_PLANTILLA = "Irene Rodil Jiménez"
DIRECCION_PLANTILLA = "LUISA CAPELL SÁNCHEZ-RUBIO"

# Formatos de fecha admitidos para los nombres de fichero
FORMATOS_FECHA = {"AAAAMMDD": "%Y%m%d", "DDMMAAAA": "%d%m%Y"}
CONVERSORES = ["auto", "libreoffice", "word", "ninguno"]
# Programa de correo: auto (Thunderbird si está instalado; si no, fichero .eml), thunderbird o eml
PROGRAMAS_CORREO = ["auto", "thunderbird", "eml"]
# Carpeta personal donde se dejan el PDF y el texto de cada correo para el programa de correo
# (Thunderbird instalado como snap en Linux no puede leer /tmp ni otros discos)
CARPETA_CORREO = Path.home() / "WebPEC_correo"

CONFIGURACION_DEFECTO = {
    "centro": "IES Rosa Chacel",
    "localidad": "Madrid",
    "jefatura_estudios": "Irene Rodil Jiménez",
    "direccion": "Luisa Capell Sánchez-Rubio",
    "conversor_pdf": "auto",
    "formato_fecha_fichero": "AAAAMMDD",
    "programa_correo": "auto",
    "puerto": "8765",
    "acceso_red": "no",
}

PLANTILLA_CONFIGURACION = """\
[centro]
centro = {centro}
localidad = {localidad}
jefatura_estudios = {jefatura_estudios}
direccion = {direccion}

[documentos]
; auto: LibreOffice si está instalado; si no, Microsoft Word (solo Windows);
; si no hay ninguno, los avisos se dejan en .docx.
; Valores posibles: auto, libreoffice, word, ninguno
conversor_pdf = {conversor_pdf}
; Fecha al principio de los nombres de fichero: AAAAMMDD (se ordenan por fecha) o DDMMAAAA
formato_fecha_fichero = {formato_fecha_fichero}

[correo]
; Programa para «Enviar por correo»: auto (Thunderbird si está instalado; si no, se descarga un
; fichero .eml para abrirlo con el programa de correo), thunderbird o eml
programa_correo = {programa_correo}

[servidor]
; Puerto de la aplicación web: http://localhost:<puerto>
puerto = {puerto}
; si: se puede abrir desde otros ordenadores de la red (http://<este ordenador>:<puerto>)
; no: solo desde este ordenador
acceso_red = {acceso_red}
"""

AVISO, PEC = "AVISO_PEC", "PEC"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
PARTICULAS = {"de", "del", "la", "las", "los", "y", "san", "da", "do", "dos", "van", "von"}

PATRON_INFORME = re.compile(r"^\d{8}_[^_]+_[^_]+_Faltas\.pdf$", re.IGNORECASE)
# Nombre del alumno seguido de las columnas FJ FI R F R
PATRON_ALUMNO = re.compile(r"^\s*(\S.*?)\s{2,}(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")

# Ancho útil de las plantillas (A4 con márgenes de 2,5 cm), en twips
ANCHO_TEXTO = 9070

# Hoja de cálculo: columnas de cada pestaña
PESTANA_MODULOS = "MODULOS"
COLUMNAS_MODULOS = ["Unidad", "Siglas", "Módulo en el informe", "Nombre del módulo en los avisos",
                    "Profesor/a", "Total horas", "7,5%", "15%"]
PESTANA_PROFESORES = "PROFESORES"
COLUMNAS_PROFESORES = ["Profesor/a en el informe", "Nombre para la firma"]


class ErrorPEC(Exception):
    """Error que se muestra tal cual al usuario."""


class ErrorInforme(ErrorPEC):
    pass


def sin_acentos(texto):
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar(texto):
    return re.sub(r"\s+", " ", sin_acentos(str(texto))).strip().lower()


def a_numero(valor):
    return float(str(valor).replace(",", ".").strip())


def formato_umbral(valor):
    return f"{valor:g}".replace(".", ",")


def para_fichero(texto):
    return re.sub(r"[^A-Za-z0-9]+", "_", sin_acentos(texto)).strip("_")


def texto_fecha(f):
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


# ------------------------------------------------------- configuración ---

def leer_configuracion(base):
    ruta = base / CONFIGURACION
    valores = dict(CONFIGURACION_DEFECTO)
    if ruta.exists():
        config = configparser.ConfigParser(inline_comment_prefixes=(";",))
        config.read(ruta, encoding="utf-8")
        for seccion in config.sections():
            for clave, valor in config.items(seccion):
                if clave in valores:
                    valores[clave] = valor.strip()
    valores["conversor_pdf"] = valores["conversor_pdf"].lower()
    if valores["conversor_pdf"] not in CONVERSORES:
        valores["conversor_pdf"] = "auto"
    valores["formato_fecha_fichero"] = valores["formato_fecha_fichero"].upper()
    if valores["formato_fecha_fichero"] not in FORMATOS_FECHA:
        valores["formato_fecha_fichero"] = "AAAAMMDD"
    valores["programa_correo"] = valores["programa_correo"].lower()
    if valores["programa_correo"] not in PROGRAMAS_CORREO:
        valores["programa_correo"] = "auto"
    return valores


def guardar_configuracion(base, nuevos):
    valores = leer_configuracion(base)
    for clave in valores:
        if clave in nuevos:
            valores[clave] = re.sub(r"[\r\n]+", " ", str(nuevos[clave])).strip()
    if valores["conversor_pdf"] not in CONVERSORES:
        raise ErrorPEC(f"Conversor no válido: {valores['conversor_pdf']}")
    if valores["formato_fecha_fichero"] not in FORMATOS_FECHA:
        raise ErrorPEC(f"Formato de fecha no válido: {valores['formato_fecha_fichero']}")
    if valores["programa_correo"] not in PROGRAMAS_CORREO:
        raise ErrorPEC(f"Programa de correo no válido: {valores['programa_correo']}")
    if not valores["puerto"].isdigit():
        raise ErrorPEC("El puerto debe ser un número")
    (base / CONFIGURACION).write_text(PLANTILLA_CONFIGURACION.format(**valores), encoding="utf-8")
    return valores


def fecha_fichero(config, f):
    return f.strftime(FORMATOS_FECHA[config["formato_fecha_fichero"]])


# ----------------------------------------------------- hoja de módulos ---

def crear_hoja_modulos(ruta):
    libro = Workbook()
    for i, (titulo, columnas, anchos) in enumerate([
            (PESTANA_MODULOS, COLUMNAS_MODULOS, [10, 8, 45, 45, 32, 12, 8, 8]),
            (PESTANA_PROFESORES, COLUMNAS_PROFESORES, [40, 40])]):
        hoja = libro.active if i == 0 else libro.create_sheet()
        hoja.title = titulo
        hoja.append(columnas)
        for celda, ancho in zip(hoja[1], anchos):
            celda.font = Font(bold=True)
            celda.fill = PatternFill("solid", fgColor="DDEBF7")
            hoja.column_dimensions[celda.column_letter].width = ancho
        hoja.freeze_panes = "A2"
    libro.save(ruta)


class HojaModulos:
    """PEC_MODULOS.xlsx: módulos con sus horas y umbrales, y nombres de los profesores."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.modulos = []
        self.profesores = {}  # nombre normalizado del informe -> (fila, nombre informe, firma)
        self.errores = []
        libro = load_workbook(ruta)
        hoja = libro[PESTANA_MODULOS]
        for n, fila in enumerate(hoja.iter_rows(min_row=2, values_only=True), start=2):
            if not fila or not fila[0] or not fila[2]:
                continue
            unidad, siglas, en_informe, en_avisos, profesor, horas = (list(fila) + [None] * 6)[:6]
            try:
                horas = a_numero(horas)
            except (TypeError, ValueError):
                self.errores.append(f"El módulo «{en_informe}» ({unidad}) no tiene un número de "
                                    f"horas válido en {HOJA_MODULOS}")
                continue
            self.modulos.append({
                "fila": n, "unidad": str(unidad).strip(), "siglas": str(siglas or "").strip(),
                "en_informe": str(en_informe).strip(),
                "nombre": str(en_avisos or en_informe).strip(),
                "profesor": str(profesor or "").strip(), "horas": horas,
                "umbral_75": horas * 0.075, "umbral_15": horas * 0.15,
            })
        for n, fila in enumerate(libro[PESTANA_PROFESORES].iter_rows(min_row=2, values_only=True),
                                 start=2):
            if fila and fila[0]:
                self.profesores[normalizar(fila[0])] = (n, str(fila[0]).strip(),
                                                        str(fila[1] or fila[0]).strip())

    def buscar_modulo(self, unidad, nombre_informe):
        for m in self.modulos:
            if normalizar(m["unidad"]) == normalizar(unidad) and \
                    normalizar(m["en_informe"]) == normalizar(nombre_informe):
                return m
        return None

    def firma(self, profesor_informe):
        dato = self.profesores.get(normalizar(profesor_informe))
        return dato[2] if dato else None

    def siglas_usadas(self, unidad, salvo_fila=None):
        return {normalizar(m["siglas"]) for m in self.modulos
                if normalizar(m["unidad"]) == normalizar(unidad) and m["fila"] != salvo_fila}

    def _guardar(self, cambiar):
        libro = load_workbook(self.ruta)
        cambiar(libro)
        # Fórmulas de los umbrales, rehechas por si se han borrado filas
        hoja = libro[PESTANA_MODULOS]
        for n in range(2, hoja.max_row + 1):
            if hoja.cell(n, 1).value:
                hoja.cell(n, 7).value = f"=F{n}*0.075"
                hoja.cell(n, 8).value = f"=F{n}*0.15"
        try:
            libro.save(self.ruta)
        except PermissionError:
            raise ErrorPEC(f"No se puede guardar {HOJA_MODULOS}: ciérrala en Excel o LibreOffice "
                           f"y vuelve a intentarlo")
        self.__init__(self.ruta)

    def anadir_modulo(self, unidad, siglas, en_informe, nombre, profesor, horas):
        self._guardar(lambda libro: libro[PESTANA_MODULOS].append(
            [unidad, siglas, en_informe, nombre, profesor, horas]))

    def actualizar_modulo(self, fila, horas, nombre, siglas):
        def cambiar(libro):
            hoja = libro[PESTANA_MODULOS]
            hoja.cell(fila, 2).value = siglas
            hoja.cell(fila, 4).value = nombre
            hoja.cell(fila, 6).value = horas
        self._guardar(cambiar)

    def borrar_modulo(self, fila):
        self._guardar(lambda libro: libro[PESTANA_MODULOS].delete_rows(fila))

    def cambiar_nombre_informe(self, profesor_informe, nuevo):
        dato = self.profesores.get(normalizar(profesor_informe))
        if dato:
            def cambiar(libro):
                libro[PESTANA_PROFESORES].cell(dato[0], 1).value = nuevo
            self._guardar(cambiar)

    def borrar_profesor(self, profesor_informe):
        dato = self.profesores.get(normalizar(profesor_informe))
        if dato:
            self._guardar(lambda libro: libro[PESTANA_PROFESORES].delete_rows(dato[0]))

    def guardar_profesor(self, profesor_informe, firma):
        dato = self.profesores.get(normalizar(profesor_informe))

        def cambiar(libro):
            hoja = libro[PESTANA_PROFESORES]
            if dato:
                hoja.cell(dato[0], 2).value = firma
            else:
                hoja.append([profesor_informe, firma])
        self._guardar(cambiar)


def siglas_propuestas(nombre, usadas=()):
    palabras = [p for p in sin_acentos(nombre).split() if len(p) > 2]
    siglas = "".join(p[0] for p in palabras).upper() or "MOD"
    propuesta, n = siglas, 2
    while normalizar(propuesta) in usadas:
        propuesta, n = f"{siglas}{n}", n + 1
    return propuesta


# ----------------------------------------------------------- informes ---

def leer_informe(ruta):
    """Extrae la cabecera del informe de faltas y la lista de alumnos con sus FI."""
    try:
        lector = PdfReader(str(ruta))
        texto = "\n".join(p.extract_text(extraction_mode="layout") or "" for p in lector.pages)
    except Exception as e:
        raise ErrorInforme(f"No se puede leer el PDF ({e})")
    if "LISTADO DE FALTAS" not in texto.upper():
        raise ErrorInforme("No parece un listado de faltas de Raíces")

    def buscar(patron, que):
        m = re.search(patron, texto)
        if not m:
            raise ErrorInforme(f"No se encuentra {que} en el informe")
        return m.group(1).strip()

    informe = {
        "unidad": buscar(r"Unidad:\s*(\S+)", "la unidad"),
        "profesor": buscar(r"Profesor/a:\s*(.+?)(?:\s{2,}|\s*Tutor/a:|\n|$)", "el profesor/a"),
        "modulo": "",
        "alumnos": [],
    }
    m = re.search(r"Fecha\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", texto) or \
        re.search(r"Periodo:.*?-\s*(\d{1,2}/\d{1,2}/\d{4})", texto)
    if not m:
        raise ErrorInforme("No se encuentra la fecha del informe")
    informe["fecha"] = datetime.strptime(m.group(1), "%d/%m/%Y").date()

    for linea in texto.splitlines():
        if "Alumno/a" in linea and "TOTAL" in linea and not informe["modulo"]:
            informe["modulo"] = re.sub(r"\s+", " ", linea.split("Alumno/a", 1)[1]
                                       .rsplit("TOTAL", 1)[0]).strip()
            continue
        m = PATRON_ALUMNO.match(linea)
        if m and m.group(1).strip().upper() != "TOTALES":
            informe["alumnos"].append({"alumno": re.sub(r"\s+", " ", m.group(1)).strip(),
                                       "fi": int(m.group(3))})
    if not informe["modulo"]:
        raise ErrorInforme("No se encuentra el nombre del módulo")
    if not informe["alumnos"]:
        raise ErrorInforme("No se han encontrado alumnos")
    return informe


def separar_nombre(apellidos_nombre):
    """'Aceituno González, Manuel' -> ('Aceituno González', 'Manuel')."""
    if "," in apellidos_nombre:
        apellidos, nombre = apellidos_nombre.split(",", 1)
        return apellidos.strip(), nombre.strip()
    return apellidos_nombre.strip(), ""


def nombre_completo(apellidos_nombre):
    """'Jimenez Castillo, Jose Antonio' -> 'Jose Antonio Jimenez Castillo'."""
    apellidos, nombre = separar_nombre(apellidos_nombre)
    return f"{nombre} {apellidos}".strip()


def primer_apellido(apellidos):
    """Primer apellido, conservando partículas: 'de la Fuente Ruiz' -> 'de la Fuente'."""
    palabras = apellidos.split()
    for i, palabra in enumerate(palabras):
        if palabra.lower() not in PARTICULAS:
            return " ".join(palabras[:i + 1])
    return apellidos


def nombres_cortos(alumnos):
    """Apellido_Nombre para cada alumno; si dos coinciden, se usan todos sus apellidos."""
    cortos = {}
    for a in alumnos:
        apellidos, nombre = separar_nombre(a["alumno"])
        cortos[a["alumno"]] = para_fichero(
            f"{primer_apellido(apellidos)} {nombre.split()[0] if nombre else ''}")
    repetidos = {c for c in cortos.values() if list(cortos.values()).count(c) > 1}
    for alumno, corto in cortos.items():
        if corto in repetidos:
            cortos[alumno] = para_fichero(alumno)
    return cortos


def parecido_nombres(a, b):
    """Parte de las palabras de a que están en b (0 a 1), sin tildes ni mayúsculas."""
    pa, pb = set(clave_alumno(a).split()), set(clave_alumno(b).split())
    return len(pa & pb) / len(pa) if pa else 0


def carpeta_profesor(profesor_informe):
    return para_fichero(profesor_informe)


def glob_literal(nombre):
    """Nombre de fichero para usar en glob sin que [ ] * ? se tomen como comodines."""
    return re.sub(r"([\[\]*?])", r"[\1]", nombre)


# ----------------------------------------------------------- registro ---

# Las columnas solo se añaden al final: así un registro antiguo sigue siendo válido
CAMPOS_REGISTRO = ["fecha_informe", "grupo", "modulo", "nombre_modulo", "profesor", "alumno",
                   "tipo", "faltas_injustificadas", "umbral", "documento", "fecha_proceso",
                   "estado", "fecha_anulacion", "motivo_anulacion",
                   "generado_por", "fecha_entrega", "entregado_por", "anulado_por"]
ANULADO = "anulado"


def leer_registro(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{campo: fila.get(campo) or "" for campo in CAMPOS_REGISTRO}
                for fila in csv.DictReader(f, delimiter=";")]


def escribir_registro(ruta, filas):
    """Reescribe el registro entero (con todas las columnas) a través de un fichero temporal."""
    temporal = ruta.with_name(ruta.name + ".tmp")
    try:
        with open(temporal, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_REGISTRO, delimiter=";", restval="",
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(filas)
        os.replace(temporal, ruta)
    except PermissionError:
        temporal.unlink(missing_ok=True)
        raise ErrorPEC(f"No se puede escribir en {REGISTRO}: ciérralo en Excel y vuelve a intentarlo")


def anotar_registro(ruta, filas):
    escribir_registro(ruta, leer_registro(ruta) + list(filas))


def anulada(fila):
    return fila.get("estado") == ANULADO


def misma_clave(fila, grupo, siglas, alumno):
    return (normalizar(fila["grupo"]), normalizar(fila["modulo"]), fila["alumno"]) == \
        (normalizar(grupo), normalizar(siglas), alumno)


def buscar_en_registro(registro, grupo, siglas, alumno, tipo):
    """Aviso vigente (no anulado) de ese tipo para el alumno en el módulo."""
    for fila in registro:
        if not anulada(fila) and fila["tipo"] == tipo and misma_clave(fila, grupo, siglas, alumno):
            return fila
    return None


# ------------------------------------------------- correos del alumnado ---

PATRON_CORREO = re.compile(r"^[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+$")


def clave_alumno(nombre):
    """Mismo alumno escrito «Apellidos, Nombre» o «Nombre Apellidos», con o sin tildes."""
    return " ".join(sorted(normalizar(nombre).replace(",", " ").split()))


def leer_tabla(nombre, datos):
    """Filas (listas de textos) de un CSV o de la primera hoja de un Excel."""
    if datos[:2] == b"PK" or nombre.lower().endswith((".xlsx", ".xlsm")):
        try:
            libro = load_workbook(io.BytesIO(datos), read_only=True, data_only=True)
        except Exception as e:
            raise ErrorPEC(f"No se puede leer la hoja de cálculo ({e})")
        return [["" if c is None else str(c).strip() for c in fila]
                for fila in libro.worksheets[0].iter_rows(values_only=True)]
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            texto = datos.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    primera = next((l for l in texto.splitlines() if l.strip()), "")
    separador = max(";,\t", key=primera.count)
    return [[c.strip() for c in fila] for fila in csv.reader(io.StringIO(texto), delimiter=separador)]


def extraer_correos(filas):
    """[(grupo, alumno, correo)] de una tabla con cabecera; las columnas se reconocen solas."""
    con_correo = [i for i, f in enumerate(filas) if any(PATRON_CORREO.match(c) for c in f)]
    if not con_correo:
        raise ErrorPEC("No se ha encontrado ninguna columna con correos electrónicos")
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    col_correo = max(range(ancho), key=lambda c: sum(bool(PATRON_CORREO.match(filas[i][c])) for i in con_correo))
    cabecera = [normalizar(c) for c in filas[con_correo[0] - 1]] if con_correo[0] > 0 else [""] * ancho

    def columna(*claves, excluir=()):
        return next((i for i, c in enumerate(cabecera) if i != col_correo and i not in excluir
                     and any(k in c for k in claves)), None)

    col_grupo = columna("grupo", "unidad", "curso")
    col_alumno = columna("alumn", "nombre completo", "apellidos y nombre", "apellidos, nombre")
    col_apellidos = col_nombre = segundo = None
    if col_alumno is None:
        col_apellidos = columna("apellido")
        col_nombre = columna("nombre", excluir=(col_apellidos,))
        segundo = columna("apellido", excluir=(col_apellidos, col_nombre))
    if col_alumno is None and (col_apellidos is None or col_nombre is None):
        # Sin cabecera reconocible: la primera columna con texto que no sea el correo
        col_alumno = next((c for c in range(ancho) if c != col_correo and c != col_grupo and
                           any(re.search(r"[A-Za-zÀ-ÿ]", filas[i][c]) for i in con_correo)), None)
        if col_alumno is None:
            raise ErrorPEC("No se encuentra la columna con el nombre del alumnado")
    resultado = []
    for i in con_correo:
        f = filas[i]
        correo = f[col_correo].strip()
        if not PATRON_CORREO.match(correo):
            continue
        if col_alumno is not None:
            alumno = f[col_alumno]
        else:
            apellidos = " ".join(x for x in (f[col_apellidos], f[segundo] if segundo is not None else "") if x)
            alumno = f"{apellidos}, {f[col_nombre]}"
        alumno = re.sub(r"\s+", " ", alumno).strip(" ,")
        if alumno:
            resultado.append((f[col_grupo].strip() if col_grupo is not None else "", alumno, correo))
    return resultado


# ------------------------------------------------- fichas del alumnado ---
# Una fila por alumno/a y grupo con lo que Raíces no da o da mal: correo y nombre corregido a mano.
# «alumno» es el nombre tal como viene en Raíces (o en el fichero de correos); con grupo vacío, la fila
# vale para cualquier grupo (correos importados sin grupo).

CAMPOS_ALUMNADO = ["grupo", "alumno", "nombre", "correo"]


def leer_alumnado(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{c: (fila.get(c) or "") for c in CAMPOS_ALUMNADO} for fila in csv.DictReader(f, delimiter=";")]


def escribir_tabla(ruta, campos, filas, orden):
    temporal = ruta.with_name(ruta.name + ".tmp")
    try:
        with open(temporal, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(sorted(filas, key=orden))
        os.replace(temporal, ruta)
    except PermissionError:
        raise ErrorPEC(f"No se puede escribir en {ruta.name}: ciérralo en Excel y vuelve a intentarlo")


def escribir_alumnado(ruta, filas):
    escribir_tabla(ruta, CAMPOS_ALUMNADO, filas, lambda f: (f["grupo"], normalizar(f["alumno"])))


# Bajas: una fila por alumno/a, grupo y módulo (siglas); módulo vacío = todos los de su grupo, también los
# de informes futuros.
CAMPOS_BAJAS = ["grupo", "alumno", "modulo", "fecha", "por", "motivo"]


def leer_bajas(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{c: (fila.get(c) or "") for c in CAMPOS_BAJAS} for fila in csv.DictReader(f, delimiter=";")]


def escribir_bajas(ruta, filas):
    escribir_tabla(ruta, CAMPOS_BAJAS, filas, lambda f: (f["grupo"], normalizar(f["alumno"]), f["modulo"]))


def clave_baja(grupo, alumno, siglas=""):
    return clave_ficha(grupo, alumno) + (normalizar(siglas or ""),)


def de_baja(claves, grupo, alumno, siglas):
    """¿Está de baja en ese módulo (o en todos los de su grupo)? claves: {clave_baja} de las bajas."""
    return clave_baja(grupo, alumno, siglas) in claves or clave_baja(grupo, alumno) in claves


def clave_ficha(grupo, alumno):
    return normalizar(grupo or ""), clave_alumno(alumno)


def ficha_de(fichas, grupo, alumno):
    """Datos de un alumno/a en su grupo; nombre y correo pueden venir de una fila sin grupo."""
    propia = fichas.get(clave_ficha(grupo, alumno), {})
    general = fichas.get(clave_ficha("", alumno), {})
    ficha = {c: propia.get(c) or general.get(c, "") for c in ("nombre", "correo")}
    ficha["nombre"] = ficha["nombre"] or alumno
    return ficha


# ------------------------------------------------------ envío por correo ---

def texto_correo(fila, firma, config, alumno=None):
    """Asunto y texto (HTML) del correo que acompaña a un aviso (alumno: nombre corregido, si lo hay)."""
    alumno = nombre_completo(alumno or fila["alumno"])
    modulo, grupo, fecha = fila["nombre_modulo"], fila["grupo"], fecha_legible(fila["fecha_informe"])
    if fila["tipo"] == AVISO:
        asunto = f"Aviso de pérdida de evaluación continua - {modulo} ({grupo})"
        que = (f"el <b>aviso de pérdida de la evaluación continua</b> en el módulo <b>{escape(modulo)}</b> "
               f"({escape(grupo)}): según el informe de faltas del {fecha}, tus faltas injustificadas "
               f"superan el 7,5 % de las horas del módulo")
    else:
        asunto = f"Pérdida de evaluación continua - {modulo} ({grupo})"
        que = (f"la <b>confirmación de la pérdida de la evaluación continua</b> en el módulo "
               f"<b>{escape(modulo)}</b> ({escape(grupo)}): según el informe de faltas del {fecha}, tus "
               f"faltas injustificadas superan el 15 % de las horas del módulo")
    html = (f'<html><head><meta charset="utf-8"></head><body>'
            f"<p>Hola, {escape(alumno)}:</p>"
            f"<p>Te envío adjunto {que}.</p>"
            f"<p>Por favor, responde a este correo para confirmar que lo has recibido.</p>"
            f"<p>Un saludo,<br>{escape(firma)}<br>{escape(config['centro'])}</p></body></html>")
    return asunto, html


def buscar_thunderbird():
    for nombre in ("thunderbird", "thunderbird.exe"):
        if shutil.which(nombre):
            return shutil.which(nombre)
    for raiz in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
        if raiz and (Path(raiz) / "Mozilla Thunderbird" / "thunderbird.exe").exists():
            return str(Path(raiz) / "Mozilla Thunderbird" / "thunderbird.exe")
    return None


def preparar_carpeta_correo():
    """Crea CARPETA_CORREO y borra lo que dejaron los correos de hace más de dos días."""
    CARPETA_CORREO.mkdir(exist_ok=True)
    limite = time.time() - 2 * 24 * 3600
    for fichero in CARPETA_CORREO.iterdir():
        try:
            if fichero.is_file() and fichero.stat().st_mtime < limite:
                fichero.unlink()
        except OSError:
            pass


def abrir_thunderbird(programa, para, asunto, cuerpo, adjunto):
    """Ventana de redacción de Thunderbird con todo preparado. El profesor/a revisa y envía."""
    def valor(texto):  # entre comillas simples para -compose: sin comillas simples dentro
        return str(texto).replace("'", "’")
    campos = [f"to='{valor(para)}'", f"subject='{valor(asunto)}'", f"message='{valor(cuerpo)}'",
              "format='1'", f"attachment='{adjunto.as_uri()}'"]
    opciones = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.DETACHED_PROCESS
    else:
        opciones["start_new_session"] = True
    subprocess.Popen([programa, "-compose", ",".join(campos)], **opciones)


# ---------------------------------------------------- migración de datos ---

def version_datos(datos):
    try:
        return int((datos / VERSION_DATOS).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def copia_antes_de_migrar(datos, origenes, desde):
    """ZIP con todo lo que hay en las carpetas y ficheros de datos, en DATOS/COPIAS_SEGURIDAD/."""
    ficheros = []
    for origen in origenes:
        if origen.is_file():
            ficheros.append((origen, origen.name))
        elif origen.is_dir():
            ficheros += [(f, f"{origen.name}/{f.relative_to(origen).as_posix()}")
                         for f in sorted(origen.rglob("*")) if f.is_file()]
    carpeta = datos / COPIAS
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{datetime.now():%Y%m%d_%H%M%S}_antes_de_migrar_datos_v{desde}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for fichero, nombre in ficheros:
            z.write(fichero, nombre)
    return destino


def choques(origen, destino):
    """Ficheros que ya existen en el destino (mover origen allí los pisaría)."""
    if origen.is_dir() and destino.is_dir():
        return [c for hijo in origen.iterdir() for c in choques(hijo, destino / hijo.name)]
    return [destino] if destino.exists() else []


def mover_a_datos(origen, destino):
    """Mueve un fichero o carpeta de la 2.x a DATOS/; si la carpeta ya existe, junta el contenido."""
    if origen.is_dir() and destino.is_dir():
        for hijo in list(origen.iterdir()):
            mover_a_datos(hijo, destino / hijo.name)
        origen.rmdir()
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origen), str(destino))


def migrar_2_a_3(datos, antigua):
    """Datos sueltos de la 2.x -> DATOS/; el registro gana las columnas de anulación."""
    hechos = []
    if antigua:
        repetidos = [c for n in DATOS_2X if (antigua / n).exists()
                     for c in choques(antigua / n, datos / n)]
        if repetidos:
            raise ErrorPEC(f"No se pueden pasar los datos a {DATOS}/: estos ficheros están a la vez "
                           f"en la carpeta del programa y en {DATOS}/: "
                           f"{', '.join(str(r.relative_to(datos)) for r in repetidos)}. "
                           f"Deja solo la copia buena de cada uno y vuelve a arrancar.")
        for nombre in DATOS_2X:
            if (antigua / nombre).exists():
                mover_a_datos(antigua / nombre, datos / nombre)
                hechos.append(f"{nombre} pasa a {DATOS}/{nombre}")
    if (datos / REGISTRO).exists():
        escribir_registro(datos / REGISTRO, leer_registro(datos / REGISTRO))
        hechos.append(f"{REGISTRO}: añadidas las columnas de anulación de avisos")
    return hechos


def migrar_3_a_4(datos, antigua):
    """El registro gana las columnas de autoría y de entrega."""
    if not (datos / REGISTRO).exists():
        return []
    escribir_registro(datos / REGISTRO, leer_registro(datos / REGISTRO))
    return [f"{REGISTRO}: añadidas las columnas de quién genera, entrega y anula cada aviso"]


def migrar_4_a_5(datos, antigua):
    """correos_alumnado.csv pasa a alumnado.csv, que además guarda nombres corregidos y bajas."""
    viejo, nuevo = datos / CORREOS_4, datos / ALUMNADO
    if not viejo.exists():
        return []
    if not nuevo.exists():  # si ya existe, es de un intento anterior que no llegó a borrar el viejo
        with open(viejo, encoding="utf-8-sig", newline="") as f:
            filas = [{c: (fila.get(c) or "") for c in CAMPOS_ALUMNADO} for fila in csv.DictReader(f, delimiter=";")]
        escribir_alumnado(nuevo, filas)
    viejo.unlink()
    return [f"{CORREOS_4} pasa a {ALUMNADO} (correos, nombres corregidos y bajas del alumnado)"]


def migrar_5_a_6(datos, antigua):
    """Las bajas pasan de alumnado.csv (todo el grupo) a bajas_alumnado.csv (por módulo o de todo el grupo)."""
    ruta = datos / ALUMNADO
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    if not filas or "baja" not in filas[0]:
        return []
    bajas = leer_bajas(datos / BAJAS)
    hay = {clave_baja(b["grupo"], b["alumno"], b["modulo"]) for b in bajas}
    nuevas = [{"grupo": f["grupo"], "alumno": f["alumno"], "modulo": "", "fecha": f["baja"],
               "por": f.get("baja_por") or "", "motivo": f.get("motivo_baja") or ""}
              for f in filas if f.get("baja") and clave_baja(f["grupo"], f["alumno"]) not in hay]
    escribir_bajas(datos / BAJAS, bajas + nuevas)  # primero las bajas: así se puede repetir sin perder nada
    escribir_alumnado(ruta, [{c: (f.get(c) or "") for c in CAMPOS_ALUMNADO} for f in filas])
    return [f"Bajas del alumnado: pasan a {BAJAS} ({len(nuevas)}, en todos los módulos de su grupo)"]


MIGRACIONES = {2: migrar_2_a_3, 3: migrar_3_a_4, 4: migrar_4_a_5, 5: migrar_5_a_6}


def migrar_datos(datos, antigua=None):
    """
    Pone los datos al formato actual (FORMATO_DATOS) antes de usarlos. antigua es la carpeta donde
    la 2.x guardaba los datos (la del programa), o None. Antes de tocar nada se guarda un ZIP con
    todos los datos. Si algo falla a medias, se puede repetir: cada paso comprueba lo que ya está
    hecho. Devuelve la lista de lo que se ha hecho (vacía si no había nada que hacer).
    """
    datos = Path(datos)
    actual = version_datos(datos)
    de_la_2x = [antigua / n for n in DATOS_2X if antigua and (antigua / n).exists()]
    if actual is None and not de_la_2x and not datos.exists():
        datos.mkdir(parents=True)  # instalación nueva: no hay nada que migrar
        (datos / VERSION_DATOS).write_text(f"{FORMATO_DATOS}\n", encoding="utf-8")
        return []
    if actual is None:
        actual = 2  # datos de la 2.x, o una migración que no llegó a terminar
    if actual > FORMATO_DATOS:
        raise ErrorPEC(f"Los datos de {datos} son de una versión de WebPEC más moderna que esta. "
                       f"Instala la última versión.")
    if actual == FORMATO_DATOS:
        return []

    try:
        datos.mkdir(parents=True, exist_ok=True)
        copia = copia_antes_de_migrar(datos, de_la_2x + [datos], actual)
        hechos = [f"Copia de seguridad de los datos: {DATOS}/{COPIAS}/{copia.name}"]
        while actual < FORMATO_DATOS:
            hechos += MIGRACIONES[actual](datos, antigua)
            actual += 1
            (datos / VERSION_DATOS).write_text(f"{actual}\n", encoding="utf-8")
            hechos.append(f"Datos actualizados al formato {actual}")
    except PermissionError as e:
        raise ErrorPEC(f"No se pueden actualizar los datos: hay un fichero abierto o bloqueado "
                       f"({e.filename}). Ciérralo (Excel, LibreOffice…) y vuelve a arrancar WebPEC.")
    with open(datos / LOG_MIGRACIONES, "a", encoding="utf-8") as log:
        log.writelines(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {h}\n" for h in hechos)
    return hechos


def evaluar(informe, modulo, registro):
    """Situación de cada alumno que supera el 7,5 %: {alumno, fi, tipo (o None), estado}."""
    fecha = informe["fecha"].isoformat()
    grupo, siglas = informe["unidad"], modulo["siglas"]
    resultado = []
    for a in informe["alumnos"]:
        if a["fi"] < modulo["umbral_75"]:
            continue
        aviso = buscar_en_registro(registro, grupo, siglas, a["alumno"], AVISO)
        pec = buscar_en_registro(registro, grupo, siglas, a["alumno"], PEC)
        tipo = None
        if not aviso:
            tipo, estado = AVISO, "Aviso del 7,5 %"
        elif pec:
            estado = f"Pérdida ya emitida ({fecha_legible(pec['fecha_informe'])})"
        elif a["fi"] < modulo["umbral_15"]:
            estado = f"Ya avisado ({fecha_legible(aviso['fecha_informe'])})"
        elif fecha > aviso["fecha_informe"] and a["fi"] > int(aviso["faltas_injustificadas"]):
            tipo, estado = PEC, "Pérdida del 15 %"
        else:
            estado = (f"Supera el 15 %, pero se le avisó el {fecha_legible(aviso['fecha_informe'])} "
                      f"con {aviso['faltas_injustificadas']} FI: espera a nuevas faltas")
        resultado.append({"alumno": a["alumno"], "fi": a["fi"], "tipo": tipo, "estado": estado})
    return resultado


def fecha_legible(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


# --------------------------------------------------------- documentos ---

def sustituir_parrafo(parrafo, partes, tabulador=None, sangria_izquierda=None):
    """
    Reparte las partes de texto entre los <w:t> del párrafo y vacía los sobrantes.
    Una parte que empieza por '\\t' va precedida de un tabulador. Opcionalmente fija
    una tabulación (tipo, posición) y la sangría izquierda del párrafo.
    """
    partes = list(partes)

    def cambiar(m):
        if not partes:
            return "<w:t></w:t>"
        texto = partes.pop(0)
        tab = ""
        if texto.startswith("\t"):
            tab, texto = "<w:tab/>", texto[1:]
        return f'{tab}<w:t xml:space="preserve">{escape(texto)}</w:t>'

    parrafo = re.sub(r"<w:t(?: [^>]*)?>[^<]*</w:t>", cambiar, parrafo)

    if tabulador or sangria_izquierda is not None:
        ppr = re.search(r"<w:pPr>.*?</w:pPr>", parrafo, re.S)
        nuevo = ppr.group(0) if ppr else "<w:pPr></w:pPr>"
        nuevo = re.sub(r"<w:tabs>.*?</w:tabs>", "", nuevo, flags=re.S)
        nuevo = re.sub(r"<w:jc [^>]*/>", "", nuevo)
        if sangria_izquierda is not None:
            nuevo = re.sub(r"<w:ind [^>]*/>", "", nuevo)
            nuevo = nuevo.replace("</w:pPr>", f'<w:ind w:left="{sangria_izquierda}"/></w:pPr>')
        if tabulador:
            tipo, posicion = tabulador
            tabs = f'<w:tabs><w:tab w:val="{tipo}" w:pos="{posicion}"/></w:tabs>'
            estilo = re.match(r"<w:pPr>(<w:pStyle [^>]*/>)?", nuevo)
            nuevo = nuevo[:estilo.end()] + tabs + nuevo[estilo.end():]
        parrafo = parrafo.replace(ppr.group(0), nuevo, 1) if ppr else \
            re.sub(r"(<w:p[ >][^>]*>|<w:p>)", r"\1" + nuevo, parrafo, count=1)
    return parrafo


def rellenar_docx(plantilla, destino, cambios, nombres):
    """
    cambios: lista, en orden, con lo que va en cada párrafo que contiene '___':
    None (se deja igual), una lista de partes o un dict con argumentos de sustituir_parrafo.
    nombres: sustituciones directas de texto (p. ej. cargos del centro).
    """
    with zipfile.ZipFile(plantilla) as zin:
        xml = zin.read("word/document.xml").decode("utf-8")
        parrafos = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
        con_huecos = [p for p in parrafos
                      if "_" in "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))]
        for parrafo, cambio in zip(con_huecos, cambios):
            if cambio is None:
                continue
            argumentos = cambio if isinstance(cambio, dict) else {"partes": cambio}
            xml = xml.replace(parrafo, sustituir_parrafo(parrafo, **argumentos), 1)
        for antiguo, nuevo in nombres.items():
            xml = xml.replace(escape(antiguo), escape(nuevo))
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                datos = xml.encode("utf-8") if item.filename == "word/document.xml" \
                    else zin.read(item.filename)
                zout.writestr(item, datos)


def crear_docx(base, config, tipo, destino, alumno, grupo, modulo, profesor, fecha):
    cabecera = [f"Alumno/a: {alumno}    Curso: {grupo}"]
    firma_profesor = f"Fdo.: {profesor}"
    lugar_fecha = f"En {config['localidad']}, a {texto_fecha(fecha)}."
    if tipo == AVISO:
        rellenar_docx(base / PLANTILLAS / PLANTILLA_AVISO, destino, [
            cabecera,
            [modulo],
            [""],
            [lugar_fecha],
            {"partes": [firma_profesor, f"\tFdo.: {config['jefatura_estudios']}"],
             "tabulador": ("right", ANCHO_TEXTO)},
            None,  # Recibí: Fdo.
            None,  # Recibí: Fecha
        ], {JEFATURA_PLANTILLA: config["jefatura_estudios"]})
    else:
        rellenar_docx(base / PLANTILLAS / PLANTILLA_PEC, destino, [
            cabecera,
            [modulo],
            [lugar_fecha],
            # La firma del profesor se añade a la izquierda de la del "Recibí"
            {"partes": [firma_profesor, "\tFdo.: ________________________"],
             "tabulador": ("left", 4248), "sangria_izquierda": 0},
            [f"{config['localidad']}, a {texto_fecha(fecha)}."],
        ], {DIRECCION_PLANTILLA: config["direccion"].upper()})


def buscar_soffice():
    for nombre in ("soffice", "soffice.exe"):
        if shutil.which(nombre):
            return shutil.which(nombre)
    for raiz in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
        if raiz:
            ruta = Path(raiz) / "LibreOffice" / "program" / "soffice.exe"
            if ruta.exists():
                return str(ruta)
    return None


def hay_word():
    return os.name == "nt" and shutil.which("powershell") is not None


def convertir_libreoffice(soffice, docx_lista, carpeta):
    # Perfil propio para no chocar con una sesión de LibreOffice abierta
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run([soffice, f"-env:UserInstallation={Path(perfil).as_uri()}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(carpeta),
                        *map(str, docx_lista)],
                       check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def convertir_word(docx_lista, carpeta):
    lineas = ["$ErrorActionPreference = 'Stop'",
              "$word = New-Object -ComObject Word.Application",
              "$word.Visible = $false",
              "try {"]
    for docx in docx_lista:
        pdf = carpeta / (docx.stem + ".pdf")
        origen, salida = (str(p).replace("'", "''") for p in (docx, pdf))
        lineas += [f"  $d = $word.Documents.Open('{origen}', $false, $true)",
                   f"  $d.SaveAs([ref]'{salida}', [ref]17)",  # 17 = PDF
                   "  $d.Close($false)"]
    lineas += ["} finally { $word.Quit() }"]
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "convertir.ps1"
        script.write_text("\n".join(lineas), encoding="utf-8-sig")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(script)],
                       check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def nombre_conversor(conversor):
    if conversor == "auto":
        return "libreoffice" if buscar_soffice() else "word" if hay_word() else "ninguno"
    return conversor


def convertir_a_pdf(conversor, docx_lista, carpeta):
    """
    Convierte los .docx a PDF en la carpeta; los que no se conviertan se copian en .docx.
    Devuelve (documentos, aviso o None).
    """
    conversor = nombre_conversor(conversor)
    aviso = None
    try:
        if conversor == "libreoffice":
            soffice = buscar_soffice()
            if not soffice:
                raise RuntimeError("no se encuentra LibreOffice")
            convertir_libreoffice(soffice, docx_lista, carpeta)
        elif conversor == "word":
            if not hay_word():
                raise RuntimeError("Microsoft Word solo puede usarse en Windows")
            convertir_word(docx_lista, carpeta)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        aviso = f"No se han podido convertir los avisos a PDF ({conversor}: {e})"
    documentos = []
    for docx in docx_lista:
        pdf = carpeta / (docx.stem + ".pdf")
        if not pdf.exists():
            shutil.copy(str(docx), str(carpeta / docx.name))
            pdf = carpeta / docx.name
            aviso = aviso or "Hay avisos que se han dejado en .docx (no hay conversor a PDF)"
        documentos.append(pdf)
    return documentos, aviso


# ---------------------------------------------------------------- motor ---

class Motor:
    """Operaciones de la aplicación sobre la carpeta de datos (base)."""

    CARPETAS_DOCUMENTOS = {"pendientes": PENDIENTES, "realizados": REALIZADOS, "anulados": ANULADOS}

    def __init__(self, base=None):
        self.base = Path(base or PROGRAMA / DATOS).resolve()
        # Los datos de la 2.x solo se buscan junto al programa si se usa la carpeta DATOS/ normal
        antigua = PROGRAMA if self.base == PROGRAMA / DATOS else None
        self.migracion = migrar_datos(self.base, antigua)
        self.usuario = ""  # quién hace la acción en curso (lo fija el servidor en cada petición)
        self._informes_leidos = {}  # caché de informes procesados: nombre -> (fecha y tamaño, informe)
        self.preparar()

    def preparar(self):
        for carpeta in (NUEVOS, PROCESAR, PROCESADOS, PENDIENTES, REALIZADOS, ANULADOS):
            (self.base / carpeta).mkdir(parents=True, exist_ok=True)
        if not (self.base / HOJA_MODULOS).exists():
            crear_hoja_modulos(self.base / HOJA_MODULOS)
        if not (self.base / CONFIGURACION).exists():
            guardar_configuracion(self.base, {})
        for plantilla in (PLANTILLA_AVISO, PLANTILLA_PEC):
            if not (PROGRAMA / PLANTILLAS / plantilla).exists():
                raise ErrorPEC(f"Falta la plantilla {PLANTILLAS}/{plantilla}")

    def config(self):
        return leer_configuracion(self.base)

    def hoja(self):
        return HojaModulos(self.base / HOJA_MODULOS)

    # ---- informes

    def subir(self, nombre, datos):
        nombre = Path(nombre).name
        if not nombre.lower().endswith(".pdf"):
            raise ErrorPEC(f"{nombre}: solo se admiten PDF")
        if not datos.startswith(b"%PDF"):
            raise ErrorPEC(f"{nombre}: el fichero no es un PDF válido")
        destino = self.base / NUEVOS / nombre
        n = 2
        while destino.exists():
            destino = self.base / NUEVOS / f"{Path(nombre).stem} ({n}).pdf"
            n += 1
        destino.write_bytes(datos)
        return destino.name

    def _pdfs(self, carpeta):
        return sorted(p for p in (self.base / carpeta).iterdir()
                      if p.is_file() and p.suffix.lower() == ".pdf")

    def clasificar(self):
        """
        Lleva a PROCESAR, con su nombre normalizado, los informes nuevos que ya tienen todos
        los datos en la hoja de módulos.
        """
        hoja, config = self.hoja(), self.config()
        candidatos = self._pdfs(NUEVOS) + [p for p in self._pdfs(PROCESAR)
                                           if not PATRON_INFORME.match(p.name)]
        for ruta in candidatos:
            try:
                informe = leer_informe(ruta)
            except ErrorInforme:
                continue
            modulo = hoja.buscar_modulo(informe["unidad"], informe["modulo"])
            if modulo is None or hoja.firma(informe["profesor"]) is None:
                continue
            destino = self.base / PROCESAR / self._nombre_informe(config, informe, modulo)
            if (self.base / PROCESADOS / destino.name).exists() or destino == ruta:
                continue
            if destino.exists():
                destino.unlink()
            shutil.move(str(ruta), str(destino))

    @staticmethod
    def _nombre_informe(config, informe, modulo):
        return f"{fecha_fichero(config, informe['fecha'])}_{para_fichero(informe['unidad'])}_" \
               f"{modulo['siglas']}_Faltas.pdf"

    def _describir(self, ruta, hoja, config):
        """Datos de un informe pendiente, sin mover ni cambiar nada. Devuelve (item, informe)."""
        carpeta = ruta.parent.name
        item = {"id": f"{carpeta}/{ruta.name}", "archivo": ruta.name, "carpeta": carpeta}
        try:
            informe = leer_informe(ruta)
        except ErrorInforme as e:
            item["error"] = str(e)
            return item, None
        modulo = hoja.buscar_modulo(informe["unidad"], informe["modulo"])
        firma = hoja.firma(informe["profesor"])
        item.update({
            "unidad": informe["unidad"], "profesor": informe["profesor"],
            "modulo": informe["modulo"], "fecha": informe["fecha"].strftime("%d/%m/%Y"),
            "orden": informe["fecha"].isoformat(), "alumnos": len(informe["alumnos"]),
            "firma": firma,
        })
        if firma is None:
            # Quizá ya está en la lista con otro nombre (p. ej. dado de alta a mano sin el segundo nombre)
            candidatos = sorted(({"en_informe": p[1], "firma": p[2],
                                  "parecido": round(parecido_nombres(informe["profesor"], p[1]), 2)}
                                 for p in hoja.profesores.values()), key=lambda c: -c["parecido"])
            item["falta_firma"] = {"profesor": informe["profesor"],
                                   "propuesta": nombre_completo(informe["profesor"]),
                                   "candidatos": candidatos}
        if modulo is None:
            item["falta_modulo"] = {
                "unidad": informe["unidad"], "en_informe": informe["modulo"],
                "profesor": informe["profesor"],
                "siglas": siglas_propuestas(informe["modulo"],
                                            hoja.siglas_usadas(informe["unidad"])),
                "nombre": informe["modulo"].upper(),
            }
            return item, informe
        item["datos_modulo"] = {
            "siglas": modulo["siglas"], "nombre": modulo["nombre"],
            "horas": formato_umbral(modulo["horas"]),
            "umbral_75": formato_umbral(modulo["umbral_75"]),
            "umbral_15": formato_umbral(modulo["umbral_15"]),
        }
        item["nombre_final"] = self._nombre_informe(config, informe, modulo)
        if carpeta == NUEVOS and (self.base / PROCESADOS / item["nombre_final"]).exists():
            item["duplicado"] = f"Ya se procesó un informe {item['nombre_final']}"
        return item, informe

    def _pendientes(self, hoja, config):
        informes = [self._describir(ruta, hoja, config)[0]
                    for carpeta in (NUEVOS, PROCESAR) for ruta in self._pdfs(carpeta)]
        informes.sort(key=lambda i: (i.get("orden", ""), i["archivo"]))
        return informes

    def estado(self):
        """Informes pendientes de procesar, tal como están: no se mueve ni renombra nada."""
        hoja, config = self.hoja(), self.config()
        return {"informes": self._pendientes(hoja, config), "errores_hoja": hoja.errores,
                "conversor": nombre_conversor(config["conversor_pdf"]),
                "procesados": len(self._pdfs(PROCESADOS))}

    def borrar_informe(self, ident):
        ruta = self._ruta_informe(ident)
        ruta.unlink()

    def _ruta_informe(self, ident):
        carpeta, _, nombre = ident.partition("/")
        if carpeta not in (NUEVOS, PROCESAR, PROCESADOS):
            raise ErrorPEC("Carpeta no válida")
        ruta = self.base / carpeta / Path(nombre).name
        if not ruta.is_file():
            raise ErrorPEC(f"No existe {ident}")
        return ruta

    def ruta_informe(self, ident):
        return self._ruta_informe(ident)

    def procesar(self):
        """
        Botón «Procesar informes»: renombra los informes que tienen todos los datos, genera sus
        avisos y devuelve los que necesitan datos nuevos (módulo o profesor) para pedirlos.
        """
        self.clasificar()
        hoja, config = self.hoja(), self.config()
        registro = leer_registro(self.base / REGISTRO)
        leidos = []
        for ruta in self._pdfs(PROCESAR):
            if not PATRON_INFORME.match(ruta.name):
                continue
            try:
                leidos.append((ruta, leer_informe(ruta)))
            except ErrorInforme:
                continue
        leidos.sort(key=lambda r: (r[1]["fecha"], r[1]["unidad"], r[1]["modulo"]))

        resumen = {"informes": [], "avisos": 0, "perdidas": 0, "mensajes": []}
        fichas, bajas = self._fichas(), self._claves_bajas()
        for ruta, informe in leidos:
            modulo = hoja.buscar_modulo(informe["unidad"], informe["modulo"])
            firma = hoja.firma(informe["profesor"])
            if modulo is None or firma is None:
                continue
            situacion = [a for a in evaluar(informe, modulo, registro)
                         if not de_baja(bajas, informe["unidad"], a["alumno"], modulo["siglas"])]
            nuevos = [a for a in situacion if a["tipo"]]
            documentos = []
            if nuevos:
                filas, aviso = self._generar(config, informe, modulo, firma, nuevos, fichas)
                registro.extend(filas)
                documentos = [f["documento"] for f in filas]
                resumen["avisos"] += sum(f["tipo"] == AVISO for f in filas)
                resumen["perdidas"] += sum(f["tipo"] == PEC for f in filas)
                if aviso and aviso not in resumen["mensajes"]:
                    resumen["mensajes"].append(aviso)
            shutil.move(str(ruta), str(self.base / PROCESADOS / ruta.name))
            resumen["informes"].append({
                "archivo": ruta.name, "modulo": modulo["nombre"], "unidad": informe["unidad"],
                "fecha": informe["fecha"].strftime("%d/%m/%Y"), "profesor": firma,
                "situacion": situacion, "documentos": documentos,
            })

        quedan = self._pendientes(hoja, config)
        resumen["faltan_datos"] = [i for i in quedan if i.get("falta_firma") or i.get("falta_modulo")]
        resumen["sin_procesar"] = [i for i in quedan if i.get("error") or i.get("duplicado")]
        return resumen

    def _generar(self, config, informe, modulo, firma, nuevos, fichas):
        grupo, siglas, fecha = informe["unidad"], modulo["siglas"], informe["fecha"]
        # Los documentos llevan el nombre corregido a mano, si lo hay; el registro, el de Raíces
        nombres = {a["alumno"]: ficha_de(fichas, grupo, a["alumno"])["nombre"] for a in informe["alumnos"]}
        carpeta = carpeta_profesor(informe["profesor"])
        pendientes = self.base / PENDIENTES / carpeta
        pendientes.mkdir(parents=True, exist_ok=True)
        (self.base / REALIZADOS / carpeta).mkdir(parents=True, exist_ok=True)
        cortos = nombres_cortos([{"alumno": n} for n in nombres.values()])
        filas = []
        with tempfile.TemporaryDirectory() as tmp:
            docx_lista = []
            for a in nuevos:
                nombre = f"{fecha_fichero(config, fecha)}_{a['tipo']}_{para_fichero(grupo)}_" \
                         f"{siglas}_{cortos[nombres[a['alumno']]]}"
                docx = Path(tmp) / f"{nombre}.docx"
                crear_docx(PROGRAMA, config, a["tipo"], docx, nombre_completo(nombres[a["alumno"]]),
                           grupo, modulo["nombre"], firma, fecha)
                docx_lista.append(docx)
                filas.append({
                    "fecha_informe": fecha.isoformat(), "grupo": grupo, "modulo": siglas,
                    "nombre_modulo": modulo["nombre"], "profesor": informe["profesor"],
                    "alumno": a["alumno"], "tipo": a["tipo"], "faltas_injustificadas": a["fi"],
                    "umbral": formato_umbral(modulo["umbral_75" if a["tipo"] == AVISO
                                                    else "umbral_15"]),
                    "fecha_proceso": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "generado_por": self.usuario,
                })
            documentos, aviso = convertir_a_pdf(config["conversor_pdf"], docx_lista, pendientes)
        for fila, documento in zip(filas, documentos):
            fila["documento"] = documento.name
        anotar_registro(self.base / REGISTRO, filas)
        return filas, aviso

    def procesados(self):
        return [{"id": f"{PROCESADOS}/{p.name}", "archivo": p.name,
                 "fecha": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")}
                for p in sorted(self._pdfs(PROCESADOS), key=lambda p: p.name, reverse=True)]

    # ---- hoja de módulos

    def registrar_profesor(self, profesor, firma):
        firma = (firma or "").strip()
        if not profesor or not firma:
            raise ErrorPEC("Falta el nombre del profesor/a para la firma")
        self.hoja().guardar_profesor(profesor.strip(), firma)

    def registrar_modulo(self, unidad, en_informe, profesor, horas, siglas, nombre):
        hoja = self.hoja()
        if hoja.buscar_modulo(unidad, en_informe):
            raise ErrorPEC(f"El módulo «{en_informe}» de {unidad} ya está registrado")
        horas, siglas = self._validar_modulo(hoja, unidad, horas, siglas)
        hoja.anadir_modulo(unidad, siglas, en_informe, (nombre or en_informe).strip(),
                           profesor, horas)

    @staticmethod
    def _validar_modulo(hoja, unidad, horas, siglas, salvo_fila=None):
        try:
            horas = a_numero(horas)
        except (TypeError, ValueError):
            raise ErrorPEC("Las horas deben ser un número (p. ej. 100)")
        if horas <= 0:
            raise ErrorPEC("Las horas deben ser mayores que cero")
        if horas == int(horas):
            horas = int(horas)
        siglas = para_fichero(siglas or "")
        if not siglas:
            raise ErrorPEC("Faltan las siglas del módulo")
        if normalizar(siglas) in hoja.siglas_usadas(unidad, salvo_fila):
            raise ErrorPEC(f"Las siglas {siglas} ya las usa otro módulo de {unidad}")
        return horas, siglas

    def modulos(self):
        hoja = self.hoja()
        registro = leer_registro(self.base / REGISTRO)
        con_avisos = {(normalizar(f["grupo"]), normalizar(f["modulo"])) for f in registro}
        return {
            "modulos": [dict(m, horas=formato_umbral(m["horas"]),
                             umbral_75=formato_umbral(m["umbral_75"]),
                             umbral_15=formato_umbral(m["umbral_15"]),
                             con_avisos=(normalizar(m["unidad"]), normalizar(m["siglas"]))
                             in con_avisos)
                        for m in hoja.modulos],
            "profesores": [{"profesor": p[1], "firma": p[2]}
                           for p in sorted(hoja.profesores.values())],
            "errores": hoja.errores,
        }

    def actualizar_modulo(self, fila, horas, nombre, siglas):
        hoja = self.hoja()
        actual = next((m for m in hoja.modulos if m["fila"] == int(fila)), None)
        if actual is None:
            raise ErrorPEC("Ese módulo ya no está en la hoja; recarga la página")
        horas, siglas = self._validar_modulo(hoja, actual["unidad"], horas, siglas, actual["fila"])
        registro = leer_registro(self.base / REGISTRO)
        if siglas != actual["siglas"] and any(
                (normalizar(f["grupo"]), normalizar(f["modulo"])) ==
                (normalizar(actual["unidad"]), normalizar(actual["siglas"])) for f in registro):
            raise ErrorPEC("No se pueden cambiar las siglas de un módulo que ya tiene avisos")
        hoja.actualizar_modulo(actual["fila"], horas, (nombre or actual["en_informe"]).strip(),
                               siglas)

    def borrar_modulo(self, fila):
        hoja = self.hoja()
        if not any(m["fila"] == int(fila) for m in hoja.modulos):
            raise ErrorPEC("Ese módulo ya no está en la hoja; recarga la página")
        hoja.borrar_modulo(int(fila))

    # ---- profesorado (quién usa la aplicación)

    def usuarios(self):
        """Nombres (los de la firma) del profesorado conocido, para elegir quién usa WebPEC."""
        return sorted({p[2] for p in self.hoja().profesores.values()}, key=normalizar)

    def nuevo_profesor(self, nombre, apellidos):
        """
        Da de alta a un profesor/a que aún no tiene informes. Se guarda como lo escribe Raíces
        («Apellidos, Nombre»; las tildes no cuentan), así su primer informe ya lo reconoce.
        """
        nombre = re.sub(r"\s+", " ", nombre or "").strip()
        apellidos = re.sub(r"\s+", " ", apellidos or "").strip()
        if not nombre or not apellidos:
            raise ErrorPEC("Escribe el nombre y los apellidos")
        hoja = self.hoja()
        en_informe = f"{apellidos}, {nombre}"
        ya = hoja.firma(en_informe)
        if ya:
            return {"firma": ya, "nuevo": False}
        firma = f"{nombre} {apellidos}"
        hoja.guardar_profesor(en_informe, firma)
        return {"firma": firma, "nuevo": True}

    def vincular_profesor(self, profesor_informe, existente):
        """
        El profesor/a del informe es alguien que ya está en la lista con otro nombre: se le pone el
        nombre que trae el informe (la firma no cambia).
        """
        hoja = self.hoja()
        if hoja.firma(existente) is None:
            raise ErrorPEC("Ese profesor/a ya no está en la lista; recarga la página")
        if hoja.firma(profesor_informe) is not None:
            raise ErrorPEC(f"«{profesor_informe}» ya está en la lista")
        hoja.cambiar_nombre_informe(existente, profesor_informe.strip())  # la hoja se vuelve a leer
        return {"firma": hoja.firma(profesor_informe)}

    def borrar_profesor(self, profesor):
        hoja = self.hoja()
        if hoja.firma(profesor) is None:
            raise ErrorPEC("Ese profesor/a ya no está en la hoja; recarga la página")
        hoja.borrar_profesor(profesor)

    def anotar_actividad(self, accion, detalle=""):
        ruta = self.base / ACTIVIDAD
        nuevo = not ruta.exists()
        try:
            with open(ruta, "a", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                if nuevo:
                    w.writerow(["fecha", "usuario", "accion", "detalle"])
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.usuario or "(sin indicar)",
                            accion, re.sub(r"\s+", " ", str(detalle)).strip()])
        except PermissionError:
            pass  # si está abierto en Excel no se pierde la acción, solo su anotación

    def actividad(self, limite=500):
        ruta = self.base / ACTIVIDAD
        if not ruta.exists():
            return []
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f, delimiter=";"))
        return filas[::-1][:limite]

    # ---- documentos generados

    def documentos(self, carpeta):
        raiz = self._carpeta_documentos(carpeta)
        # Un documento anulado y otro nuevo pueden llamarse igual: cada bandeja busca el suyo
        por_documento = {f["documento"]: f for f in leer_registro(self.base / REGISTRO)
                         if anulada(f) == (carpeta == "anulados")}
        hoja = self.hoja()
        firmas = {para_fichero(p[1]): p[2] for p in hoja.profesores.values()}
        fichas = self._fichas()
        lista = []
        for ruta in sorted(raiz.glob("*/*")):
            if not ruta.is_file() or ruta.suffix.lower() not in (".pdf", ".docx"):
                continue
            fila = por_documento.get(ruta.name, {})
            tipo = fila.get("tipo") or (AVISO if f"_{AVISO}_" in ruta.name else PEC)
            ficha = ficha_de(fichas, fila.get("grupo", ""), fila.get("alumno", "")) if fila else {}
            lista.append({
                "ruta": f"{ruta.parent.name}/{ruta.name}", "archivo": ruta.name,
                "profesor": firmas.get(ruta.parent.name, ruta.parent.name.replace("_", " ")),
                "tipo": tipo, "alumno": ficha.get("nombre", ""),
                "grupo": fila.get("grupo", ""), "modulo": fila.get("nombre_modulo", ""),
                "fi": fila.get("faltas_injustificadas", ""),
                "fecha": fecha_legible(fila.get("fecha_informe", "")),
                "orden": fila.get("fecha_informe", ""),
                "pdf": ruta.suffix.lower() == ".pdf",
                "fecha_anulacion": fila.get("fecha_anulacion", ""),
                "motivo_anulacion": fila.get("motivo_anulacion", ""),
                "anulado_por": fila.get("anulado_por", ""),
                "fecha_entrega": fila.get("fecha_entrega", ""),
                "entregado_por": fila.get("entregado_por", ""),
                "correo": ficha.get("correo", ""),
            })
        lista.sort(key=lambda d: (d["orden"], d["profesor"], d["archivo"]), reverse=True)
        return lista

    def _carpeta_documentos(self, carpeta):
        if carpeta not in self.CARPETAS_DOCUMENTOS:
            raise ErrorPEC("Carpeta no válida")
        return self.base / self.CARPETAS_DOCUMENTOS[carpeta]

    def ruta_documento(self, carpeta, relativa):
        raiz = self._carpeta_documentos(carpeta).resolve()
        ruta = (raiz / relativa).resolve()
        if raiz not in ruta.parents or not ruta.is_file():
            raise ErrorPEC(f"No existe el documento {relativa}")
        return ruta

    def unir_pdf(self, carpeta, rutas):
        escritor = PdfWriter()
        for relativa in rutas:
            ruta = self.ruta_documento(carpeta, relativa)
            if ruta.suffix.lower() == ".pdf":
                escritor.append(str(ruta))
        if not escritor.pages:
            raise ErrorPEC("No hay ningún PDF entre los documentos elegidos")
        salida = io.BytesIO()
        escritor.write(salida)
        return salida.getvalue()

    def zip_documentos(self, carpeta, rutas):
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            for relativa in rutas:
                ruta = self.ruta_documento(carpeta, relativa)
                z.write(ruta, ruta.name)
        return salida.getvalue()

    def mover_documentos(self, carpeta, rutas, accion):
        """Entre pendientes y entregados. accion: 'realizados' o 'pendientes'."""
        if accion not in ("realizados", "pendientes") or carpeta == "anulados":
            raise ErrorPEC("Acción no válida")
        movidos = []
        for relativa in rutas:
            ruta = self.ruta_documento(carpeta, relativa)
            if accion != carpeta:
                destino = self._carpeta_documentos(accion) / ruta.parent.name
                destino.mkdir(parents=True, exist_ok=True)
                shutil.move(str(ruta), str(destino / ruta.name))
                movidos.append(ruta.name)
        # La entrega queda anotada en el registro (y se borra si vuelve a pendientes)
        if movidos:
            entrega = {"fecha_entrega": datetime.now().strftime("%Y-%m-%d %H:%M"),
                       "entregado_por": self.usuario} if accion == "realizados" else \
                {"fecha_entrega": "", "entregado_por": ""}
            registro = leer_registro(self.base / REGISTRO)
            for fila in registro:
                if fila["documento"] in movidos and not anulada(fila):
                    fila.update(entrega)
            escribir_registro(self.base / REGISTRO, registro)
        return len(movidos)

    def contar_documentos(self):
        return {clave: sum(1 for p in (self.base / carpeta).glob("*/*") if p.is_file())
                for clave, carpeta in self.CARPETAS_DOCUMENTOS.items()}

    def borrar_todos_documentos(self, cuales):
        """cuales: 'pendientes', 'realizados' o 'todos'."""
        if cuales not in ("pendientes", "realizados", "todos"):
            raise ErrorPEC("Opción no válida")
        claves = ["pendientes", "realizados"] if cuales == "todos" else [cuales]
        borrados = 0
        for clave in claves:
            for ruta in (self.base / self.CARPETAS_DOCUMENTOS[clave]).glob("*/*"):
                if ruta.is_file():
                    ruta.unlink()
                    borrados += 1
        return borrados

    def borrar_procesados(self):
        rutas = self._pdfs(PROCESADOS)
        for ruta in rutas:
            ruta.unlink()
        return len(rutas)

    # ---- anulación de avisos

    def anular(self, documentos, motivo):
        """
        Anula avisos del registro (por nombre de documento): quedan anotados como anulados, con
        fecha y motivo, y su documento pasa a AVISOS_ANULADOS. Como ya no cuentan, el siguiente
        informe que se procese puede volver a generarlos.
        """
        motivo = re.sub(r"\s+", " ", motivo or "").strip()
        if not motivo:
            raise ErrorPEC("Indica el motivo de la anulación")
        if not documentos:
            raise ErrorPEC("No hay ningún aviso elegido")
        registro = leer_registro(self.base / REGISTRO)
        filas = []
        for documento in dict.fromkeys(documentos):
            fila = next((f for f in registro if f["documento"] == documento and not anulada(f)), None)
            if fila is None:
                raise ErrorPEC(f"{documento} no está en el registro o ya está anulado")
            filas.append(fila)
        # Sin el aviso del 7,5 % no puede quedar en pie la pérdida del 15 %
        for fila in filas:
            if fila["tipo"] == AVISO:
                perdida = buscar_en_registro(registro, fila["grupo"], fila["modulo"], fila["alumno"], PEC)
                if perdida is not None and not any(perdida is f for f in filas):
                    raise ErrorPEC(f"{fila['alumno']} ({fila['grupo']}, {fila['modulo']}) tiene también la "
                                   f"pérdida del 15 %: anúlala antes, o las dos a la vez")
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        for fila in filas:
            fila.update(estado=ANULADO, fecha_anulacion=ahora, motivo_anulacion=motivo,
                        anulado_por=self.usuario)
        escribir_registro(self.base / REGISTRO, registro)

        movidos = 0
        for fila in filas:
            for carpeta in (PENDIENTES, REALIZADOS):
                for ruta in (self.base / carpeta).glob(f"*/{glob_literal(fila['documento'])}"):
                    destino = self.base / ANULADOS / ruta.parent.name / ruta.name
                    n = 2
                    while destino.exists():
                        destino = destino.with_name(f"{ruta.stem} ({n}){ruta.suffix}")
                        n += 1
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(ruta), str(destino))
                    movidos += 1
        return {"anulados": len(filas), "documentos": movidos}

    # ---- situación del alumnado

    def _informe_procesado(self, ruta):
        """Lee un informe procesado (con caché: leer PDF es lento)."""
        estado = ruta.stat()
        clave = (estado.st_mtime, estado.st_size)
        guardado = self._informes_leidos.get(ruta.name)
        if guardado and guardado[0] == clave:
            return guardado[1]
        try:
            informe = leer_informe(ruta)
        except ErrorInforme:
            informe = None
        self._informes_leidos[ruta.name] = (clave, informe)
        return informe

    def situacion_alumnado(self):
        """
        Cada alumno de cada módulo según el último informe procesado que se conserva:
        faltas, porcentaje y avisos vigentes.
        """
        hoja = self.hoja()
        registro = leer_registro(self.base / REGISTRO)
        fichas, claves_bajas = self._fichas(), self._claves_bajas()
        ultimos = {}
        for ruta in self._pdfs(PROCESADOS):
            informe = self._informe_procesado(ruta)
            if informe is None:
                continue
            clave = (normalizar(informe["unidad"]), normalizar(informe["modulo"]))
            if clave not in ultimos or (informe["fecha"], ruta.name) > (ultimos[clave][0]["fecha"], ultimos[clave][1]):
                ultimos[clave] = (informe, ruta.name)
        alumnos, sin_modulo = [], []
        for informe, archivo in ultimos.values():
            modulo = hoja.buscar_modulo(informe["unidad"], informe["modulo"])
            if modulo is None:
                sin_modulo.append(archivo)
                continue
            grupo, siglas = informe["unidad"], modulo["siglas"]
            for a in informe["alumnos"]:
                if de_baja(claves_bajas, grupo, a["alumno"], siglas):
                    continue
                ficha = ficha_de(fichas, grupo, a["alumno"])
                aviso = buscar_en_registro(registro, grupo, siglas, a["alumno"], AVISO)
                perdida = buscar_en_registro(registro, grupo, siglas, a["alumno"], PEC)
                estado = "perdida" if perdida else "aviso" if aviso else \
                    "supera" if a["fi"] >= modulo["umbral_75"] else "sin_avisos"
                alumnos.append({
                    "alumno": ficha["nombre"], "en_raices": a["alumno"], "grupo": grupo, "siglas": siglas, "modulo": modulo["nombre"],
                    "profesor": hoja.firma(informe["profesor"]) or informe["profesor"],
                    "fi": a["fi"], "horas": formato_umbral(modulo["horas"]),
                    "porcentaje": formato_umbral(round(a["fi"] * 100 / modulo["horas"], 1)),
                    "umbral_75": formato_umbral(modulo["umbral_75"]),
                    "umbral_15": formato_umbral(modulo["umbral_15"]),
                    "supera_15": a["fi"] >= modulo["umbral_15"],
                    "estado": estado, "informe": informe["fecha"].strftime("%d/%m/%Y"),
                    "fecha_aviso": fecha_legible(aviso["fecha_informe"]) if aviso else "",
                    "fecha_perdida": fecha_legible(perdida["fecha_informe"]) if perdida else "",
                    "correo": ficha["correo"],
                })
        alumnos.sort(key=lambda x: (x["grupo"], normalizar(x["alumno"]), x["siglas"]))
        nombres_modulo = {(normalizar(m["unidad"]), normalizar(m["siglas"])): m["nombre"] for m in hoja.modulos}
        bajas = [dict(b, nombre=ficha_de(fichas, b["grupo"], b["alumno"])["nombre"],
                      nombre_modulo=nombres_modulo.get((normalizar(b["grupo"]), normalizar(b["modulo"])), b["modulo"])
                      if b["modulo"] else "")
                 for b in leer_bajas(self.base / BAJAS)]
        bajas.sort(key=lambda b: (b["grupo"], normalizar(b["nombre"]), b["modulo"]))
        return {"alumnos": alumnos, "informes": len(ultimos), "sin_modulo": sin_modulo, "bajas": bajas}

    # ---- fichas del alumnado: correos (solo el dato), nombres corregidos y bajas

    def _fichas(self):
        return {clave_ficha(f["grupo"], f["alumno"]): f for f in leer_alumnado(self.base / ALUMNADO)}

    def importar_correos(self, nombre, datos, grupo=""):
        """Añade o actualiza correos desde un CSV o Excel (alumno y correo; grupo opcional)."""
        nuevos = extraer_correos(leer_tabla(nombre, datos))
        fichas = self._fichas()
        resultado = {"leidos": len(nuevos), "nuevos": 0, "actualizados": 0}
        for g, alumno, correo in nuevos:
            g = g or (grupo or "").strip()
            clave = clave_ficha(g, alumno)
            if clave in fichas:
                if fichas[clave]["correo"] != correo:
                    fichas[clave]["correo"] = correo
                    resultado["actualizados"] += 1
            else:
                fichas[clave] = dict({c: "" for c in CAMPOS_ALUMNADO}, grupo=g, alumno=alumno, correo=correo)
                resultado["nuevos"] += 1
        escribir_alumnado(self.base / ALUMNADO, fichas.values())
        return resultado

    def _ficha_propia(self, fichas, grupo, alumno):
        """La fila del alumno/a en su grupo (se crea si no existe); absorbe la que no tiene grupo."""
        if not (grupo or "").strip() or not (alumno or "").strip():
            raise ErrorPEC("Falta el grupo o el nombre del alumno/a")
        clave = clave_ficha(grupo, alumno)
        if clave not in fichas:
            fichas[clave] = dict({c: "" for c in CAMPOS_ALUMNADO}, grupo=grupo.strip(), alumno=alumno.strip())
        general = fichas.pop(clave_ficha("", alumno), None)
        if general:
            for c in ("nombre", "correo"):
                fichas[clave][c] = fichas[clave][c] or general[c]
        return fichas[clave]

    def editar_alumno(self, grupo, alumno, apellidos, nombre, correo):
        """Corrige a mano el nombre (para avisos y listados) o el correo de un alumno/a de un grupo."""
        apellidos, nombre, correo = (re.sub(r"\s+", " ", x or "").strip(" ,") for x in (apellidos, nombre, correo))
        if not apellidos:
            raise ErrorPEC("Escribe al menos los apellidos")
        if correo and not PATRON_CORREO.match(correo):
            raise ErrorPEC(f"«{correo}» no es una dirección de correo válida")
        fichas = self._fichas()
        ficha = self._ficha_propia(fichas, grupo, alumno)
        completo = f"{apellidos}, {nombre}" if nombre else apellidos
        ficha["nombre"] = "" if completo == alumno.strip() else completo
        ficha["correo"] = correo
        escribir_alumnado(self.base / ALUMNADO, fichas.values())
        return {"nombre": completo, "correo": correo}

    def _claves_bajas(self):
        return {clave_baja(b["grupo"], b["alumno"], b["modulo"]) for b in leer_bajas(self.base / BAJAS)}

    def dar_de_baja(self, grupo, alumno, modulos, motivo=""):
        """
        Baja en los módulos elegidos (siglas) o, con modulos vacío, en todos los de su grupo (también los de
        informes futuros): ahí desaparece de Alumnado y ya no recibe avisos nuevos aunque siga en los informes
        de Raíces. Lo ya generado no se toca: devuelve sus avisos de esos módulos que siguen en Pendientes.
        """
        grupo, alumno = (grupo or "").strip(), (alumno or "").strip()
        if not grupo or not alumno:
            raise ErrorPEC("Falta el grupo o el nombre del alumno/a")
        modulos = sorted({m.strip() for m in modulos or [] if m.strip()})
        ruta = self.base / BAJAS
        bajas = leer_bajas(ruta)
        clave = clave_ficha(grupo, alumno)
        propias = [b for b in bajas if clave_ficha(b["grupo"], b["alumno"]) == clave]
        if any(not b["modulo"] for b in propias):
            raise ErrorPEC(f"{alumno} ya está de baja en todos los módulos de {grupo}")
        if not modulos:  # todos: sustituye a las bajas de módulos sueltos
            bajas = [b for b in bajas if b not in propias]
        ya = {normalizar(b["modulo"]) for b in propias}
        fila = {"grupo": grupo, "alumno": alumno, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "por": self.usuario, "motivo": (motivo or "").strip()}
        bajas += [dict(fila, modulo=m) for m in (modulos or [""]) if normalizar(m) not in ya or not modulos]
        escribir_bajas(ruta, bajas)
        elegidos = {normalizar(m) for m in modulos}
        pendientes = [f["documento"] for f in leer_registro(self.base / REGISTRO)
                      if not anulada(f) and clave_ficha(f["grupo"], f["alumno"]) == clave
                      and (not elegidos or normalizar(f["modulo"]) in elegidos)
                      and list((self.base / PENDIENTES).glob(f"*/{glob_literal(f['documento'])}"))]
        return {"nombre": ficha_de(self._fichas(), grupo, alumno)["nombre"], "pendientes": pendientes}

    def recuperar_alumno(self, grupo, alumno, modulo=""):
        """Deshace una baja (por si se dio por error): la de ese módulo o, con modulo vacío, la de todos."""
        ruta = self.base / BAJAS
        bajas = leer_bajas(ruta)
        quedan = [b for b in bajas if clave_baja(b["grupo"], b["alumno"], b["modulo"]) != clave_baja(grupo, alumno, modulo)]
        if len(quedan) == len(bajas):
            raise ErrorPEC(f"{alumno} ({grupo}) no está dado/a de baja ahí")
        escribir_bajas(ruta, quedan)
        return {"nombre": ficha_de(self._fichas(), grupo, alumno)["nombre"]}

    # ---- envío por correo (lo prepara el programa de correo; WebPEC no envía nada)

    def programa_correo(self):
        """'thunderbird' o 'eml', según la configuración y lo que haya instalado."""
        elegido = self.config()["programa_correo"]
        if elegido == "eml" or (elegido == "auto" and not buscar_thunderbird()):
            return "eml"
        return "thunderbird"

    def _datos_correo(self, carpeta, relativa):
        """Fichero, fila del registro, destinatario, asunto y texto (HTML) del correo de un aviso."""
        ruta = self.ruta_documento(carpeta, relativa)
        fila = next((f for f in leer_registro(self.base / REGISTRO)
                     if f["documento"] == ruta.name and not anulada(f)), None)
        if fila is None:
            raise ErrorPEC(f"{ruta.name} no está en el registro")
        firma = self.hoja().firma(fila["profesor"]) or nombre_completo(fila["profesor"])
        ficha = ficha_de(self._fichas(), fila["grupo"], fila["alumno"])
        asunto, html = texto_correo(fila, firma, self.config(), ficha["nombre"])
        return ruta, fila, ficha["correo"], asunto, html

    def preparar_correos(self, carpeta, rutas):
        """Abre en Thunderbird un correo por aviso, con el PDF adjunto y el texto ya escritos."""
        if not rutas:
            raise ErrorPEC("No hay ningún aviso elegido")
        programa = self.programa_correo()
        sin_correo, abiertos = [], 0
        if programa == "thunderbird":
            thunderbird = buscar_thunderbird()
            if not thunderbird:
                raise ErrorPEC("No se encuentra Thunderbird. En Configuración se puede elegir «fichero .eml».")
            preparar_carpeta_correo()
            for relativa in rutas:
                ruta, fila, correo, asunto, html = self._datos_correo(carpeta, relativa)
                if not correo:
                    sin_correo.append(fila["alumno"])
                # Copias que el programa de correo pueda leer
                adjunto = CARPETA_CORREO / ruta.name
                shutil.copyfile(ruta, adjunto)
                cuerpo = CARPETA_CORREO / f"{ruta.stem}.html"
                cuerpo.write_text(html, encoding="utf-8")
                abrir_thunderbird(thunderbird, correo, asunto, cuerpo, adjunto)
                abiertos += 1
        else:
            for relativa in rutas:
                _, fila, correo, _, _ = self._datos_correo(carpeta, relativa)
                if not correo:
                    sin_correo.append(fila["alumno"])
        return {"programa": programa, "abiertos": abiertos, "sin_correo": sin_correo}

    def eml(self, carpeta, relativa):
        """Fichero .eml (borrador sin enviar) con el aviso adjunto, para el programa de correo."""
        ruta, fila, correo, asunto, html = self._datos_correo(carpeta, relativa)
        mensaje = EmailMessage()
        mensaje["To"] = correo
        mensaje["Subject"] = asunto
        mensaje["X-Unsent"] = "1"  # Outlook y otros lo abren como borrador para enviar
        texto = html.replace("<br>", "\n").replace("</p>", "\n\n")
        mensaje.set_content(re.sub(r"<[^>]+>", "", texto).strip())
        mensaje.add_alternative(html, subtype="html")
        tipo = ("application", "pdf") if ruta.suffix.lower() == ".pdf" else \
            ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
        mensaje.add_attachment(ruta.read_bytes(), maintype=tipo[0], subtype=tipo[1], filename=ruta.name)
        return f"{ruta.stem}.eml", bytes(mensaje)

    # ---- exportar e importar todos los datos

    def exportar_datos(self):
        """ZIP con todo DATOS/ (salvo las copias de seguridad)."""
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            for fichero in sorted(self.base.rglob("*")):
                relativa = fichero.relative_to(self.base)
                if fichero.is_file() and relativa.parts[0] != COPIAS and fichero.suffix != ".tmp":
                    z.write(fichero, relativa.as_posix())
        return salida.getvalue()

    def importar_datos(self, datos):
        """
        Sustituye los datos por los de un ZIP exportado (de este u otro ordenador, también de una
        versión anterior). Antes se guarda un ZIP con los datos actuales en COPIAS_SEGURIDAD/.
        """
        try:
            z = zipfile.ZipFile(io.BytesIO(datos))
        except zipfile.BadZipFile:
            raise ErrorPEC("El fichero no es un ZIP válido")
        with z:
            nombres = [n for n in z.namelist() if not n.endswith("/")]
            marcas = (VERSION_DATOS, REGISTRO, HOJA_MODULOS)
            # Los datos pueden venir en la raíz del ZIP o dentro de una carpeta (p. ej. DATOS/)
            prefijos = {n[:-len(m)] for n in nombres for m in marcas
                        if n == m or n.endswith("/" + m) and n.count("/") == 1}
            if len(prefijos) != 1:
                raise ErrorPEC("El ZIP no contiene datos de WebPEC (registro de avisos, hoja de módulos…)")
            prefijo = prefijos.pop()
            if prefijo + VERSION_DATOS in nombres:
                try:
                    formato = int(z.read(prefijo + VERSION_DATOS).decode().strip())
                except ValueError:
                    formato = FORMATO_DATOS
                if formato > FORMATO_DATOS:
                    raise ErrorPEC("Los datos son de una versión de WebPEC más moderna que esta: "
                                   "instala antes la última versión")
            copia = self.base / COPIAS / f"{datetime.now():%Y%m%d_%H%M%S}_antes_de_importar_datos.zip"
            copia.parent.mkdir(exist_ok=True)
            copia.write_bytes(self.exportar_datos())
            try:
                for hijo in list(self.base.iterdir()):
                    if hijo.name != COPIAS:
                        shutil.rmtree(hijo) if hijo.is_dir() else hijo.unlink()
                copiados = 0
                for nombre in nombres:
                    if not nombre.startswith(prefijo):
                        continue
                    partes = PurePosixPath(nombre[len(prefijo):]).parts
                    if not partes or partes[0] == COPIAS or ".." in partes or partes[0].startswith("/"):
                        continue
                    destino = self.base.joinpath(*partes)
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(nombre) as origen, open(destino, "wb") as salida:
                        shutil.copyfileobj(origen, salida)
                    copiados += 1
            except PermissionError as e:
                raise ErrorPEC(f"No se han podido sustituir los datos: {e.filename} está abierto. Ciérralo y "
                               f"vuelve a importar; los datos anteriores están en {COPIAS}/{copia.name}")
        migracion = migrar_datos(self.base)  # por si el ZIP es de un formato anterior
        self._informes_leidos.clear()
        self.preparar()
        return {"ficheros": copiados, "copia": f"{COPIAS}/{copia.name}", "migracion": migracion}

    # ---- borrados completos de datos (con copia de seguridad)

    def _copia_seguridad(self, nombre):
        origen = self.base / nombre
        if not origen.exists():
            return None
        carpeta = self.base / COPIAS
        carpeta.mkdir(exist_ok=True)
        destino = carpeta / f"{datetime.now():%Y%m%d_%H%M%S}_{nombre}"
        shutil.copyfile(origen, destino)
        return f"{COPIAS}/{destino.name}"

    def vaciar_registro(self):
        filas = leer_registro(self.base / REGISTRO)
        copia = self._copia_seguridad(REGISTRO)
        try:
            (self.base / REGISTRO).unlink(missing_ok=True)
        except PermissionError:
            raise ErrorPEC(f"No se puede borrar {REGISTRO}: ciérralo en Excel y vuelve a intentarlo")
        anotar_registro(self.base / REGISTRO, [])
        return {"borrados": len(filas), "copia": copia}

    def vaciar_hoja(self):
        hoja = self.hoja()
        cuantos = {"modulos": len(hoja.modulos), "profesores": len(hoja.profesores)}
        copia = self._copia_seguridad(HOJA_MODULOS)
        try:
            crear_hoja_modulos(self.base / HOJA_MODULOS)
        except PermissionError:
            raise ErrorPEC(f"No se puede guardar {HOJA_MODULOS}: ciérrala en Excel o LibreOffice "
                           f"y vuelve a intentarlo")
        return dict(cuantos, copia=copia)

    # ---- registro

    def registro(self):
        filas = leer_registro(self.base / REGISTRO)
        for f in filas:
            f["fecha"] = fecha_legible(f.get("fecha_informe", ""))
        filas.sort(key=lambda f: (f.get("fecha_informe", ""), f.get("fecha_proceso", "")),
                   reverse=True)
        return filas

#!/usr/bin/env python3
"""
WebPEC: aplicación web para generar los avisos de pérdida de evaluación continua.

Arranca un pequeño servidor en este ordenador y abre el navegador en http://localhost:<puerto>.
Mientras se usa, la ventana del programa debe quedar abierta; al cerrarla se detiene.

Uso:
  webpec.py                       arranca y abre el navegador
  webpec.py --sin-navegador       arranca sin abrir el navegador
  webpec.py --instalar            prepara los datos, crea el icono del escritorio y arranca
  webpec.py --instalar --destino CARPETA
                                  actualiza sin preguntas la instalación de CARPETA con esta versión
                                  (lo usa «Actualizar ahora» desde dentro de WebPEC)
  webpec.py --crear-acceso-directo  solo crea el icono de WebPEC en el escritorio

Licencia: Creative Commons BY-NC-SA 4.0 (ver LICENCIA.txt).
"""

import argparse
import base64
import filecmp
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
import zipfile
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urlparse

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"

if sys.version_info < (3, 9):
    sys.exit("WebPEC necesita Python 3.9 o posterior. Instálalo desde https://www.python.org "
             "(en Windows, marcando «Add Python to PATH»).")

try:
    import motor_pec
    from motor_pec import ErrorPEC, Motor
except ImportError as e:
    sys.exit(f"No se pueden cargar las librerías de WebPEC ({e}).\n"
             f"Copia de nuevo la carpeta completa del programa, incluida lib/. Si has abierto el "
             f"instalador desde dentro del ZIP, descomprímelo antes («Extraer todo»).")

# Versión: X.YY. Cambios pequeños suben las centésimas; muchos cambios, la décima;
# cambios grandes, la unidad. El historial está en CAMBIOS.md.
try:
    VERSION = (BASE / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    VERSION = "?"
TAMANO_MAXIMO = 200 * 1024 * 1024
# Peticiones que traen un fichero en lugar de JSON
FICHEROS_SUBIDOS = {"/api/subir", "/api/correos/importar", "/api/datos/importar"}
MANUAL = BASE / "MANUAL_USUARIO.md"
MANUAL_PDF = BASE / "MANUAL_USUARIO.pdf"
INSTRUCCIONES = BASE / "INSTRUCCIONES.html"
INSTRUCCIONES_PDF = BASE / "INSTRUCCIONES.pdf"

# Las operaciones sobre ficheros, hoja y registro se hacen de una en una
CERROJO = threading.Lock()


class Manejador(BaseHTTPRequestHandler):
    server_version = f"WebPEC/{VERSION}"
    motor = None

    # ---- respuestas

    def _enviar(self, codigo, cuerpo, tipo, extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for clave, valor in (extra or {}).items():
            self.send_header(clave, valor)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, datos, codigo=200):
        self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def _fichero(self, datos, nombre, tipo, descargar):
        modo = "attachment" if descargar else "inline"
        self._enviar(200, datos, tipo, {
            "Content-Disposition": f"{modo}; filename*=UTF-8''{quote(nombre)}"})

    def _leer_json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(largo) or b"{}") if largo else {}

    def log_message(self, formato, *args):
        pass  # sin registro de cada petición en la consola

    # ---- rutas

    def do_GET(self):
        self._atender(self._get)

    def do_POST(self):
        self._atender(self._post)

    def _atender(self, funcion):
        url = urlparse(self.path)
        consulta = {k: v if len(v) > 1 or k == "r" else v[0]
                    for k, v in parse_qs(url.query).items()}
        try:
            funcion(url.path, consulta)
        except ErrorPEC as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # cualquier fallo inesperado se muestra en la página
            traceback.print_exc()
            self._json({"error": f"Error inesperado: {e}"}, 500)

    def _get(self, ruta, q):
        m = self.motor
        if ruta == "/api/version":  # para saber, tras «Actualizar ahora», cuándo ha vuelto a arrancar
            return self._json({"version": VERSION})
        if ruta == "/api/actualizacion":  # fuera del cerrojo: consulta Internet y puede tardar unos segundos
            return self._json(comprobar_actualizacion(m.config(), forzar="forzar" in q))
        if ruta in ("/", "/index.html"):
            return self._estatico("index.html")
        if ruta.startswith("/web/"):
            return self._estatico(unquote(ruta[5:]))
        if ruta == "/ayuda":
            return self._enviar(200, manual_html().encode("utf-8"), "text/html; charset=utf-8")
        if ruta == "/instrucciones":
            return self._enviar(200, instrucciones_html().encode("utf-8"), "text/html; charset=utf-8")
        if ruta == "/instrucciones.pdf":
            if not INSTRUCCIONES_PDF.is_file():
                raise ErrorPEC("No están las instrucciones en PDF: usa la versión en pantalla (/instrucciones)")
            return self._fichero(INSTRUCCIONES_PDF.read_bytes(), f"Instrucciones_WebPEC_{VERSION}.pdf",
                                 "application/pdf", "descargar" in q)
        if ruta == "/manual.pdf":
            if not MANUAL_PDF.is_file():
                raise ErrorPEC("No está el manual en PDF: usa la versión en pantalla (y su botón Imprimir)")
            return self._fichero(MANUAL_PDF.read_bytes(), MANUAL_PDF.name, "application/pdf", "descargar" in q)
        with CERROJO:
            if ruta == "/api/estado":
                return self._json(m.estado())
            if ruta == "/api/procesados":
                return self._json(m.procesados())
            if ruta == "/api/documentos/contar":
                return self._json(m.contar_documentos())
            if ruta == "/api/documentos":
                return self._json(m.documentos(q.get("carpeta", "pendientes")))
            if ruta == "/api/modulos":
                return self._json(m.modulos())
            if ruta == "/api/registro":
                return self._json(m.registro())
            if ruta == "/api/usuarios":
                return self._json({"usuarios": m.usuarios()})
            if ruta == "/api/alumnado":
                return self._json(m.situacion_alumnado())
            if ruta == "/api/simulacion":
                return self._json(m.simulacion(q.get("unidad", ""), q.get("siglas", ""), q.get("criterio", "")))
            if ruta == "/api/actividad":
                return self._json(m.actividad())
            if ruta == "/datos/exportar":
                m.usuario = self._usuario(q)
                datos = m.exportar_datos()
                m.anotar_actividad("Exportar datos", f"{len(datos) // 1024} KB")
                nombre = f"WebPEC_datos_{datetime.now():%Y%m%d_%H%M}.zip"
                return self._fichero(datos, nombre, "application/zip", True)
            if ruta == "/evaluacion":
                m.usuario = self._usuario(q)
                grupo, excel = q.get("grupo", ""), q.get("formato") == "xlsx"
                datos = m.informe_evaluacion_xlsx(grupo) if excel else \
                    evaluacion_html(m.informe_evaluacion(grupo)).encode("utf-8")
                m.anotar_actividad("Informe para la evaluación", f"{grupo or 'todos los grupos'} "
                                   f"({'Excel' if excel else 'para imprimir'})")
                if excel:
                    nombre = f"Evaluacion_{motor_pec.para_fichero(grupo) or 'todos'}_{datetime.now():%Y%m%d}.xlsx"
                    return self._fichero(datos, nombre,
                                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True)
                return self._enviar(200, datos, "text/html; charset=utf-8")
            if ruta == "/api/config":
                # Lo hecho al migrar los datos se muestra una vez, al abrir la página
                migracion, m.migracion = m.migracion, []
                return self._json({"config": m.config(), "version": VERSION,
                                   "conversor_detectado": motor_pec.nombre_conversor("auto"),
                                   "thunderbird": motor_pec.buscar_thunderbird() or "",
                                   "carpeta": str(m.base), "migracion": migracion})
            if ruta == "/informe":
                fichero = m.ruta_informe(q.get("id", ""))
                return self._fichero(fichero.read_bytes(), fichero.name, "application/pdf",
                                     "descargar" in q)
            if ruta == "/documento":
                fichero = m.ruta_documento(q.get("carpeta", ""), q.get("ruta", ""))
                tipo = mimetypes.guess_type(fichero.name)[0] or "application/octet-stream"
                return self._fichero(fichero.read_bytes(), fichero.name, tipo,
                                     "descargar" in q or not fichero.name.lower().endswith(".pdf"))
            if ruta == "/imprimir":
                datos = m.unir_pdf(q.get("carpeta", ""), q.get("r", []))
                return self._fichero(datos, "WebPEC_imprimir.pdf", "application/pdf", False)
            if ruta == "/correo.eml":
                nombre, datos = m.eml(q.get("carpeta", ""), q.get("ruta", ""))
                return self._fichero(datos, nombre, "message/rfc822", True)
            if ruta == "/zip":
                datos = m.zip_documentos(q.get("carpeta", ""), q.get("r", []))
                return self._fichero(datos, "WebPEC_avisos.zip", "application/zip", True)
        self._json({"error": "No encontrado"}, 404)

    def _usuario(self, q):
        """Quién usa WebPEC: lo manda la página en cada petición (cabecera o ?usuario=)."""
        return unquote(self.headers.get("X-WebPEC-Usuario") or q.get("usuario") or "").strip()

    def _cuerpo(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > TAMANO_MAXIMO:
            raise ErrorPEC("El fichero es demasiado grande")
        return self.rfile.read(largo)

    def _post(self, ruta, q):
        m = self.motor
        if ruta == "/api/salir":
            self._json({"ok": True})
            print("\nWebPEC cerrado desde el navegador")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if ruta == "/api/actualizar":
            self._leer_json()
            usuario = self._usuario(q)
            if not usuario:
                raise ErrorPEC("Indica quién eres (arriba a la derecha) antes de actualizar")
            with CERROJO:
                r = descargar_actualizacion(m.config())
                m.usuario = usuario
                m.anotar_actividad("Actualizar WebPEC", f"{VERSION} → {r['version']}")
            self._json(r)
            print(f"\nActualizando WebPEC a la versión {r['version']}…")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        datos = self._cuerpo() if ruta in FICHEROS_SUBIDOS else self._leer_json()
        usuario = self._usuario(q)
        if not usuario and ruta != "/api/profesor/nuevo":
            raise ErrorPEC("Indica quién eres (arriba a la derecha) antes de hacer cambios")
        with CERROJO:
            m.usuario = usuario
            hecho = self._accion(m, ruta, q, datos)
            if hecho is None:
                return self._json({"error": "No encontrado"}, 404)
            respuesta, accion, detalle = hecho
            if accion:
                m.anotar_actividad(accion, detalle)
        self._json(respuesta)

    @staticmethod
    def _accion(m, ruta, q, d):
        """Hace la acción pedida. Devuelve (respuesta, acción para la actividad o None, detalle)."""
        if ruta == "/api/subir":
            nombre = m.subir(q.get("nombre", "informe.pdf"), d)
            return {"archivo": nombre}, "Subir informe", nombre
        if ruta == "/api/procesar":
            r = m.procesar()
            return r, "Procesar informes" if r["informes"] else None, \
                f"{len(r['informes'])} informes: {r['avisos']} avisos y {r['perdidas']} pérdidas"
        if ruta == "/api/informe/reprocesar":
            if d.get("simular"):
                return m.reprocesar(d.get("id", ""), simular=True), None, ""
            r = m.reprocesar(d.get("id", ""), d.get("alumnos"))
            return r, "Reprocesar informe", \
                f"{d.get('id', '').split('/')[-1]}: {r['avisos']} avisos y {r['perdidas']} pérdidas"
        if ruta == "/api/informe/borrar":
            m.borrar_informe(d.get("id", ""))
            return {"ok": True}, "Quitar informe pendiente", d.get("id", "")
        if ruta == "/api/profesor":
            m.registrar_profesor(d.get("profesor"), d.get("firma"))
            return {"ok": True}, "Guardar profesor/a", f"{d.get('profesor')} → {d.get('firma')}"
        if ruta == "/api/profesor/nuevo":
            r = m.nuevo_profesor(d.get("nombre"), d.get("apellidos"))
            m.usuario = m.usuario or r["firma"]  # quien se da de alta a sí mismo
            return r, "Alta de profesor/a" if r["nuevo"] else None, r["firma"]
        if ruta == "/api/profesor/vincular":
            r = m.vincular_profesor(d.get("profesor", ""), d.get("existente", ""))
            return r, "Reconocer profesor/a del informe", f"{d.get('existente')} → {d.get('profesor')} ({r['firma']})"
        if ruta == "/api/correo":
            r = m.preparar_correos(d.get("carpeta", ""), d.get("rutas", []))
            return r, "Preparar correos" if r["programa"] == "thunderbird" else "Descargar correos (.eml)", \
                ", ".join(x.split("/")[-1] for x in d.get("rutas", []))
        if ruta == "/api/profesor/borrar":
            m.borrar_profesor(d.get("profesor", ""))
            return {"ok": True}, "Borrar profesor/a", d.get("profesor", "")
        if ruta == "/api/modulo":
            criterio = d.get("criterio") or motor_pec.CRITERIO_NUEVOS
            m.registrar_modulo(d.get("unidad"), d.get("en_informe"), d.get("profesor", ""),
                               d.get("horas"), d.get("siglas"), d.get("nombre"), criterio)
            return {"ok": True}, "Registrar módulo", \
                f"{d.get('unidad')} {d.get('siglas')}: {d.get('horas')} h, cuentan {criterio}"
        if ruta == "/api/modulo/actualizar":
            r = m.actualizar_modulo(d.get("fila"), d.get("horas"), d.get("nombre"), d.get("siglas"), d.get("criterio"))
            cambio = f"; criterio de faltas: {r['criterio_anterior']} → {r['criterio']}" \
                if r["criterio"] != r["criterio_anterior"] else ""
            return dict(r, ok=True), "Cambiar módulo", \
                f"{r['modulo']}: {d.get('nombre')}, {d.get('horas')} h{cambio}"
        if ruta == "/api/modulo/borrar":
            m.borrar_modulo(d.get("fila"))
            return {"ok": True}, "Borrar módulo", f"fila {d.get('fila')}"
        if ruta == "/api/anular":
            r = m.anular(d.get("documentos", []), d.get("motivo", ""))
            return r, "Anular avisos", f"{', '.join(d.get('documentos', []))} — motivo: {d.get('motivo', '')}"
        if ruta == "/api/documentos/mover":
            n = m.mover_documentos(d.get("carpeta", ""), d.get("rutas", []), d.get("accion", ""))
            accion = "Marcar como entregados" if d.get("accion") == "realizados" else "Volver a pendientes"
            return {"ok": True, "movidos": n}, accion if n else None, \
                ", ".join(r.split("/")[-1] for r in d.get("rutas", []))
        if ruta == "/api/config":
            return {"config": motor_pec.guardar_configuracion(m.base, d)}, "Cambiar configuración", ""
        if ruta == "/api/procesados/borrar":
            n = m.borrar_procesados()
            return {"borrados": n}, "Borrar informes procesados", f"{n} informes"
        if ruta == "/api/documentos/borrar_todos":
            n = m.borrar_todos_documentos(d.get("cuales", ""))
            return {"borrados": n}, "Borrar avisos", f"{d.get('cuales')}: {n} documentos"
        if ruta == "/api/registro/vaciar":
            r = m.vaciar_registro()
            return r, "Vaciar registro", f"{r['borrados']} anotaciones; copia {r['copia']}"
        if ruta == "/api/modulos/vaciar":
            r = m.vaciar_hoja()
            return r, "Vaciar módulos y profesorado", f"copia {r['copia']}"
        if ruta == "/api/correos/importar":
            r = m.importar_correos(q.get("nombre", ""), d, q.get("grupo", ""))
            return r, "Importar correos del alumnado", \
                f"{q.get('nombre', '')}: {r['nuevos']} nuevos, {r['actualizados']} actualizados"
        if ruta == "/api/alumno/editar":
            r = m.editar_alumno(d.get("grupo", ""), d.get("alumno", ""), d.get("apellidos", ""),
                                d.get("nombre", ""), d.get("correo", ""))
            return r, "Editar alumno/a", f"{d.get('alumno')} ({d.get('grupo')}): {r['nombre']}, {r['correo'] or 'sin correo'}"
        if ruta == "/api/alumno/baja":
            r = m.dar_de_baja(d.get("grupo", ""), d.get("alumno", ""), d.get("modulos", []), d.get("motivo", ""))
            return r, "Dar de baja a alumno/a", f"{d.get('alumno')} ({d.get('grupo')}): " + \
                (", ".join(d.get("modulos") or []) or "todos los módulos") + \
                (f" — motivo: {d.get('motivo')}" if d.get("motivo") else "")
        if ruta == "/api/alumno/recuperar":
            m.recuperar_alumno(d.get("grupo", ""), d.get("alumno", ""), d.get("modulo", ""))
            return {"ok": True}, "Recuperar alumno/a dado de baja", \
                f"{d.get('alumno')} ({d.get('grupo')}): {d.get('modulo') or 'todos los módulos'}"
        if ruta == "/api/datos/importar":
            r = m.importar_datos(d)
            return r, "Importar datos", f"{q.get('nombre', '')}: {r['ficheros']} ficheros; copia {r['copia']}"
        return None

    def _estatico(self, nombre):
        ruta = (WEB / nombre).resolve()
        if WEB.resolve() not in ruta.parents or not ruta.is_file():
            return self._json({"error": "No encontrado"}, 404)
        tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
            tipo += "; charset=utf-8"
        self._enviar(200, ruta.read_bytes(), tipo)


# ------------------------------------------------------------- manual ---
# El manual se escribe una sola vez, en MANUAL_USUARIO.md, y aquí se convierte en página web.
# Solo se admite lo que usa el manual: títulos, párrafos, listas (también anidadas), tablas,
# citas, separadores, negrita, cursiva, código y enlaces.

MARCA_LISTA = re.compile(r"^( *)(?:[-*]|\d+\.)\s+(.*)$")


def md_en_linea(texto):
    t = escape(texto, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    t = re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1" target="_blank" rel="noopener">\1</a>', t)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)


def md_lista(lineas, i, sangria):
    ordenada = bool(re.match(r"^\s*\d+\.", lineas[i]))
    html = ["<ol>" if ordenada else "<ul>"]
    while i < len(lineas):
        m = MARCA_LISTA.match(lineas[i])
        if not m or len(m.group(1)) != sangria:
            break
        elemento, i = md_en_linea(m.group(2)), i + 1
        # Líneas que continúan el elemento (sangradas y sin marca de lista)
        while i < len(lineas) and lineas[i].startswith(" " * (sangria + 2)) and not MARCA_LISTA.match(lineas[i]):
            elemento += " " + md_en_linea(lineas[i].strip())
            i += 1
        siguiente = MARCA_LISTA.match(lineas[i]) if i < len(lineas) else None
        if siguiente and len(siguiente.group(1)) > sangria:
            sublista, i = md_lista(lineas, i, len(siguiente.group(1)))
            elemento += sublista
        html.append(f"<li>{elemento}</li>")
    html.append("</ol>" if ordenada else "</ul>")
    return "".join(html), i


def markdown_html(md):
    lineas, html, i = md.splitlines(), [], 0
    inicio_bloque = re.compile(r"^(#{1,3} |---+\s*$|>|\||(?:[-*]|\d+\.)\s)")
    while i < len(lineas):
        linea = lineas[i]
        if not linea.strip():
            i += 1
        elif m := re.match(r"^(#{1,3}) (.*)$", linea):
            nivel = len(m.group(1))
            html.append(f"<h{nivel}>{md_en_linea(m.group(2))}</h{nivel}>")
            i += 1
        elif re.match(r"^---+\s*$", linea):
            html.append("<hr>")
            i += 1
        elif linea.startswith(">"):
            texto = []
            while i < len(lineas) and lineas[i].startswith(">"):
                texto.append(lineas[i].lstrip("> ").strip())
                i += 1
            html.append(f"<blockquote><p>{md_en_linea(' '.join(texto))}</p></blockquote>")
        elif linea.startswith("|"):
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|?\s*$", lineas[i]):
                    filas.append([c.strip() for c in lineas[i].strip().strip("|").split("|")])
                i += 1
            cabecera = "".join(f"<th>{md_en_linea(c)}</th>" for c in filas[0])
            cuerpo = "".join("<tr>" + "".join(f"<td>{md_en_linea(c)}</td>" for c in f) + "</tr>"
                             for f in filas[1:])
            html.append(f"<table><thead><tr>{cabecera}</tr></thead><tbody>{cuerpo}</tbody></table>")
        elif MARCA_LISTA.match(linea):
            lista, i = md_lista(lineas, i, len(MARCA_LISTA.match(linea).group(1)))
            html.append(lista)
        else:
            texto = []
            while i < len(lineas) and lineas[i].strip() and not inicio_bloque.match(lineas[i]):
                texto.append(lineas[i].strip())
                i += 1
            html.append(f"<p>{md_en_linea(' '.join(texto))}</p>")
    return "\n".join(html)


def escudo_en_linea():
    try:
        return "data:image/png;base64," + base64.b64encode((WEB / "escudo.png").read_bytes()).decode()
    except OSError:
        return ""


def evaluacion_html(datos):
    """Página para imprimir (o guardar en PDF) con la situación de cada grupo, para la sesión de evaluación."""
    e = escape

    def casilla(c):
        if not c:
            return '<td class="nada">—</td>'
        if c["estado"] == "baja":
            return '<td class="baja">Baja</td>'
        marca = {"aviso": f'<b>Aviso</b> {e(c["fecha_aviso"][:5])}' + (" · ≥ 15 %" if c.get("supera_15") else ""),
                 "perdida": f'<b>Pérdida</b> {e(c["fecha_perdida"][:5])}',
                 "supera": "<b>≥ 7,5 %</b> sin aviso"}.get(c["estado"], "")
        fj = f' <span class="fj">+ {c["fj"]} FJ</span>' if c.get("fj") and c.get("criterio") == motor_pec.FI_FJ else \
            (f' <span class="fj no-cuenta" title="Justificadas: en este módulo no cuentan">({c["fj"]} FJ)</span>' if c.get("fj") else "")
        return (f'<td class="{c["estado"]}"><span class="fi">{c["fi"]} FI</span>{fj} <span class="pc">{e(c["porcentaje"])} %</span>'
                + (f'<span class="marca">{marca}</span>' if marca else "") + "</td>")

    secciones = []
    for g in datos["grupos"]:
        r = g["resumen"]
        cabeza = "".join(f'<th title="{e(m["nombre"])}">{e(m["siglas"])}</th>' for m in g["modulos"])
        filas = "".join(
            f'<tr><td class="alumno">{e(a["nombre"])}</td>'
            + "".join(casilla(a["modulos"].get(m["siglas"])) for m in g["modulos"])
            + f'<td class="num">{a["avisos"] or ""}</td><td class="num">{a["perdidas"] or ""}</td></tr>'
            for a in g["alumnos"])
        modulos = "".join(
            f'<tr><td><b>{e(m["siglas"])}</b></td><td>{e(m["nombre"])}</td><td>{e(m["profesor"])}</td>'
            f'<td class="num">{e(m["horas"])}</td><td class="num">{e(m["umbral_75"])}</td>'
            f'<td class="num">{e(m["umbral_15"])}</td><td>{e(m["informe"])}</td>'
            f'<td>{e(motor_pec.CRITERIOS[m["criterio"]])}</td></tr>' for m in g["modulos"])
        bajas = "" if not g["bajas"] else (
            '<h3>Alumnado dado de baja</h3><table class="lista"><tr><th>Alumno/a</th><th>Módulo</th><th>Fecha</th>'
            '<th>Motivo</th></tr>' + "".join(
                f'<tr><td>{e(b["nombre"])}</td><td>{e(b["nombre_modulo"] or "Todos los módulos")}</td>'
                f'<td>{e(motor_pec.fecha_legible(b["fecha"][:10]))}</td><td>{e(b["motivo"])}</td></tr>'
                for b in g["bajas"]) + "</table>")
        secciones.append(f"""<section>
<div class="titulo"><img src="{escudo_en_linea()}" alt=""><div><h1>Grupo {e(g["grupo"])}</h1>
<p>{e(datos["centro"])} · Faltas y avisos de pérdida de evaluación continua · {e(datos["fecha"])}</p></div></div>
<ul class="resumen"><li><b>{r["alumnos"]}</b> alumnos/as</li>
<li><b>{r["con_aviso"]}</b> con aviso del 7,5 % ({r["avisos"]} {"aviso" if r["avisos"] == 1 else "avisos"})</li>
<li><b>{r["con_perdida"]}</b> con pérdida del 15 % ({r["perdidas"]} {"pérdida" if r["perdidas"] == 1 else "pérdidas"})</li>
{f'<li class="ojo"><b>{r["supera"]}</b> superan el 7,5 % sin aviso</li>' if r["supera"] else ""}</ul>
<table class="matriz"><thead><tr><th class="alumno">Alumno/a</th>{cabeza}<th>Avisos<br>7,5 %</th><th>Pérdidas<br>15 %</th></tr></thead>
<tbody>{filas}</tbody></table>
<p class="leyenda">Cada casilla: faltas injustificadas (FI), justificadas (FJ) y % de las horas del módulo, según el último
informe procesado. El % cuenta las faltas según el criterio del módulo (tabla de abajo): con «solo FI», las FJ van entre
paréntesis y no cuentan.
<span class="aviso">Aviso</span> aviso del 7,5 % (fecha del informe) · <span class="perdida">Pérdida</span> pérdida del 15 % ·
<span class="supera">≥ 7,5 % sin aviso</span> le corresponde un aviso que aún no tiene · <span class="baja">Baja</span> dado/a de
baja en ese módulo · — no aparece en el informe del módulo.</p>
<h3>Módulos</h3><table class="lista"><tr><th>Siglas</th><th>Módulo</th><th>Profesor/a</th><th>Horas</th><th>7,5 %</th>
<th>15 %</th><th>Último informe</th><th>Faltas que cuentan</th></tr>{modulos}</table>
{bajas}</section>""")
    if not secciones:
        secciones.append("<section><p>No hay informes procesados con datos de alumnado.</p></section>")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WebPEC · Informe para la evaluación</title>
<style>
  :root {{ --texto: #1e293b; --suave: #64748b; --linea: #cbd5e1; --principal: #0f766e; }}
  body {{ margin: 0; background: #f5f7fb; color: var(--texto); font: 13px/1.45 system-ui, "Segoe UI", sans-serif; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 20px 16px 50px; }}
  .botones {{ display: flex; gap: 10px; margin-bottom: 16px; }}
  .botones button {{ font: inherit; font-weight: 600; padding: 7px 14px; border-radius: 999px; border: 1px solid var(--linea);
    background: #fff; color: var(--principal); cursor: pointer; }}
  section {{ background: #fff; padding: 18px 20px; border-radius: 12px; margin-bottom: 24px; }}
  .titulo {{ display: flex; gap: 12px; align-items: center; }} .titulo img {{ height: 52px; }}
  h1 {{ margin: 0; font-size: 21px; }} .titulo p {{ margin: 2px 0 0; color: var(--suave); }}
  h3 {{ margin: 18px 0 6px; font-size: 14px; }}
  .resumen {{ display: flex; flex-wrap: wrap; gap: 6px 22px; list-style: none; padding: 0; margin: 12px 0; }}
  .resumen .ojo {{ color: #3730a3; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid var(--linea); padding: 4px 6px; vertical-align: middle; }}
  th {{ background: #eef2f7; font-size: 12px; }}
  .matriz td {{ text-align: center; white-space: nowrap; }} .matriz td.alumno {{ white-space: normal; }}
  .matriz td.num {{ text-align: center; }}
  .matriz {{ width: auto; min-width: 55%; }} .matriz td, .matriz th {{ min-width: 82px; }}
  .matriz th.alumno, .matriz td.alumno {{ text-align: left; min-width: 250px; }}
  .fi {{ font-weight: 700; }} .pc {{ color: var(--suave); font-size: 11.5px; }}
  .fj {{ font-weight: 600; }} .fj.no-cuenta {{ font-weight: 400; color: var(--suave); }}
  .marca {{ display: block; font-size: 11px; }}
  .aviso {{ background: #fef3c7; }} .perdida {{ background: #ffe4e6; }} .supera {{ background: #e0e7ff; }}
  .baja {{ background: #e2e8f0; color: var(--suave); }} .nada {{ color: var(--suave); }}
  .leyenda {{ color: var(--suave); font-size: 11.5px; margin: 8px 0 0; }}
  .leyenda span {{ padding: 0 4px; border-radius: 3px; color: var(--texto); }}
  .num {{ text-align: right; }} .lista td, .lista th {{ text-align: left; }}
  @page {{ size: A4 landscape; margin: 10mm; }}
  @media print {{
    body {{ background: #fff; font-size: 11px; }} main {{ padding: 0; max-width: none; }} .botones {{ display: none; }}
    section {{ padding: 0; margin: 0; border-radius: 0; break-after: page; }} section:last-child {{ break-after: auto; }}
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    tr {{ break-inside: avoid; }} thead {{ display: table-header-group; }}
  }}
</style></head>
<body><main>
<div class="botones"><button onclick="window.print()">Imprimir o guardar en PDF</button></div>
{"".join(secciones)}
</main></body></html>"""


def manual_html(para_pdf=False):
    """Página con el manual de usuario (para la pestaña Ayuda o para generar el PDF)."""
    try:
        md = MANUAL.read_text(encoding="utf-8")
    except OSError:
        md = "# Manual de usuario\n\nNo se encuentra MANUAL_USUARIO.md en la carpeta de WebPEC."
    escudo = escudo_en_linea()
    botones = "" if para_pdf else (
        '<div class="botones"><button onclick="window.print()">Imprimir o guardar en PDF</button>'
        + ('<a href="/manual.pdf?descargar=1">Descargar el manual en PDF</a>' if MANUAL_PDF.is_file() else "")
        + '<a href="/instrucciones" target="_blank">Instrucciones rápidas (una página)</a>'
        + "</div>")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WebPEC {escape(VERSION)} · Manual de usuario</title>
<style>
  :root {{ --texto: #1e293b; --suave: #64748b; --linea: #e2e8f0; --principal: #0f766e; }}
  body {{ margin: 0; background: #f5f7fb; color: var(--texto); font: 15px/1.6 system-ui, "Segoe UI", sans-serif; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 60px; }}
  .cabecera {{ display: flex; align-items: center; gap: 14px; }}
  .cabecera img {{ height: 64px; }}
  .botones {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0 6px; }}
  .botones button, .botones a {{ font: inherit; font-weight: 600; padding: 7px 14px; border-radius: 999px;
    border: 1px solid var(--linea); background: #fff; color: var(--principal); cursor: pointer; text-decoration: none; }}
  h1 {{ font-size: 28px; margin: 0; }} h2 {{ margin-top: 34px; padding-bottom: 4px; border-bottom: 2px solid var(--linea); }}
  h3 {{ margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; background: #fff; font-size: 14px; }}
  th, td {{ border: 1px solid var(--linea); padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #eef2f7; }}
  code {{ background: #e9eef5; padding: 1px 5px; border-radius: 4px; font-size: 13px; overflow-wrap: anywhere; }}
  blockquote {{ margin: 14px 0; padding: 4px 16px; border-left: 4px solid #f59e0b; background: #fffbeb; }}
  hr {{ border: 0; border-top: 1px solid var(--linea); margin: 18px 0; }}
  a {{ color: var(--principal); }}
  @media print {{ body {{ background: #fff; font-size: 12.5px; }} .botones {{ display: none; }} main {{ padding: 0; }}
    h2 {{ break-after: avoid; }} table, blockquote {{ break-inside: avoid; }} }}
</style></head>
<body><main>
<div class="cabecera"><img src="{escudo}" alt=""><div><b>WebPEC {escape(VERSION)}</b><br>
<span style="color:var(--suave)">IES Rosa Chacel · Departamento de Informática</span></div></div>
{botones}
{markdown_html(md)}
</main></body></html>"""


def instrucciones_html(para_pdf=False):
    """Hoja de instrucciones rápidas (INSTRUCCIONES.html con la versión y el escudo puestos)."""
    try:
        html = INSTRUCCIONES.read_text(encoding="utf-8")
    except OSError:
        return "<!doctype html><meta charset=utf-8><p>No se encuentra INSTRUCCIONES.html en la carpeta de WebPEC.</p>"
    botones = "" if para_pdf else (
        '<div class="botones"><button onclick="window.print()">Imprimir</button>'
        + ('<a href="/instrucciones.pdf?descargar=1">Descargar en PDF</a>' if INSTRUCCIONES_PDF.is_file() else "")
        + '<a href="/ayuda">Manual completo</a></div>')
    return (html.replace("{{VERSION}}", escape(VERSION)).replace("{{ESCUDO}}", escudo_en_linea())
            .replace("<!--BOTONES-->", botones))


def ya_en_marcha(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


# ------------------------------------------------------ actualizaciones ---
# Las versiones se publican en GitHub (Releases), con el ZIP como fichero adjunto. La última se averigua
# mirando adónde redirige la página «latest» (…/releases/tag/vX.YY): no se usa la API de GitHub, que solo
# admite 60 consultas por hora desde una misma dirección (todo el instituto sale a Internet con una).
# No se envía ningún dato: solo se pide esa página y, al actualizar, el ZIP.

# WEBPEC_REPOSITORIO: otra dirección con la misma estructura (solo para pruebas)
REPOSITORIO = os.environ.get("WEBPEC_REPOSITORIO", "https://github.com/jj99211/WebPEC").rstrip("/")
ULTIMA_VERSION = REPOSITORIO + "/releases/latest"
CONSULTA_CADA = 6 * 3600       # como mucho, una consulta cada 6 horas (salvo «Comprobar ahora»)
MAXIMO_ZIP = 100 * 1024 * 1024
PREFIJO_TEMPORAL = "WebPEC_actualizacion_"
_consulta = {"cuando": 0.0, "datos": None}
PENDIENTE = {}  # versión descargada cuyo instalador se lanza al apagar el servidor


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def peticion(url, metodo="GET"):
    return urllib.request.Request(url, method=metodo, headers={"User-Agent": f"WebPEC/{VERSION}"})


def ultima_publicada():
    """Número de la última versión publicada en GitHub («3.40»)."""
    destino = ""
    try:
        urllib.request.build_opener(_SinRedireccion).open(peticion(ULTIMA_VERSION, "HEAD"), timeout=8)
    except urllib.error.HTTPError as e:
        destino = e.headers.get("Location", "") if e.code in (301, 302, 303, 307, 308) else ""
    m = re.search(r"/releases/tag/v(\d+\.\d+)/?$", destino)
    if not m:
        raise ErrorPEC("GitHub no ha indicado cuál es la última versión")
    return m.group(1)


def comprobar_actualizacion(config, forzar=False):
    """¿Hay una versión más moderna en GitHub? Sin Internet, devuelve el error sin más."""
    if config.get("buscar_actualizaciones") == "no" and not forzar:
        return {"activada": False, "actual": VERSION}
    if forzar or not _consulta["datos"] or time.time() - _consulta["cuando"] > CONSULTA_CADA:
        try:
            ultima = ultima_publicada()
        except (OSError, ErrorPEC) as e:
            motivo = getattr(e, "reason", None) or e
            return {"activada": True, "actual": VERSION, "error": f"No se ha podido consultar GitHub ({motivo})",
                    "descargas": ULTIMA_VERSION}
        _consulta.update(cuando=time.time(), datos={
            "activada": True, "actual": VERSION, "ultima": ultima,
            "hay_nueva": numero_version(ultima) > numero_version(VERSION),
            "novedades": f"{REPOSITORIO}/releases/tag/v{ultima}",
            "zip": f"{REPOSITORIO}/releases/download/v{ultima}/WebPEC_v{ultima}.zip",
            "descargas": ULTIMA_VERSION})
    return _consulta["datos"]


def limpiar_temporales(dias=1):
    """Borra las carpetas de actualizaciones anteriores (las deja el instalador, que se ejecuta desde ellas)."""
    limite = time.time() - dias * 24 * 3600
    for carpeta in Path(tempfile.gettempdir()).glob(PREFIJO_TEMPORAL + "*"):
        try:
            if carpeta.is_dir() and carpeta.stat().st_mtime < limite:
                shutil.rmtree(carpeta, ignore_errors=True)
        except OSError:
            pass


def se_puede_escribir(carpeta):
    try:
        with tempfile.NamedTemporaryFile(dir=carpeta):
            return True
    except OSError:
        return False


def descargar_actualizacion(config):
    """
    «Actualizar ahora»: descarga y comprueba el ZIP de la última versión y lo descomprime en una carpeta
    temporal. Su instalador se lanza cuando se apaga el servidor (ver lanzar_instalador_descargado).
    """
    info = comprobar_actualizacion(config, forzar=True)
    a_mano = f"Se puede descargar a mano desde {ULTIMA_VERSION}"
    if info.get("error"):
        raise ErrorPEC(f"{info['error']}. {a_mano}")
    if not info["hay_nueva"]:
        raise ErrorPEC(f"Ya tienes la última versión ({VERSION})")
    if not se_puede_escribir(BASE):
        raise ErrorPEC(f"No se puede escribir en la carpeta de WebPEC ({BASE}): pide ayuda para actualizarla. {a_mano}")
    limpiar_temporales()
    carpeta = Path(tempfile.mkdtemp(prefix=PREFIJO_TEMPORAL))
    ultima = info["ultima"]
    try:
        with urllib.request.urlopen(peticion(info["zip"]), timeout=90) as r:
            datos = r.read(MAXIMO_ZIP + 1)
        if len(datos) > MAXIMO_ZIP:
            raise ErrorPEC("el fichero descargado es demasiado grande")
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            nombres = z.namelist()
            if any(not n.startswith("WebPEC/") or ".." in PurePosixPath(n).parts for n in nombres) or \
                    "WebPEC/webpec.py" not in nombres or "WebPEC/VERSION" not in nombres:
                raise ErrorPEC("el ZIP descargado no es un paquete de WebPEC")
            if z.testzip() is not None:
                raise ErrorPEC("el ZIP descargado está dañado")
            if z.read("WebPEC/VERSION").decode("utf-8").strip() != ultima:
                raise ErrorPEC("el ZIP descargado no es de la versión anunciada")
            z.extractall(carpeta)
    except (OSError, zipfile.BadZipFile, ErrorPEC) as e:
        shutil.rmtree(carpeta, ignore_errors=True)
        motivo = getattr(e, "reason", None) or e
        raise ErrorPEC(f"No se ha podido descargar la versión {ultima} ({motivo}). {a_mano}")
    for lanzador in (carpeta / "WebPEC").glob("*.sh"):
        try:
            lanzador.chmod(0o755)
        except OSError:
            pass
    PENDIENTE.update(instalador=carpeta / "WebPEC" / "webpec.py", version=ultima)
    return {"ok": True, "version": ultima}


def lanzar_instalador_descargado():
    """
    Con el servidor ya apagado, el instalador de la versión descargada actualiza esta carpeta y arranca la
    versión nueva. Todo sigue en esta misma ventana (este proceso espera a que termine).
    """
    print("=" * 62)
    print(f"  Instalando WebPEC {PENDIENTE['version']} (los datos no se tocan)…")
    print("=" * 62)
    orden = [sys.executable, str(PENDIENTE["instalador"]), "--instalar", "--destino", str(BASE),
             "--sin-navegador"]  # la pestaña del navegador ya abierta se recarga sola
    sys.exit(subprocess.call(orden, cwd=str(BASE)))


# ------------------------------------------------------- acceso directo ---

DESCRIPCION = "Avisos de pérdida de evaluación continua"


def crear_acceso_directo():
    """Crea el icono de WebPEC en el escritorio. Devuelve un texto con lo que se ha hecho."""
    if os.name == "nt":
        return acceso_windows()
    if sys.platform.startswith("linux"):
        return acceso_linux()
    raise RuntimeError("Solo se pueden crear accesos directos en Windows y Linux")


def acceso_windows():
    def texto(ruta):  # cadena entre comillas simples de PowerShell
        return "'" + str(ruta).replace("'", "''") + "'"

    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$escritorio = [Environment]::GetFolderPath('Desktop')",
        "$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut("
        "(Join-Path $escritorio 'WebPEC.lnk'))",
        f"$acceso.TargetPath = {texto(BASE / 'WebPEC.bat')}",
        f"$acceso.WorkingDirectory = {texto(BASE)}",
        f"$acceso.IconLocation = {texto(BASE / 'web' / 'escudo.ico')} + ',0'",
        "$acceso.WindowStyle = 7",  # ventana del servidor minimizada
        f"$acceso.Description = {texto('WebPEC - ' + DESCRIPCION)}",
        "$acceso.Save()",
    ])
    with tempfile.TemporaryDirectory() as tmp:
        ps1 = Path(tmp) / "acceso_directo.ps1"
        ps1.write_text(script, encoding="utf-8-sig")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", str(ps1)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "PowerShell no ha podido crearlo")
    return "Creado el icono «WebPEC» en el escritorio."


def escritorio_linux():
    try:
        r = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5)
        carpeta = Path(r.stdout.strip())
        # xdg-user-dir devuelve la carpeta personal si no hay escritorio configurado
        if r.stdout.strip() and carpeta.is_dir() and carpeta != Path.home():
            return carpeta
    except (OSError, subprocess.SubprocessError):
        pass
    for nombre in ("Escritorio", "Desktop"):
        if (Path.home() / nombre).is_dir():
            return Path.home() / nombre
    return None


def acceso_linux():
    lanzador = BASE / "WebPEC.sh"
    try:
        lanzador.chmod(0o755)
    except OSError:
        pass  # en discos NTFS o FAT no se pueden cambiar permisos (ya son ejecutables)
    exec_ = '"' + "".join("\\" + c if c in '"`$\\' else c for c in str(lanzador)) + '"'
    contenido = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        "Name=WebPEC",
        f"Comment={DESCRIPCION}",
        f"Exec={exec_}",
        f"Path={BASE}",
        f"Icon={BASE / 'web' / 'escudo.png'}",
        "Terminal=true",
        "Categories=Office;",
        "",
    ])
    datos = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    destinos = [("en el menú de aplicaciones", datos / "applications")]
    escritorio = escritorio_linux()
    if escritorio:
        destinos.insert(0, ("en el escritorio", escritorio))
    hechos = []
    for donde, carpeta in destinos:
        carpeta.mkdir(parents=True, exist_ok=True)
        fichero = carpeta / "WebPEC.desktop"
        fichero.write_text(contenido, encoding="utf-8")
        fichero.chmod(0o755)
        if shutil.which("gio"):  # GNOME: marcarlo como de confianza para poder abrirlo
            subprocess.run(["gio", "set", str(fichero), "metadata::trusted", "true"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        hechos.append(donde)
    mensaje = f"Creado el icono «WebPEC» {' y '.join(hechos)}."
    if escritorio:
        mensaje += ("\nSi al abrirlo el escritorio pregunta, elige «Permitir ejecución» "
                    "(KDE) o «Permitir lanzar» (GNOME).")
    if shutil.which("notify-send"):  # aviso visible si se ha lanzado sin terminal
        subprocess.run(["notify-send", "-i", str(BASE / "web" / "escudo.png"), "WebPEC",
                        mensaje.splitlines()[0]],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return mensaje


def configuracion_previa(datos, programa=BASE):
    """Configuración para saber el puerto antes de abrir (y migrar) los datos."""
    for carpeta in (datos, programa):
        if (carpeta / motor_pec.CONFIGURACION).exists():
            return motor_pec.leer_configuracion(carpeta)
    return motor_pec.leer_configuracion(datos)


# ----------------------------------------------------------- instalador ---

# Ficheros de versiones anteriores que ya no forman parte del programa (al actualizar se quitan)
OBSOLETOS = ["Crear_acceso_directo.bat", "Crear_acceso_directo.sh", "LEEME.txt"]
# Lo que hay en la carpeta y no es programa: no se copia al instalar en otra carpeta
NO_PROGRAMA = {motor_pec.DATOS, "__pycache__", *motor_pec.DATOS_2X}


def salida_powershell(orden):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", orden],
                       capture_output=True, text=True, timeout=20)
    return r.stdout.strip()


def carpeta_documentos():
    try:
        if os.name == "nt":
            carpeta = Path(salida_powershell("[Environment]::GetFolderPath('MyDocuments')"))
        else:
            carpeta = Path(subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True,
                                          text=True, timeout=5).stdout.strip())
        if str(carpeta) not in ("", ".") and carpeta.is_dir() and carpeta != Path.home():
            return carpeta
    except (OSError, subprocess.SubprocessError):
        pass
    for nombre in ("Documentos", "Documents"):
        if (Path.home() / nombre).is_dir():
            return Path.home() / nombre
    return Path.home()


def instalacion_existente():
    """Carpeta de WebPEC a la que apunta el icono del escritorio (o del menú), si lo hay."""
    candidatos = []
    try:
        if os.name == "nt":
            candidatos.append(salida_powershell(
                "$l = Join-Path ([Environment]::GetFolderPath('Desktop')) 'WebPEC.lnk'; "
                "if (Test-Path $l) { (New-Object -ComObject WScript.Shell).CreateShortcut($l).WorkingDirectory }"))
        else:
            datos = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
            for carpeta in (escritorio_linux(), datos / "applications"):
                fichero = (carpeta or Path("/nonexistent")) / "WebPEC.desktop"
                if fichero.is_file():
                    m = re.search(r"^Path=(.+)$", fichero.read_text(encoding="utf-8"), re.M)
                    if m:
                        candidatos.append(m.group(1).strip())
    except (OSError, subprocess.SubprocessError):
        pass
    for c in candidatos:
        if c and (Path(c) / "webpec.py").is_file():
            return Path(c).resolve()
    return None


def version_de(carpeta):
    try:
        return (carpeta / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "?"


def numero_version(texto):
    try:
        return float(texto)
    except ValueError:
        return 0.0


def preguntar(texto, defecto=""):
    try:
        respuesta = input(texto).strip()
    except EOFError:  # sin teclado (p. ej. lanzado sin terminal): la opción por defecto
        respuesta = ""
    return respuesta or defecto


def elegir_destino():
    """Pregunta dónde instalar. Devuelve la carpeta elegida."""
    existente = instalacion_existente()
    opciones = []
    if existente and existente != BASE:
        opciones.append((f"Actualizar la instalación que ya hay en {existente} "
                         f"(versión {version_de(existente)}). Sus datos se conservan.", existente))
    if existente == BASE:
        opciones.append((f"Esta misma carpeta, que es la instalada: {BASE}", BASE))
    nueva = carpeta_documentos() / "WebPEC"
    if nueva not in (BASE, existente):
        opciones.append((f"Instalar en {nueva}", nueva))
    if existente != BASE:
        opciones.append((f"Dejar WebPEC en esta carpeta, donde está ahora: {BASE}", BASE))
    opciones.append(("Otra carpeta (escribir la ruta)", None))
    print("  ¿Dónde quieres instalar WebPEC?")
    for n, (texto, _) in enumerate(opciones, 1):
        print(f"    {n}) {texto}")
    while True:
        eleccion = preguntar("  Escribe el número y pulsa Intro [1]: ", "1")
        if eleccion.isdigit() and 1 <= int(eleccion) <= len(opciones):
            break
        print("  Opción no válida.")
    destino = opciones[int(eleccion) - 1][1]
    if destino is None:
        texto = preguntar("  Carpeta: ").strip('"\'')
        if not texto:
            sys.exit("No se ha indicado ninguna carpeta: no se instala nada.")
        destino = Path(os.path.expandvars(os.path.expanduser(texto)))
        # Una carpeta con otras cosas (p. ej. Documentos): WebPEC va dentro, en su propia carpeta
        if not (destino / "webpec.py").is_file() and destino.is_dir() and any(destino.iterdir()):
            destino = destino / "WebPEC"
    return destino.resolve()


def esperar_cerrado(destino, segundos=None):
    """
    Antes de sustituir el programa, la instalación de destino no debe estar en marcha. Sin segundos, pregunta
    hasta que se cierre; con segundos (actualización sin preguntas), espera como mucho ese tiempo.
    Devuelve True si está cerrada.
    """
    puerto = int(configuracion_previa(destino / motor_pec.DATOS, destino)["puerto"])
    limite = time.time() + (segundos or 0)
    while ya_en_marcha(puerto):
        if segundos is not None:
            if time.time() > limite:
                return False
            time.sleep(0.5)
            continue
        print(f"  WebPEC está abierto (puerto {puerto}). Ciérralo con su botón de apagado.")
        if preguntar("  Pulsa Intro cuando esté cerrado (o escribe n para cancelar): ").lower() == "n":
            sys.exit("Instalación cancelada: no se ha cambiado nada.")
    return True


COPIAS_PROGRAMA = 3  # copias del programa que se guardan antes de actualizar (las más recientes)


def copia_del_programa(destino):
    """Copia del programa instalado en destino (sin los datos) en DATOS/COPIAS_SEGURIDAD/, por si hay que volver atrás."""
    copias = destino / motor_pec.DATOS / motor_pec.COPIAS
    copia = copias / f"programa_v{version_de(destino)}_{datetime.now():%Y%m%d_%H%M%S}"
    copia.mkdir(parents=True)
    for origen in destino.iterdir():
        if origen.name not in NO_PROGRAMA:
            copiar(origen, copia / origen.name)
    for vieja in sorted(copias.glob("programa_v*"), key=lambda c: c.stat().st_mtime)[:-COPIAS_PROGRAMA]:
        shutil.rmtree(vieja, ignore_errors=True)
    return copia


def copiar(origen, destino):
    """
    Copia un fichero o carpeta (sin __pycache__). Solo escribe los ficheros que cambian, y cada uno a través de
    un temporal: así un lanzador en marcha (WebPEC.sh, WebPEC.bat) no se reescribe por debajo si no ha cambiado.
    """
    if origen.is_dir():
        if origen.name != "__pycache__":
            destino.mkdir(parents=True, exist_ok=True)
            for hijo in origen.iterdir():
                copiar(hijo, destino / hijo.name)
    elif not (destino.is_file() and filecmp.cmp(origen, destino, shallow=False)):
        temporal = destino.with_name(destino.name + ".nuevo")
        shutil.copy2(origen, temporal)
        os.replace(temporal, destino)


def copiar_programa(destino):
    """Copia el programa (no los datos) a destino y quita los ficheros que ya no se usan."""
    destino.mkdir(parents=True, exist_ok=True)
    for origen in BASE.iterdir():
        if origen.name not in NO_PROGRAMA:
            copiar(origen, destino / origen.name)
    for nombre in OBSOLETOS:
        (destino / nombre).unlink(missing_ok=True)
    shutil.rmtree(destino / "__pycache__", ignore_errors=True)
    for lanzador in destino.glob("*.sh"):
        try:
            lanzador.chmod(0o755)
        except OSError:
            pass


def instalar(preguntar_destino=True, sin_navegador=False):
    """
    --instalar: elige la carpeta (la instalación que ya haya, Documentos u otra), copia allí el
    programa sin tocar los datos, crea el icono y arranca. Si la carpeta es otra, se sigue desde
    la copia instalada y esta función no vuelve.
    """
    print("=" * 62)
    print(f"  Instalación de WebPEC {VERSION}")
    print("=" * 62)
    print(f"  Python {sys.version.split()[0]}: correcto")
    destino = elegir_destino() if preguntar_destino else BASE
    if destino != BASE:
        instalada = version_de(destino)
        if numero_version(instalada) > numero_version(VERSION):
            print(f"  OJO: en {destino} hay una versión más moderna ({instalada}) que esta ({VERSION}).")
            if preguntar("  ¿Instalar de todos modos? [s/N]: ").lower() != "s":
                sys.exit("Instalación cancelada: no se ha cambiado nada.")
        esperar_cerrado(destino)
        if (destino / "webpec.py").is_file():
            print(f"  Copia del programa actual: {copia_del_programa(destino)}")
        print(f"  Copiando el programa a {destino} (los datos no se tocan)…")
        copiar_programa(destino)
        print(f"  Hecho. La carpeta descomprimida ({BASE}) ya no hace falta: puedes borrarla.")
        print()
        orden = [sys.executable, str(destino / "webpec.py"), "--instalar", "--aqui"]
        sys.exit(subprocess.call(orden + (["--sin-navegador"] if sin_navegador else []), cwd=destino))
    print(f"  Carpeta del programa: {BASE}")
    try:
        print("  " + crear_acceso_directo().replace("\n", "\n  "))
    except (RuntimeError, OSError) as e:
        print(f"  AVISO: no se ha podido crear el icono del escritorio ({e}).")
        print("  WebPEC funciona igual: se puede arrancar con WebPEC.bat o WebPEC.sh.")
    print("  Si mueves la carpeta de WebPEC, vuelve a ejecutar el instalador.")
    print()


def actualizar_sin_preguntas(destino, sin_navegador=False):
    """
    --instalar --destino CARPETA: actualiza la instalación de CARPETA con esta versión, sin preguntas, y la arranca.
    La lanza «Actualizar ahora» de la versión ANTERIOR: no cambiar el nombre ni el significado de estas opciones.
    Si algo falla, la instalación se queda (o vuelve) como estaba y se arranca la versión que había.
    """
    print(f"  Instalación de WebPEC {VERSION} en {destino}")
    error, copia = None, None
    if not (destino / "webpec.py").is_file():
        sys.exit(f"No hay ningún WebPEC en {destino}: no se ha cambiado nada.")
    if numero_version(version_de(destino)) > numero_version(VERSION):
        error = f"la versión instalada ({version_de(destino)}) es más moderna que esta"
    elif not esperar_cerrado(destino, segundos=30):
        error = "WebPEC sigue abierto"
    else:
        try:
            copia = copia_del_programa(destino)
            print(f"  Copia del programa actual: {copia}")
            copiar_programa(destino)
        except OSError as e:
            error = f"no se ha podido copiar el programa nuevo ({e})"
            if copia:
                try:
                    copiar(copia, destino)  # vuelve a dejar el programa como estaba
                except OSError as e2:
                    error += f"; tampoco se ha podido volver atrás ({e2}): la copia está en {copia}"
    if error:
        print(f"  NO SE HA ACTUALIZADO: {error}. Sigue la versión {version_de(destino)}.")
    else:
        print(f"  Hecho: WebPEC {VERSION} instalado.")
    print()
    orden = [sys.executable, str(destino / "webpec.py"), "--instalar", "--aqui"]
    sys.exit(subprocess.call(orden + (["--sin-navegador"] if sin_navegador else []), cwd=destino))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-navegador", action="store_true",
                        help="no abrir el navegador al arrancar")
    parser.add_argument("--carpeta", type=Path, default=BASE / motor_pec.DATOS,
                        help="carpeta de datos (por defecto, DATOS/ junto al programa)")
    parser.add_argument("--instalar", action="store_true",
                        help="elegir carpeta, copiar el programa, crear el icono y arrancar")
    parser.add_argument("--aqui", action="store_true", help=argparse.SUPPRESS)  # instalar sin preguntar
    parser.add_argument("--destino", type=Path,
                        help="con --instalar: actualizar sin preguntas la instalación de esa carpeta")
    parser.add_argument("--crear-acceso-directo", action="store_true",
                        help="crear el icono de WebPEC en el escritorio y terminar")
    args = parser.parse_args()

    if args.crear_acceso_directo:
        try:
            print(crear_acceso_directo())
            print("Si mueves la carpeta de WebPEC, vuelve a crear el acceso directo.")
        except (RuntimeError, OSError) as e:
            sys.exit(f"No se ha podido crear el acceso directo: {e}")
        return

    if args.instalar and args.destino:
        actualizar_sin_preguntas(args.destino.resolve(), args.sin_navegador)
    if args.instalar:
        instalar(preguntar_destino=not args.aqui, sin_navegador=args.sin_navegador)

    # Antes de tocar los datos: si ya hay un WebPEC en marcha, se usa ese
    puerto = int(configuracion_previa(args.carpeta)["puerto"])
    direccion_url = f"http://localhost:{puerto}"
    if ya_en_marcha(puerto):
        print(f"WebPEC ya está en marcha: se abre {direccion_url}")
        if not args.sin_navegador:
            webbrowser.open(direccion_url)
        return

    limpiar_temporales()
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    try:
        Manejador.motor = Motor(args.carpeta)
    except ErrorPEC as e:
        sys.exit(f"No se puede arrancar WebPEC: {e}")
    for hecho in Manejador.motor.migracion:
        print(f"  Datos: {hecho}")
    config = Manejador.motor.config()
    if int(config["puerto"]) != puerto:  # la configuración estaba aún sin migrar
        puerto = int(config["puerto"])
        direccion_url = f"http://localhost:{puerto}"

    escucha = "0.0.0.0" if config["acceso_red"].lower() in ("si", "sí", "yes", "1") else "127.0.0.1"
    try:
        servidor = ThreadingHTTPServer((escucha, puerto), Manejador)
    except OSError as e:
        sys.exit(f"No se puede usar el puerto {puerto} ({e}). Cámbialo en configuracion.ini")

    print("=" * 62)
    print(f"  WebPEC {VERSION} en marcha:  {direccion_url}")
    print("  Licencia CC BY-NC-SA 4.0 · Departamento de Informática del IES Rosa Chacel (Madrid)")
    if escucha == "0.0.0.0":
        print(f"  También desde la red:  http://{socket.gethostname()}:{puerto}")
    print("  NO CIERRES ESTA VENTANA mientras uses la aplicación.")
    print("  Para terminar: botón de apagado de WebPEC, cerrar esta ventana o Ctrl+C.")
    print("=" * 62)
    if not args.sin_navegador:
        threading.Timer(0.8, webbrowser.open, [direccion_url]).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nWebPEC detenido")
        PENDIENTE.clear()
    finally:
        servidor.server_close()
    if PENDIENTE:  # «Actualizar ahora»: con el servidor apagado, se instala la versión descargada
        lanzar_instalador_descargado()


if __name__ == "__main__":
    main()

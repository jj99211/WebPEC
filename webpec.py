#!/usr/bin/env python3
"""
WebPEC: aplicación web para generar los avisos de pérdida de evaluación continua.

Arranca un pequeño servidor en este ordenador y abre el navegador en http://localhost:<puerto>.
Mientras se usa, la ventana del programa debe quedar abierta; al cerrarla se detiene.

Uso:
  webpec.py                       arranca y abre el navegador
  webpec.py --sin-navegador       arranca sin abrir el navegador
  webpec.py --instalar            prepara los datos, crea el icono del escritorio y arranca
  webpec.py --crear-acceso-directo  solo crea el icono de WebPEC en el escritorio

Licencia: Creative Commons BY-NC-SA 4.0 (ver LICENCIA.txt).
"""

import argparse
import base64
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
import traceback
import webbrowser
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
        if ruta in ("/", "/index.html"):
            return self._estatico("index.html")
        if ruta.startswith("/web/"):
            return self._estatico(unquote(ruta[5:]))
        if ruta == "/ayuda":
            return self._enviar(200, manual_html().encode("utf-8"), "text/html; charset=utf-8")
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
            if ruta == "/api/actividad":
                return self._json(m.actividad())
            if ruta == "/datos/exportar":
                m.usuario = self._usuario(q)
                datos = m.exportar_datos()
                m.anotar_actividad("Exportar datos", f"{len(datos) // 1024} KB")
                nombre = f"WebPEC_datos_{datetime.now():%Y%m%d_%H%M}.zip"
                return self._fichero(datos, nombre, "application/zip", True)
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
            m.registrar_modulo(d.get("unidad"), d.get("en_informe"), d.get("profesor", ""),
                               d.get("horas"), d.get("siglas"), d.get("nombre"))
            return {"ok": True}, "Registrar módulo", f"{d.get('unidad')} {d.get('siglas')}: {d.get('horas')} h"
        if ruta == "/api/modulo/actualizar":
            m.actualizar_modulo(d.get("fila"), d.get("horas"), d.get("nombre"), d.get("siglas"))
            return {"ok": True}, "Cambiar módulo", f"{d.get('siglas')}: {d.get('nombre')}, {d.get('horas')} h"
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
            r = m.dar_de_baja(d.get("grupo", ""), d.get("alumno", ""), d.get("motivo", ""))
            return r, "Dar de baja a alumno/a", f"{d.get('alumno')} ({d.get('grupo')})" + \
                (f" — motivo: {d.get('motivo')}" if d.get("motivo") else "")
        if ruta == "/api/alumno/recuperar":
            m.recuperar_alumno(d.get("grupo", ""), d.get("alumno", ""))
            return {"ok": True}, "Recuperar alumno/a dado de baja", f"{d.get('alumno')} ({d.get('grupo')})"
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


def manual_html(para_pdf=False):
    """Página con el manual de usuario (para la pestaña Ayuda o para generar el PDF)."""
    try:
        md = MANUAL.read_text(encoding="utf-8")
    except OSError:
        md = "# Manual de usuario\n\nNo se encuentra MANUAL_USUARIO.md en la carpeta de WebPEC."
    try:
        escudo = "data:image/png;base64," + base64.b64encode((WEB / "escudo.png").read_bytes()).decode()
    except OSError:
        escudo = ""
    botones = "" if para_pdf else (
        '<div class="botones"><button onclick="window.print()">Imprimir o guardar en PDF</button>'
        + ('<a href="/manual.pdf?descargar=1">Descargar el manual en PDF</a>' if MANUAL_PDF.is_file() else "")
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


def ya_en_marcha(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


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
OBSOLETOS = ["Crear_acceso_directo.bat", "Crear_acceso_directo.sh"]
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


def esperar_cerrado(destino):
    """Antes de sustituir el programa, la instalación de destino no debe estar en marcha."""
    puerto = int(configuracion_previa(destino / motor_pec.DATOS, destino)["puerto"])
    while ya_en_marcha(puerto):
        print(f"  WebPEC está abierto (puerto {puerto}). Ciérralo con su botón de apagado.")
        if preguntar("  Pulsa Intro cuando esté cerrado (o escribe n para cancelar): ").lower() == "n":
            sys.exit("Instalación cancelada: no se ha cambiado nada.")


def copiar_programa(destino):
    """Copia el programa (no los datos) a destino y quita los ficheros que ya no se usan."""
    destino.mkdir(parents=True, exist_ok=True)
    for origen in BASE.iterdir():
        if origen.name in NO_PROGRAMA:
            continue
        if origen.is_dir():
            shutil.copytree(origen, destino / origen.name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(origen, destino / origen.name)
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
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()

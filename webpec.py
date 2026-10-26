#!/usr/bin/env python3
"""
WebPEC: aplicación web para generar los avisos de pérdida de evaluación continua.

Arranca un pequeño servidor en este ordenador y abre el navegador en http://localhost:<puerto>.
Mientras se usa, la ventana del programa debe quedar abierta; al cerrarla se detiene.

Uso:
  webpec.py                       arranca y abre el navegador
  webpec.py --sin-navegador       arranca sin abrir el navegador
  webpec.py --crear-acceso-directo  crea el icono de WebPEC en el escritorio
"""

import argparse
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"

try:
    import motor_pec
    from motor_pec import ErrorPEC, Motor
except ImportError as e:
    sys.exit(f"No se pueden cargar las librerías de WebPEC ({e}).\n"
             f"Copia de nuevo la carpeta completa del programa, incluida lib/.")

# Versión: X.YY. Cambios pequeños suben las centésimas; muchos cambios, la décima;
# cambios grandes, la unidad. El historial está en CAMBIOS.md.
try:
    VERSION = (BASE / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    VERSION = "?"
TAMANO_MAXIMO = 50 * 1024 * 1024

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
            if ruta == "/api/config":
                return self._json({"config": m.config(), "version": VERSION,
                                   "conversor_detectado": motor_pec.nombre_conversor("auto"),
                                   "carpeta": str(m.base)})
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
            if ruta == "/zip":
                datos = m.zip_documentos(q.get("carpeta", ""), q.get("r", []))
                return self._fichero(datos, "WebPEC_avisos.zip", "application/zip", True)
        self._json({"error": "No encontrado"}, 404)

    def _post(self, ruta, q):
        m = self.motor
        if ruta == "/api/subir":
            largo = int(self.headers.get("Content-Length") or 0)
            if largo > TAMANO_MAXIMO:
                raise ErrorPEC("El fichero es demasiado grande")
            datos = self.rfile.read(largo)
            with CERROJO:
                return self._json({"archivo": m.subir(q.get("nombre", "informe.pdf"), datos)})
        datos = self._leer_json()
        if ruta == "/api/salir":
            self._json({"ok": True})
            print("\nWebPEC cerrado desde el navegador")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        with CERROJO:
            if ruta == "/api/procesar":
                return self._json(m.procesar())
            if ruta == "/api/informe/borrar":
                m.borrar_informe(datos.get("id", ""))
                return self._json({"ok": True})
            if ruta == "/api/profesor":
                m.registrar_profesor(datos.get("profesor"), datos.get("firma"))
                return self._json({"ok": True})
            if ruta == "/api/modulo":
                m.registrar_modulo(datos.get("unidad"), datos.get("en_informe"),
                                   datos.get("profesor", ""), datos.get("horas"),
                                   datos.get("siglas"), datos.get("nombre"))
                return self._json({"ok": True})
            if ruta == "/api/modulo/actualizar":
                m.actualizar_modulo(datos.get("fila"), datos.get("horas"), datos.get("nombre"),
                                    datos.get("siglas"))
                return self._json({"ok": True})
            if ruta == "/api/modulo/borrar":
                m.borrar_modulo(datos.get("fila"))
                return self._json({"ok": True})
            if ruta == "/api/documentos/mover":
                n = m.mover_documentos(datos.get("carpeta", ""), datos.get("rutas", []),
                                       datos.get("accion", ""))
                return self._json({"ok": True, "movidos": n})
            if ruta == "/api/config":
                return self._json({"config": motor_pec.guardar_configuracion(m.base, datos)})
            if ruta == "/api/procesados/borrar":
                return self._json({"borrados": m.borrar_procesados()})
            if ruta == "/api/documentos/borrar_todos":
                return self._json({"borrados": m.borrar_todos_documentos(datos.get("cuales", ""))})
            if ruta == "/api/registro/vaciar":
                return self._json(m.vaciar_registro())
            if ruta == "/api/modulos/vaciar":
                return self._json(m.vaciar_hoja())
        self._json({"error": "No encontrado"}, 404)

    def _estatico(self, nombre):
        ruta = (WEB / nombre).resolve()
        if WEB.resolve() not in ruta.parents or not ruta.is_file():
            return self._json({"error": "No encontrado"}, 404)
        tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
            tipo += "; charset=utf-8"
        self._enviar(200, ruta.read_bytes(), tipo)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sin-navegador", action="store_true",
                        help="no abrir el navegador al arrancar")
    parser.add_argument("--carpeta", type=Path, default=BASE,
                        help="carpeta de datos (por defecto, la del programa)")
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

    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("image/svg+xml", ".svg")
    Manejador.motor = Motor(args.carpeta)
    config = Manejador.motor.config()
    puerto = int(config["puerto"])
    direccion_url = f"http://localhost:{puerto}"

    if ya_en_marcha(puerto):
        print(f"WebPEC ya está en marcha: se abre {direccion_url}")
        if not args.sin_navegador:
            webbrowser.open(direccion_url)
        return

    escucha = "0.0.0.0" if config["acceso_red"].lower() in ("si", "sí", "yes", "1") else "127.0.0.1"
    try:
        servidor = ThreadingHTTPServer((escucha, puerto), Manejador)
    except OSError as e:
        sys.exit(f"No se puede usar el puerto {puerto} ({e}). Cámbialo en configuracion.ini")

    print("=" * 62)
    print(f"  WebPEC {VERSION} en marcha:  {direccion_url}")
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

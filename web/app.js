"use strict";

// ------------------------------------------------------------ utilidades ---

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}

async function api(ruta, datos) {
  const opciones = datos === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  };
  const r = await fetch(ruta, opciones);
  const json = await r.json().catch(() => ({ error: "Respuesta no válida del servidor" }));
  if (!r.ok || json.error) throw new Error(json.error || `Error ${r.status}`);
  return json;
}

function tostada(texto, tipo = "") {
  const t = document.createElement("div");
  t.className = `tostada ${tipo}`;
  t.textContent = texto;
  $("#tostadas").append(t);
  setTimeout(() => t.remove(), tipo === "error" ? 7000 : 3500);
}

function error(e) { tostada(e.message || String(e), "error"); }

/** Ventana de diálogo. botones: [{texto, clase, valor}]. Devuelve el valor elegido. */
function dialogo(titulo, html, botones) {
  return new Promise(resolver => {
    $("#modal-titulo").textContent = titulo;
    $("#modal-texto").innerHTML = html;
    const acciones = $("#modal-acciones");
    acciones.innerHTML = "";
    const cerrar = valor => { $("#modal").classList.add("oculto"); resolver(valor); };
    for (const b of botones) {
      const boton = document.createElement("button");
      boton.className = `boton ${b.clase || ""}`;
      boton.textContent = b.texto;
      boton.onclick = () => cerrar(b.valor);
      acciones.append(boton);
    }
    $("#modal").onclick = ev => { if (ev.target.id === "modal") cerrar(null); };
    $("#modal").classList.remove("oculto");
    acciones.lastElementChild?.focus();
  });
}

function chipTipo(tipo) {
  return tipo === "PEC"
    ? '<span class="chip perdida">Pérdida 15 %</span>'
    : '<span class="chip aviso">Aviso 7,5 %</span>';
}

function plural(n, uno, varios) { return `${n} ${n === 1 ? uno : varios}`; }

function guardarPreferencia(clave, valor) { try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento */ } }
function leerPreferencia(clave) { try { return localStorage.getItem(clave) || ""; } catch (e) { return ""; } }

// ------------------------------------------------------------- pestañas ---

const cargadores = {};

function mostrarVista(nombre) {
  $$(".pestana").forEach(p => p.classList.toggle("activa", p.dataset.vista === nombre));
  $$(".vista").forEach(v => v.classList.toggle("activa", v.id === `vista-${nombre}`));
  $("#barra-seleccion").classList.add("oculto");
  $("#barra-procesar").classList.toggle("oculto", nombre !== "informes" || !estadoInformes.listos);
  cargadores[nombre]?.();
  if (nombre === "avisos") actualizarBarraSeleccion();
  guardarPreferencia("webpec-vista", nombre);
}

$$(".pestana").forEach(p => p.addEventListener("click", () => mostrarVista(p.dataset.vista)));

// ------------------------------------------------------------- informes ---

const estadoInformes = { listos: 0 };

function subirFicheros(ficheros) {
  const pdfs = [...ficheros].filter(f => /\.pdf$/i.test(f.name));
  if (!pdfs.length) { tostada("Solo se admiten ficheros PDF", "error"); return; }
  tostada(`Subiendo ${plural(pdfs.length, "informe", "informes")}…`);
  Promise.all(pdfs.map(async f => {
    const r = await fetch(`/api/subir?nombre=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const json = await r.json();
    if (!r.ok) throw new Error(json.error);
  })).then(() => {
    tostada(`${plural(pdfs.length, "informe subido", "informes subidos")}`, "ok");
  }).catch(error).finally(cargarInformes);
}

const zona = $("#zona-subida");
zona.addEventListener("click", () => $("#selector").click());
zona.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") $("#selector").click(); });
$("#selector").addEventListener("change", ev => { subirFicheros(ev.target.files); ev.target.value = ""; });
["dragenter", "dragover"].forEach(t => zona.addEventListener(t, ev => { ev.preventDefault(); zona.classList.add("encima"); }));
["dragleave", "drop"].forEach(t => zona.addEventListener(t, ev => { ev.preventDefault(); zona.classList.remove("encima"); }));
zona.addEventListener("drop", ev => subirFicheros(ev.dataTransfer.files));
// Soltar un fichero fuera de la zona no debe abrirlo en el navegador
window.addEventListener("dragover", ev => ev.preventDefault());
window.addEventListener("drop", ev => ev.preventDefault());

async function cargarInformes() {
  const lista = $("#lista-informes");
  if (!lista.children.length) lista.innerHTML = '<div class="cargando">Leyendo informes…</div>';
  try {
    const estado = await api("/api/estado");
    pintarInformes(estado);
  } catch (e) { error(e); lista.innerHTML = ""; }
  cargarProcesados();
}
cargadores.informes = cargarInformes;
$("#recargar-informes").addEventListener("click", cargarInformes);

function pintarInformes(estado) {
  const lista = $("#lista-informes");
  const informes = estado.informes;
  let avisos = 0, perdidas = 0, listos = 0;
  const avisosHoja = estado.errores_hoja.map(e => `<div class="tarjeta informe"><span class="chip error">Hoja de módulos</span> ${esc(e)}</div>`).join("");

  if (!informes.length) {
    lista.innerHTML = avisosHoja + '<div class="tarjeta vacio">No hay informes pendientes. Sube los PDF de faltas para empezar.</div>';
  } else {
    lista.innerHTML = avisosHoja + informes.map(inf => {
      const verPdf = `<a class="enlace" href="/informe?id=${encodeURIComponent(inf.id)}" target="_blank">Ver PDF</a>`;
      const borrar = `<button class="enlace peligro" data-borrar-informe="${esc(inf.id)}">Quitar</button>`;
      if (inf.error) {
        return `<div class="tarjeta informe">
          <div class="informe-cabecera">
            <div><h3>${esc(inf.archivo)}</h3><div class="meta">${esc(inf.error)}</div></div>
            <div class="informe-acciones"><span class="chip error">No válido</span>${verPdf}${borrar}</div>
          </div></div>`;
      }
      let chip, cuerpo = "";
      if (inf.duplicado) {
        chip = '<span class="chip gris">Ya procesado</span>';
        cuerpo = `<p class="sin-avisos">${esc(inf.duplicado)}. Puedes quitarlo.</p>`;
      } else if (inf.falta_firma || inf.falta_modulo) {
        chip = '<span class="chip aviso">Faltan datos</span>';
      } else {
        chip = '<span class="chip ok">Listo</span>';
        listos++;
      }
      if (inf.falta_firma) {
        const f = inf.falta_firma;
        cuerpo += `<form class="formulario-dato" data-profesor="${esc(f.profesor)}">
          <p><b>Profesor/a nuevo.</b> Raíces escribe «${esc(f.profesor)}». ¿Cómo debe aparecer en la firma?</p>
          <div class="fila">
            <label class="ancho">Nombre para la firma, con tildes<input name="firma" value="${esc(f.propuesta)}" required></label>
            <button class="boton principal">Guardar</button>
          </div></form>`;
      }
      if (inf.falta_modulo) {
        const m = inf.falta_modulo;
        cuerpo += `<form class="formulario-dato" data-modulo='${esc(JSON.stringify(m))}'>
          <p><b>Módulo nuevo.</b> Indica sus horas lectivas totales: con ellas se calculan el 7,5 % y el 15 %.</p>
          <div class="fila">
            <label>Horas totales<input name="horas" inputmode="decimal" required placeholder="p. ej. 100" size="8"></label>
            <label>Siglas<input name="siglas" value="${esc(m.siglas)}" required size="8"></label>
            <label class="ancho">Nombre del módulo en los avisos<input name="nombre" value="${esc(m.nombre)}" required></label>
            <button class="boton principal">Registrar módulo</button>
          </div></form>`;
      }
      if (inf.previsto) {
        const conAviso = inf.previsto.filter(a => a.tipo);
        avisos += conAviso.filter(a => a.tipo === "AVISO_PEC").length;
        perdidas += conAviso.filter(a => a.tipo === "PEC").length;
        cuerpo += inf.previsto.length ? `<table class="alumnos">${inf.previsto.map(a => `
            <tr class="${a.tipo ? "" : "nada"}">
              <td>${esc(a.alumno)}</td>
              <td class="num">${a.fi} FI</td>
              <td>${a.tipo ? chipTipo(a.tipo) : `<span class="secundario">${esc(a.estado)}</span>`}</td>
            </tr>`).join("")}</table>`
          : '<p class="sin-avisos">Ningún alumno llega al 7,5 %.</p>';
      }
      const d = inf.datos_modulo;
      const umbrales = d ? `<div class="umbrales">${d.horas} h · 7,5 % = ${d.umbral_75} FI · 15 % = ${d.umbral_15} FI</div>` : "";
      return `<div class="tarjeta informe">
        <div class="informe-cabecera">
          <div>
            <h3>${esc(d ? d.nombre : inf.modulo)}</h3>
            <div class="meta"><b>${esc(inf.unidad)}</b> · informe del ${esc(inf.fecha)} · ${esc(inf.firma || inf.profesor)} · ${inf.alumnos} alumnos</div>
            ${umbrales}
          </div>
          <div class="informe-acciones">${chip}${verPdf}${borrar}</div>
        </div>${cuerpo}</div>`;
    }).join("");
  }

  estadoInformes.listos = listos;
  const barra = $("#barra-procesar");
  barra.classList.toggle("oculto", !listos || !$("#vista-informes").classList.contains("activa"));
  const partes = [];
  if (avisos) partes.push(plural(avisos, "aviso del 7,5 %", "avisos del 7,5 %"));
  if (perdidas) partes.push(plural(perdidas, "pérdida del 15 %", "pérdidas del 15 %"));
  $("#resumen-previsto").innerHTML = `<b>${plural(listos, "informe listo", "informes listos")}</b>` +
    (partes.length ? ` · se generarán ${partes.join(" y ")}` : " · no hay avisos que generar");
  $("#boton-procesar").textContent = partes.length ? "Generar avisos" : "Archivar informes";
  if (estado.conversor === "ninguno" && partes.length) {
    $("#resumen-previsto").innerHTML += '<br><small>Sin LibreOffice ni Word: los avisos saldrán en .docx</small>';
  }
}

$("#lista-informes").addEventListener("submit", async ev => {
  ev.preventDefault();
  const form = ev.target;
  const datos = Object.fromEntries(new FormData(form));
  try {
    if (form.dataset.profesor) {
      await api("/api/profesor", { profesor: form.dataset.profesor, firma: datos.firma });
      tostada("Profesor/a registrado", "ok");
    } else {
      const m = JSON.parse(form.dataset.modulo);
      await api("/api/modulo", { ...m, ...datos });
      tostada("Módulo registrado", "ok");
    }
    cargarInformes();
  } catch (e) { error(e); }
});

$("#lista-informes").addEventListener("click", async ev => {
  const id = ev.target.dataset.borrarInforme;
  if (!id) return;
  const ok = await dialogo("Quitar informe", `<p>Se borrará <b>${esc(id.split("/").pop())}</b> de la lista de pendientes.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Quitar", clase: "peligro", valor: true }]);
  if (!ok) return;
  try { await api("/api/informe/borrar", { id }); cargarInformes(); } catch (e) { error(e); }
});

$("#boton-procesar").addEventListener("click", async () => {
  const boton = $("#boton-procesar");
  boton.disabled = true;
  boton.textContent = "Generando…";
  try {
    const r = await api("/api/procesar", {});
    const items = r.informes.map(i =>
      `<li><b>${esc(i.modulo)}</b> (${esc(i.unidad)}): ${i.documentos.length ? plural(i.documentos.length, "documento", "documentos") : "sin avisos"}</li>`).join("");
    const mensajes = r.mensajes.map(m => `<p class="nota">⚠ ${esc(m)}</p>`).join("");
    $("#resultado-proceso").innerHTML = `<div class="tarjeta resultado">
      <h3>Hecho: ${plural(r.avisos, "aviso", "avisos")} y ${plural(r.perdidas, "pérdida", "pérdidas")}</h3>
      <ul>${items}</ul>${mensajes}
      ${r.avisos + r.perdidas ? '<p><button class="boton principal" id="ir-avisos">Ver los avisos para imprimir</button></p>' : ""}
    </div>`;
    $("#ir-avisos")?.addEventListener("click", () => mostrarVista("avisos"));
    tostada("Informes procesados", "ok");
  } catch (e) { error(e); }
  boton.disabled = false;
  cargarInformes();
  contarPendientes();
});

async function cargarProcesados() {
  try {
    const lista = await api("/api/procesados");
    $("#lista-procesados").innerHTML = lista.length
      ? `<ul class="lista-simple">${lista.map(p => `<li><a href="/informe?id=${encodeURIComponent(p.id)}" target="_blank">${esc(p.archivo)}</a> <small>${esc(p.fecha)}</small></li>`).join("")}</ul>`
      : '<p class="nota" style="margin-top:12px">Todavía no hay informes procesados.</p>';
  } catch (e) { error(e); }
}

// --------------------------------------------------------------- avisos ---

const estadoAvisos = { carpeta: "pendientes", lista: [], marcados: new Set() };

$$(".interruptor button").forEach(b => b.addEventListener("click", () => {
  $$(".interruptor button").forEach(x => x.classList.toggle("activo", x === b));
  estadoAvisos.carpeta = b.dataset.carpeta;
  estadoAvisos.marcados.clear();
  cargarAvisos();
}));

async function cargarAvisos() {
  try {
    estadoAvisos.lista = await api(`/api/documentos?carpeta=${estadoAvisos.carpeta}`);
  } catch (e) { error(e); estadoAvisos.lista = []; }
  const existentes = new Set(estadoAvisos.lista.map(d => d.ruta));
  estadoAvisos.marcados.forEach(r => { if (!existentes.has(r)) estadoAvisos.marcados.delete(r); });

  const filtro = $("#filtro-profesor");
  const elegido = filtro.value || leerPreferencia("webpec-profesor");
  const profesores = [...new Set(estadoAvisos.lista.map(d => d.profesor))].sort();
  filtro.innerHTML = '<option value="">Todos los profesores</option>' +
    profesores.map(p => `<option ${p === elegido ? "selected" : ""}>${esc(p)}</option>`).join("");
  pintarAvisos();
  if (estadoAvisos.carpeta === "pendientes") pintarContador(estadoAvisos.lista.length);
}
cargadores.avisos = cargarAvisos;

function avisosVisibles() {
  const profesor = $("#filtro-profesor").value;
  const tipo = $("#filtro-tipo").value;
  const texto = $("#filtro-texto").value.trim().toLowerCase();
  return estadoAvisos.lista.filter(d =>
    (!profesor || d.profesor === profesor) && (!tipo || d.tipo === tipo) &&
    (!texto || [d.alumno, d.grupo, d.modulo, d.archivo].join(" ").toLowerCase().includes(texto)));
}

function pintarAvisos() {
  const visibles = avisosVisibles();
  const cuerpo = $("#tabla-avisos tbody");
  const carpeta = estadoAvisos.carpeta;
  cuerpo.innerHTML = visibles.map(d => {
    const url = `/documento?carpeta=${carpeta}&ruta=${encodeURIComponent(d.ruta)}`;
    return `<tr class="${estadoAvisos.marcados.has(d.ruta) ? "marcada" : ""}">
      <td class="col-check"><input type="checkbox" data-ruta="${esc(d.ruta)}" ${estadoAvisos.marcados.has(d.ruta) ? "checked" : ""}></td>
      <td>${chipTipo(d.tipo)}</td>
      <td>${esc(d.alumno || d.archivo)}${d.pdf ? "" : ' <span class="chip gris">.docx</span>'}</td>
      <td>${esc(d.grupo)}</td>
      <td class="secundario">${esc(d.modulo)}</td>
      <td class="num">${esc(d.fi)}</td>
      <td>${esc(d.fecha)}</td>
      <td class="secundario">${esc(d.profesor)}</td>
      <td class="acciones-fila">
        ${d.pdf ? `<a class="enlace" href="${url}" target="_blank">Ver</a>` : ""}
        <a class="enlace" href="${url}&descargar=1">Descargar</a>
      </td></tr>`;
  }).join("");
  const vacio = $("#avisos-vacio");
  vacio.classList.toggle("oculto", visibles.length > 0);
  vacio.textContent = estadoAvisos.lista.length
    ? "Ningún aviso coincide con los filtros."
    : carpeta === "pendientes" ? "No hay avisos pendientes de entregar. 🎉" : "Todavía no hay avisos entregados.";
  $("#marcar-todos").checked = visibles.length > 0 && visibles.every(d => estadoAvisos.marcados.has(d.ruta));
  actualizarBarraSeleccion();
}

["#filtro-profesor", "#filtro-tipo"].forEach(s => $(s).addEventListener("change", () => {
  guardarPreferencia("webpec-profesor", $("#filtro-profesor").value);
  pintarAvisos();
}));
$("#filtro-texto").addEventListener("input", pintarAvisos);

$("#tabla-avisos").addEventListener("change", ev => {
  if (ev.target.id === "marcar-todos") {
    avisosVisibles().forEach(d => ev.target.checked ? estadoAvisos.marcados.add(d.ruta) : estadoAvisos.marcados.delete(d.ruta));
  } else if (ev.target.dataset.ruta) {
    const r = ev.target.dataset.ruta;
    ev.target.checked ? estadoAvisos.marcados.add(r) : estadoAvisos.marcados.delete(r);
  }
  pintarAvisos();
});

function actualizarBarraSeleccion() {
  const n = estadoAvisos.marcados.size;
  const barra = $("#barra-seleccion");
  barra.classList.toggle("oculto", !n || !$("#vista-avisos").classList.contains("activa"));
  $("#texto-seleccion").innerHTML = `<b>${plural(n, "aviso seleccionado", "avisos seleccionados")}</b>`;
  $("#accion-mover").textContent = estadoAvisos.carpeta === "pendientes" ? "Marcar como entregados" : "Volver a pendientes";
}

function seleccion() {
  return estadoAvisos.lista.filter(d => estadoAvisos.marcados.has(d.ruta));
}

function urlVarios(ruta, docs) {
  return `${ruta}?carpeta=${estadoAvisos.carpeta}&` + docs.map(d => `r=${encodeURIComponent(d.ruta)}`).join("&");
}

async function moverSeleccion(accion, docs) {
  try {
    await api("/api/documentos/mover", { carpeta: estadoAvisos.carpeta, rutas: docs.map(d => d.ruta), accion });
    const textos = { realizados: "movidos a entregados", pendientes: "devueltos a pendientes", borrar: "borrados" };
    tostada(`${plural(docs.length, "aviso", "avisos")} ${textos[accion]}`, "ok");
    estadoAvisos.marcados.clear();
    cargarAvisos();
    contarPendientes();
  } catch (e) { error(e); }
}

/** Después de imprimir o descargar, pregunta qué hacer con los avisos. */
async function preguntarDespues(docs, que) {
  if (estadoAvisos.carpeta !== "pendientes") return;
  const valor = await dialogo(`¿Ya están ${que}?`,
    `<p>Cuando los ${plural(docs.length, "aviso esté entregado", "avisos estén entregados")}, puedes pasarlos a
     <b>Entregados</b> (recomendado: quedan guardados por si hay que reimprimirlos) o borrarlos.</p>
     <p class="nota">Sea como sea, el registro los conserva y no se volverán a generar.</p>`,
    [{ texto: "Dejarlos pendientes", valor: null },
     { texto: "Borrarlos", clase: "peligro", valor: "borrar" },
     { texto: "Pasar a Entregados", clase: "principal", valor: "realizados" }]);
  if (valor) moverSeleccion(valor, docs);
}

$("#accion-imprimir").addEventListener("click", async () => {
  const docs = seleccion();
  const pdfs = docs.filter(d => d.pdf);
  if (!pdfs.length) { tostada("Los documentos .docx hay que descargarlos e imprimirlos con Word o LibreOffice", "error"); return; }
  if (pdfs.length < docs.length) tostada("Los .docx no se incluyen en la impresión: descárgalos aparte", "error");
  const url = urlVarios("/imprimir", pdfs);
  const marco = $("#marco-impresion");
  tostada("Preparando la impresión…");
  marco.onload = () => {
    try {
      marco.contentWindow.focus();
      marco.contentWindow.print();
    } catch (e) {
      window.open(url, "_blank");
    }
    setTimeout(() => preguntarDespues(pdfs, "impresos"), 1500);
  };
  marco.src = url;
});

$("#accion-zip").addEventListener("click", () => {
  const docs = seleccion();
  window.location.href = urlVarios("/zip", docs);
  setTimeout(() => preguntarDespues(docs, "enviados"), 1200);
});

$("#accion-mover").addEventListener("click", () =>
  moverSeleccion(estadoAvisos.carpeta === "pendientes" ? "realizados" : "pendientes", seleccion()));

$("#accion-borrar").addEventListener("click", async () => {
  const docs = seleccion();
  const ok = await dialogo("Borrar avisos",
    `<p>Se borrarán ${plural(docs.length, "documento", "documentos")}. No se puede deshacer.</p>
     <p class="nota">El registro los conserva: no se volverán a generar.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Borrar", clase: "peligro", valor: true }]);
  if (ok) moverSeleccion("borrar", docs);
});

function pintarContador(n) { $("#contador-avisos").textContent = n || ""; }

async function contarPendientes() {
  try { pintarContador((await api("/api/documentos?carpeta=pendientes")).length); } catch (e) { /* sin contador */ }
}

// ------------------------------------------------------------- registro ---

let filasRegistro = [];

async function cargarRegistro() {
  try { filasRegistro = await api("/api/registro"); } catch (e) { error(e); }
  pintarRegistro();
}
cargadores.registro = cargarRegistro;

function pintarRegistro() {
  const texto = $("#filtro-registro").value.trim().toLowerCase();
  const filas = filasRegistro.filter(f => !texto ||
    [f.alumno, f.grupo, f.nombre_modulo, f.modulo, f.profesor, f.fecha].join(" ").toLowerCase().includes(texto));
  $("#tabla-registro tbody").innerHTML = filas.length ? filas.map(f => `<tr>
      <td>${esc(f.fecha)}</td><td>${chipTipo(f.tipo)}</td><td>${esc(f.alumno)}</td><td>${esc(f.grupo)}</td>
      <td class="secundario">${esc(f.nombre_modulo)}</td><td class="num">${esc(f.faltas_injustificadas)}</td>
      <td class="num">${esc(f.umbral)}</td><td class="secundario">${esc(f.profesor)}</td>
      <td class="secundario">${esc(f.fecha_proceso)}</td></tr>`).join("")
    : '<tr><td colspan="9" class="vacio">No hay avisos registrados.</td></tr>';
}
$("#filtro-registro").addEventListener("input", pintarRegistro);

// -------------------------------------------------------------- módulos ---

async function cargarModulos() {
  let datos;
  try { datos = await api("/api/modulos"); } catch (e) { error(e); return; }
  datos.errores.forEach(e => tostada(e, "error"));
  $("#tabla-modulos tbody").innerHTML = datos.modulos.length ? datos.modulos.map(m => `
    <tr data-fila="${m.fila}">
      <td><b>${esc(m.unidad)}</b></td>
      <td><input name="siglas" value="${esc(m.siglas)}" size="6" ${m.con_avisos ? 'disabled title="Tiene avisos: no se pueden cambiar"' : ""}></td>
      <td class="secundario">${esc(m.en_informe)}</td>
      <td><input name="nombre" value="${esc(m.nombre)}"></td>
      <td class="num"><input name="horas" value="${m.horas}" size="5" inputmode="decimal" style="text-align:right"></td>
      <td class="num">${esc(m.umbral_75)}</td>
      <td class="num">${esc(m.umbral_15)}</td>
      <td class="acciones-fila">
        <button class="enlace" data-guardar-modulo>Guardar</button>
        <button class="enlace peligro" data-borrar-modulo>Borrar</button>
      </td></tr>`).join("")
    : '<tr><td colspan="8" class="vacio">Todavía no hay módulos. Se añaden al subir el primer informe de cada uno.</td></tr>';

  $("#tabla-profesores tbody").innerHTML = datos.profesores.length ? datos.profesores.map(p => `
    <tr data-profesor="${esc(p.profesor)}">
      <td class="secundario">${esc(p.profesor)}</td>
      <td><input name="firma" value="${esc(p.firma)}"></td>
      <td class="acciones-fila"><button class="enlace" data-guardar-profesor>Guardar</button></td></tr>`).join("")
    : '<tr><td colspan="3" class="vacio">Todavía no hay profesores registrados.</td></tr>';
}
cargadores.modulos = cargarModulos;

$("#vista-modulos").addEventListener("click", async ev => {
  const fila = ev.target.closest("tr");
  try {
    if (ev.target.matches("[data-guardar-modulo]")) {
      await api("/api/modulo/actualizar", {
        fila: fila.dataset.fila, horas: $("[name=horas]", fila).value,
        nombre: $("[name=nombre]", fila).value, siglas: $("[name=siglas]", fila).value,
      });
      tostada("Módulo guardado", "ok");
      cargarModulos();
    } else if (ev.target.matches("[data-borrar-modulo]")) {
      const ok = await dialogo("Borrar módulo",
        `<p>Se quitará <b>${esc($("td:nth-child(3)", fila).textContent)}</b> (${esc($("td", fila).textContent)}) de la hoja de módulos.</p>
         <p class="nota">Los avisos ya emitidos no se tocan. Si vuelve a llegar un informe suyo, se pedirán otra vez sus horas.</p>`,
        [{ texto: "Cancelar", valor: false }, { texto: "Borrar", clase: "peligro", valor: true }]);
      if (!ok) return;
      await api("/api/modulo/borrar", { fila: fila.dataset.fila });
      tostada("Módulo borrado", "ok");
      cargarModulos();
    } else if (ev.target.matches("[data-guardar-profesor]")) {
      await api("/api/profesor", { profesor: fila.dataset.profesor, firma: $("[name=firma]", fila).value });
      tostada("Nombre guardado", "ok");
      cargarModulos();
    }
  } catch (e) { error(e); }
});

// -------------------------------------------------------- configuración ---

async function cargarConfig() {
  try {
    const r = await api("/api/config");
    const form = $("#form-config");
    for (const [clave, valor] of Object.entries(r.config)) {
      if (form.elements[clave]) form.elements[clave].value = clave === "acceso_red" ? (/^s/i.test(valor) ? "si" : "no") : valor;
    }
    const nombres = { libreoffice: "LibreOffice", word: "Microsoft Word", ninguno: "ninguno (los avisos quedarán en .docx)" };
    $("#conversor-detectado").textContent = `En este ordenador, la conversión automática usa: ${nombres[r.conversor_detectado]}`;
    $("#carpeta-datos").textContent = `Carpeta de datos: ${r.carpeta}`;
    pintarCabecera(r.config, r.version);
  } catch (e) { error(e); }
}
cargadores.config = cargarConfig;

$("#form-config").addEventListener("submit", async ev => {
  ev.preventDefault();
  try {
    const r = await api("/api/config", Object.fromEntries(new FormData(ev.target)));
    pintarCabecera(r.config);
    tostada("Configuración guardada", "ok");
  } catch (e) { error(e); }
});

function pintarCabecera(config, version) {
  $("#subtitulo").textContent = `Avisos de pérdida de evaluación continua · ${config.centro}`;
  if (version) $("#pie").title = `WebPEC ${version}`;
}

// -------------------------------------------------------------- cerrar ---

$("#boton-cerrar").addEventListener("click", async () => {
  const ok = await dialogo("Cerrar WebPEC",
    "<p>Se detendrá la aplicación. Para volver a usarla habrá que arrancarla de nuevo.</p>",
    [{ texto: "Cancelar", valor: false }, { texto: "Cerrar WebPEC", clase: "peligro", valor: true }]);
  if (!ok) return;
  try { await api("/api/salir", {}); } catch (e) { /* el servidor ya se está cerrando */ }
  document.body.innerHTML = `<div class="fondo" aria-hidden="true"><div class="mancha m1"></div>
    <div class="mancha m2"></div><div class="marca-agua">WebPEC</div></div>
    <div class="cerrado"><img src="data:image/svg+xml,${encodeURIComponent(iconoCerrado)}" alt="">
    <h1>WebPEC se ha cerrado</h1><p>Ya puedes cerrar esta pestaña.</p></div>`;
});

const iconoCerrado = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 3v8M6.3 6.3a8 8 0 1 0 11.4 0" fill="none" stroke="#0f766e" stroke-width="2" stroke-linecap="round"/></svg>';

// --------------------------------------------------------------- inicio ---

document.addEventListener("keydown", ev => {
  if (ev.key === "Escape" && !$("#modal").classList.contains("oculto")) $("#modal").click();
});

cargarConfig();
contarPendientes();
const vistaInicial = location.hash.slice(1) || leerPreferencia("webpec-vista");
mostrarVista($(`#vista-${vistaInicial}`) ? vistaInicial : "informes");

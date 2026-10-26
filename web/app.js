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
  cargadores[nombre]?.();
  if (nombre === "avisos") actualizarBarraSeleccion();
  guardarPreferencia("webpec-vista", nombre);
}

$$(".pestana").forEach(p => p.addEventListener("click", () => mostrarVista(p.dataset.vista)));

// ------------------------------------------------------------- informes ---

function subirFicheros(ficheros) {
  const pdfs = [...ficheros].filter(f => /\.pdf$/i.test(f.name));
  if (!pdfs.length) { tostada("Solo se admiten ficheros PDF", "error"); return; }
  tostada(`Subiendo ${plural(pdfs.length, "informe", "informes")}…`);
  Promise.all(pdfs.map(async f => {
    const r = await fetch(`/api/subir?nombre=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const json = await r.json();
    if (!r.ok) throw new Error(json.error);
  })).then(() => {
    tostada(`${plural(pdfs.length, "informe subido", "informes subidos")}. Pulsa «Procesar informes» cuando quieras.`, "ok");
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

const estadoInformes = { pendientes: 0, procesados: 0, resultado: null };

async function cargarInformes() {
  const lista = $("#lista-informes");
  if (!lista.children.length) lista.innerHTML = '<div class="cargando">Leyendo informes…</div>';
  try {
    pintarPendientes(await api("/api/estado"));
  } catch (e) { error(e); lista.innerHTML = ""; }
  cargarProcesados();
}
cargadores.informes = cargarInformes;
$("#recargar-informes").addEventListener("click", cargarInformes);

const enlaceVer = inf => `<a class="enlace" href="/informe?id=${encodeURIComponent(inf.id)}" target="_blank">Ver PDF</a>`;
const botonQuitar = inf => `<button class="enlace peligro" data-borrar-informe="${esc(inf.id)}">Quitar</button>`;

/** Lista de informes pendientes: solo informa, no cambia nada. */
function pintarPendientes(estado) {
  const lista = $("#lista-informes");
  const avisosHoja = estado.errores_hoja.map(e =>
    `<div class="tarjeta pendiente"><span><span class="chip error">Hoja de módulos</span> ${esc(e)}</span></div>`).join("");
  estadoInformes.pendientes = estado.informes.filter(i => !i.error && !i.duplicado).length;
  estadoInformes.procesados = estado.procesados;

  lista.innerHTML = avisosHoja + (estado.informes.length ? estado.informes.map(inf => {
    let chips = "", meta;
    if (inf.error) {
      chips = '<span class="chip error">No válido</span>';
      meta = esc(inf.error);
    } else {
      meta = `<b>${esc(inf.unidad)}</b> · ${esc(inf.datos_modulo ? inf.datos_modulo.nombre : inf.modulo)} · ` +
        `informe del ${esc(inf.fecha)} · ${esc(inf.firma || inf.profesor)}`;
      if (inf.duplicado) chips += '<span class="chip gris">Ya procesado</span>';
      if (inf.falta_modulo) chips += '<span class="chip aviso">Módulo nuevo</span>';
      if (inf.falta_firma) chips += '<span class="chip aviso">Profesor/a nuevo</span>';
      if (!chips) chips = '<span class="chip ok">Listo</span>';
    }
    const destino = inf.nombre_final && inf.nombre_final !== inf.archivo
      ? `<div class="flecha">→ ${esc(inf.nombre_final)}</div>` : "";
    return `<div class="tarjeta pendiente">
      <div><h3>${esc(inf.archivo)}</h3><div class="meta">${meta}</div>${destino}</div>
      <div class="etiquetas">${chips}${enlaceVer(inf)}${botonQuitar(inf)}</div></div>`;
  }).join("") : '<div class="tarjeta vacio">No hay informes pendientes. Sube los PDF de faltas para empezar.</div>');

  $("#boton-procesar").disabled = !estadoInformes.pendientes;
  $("#boton-procesar").textContent = estadoInformes.pendientes
    ? `Procesar informes (${estadoInformes.pendientes})` : "Procesar informes";
  $("#boton-borrar-procesados").disabled = !estado.procesados;
  $("#boton-borrar-procesados").textContent = `Borrar todos los informes procesados (${estado.procesados})`;
}

/** Botón «Procesar informes» y continuación tras completar los datos que falten. */
async function procesar(continuar = false) {
  const boton = $("#boton-procesar");
  boton.disabled = true;
  boton.textContent = "Procesando…";
  try {
    const r = await api("/api/procesar", {});
    const previo = continuar && estadoInformes.resultado;
    if (previo) {
      r.informes = previo.informes.concat(r.informes);
      r.avisos += previo.avisos;
      r.perdidas += previo.perdidas;
      r.mensajes = [...new Set(previo.mensajes.concat(r.mensajes))];
    }
    estadoInformes.resultado = r;
    pintarResultado(r);
    if (r.informes.length && !continuar) tostada("Informes procesados", "ok");
  } catch (e) { error(e); }
  cargarInformes();
  contarPendientes();
}
$("#boton-procesar").addEventListener("click", () => procesar(false));

function pintarResultado(r) {
  const partes = [];

  if (r.informes.length) {
    const informes = r.informes.map(i => `
      <h4>${esc(i.modulo)} <small>· ${esc(i.unidad)} · informe del ${esc(i.fecha)} · ${esc(i.profesor)}</small></h4>
      ${i.situacion.length ? `<table class="alumnos">${i.situacion.map(a => `
        <tr class="${a.tipo ? "" : "nada"}"><td>${esc(a.alumno)}</td><td class="num">${a.fi} FI</td>
        <td>${a.tipo ? chipTipo(a.tipo) : `<span class="secundario">${esc(a.estado)}</span>`}</td></tr>`).join("")}</table>`
        : '<p class="sin-avisos">Ningún alumno llega al 7,5 %.</p>'}`).join("");
    const mensajes = r.mensajes.map(m => `<p class="nota">⚠ ${esc(m)}</p>`).join("");
    partes.push(`<div class="tarjeta resultado">
      <h3>${plural(r.informes.length, "informe procesado", "informes procesados")}:
        ${plural(r.avisos, "aviso", "avisos")} y ${plural(r.perdidas, "pérdida", "pérdidas")}</h3>
      ${mensajes}${informes}
      ${r.avisos + r.perdidas ? '<p style="margin-top:16px"><button class="boton principal" data-ir-avisos>Ver los avisos para imprimir</button></p>' : ""}
    </div>`);
  }

  if (r.faltan_datos.length) {
    // Un formulario por profesor y por módulo, aunque aparezcan en varios informes
    const profesores = new Map(), modulos = new Map();
    for (const i of r.faltan_datos) {
      if (i.falta_firma) profesores.set(i.falta_firma.profesor, i.falta_firma);
      if (i.falta_modulo) modulos.set(`${i.falta_modulo.unidad}|${i.falta_modulo.en_informe}`, i.falta_modulo);
    }
    const formularios = [...profesores.values()].map(f => `
      <form class="formulario-dato" data-profesor="${esc(f.profesor)}">
        <p><b>Profesor/a nuevo.</b> Raíces escribe «${esc(f.profesor)}». ¿Cómo debe aparecer en la firma?</p>
        <div class="fila">
          <label class="ancho">Nombre para la firma, con tildes<input name="firma" value="${esc(f.propuesta)}" required></label>
          <button class="boton principal">Guardar y continuar</button>
        </div></form>`).concat([...modulos.values()].map(m => `
      <form class="formulario-dato" data-modulo='${esc(JSON.stringify(m))}'>
        <p><b>Módulo nuevo: ${esc(m.en_informe)}</b> (${esc(m.unidad)}). Indica sus horas lectivas totales:
          con ellas se calculan el 7,5 % y el 15 %.</p>
        <div class="fila">
          <label>Horas totales<input name="horas" inputmode="decimal" required placeholder="p. ej. 100" size="8"></label>
          <label>Siglas<input name="siglas" value="${esc(m.siglas)}" required size="8"></label>
          <label class="ancho">Nombre del módulo en los avisos<input name="nombre" value="${esc(m.nombre)}" required></label>
          <button class="boton principal">Guardar y continuar</button>
        </div></form>`)).join("");
    partes.push(`<div class="tarjeta faltan">
      <h3>Faltan datos para ${plural(r.faltan_datos.length, "informe", "informes")}</h3>
      <p class="nota">Al guardarlos, el procesado continúa solo.</p>${formularios}</div>`);
  }

  if (r.sin_procesar.length) {
    partes.push(`<div class="tarjeta sin-procesar"><h3>No se han procesado</h3><ul>${r.sin_procesar.map(i =>
      `<li><b>${esc(i.archivo)}</b>: ${esc(i.error || i.duplicado)}</li>`).join("")}</ul>
      <p class="nota" style="margin-top:8px">Puedes quitarlos de la lista de pendientes.</p></div>`);
  }

  if (!partes.length) partes.push('<div class="tarjeta vacio">No había informes que procesar.</div>');
  $("#resultado-proceso").innerHTML = partes.join("");
  $("#resultado-proceso").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#resultado-proceso").addEventListener("click", ev => {
  if (ev.target.matches("[data-ir-avisos]")) mostrarVista("avisos");
});

$("#resultado-proceso").addEventListener("submit", async ev => {
  ev.preventDefault();
  const form = ev.target;
  const datos = Object.fromEntries(new FormData(form));
  try {
    if (form.dataset.profesor) {
      await api("/api/profesor", { profesor: form.dataset.profesor, firma: datos.firma });
      tostada("Profesor/a registrado", "ok");
    } else {
      await api("/api/modulo", { ...JSON.parse(form.dataset.modulo), ...datos });
      tostada("Módulo registrado", "ok");
    }
  } catch (e) { error(e); return; }
  // Si aún quedan formularios por rellenar, se espera a ellos antes de continuar
  form.remove();
  if (!$("#resultado-proceso form")) procesar(true);
});

$("#lista-informes").addEventListener("click", async ev => {
  const id = ev.target.dataset.borrarInforme;
  if (!id) return;
  const ok = await dialogo("Quitar informe", `<p>Se borrará <b>${esc(id.split("/").pop())}</b> de la lista de pendientes.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Quitar", clase: "peligro", valor: true }]);
  if (!ok) return;
  try { await api("/api/informe/borrar", { id }); cargarInformes(); } catch (e) { error(e); }
});

$("#boton-borrar-procesados").addEventListener("click", async () => {
  const n = estadoInformes.procesados;
  const ok = await dialogo("Borrar todos los informes procesados",
    `<p>Se borrarán los <b>${plural(n, "informe", "informes")}</b> de faltas ya procesados (los PDF de Raíces).</p>
     <p class="nota">Los avisos generados y el registro no se tocan.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: `Borrar ${n}`, clase: "peligro", valor: true }]);
  if (!ok) return;
  try {
    const r = await api("/api/procesados/borrar", {});
    tostada(`${plural(r.borrados, "informe borrado", "informes borrados")}`, "ok");
    cargarInformes();
  } catch (e) { error(e); }
});

async function cargarProcesados() {
  try {
    const lista = await api("/api/procesados");
    $("#lista-procesados").innerHTML = lista.length
      ? `<ul class="lista-simple">${lista.map(p => `<li><a href="/informe?id=${encodeURIComponent(p.id)}" target="_blank">${esc(p.archivo)}</a> <small>${esc(p.fecha)}</small></li>`).join("")}</ul>`
      : '<p class="nota" style="margin-top:12px">No hay informes procesados.</p>';
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
  if (version) {
    $("#pie").title = `WebPEC ${version}`;
    $("#version").textContent = `v${version}`;
    document.title = `WebPEC ${version}`;
  }
}

// -------------------------------------------------------------- cerrar ---

$("#boton-cerrar").addEventListener("click", async () => {
  const ok = await dialogo("Cerrar WebPEC",
    "<p>Se detendrá la aplicación. Para volver a usarla habrá que arrancarla de nuevo.</p>",
    [{ texto: "Cancelar", valor: false }, { texto: "Cerrar WebPEC", clase: "peligro", valor: true }]);
  if (!ok) return;
  // El escudo se lee antes de apagar: después el servidor ya no puede servirlo
  const escudoCerrado = await fetch("/web/escudo.png").then(r => r.blob())
    .then(b => URL.createObjectURL(b)).catch(() => "");
  try { await api("/api/salir", {}); } catch (e) { /* el servidor ya se está cerrando */ }
  document.body.innerHTML = `<div class="fondo" aria-hidden="true"><div class="mancha m1"></div>
    <div class="mancha m2"></div><div class="marca-agua">WebPEC</div></div>
    <div class="cerrado"><img src="${escudoCerrado}" alt="">
    <h1>WebPEC se ha cerrado</h1><p>Ya puedes cerrar esta pestaña.</p></div>`;
});

// ------------------------------------------------------ borrados masivos ---

$("#boton-borrar-avisos").addEventListener("click", async () => {
  let n;
  try { n = await api("/api/documentos/contar"); } catch (e) { error(e); return; }
  const total = n.pendientes + n.realizados;
  if (!total) { tostada("No hay avisos que borrar"); return; }
  const cuales = await dialogo("Borrar avisos generados",
    `<p>¿Qué avisos quieres borrar?</p>
     <p>Pendientes de entregar: <b>${n.pendientes}</b> · Entregados: <b>${n.realizados}</b></p>
     <p class="nota">Se borran los documentos. El registro los conserva: no se volverán a generar.</p>`,
    [{ texto: "Cancelar", valor: null },
     { texto: `Pendientes (${n.pendientes})`, clase: "peligro-suave", valor: "pendientes" },
     { texto: `Entregados (${n.realizados})`, clase: "peligro-suave", valor: "realizados" },
     { texto: `Todos (${total})`, clase: "peligro", valor: "todos" }]);
  if (!cuales) return;
  const cuantos = { pendientes: n.pendientes, realizados: n.realizados, todos: total }[cuales];
  if (!cuantos) { tostada("No hay avisos de ese tipo"); return; }
  const ok = await dialogo("¿Seguro?",
    `<p class="peligro-texto">Se borrarán ${plural(cuantos, "documento", "documentos")}. No se puede deshacer.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Borrar", clase: "peligro", valor: true }]);
  if (!ok) return;
  try {
    const r = await api("/api/documentos/borrar_todos", { cuales });
    tostada(`${plural(r.borrados, "aviso borrado", "avisos borrados")}`, "ok");
    estadoAvisos.marcados.clear();
    cargarAvisos();
    contarPendientes();
  } catch (e) { error(e); }
});

$("#boton-vaciar-registro").addEventListener("click", async () => {
  const ok = await dialogo("Vaciar el registro de avisos",
    `<p>Se borrarán las <b>${plural(filasRegistro.length, "anotación", "anotaciones")}</b> del registro.</p>
     <p class="peligro-texto">Sin registro, WebPEC ya no sabe a quién se avisó: si se vuelven a procesar informes,
       se generarán de nuevo los avisos del 7,5 % y no podrá emitir pérdidas del 15 % de avisos anteriores.</p>
     <p class="nota">Útil al empezar un curso nuevo. Antes de vaciarlo se guarda una copia en COPIAS_SEGURIDAD.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Vaciar registro", clase: "peligro", valor: true }]);
  if (!ok) return;
  try {
    const r = await api("/api/registro/vaciar", {});
    tostada(`Registro vaciado (${plural(r.borrados, "anotación", "anotaciones")}).` +
      (r.copia ? ` Copia: ${r.copia}` : ""), "ok");
    cargarRegistro();
  } catch (e) { error(e); }
});

$("#boton-vaciar-modulos").addEventListener("click", async () => {
  const ok = await dialogo("Borrar todos los módulos y profesores",
    `<p>La hoja de módulos quedará vacía: módulos, horas, siglas y nombres de firma.
       Sirve para empezar de cero (por ejemplo, para otro departamento).</p>
     <p class="nota">Los avisos y el registro no se tocan. Antes de borrar se guarda una copia en COPIAS_SEGURIDAD.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Borrar todo", clase: "peligro", valor: true }]);
  if (!ok) return;
  try {
    const r = await api("/api/modulos/vaciar", {});
    tostada(`Borrados ${plural(r.modulos, "módulo", "módulos")} y ${plural(r.profesores, "profesor/a", "profesores")}.` +
      (r.copia ? ` Copia: ${r.copia}` : ""), "ok");
    cargarModulos();
  } catch (e) { error(e); }
});

// --------------------------------------------------------------- inicio ---

document.addEventListener("keydown", ev => {
  if (ev.key === "Escape" && !$("#modal").classList.contains("oculto")) $("#modal").click();
});

cargarConfig();
contarPendientes();
const vistaInicial = location.hash.slice(1) || leerPreferencia("webpec-vista");
mostrarVista($(`#vista-${vistaInicial}`) ? vistaInicial : "informes");

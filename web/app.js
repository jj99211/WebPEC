"use strict";

// ------------------------------------------------------------ utilidades ---

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}

// Quién usa WebPEC en esta pestaña: se manda en cada petición y queda anotado en lo que haga
let usuario = "";
try { usuario = sessionStorage.getItem("webpec-usuario") || ""; } catch (e) { /* sin almacenamiento */ }
const cabeceraUsuario = () => ({ "X-WebPEC-Usuario": encodeURIComponent(usuario) });

async function api(ruta, datos) {
  const opciones = datos === undefined ? { headers: cabeceraUsuario() } : {
    method: "POST",
    headers: { "Content-Type": "application/json", ...cabeceraUsuario() },
    body: JSON.stringify(datos),
  };
  const r = await fetch(ruta, opciones);
  const json = await r.json().catch(() => ({ error: "Respuesta no válida del servidor" }));
  if (!r.ok || json.error) throw new Error(json.error || `Error ${r.status}`);
  return json;
}

/** Sube un fichero tal cual (informe, correos, datos). */
async function subirFichero(ruta, fichero, parametros = {}) {
  const consulta = new URLSearchParams({ nombre: fichero.name, ...parametros });
  const r = await fetch(`${ruta}?${consulta}`, { method: "POST", body: fichero, headers: cabeceraUsuario() });
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
      if (b.requiere) {
        // Casilla que hay que marcar o campo de texto que hay que rellenar
        const campo = $("#modal-texto").querySelector(b.requiere);
        const listo = () => campo.type === "checkbox" ? campo.checked : campo.value.trim() !== "";
        boton.disabled = !listo();
        campo.oninput = campo.onchange = () => { boton.disabled = !listo(); };
      }
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

/** "2026-10-28 20:03" -> "28/10/2026 20:03" */
function fechaHora(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(.*)$/.exec(iso || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}${m[4]}` : (iso || "");
}

const porQuien = nombre => nombre ? ` por ${esc(nombre)}` : "";

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
  Promise.all(pdfs.map(f => subirFichero("/api/subir", f))).then(() => {
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
    const formularios = [...profesores.values()].map(f => {
      // Puede ser alguien dado de alta a mano con el nombre algo distinto: se propone el más parecido
      const candidatos = (f.candidatos || []).filter(c => c.parecido > 0);
      const sugerido = candidatos.find(c => c.parecido >= 0.5);
      return `
      <form class="formulario-dato" data-profesor="${esc(f.profesor)}">
        <p><b>Profesor/a que no está en la lista.</b> Raíces escribe «${esc(f.profesor)}».</p>
        ${candidatos.length ? `<label class="ancho">¿Es alguien que ya está en la lista con el nombre escrito de otra forma?
          <select name="existente">
            <option value="">No: es otra persona</option>
            ${candidatos.map(c => `<option value="${esc(c.en_informe)}" ${c === sugerido ? "selected" : ""}>Sí: ${esc(c.firma)}</option>`).join("")}
          </select></label>
          <p class="nota">Si es la misma persona, se guarda con el nombre que trae el informe y su firma no cambia.</p>` : ""}
        <div class="fila">
          <label class="ancho campo-firma ${sugerido ? "oculto" : ""}">Nombre para la firma, con tildes<input name="firma" value="${esc(f.propuesta)}"></label>
          <button class="boton principal">Guardar y continuar</button>
        </div></form>`;
    }).concat([...modulos.values()].map(m => `
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

$("#resultado-proceso").addEventListener("change", ev => {
  if (ev.target.name === "existente") $(".campo-firma", ev.target.form).classList.toggle("oculto", !!ev.target.value);
});

$("#resultado-proceso").addEventListener("submit", async ev => {
  ev.preventDefault();
  const form = ev.target;
  const datos = Object.fromEntries(new FormData(form));
  try {
    if (form.dataset.profesor && datos.existente) {
      const r = await api("/api/profesor/vincular", { profesor: form.dataset.profesor, existente: datos.existente });
      tostada(`Reconocido: ${r.firma}`, "ok");
    } else if (form.dataset.profesor) {
      if (!datos.firma?.trim()) { tostada("Escribe el nombre para la firma", "error"); return; }
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
      <td>${esc(d.alumno || d.archivo)}${d.pdf ? "" : ' <span class="chip gris">.docx</span>'}
        ${d.correo && carpeta !== "anulados" ? `<span class="motivo">${esc(d.correo)}</span>` : ""}
        ${carpeta === "anulados" ? `<span class="motivo">Anulado el ${esc(fechaHora(d.fecha_anulacion))}${porQuien(d.anulado_por)}: ${esc(d.motivo_anulacion)}</span>` : ""}
        ${carpeta === "realizados" && d.fecha_entrega ? `<span class="motivo">Entregado el ${esc(fechaHora(d.fecha_entrega))}${porQuien(d.entregado_por)}</span>` : ""}</td>
      <td>${esc(d.grupo)}</td>
      <td class="secundario">${esc(d.modulo)}</td>
      <td class="num">${esc(d.fi)}</td>
      <td>${esc(d.fecha)}</td>
      <td class="secundario">${esc(d.profesor)}</td>
      <td class="acciones-fila">
        ${d.pdf ? `<a class="enlace" href="${url}" target="_blank">Ver</a>` : ""}
        <a class="enlace" href="${url}&descargar=1">Descargar</a>
        ${carpeta !== "anulados" ? `<button class="enlace" data-correo="${esc(d.ruta)}" title="${d.correo ? `Preparar el correo para ${esc(d.correo)}` : "No hay correo de este alumno/a: habrá que escribirlo"}">Correo</button>` : ""}
        ${carpeta === "pendientes" ? `<button class="enlace" data-entregar="${esc(d.ruta)}">Entregado</button>` : ""}
      </td></tr>`;
  }).join("");
  const vacio = $("#avisos-vacio");
  vacio.classList.toggle("oculto", visibles.length > 0);
  vacio.textContent = estadoAvisos.lista.length
    ? "Ningún aviso coincide con los filtros."
    : { pendientes: "No hay avisos pendientes de entregar. 🎉", realizados: "Todavía no hay avisos entregados.",
        anulados: "No hay avisos anulados." }[carpeta];
  $("#marcar-todos").checked = visibles.length > 0 && visibles.every(d => estadoAvisos.marcados.has(d.ruta));
  $("#ayuda-avisos").classList.toggle("oculto", carpeta !== "pendientes" || !visibles.length);
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

$("#tabla-avisos").addEventListener("click", ev => {
  const ruta = ev.target.dataset?.entregar;
  if (ruta) entregar(estadoAvisos.lista.filter(d => d.ruta === ruta));
  const correo = ev.target.dataset?.correo;
  if (correo) enviarCorreo(estadoAvisos.lista.filter(d => d.ruta === correo));
});

/**
 * «Enviar por correo»: Thunderbird abre un correo por aviso con el PDF adjunto y el texto escritos
 * (o se descargan ficheros .eml). El profesor/a lo revisa y lo envía; WebPEC no envía nada.
 */
async function enviarCorreo(docs) {
  if (!docs.length) return;
  if (docs.length > 10 && !await dialogo("Muchos correos",
    `<p>Se abrirán ${docs.length} ventanas de correo, una por aviso.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Seguir", clase: "principal", valor: true }])) return;
  let r;
  try {
    r = await api("/api/correo", { carpeta: estadoAvisos.carpeta, rutas: docs.map(d => d.ruta) });
  } catch (e) { error(e); return; }
  if (r.programa === "eml") {
    // Un fichero .eml por aviso: se abre con el programa de correo (borrador con el PDF adjunto)
    docs.forEach((d, i) => setTimeout(() => {
      const enlace = document.createElement("a");
      enlace.href = `/correo.eml?carpeta=${estadoAvisos.carpeta}&ruta=${encodeURIComponent(d.ruta)}`;
      enlace.click();
    }, i * 400));
  }
  const sin = r.sin_correo.length
    ? `<p class="peligro-texto">Sin correo guardado (habrá que escribir la dirección): ${r.sin_correo.map(esc).join(", ")}.</p>
       <p class="nota">Los correos del alumnado se importan en la pestaña Alumnado.</p>` : "";
  const cuantos = plural(docs.length, "correo", "correos");
  await dialogo(r.programa === "eml" ? "Correos descargados" : "Correos preparados en Thunderbird",
    (r.programa === "eml"
      ? `<p>Se ${docs.length === 1 ? "ha" : "han"} descargado ${cuantos} (.eml). Ábrelos con tu programa de correo, revísalos y envíalos.</p>`
      : `<p>Thunderbird ha abierto ${cuantos} con el aviso adjunto y el texto escritos. Revísalos y pulsa <b>Enviar</b>.</p>`) +
    `${sin}<p class="nota">Recuerda: es la entrega oficial al alumnado. Cuando estén enviados, pásalos a Entregados.</p>`,
    [{ texto: "Entendido", clase: "principal", valor: true }]);
  if (estadoAvisos.carpeta === "pendientes") preguntarDespues(docs, "enviados");
}

function actualizarBarraSeleccion() {
  const n = estadoAvisos.marcados.size;
  const barra = $("#barra-seleccion");
  barra.classList.toggle("oculto", !n || !$("#vista-avisos").classList.contains("activa"));
  $("#texto-seleccion").innerHTML = `<b>${plural(n, "aviso seleccionado", "avisos seleccionados")}</b>`;
  $("#accion-mover").textContent = estadoAvisos.carpeta === "pendientes" ? "Marcar como entregados" : "Volver a pendientes";
  const anulados = estadoAvisos.carpeta === "anulados";
  $("#accion-mover").classList.toggle("oculto", anulados);
  $("#accion-anular").classList.toggle("oculto", anulados);
  $("#accion-correo").classList.toggle("oculto", anulados);
}

function seleccion() {
  return estadoAvisos.lista.filter(d => estadoAvisos.marcados.has(d.ruta)).map(d => ({ ...d, documento: d.archivo }));
}

function urlVarios(ruta, docs) {
  return `${ruta}?carpeta=${estadoAvisos.carpeta}&` + docs.map(d => `r=${encodeURIComponent(d.ruta)}`).join("&");
}

async function moverSeleccion(accion, docs) {
  try {
    await api("/api/documentos/mover", { carpeta: estadoAvisos.carpeta, rutas: docs.map(d => d.ruta), accion });
    const textos = { realizados: "movidos a entregados", pendientes: "devueltos a pendientes" };
    tostada(`${plural(docs.length, "aviso", "avisos")} ${textos[accion]}`, "ok");
    docs.forEach(d => estadoAvisos.marcados.delete(d.ruta));
    cargarAvisos();
    contarPendientes();
  } catch (e) { error(e); }
}

/** Pide al profesor que confirme la entrega personal de los avisos antes de pasarlos a Entregados. */
async function entregar(docs) {
  if (!docs.length) return;
  const max = 8;
  const lista = docs.slice(0, max).map(d =>
    `<li>${esc(d.alumno || d.archivo)} <span class="secundario">· ${esc(d.grupo)} · ${esc(d.modulo)}</span></li>`).join("") +
    (docs.length > max ? `<li class="secundario">y ${docs.length - max} más…</li>` : "");
  const ok = await dialogo("Confirmar la entrega",
    `<p>Pasar a <b>Entregados</b> no avisa al alumnado: <b>la entrega la tiene que hacer el profesor o la profesora
     personalmente</b>, en mano (con el «Recibí» firmado) o por correo electrónico.</p>
     <ul class="lista-modal">${lista}</ul>
     <label class="casilla-confirmar"><input type="checkbox" id="confirmo-entrega">
       Confirmo que ${docs.length === 1 ? "este aviso se ha entregado" : `estos ${docs.length} avisos se han entregado`}
       al alumnado, en persona o por correo electrónico.</label>`,
    [{ texto: "Cancelar", valor: false },
     { texto: "Marcar como entregados", clase: "principal", valor: true, requiere: "#confirmo-entrega" }]);
  if (ok) moverSeleccion("realizados", docs);
}

/** Después de imprimir o descargar, pregunta qué hacer con los avisos. */
async function preguntarDespues(docs, que) {
  if (estadoAvisos.carpeta !== "pendientes") return;
  const valor = await dialogo(`¿Ya están ${que}?`,
    `<p>Cuando los ${plural(docs.length, "aviso esté entregado", "avisos estén entregados")}, pásalos a
     <b>Entregados</b>: quedan guardados por si hay que reimprimirlos.</p>`,
    [{ texto: "Dejarlos pendientes", valor: null },
     { texto: "Pasar a Entregados", clase: "principal", valor: "realizados" }]);
  if (valor === "realizados") entregar(docs);
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

$("#accion-correo").addEventListener("click", () => enviarCorreo(seleccion()));

$("#accion-zip").addEventListener("click", () => {
  const docs = seleccion();
  window.location.href = urlVarios("/zip", docs);
  setTimeout(() => preguntarDespues(docs, "enviados"), 1200);
});

$("#accion-mover").addEventListener("click", () => {
  if (estadoAvisos.carpeta === "pendientes") entregar(seleccion());
  else moverSeleccion("pendientes", seleccion());
});

$("#accion-anular").addEventListener("click", async () => { if (await anular(seleccion())) cargarAvisos(); });

/**
 * Anula avisos (cada uno con su alumno, grupo y módulo). Pide el motivo; al terminar recarga lo que haga falta.
 * docs: [{documento, alumno, grupo, modulo}]
 */
async function anular(docs) {
  if (!docs.length) return false;
  const max = 8;
  const lista = docs.slice(0, max).map(d =>
    `<li>${esc(d.alumno || d.documento)} <span class="secundario">· ${esc(d.grupo)} · ${esc(d.modulo)}</span></li>`).join("") +
    (docs.length > max ? `<li class="secundario">y ${docs.length - max} más…</li>` : "");
  const ok = await dialogo(docs.length === 1 ? "Anular aviso" : `Anular ${docs.length} avisos`,
    `<p>Úsalo cuando un aviso se emitió por error (horas del módulo mal puestas, faltas que luego se justificaron…).</p>
     <ul class="lista-modal">${lista}</ul>
     <p class="nota">El aviso queda tachado en el registro con la fecha y el motivo, y su documento pasa a <b>Anulados</b>.
       Si el alumno/a sigue superando el límite, el siguiente informe que se procese lo volverá a generar.
       Una pérdida del 15 % hay que anularla antes que su aviso del 7,5 % (o los dos a la vez).</p>
     <label class="campo-motivo">Motivo de la anulación<textarea id="motivo-anulacion" maxlength="300"
       placeholder="p. ej. Las horas del módulo estaban mal"></textarea></label>`,
    [{ texto: "Cancelar", valor: false },
     { texto: "Anular", clase: "peligro", valor: true, requiere: "#motivo-anulacion" }]);
  if (!ok) return false;
  try {
    const r = await api("/api/anular", { documentos: docs.map(d => d.documento), motivo: $("#motivo-anulacion").value });
    tostada(`${plural(r.anulados, "aviso anulado", "avisos anulados")}`, "ok");
    estadoAvisos.marcados.clear();
    contarPendientes();
    return true;
  } catch (e) { error(e); return false; }
}

function pintarContador(n) { $("#contador-avisos").textContent = n || ""; }

async function contarPendientes() {
  try { pintarContador((await api("/api/documentos?carpeta=pendientes")).length); } catch (e) { /* sin contador */ }
}

// ------------------------------------------------------------- registro ---

let filasRegistro = [];

async function cargarRegistro() {
  try { filasRegistro = await api("/api/registro"); } catch (e) { error(e); }
  pintarRegistro();
  if ($("#plegable-actividad").open) cargarActividad();
}

async function cargarActividad() {
  let filas = [];
  try { filas = await api("/api/actividad"); } catch (e) { error(e); }
  $("#tabla-actividad tbody").innerHTML = filas.length ? filas.map(f => `<tr>
      <td class="secundario">${esc(fechaHora(f.fecha))}</td><td>${esc(f.usuario)}</td>
      <td>${esc(f.accion)}</td><td class="secundario">${esc(f.detalle)}</td></tr>`).join("")
    : '<tr><td colspan="4" class="vacio">Todavía no hay actividad anotada.</td></tr>';
}
$("#plegable-actividad").addEventListener("toggle", ev => { if (ev.target.open) cargarActividad(); });
cargadores.registro = cargarRegistro;

function pintarRegistro() {
  const texto = $("#filtro-registro").value.trim().toLowerCase();
  const filas = filasRegistro.filter(f => !texto ||
    [f.alumno, f.grupo, f.nombre_modulo, f.modulo, f.profesor, f.fecha, f.estado, f.motivo_anulacion,
     f.generado_por, f.entregado_por, f.anulado_por].join(" ").toLowerCase().includes(texto));
  $("#tabla-registro tbody").innerHTML = filas.length ? filas.map(f => {
    const anulada = f.estado === "anulado";
    return `<tr class="${anulada ? "anulada" : ""}">
      <td>${esc(f.fecha)}</td>
      <td>${anulada ? `<span class="chip anulado" title="${esc(f.motivo_anulacion)}">${f.tipo === "PEC" ? "Pérdida 15 %" : "Aviso 7,5 %"}</span>` : chipTipo(f.tipo)}</td>
      <td>${anulada ? `<span class="tachado">${esc(f.alumno)}</span>
        <span class="motivo">Anulado el ${esc(fechaHora(f.fecha_anulacion))}${porQuien(f.anulado_por)}: ${esc(f.motivo_anulacion)}</span>` : esc(f.alumno)}
        ${f.fecha_entrega ? `<span class="motivo">Entregado el ${esc(fechaHora(f.fecha_entrega))}${porQuien(f.entregado_por)}</span>` : ""}</td>
      <td>${esc(f.grupo)}</td>
      <td class="secundario">${esc(f.nombre_modulo)}</td><td class="num">${esc(f.faltas_injustificadas)}</td>
      <td class="num">${esc(f.umbral)}</td><td class="secundario">${esc(f.profesor)}</td>
      <td class="secundario">${esc(fechaHora(f.fecha_proceso))}${f.generado_por ? `<span class="motivo">${porQuien(f.generado_por).trim()}</span>` : ""}</td>
      <td class="acciones-fila">${anulada ? "" : `<button class="enlace peligro" data-anular="${esc(f.documento)}">Anular</button>`}</td></tr>`;
  }).join("")
    : '<tr><td colspan="10" class="vacio">No hay avisos registrados.</td></tr>';
}
$("#filtro-registro").addEventListener("input", pintarRegistro);

$("#tabla-registro").addEventListener("click", async ev => {
  const documento = ev.target.dataset?.anular;
  if (!documento) return;
  const f = filasRegistro.find(x => x.documento === documento && x.estado !== "anulado");
  if (await anular([{ documento, alumno: f.alumno, grupo: f.grupo, modulo: f.nombre_modulo }])) cargarRegistro();
});

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
      <td class="acciones-fila"><button class="enlace" data-guardar-profesor>Guardar</button>
        <button class="enlace peligro" data-borrar-profesor>Borrar</button></td></tr>`).join("")
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
    } else if (ev.target.matches("[data-borrar-profesor]")) {
      const ok = await dialogo("Borrar profesor/a",
        `<p>Se quitará <b>${esc($("[name=firma]", fila).value)}</b> de la lista del profesorado.</p>
         <p class="nota">Sus avisos no se tocan. Si vuelve a llegar un informe suyo, se pedirá otra vez su firma.</p>`,
        [{ texto: "Cancelar", valor: false }, { texto: "Borrar", clase: "peligro", valor: true }]);
      if (!ok) return;
      await api("/api/profesor/borrar", { profesor: fila.dataset.profesor });
      tostada("Profesor/a borrado", "ok");
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
    $("#correo-detectado").textContent = r.thunderbird ? `Thunderbird encontrado: ${r.thunderbird}`
      : "No se encuentra Thunderbird en este ordenador: «Automático» descargará ficheros .eml";
    pintarCabecera(r.config, r.version);
    if (r.migracion?.length) {
      await dialogo(`Datos actualizados a WebPEC ${r.version}`,
        `<p>Al arrancar, WebPEC ha puesto al día los datos de la versión anterior. No se ha perdido nada.</p>
         <ul class="lista-modal">${r.migracion.map(h => `<li>${esc(h)}</li>`).join("")}</ul>`,
        [{ texto: "Entendido", clase: "principal", valor: true }]);
    }
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

// ------------------------------------------------------------- usuario ---

const camposNombre = `
  <div class="fila-campos">
    <label class="campo-motivo">Nombre<input id="profesor-nombre" placeholder="p. ej. José Antonio"></label>
    <label class="campo-motivo">Apellidos<input id="profesor-apellidos" placeholder="p. ej. Jiménez Castillo"></label>
  </div>`;

function pintarUsuario() { $("#nombre-usuario").textContent = usuario || "¿Quién eres?"; }

function fijarUsuario(nombre) {
  usuario = nombre;
  try { sessionStorage.setItem("webpec-usuario", nombre); } catch (e) { /* sin almacenamiento */ }
  guardarPreferencia("webpec-ultimo-usuario", nombre);
  pintarUsuario();
}

/** Pregunta quién usa WebPEC. Hasta que no se elige (o se da de alta), no se puede seguir. */
async function elegirUsuario() {
  let lista = [];
  try { lista = (await api("/api/usuarios")).usuarios; } catch (e) { error(e); }
  const ultimo = usuario || leerPreferencia("webpec-ultimo-usuario");
  for (;;) {
    const espera = dialogo("¿Quién eres?",
      `<p>WebPEC anota quién procesa, entrega y anula cada aviso.</p>
       ${lista.length ? `<label class="campo-motivo">Profesor/a<select id="usuario-elegido">
         ${lista.map(n => `<option ${n === ultimo ? "selected" : ""}>${esc(n)}</option>`).join("")}
         <option value="">Soy nuevo/a: no estoy en la lista</option></select></label>` : ""}
       <div id="usuario-nuevo" class="${lista.length ? "oculto" : ""}">
         <p class="nota">${lista.length ? "" : "Todavía no hay nadie registrado. "}Escribe tu nombre y tus apellidos
           como aparecen en Raíces (las tildes no importan): así WebPEC reconocerá tus informes.</p>${camposNombre}
       </div>`,
      [{ texto: "Entrar", clase: "principal", valor: true }]);
    const selector = $("#usuario-elegido");
    if (selector) selector.onchange = () => $("#usuario-nuevo").classList.toggle("oculto", selector.value !== "");
    const ok = await espera;
    if (!ok && usuario) return;  // cerrado sin elegir: se sigue como estaba
    if (selector && selector.value) { fijarUsuario(selector.value); return; }
    try {
      const r = await api("/api/profesor/nuevo", { nombre: $("#profesor-nombre").value, apellidos: $("#profesor-apellidos").value });
      fijarUsuario(r.firma);
      tostada(r.nuevo ? `Bienvenido/a, ${r.firma}` : `Ya estabas registrado/a como ${r.firma}`, "ok");
      return;
    } catch (e) { error(e); }
  }
}
$("#boton-usuario").addEventListener("click", elegirUsuario);

$("#boton-nuevo-profesor").addEventListener("click", async () => {
  const ok = await dialogo("Añadir profesor/a",
    `<p>Para quien todavía no tiene informes procesados. Escribe el nombre y los apellidos como aparecen en Raíces
      (las tildes no importan): cuando llegue su primer informe, WebPEC ya lo reconocerá.</p>${camposNombre}`,
    [{ texto: "Cancelar", valor: false }, { texto: "Añadir", clase: "principal", valor: true }]);
  if (!ok) return;
  try {
    const r = await api("/api/profesor/nuevo", { nombre: $("#profesor-nombre").value, apellidos: $("#profesor-apellidos").value });
    tostada(r.nuevo ? `Añadido: ${r.firma}` : `${r.firma} ya estaba en la lista`, "ok");
    cargarModulos();
  } catch (e) { error(e); }
});

// ------------------------------------------------------------ alumnado ---

let alumnado = { alumnos: [], informes: 0, sin_modulo: [], bajas: [] };

const SITUACIONES = {
  sin_avisos: () => '<span class="chip ok">Sin avisos</span>',
  supera: () => '<span class="chip info" title="Supera el 7,5 % pero no tiene un aviso vigente (p. ej. se anuló): el siguiente informe lo generará">Supera el 7,5 % sin aviso</span>',
  aviso: a => `${chipTipo("AVISO_PEC")}<span class="motivo">del ${esc(a.fecha_aviso)}${a.supera_15 ? " · ya supera el 15 %" : ""}</span>`,
  perdida: a => `${chipTipo("PEC")}<span class="motivo">del ${esc(a.fecha_perdida)}</span>`,
};

async function cargarAlumnado() {
  const cuerpo = $("#tabla-alumnado tbody");
  if (!alumnado.alumnos.length) cuerpo.innerHTML = '<tr><td colspan="11" class="cargando">Leyendo los informes procesados…</td></tr>';
  try { alumnado = await api("/api/alumnado"); } catch (e) { error(e); }
  for (const [id, campo, todos] of [["#filtro-al-grupo", "grupo", "Todos los grupos"],
    ["#filtro-al-modulo", "modulo", "Todos los módulos"], ["#filtro-al-profesor", "profesor", "Todos los profesores"]]) {
    const filtro = $(id), elegido = filtro.value;
    const valores = [...new Set(alumnado.alumnos.map(a => a[campo]))].sort();
    filtro.innerHTML = `<option value="">${todos}</option>` +
      valores.map(v => `<option ${v === elegido ? "selected" : ""}>${esc(v)}</option>`).join("");
  }
  pintarAlumnado();
}
cargadores.alumnado = cargarAlumnado;

function pintarAlumnado() {
  const [grupo, modulo, profesor, estado] = ["#filtro-al-grupo", "#filtro-al-modulo", "#filtro-al-profesor", "#filtro-al-estado"].map(s => $(s).value);
  const texto = $("#filtro-al-texto").value.trim().toLowerCase();
  const filas = alumnado.alumnos.filter(a => (!grupo || a.grupo === grupo) && (!modulo || a.modulo === modulo) &&
    (!profesor || a.profesor === profesor) && (!estado || a.estado === estado) &&
    (!texto || `${a.alumno} ${a.en_raices} ${a.correo}`.toLowerCase().includes(texto)));
  $("#tabla-alumnado tbody").innerHTML = filas.length ? filas.map(a => `<tr>
      <td>${esc(a.alumno)}${a.correo ? `<span class="motivo">${esc(a.correo)}</span>` : ""}</td>
      <td>${esc(a.grupo)}</td><td class="secundario" title="${esc(a.siglas)}">${esc(a.modulo)}</td>
      <td class="num">${a.fi}</td><td class="num">${esc(a.porcentaje)} %</td>
      <td class="num">${esc(a.umbral_75)}</td><td class="num">${esc(a.umbral_15)}</td>
      <td>${SITUACIONES[a.estado](a)}</td><td>${esc(a.informe)}</td><td class="secundario">${esc(a.profesor)}</td>
      <td class="acciones-fila apiladas" data-grupo="${esc(a.grupo)}" data-alumno="${esc(a.en_raices)}" data-siglas="${esc(a.siglas)}">
        <button class="enlace" data-editar>Editar</button><button class="enlace peligro" data-baja>Baja</button></td></tr>`).join("")
    : `<tr><td colspan="11" class="vacio">${alumnado.alumnos.length ? "Nadie coincide con los filtros."
        : "No hay informes procesados. La situación se calcula con los informes que se conservan en «Informes ya procesados»."}</td></tr>`;
  const con = n => alumnado.alumnos.filter(a => a.estado === n).length;
  $("#nota-alumnado").innerHTML = `Según el último informe procesado de cada módulo (${plural(alumnado.informes, "módulo", "módulos")}):
    ${plural(alumnado.alumnos.length, "alumno/a", "alumnos/as")} · ${con("aviso")} con aviso · ${con("perdida")} con pérdida
    ${con("supera") ? `· <b>${con("supera")} superan el 7,5 % sin aviso vigente</b>` : ""}` +
    (alumnado.sin_modulo.length ? `<br>⚠ Sin datos del módulo en la hoja: ${esc(alumnado.sin_modulo.join(", "))}` : "");
  $("#contador-bajas").textContent = alumnado.bajas.length;
  $("#tabla-bajas tbody").innerHTML = alumnado.bajas.length ? alumnado.bajas.map(b => `<tr>
      <td>${esc(b.nombre)}</td><td>${esc(b.grupo)}</td>
      <td>${b.modulo ? `<span class="secundario" title="${esc(b.modulo)}">${esc(b.nombre_modulo)}</span>` : "<b>Todos los módulos</b>"}</td>
      <td class="secundario">${esc(fechaHora(b.fecha))}${b.por ? `<span class="motivo">${porQuien(b.por).trim()}</span>` : ""}</td>
      <td class="secundario">${esc(b.motivo)}</td>
      <td class="acciones-fila" data-grupo="${esc(b.grupo)}" data-alumno="${esc(b.alumno)}" data-siglas="${esc(b.modulo)}">
        <button class="enlace" data-recuperar>Recuperar</button></td></tr>`).join("")
    : '<tr><td colspan="6" class="vacio">Nadie dado de baja.</td></tr>';
}
["#filtro-al-grupo", "#filtro-al-modulo", "#filtro-al-profesor", "#filtro-al-estado"].forEach(s => $(s).addEventListener("change", pintarAlumnado));
$("#filtro-al-texto").addEventListener("input", pintarAlumnado);

/** Separa «Apellidos, Nombre» para rellenar el formulario. */
function partesNombre(completo) {
  const i = completo.indexOf(",");
  return i < 0 ? [completo.trim(), ""] : [completo.slice(0, i).trim(), completo.slice(i + 1).trim()];
}

async function editarAlumno(grupo, enRaices) {
  const a = alumnado.alumnos.find(x => x.grupo === grupo && x.en_raices === enRaices);
  const [apellidos, nombre] = partesNombre(a.alumno);
  const ok = await dialogo("Editar alumno/a",
    `<p>${esc(grupo)} · en Raíces: <b>${esc(enRaices)}</b></p>
     <label class="campo-motivo">Apellidos<input id="alumno-apellidos" value="${esc(apellidos)}"></label>
     <label class="campo-motivo">Nombre<input id="alumno-nombre" value="${esc(nombre)}"></label>
     <label class="campo-motivo">Correo electrónico<input id="alumno-correo" type="email" value="${esc(a.correo)}"
       placeholder="vacío: sin correo"></label>
     <p class="nota">El nombre corregido se usa en los listados, en los correos y en los avisos que se generen a partir de
       ahora (los ya generados no cambian). Los informes de Raíces se siguen reconociendo con el nombre original.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Guardar", clase: "principal", valor: true, requiere: "#alumno-apellidos" }]);
  if (!ok) return;
  try {
    await api("/api/alumno/editar", { grupo, alumno: enRaices, apellidos: $("#alumno-apellidos").value,
      nombre: $("#alumno-nombre").value, correo: $("#alumno-correo").value });
    tostada("Datos del alumno/a guardados", "ok");
    cargarAlumnado();
  } catch (e) { error(e); }
}

async function darDeBaja(grupo, enRaices, siglas) {
  const filas = alumnado.alumnos.filter(x => x.grupo === grupo && x.en_raices === enRaices);
  const nombre = filas[0].alumno;
  const casillas = filas.map(x => `<label class="casilla-modulo"><input type="checkbox" name="modulo-baja"
      value="${esc(x.siglas)}" ${x.siglas === siglas ? "checked" : ""}><span>${esc(x.modulo)} <span class="secundario">(${esc(x.siglas)})</span></span></label>`).join("");
  const ok = await dialogo("Dar de baja",
    `<p><b>${esc(nombre)}</b> (${esc(grupo)}) dejará de aparecer en Alumnado y <b>no recibirá avisos nuevos</b> en los
       módulos que marques, aunque siga saliendo en los informes de Raíces.</p>
     <div class="lista-modulos">${casillas}
       <label class="casilla-modulo"><input type="checkbox" id="baja-todos"><span><b>Todos sus módulos de ${esc(grupo)}</b>
         <span class="secundario">(baja en el centro: también los de informes futuros)</span></span></label></div>
     <p class="nota">Los avisos ya generados y el registro se conservan. Si te equivocas, se puede recuperar en
       «Alumnado dado de baja», al final de esta pestaña.</p>
     <label class="campo-motivo">Motivo (opcional)<input id="motivo-baja" maxlength="200"
       placeholder="p. ej. Baja en el centro el 15/10/2026, convalidación…"></label>
     <input type="hidden" id="baja-elegidos" value="si">`,
    [{ texto: "Cancelar", valor: false }, { texto: "Dar de baja", clase: "peligro", valor: true, requiere: "#baja-elegidos" }]);
  if (!ok) return;
  const todos = $("#baja-todos").checked;
  const modulos = todos ? [] : [...document.querySelectorAll("[name=modulo-baja]:checked")].map(c => c.value);
  try {
    const r = await api("/api/alumno/baja", { grupo, alumno: enRaices, modulos, motivo: $("#motivo-baja").value });
    tostada(`${r.nombre}: dado/a de baja en ${todos ? "todos los módulos" : plural(modulos.length, "módulo", "módulos")}`, "ok");
    if (r.pendientes.length) {
      await dialogo("Avisos pendientes de entregar",
        `<p>${esc(r.nombre)} tiene ${plural(r.pendientes.length, "aviso", "avisos")} de esos módulos en <b>Pendientes de entregar</b>:</p>
         <ul class="lista-modal">${r.pendientes.map(d => `<li>${esc(d)}</li>`).join("")}</ul>
         <p class="nota">Si ya no se van a entregar, anúlalos desde la pestaña Avisos (motivo: la baja).</p>`,
        [{ texto: "Entendido", clase: "principal", valor: true }]);
    }
    cargarAlumnado();
    contarPendientes();
  } catch (e) { error(e); }
}

// El botón «Dar de baja» solo se activa con algún módulo marcado (o «Todos»)
$("#modal").addEventListener("change", ev => {
  const oculto = $("#baja-elegidos");
  if (!oculto || !(ev.target.name === "modulo-baja" || ev.target.id === "baja-todos")) return;
  const todos = $("#baja-todos").checked;
  document.querySelectorAll("[name=modulo-baja]").forEach(c => { c.disabled = todos; });
  oculto.value = todos || document.querySelector("[name=modulo-baja]:checked") ? "si" : "";
  oculto.oninput();
});

$("#vista-alumnado").addEventListener("click", async ev => {
  const celda = ev.target.closest("[data-alumno]");
  if (!celda || ev.target.tagName !== "BUTTON") return;
  const { grupo, alumno, siglas } = celda.dataset;
  if ("editar" in ev.target.dataset) editarAlumno(grupo, alumno);
  if ("baja" in ev.target.dataset) darDeBaja(grupo, alumno, siglas);
  if ("recuperar" in ev.target.dataset) {
    try {
      await api("/api/alumno/recuperar", { grupo, alumno, modulo: siglas });
      tostada("Baja deshecha: vuelve a la lista y a recibir avisos", "ok");
      cargarAlumnado();
    } catch (e) { error(e); }
  }
});

$("#boton-importar-correos").addEventListener("click", async () => {
  const ok = await dialogo("Importar correos del alumnado",
    `<p>Elige un fichero CSV o Excel con el nombre del alumno/a y su correo (por ejemplo, una exportación de Raíces o
      de EducaMadrid). Las columnas se reconocen solas; si hay columna de grupo o unidad, también se usa.</p>
     <p class="nota">Los correos solo se guardan como dato: WebPEC no envía nada. Los que ya estaban se actualizan.</p>
     <label class="campo-motivo">Grupo (solo si el fichero no lo indica; puede quedar vacío)<input id="grupo-correos" placeholder="p. ej. ASIR2A"></label>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Elegir fichero…", clase: "principal", valor: true }]);
  if (!ok) return;
  $("#selector-correos").dataset.grupo = $("#grupo-correos").value.trim();
  $("#selector-correos").click();
});
$("#selector-correos").addEventListener("change", async ev => {
  const fichero = ev.target.files[0];
  ev.target.value = "";
  if (!fichero) return;
  try {
    const r = await subirFichero("/api/correos/importar", fichero, { grupo: ev.target.dataset.grupo || "" });
    tostada(`Correos: ${r.leidos} leídos, ${r.nuevos} nuevos, ${r.actualizados} actualizados`, "ok");
    cargarAlumnado();
  } catch (e) { error(e); }
});

// ------------------------------------------------- exportar e importar ---

$("#boton-exportar").addEventListener("click", () => {
  window.location.href = `/datos/exportar?usuario=${encodeURIComponent(usuario)}`;
});
$("#boton-importar").addEventListener("click", async () => {
  const ok = await dialogo("Importar datos",
    `<p>Los datos de este WebPEC se <b>sustituirán</b> por los del ZIP (uno exportado con «Exportar datos», de este u otro
      ordenador; también de una versión anterior).</p>
     <p class="nota">Antes se guarda una copia de los datos actuales en COPIAS_SEGURIDAD, por si hay que volver atrás.</p>`,
    [{ texto: "Cancelar", valor: false }, { texto: "Elegir el ZIP…", clase: "peligro", valor: true }]);
  if (ok) $("#selector-datos").click();
});
$("#selector-datos").addEventListener("change", async ev => {
  const fichero = ev.target.files[0];
  ev.target.value = "";
  if (!fichero) return;
  try {
    const r = await subirFichero("/api/datos/importar", fichero);
    await dialogo("Datos importados",
      `<p>Se han importado ${plural(r.ficheros, "fichero", "ficheros")}. Los datos anteriores quedan en <b>${esc(r.copia)}</b>.</p>
       ${r.migracion.length ? `<ul class="lista-modal">${r.migracion.map(h => `<li>${esc(h)}</li>`).join("")}</ul>` : ""}
       <p class="nota">Si el puerto o el acceso en red han cambiado, se aplicarán al volver a arrancar WebPEC.</p>`,
      [{ texto: "Recargar", clase: "principal", valor: true }]);
    location.reload();
  } catch (e) { error(e); }
});

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
    <h1>WebPEC se ha cerrado</h1><p>Ya puedes cerrar esta pestaña.</p>
    <p class="licencia-cierre">WebPEC © 2026 Departamento de Informática del IES Rosa Chacel (Madrid)<br>
      Se puede usar, copiar y modificar libremente citando al autor, sin fines comerciales y compartiendo con la misma licencia:<br>
      <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.es" target="_blank" rel="license noopener">
        <span class="cc">CC BY-NC-SA 4.0</span> Reconocimiento-NoComercial-CompartirIgual 4.0 Internacional</a></p></div>`;
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
     <p class="nota">Pensado para limpiar al terminar el curso: se borran los documentos, pero el registro los conserva
       y no se volverán a generar. Para quitar un aviso emitido por error, usa <b>Anular</b>.</p>`,
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

pintarUsuario();
contarPendientes();
// Primero el aviso de datos actualizados (si lo hay) y después, si hace falta, quién eres
cargarConfig().then(() => { if (!usuario) elegirUsuario(); });
const vistaInicial = location.hash.slice(1) || leerPreferencia("webpec-vista");
mostrarVista($(`#vista-${vistaInicial}`) ? vistaInicial : "informes");

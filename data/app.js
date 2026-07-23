const $ = id => document.getElementById(id);

const fmt  = n => Math.round(n || 0).toLocaleString("es-PE");
const fmtS = n => "S/ " + fmt(n);

function fechaHoy() {
  const d = new Date();
  const dias  = ["domingo","lunes","martes","miércoles","jueves","viernes","sábado"];
  const meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
                 "agosto","septiembre","octubre","noviembre","diciembre"];
  return `${dias[d.getDay()]}, ${d.getDate()} de ${meses[d.getMonth()]} de ${d.getFullYear()}`;
}

function fechaCorta() {
  const d = new Date();
  const meses = ["enero","febrero","marzo","abril","mayo","junio","julio",
                 "agosto","septiembre","octubre","noviembre","diciembre"];
  return `${d.getDate()} de ${meses[d.getMonth()]} de ${d.getFullYear()}`;
}

function colorSem(pct) {
  if (pct === null) return "#888";
  if (pct >= 70)   return "var(--verde)";
  if (pct >= 40)   return "var(--amarillo-s)";
  return "var(--rojo-s)";
}

function barraHTML(pct) {
  if (pct === null) {
    return '<span style="font-family:\'Barlow Condensed\';font-weight:700;color:#888;font-size:13px">N/A</span>';
  }
  const col = colorSem(pct);
  const w   = Math.min(100, pct).toFixed(1);
  return `<div class="av-wrap">
    <div class="av-bar"><span style="width:${w}%;background:${col}"></span></div>
    <span class="av-pct" style="color:${col}">${pct.toFixed(1)}%</span>
  </div>`;
}

function toNum(v) {
  if (v == null || v === "") return 0;
  const s = String(v).replace(/,/g, "").trim();
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

function esFilaDato(row) {
  const c0 = String(row[0] || "").trim();
  if (!c0) return false;
  if (/^total\b/i.test(c0))                           return false;
  if (/^nivel de gobierno/i.test(c0))                 return false;
  if (/^gob\.loc/i.test(c0))                          return false;
  if (/^departamento/i.test(c0))                      return false;
  if (/^municipalidad\b/i.test(c0) &&
      !/^\d{6}-/.test(c0))                            return false;
  if (/^fuente de financiamiento/i.test(c0))          return false;
  if (/^rubro$/i.test(c0))                            return false;
  if (/^genérica$/i.test(c0))                         return false;
  if (/^consulta amigable/i.test(c0))                 return false;
  const pim = toNum(row[2]);
  const rec = toNum(row[3]);
  return pim > 0 || rec > 0;
}

function detectarTipo(registros) {
  if (!registros.length) return "desconocido";
  const c0 = String(registros[0].descripcion || "");
  if (/^\d{6}-\d+:/.test(c0)) return "ranking";
  if (/^0\d:/.test(c0))       return "rubro";
  const todas = registros.map(r => String(r.descripcion || "").toUpperCase()).join(" ");
  if (/RECURSOS DIRECTAMENTE|RECURSOS DETERMINADOS|OPERACIONES OFICIALES/.test(todas))
    return "fuente";
  return "generica";
}

function parsearIngresos(arrayBuffer, nombreArchivo) {
  try {
    const u8 = new Uint8Array(arrayBuffer);
    const wb = XLSX.read(u8, { type: "array", codepage: 1252 });

    const registros = [];
    let totalPIA = 0, totalPIM = 0, totalRec = 0;
    let totalEncontrado = false;

    for (const sheetName of wb.SheetNames) {
      const aoa = XLSX.utils.sheet_to_json(
        wb.Sheets[sheetName],
        { header: 1, blankrows: false, raw: false }
      );

      for (const row of aoa) {
        const c0 = String(row[0] || "").trim();

        if (/Municipalidad\s+140301/i.test(c0) && !totalEncontrado) {
          totalPIA = toNum(row[1]);
          totalPIM = toNum(row[2]);
          totalRec = toNum(row[3]);
          totalEncontrado = true;
          continue;
        }

        if (!esFilaDato(row)) continue;

        registros.push({
          descripcion: c0,
          pia: toNum(row[1]),
          pim: toNum(row[2]),
          rec: toNum(row[3])
        });
      }
      if (registros.length) break;
    }

    if (!registros.length) return null;

    const tipo = detectarTipo(registros);

    if (!totalEncontrado) {
      totalPIA = registros.reduce((s, r) => s + r.pia, 0);
      totalPIM = registros.reduce((s, r) => s + r.pim, 0);
      totalRec = registros.reduce((s, r) => s + r.rec, 0);
    }

    return { tipo, totalPIA, totalPIM, totalRec, registros };
  } catch (e) {
    console.warn("[MPL] parsearIngresos error:", nombreArchivo, e.message);
    return null;
  }
}

const ARCHIVOS_ESPERADOS = ["fuente.xls", "generica.xls", "rubro.xls", "ranking.xls"];
let datos = {};
let cargados = new Set();

async function autoCargar() {
  for (const nombre of ARCHIVOS_ESPERADOS) {
    try {
      const r = await fetch("xls/" + nombre + "?" + Date.now());
      if (!r.ok) continue;
      const buf = await r.arrayBuffer();
      const res = parsearIngresos(buf, nombre);
      if (res) {
        datos[res.tipo] = res;
        cargados.add(nombre);
        actualizarFileList();
        render();
        console.log("[MPL] Auto-cargado: xls/" + nombre, "→ tipo:", res.tipo,
                    "| registros:", res.registros.length,
                    "| PIM:", res.totalPIM, "| Rec:", res.totalRec);
      }
    } catch (e) { /* archivo no disponible */ }
  }
}

function procesarArchivos(files) {
  Array.from(files).forEach(file => {
    const reader = new FileReader();
    reader.onload = e => {
      const res = parsearIngresos(e.target.result, file.name);
      if (res) {
        datos[res.tipo] = res;
        cargados.add(file.name);
        actualizarFileList();
        render();
        console.log("[MPL] Manual:", file.name, "→ tipo:", res.tipo,
                    "| registros:", res.registros.length);
      } else {
        console.warn("[MPL] No se pudo parsear:", file.name);
      }
    };
    reader.readAsArrayBuffer(file);
  });
}

function actualizarFileList() {
  const fl = $("fileList");
  if (!fl) return;
  fl.innerHTML = ARCHIVOS_ESPERADOS.map(f => {
    const ok = cargados.has(f);
    return `<div class="file-item">
      <span class="${ok ? "fi-ok" : "fi-wait"}">${ok ? "✓" : "○"}</span>
      <span class="fi-name">${f}</span>
    </div>`;
  }).join("");
}

function render() {
  const hoy = fechaHoy();
  ["b1fecha","b2fecha","b3fecha","b4fecha"].forEach(id => {
    const el = $(id); if (el) el.textContent = hoy;
  });
  renderB1();
  renderB2();
  renderB3();
  renderB4();
  renderB5();
  renderB6();
  renderB7();
}

function renderB1() {
  const d = datos.rubro || datos.fuente;
  if (!d) return;

  const pia = d.totalPIA, pim = d.totalPIM, rec = d.totalRec;
  const pct    = pim > 0 ? rec / pim * 100 : null;
  const pend   = pim - rec;
  const difPIA = pim - pia;
  const pctPIA = pia > 0 ? difPIA / pia * 100 : 0;

  const hoy   = new Date();
  const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

  $("kpi-pia").textContent = fmtS(pia);
  $("kpi-pim").textContent = fmtS(pim);
  $("kpi-pim-sub").textContent =
    (pctPIA >= 0 ? "+" : "") + pctPIA.toFixed(1) +
    "% sobre PIA · Modificaciones al " + hoy.getDate() + "-" + meses[hoy.getMonth()];
  $("kpi-rec").textContent = fmtS(rec);
  $("kpi-pct").textContent = pct !== null ? pct.toFixed(1) + "%" : "N/A";
  $("kpi-pct-sub").textContent = pct !== null
    ? "Pendiente de recaudar: " + fmtS(Math.max(0, pend))
    : "PIM = 0";
}

function renderB2() {
  const d     = datos.fuente;
  const tbody = $("b2tbody"), tfoot = $("b2tfoot"), nota = $("b2nota");
  if (!d || !d.registros.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="vacio">Carga fuente.xls para ver los datos.</td></tr>';
    return;
  }

  const notas = [];
  tbody.innerHTML = d.registros.map(r => {
    const pend  = r.pim - r.rec;
    const pct   = r.pim > 0 ? r.rec / r.pim * 100 : (r.rec > 0 ? null : 0);
    const nombre = r.descripcion.replace(/^\d+:\s*/, "");
    const cod    = (r.descripcion.match(/^(\d+)/) || ["",""])[1];
    if (r.pim === 0 && r.rec > 0) {
      notas.push(`<strong>${cod}: ${nombre.substring(0,50)}</strong> — PIA y PIM = S/ 0 con Recaudado = S/ ${fmt(r.rec)}. Corresponde a rendimientos sin presupuesto asignado. Se muestra como "N/A".`);
    }
    return `<tr>
      <td style="font-weight:600">${cod}: ${nombre}</td>
      <td class="num">${fmtS(r.pia)}</td>
      <td class="num">${fmtS(r.pim)}</td>
      <td class="num">${fmtS(r.rec)}</td>
      <td class="num" style="color:${pend < 0 ? "var(--rojo-s)" : "inherit"}">${fmtS(pend)}</td>
      <td>${barraHTML(pct)}</td>
    </tr>`;
  }).join("");

  const tp = d.totalPIM, tr_ = d.totalRec, tpia = d.totalPIA;
  const tpct = tp > 0 ? tr_ / tp * 100 : null;
  tfoot.innerHTML = `<tr>
    <td style="font-family:'Barlow Condensed';font-weight:800;text-transform:uppercase">TOTAL</td>
    <td class="num">${fmtS(tpia)}</td>
    <td class="num">${fmtS(tp)}</td>
    <td class="num">${fmtS(tr_)}</td>
    <td class="num">${fmtS(tp - tr_)}</td>
    <td>${barraHTML(tpct)}</td>
  </tr>`;

  if (notas.length) { nota.style.display = ""; nota.innerHTML = "⚠️ " + notas.join("<br/>⚠️ "); }
  else nota.style.display = "none";
}

function renderB3() {
  const d     = datos.rubro;
  const tbody = $("b3tbody"), tfoot = $("b3tfoot"), nota = $("b3nota");
  if (!d || !d.registros.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="vacio">Carga rubro.xls para ver los datos.</td></tr>';
    return;
  }

  const notas = [];
  tbody.innerHTML = d.registros.map(r => {
    const pend   = r.pim - r.rec;
    const pct    = r.pim > 0 ? r.rec / r.pim * 100 : (r.rec > 0 ? null : 0);
    const cod    = (r.descripcion.match(/^(\d+)/) || ["",""])[1];
    const nombre = r.descripcion.replace(/^\d+:\s*/, "").trim();
    if (r.pim === 0 && r.rec > 0)
      notas.push(`<strong>Rubro ${cod}:</strong> PIA y PIM = S/ 0 con Recaudado > 0. Ver nota en Bloque 2.`);
    if (r.pim > 0 && r.rec > r.pim)
      notas.push(`<strong>Rubro ${cod} (${nombre.substring(0,40)}):</strong> Recaudado (S/ ${fmt(r.rec)}) supera el PIM (S/ ${fmt(r.pim)}). Ocurre cuando se perciben saldos de períodos anteriores no presupuestados. Comportamiento normal en recursos Canon.`);
    return `<tr>
      <td class="cod">${cod}</td>
      <td style="font-weight:600">${nombre}</td>
      <td class="num">${fmtS(r.pia)}</td>
      <td class="num">${fmtS(r.pim)}</td>
      <td class="num">${fmtS(r.rec)}</td>
      <td class="num" style="color:${pend < 0 ? "var(--rojo-s)" : "inherit"}">${fmtS(pend)}</td>
      <td>${barraHTML(pct)}</td>
    </tr>`;
  }).join("");

  const tp = d.totalPIM, tr_ = d.totalRec, tpia = d.totalPIA;
  const tpct = tp > 0 ? tr_ / tp * 100 : null;
  tfoot.innerHTML = `<tr>
    <td class="cod">—</td>
    <td style="font-family:'Barlow Condensed';font-weight:800;text-transform:uppercase">TOTAL</td>
    <td class="num">${fmtS(tpia)}</td>
    <td class="num">${fmtS(tp)}</td>
    <td class="num">${fmtS(tr_)}</td>
    <td class="num">${fmtS(tp - tr_)}</td>
    <td>${barraHTML(tpct)}</td>
  </tr>`;

  if (notas.length) { nota.style.display = ""; nota.innerHTML = "⚠️ " + notas.join("<br/>⚠️ "); }
  else nota.style.display = "none";
}

function renderB4() {
  const d     = datos.generica;
  const tbody = $("b4tbody"), tfoot = $("b4tfoot"), nota = $("b4nota");
  if (!d || !d.registros.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="vacio">Carga generica.xls para ver los datos.</td></tr>';
    return;
  }

  const notas = [];
  tbody.innerHTML = d.registros.map(r => {
    const pend   = r.pim - r.rec;
    const pct    = r.pim > 0 ? r.rec / r.pim * 100 : (r.rec > 0 ? null : 0);
    const cod    = (r.descripcion.match(/^(\d+)/) || ["",""])[1];
    const nombre = r.descripcion.replace(/^\d+:\s*/, "").trim();
    if (r.pim > 0 && r.rec > r.pim)
      notas.push(`<strong>Genérica ${cod} (${nombre.substring(0,50)}):</strong> Puede superar el 100% de recaudación. Los saldos de balance son recursos del año anterior incorporados al presupuesto.`);
    return `<tr>
      <td class="cod">${cod}</td>
      <td style="font-weight:600">${nombre}</td>
      <td class="num">${fmtS(r.pia)}</td>
      <td class="num">${fmtS(r.pim)}</td>
      <td class="num">${fmtS(r.rec)}</td>
      <td class="num" style="color:${pend < 0 ? "var(--rojo-s)" : "inherit"}">${fmtS(pend)}</td>
      <td>${barraHTML(pct)}</td>
    </tr>`;
  }).join("");

  const tp = d.totalPIM, tr_ = d.totalRec, tpia = d.totalPIA;
  const tpct = tp > 0 ? tr_ / tp * 100 : null;
  tfoot.innerHTML = `<tr>
    <td class="cod">—</td>
    <td style="font-family:'Barlow Condensed';font-weight:800;text-transform:uppercase">TOTAL</td>
    <td class="num">${fmtS(tpia)}</td>
    <td class="num">${fmtS(tp)}</td>
    <td class="num">${fmtS(tr_)}</td>
    <td class="num">${fmtS(tp - tr_)}</td>
    <td>${barraHTML(tpct)}</td>
  </tr>`;

  if (notas.length) { nota.style.display = ""; nota.innerHTML = "⚠️ " + notas.join("<br/>⚠️ "); }
  else nota.style.display = "none";
}

function renderB5() {
  const d     = datos.ranking;
  const tbody = $("b5tbody"), nota = $("b5nota"), hl = $("b5highlight");
  if (!d || !d.registros.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="vacio">Carga ranking.xls para ver los datos.</td></tr>';
    hl.textContent = "Carga ranking.xls para ver la posición de la Municipalidad Provincial de Lambayeque.";
    return;
  }

  const muns = d.registros.map(r => {
    const pct       = r.pim > 0 ? r.rec / r.pim * 100 : null;
    const nombre    = r.descripcion.replace(/^\d{6}-\d+:\s*/, "").trim();
    const nombreFmt = nombre.split(" ").map((w, i) =>
      i === 0 || w.length > 2 ? w[0] + w.slice(1).toLowerCase() : w.toLowerCase()
    ).join(" ");
    const esMPL = r.descripcion.includes("140301") ||
                  (/LAMBAYEQUE/i.test(r.descripcion) && /PROVINCIAL/i.test(r.descripcion));
    return { ...r, pct, nombre: nombreFmt, esMPL };
  });

  const porPct   = [...muns].sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));
  const porMonto = [...muns].sort((a, b) => (b.rec || 0) - (a.rec || 0));

  const posPct   = porPct.findIndex(m => m.esMPL) + 1;
  const posMonto = porMonto.findIndex(m => m.esMPL) + 1;
  const mpl      = muns.find(m => m.esMPL);

  if (mpl) {
    const pctStr = mpl.pct !== null ? mpl.pct.toFixed(1) + "%" : "N/A";
    hl.innerHTML =
      `&#128269; La <strong>Municipalidad Provincial de Lambayeque</strong> ocupa el puesto
       <strong>${posPct}° de ${muns.length}</strong> en % de recaudación sobre PIM (${pctStr}).
       Por <strong>monto recaudado absoluto</strong>, se ubica en el puesto
       <strong>${posMonto}° de ${muns.length}</strong> con ${fmtS(mpl.rec)}.`;
  }

  tbody.innerHTML = porPct.map((m, i) => {
    const pos      = i + 1;
    const trC      = m.esMPL ? 'class="mpl-row"' : "";
    const posStyle = pos <= 3 ? 'style="color:var(--dorado-osc);font-weight:800"' : 'style="font-weight:700"';
    return `<tr ${trC}>
      <td style="text-align:center" ${posStyle}>${pos}°</td>
      <td style="font-weight:${m.esMPL ? "700" : "500"}">${m.nombre}</td>
      <td class="num">${fmtS(m.pia)}</td>
      <td class="num">${fmtS(m.pim)}</td>
      <td class="num">${fmtS(m.rec)}</td>
      <td>${barraHTML(m.pct)}</td>
    </tr>`;
  }).join("");

  nota.style.display = "";
}

$("pick").addEventListener("click", () => $("file").click());
$("dropzone").addEventListener("click", () => $("file").click());
$("dropzone").addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); }
});
$("file").addEventListener("change", e => {
  procesarArchivos(e.target.files); e.target.value = "";
});
$("clear").addEventListener("click", () => {
  datos = {}; cargados = new Set(); actualizarFileList(); render();
});

const dz = $("dropzone");
["dragenter","dragover"].forEach(ev =>
  dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave","drop"].forEach(ev =>
  dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", e => {
  if (e.dataTransfer.files.length) procesarArchivos(e.dataTransfer.files);
});

let pdfLibsCargadas = false;
let b6ChartInstance = null;
let B6_HIST = {};

// Carga historico.json como única fuente de verdad para los datos históricos
fetch("data/historico.json?" + Date.now())
  .then(r => r.json())
  .then(data => {
    B6_HIST = data;
    renderB6();
  })
  .catch(() => console.warn("[MPL] No se pudo cargar historico.json"));

function renderB6() {
  const dev2026 = datos.rubro ? (datos.rubro.totalRec || 0) : 0;

  // Construir serie desde historico.json + 2026 dinámico
  const añosHist = Object.keys(B6_HIST).map(Number).sort();
  const años     = [...añosHist, 2026];
  const valores  = [...añosHist.map(a => B6_HIST[a]), dev2026];
  const IDX_2026 = años.length - 1; // siempre el último

  const fmtM = n => {
    if (!n) return "S/ —";
    if (n >= 1e6) return "S/ " + (n / 1e6).toLocaleString("es-PE",
                    { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " M";
    return "S/ " + Math.round(n).toLocaleString("es-PE");
  };

  // KPI cards
  const kpiContainer = $("b6kpis");
  if (kpiContainer) {
    kpiContainer.innerHTML = años.map((a, i) => {
      const v      = valores[i];
      const es2026 = a === 2026;
      const prev   = i > 0 ? valores[i - 1] : null;
      let deltaHtml = "";
      if (prev && prev > 0 && v > 0) {
        const pct   = (v - prev) / prev * 100;
        const color = pct >= 0 ? "#2a7d46" : "#c0392b";
        const signo = pct >= 0 ? "▲" : "▼";
        deltaHtml = `<span style="font-size:10px;color:${color};font-weight:700">${signo} ${Math.abs(pct).toFixed(1)}%</span>`;
      }
      return `<div style="background:${es2026 ? "#fef3c7" : "#f9fafb"};border:1px solid ${es2026 ? "#fbbf24" : "#e5e7eb"};
               border-radius:10px;padding:10px 16px;min-width:110px;flex:1;text-align:center">
        <div style="font-family:'Barlow Condensed';font-size:13px;font-weight:700;color:#6b7280;margin-bottom:3px">
          Ene–Jul ${a}${es2026 ? " ★" : ""}
        </div>
        <div style="font-family:'Barlow Condensed';font-size:18px;font-weight:800;color:${es2026 ? "#92400e" : "#1f2937"}">
          ${v ? fmtM(v) : "Cargando…"}
        </div>
        <div style="margin-top:3px">${deltaHtml}</div>
      </div>`;
    }).join("");
  }

  const canvas = $("b6chart");
  if (!canvas) return;

  if (b6ChartInstance) { b6ChartInstance.destroy(); b6ChartInstance = null; }

  const colores      = años.map(a => a === 2026 ? "#FFC526" : "#9a1820");
  const borderColores = años.map(a => a === 2026 ? "#d9a000" : "#7a1219");

  b6ChartInstance = new Chart(canvas, {
    type: "bar",
    data: {
      labels: años.map(a => `Ene–Jul ${a}${a === 2026 ? " ★" : ""}`),
      datasets: [{
        label: "Recaudado Ene–Jul",
        data: valores,
        backgroundColor: colores,
        borderColor: borderColores,
        borderWidth: 2,
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.raw;
              if (!v) return " Sin datos";
              return ` S/ ${Math.round(v).toLocaleString("es-PE")}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: "'Barlow Condensed'", weight: "700", size: 12 },
            // FIX: IDX_2026 es el índice real del año 2026 (no hardcodeado)
            color: ctx => ctx.index === IDX_2026 ? "#92400e" : "#374151"
          }
        },
        y: {
          beginAtZero: false,
          ticks: {
            callback: v => {
              if (v >= 1e6) return "S/ " + (v / 1e6).toFixed(1) + " M";
              if (v >= 1e3) return "S/ " + (v / 1e3).toFixed(0) + " K";
              return "S/ " + v;
            },
            font: { family: "'Barlow'", size: 11 },
            color: "#6b7280"
          },
          grid: { color: "#f3f4f6" }
        }
      },
      animation: { duration: 600 }
    },
    plugins: [{
      id: "b6Labels",
      afterDatasetsDraw(chart) {
        const { ctx, data } = chart;
        ctx.save();
        data.datasets[0].data.forEach((value, i) => {
          if (!value) return;
          const meta = chart.getDatasetMeta(0);
          const bar  = meta.data[i];
          const txt  = "S/ " + (value / 1e6).toLocaleString("es-PE",
                         { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " M";
          // FIX: usar IDX_2026 en lugar de 4 hardcodeado
          ctx.fillStyle    = i === IDX_2026 ? "#92400e" : "#7a1219";
          ctx.font         = "700 12px 'Barlow Condensed'";
          ctx.textAlign    = "center";
          ctx.textBaseline = "bottom";
          ctx.fillText(txt, bar.x, bar.y - 8);
        });
        ctx.restore();
      }
    }]
  });
}

function exportarPDF() {
  if (!pdfLibsCargadas) {
    const s1 = document.createElement("script");
    s1.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
    s1.onload = () => {
      const s2 = document.createElement("script");
      s2.src = "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js";
      s2.onload = () => { pdfLibsCargadas = true; generarPDF(); };
      document.head.appendChild(s2);
    };
    document.head.appendChild(s1);
  } else { generarPDF(); }
}

function generarPDF() {
  const { jsPDF } = window.jspdf;
  html2canvas(document.body, { scale: 1.5, useCORS: true, logging: false }).then(canvas => {
    const pdf    = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
    const pw     = pdf.internal.pageSize.getWidth();
    const ph     = pdf.internal.pageSize.getHeight();
    const sliceH = Math.round(canvas.width * ph / pw);
    let yOff = 0;
    while (yOff < canvas.height) {
      if (yOff > 0) pdf.addPage();
      const sl = document.createElement("canvas");
      sl.width  = canvas.width;
      sl.height = Math.min(sliceH, canvas.height - yOff);
      sl.getContext("2d").drawImage(canvas, 0, -yOff);
      pdf.addImage(sl.toDataURL("image/jpeg", 0.85), "JPEG", 0, 0, pw, ph);
      yOff += sliceH;
    }
    const hoy = new Date();
    pdf.save(`MPL_Ingresos_${String(hoy.getDate()).padStart(2,"0")}${String(hoy.getMonth()+1).padStart(2,"0")}${hoy.getFullYear()}.pdf`);
  });
}

$("fechaHeader").textContent = fechaCorta();
["b1fecha","b2fecha","b3fecha","b4fecha"].forEach(id => {
  const el = $(id); if (el) el.textContent = fechaHoy();
});
autoCargar();

// ═══════════════════════════════════════════════════════════════
//  BLOQUE 7 — COMPARATIVO HISTÓRICO RUBRO 08: IMPUESTOS MUNICIPALES
// ═══════════════════════════════════════════════════════════════

let B7_HIST = {};
let b7ChartInstance = null;

const B7_MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul"];

fetch("data/historico_rubro08.json?" + Date.now())
  .then(r => r.json())
  .then(data => {
    B7_HIST = data;
    renderB7();
  })
  .catch(() => console.warn("[MPL] No se pudo cargar historico_rubro08.json"));

function getRubro08_2026() {
  if (!datos.rubro || !datos.rubro.registros) return 0;
  const r08 = datos.rubro.registros.find(r => {
    const cod = (r.descripcion.match(/^(\d+)/) || ["",""])[1];
    return cod === "08";
  });
  return r08 ? (r08.rec || 0) : 0;
}

function renderB7() {
  const rec2026 = getRubro08_2026();

  const añosHist = Object.keys(B7_HIST).map(Number).sort();
  const años     = [...añosHist, 2026];
  const IDX_2026 = años.length - 1;

  // Totales Ene-Jul por año (históricos desde JSON, 2026 del rubro.xls diario)
  const totales = [...añosHist.map(a => B7_HIST[String(a)].total), rec2026];

  // Datos mensuales por año (para la leyenda de barras agrupadas)
  const mesesPorAnio = añosHist.map(a => B7_HIST[String(a)].meses);

  const fmtM = n => {
    if (!n) return "S/ —";
    if (n >= 1e6) return "S/ " + (n / 1e6).toLocaleString("es-PE",
                    { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " M";
    if (n >= 1e3) return "S/ " + (n / 1e3).toLocaleString("es-PE",
                    { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + " K";
    return "S/ " + Math.round(n).toLocaleString("es-PE");
  };

  // ── KPI cards ────────────────────────────────────────────────
  const kpiContainer = $("b7kpis");
  if (kpiContainer) {
    kpiContainer.innerHTML = años.map((a, i) => {
      const v      = totales[i];
      const es2026 = a === 2026;
      const prev   = i > 0 ? totales[i - 1] : null;
      let deltaHtml = "";
      if (prev && prev > 0 && v > 0) {
        const pct   = (v - prev) / prev * 100;
        const color = pct >= 0 ? "#2a7d46" : "#c0392b";
        const signo = pct >= 0 ? "▲" : "▼";
        deltaHtml = `<span style="font-size:10px;color:${color};font-weight:700">${signo} ${Math.abs(pct).toFixed(1)}%</span>`;
      }
      return `<div style="background:${es2026 ? "#fef3c7" : "#f9fafb"};border:1px solid ${es2026 ? "#fbbf24" : "#e5e7eb"};
               border-radius:10px;padding:10px 16px;min-width:110px;flex:1;text-align:center">
        <div style="font-family:'Barlow Condensed';font-size:13px;font-weight:700;color:#6b7280;margin-bottom:3px">
          Ene–Jul ${a}${es2026 ? " ★" : ""}
        </div>
        <div style="font-family:'Barlow Condensed';font-size:17px;font-weight:800;color:${es2026 ? "#92400e" : "#1f2937"}">
          ${v ? fmtM(v) : "Cargando…"}
        </div>
        <div style="margin-top:3px">${deltaHtml}</div>
      </div>`;
    }).join("");
  }

  // ── Gráfico de barras agrupadas por mes ───────────────────────
  const canvas = $("b7chart");
  if (!canvas) return;
  if (b7ChartInstance) { b7ChartInstance.destroy(); b7ChartInstance = null; }

  // Colores por año: escala de rojos para históricos, dorado para 2026
  const paleta = {
    2022: { bg: "rgba(154,24,32,0.45)", border: "#9a1820" },
    2023: { bg: "rgba(154,24,32,0.60)", border: "#9a1820" },
    2024: { bg: "rgba(154,24,32,0.78)", border: "#7a1219" },
    2025: { bg: "rgba(122,18,25,1.00)", border: "#5a0e12" },
    2026: { bg: "#FFC526",              border: "#d9a000"  },
  };

  const datasets = años.map((a, i) => {
    const es2026  = a === 2026;
    const meses   = es2026 ? [] : B7_HIST[String(a)].meses; // 2026 = 1 barra total
    const col     = paleta[a] || paleta[2025];
    if (es2026) {
      // 2026: una sola barra en el primer mes visible (Acumulado Ene-Jul)
      return {
        label: `${a} ★ (acum.)`,
        data: [rec2026, null, null, null, null, null, null],
        backgroundColor: col.bg,
        borderColor: col.border,
        borderWidth: 2,
        borderRadius: 5,
        borderSkipped: false,
      };
    }
    return {
      label: String(a),
      data: meses,
      backgroundColor: col.bg,
      borderColor: col.border,
      borderWidth: 1.5,
      borderRadius: 4,
      borderSkipped: false,
    };
  });

  b7ChartInstance = new Chart(canvas, {
    type: "bar",
    data: {
      labels: B7_MESES,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            font: { family: "'Barlow Condensed'", size: 12, weight: "700" },
            color: "#374151",
            boxWidth: 14,
            padding: 16,
          }
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: S/ ${Math.round(ctx.raw || 0).toLocaleString("es-PE")}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: "'Barlow Condensed'", weight: "700", size: 12 },
            color: "#374151"
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            callback: v => {
              if (v >= 1e6) return "S/ " + (v / 1e6).toFixed(1) + " M";
              if (v >= 1e3) return "S/ " + (v / 1e3).toFixed(0) + " K";
              return "S/ " + v;
            },
            font: { family: "'Barlow'", size: 11 },
            color: "#6b7280"
          },
          grid: { color: "#f3f4f6" }
        }
      },
      animation: { duration: 600 }
    }
  });
}

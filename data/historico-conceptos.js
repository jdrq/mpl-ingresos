// historico-conceptos.js
// Renderizador genérico de bloques históricos por concepto.
// Se usa en historico-rubro08.html e historico-rubro09.html.
// Config esperada en window.HIST_CONFIG:
//   { jsonPath: "data/historico_conceptos_rubro08.json",
//     numeroBase: 1,          // numeración de bloques (01, 02, ...)
//     fuenteTexto: "..." }

// Números completos, sin abreviar a K/M — a pedido del jefe.
const fmtM = n => {
  if (n === null || n === undefined) return "S/ —";
  return "S/ " + Math.round(n).toLocaleString("es-PE");
};

function crearBloqueHTML(numero, key, concepto) {
  const num = String(numero).padStart(2, "0");
  return `
  <div class="bloque" id="bloque-${key}">
    <div class="bloque-header">
      <div class="bloque-num">${num}</div>
      <div class="bloque-titulo">${concepto.label.toUpperCase()}</div>
    </div>
    <div class="bloque-subtitle">
      <span class="bloque-subtitle-text">Serie histórica Ene–Ago</span>
      <span class="bloque-subtitle-date">${window.HIST_RANGO || "2021–2025"}</span>
    </div>
    <div class="bloque-body">
      <div style="position:relative;height:300px;background:#fff;border-radius:10px;padding:8px 0 0 0">
        <canvas id="chart-${key}"></canvas>
      </div>
    </div>
    <div class="bloque-footer">
      <span>Fuente: Consulta Amigable MEF — Ingresos (corte anual, actualización manual)</span>
      <span class="foot-label">MPL · SERIE ${window.HIST_RANGO || "2021–2025"}</span>
    </div>
  </div>`;
}

function pintarChart(key, concepto) {
  // Años dinámicos: toma todas las claves de 4 dígitos presentes en el JSON
  // (así 2026, o cualquier año futuro que agregues, aparece solo sin tocar código).
  const años = Object.keys(concepto).filter(k => /^\d{4}$/.test(k)).sort();
  const valores = años.map(a => concepto[a] ?? null);
  const IDX_ACTUAL = años.length - 1; // último año = destacado en dorado

  const canvas = document.getElementById("chart-" + key);
  if (!canvas) return;

  const maxVal = Math.max(0, ...valores.filter(v => v !== null));
  // Headroom del 22% arriba de la barra más alta para que la etiqueta nunca se corte
  const yMax = maxVal > 0 ? maxVal * 1.22 : 10;

  const colores       = años.map((a, i) => i === IDX_ACTUAL ? "#FFC526" : "#9a1820");
  const borderColores = años.map((a, i) => i === IDX_ACTUAL ? "#d9a000" : "#7a1219");

  new Chart(canvas, {
    type: "bar",
    data: {
      labels: años.map((a, i) => `Ene–Ago ${a}${i === IDX_ACTUAL ? " ★" : ""}`),
      datasets: [{
        label: concepto.label,
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
      layout: { padding: { top: 26 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ctx.raw === null ? " Sin dato" : ` S/ ${Math.round(ctx.raw).toLocaleString("es-PE")}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            font: { family: "'Barlow Condensed'", weight: "700", size: 12 },
            color: ctx => ctx.index === IDX_ACTUAL ? "#92400e" : "#374151"
          }
        },
        y: {
          beginAtZero: true,
          suggestedMax: yMax,
          ticks: {
            callback: v => "S/ " + Math.round(v).toLocaleString("es-PE"),
            font: { family: "'Barlow'", size: 10.5 }, color: "#6b7280"
          },
          grid: { color: "#f3f4f6" }
        }
      },
      animation: { duration: 500 }
    },
    plugins: [{
      id: "labelsPlugin",
      afterDatasetsDraw(chart) {
        const { ctx, data } = chart;
        ctx.save();
        data.datasets[0].data.forEach((value, i) => {
          if (value === null) return;
          const meta = chart.getDatasetMeta(0);
          const bar  = meta.data[i];
          ctx.fillStyle    = i === IDX_ACTUAL ? "#92400e" : "#7a1219";
          ctx.font         = "700 12px 'Barlow Condensed'";
          ctx.textAlign    = "center";
          ctx.textBaseline = "bottom";
          ctx.fillText(fmtM(value), bar.x, bar.y - 8);
        });
        ctx.restore();
      }
    }]
  });
}

async function initHistoricoConceptos() {
  const cfg = window.HIST_CONFIG;
  const cont = document.getElementById("bloquesContainer");
  try {
    const r = await fetch(cfg.jsonPath + "?" + Date.now());
    const data = await r.json();
    const keys = Object.keys(data);

    // Rango de años dinámico para el subtítulo (toma la primera clave como referencia)
    const añosMuestra = Object.keys(data[keys[0]]).filter(k => /^\d{4}$/.test(k)).sort();
    window.HIST_RANGO = añosMuestra.length ? `${añosMuestra[0]}–${añosMuestra[añosMuestra.length - 1]}` : "";

    cont.innerHTML = keys.map((k, i) => crearBloqueHTML(i + 1, k, data[k])).join("");
    keys.forEach(k => pintarChart(k, data[k]));
  } catch (e) {
    cont.innerHTML = `<div class="bloque"><div class="bloque-body vacio">
      No se pudo cargar ${cfg.jsonPath}. Verifica la ruta del archivo.
    </div></div>`;
    console.error("[MPL] Error cargando histórico de conceptos:", e);
  }
}

document.addEventListener("DOMContentLoaded", initHistoricoConceptos);

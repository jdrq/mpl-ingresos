// historico-conceptos.js
// Renderizador genérico de bloques históricos por concepto.
// Se usa en historico-rubro08.html e historico-rubro09.html.
// Config esperada en window.HIST_CONFIG:
//   { jsonPath: "data/historico_conceptos_rubro08.json",
//     numeroBase: 1,          // numeración de bloques (01, 02, ...)
//     fuenteTexto: "..." }

const fmtM = n => {
  if (n === null || n === undefined) return "S/ —";
  if (Math.abs(n) >= 1e6) return "S/ " + (n / 1e6).toLocaleString("es-PE",
                  { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " M";
  if (Math.abs(n) >= 1e3) return "S/ " + (n / 1e3).toLocaleString("es-PE",
                  { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + " K";
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
      <span class="bloque-subtitle-date">2021–2025</span>
    </div>
    <div class="bloque-body">
      <div style="position:relative;height:300px;background:#fff;border-radius:10px;padding:8px 0 0 0">
        <canvas id="chart-${key}"></canvas>
      </div>
    </div>
    <div class="bloque-footer">
      <span>Fuente: Consulta Amigable MEF — Ingresos (corte anual, actualización manual)</span>
      <span class="foot-label">MPL · SERIE 2021–2025</span>
    </div>
  </div>`;
}

function pintarChart(key, concepto) {
  const años = ["2021", "2022", "2023", "2024", "2025"];
  const valores = años.map(a => concepto[a] ?? null);

  const canvas = document.getElementById("chart-" + key);
  if (!canvas) return;

  new Chart(canvas, {
    type: "bar",
    data: {
      labels: años.map(a => `Ene–Ago ${a}`),
      datasets: [{
        label: concepto.label,
        data: valores,
        backgroundColor: "#9a1820",
        borderColor: "#7a1219",
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
            label: ctx => ctx.raw === null ? " Sin dato" : ` S/ ${Math.round(ctx.raw).toLocaleString("es-PE")}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: "'Barlow Condensed'", weight: "700", size: 12 }, color: "#374151" }
        },
        y: {
          beginAtZero: true,
          ticks: {
            callback: v => {
              if (v >= 1e6) return "S/ " + (v / 1e6).toFixed(1) + " M";
              if (v >= 1e3) return "S/ " + (v / 1e3).toFixed(0) + " K";
              return "S/ " + v;
            },
            font: { family: "'Barlow'", size: 11 }, color: "#6b7280"
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
          const bar = meta.data[i];
          ctx.fillStyle = "#7a1219";
          ctx.font = "700 12px 'Barlow Condensed'";
          ctx.textAlign = "center";
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

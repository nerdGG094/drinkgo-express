/* =============================================================
   DASHBOARD — Chart.js (visual moderno)
============================================================= */

/* ---------- Paleta alinhada ao tema ---------- */
const PALETTE = [
  { strong: "#ef4444", soft: "rgba(239, 68, 68, 0.85)",  faint: "rgba(239, 68, 68, 0.10)"  }, // brand
  { strong: "#f59e0b", soft: "rgba(245, 158, 11, 0.85)", faint: "rgba(245, 158, 11, 0.10)" }, // accent
  { strong: "#3b82f6", soft: "rgba(59, 130, 246, 0.85)", faint: "rgba(59, 130, 246, 0.10)" }, // info
  { strong: "#22c55e", soft: "rgba(34, 197, 94, 0.85)",  faint: "rgba(34, 197, 94, 0.10)"  }, // success
  { strong: "#a855f7", soft: "rgba(168, 85, 247, 0.85)", faint: "rgba(168, 85, 247, 0.10)" }, // violet
  { strong: "#06b6d4", soft: "rgba(6, 182, 212, 0.85)",  faint: "rgba(6, 182, 212, 0.10)"  }, // cyan
  { strong: "#ec4899", soft: "rgba(236, 72, 153, 0.85)", faint: "rgba(236, 72, 153, 0.10)" }, // pink
];

const TEXT       = "#e2e8f0";
const TEXT_MUTED = "#94a3b8";
const SURFACE    = "#121a2e";
const GRID       = "rgba(148, 163, 184, 0.08)";

/* ---------- Defaults globais Chart.js ---------- */
if (typeof Chart !== "undefined") {
  Chart.defaults.font.family    = "'Inter', system-ui, -apple-system, sans-serif";
  Chart.defaults.font.size      = 11.5;
  Chart.defaults.color          = TEXT_MUTED;
  Chart.defaults.borderColor    = GRID;
  Chart.defaults.animation.duration = 700;
  Chart.defaults.animation.easing   = "easeOutQuart";
}

/* ---------- Helpers ---------- */
function pickColor(i)        { return PALETTE[i % PALETTE.length]; }
function multiColors(n, k)   { return Array.from({ length: n }, (_, i) => pickColor(i)[k]); }

/* gradient vertical (para barras verticais) */
function makeVerticalGradient(ctx, area, hex) {
  if (!area) return hex;
  const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = parseInt(m[1], 16), gg = parseInt(m[2], 16), b = parseInt(m[3], 16);
  g.addColorStop(0,   `rgba(${r}, ${gg}, ${b}, 0.95)`);
  g.addColorStop(0.5, `rgba(${r}, ${gg}, ${b}, 0.65)`);
  g.addColorStop(1,   `rgba(${r}, ${gg}, ${b}, 0.25)`);
  return g;
}

/* gradient horizontal (para barras horizontais) */
function makeHorizontalGradient(ctx, area, hex) {
  if (!area) return hex;
  const g = ctx.createLinearGradient(area.left, 0, area.right, 0);
  const m = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!m) return hex;
  const r = parseInt(m[1], 16), gg = parseInt(m[2], 16), b = parseInt(m[3], 16);
  g.addColorStop(0, `rgba(${r}, ${gg}, ${b}, 0.45)`);
  g.addColorStop(1, `rgba(${r}, ${gg}, ${b}, 0.95)`);
  return g;
}

/* ---------- Tooltip moderno ---------- */
const tooltipModern = {
  enabled: true,
  backgroundColor: "rgba(15, 23, 42, 0.96)",
  titleColor: TEXT,
  bodyColor: TEXT,
  borderColor: "rgba(148, 163, 184, 0.18)",
  borderWidth: 1,
  padding: 12,
  cornerRadius: 10,
  displayColors: true,
  boxPadding: 6,
  usePointStyle: true,
  titleFont: { family: "'Inter', sans-serif", size: 12, weight: "700" },
  bodyFont:  { family: "'Inter', sans-serif", size: 12, weight: "500" },
  caretSize: 6,
  caretPadding: 8,
};

/* ---------- Plugin: rótulo central no donut ---------- */
const centerLabelPlugin = {
  id: "centerLabel",
  afterDraw(chart, _args, opts) {
    if (!opts || !opts.show) return;
    const { ctx, chartArea } = chart;
    if (!chartArea) return;
    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;

    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font = "800 26px 'Inter', sans-serif";
    ctx.fillStyle = TEXT;
    ctx.fillText(opts.value || "", cx, cy - 8);

    ctx.font = "700 10px 'Inter', sans-serif";
    ctx.fillStyle = TEXT_MUTED;
    ctx.fillText((opts.label || "").toUpperCase(), cx, cy + 14);
    ctx.restore();
  },
};

/* ---------- Eixos / grid base ---------- */
function axisX(showGrid = false) {
  return {
    ticks: { color: TEXT_MUTED, font: { size: 11 }, padding: 6 },
    grid:  { display: showGrid, color: GRID, drawBorder: false },
    border:{ display: false },
  };
}

function axisY(showGrid = true) {
  return {
    beginAtZero: true,
    ticks: { color: TEXT_MUTED, font: { size: 11 }, padding: 8, precision: 0 },
    grid:  { display: showGrid, color: GRID, drawBorder: false, drawTicks: false },
    border:{ display: false },
  };
}

/* =============================================================
   BOOT
============================================================= */
document.addEventListener("DOMContentLoaded", () => {
  const d = window.dashboardData;
  if (!d || typeof Chart === "undefined") return;

  /* ---------- 1) Bar vertical: Finalizadores ---------- */
  const ctx1 = document.getElementById("finalizadores");
  if (ctx1) {
    new Chart(ctx1, {
      type: "bar",
      data: {
        labels: d.usuarios,
        datasets: [{
          label: "Mesas finalizadas",
          data: d.total_mesas,
          backgroundColor: (c) => makeVerticalGradient(c.chart.ctx, c.chart.chartArea, "#ef4444"),
          hoverBackgroundColor: (c) => makeVerticalGradient(c.chart.ctx, c.chart.chartArea, "#f87171"),
          borderRadius: 8,
          borderSkipped: false,
          barThickness: "flex",
          maxBarThickness: 48,
          categoryPercentage: 0.7,
          barPercentage: 0.85,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: tooltipModern,
        },
        scales: {
          x: axisX(false),
          y: axisY(true),
        },
      },
    });
  }

  /* ---------- 2) Donut: Participação ---------- */
  const ctx2 = document.getElementById("donutMesas");
  if (ctx2) {
    const totalDonut = (d.total_mesas || []).reduce((a, b) => a + Number(b || 0), 0);
    new Chart(ctx2, {
      type: "doughnut",
      data: {
        labels: d.usuarios,
        datasets: [{
          data: d.porcentagens,
          backgroundColor: multiColors(d.usuarios.length, "soft"),
          hoverBackgroundColor: multiColors(d.usuarios.length, "strong"),
          borderColor: SURFACE,
          borderWidth: 3,
          hoverOffset: 8,
          spacing: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        layout: { padding: 8 },
        plugins: {
          legend: {
            position: "right",
            labels: {
              color: TEXT,
              usePointStyle: true,
              pointStyle: "circle",
              padding: 14,
              boxWidth: 8,
              boxHeight: 8,
              font: { size: 11.5, weight: "600" },
            },
          },
          tooltip: {
            ...tooltipModern,
            callbacks: {
              label: (c) => ` ${c.label}: ${c.parsed}%`,
            },
          },
          centerLabel: { show: true, value: String(totalDonut), label: "Mesas" },
        },
      },
      plugins: [centerLabelPlugin],
    });
  }

  /* ---------- 3) Line: Saída diária ---------- */
  const ctx3 = document.getElementById("saidaDiaria");
  if (ctx3) {
    new Chart(ctx3, {
      type: "line",
      data: {
        labels: d.dias,
        datasets: [{
          label: "Produtos por dia",
          data: d.qtd_dia,
          borderColor: "#ef4444",
          backgroundColor: (c) => {
            const { ctx, chartArea } = c.chart;
            if (!chartArea) return "rgba(239,68,68,0.20)";
            const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
            g.addColorStop(0, "rgba(239, 68, 68, 0.45)");
            g.addColorStop(1, "rgba(239, 68, 68, 0)");
            return g;
          },
          tension: 0.4,
          borderWidth: 2.5,
          fill: true,
          pointRadius: 0,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: "#ef4444",
          pointHoverBorderColor: "#fff",
          pointHoverBorderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { display: false },
          tooltip: tooltipModern,
        },
        scales: {
          x: axisX(false),
          y: axisY(true),
        },
      },
    });
  }

  /* ---------- 4) Bar horizontal: Mais vendidos ---------- */
  const ctx4 = document.getElementById("maisVendidos");
  if (ctx4) {
    const n = (d.prod_nomes || []).length;
    new Chart(ctx4, {
      type: "bar",
      data: {
        labels: d.prod_nomes,
        datasets: [{
          label: "Quantidade vendida",
          data: d.prod_qtd,
          backgroundColor: (c) => {
            const idx = c.dataIndex ?? 0;
            const hex = pickColor(idx).strong;
            return makeHorizontalGradient(c.chart.ctx, c.chart.chartArea, hex);
          },
          hoverBackgroundColor: (c) => pickColor(c.dataIndex ?? 0).strong,
          borderRadius: 8,
          borderSkipped: false,
          barThickness: "flex",
          maxBarThickness: 28,
          categoryPercentage: 0.85,
          barPercentage: 0.9,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: tooltipModern,
        },
        scales: {
          x: axisY(true),
          y: {
            ...axisX(false),
            ticks: { ...axisX(false).ticks, autoSkip: false },
          },
        },
      },
    });
  }
});

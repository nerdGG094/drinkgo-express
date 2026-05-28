/* ============================================================
   RELATÓRIOS — chips de período rápido
============================================================ */
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("relFiltroForm");
  if (!form) return;

  const inIni = form.querySelector('input[name="data_ini"]');
  const inFim = form.querySelector('input[name="data_fim"]');
  const chips = document.querySelectorAll(".rel-quick-chips .rel-chip");
  if (!inIni || !inFim || !chips.length) return;

  const fmt = (d) => d.toISOString().slice(0, 10);

  function setRange(quick) {
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    let ini = new Date(hoje);
    let fim = new Date(hoje);

    if (quick === "hoje") {
      // ini == fim == hoje
    } else if (quick === "7") {
      ini.setDate(hoje.getDate() - 6);
    } else if (quick === "30") {
      ini.setDate(hoje.getDate() - 29);
    } else if (quick === "mes") {
      ini = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
      fim = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0);
    }

    inIni.value = fmt(ini);
    inFim.value = fmt(fim);
    form.submit();
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => setRange(chip.dataset.quick));
  });

  // marca o chip ativo se o range atual coincidir com algum atalho
  (function markActiveChip() {
    const ini = inIni.value;
    const fim = inFim.value;
    if (!ini || !fim) return;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tIso = fmt(today);

    const candidates = {
      hoje: () => ini === tIso && fim === tIso,
      "7":  () => {
        const d = new Date(today); d.setDate(today.getDate() - 6);
        return ini === fmt(d) && fim === tIso;
      },
      "30": () => {
        const d = new Date(today); d.setDate(today.getDate() - 29);
        return ini === fmt(d) && fim === tIso;
      },
      mes: () => {
        const a = new Date(today.getFullYear(), today.getMonth(), 1);
        const b = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        return ini === fmt(a) && fim === fmt(b);
      },
    };

    chips.forEach((chip) => {
      const ck = candidates[chip.dataset.quick];
      if (ck && ck()) chip.classList.add("active");
    });
  })();
});

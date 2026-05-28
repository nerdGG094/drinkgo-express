/* ===========================================================
   CHOPEIRAS — interações cliente
=========================================================== */

let chopeiraSelecionada = null;

/* ---------- Modal confirmação ---------- */
function abrirConfirmacao(id) {
  chopeiraSelecionada = id;
  const modal = document.getElementById("modal-confirm");
  if (modal) modal.classList.add("ativo");
}

function fecharModal() {
  const modal = document.getElementById("modal-confirm");
  if (modal) modal.classList.remove("ativo");
  chopeiraSelecionada = null;
}

function confirmarDevolucao() {
  if (!chopeiraSelecionada) return;
  const form = document.getElementById("form-retorno-" + chopeiraSelecionada);
  if (form) form.submit();
}

/* ESC fecha modal; clique fora também */
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") fecharModal();
});
document.addEventListener("click", (e) => {
  const modal = document.getElementById("modal-confirm");
  if (!modal || !modal.classList.contains("ativo")) return;
  if (e.target === modal) fecharModal();
});

/* ---------- Filtro de status (chips) ---------- */
document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector(".chopeiras-page");
  if (!page) return;

  const chips = page.querySelectorAll(".chip-filtro");
  const grupos = page.querySelectorAll(".chopeira-grupo");

  function aplicarFiltro(tipo) {
    page.dataset.filtro = tipo;

    chips.forEach(c => {
      c.classList.toggle("active", c.dataset.filtro === tipo);
    });

    // Em cada grupo, mostra/oculta a mensagem "vazio" caso nenhum card visível
    grupos.forEach(g => {
      const cards = g.querySelectorAll(".chopeira-card");
      const vazio = g.querySelector(".chopeira-grupo-vazio");

      let visiveis = 0;
      cards.forEach(card => {
        const status = card.dataset.status;
        const ok = (tipo === "todas") || (status === tipo);
        if (ok) visiveis++;
      });

      if (vazio) vazio.hidden = (visiveis !== 0 || cards.length === 0);
    });
  }

  chips.forEach(chip => {
    chip.addEventListener("click", () => aplicarFiltro(chip.dataset.filtro));
  });
});

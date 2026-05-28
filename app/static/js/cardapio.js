document.addEventListener("DOMContentLoaded", function () {

  // ---------- TOGGLE DE CATEGORIA ----------
  const botoes = document.querySelectorAll(".categoria-header");
  botoes.forEach(btn => {
    btn.addEventListener("click", () => {
      const box = btn.closest(".categoria-box");
      box.classList.toggle("open");
    });
  });

  // ---------- BUSCA / FILTRO ----------
  const input    = document.getElementById("cardapio_busca");
  const btnClear = document.getElementById("cardapio_busca_clear");
  const empty    = document.getElementById("cardapio_sem_resultado");
  const boxes    = document.querySelectorAll(".categoria-box");

  if (!input || !boxes.length) return;

  // remove acentos + lowercase
  function norm(s) {
    return (s || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  function aplicarFiltro(termo) {
    const partes = norm(termo).split(/\s+/).filter(Boolean);
    const filtrando = partes.length > 0;

    let totalVisivel = 0;

    boxes.forEach(box => {
      const nomeCat = norm(box.dataset.categoria || "");
      const cards   = box.querySelectorAll(".produto-card");

      // categoria casa se TODAS as palavras digitadas estão no nome dela
      const categoriaCasa = filtrando && partes.every(t => nomeCat.includes(t));

      let visiveisNaCat = 0;

      cards.forEach(card => {
        const nomeProd = norm(card.dataset.nome || "");
        // se a categoria toda casa, mostra todos os produtos dela
        // senão, produto casa se TODAS as palavras estão no nome
        const casa = !filtrando
          ? true
          : (categoriaCasa || partes.every(t => nomeProd.includes(t)));
        card.style.display = casa ? "" : "none";
        if (casa) visiveisNaCat++;
      });

      if (!filtrando) {
        // sem busca: mostra a caixa, deixa o usuário expandir como quiser
        box.style.display = "";
        // não mexe no estado open/closed
      } else if (visiveisNaCat > 0) {
        // tem item visível: mostra a caixa e abre pra ver os resultados
        box.style.display = "";
        box.classList.add("open");
        totalVisivel += visiveisNaCat;
      } else {
        // não casa nada nesta categoria: esconde
        box.style.display = "none";
      }
    });

    // estado vazio
    if (filtrando && totalVisivel === 0) {
      empty.hidden = false;
    } else {
      empty.hidden = true;
    }

    // botão de limpar visível só quando há texto
    btnClear.hidden = !filtrando;
  }

  // Debounce simples pra não filtrar a cada tecla
  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => aplicarFiltro(input.value), 80);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      input.value = "";
      aplicarFiltro("");
      input.blur();
    }
  });

  btnClear.addEventListener("click", () => {
    input.value = "";
    aplicarFiltro("");
    input.focus();
  });
});

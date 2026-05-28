// =====================================================================
// Adicionar produto ao pedido (caixa) — busca por digitação (autocomplete)
// =====================================================================

(function () {
  const inputBusca   = document.getElementById("produto_busca");
  const inputHidden  = document.getElementById("produto_select");
  const lista        = document.getElementById("produto_lista");
  const dataEl       = document.getElementById("produtos_json");

  if (!inputBusca || !lista || !dataEl) return;

  let produtos = [];
  try {
    produtos = JSON.parse(dataEl.textContent) || [];
  } catch (e) {
    console.warn("Falha ao ler lista de produtos", e);
  }

  // Normaliza: minúsculas + remove acentos (NFD + remove combining marks U+0300..U+036F)
  function norm(s) {
    return (s || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  // Cada termo digitado precisa estar presente no nome — busca tipo "fuzzy" simples.
  // "refri pet 250" → casa "Refrigerante PET 250ml", "Refri PET 250 zero", etc.
  function filtrar(termo) {
    const partes = norm(termo).split(/\s+/).filter(Boolean);
    if (!partes.length) return [];
    return produtos
      .filter(p => {
        const alvo = norm(p.nome);
        return partes.every(t => alvo.includes(t));
      })
      .slice(0, 30);
  }

  function fmtPreco(v) {
    return Number(v).toFixed(2).replace(".", ",");
  }

  let activeIdx = -1;

  function render(itens) {
    lista.innerHTML = "";
    activeIdx = -1;

    if (!itens.length) {
      lista.hidden = true;
      inputBusca.setAttribute("aria-expanded", "false");
      return;
    }

    itens.forEach((p, i) => {
      const li = document.createElement("li");
      li.className = "produto-busca-item";
      li.setAttribute("role", "option");
      li.dataset.id = p.id;
      li.dataset.nome = p.nome;
      li.dataset.idx = i;
      li.innerHTML =
        '<span class="produto-busca-nome">' + escapeHtml(p.nome) + '</span>' +
        '<span class="produto-busca-preco">R$ ' + fmtPreco(p.preco) + '</span>';
      lista.appendChild(li);
    });

    lista.hidden = false;
    inputBusca.setAttribute("aria-expanded", "true");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function selecionar(li) {
    if (!li) return;
    inputHidden.value = li.dataset.id;
    inputBusca.value = li.dataset.nome;
    lista.hidden = true;
    inputBusca.setAttribute("aria-expanded", "false");
  }

  function setActive(i) {
    const items = lista.querySelectorAll(".produto-busca-item");
    if (!items.length) return;
    if (i < 0) i = items.length - 1;
    if (i >= items.length) i = 0;
    activeIdx = i;
    items.forEach((el, idx) => {
      el.classList.toggle("is-active", idx === activeIdx);
      if (idx === activeIdx) el.scrollIntoView({ block: "nearest" });
    });
  }

  // ----- Eventos -----
  inputBusca.addEventListener("input", () => {
    inputHidden.value = ""; // qualquer digitação invalida a seleção anterior
    render(filtrar(inputBusca.value));
  });

  inputBusca.addEventListener("focus", () => {
    if (inputBusca.value.trim()) render(filtrar(inputBusca.value));
  });

  inputBusca.addEventListener("keydown", (e) => {
    const visible = !lista.hidden;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!visible) render(filtrar(inputBusca.value));
      setActive(activeIdx + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(activeIdx - 1);
    } else if (e.key === "Enter") {
      if (visible && activeIdx >= 0) {
        e.preventDefault();
        const items = lista.querySelectorAll(".produto-busca-item");
        selecionar(items[activeIdx]);
      }
    } else if (e.key === "Escape") {
      lista.hidden = true;
      inputBusca.setAttribute("aria-expanded", "false");
    }
  });

  lista.addEventListener("click", (e) => {
    const li = e.target.closest(".produto-busca-item");
    if (li) selecionar(li);
  });

  document.addEventListener("click", (e) => {
    if (!inputBusca.contains(e.target) && !lista.contains(e.target)) {
      lista.hidden = true;
      inputBusca.setAttribute("aria-expanded", "false");
    }
  });
})();

// =====================================================================
// Submissão: envia produto_id + qtd para o backend
// =====================================================================
function adicionarProduto(pedidoId, urlAdicionar) {
    const produtoId = document.getElementById("produto_select").value;
    const qtd = document.getElementById("produto_qtd").value;
    const inputBusca = document.getElementById("produto_busca");

    if (!produtoId) {
        alert("Digite e selecione um produto da lista.");
        if (inputBusca) inputBusca.focus();
        return;
    }

    fetch(urlAdicionar, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            produto_id: produtoId,
            quantidade: qtd
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || "Erro ao adicionar produto.");
        }
    })
    .catch(() => {
        alert("Erro de conexão com o servidor.");
    });
}

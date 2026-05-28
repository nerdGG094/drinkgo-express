let pedidoSelecionado = null;

// ===============================
// NORMALIZAÇÃO (aceita 201,60 | 201.60 | 1.201,60 | 1,201.60)
// ===============================
function normalizeToDot2(v) {
  if (v === null || v === undefined) return "";
  let s = String(v).trim();
  if (!s) return "";

  // mantém só dígitos e separadores
  s = s.replace(/[^\d.,]/g, "");

  const hasComma = s.includes(",");
  const hasDot = s.includes(".");

  // Se tem vírgula E ponto, o ÚLTIMO separador é o decimal
  if (hasComma && hasDot) {
    const lastComma = s.lastIndexOf(",");
    const lastDot = s.lastIndexOf(".");
    const decIsComma = lastComma > lastDot;

    if (decIsComma) {
      // "1.234,56" -> remove pontos (milhar) e troca vírgula por ponto
      s = s.replace(/\./g, "").replace(",", ".");
    } else {
      // "1,234.56" -> remove vírgulas (milhar), mantém ponto decimal
      s = s.replace(/,/g, "");
    }
  } else if (hasComma) {
    // "1234,56" -> "1234.56"
    s = s.replace(/\./g, "").replace(",", ".");
  } else {
    // só ponto ou só dígitos: "1234.56" ou "1234"
    // se tiver múltiplos pontos (usuário zoou), mantém só o primeiro como decimal
    const parts = s.split(".");
    if (parts.length > 2) s = parts[0] + "." + parts.slice(1).join("");
  }

  const n = Number(s);
  if (Number.isNaN(n)) return "";
  return n.toFixed(2);
}

// ===============================
// MODAL
// ===============================
function abrirConfirmacao(id) {
  pedidoSelecionado = id;
  document.getElementById("modal-confirm").classList.add("ativo");
}

function fecharModal() {
  document.getElementById("modal-confirm").classList.remove("ativo");
  pedidoSelecionado = null;
}

function confirmarFechamento() {
  fetch(`/admin/pedido/${pedidoSelecionado}/fechar`, { method: "POST" })
    .then(r => r.json())
    .then(resp => {
      if (!resp.success) {
        alert("⚠️ Defina a forma de pagamento antes de fechar!");
        return;
      }
      location.reload();
    });

  fecharModal();
}

// ===============================
// FORMA 1
// ===============================
function togglePagamento(pedidoId, forma) {
  const dinheiroInput = document.getElementById(`dinheiro-input-${pedidoId}`);
  const tipoCartao = document.getElementById(`tipo-cartao-${pedidoId}`);

  if (!dinheiroInput) return;

  dinheiroInput.style.display = "none";
  if (tipoCartao) tipoCartao.style.display = "none";

  if (forma === "dinheiro") {
    dinheiroInput.style.display = "block";
  }

  if (forma === "cartao" && tipoCartao) {
    tipoCartao.style.display = "block";
  }
}

// ===============================
// FORMA 2
// ===============================
function togglePagamento2(pedidoId) {
  const select = document.querySelector(`#pedido-${pedidoId} select[name="forma_pagamento2"]`);
  const valorInput = document.getElementById(`valor-pagamento2-${pedidoId}`);

  if (!select || !valorInput) return;

  const forma = select.value;

  if (forma === "dinheiro" || forma === "pix" || forma === "cartao") {
    valorInput.style.display = "block";
  } else {
    valorInput.style.display = "none";
    valorInput.value = "";
  }
}

// ===============================
// AO CARREGAR PÁGINA
// ===============================
document.addEventListener("DOMContentLoaded", () => {
  // ativa exibição correta ao carregar
  document.querySelectorAll('select[name="forma_pagamento"]').forEach(select => {
    const pedidoId = select.closest(".pedido-card").id.split("-")[1];
    togglePagamento(pedidoId, select.value);
  });

  document.querySelectorAll('select[name="forma_pagamento2"]').forEach(select => {
    const pedidoId = select.closest(".pedido-card").id.split("-")[1];
    togglePagamento2(pedidoId);
  });

  // ✅ Antes de enviar pro Flask, normaliza para 1234.56
  document.querySelectorAll(".form-pagamento").forEach(form => {
    form.addEventListener("submit", () => {
      const v1 = form.querySelector('input[name="valor_entregue"]');
      const v2 = form.querySelector('input[name="valor_pagamento2"]');
      const desc = form.querySelector('input[name="desconto"]');

      if (v1 && v1.value) v1.value = normalizeToDot2(v1.value);
      if (v2 && v2.value) v2.value = normalizeToDot2(v2.value);
      if (desc && desc.value) desc.value = normalizeToDot2(desc.value);
    });
  });
});
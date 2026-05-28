function toggleSenha() {
  const campo = document.getElementById("senha");
  const btn = document.querySelector(".btn-olho");

  if (campo.type === "password") {
    campo.type = "text";
    btn.textContent = "🙈";
  } else {
    campo.type = "password";
    btn.textContent = "👁️";
  }
}

function iniciarLogin(form) {
  const btn = document.getElementById("btnLogin");
  const email = document.getElementById("email");

  // força uppercase no email antes de enviar
  if (email) {
    email.value = email.value.toUpperCase();
  }

  btn.disabled = true;
  btn.innerHTML = "ENTRANDO...";

  return true;
}

// Converte para uppercase enquanto digita
document.addEventListener("DOMContentLoaded", () => {
  const email = document.getElementById("email");

  if (email) {
    email.addEventListener("input", () => {
      email.value = email.value.toUpperCase();
    });
  }
});

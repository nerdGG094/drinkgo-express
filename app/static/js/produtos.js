function toggleGrupo(id) {
    const conteudo = document.getElementById(id);
    const container = conteudo.closest(".grupo-container");

    container.classList.toggle("aberto");
}
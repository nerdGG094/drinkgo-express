    const btnMenu = document.getElementById("btnMenu");
    const sidebar = document.getElementById("sidebarMenu");

    if (btnMenu && sidebar) {
      btnMenu.addEventListener("click", () => {
        sidebar.classList.toggle("open");
        document.body.classList.toggle("menu-open");
      });
    }
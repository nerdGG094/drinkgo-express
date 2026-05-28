"""
Launcher do Comanda Digital — substitui o run.py no build PyInstaller.

Comportamento:
  - Sobe o Flask + Socket.IO em uma thread daemon (sem janela de terminal).
  - Abre uma janela compacta exibindo:
      * IP local da máquina + porta (endereço para os tablets)
      * QR Code do endereço (escanear no tablet)
      * Botões "Copiar endereço" e "Abrir no navegador"
  - Fechar a janela encerra o servidor.

Para uso em DEV continua valendo o run.py (com auto-reload).
"""

import os
import sys
import socket
import subprocess
import threading
import webbrowser
import tkinter as tk

# ---------- Config ----------
PORT = 5020
TITULO_JANELA = "Comanda Digital — Servidor"

# Auto-update via git pull a cada abertura. Setar COMANDA_NO_AUTOUPDATE=1 desativa.
AUTO_UPDATE_DISABLE_ENV = "COMANDA_NO_AUTOUPDATE"
UPDATE_FETCH_TIMEOUT = 15
UPDATE_PULL_TIMEOUT = 45

# Paleta (espelha a do app)
BG_DARK     = "#0b1020"
BG_CARD     = "#121a2e"
BORDA       = "#1f2a47"
TEXT        = "#e2e8f0"
TEXT_MUTED  = "#94a3b8"
BRAND       = "#ef4444"
BRAND_HOVER = "#dc2626"
SUCCESS     = "#22c55e"


# ---------- Helpers ----------
def get_local_ip() -> str:
    """Detecta o IP local da máquina na LAN (sem precisar conectar)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.6)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_hostname() -> str:
    """Nome NetBIOS / hostname da máquina (resolvível na LAN do Windows)."""
    try:
        return socket.gethostname() or ""
    except Exception:
        return ""


# Nome mDNS registrado (funciona em iOS, Android, Windows 10+, Mac)
MDNS_NOME = "comanda"   # vira "comanda.local"


def registrar_mdns(porta: int, ip: str):
    """
    Registra `comanda.local` via mDNS/Zeroconf — assim qualquer tablet/celular
    da rede acessa http://comanda.local:porta sem precisar saber o IP.

    Retorna a tupla (zc, info) para que o caller possa fazer unregister no fim,
    ou (None, None) se a lib nao estiver disponivel ou der erro.
    """
    try:
        from zeroconf import Zeroconf, ServiceInfo
    except Exception:
        return None, None

    try:
        zc = Zeroconf()
        info = ServiceInfo(
            type_="_http._tcp.local.",
            name=f"{MDNS_NOME}._http._tcp.local.",
            server=f"{MDNS_NOME}.local.",
            addresses=[socket.inet_aton(ip)],
            port=porta,
            properties={"app": "comanda-digital"},
        )
        zc.register_service(info)
        return zc, info
    except Exception:
        return None, None


def app_path() -> str:
    """Diretório raiz do app (compatível com PyInstaller frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))


# ---------- Auto-update (git pull) ----------
def _run_git(args, cwd, timeout):
    """Executa git silencioso no Windows (sem flash de console)."""
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=creationflags,
    )


def verificar_atualizacoes():
    """
    Verifica o repositório remoto (GitHub) e, se houver commits novos, baixa.
    Retorna (atualizou: bool, mensagem: str). Falhas silenciosas — nunca bloqueia.
    """
    if os.environ.get(AUTO_UPDATE_DISABLE_ENV) == "1":
        return False, "auto-update desativado"
    if getattr(sys, "frozen", False):
        return False, "build empacotado (sem auto-update)"

    base = app_path()
    if not os.path.isdir(os.path.join(base, ".git")):
        return False, "sem repositório git"

    try:
        _run_git(["--version"], base, 5)
    except Exception:
        return False, "git não instalado"

    try:
        r = _run_git(["fetch", "--quiet"], base, UPDATE_FETCH_TIMEOUT)
        if r.returncode != 0:
            return False, "fetch falhou"
    except subprocess.TimeoutExpired:
        return False, "timeout no fetch"
    except Exception:
        return False, "erro no fetch"

    try:
        local = _run_git(["rev-parse", "@"], base, 5).stdout.strip()
        remote = _run_git(["rev-parse", "@{u}"], base, 5).stdout.strip()
    except Exception:
        return False, "sem upstream configurado"

    if not local or not remote or local == remote:
        return False, "já está atualizado"

    try:
        r = _run_git(["pull", "--ff-only", "--quiet"], base, UPDATE_PULL_TIMEOUT)
        if r.returncode != 0:
            return False, "pull falhou (conflitos locais?)"
    except Exception:
        return False, "erro no pull"

    return True, "nova versão baixada"


def reiniciar_processo():
    """Relança o launcher com o código atualizado e encerra o processo atual."""
    try:
        subprocess.Popen([sys.executable, *sys.argv], close_fds=True)
    finally:
        os._exit(0)


def start_server():
    """Sobe o Flask em thread daemon (não bloqueia a UI)."""
    from app import create_app
    from app.sockets import socketio
    app = create_app()
    socketio.run(
        app,
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )


# ---------- GUI ----------
def main():
    # Verifica atualizações antes de subir o servidor. Se baixou nova versão,
    # relança o processo para que o código atualizado seja carregado.
    atualizou, _ = verificar_atualizacoes()
    if atualizou:
        reiniciar_processo()
        return

    threading.Thread(target=start_server, daemon=True).start()

    ip = get_local_ip()
    host = get_hostname()
    url       = f"http://{ip}:{PORT}"
    url_host  = f"http://{host}:{PORT}" if host else None
    url_local = f"http://127.0.0.1:{PORT}"

    # Registra mDNS — habilita acesso por http://comanda.local:5020
    # em qualquer dispositivo (iOS, Android, Windows 10+, Mac)
    zc, zc_info = registrar_mdns(PORT, ip)
    url_mdns = f"http://{MDNS_NOME}.local:{PORT}" if zc else None

    root = tk.Tk()
    root.title(TITULO_JANELA)
    root.configure(bg=BG_DARK)
    root.geometry("440x620")
    root.resizable(False, False)

    # Ícone (pega do app/static se existir)
    try:
        ico = os.path.join(app_path(), "app", "static", "imagens", "favicon.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)
    except Exception:
        pass

    # ---- Cabeçalho ----
    header = tk.Frame(root, bg=BG_DARK)
    header.pack(pady=(22, 0))
    tk.Label(header, text="CHOPP PALAZZO", bg=BG_DARK, fg=TEXT,
             font=("Segoe UI", 9, "bold")).pack()
    tk.Label(header, text="EXPRESS", bg=BG_DARK, fg=BRAND,
             font=("Segoe UI", 16, "bold")).pack()

    # ---- Status ----
    status = tk.Frame(root, bg=BG_DARK)
    status.pack(pady=(10, 0))
    dot = tk.Canvas(status, width=14, height=14, bg=BG_DARK, highlightthickness=0)
    dot.create_oval(2, 2, 12, 12, fill=SUCCESS, outline="")
    dot.pack(side=tk.LEFT, padx=(0, 6))
    tk.Label(status, text="Servidor rodando", bg=BG_DARK, fg=SUCCESS,
             font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    # ---- Card dos endereços (IP + hostname) ----
    card = tk.Frame(root, bg=BG_CARD,
                    highlightbackground=BORDA, highlightthickness=1,
                    padx=18, pady=14)
    card.pack(pady=14, padx=24, fill="x")

    tk.Label(card, text="ENDEREÇOS PARA OS TABLETS",
             bg=BG_CARD, fg=TEXT_MUTED,
             font=("Segoe UI", 8, "bold")).pack(anchor="w")

    # Linha 1: mDNS (.local) — primário, funciona em iOS/Android/Win/Mac
    if url_mdns:
        linha_mdns = tk.Frame(card, bg=BG_CARD)
        linha_mdns.pack(anchor="w", pady=(6, 0), fill="x")
        tk.Label(linha_mdns, text="★", bg=BG_CARD, fg=SUCCESS,
                 font=("Segoe UI", 10, "bold"), width=2, anchor="w").pack(side=tk.LEFT)
        tk.Label(linha_mdns, text=url_mdns, bg=BG_CARD, fg=TEXT,
                 font=("Consolas", 13, "bold")).pack(side=tk.LEFT, padx=(4, 0))

    # Linha 2: IP — fallback robusto sempre disponível
    linha_ip = tk.Frame(card, bg=BG_CARD)
    linha_ip.pack(anchor="w", pady=(4, 0), fill="x")
    tk.Label(linha_ip, text="IP", bg=BG_CARD, fg=BRAND,
             font=("Segoe UI", 8, "bold"), width=2, anchor="w").pack(side=tk.LEFT)
    tk.Label(linha_ip, text=url, bg=BG_CARD, fg=TEXT,
             font=("Consolas", 13, "bold")).pack(side=tk.LEFT, padx=(4, 0))

    # Linha 3: Hostname Windows (NetBIOS) — só pra outros PCs Windows
    if url_host:
        linha_host = tk.Frame(card, bg=BG_CARD)
        linha_host.pack(anchor="w", pady=(4, 0), fill="x")
        tk.Label(linha_host, text="W", bg=BG_CARD, fg="#fcd34d",
                 font=("Segoe UI", 8, "bold"), width=2, anchor="w").pack(side=tk.LEFT)
        tk.Label(linha_host, text=url_host, bg=BG_CARD, fg=TEXT,
                 font=("Consolas", 13, "bold")).pack(side=tk.LEFT, padx=(4, 0))

    # Aviso explicativo
    aviso = "★ recomendado (iOS/Android/Win)   |   IP sempre funciona"
    if url_host:
        aviso += "   |   W só PCs Windows"
    tk.Label(card, text=aviso,
             bg=BG_CARD, fg=TEXT_MUTED,
             font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(6, 0))

    # ---- QR Code (aponta pro IP — funciona sempre, inclusive sem mDNS) ----
    qr_frame = tk.Frame(root, bg=BG_DARK)
    qr_frame.pack(pady=12)
    try:
        import qrcode
        from PIL import ImageTk
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_tk = ImageTk.PhotoImage(qr_img)
        qr_label = tk.Label(qr_frame, image=qr_tk, bg="white", padx=8, pady=8)
        qr_label.image = qr_tk
        qr_label.pack()
        tk.Label(root, text="Escaneie no tablet para acessar (via IP)",
                 bg=BG_DARK, fg=TEXT_MUTED, font=("Segoe UI", 9)).pack()
    except Exception as e:
        tk.Label(qr_frame, text=f"(QR Code indisponível: {e})",
                 bg=BG_DARK, fg=TEXT_MUTED, font=("Segoe UI", 9)).pack()

    # ---- Botões ----
    btns = tk.Frame(root, bg=BG_DARK)
    btns.pack(pady=14)

    def _copiar_str(s, botao, label_default):
        root.clipboard_clear()
        root.clipboard_append(s)
        botao.config(text="✓ Copiado!", fg=SUCCESS)
        root.after(1600, lambda: botao.config(text=label_default, fg=TEXT))

    def copiar_mdns():
        _copiar_str(url_mdns, btn_copiar_mdns, "Copiar .local")

    def copiar_ip():
        _copiar_str(url, btn_copiar, "Copiar IP")

    def abrir():
        webbrowser.open(url_local)

    if url_mdns:
        btn_copiar_mdns = tk.Button(
            btns, text="Copiar .local", command=copiar_mdns,
            bg=BG_CARD, fg=TEXT,
            activebackground=BORDA, activeforeground=TEXT,
            relief="flat", padx=14, pady=9,
            font=("Segoe UI", 9, "bold"), cursor="hand2",
            bd=0,
        )
        btn_copiar_mdns.pack(side=tk.LEFT, padx=3)

    btn_copiar = tk.Button(
        btns, text="Copiar IP", command=copiar_ip,
        bg=BG_CARD, fg=TEXT,
        activebackground=BORDA, activeforeground=TEXT,
        relief="flat", padx=14, pady=9,
        font=("Segoe UI", 9, "bold"), cursor="hand2",
        bd=0,
    )
    btn_copiar.pack(side=tk.LEFT, padx=3)

    btn_abrir = tk.Button(
        btns, text="Abrir no navegador", command=abrir,
        bg=BRAND, fg="#ffffff",
        activebackground=BRAND_HOVER, activeforeground="#ffffff",
        relief="flat", padx=16, pady=9,
        font=("Segoe UI", 9, "bold"), cursor="hand2",
        bd=0,
    )
    btn_abrir.pack(side=tk.LEFT, padx=4)

    # ---- Rodapé ----
    tk.Label(root, text="Feche esta janela para encerrar o servidor",
             bg=BG_DARK, fg=TEXT_MUTED,
             font=("Segoe UI", 8)).pack(side="bottom", pady=12)

    def on_close():
        try:
            if zc and zc_info:
                try:
                    zc.unregister_service(zc_info)
                    zc.close()
                except Exception:
                    pass
            root.destroy()
        finally:
            os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Centraliza na tela
    root.update_idletasks()
    w, h = 440, 620
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    root.mainloop()


if __name__ == "__main__":
    main()

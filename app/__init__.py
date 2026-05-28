import os
import shutil
from datetime import datetime
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from sqlalchemy import inspect, text
from .models import db, User, seed_if_empty
from .sockets import socketio


def _precisa_migrar():
    """
    Verifica se o schema atual do DB precisa ganhar alguma alteração.
    Usado para decidir se vale a pena fazer backup antes.
    """
    try:
        insp = inspect(db.engine)

        # Banco novinho — db.create_all() já vai criar tudo do zero, sem migração
        if not insp.has_table("usuarios"):
            return False

        cols_usr = {c["name"] for c in insp.get_columns("usuarios")}
        if "permissoes_json" not in cols_usr or "foto" not in cols_usr:
            return True

        if insp.has_table("pedidos"):
            cols_ped = {c["name"] for c in insp.get_columns("pedidos")}
            if "cupom_impresso_em" not in cols_ped:
                return True

        if insp.has_table("produtos"):
            cols_prod = {c["name"] for c in insp.get_columns("produtos")}
            for col in ("ultima_quantidade", "ultima_contagem_data", "alerta_se_abaixo"):
                if col not in cols_prod:
                    return True

        # Schema legado intermediário
        if insp.has_table("inventario_movimentos"):
            return True
        if insp.has_table("inventario_contagens"):
            cols = {c["name"] for c in insp.get_columns("inventario_contagens")}
            if "produto_id" not in cols:
                return True

        return False
    except Exception:
        return False


def _path_externo(*partes):
    """Caminho relativo ao .exe (frozen) ou raiz do projeto (dev)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(base, *partes)


def _carregar_pix_settings(app):
    """
    Sobrescreve PIX_CHAVE / PIX_NOME / PIX_CIDADE com valores salvos pelo admin
    em pix_settings.json (ao lado do .exe). Se o arquivo não existir, mantém
    o que está em config.py / env vars.
    """
    import json
    path = _path_externo("pix_settings.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in ("PIX_CHAVE", "PIX_NOME", "PIX_CIDADE"):
                v = data.get(key)
                if isinstance(v, str):
                    app.config[key] = v
    except Exception as e:
        app.logger.warning(f"[PIX] Falha ao carregar pix_settings.json: {e}")


def _garantir_secret_key(app):
    """
    Garante uma SECRET_KEY estável e persistente entre reinícios.
    - Se SECRET_KEY já vem de variável de ambiente válida, mantém.
    - Se está no default 'dev-secret-key', gera uma chave aleatória e salva
      em arquivo `.secret_key` ao lado do executável.
    Sem chave estável, qualquer reinício invalida todos os cookies de sessão
    e os usuários caem na tela de login.
    """
    import secrets
    chave_atual = app.config.get("SECRET_KEY") or ""
    if chave_atual and chave_atual != "dev-secret-key":
        return  # já tem chave customizada (env var)

    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    secret_path = os.path.join(base, ".secret_key")

    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                app.config["SECRET_KEY"] = key
                return
        except Exception:
            pass

    # gera + persiste
    nova = secrets.token_urlsafe(48)
    try:
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(nova)
        app.config["SECRET_KEY"] = nova
        app.logger.info(f"[SECRET_KEY] Chave gerada e salva em {secret_path}")
    except Exception as e:
        app.config["SECRET_KEY"] = nova  # ao menos roda enquanto não pode salvar
        app.logger.warning(f"[SECRET_KEY] Não foi possível persistir: {e}")


import sys


def _backup_sqlite_pre_migracao(app):
    """
    Cria uma cópia do arquivo .db em uploads/backups antes de rodar migrações.
    Mantém só os 10 backups mais recentes. Não-destrutivo.
    Só roda se: DB é SQLite, arquivo existe, e há migração pendente.
    """
    try:
        if not _precisa_migrar():
            return None

        url = db.engine.url
        if url.drivername != "sqlite":
            return None
        path = url.database
        if not path or not os.path.exists(path):
            return None

        base = os.path.dirname(path) or "."
        backups_dir = os.path.join(base, "backups")
        os.makedirs(backups_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(backups_dir, f"comanda_pre_migracao_{ts}.db")
        shutil.copy2(path, dst)

        # Retém apenas os 10 mais recentes
        existentes = sorted(
            f for f in os.listdir(backups_dir)
            if f.startswith("comanda_pre_migracao_") and f.endswith(".db")
        )
        for old in existentes[:-10]:
            try:
                os.remove(os.path.join(backups_dir, old))
            except Exception:
                pass

        app.logger.warning(f"[MIGRACAO] Backup criado em: {dst}")
        return dst
    except Exception as e:
        app.logger.warning(f"[MIGRACAO] Falha ao criar backup automatico: {e}")
        return None


def _migrar_coluna_permissoes():
    """
    Adiciona colunas novas à tabela `usuarios` se ainda não existirem.
    Compatível com SQLite (ALTER TABLE ADD COLUMN).
    """
    try:
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("usuarios")}
        with db.engine.begin() as conn:
            if "permissoes_json" not in cols:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN permissoes_json TEXT"))
            if "foto" not in cols:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN foto VARCHAR(255)"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Falha na migração usuarios: {e}")


def _migrar_cupom_impresso():
    """
    Adiciona a coluna `cupom_impresso_em` em `pedidos` se ainda não existir.
    Permite rastrear quais pedidos tiveram o cupom de fato impresso.
    """
    try:
        insp = inspect(db.engine)
        if not insp.has_table("pedidos"):
            return
        cols = {c["name"] for c in insp.get_columns("pedidos")}
        if "cupom_impresso_em" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE pedidos ADD COLUMN cupom_impresso_em DATETIME"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Falha na migração cupom_impresso: {e}")


def _migrar_inventario_para_contagem():
    """
    Migra o schema do inventário ao longo das versões:
      - dropa `inventario_movimentos` (controle de estoque legado)
      - adiciona colunas de cache em `inventario_itens`
      - adiciona colunas de cache em `produtos` (contagem física)
      - dropa `inventario_contagens` se faltar `produto_id` (será recriada por db.create_all)
    """
    try:
        insp = inspect(db.engine)

        # 1) Drop tabela antiga de movimentos (legado)
        if insp.has_table("inventario_movimentos"):
            with db.engine.begin() as conn:
                conn.execute(text("DROP TABLE inventario_movimentos"))

        # 2) Adiciona colunas em inventario_itens
        if insp.has_table("inventario_itens"):
            cols = {c["name"] for c in insp.get_columns("inventario_itens")}
            with db.engine.begin() as conn:
                if "ultima_quantidade" not in cols:
                    conn.execute(text("ALTER TABLE inventario_itens ADD COLUMN ultima_quantidade INTEGER"))
                if "ultima_contagem_data" not in cols:
                    conn.execute(text("ALTER TABLE inventario_itens ADD COLUMN ultima_contagem_data DATE"))
                if "alerta_se_abaixo" not in cols:
                    conn.execute(text("ALTER TABLE inventario_itens ADD COLUMN alerta_se_abaixo INTEGER"))

        # 3) Adiciona colunas em produtos (cache de contagem)
        if insp.has_table("produtos"):
            cols = {c["name"] for c in insp.get_columns("produtos")}
            with db.engine.begin() as conn:
                if "ultima_quantidade" not in cols:
                    conn.execute(text("ALTER TABLE produtos ADD COLUMN ultima_quantidade INTEGER"))
                if "ultima_contagem_data" not in cols:
                    conn.execute(text("ALTER TABLE produtos ADD COLUMN ultima_contagem_data DATE"))
                if "alerta_se_abaixo" not in cols:
                    conn.execute(text("ALTER TABLE produtos ADD COLUMN alerta_se_abaixo INTEGER"))

        # 4) Rebuild de inventario_contagens se ainda não tem produto_id
        if insp.has_table("inventario_contagens"):
            cols = {c["name"] for c in insp.get_columns("inventario_contagens")}
            if "produto_id" not in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("DROP TABLE inventario_contagens"))
                # db.create_all() na sequência recria com schema novo
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Falha na migração inventário: {e}")

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object("config.Config")

    import os
    os.makedirs(app.instance_path, exist_ok=True)

    # Garante SECRET_KEY estável (persiste em arquivo .secret_key se for default)
    _garantir_secret_key(app)

    # Carrega chave Pix salva pelo admin (sobrescreve config.py se existir)
    _carregar_pix_settings(app)

    db.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        # Backup defensivo do SQLite ANTES de qualquer alteração de schema.
        # Só dispara se houver migração pendente.
        _backup_sqlite_pre_migracao(app)

        db.create_all()
        _migrar_coluna_permissoes()
        _migrar_inventario_para_contagem()
        _migrar_cupom_impresso()
        # roda novamente para recriar tabelas que podem ter sido dropadas pela migração
        db.create_all()
        seed_if_empty()

    # Disponibiliza o registry de permissões nos templates
    from .utils.permissoes import PERMISSOES, PERMISSOES_BY_KEY
    @app.context_processor
    def _inject_permissoes():
        return {
            "PERMISSOES": PERMISSOES,
            "PERMISSOES_BY_KEY": PERMISSOES_BY_KEY,
        }

    from .public import public_bp
    from .admin import admin_bp
    from .admin.api import admin_api_bp
    from .auth import auth_bp

    app.register_blueprint(public_bp, url_prefix="/public")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(admin_api_bp, url_prefix="/admin/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("admin.pedidos"))
        return redirect(url_for("auth.login"))

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404


    # ================================
    # 🔥 SERVIR IMAGENS UPLOADS
    # ================================
    from flask import send_from_directory
    import sys

    def _base_externo():
        """
        Pasta-raiz para conteúdo persistente (uploads, db, backups).
        Sempre relativo ao .exe quando frozen, e ao diretório do projeto em dev.
        Não usa os.getcwd() pra evitar caminhos errados quando o .exe é
        iniciado via atalho com 'Iniciar em' diferente.
        """
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    def get_upload_dir():
        pasta = os.path.join(_base_externo(), "uploads", "produtos")
        os.makedirs(pasta, exist_ok=True)
        return pasta

    UPLOAD_DIR_GLOBAL = get_upload_dir()

    @app.route("/uploads/produtos/<filename>")
    def imagem_produto_global(filename):
        return send_from_directory(UPLOAD_DIR_GLOBAL, filename)

    # ================================
    # 🔥 SERVIR FOTOS DE USUÁRIOS
    # ================================
    def get_upload_dir_usuarios():
        pasta = os.path.join(_base_externo(), "uploads", "usuarios")
        os.makedirs(pasta, exist_ok=True)
        return pasta

    UPLOAD_DIR_USUARIOS = get_upload_dir_usuarios()

    @app.route("/uploads/usuarios/<filename>")
    def imagem_usuario(filename):
        return send_from_directory(UPLOAD_DIR_USUARIOS, filename)

    app.config["UPLOAD_DIR_USUARIOS"] = UPLOAD_DIR_USUARIOS

    return app

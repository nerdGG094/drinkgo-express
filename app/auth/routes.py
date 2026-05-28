import os
from flask import render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from ..models import User, db
from . import auth_bp


ALLOWED_EXT_FOTO = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "garcom":
            return redirect(url_for("public.novo"))
        elif current_user.role == "caixa":
            return redirect(url_for("admin.pedidos"))
        else:
            return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        senha = request.form.get("senha") or ""
        # Busca case-insensitive: mesmo que o cadastro tenha sido em
        # MAIUSCULAS e o usuário digite em minúsculas (ou vice-versa)
        user = User.query.filter(
            func.lower(User.email) == email.lower(),
            User.ativo == True,
        ).first()
        if user and check_password_hash(user.senha_hash, senha):
            session.permanent = True
            login_user(user, remember=True)
            if user.role == "garcom":
                return redirect(url_for("public.novo"))
            elif user.role == "caixa":
                return redirect(url_for("admin.pedidos"))
            else:
                return redirect(url_for("admin.dashboard"))
        flash("Usuário ou senha inválidos.", "warning")
    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


# ======================================================================
# PERFIL — usuário edita os próprios dados (nome, email, foto, senha)
# ======================================================================
@auth_bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    user = current_user

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip()

        if not nome or not email:
            flash("Nome e e-mail são obrigatórios.", "warning")
            return redirect(url_for("auth.perfil"))

        # E-mail único (exceto o próprio)
        if email != user.email:
            outro = User.query.filter(User.email == email, User.id != user.id).first()
            if outro:
                flash("Este e-mail já está em uso por outro usuário.", "warning")
                return redirect(url_for("auth.perfil"))

        user.nome = nome
        user.email = email

        # ---------- Foto (upload opcional) ----------
        remover_foto = bool(request.form.get("remover_foto"))
        if remover_foto and user.foto:
            try:
                pasta = current_app.config.get("UPLOAD_DIR_USUARIOS")
                if pasta:
                    f = os.path.join(pasta, user.foto)
                    if os.path.exists(f):
                        os.remove(f)
            except Exception:
                pass
            user.foto = None

        arquivo = request.files.get("foto_arquivo")
        if arquivo and arquivo.filename:
            ext = os.path.splitext(arquivo.filename)[1].lower()
            if ext not in ALLOWED_EXT_FOTO:
                flash("Formato de imagem inválido. Use PNG, JPG, GIF ou WEBP.", "warning")
                return redirect(url_for("auth.perfil"))

            filename = secure_filename(f"user_{user.id}{ext}")
            pasta = current_app.config.get("UPLOAD_DIR_USUARIOS")
            os.makedirs(pasta, exist_ok=True)
            arquivo.save(os.path.join(pasta, filename))
            user.foto = filename

        # ---------- Senha (opcional, com confirmação dupla) ----------
        alterar = bool(request.form.get("alterar_senha"))
        senha_atual = (request.form.get("senha_atual") or "").strip()
        nova_senha = (request.form.get("senha") or "").strip()
        confirmar = (request.form.get("senha_confirmar") or "").strip()

        senha_alterada = False
        if alterar:
            if not senha_atual:
                flash("Informe a senha atual para alterá-la.", "warning")
                return redirect(url_for("auth.perfil"))
            if not check_password_hash(user.senha_hash, senha_atual):
                flash("Senha atual incorreta. A senha NÃO foi alterada.", "warning")
                return redirect(url_for("auth.perfil"))
            if not nova_senha:
                flash("Informe a nova senha.", "warning")
                return redirect(url_for("auth.perfil"))
            if nova_senha != confirmar:
                flash("Nova senha e confirmação não coincidem.", "warning")
                return redirect(url_for("auth.perfil"))
            user.senha_hash = generate_password_hash(nova_senha)
            senha_alterada = True

        db.session.commit()

        if senha_alterada:
            flash("Perfil atualizado e senha redefinida.", "success")
        else:
            flash("Perfil atualizado.", "success")
        return redirect(url_for("auth.perfil"))

    return render_template("auth/perfil.html", user=user)

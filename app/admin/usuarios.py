from flask import render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from ..models import db, User
from ..utils.decorators import role_required
from ..utils.permissoes import PERMISSOES, PERMISSOES_BY_KEY, permissoes_default_por_role
from . import admin_bp


def _coletar_permissoes_form():
    """Lê os checkboxes 'permissao_<key>' do formulário e devolve a lista válida."""
    chaves_validas = set(PERMISSOES_BY_KEY.keys())
    selecionadas = []
    for key in chaves_validas:
        if request.form.get(f"permissao_{key}"):
            selecionadas.append(key)
    return selecionadas


@admin_bp.route("/usuarios")
@role_required("admin", "caixa")
def usuarios():
    usuarios = User.query.order_by(User.nome).all()
    return render_template("admin/usuarios.html", usuarios=usuarios)


@admin_bp.route("/usuarios/novo", methods=["GET", "POST"])
@role_required("admin")
def usuarios_novo():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        senha = request.form.get("senha")
        role = request.form.get("role")

        if not (nome and email and senha and role):
            flash("Preencha todos os campos.", "warning")
            return redirect(url_for("admin.usuarios_novo"))

        if User.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.", "warning")
            return redirect(url_for("admin.usuarios_novo"))

        u = User(
            nome=nome,
            email=email,
            senha_hash=generate_password_hash(senha),
            role=role,
        )

        # Permissões: admin sempre tem tudo; demais herdam o checkbox enviado
        if role != "admin":
            u.set_permissoes(_coletar_permissoes_form())

        db.session.add(u)
        db.session.commit()
        flash("Usuário criado.", "success")
        return redirect(url_for("admin.usuarios"))

    return render_template(
        "admin/usuarios_form.html",
        usuario=None,
        permissoes_disponiveis=PERMISSOES,
        permissoes_marcadas=set(permissoes_default_por_role("garcom")),
    )


@admin_bp.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
@role_required("admin")
def usuarios_editar(user_id):
    usuario = User.query.get_or_404(user_id)

    if request.method == "POST":
        usuario.nome = (request.form.get("nome") or "").strip()
        usuario.email = (request.form.get("email") or "").strip()
        usuario.role = request.form.get("role")
        usuario.ativo = bool(request.form.get("ativo"))

        # Senha: trata strip + flag explícita "alterar_senha"
        senha_alterada = False
        alterar = request.form.get("alterar_senha")  # checkbox/flag explícita
        nova_senha = (request.form.get("senha") or "").strip()
        confirmar = (request.form.get("senha_confirmar") or "").strip()

        if alterar and nova_senha:
            if nova_senha != confirmar:
                flash("As duas senhas digitadas não coincidem. Senha NÃO foi alterada.", "warning")
                return redirect(url_for("admin.usuarios_editar", user_id=usuario.id))
            usuario.senha_hash = generate_password_hash(nova_senha)
            senha_alterada = True

        # Permissões
        if usuario.role == "admin":
            usuario.set_permissoes(None)
        else:
            usuario.set_permissoes(_coletar_permissoes_form())

        db.session.commit()

        if senha_alterada:
            flash(f"Usuário atualizado e senha redefinida para {usuario.nome}.", "success")
        else:
            flash("Usuário atualizado (senha mantida).", "info")

        return redirect(url_for("admin.usuarios"))

    return render_template(
        "admin/usuarios_form.html",
        usuario=usuario,
        permissoes_disponiveis=PERMISSOES,
        permissoes_marcadas=set(usuario.permissoes_efetivas()),
    )

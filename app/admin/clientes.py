from flask import render_template, request, redirect, url_for, flash
from ..models import db, Cliente
from ..utils.decorators import role_required
from . import admin_bp

@admin_bp.route("/clientes")
@role_required("admin", "caixa")
def clientes():
    q = request.args.get("q")
    query = Cliente.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Cliente.nome.ilike(like)) |
            (Cliente.codigo.ilike(like)) |
            (Cliente.telefone.ilike(like))
        )
    clientes = query.order_by(Cliente.nome).all()
    return render_template("admin/clientes.html", clientes=clientes, q=q)

@admin_bp.route("/clientes/novo", methods=["GET", "POST"])
@role_required("admin", "caixa")
def clientes_novo():
    if request.method == "POST":
        codigo = request.form.get("codigo")
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        endereco = request.form.get("endereco")
        obs = request.form.get("obs")

        if not nome:
            flash("Nome é obrigatório.", "warning")
            return redirect(url_for("admin.clientes_novo"))

        if codigo and Cliente.query.filter_by(codigo=codigo).first():
            flash("Código já utilizado.", "warning")
            return redirect(url_for("admin.clientes_novo"))

        c = Cliente(codigo=codigo or None, nome=nome, telefone=telefone, endereco=endereco, obs=obs)
        db.session.add(c)
        db.session.commit()
        return redirect(url_for("admin.clientes"))

    return render_template("admin/clientes_form.html", cliente=None)

@admin_bp.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
@role_required("admin", "caixa")
def clientes_editar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == "POST":
        cliente.codigo = request.form.get("codigo") or None
        cliente.nome = request.form.get("nome")
        cliente.telefone = request.form.get("telefone")
        cliente.endereco = request.form.get("endereco")
        cliente.obs = request.form.get("obs")
        cliente.ativo = bool(request.form.get("ativo"))
        db.session.commit()
        return redirect(url_for("admin.clientes"))

    return render_template("admin/clientes_form.html", cliente=cliente)

from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from app import db
from app.models import EntradaProduto, Produto
from . import admin_bp
from app.utils.decorators import role_required
from app.utils.permissoes import permissao_required
from datetime import datetime
from sqlalchemy import func

@admin_bp.route("/entradas/produtos", methods=["GET", "POST"])
@permissao_required("entradas")
def entrada_produtos():

    # ==========================
    # POST (registro de entrada)
    # ==========================
    if request.method == "POST":
        nome = request.form.get("produto_nome")
        qtd = request.form.get("quantidade")
        obs = request.form.get("observacao")

        if not nome or not qtd:
            flash("Informe produto e quantidade.", "warning")
            return redirect(url_for("admin.entrada_produtos"))

        entrada = EntradaProduto(
            produto_nome=nome,
            quantidade=int(qtd),
            observacao=obs,
            usuario_id=current_user.id
        )

        db.session.add(entrada)
        db.session.commit()

        flash("Entrada registrada com sucesso.", "success")
        return redirect(url_for("admin.entrada_produtos"))

    # ==========================
    # GET (listagem + filtro)
    # ==========================
    query = EntradaProduto.query

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    # filtro por data (sem bug de horário)
    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        query = query.filter(func.date(EntradaProduto.criado_em) >= data_inicio.date())

    if data_fim:
        data_fim = datetime.strptime(data_fim, "%Y-%m-%d")
        query = query.filter(func.date(EntradaProduto.criado_em) <= data_fim.date())

    entradas = (
        query
        .order_by(EntradaProduto.criado_em.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "admin/entrada_produtos.html",
        entradas=entradas,
        produtos=Produto.query.all()  # ESSENCIAL pro select funcionar
    )
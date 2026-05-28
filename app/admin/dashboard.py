from flask import render_template
from ..utils.decorators import role_required
from ..utils.permissoes import permissao_required
from . import admin_bp
from ..models import db
from sqlalchemy import func
from datetime import date


@admin_bp.route("/dashboard")
@permissao_required("dashboard")
def dashboard():

    from app.models import User, Pedido, PedidoItem, Produto

    hoje = date.today()

    # ================================
    # 1) QUEM FINALIZOU MAIS PEDIDOS
    # ================================
    ranking_mesas = (
        db.session.query(User.nome, func.count(Pedido.id))
        .join(Pedido, Pedido.garcom_id == User.id)
        .filter(Pedido.pedido_fechado == True)
        .group_by(User.nome)
        .all()
    )

    usuarios = [u for u, _ in ranking_mesas]
    total_mesas = [q for _, q in ranking_mesas]

    total_geral = sum(total_mesas)
    porcentagens = [
        (q / total_geral) * 100 if total_geral else 0
        for q in total_mesas
    ]

    # ================================
    # 2) SAÍDA DIÁRIA DE PRODUTOS
    # ================================
    saida_diaria = (
        db.session.query(
            func.date(Pedido.criado_em),
            func.sum(PedidoItem.quantidade)
        )
        .join(PedidoItem, Pedido.id == PedidoItem.pedido_id)
        .filter(Pedido.pedido_fechado == True)
        .group_by(func.date(Pedido.criado_em))
        .order_by(func.date(Pedido.criado_em))
        .all()
    )

    dias = [str(d) for d, _ in saida_diaria]
    qtd_dia = [q for _, q in saida_diaria]

    # ================================
    # 3) PRODUTOS MAIS VENDIDOS (GERAL)
    # ================================
    prod_vendidos = (
        db.session.query(
            Produto.nome,
            func.sum(PedidoItem.quantidade)
        )
        .join(PedidoItem, Produto.id == PedidoItem.produto_id)
        .join(Pedido, PedidoItem.pedido_id == Pedido.id)
        .filter(Pedido.pedido_fechado == True)
        .group_by(Produto.nome)
        .order_by(func.sum(PedidoItem.quantidade).desc())
        .limit(10)
        .all()
    )

    prod_nomes = [p for p, _ in prod_vendidos]
    prod_qtd = [q for _, q in prod_vendidos]

    # ================================
    # 4) PEDIDOS FINALIZADOS HOJE (TODOS OS TIPOS)
    # ================================
    mesas_finalizadas_hoje = (
        db.session.query(func.count(Pedido.id))
        .filter(Pedido.pedido_fechado == True)
        .filter(func.date(Pedido.criado_em) == hoje)
        .scalar()
    )

    # ================================
    # 5) ITENS VENDIDOS HOJE (TODOS OS TIPOS)
    # ================================
    itens_vendidos_hoje = (
        db.session.query(func.sum(PedidoItem.quantidade))
        .join(Pedido)
        .filter(Pedido.pedido_fechado == True)
        .filter(func.date(Pedido.criado_em) == hoje)
        .scalar()
    ) or 0

    # ================================
    # 6) FATURAMENTO DO DIA (TOTAL)
    # ================================
    faturamento_hoje = (
        db.session.query(
            func.sum(PedidoItem.quantidade * Produto.preco)
        )
        .join(Pedido, PedidoItem.pedido_id == Pedido.id)
        .join(Produto, Produto.id == PedidoItem.produto_id)
        .filter(Pedido.pedido_fechado == True)
        .filter(func.date(Pedido.criado_em) == hoje)
        .scalar()
    ) or 0

    return render_template(
        "admin/dashboard.html",
        mesas_finalizadas_hoje=mesas_finalizadas_hoje,
        itens_vendidos_hoje=itens_vendidos_hoje,
        faturamento_hoje=faturamento_hoje,
        usuarios=usuarios,
        total_mesas=total_mesas,
        porcentagens=porcentagens,
        dias=dias,
        qtd_dia=qtd_dia,
        prod_nomes=prod_nomes,
        prod_qtd=prod_qtd
    )

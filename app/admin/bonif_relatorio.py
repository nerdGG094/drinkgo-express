from flask import render_template, request
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from ..models import db, Pedido, PedidoItem, Produto
from ..utils.decorators import role_required
from ..utils.permissoes import permissao_required
from . import admin_bp

@admin_bp.route("/relatorio/bonificacao")
@permissao_required("relatorios")
def bonif_relatorio_itens():
    data_ini_str = request.args.get("data_ini")
    data_fim_str = request.args.get("data_fim")

    hoje = datetime.now().date()
    amanha = hoje + timedelta(days=1)

    # DATA INICIAL
    if not data_ini_str:
        data_ini = datetime.combine(hoje, datetime.min.time())
    else:
        data_ini = datetime.combine(
            datetime.strptime(data_ini_str, "%Y-%m-%d").date(),
            datetime.min.time()
        )

    # DATA FINAL
    if not data_fim_str:
        data_fim = datetime.combine(amanha, datetime.max.time())
    else:
        data_fim = datetime.combine(
            datetime.strptime(data_fim_str, "%Y-%m-%d").date(),
            datetime.max.time()
        )

    q = (
        db.session.query(
            Produto.nome.label("produto_nome"),
            func.sum(PedidoItem.quantidade).label("qtd"),
            func.sum(PedidoItem.quantidade * Produto.preco).label("total")
        )
        .join(Pedido, PedidoItem.pedido_id == Pedido.id)
        .join(Produto, PedidoItem.produto_id == Produto.id)
        .filter(Pedido.criado_em >= data_ini, Pedido.criado_em <= data_fim)
        .filter(Pedido.forma_pagamento == "bonif")  # 🔥 SOMENTE BONIFICAÇÃ
        .filter(
            or_(
                Pedido.nfe_emitida == False,
                Pedido.nfe_emitida == None
            )
        )
    .group_by(Produto.nome)
    .order_by(func.sum(PedidoItem.quantidade).desc())
)
    itens = q.all()

    return render_template(
        "admin/bonif_rel_itens.html",
        itens=itens,
        data_ini=data_ini.date(),
        data_fim=data_fim.date()
    )
#-------------------------------
from flask import Response, request
from datetime import datetime
from ..models import db, PedidoItem, Produto, Pedido
from . import admin_bp

@admin_bp.route("/relatorio/exportar_csv_bonif")
@permissao_required("relatorios")
def exportar_relatorio_csv_bonif():
    # Recebe parâmetros
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    # Converte para datetime
    try:
        dt_ini = datetime.fromisoformat(data_ini)
        dt_fim = datetime.fromisoformat(data_fim)
    except:
        return "Datas inválidas.", 400

    # Consulta idêntica ao relatório
    query = db.session.query(
        Produto.nome.label("produto_nome"),
        db.func.sum(PedidoItem.quantidade).label("qtd"),
        db.func.sum(PedidoItem.quantidade * Produto.preco).label("total")
    ).join(
        Produto, Produto.id == PedidoItem.produto_id
    ).join(
        Pedido, Pedido.id == PedidoItem.pedido_id
    ).filter(
        Pedido.criado_em >= dt_ini,
        Pedido.criado_em <= dt_fim,
        Pedido.forma_pagamento == "bonif",
        or_(Pedido.nfe_emitida == False, Pedido.nfe_emitida == None)
    ).group_by(
        Produto.nome
    ).order_by(
        Produto.nome
    )

    itens = query.all()

    linhas = ["sep=;", "PRODUTO;QTD;TOTAL"]

    total_qtd = 0
    total_dinheiro = 0.0

    for item in itens:
        qtd = item.qtd or 0
        total = float(item.total) if item.total else 0.0  # 🔥 correção aqui

        total_qtd += qtd
        total_dinheiro += total

        total_formatado = f"{total:.2f}".replace(".", ",")
        nome_produto = item.produto_nome.replace('"', '""')  # escapa aspas

        linhas.append(
            f"\"{nome_produto}\";{qtd};{total_formatado}"
        )

    # linha de totalização
    total_dinheiro_formatado = f"{total_dinheiro:.2f}".replace(".", ",")

    linhas.append("")
    linhas.append(
        f"\"TOTAL GERAL\";{total_qtd};{total_dinheiro_formatado}"
    )

    csv_data = "\n".join(linhas)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=relatorio_{data_ini}_a_{data_fim}.csv"
        }
    )

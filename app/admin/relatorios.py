from flask import render_template, request, Response
from sqlalchemy import func, or_, case
from datetime import datetime, timedelta
from ..models import db, Pedido, PedidoItem, Produto, User
from ..utils.decorators import role_required
from ..utils.permissoes import permissao_required
from . import admin_bp


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _parse_intervalo(data_ini_str, data_fim_str):
    """Retorna (dt_ini, dt_fim) cobrindo todo o intervalo de dias."""
    hoje = datetime.now().date()
    amanha = hoje + timedelta(days=1)

    if not data_ini_str:
        dt_ini = datetime.combine(hoje, datetime.min.time())
    else:
        dt_ini = datetime.combine(
            datetime.strptime(data_ini_str, "%Y-%m-%d").date(),
            datetime.min.time()
        )

    if not data_fim_str:
        dt_fim = datetime.combine(amanha, datetime.max.time())
    else:
        dt_fim = datetime.combine(
            datetime.strptime(data_fim_str, "%Y-%m-%d").date(),
            datetime.max.time()
        )

    return dt_ini, dt_fim


def _subquery_totais_brutos():
    """
    Subquery: total bruto por pedido.
    É o divisor correto para ratear o desconto entre os itens.
    """
    return (
        db.session.query(
            PedidoItem.pedido_id.label("pedido_id"),
            func.sum(PedidoItem.quantidade * Produto.preco).label("total_bruto")
        )
        .join(Produto, Produto.id == PedidoItem.produto_id)
        .group_by(PedidoItem.pedido_id)
        .subquery()
    )


# ----------------------------------------------------------------------
# Helpers de breakdown por forma de pagamento
# ----------------------------------------------------------------------
def _label_forma(forma, tipo_cartao=None):
    """Devolve um label amigável (sempre em CAIXA ALTA) para a forma de pagamento."""
    if not forma:
        return None
    f = forma.lower().strip()
    if f == "cancelado":
        return None
    if f == "cartao":
        t = (tipo_cartao or "").lower().strip()
        if t == "credito":
            return "CARTÃO CRÉDITO"
        if t == "debito":
            return "CARTÃO DÉBITO"
        return "CARTÃO"
    if f == "dinheiro":
        return "DINHEIRO"
    if f == "pix":
        return "PIX"
    if f == "bonif":
        return "BONIFICAÇÃO"
    return forma.upper()


def _breakdown_pagamentos(dt_ini, dt_fim):
    """
    Soma o valor recebido em cada forma de pagamento no período.
    - Pedidos cancelados são ignorados.
    - Pedidos com NFe emitida são ignorados (consistente com o resto do relatório).
    - Pedidos com 2 formas de pagamento têm o total dividido entre elas.
    Retorna lista [{label, total}, ...] ordenada por valor desc.
    """
    sub_totais = _subquery_totais_brutos()

    pedidos = (
        db.session.query(
            Pedido.id,
            Pedido.forma_pagamento,
            Pedido.forma_pagamento2,
            Pedido.tipo_cartao,
            Pedido.valor_pagamento2,
            Pedido.desconto,
            func.coalesce(sub_totais.c.total_bruto, 0).label("total_bruto"),
        )
        .outerjoin(sub_totais, sub_totais.c.pedido_id == Pedido.id)
        .filter(Pedido.criado_em >= dt_ini, Pedido.criado_em <= dt_fim)
        .filter(or_(Pedido.nfe_emitida == False, Pedido.nfe_emitida == None))
        .all()
    )

    breakdown = {}
    for p in pedidos:
        if not p.forma_pagamento:
            continue
        if (p.forma_pagamento or "").lower().strip() == "cancelado":
            continue

        total_cd = float(p.total_bruto or 0) - float(p.desconto or 0)
        if total_cd < 0:
            total_cd = 0.0

        val2 = float(p.valor_pagamento2 or 0)
        if p.forma_pagamento2:
            val1 = total_cd - val2
            if val1 < 0:
                val1 = 0.0
        else:
            val1 = total_cd
            val2 = 0.0

        lbl1 = _label_forma(p.forma_pagamento, p.tipo_cartao)
        if lbl1 and val1 > 0:
            breakdown[lbl1] = breakdown.get(lbl1, 0.0) + val1

        if p.forma_pagamento2:
            lbl2 = _label_forma(p.forma_pagamento2)
            if lbl2 and val2 > 0:
                breakdown[lbl2] = breakdown.get(lbl2, 0.0) + val2

    return sorted(
        [{"label": k, "total": v} for k, v in breakdown.items()],
        key=lambda x: x["total"],
        reverse=True,
    )


# ----------------------------------------------------------------------
# Tela: Relatório de itens vendidos (com desconto rateado)
# ----------------------------------------------------------------------
@admin_bp.route("/relatorio/itens")
@permissao_required("relatorios")
def relatorio_itens():
    data_ini_str = request.args.get("data_ini")
    data_fim_str = request.args.get("data_fim")
    dt_ini, dt_fim = _parse_intervalo(data_ini_str, data_fim_str)

    sub_totais = _subquery_totais_brutos()

    # Subtotal do item (bruto) e desconto rateado
    subtotal_item = PedidoItem.quantidade * Produto.preco
    desconto_rateado = (
        (subtotal_item / func.nullif(sub_totais.c.total_bruto, 0))
        * func.coalesce(Pedido.desconto, 0)
    )
    total_liquido_item = subtotal_item - desconto_rateado

    q = (
        db.session.query(
            Produto.nome.label("produto_nome"),
            func.sum(PedidoItem.quantidade).label("qtd"),
            func.sum(subtotal_item).label("total_bruto"),
            func.sum(desconto_rateado).label("desconto"),
            func.sum(total_liquido_item).label("total"),  # líquido com desconto aplicado
        )
        .join(Pedido, PedidoItem.pedido_id == Pedido.id)
        .join(Produto, PedidoItem.produto_id == Produto.id)
        .join(sub_totais, sub_totais.c.pedido_id == Pedido.id)
        .filter(Pedido.criado_em >= dt_ini, Pedido.criado_em <= dt_fim)
        .filter(or_(Pedido.nfe_emitida == False, Pedido.nfe_emitida == None))
        .filter(or_(
            Pedido.forma_pagamento == None,
            func.lower(func.trim(Pedido.forma_pagamento)).notin_(["bonif", "cancelado"])
        ))
        .group_by(Produto.id, Produto.nome)
        .order_by(func.sum(PedidoItem.quantidade).desc())
    )

    itens = q.all()
    pagamentos = _breakdown_pagamentos(dt_ini, dt_fim)
    total_pagamentos = sum(p["total"] for p in pagamentos)

    return render_template(
        "admin/relatorio_itens.html",
        itens=itens,
        pagamentos=pagamentos,
        total_pagamentos=total_pagamentos,
        data_ini=dt_ini.date(),
        data_fim=dt_fim.date()
    )


# ----------------------------------------------------------------------
# CSV: Relatório de itens vendidos
# ----------------------------------------------------------------------
@admin_bp.route("/relatorio/exportar_csv")
@permissao_required("relatorios")
def exportar_relatorio_csv():
    data_ini = request.args.get("data_ini")
    data_fim = request.args.get("data_fim")

    try:
        dt_ini = datetime.fromisoformat(data_ini)
        dt_fim = datetime.fromisoformat(data_fim) + timedelta(days=1)
    except Exception:
        return "Datas inválidas.", 400

    sub_totais = _subquery_totais_brutos()

    subtotal_item = PedidoItem.quantidade * Produto.preco
    desconto_rateado = (
        (subtotal_item / func.nullif(sub_totais.c.total_bruto, 0))
        * func.coalesce(Pedido.desconto, 0)
    )
    total_liquido_item = subtotal_item - desconto_rateado

    query = (
        db.session.query(
            Produto.nome.label("produto_nome"),
            func.sum(PedidoItem.quantidade).label("qtd"),
            func.sum(subtotal_item).label("total_bruto"),
            func.sum(desconto_rateado).label("desconto"),
            func.sum(total_liquido_item).label("total_liquido"),
        )
        .join(Produto, Produto.id == PedidoItem.produto_id)
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .join(sub_totais, sub_totais.c.pedido_id == Pedido.id)
        .filter(
            Pedido.criado_em >= dt_ini,
            Pedido.criado_em < dt_fim,
            or_(Pedido.nfe_emitida == False, Pedido.nfe_emitida == None),
            or_(Pedido.forma_pagamento == None,
                func.lower(func.trim(Pedido.forma_pagamento)) != "bonif"),
        )
        .group_by(Produto.nome)
        .order_by(Produto.nome)
    )

    itens = query.all()

    linhas = ["sep=;", "PRODUTO;QTD;TOTAL_BRUTO;DESCONTO;TOTAL_LIQUIDO"]

    total_qtd = 0
    total_bruto_geral = 0.0
    total_desconto_geral = 0.0
    total_liquido_geral = 0.0

    for item in itens:
        qtd = item.qtd or 0
        bruto = float(item.total_bruto or 0)
        desc = float(item.desconto or 0)
        liquido = float(item.total_liquido or 0)

        total_qtd += qtd
        total_bruto_geral += bruto
        total_desconto_geral += desc
        total_liquido_geral += liquido

        bruto_f = f"{bruto:.2f}".replace(".", ",")
        desc_f = f"{desc:.2f}".replace(".", ",")
        liquido_f = f"{liquido:.2f}".replace(".", ",")

        nome_produto = item.produto_nome.replace('"', '""')
        linhas.append(f"\"{nome_produto}\";{qtd};{bruto_f};{desc_f};{liquido_f}")

    bruto_total_f = f"{total_bruto_geral:.2f}".replace(".", ",")
    desc_total_f = f"{total_desconto_geral:.2f}".replace(".", ",")
    liquido_total_f = f"{total_liquido_geral:.2f}".replace(".", ",")

    linhas.append("")
    linhas.append(f"\"TOTAL GERAL\";{total_qtd};{bruto_total_f};{desc_total_f};{liquido_total_f}")

    # ---- Bloco: Recebido por forma de pagamento ----
    # Mesma lógica da tela: divide split entre as duas formas, ignora
    # cancelados e pedidos com NFe emitida.
    pagamentos = _breakdown_pagamentos(dt_ini, dt_fim)

    if pagamentos:
        total_pgto = sum(p["total"] for p in pagamentos)
        linhas.append("")
        linhas.append("\"FORMA DE PAGAMENTO\";\"VALOR\"")
        for fp in pagamentos:
            v = f"{fp['total']:.2f}".replace(".", ",")
            nome = fp["label"].replace('"', '""')
            linhas.append(f"\"{nome}\";{v}")
        total_pgto_f = f"{total_pgto:.2f}".replace(".", ",")
        linhas.append(f"\"TOTAL RECEBIDO\";{total_pgto_f}")

    csv_data = "\n".join(linhas)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=relatorio_{data_ini}_a_{data_fim}.csv"
        }
    )


# ----------------------------------------------------------------------
# Tela: Pedidos por usuário (apenas admin)
# Agrupa por garçom e mostra contagem por tipo (mesa/retirada/delivery)
# + valor total movimentado por cada um.
# ----------------------------------------------------------------------
@admin_bp.route("/relatorio/usuarios")
@role_required("admin")
def relatorio_usuarios():
    data_ini_str = request.args.get("data_ini")
    data_fim_str = request.args.get("data_fim")
    dt_ini, dt_fim = _parse_intervalo(data_ini_str, data_fim_str)

    # Subquery: total bruto por pedido (sum quantidade * preco)
    sub_totais = (
        db.session.query(
            PedidoItem.pedido_id.label("pedido_id"),
            func.sum(PedidoItem.quantidade * Produto.preco).label("total_bruto"),
        )
        .join(Produto, Produto.id == PedidoItem.produto_id)
        .group_by(PedidoItem.pedido_id)
        .subquery()
    )

    # Busca todos os pedidos do intervalo + dados do usuário + total
    rows = (
        db.session.query(
            Pedido.id,
            Pedido.tipo,
            Pedido.forma_pagamento,
            Pedido.desconto,
            Pedido.garcom_id,
            User.nome.label("usuario_nome"),
            User.role.label("usuario_role"),
            func.coalesce(sub_totais.c.total_bruto, 0).label("total_bruto"),
        )
        .outerjoin(User, User.id == Pedido.garcom_id)
        .outerjoin(sub_totais, sub_totais.c.pedido_id == Pedido.id)
        .filter(Pedido.criado_em >= dt_ini, Pedido.criado_em <= dt_fim)
        .all()
    )

    # Agrega em Python — volume baixo, mais legível que SQL com vários CASE
    resumo = {}  # garcom_id -> dict
    total_geral = {
        "mesas": 0, "retiradas": 0, "deliveries": 0, "cancelados": 0,
        "total_pedidos": 0, "valor": 0.0,
    }

    for r in rows:
        chave = r.garcom_id or 0
        if chave not in resumo:
            resumo[chave] = {
                "id": r.garcom_id,
                "nome": r.usuario_nome or "(sem usuário)",
                "role": (r.usuario_role or "").upper() if r.usuario_role else "—",
                "mesas": 0, "retiradas": 0, "deliveries": 0,
                "cancelados": 0, "total_pedidos": 0, "valor": 0.0,
            }
        u = resumo[chave]

        cancelado = (r.forma_pagamento or "").lower().strip() == "cancelado"

        u["total_pedidos"] += 1
        total_geral["total_pedidos"] += 1

        if cancelado:
            u["cancelados"] += 1
            total_geral["cancelados"] += 1
            continue  # cancelado não soma valor nem entra no tipo

        # contagem por tipo (não-cancelados)
        tipo = (r.tipo or "").lower()
        if tipo == "mesa":
            u["mesas"] += 1
            total_geral["mesas"] += 1
        elif tipo == "retirada":
            u["retiradas"] += 1
            total_geral["retiradas"] += 1
        elif tipo == "delivery":
            u["deliveries"] += 1
            total_geral["deliveries"] += 1

        valor_pedido = float(r.total_bruto or 0) - float(r.desconto or 0)
        if valor_pedido < 0:
            valor_pedido = 0.0
        u["valor"] += valor_pedido
        total_geral["valor"] += valor_pedido

    # ordena pela soma de pedidos lançados (decrescente)
    usuarios = sorted(
        resumo.values(),
        key=lambda x: (-x["total_pedidos"], x["nome"].lower()),
    )

    return render_template(
        "admin/relatorio_usuarios.html",
        usuarios=usuarios,
        total_geral=total_geral,
        data_ini=dt_ini.date(),
        data_fim=dt_fim.date(),
    )


# ----------------------------------------------------------------------
# CSV: Pedidos por usuário
# ----------------------------------------------------------------------
@admin_bp.route("/relatorio/usuarios/exportar_csv")
@role_required("admin")
def exportar_relatorio_usuarios_csv():
    data_ini_str = request.args.get("data_ini")
    data_fim_str = request.args.get("data_fim")
    dt_ini, dt_fim = _parse_intervalo(data_ini_str, data_fim_str)

    sub_totais = _subquery_totais_brutos()

    rows = (
        db.session.query(
            Pedido.id,
            Pedido.tipo,
            Pedido.forma_pagamento,
            Pedido.desconto,
            Pedido.garcom_id,
            User.nome.label("usuario_nome"),
            User.role.label("usuario_role"),
            func.coalesce(sub_totais.c.total_bruto, 0).label("total_bruto"),
        )
        .outerjoin(User, User.id == Pedido.garcom_id)
        .outerjoin(sub_totais, sub_totais.c.pedido_id == Pedido.id)
        .filter(Pedido.criado_em >= dt_ini, Pedido.criado_em <= dt_fim)
        .all()
    )

    resumo = {}
    total_geral = {"mesas": 0, "retiradas": 0, "deliveries": 0, "cancelados": 0,
                   "total_pedidos": 0, "valor": 0.0}

    for r in rows:
        chave = r.garcom_id or 0
        if chave not in resumo:
            resumo[chave] = {
                "nome": r.usuario_nome or "(sem usuario)",
                "role": (r.usuario_role or "").upper() if r.usuario_role else "—",
                "mesas": 0, "retiradas": 0, "deliveries": 0,
                "cancelados": 0, "total_pedidos": 0, "valor": 0.0,
            }
        u = resumo[chave]
        cancelado = (r.forma_pagamento or "").lower().strip() == "cancelado"
        u["total_pedidos"] += 1
        total_geral["total_pedidos"] += 1
        if cancelado:
            u["cancelados"] += 1
            total_geral["cancelados"] += 1
            continue
        tipo = (r.tipo or "").lower()
        if tipo == "mesa":
            u["mesas"] += 1; total_geral["mesas"] += 1
        elif tipo == "retirada":
            u["retiradas"] += 1; total_geral["retiradas"] += 1
        elif tipo == "delivery":
            u["deliveries"] += 1; total_geral["deliveries"] += 1
        valor_pedido = float(r.total_bruto or 0) - float(r.desconto or 0)
        if valor_pedido < 0:
            valor_pedido = 0.0
        u["valor"] += valor_pedido
        total_geral["valor"] += valor_pedido

    usuarios = sorted(
        resumo.values(),
        key=lambda x: (-x["total_pedidos"], x["nome"].lower()),
    )

    linhas = ["sep=;",
              "USUARIO;ROLE;MESAS;RETIRADAS;DELIVERIES;CANCELADOS;TOTAL_PEDIDOS;VALOR"]

    for u in usuarios:
        nome = (u["nome"] or "").replace('"', '""')
        valor = f"{u['valor']:.2f}".replace(".", ",")
        linhas.append(
            f"\"{nome}\";{u['role']};{u['mesas']};{u['retiradas']};"
            f"{u['deliveries']};{u['cancelados']};{u['total_pedidos']};{valor}"
        )

    valor_total_f = f"{total_geral['valor']:.2f}".replace(".", ",")
    linhas.append("")
    linhas.append(
        f"\"TOTAL GERAL\";;{total_geral['mesas']};{total_geral['retiradas']};"
        f"{total_geral['deliveries']};{total_geral['cancelados']};"
        f"{total_geral['total_pedidos']};{valor_total_f}"
    )

    csv_data = "\n".join(linhas)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=pedidos_por_usuario_"
                f"{dt_ini.date().isoformat()}_a_{dt_fim.date().isoformat()}.csv"
            )
        }
    )

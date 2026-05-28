from flask import render_template, request, redirect, url_for, jsonify, current_app
from ..models import Pedido, PedidoItem, db, Produto, agora_brasil
from ..utils.decorators import role_required
from ..utils.permissoes import permissao_required
from ..utils.pix import gerar_brcode, gerar_qrcode_base64
from . import admin_bp
from flask_login import current_user
from flask import flash


from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

Q = Decimal("0.01")

def money(v) -> Decimal:
    if v is None:
        return Decimal("0.00")
    s = str(v).strip()
    if not s:
        return Decimal("0.00")

    # mantém só dígitos e separadores
    s = s.replace(" ", "")

    try:
        # Se tem vírgula, assume pt-BR: "." milhar e "," decimal
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            # Se não tem vírgula, assume "." decimal (padrão)
            # (não remove o ponto!)
            pass

        return Decimal(s).quantize(Q, rounding=ROUND_HALF_UP)

    except InvalidOperation:
        return Decimal("0.00")

@admin_bp.route("/pedidos")
@permissao_required("caixa")
def pedidos():

    from datetime import datetime, timedelta, date
    from sqlalchemy import or_

    hoje = date.today()
    inicio = datetime.combine(hoje, datetime.min.time())
    fim = datetime.combine(hoje, datetime.max.time())

    # Mostra:
    #   1) todos os pedidos de hoje (abertos OU fechados)
    #   2) qualquer pedido AINDA aberto de dias anteriores (esquecidos)
    pedidos = (
        Pedido.query
        .filter(
            or_(
                Pedido.criado_em.between(inicio, fim),
                Pedido.pedido_fechado == False,
            )
        )
        .order_by(
            Pedido.pedido_fechado.asc(),   # abertos primeiro
            Pedido.criado_em.asc(),        # mais antigos em cima dentro dos abertos (atrasados topo)
        )
        .all()
    )

    # Pedidos atrasados = abertos com criado_em < hoje 00:00
    atrasados_count = sum(
        1 for p in pedidos
        if (not p.pedido_fechado) and p.criado_em and p.criado_em < inicio
    )

    return render_template(
        "admin/pedidos.html",
        pedidos=pedidos,
        agora=datetime.now(),
        hoje_inicio=inicio,
        atrasados_count=atrasados_count,
    )

@admin_bp.route("/pedido/<int:pedido_id>/cupom")
@permissao_required("caixa")
def cupom(pedido_id):

    pedido = db.session.get(Pedido, pedido_id)
    db.session.refresh(pedido)

    forma = request.args.get("forma")
    valor_entregue = request.args.get("valor_entregue", type=float)

    if forma:
        pedido.forma_pagamento = forma

        if forma == "dinheiro":
            if not valor_entregue:
                flash("Informe o valor entregue pelo cliente.", "warning")
                return redirect(url_for("admin.pedidos"))

            try:
                valor = float(valor_entregue)
            except ValueError:
                flash("Valor entregue inválido.", "warning")
                return redirect(url_for("admin.pedidos"))

            pedido.valor_entregue = valor
            pedido.troco = 0  # 🔧 evita variável inexistente

        elif forma == "bonif":
            # 🔥 BONIFICAÇÃO
            pedido.valor_entregue = 0
            pedido.troco = 0

        else:
            # PIX ou CARTÃO
            pedido.valor_entregue = None
            pedido.troco = None

        db.session.commit()

    # Pix: gera "Copia e Cola" + QR Code se a forma de pagamento for pix
    pix_payload = None
    pix_qrcode = None
    pix_chave = current_app.config.get("PIX_CHAVE", "")
    pix_valor = 0.0

    formas_pagto_pix = (pedido.forma_pagamento == "pix") or (
        getattr(pedido, "forma_pagamento2", None) == "pix"
    )

    if formas_pagto_pix and pix_chave:
        # Define o valor exato cobrado em Pix:
        #   - se pix é a 1ª forma (sem 2ª): valor total final
        #   - se pix é a 2ª forma: valor_pagamento2
        #   - se pix é a 1ª e há outra como 2ª: valor_entregue (registrado pelo caixa)
        try:
            total_final = float(pedido.total_com_desconto())
        except Exception:
            total_final = float(pedido.total() or 0) - float(pedido.desconto or 0)

        if pedido.forma_pagamento == "pix" and not getattr(pedido, "forma_pagamento2", None):
            pix_valor = total_final
        elif pedido.forma_pagamento == "pix":
            pix_valor = float(pedido.valor_entregue or total_final)
        elif getattr(pedido, "forma_pagamento2", None) == "pix":
            pix_valor = float(pedido.valor_pagamento2 or 0)

        if pix_valor > 0:
            try:
                pix_payload = gerar_brcode(
                    chave=pix_chave,
                    nome=current_app.config.get("PIX_NOME", "RECEBEDOR"),
                    cidade=current_app.config.get("PIX_CIDADE", "BRASIL"),
                    valor=pix_valor,
                    txid=f"PED{pedido.id}",
                )
                pix_qrcode = gerar_qrcode_base64(pix_payload)
            except Exception as e:
                current_app.logger.warning(f"Falha ao gerar Pix p/ pedido {pedido.id}: {e}")
                pix_payload = None
                pix_qrcode = None

    # Carimba a 1ª visualização do cupom (só uma vez por pedido).
    # Permite identificar pedidos fechados em que o cupom não foi impresso.
    if pedido.cupom_impresso_em is None:
        pedido.cupom_impresso_em = agora_brasil()
        db.session.commit()

    return render_template(
        "admin/cupom.html",
        pedido=pedido,
        pix_payload=pix_payload,
        pix_qrcode=pix_qrcode,
        pix_valor=pix_valor,
        pix_chave=pix_chave,
    )


@admin_bp.route("/pedido/<int:pedido_id>/pagar", methods=["POST"])
@permissao_required("caixa")
def pagar_pedido(pedido_id):

    pedido = Pedido.query.get_or_404(pedido_id)

    # valores vindos do formulário
    forma = request.form.get("forma_pagamento")
    forma2 = request.form.get("forma_pagamento2")  # <<< NOVO
    pedido.tipo_cartao = request.form.get("tipo_cartao")
    valor_entregue = request.form.get("valor_entregue")
    valor_pagamento2 = request.form.get("valor_pagamento2")  # <<< NOVO
    fechar = request.form.get("fechar")

    # >>> DESCONTO <<<
    desconto = request.form.get("desconto")
    if desconto:
        try:
            pedido.desconto = float(money(desconto))
        except Exception:
            pedido.desconto = 0
    else:
        pedido.desconto = 0

    # ------------------------------------------------------------
    # 1) FECHAR PEDIDO
    # ------------------------------------------------------------
    if fechar == "1":
        pedido.pedido_fechado = True
        pedido.status = "finalizado"

        # Mesa só vira "livre" se não houver outros pedidos abertos nela.
        # Não fecha em cascata os outros pedidos — eles permanecem como estão.
        if pedido.tipo == "mesa" and pedido.mesa_id and pedido.mesa:
            outros_abertos = (
                Pedido.query
                .filter_by(mesa_id=pedido.mesa_id)
                .filter(Pedido.pedido_fechado == False)
                .filter(Pedido.id != pedido.id)
                .count()
            )
            if outros_abertos == 0:
                pedido.mesa.status = "livre"

        db.session.commit()
        flash("Pedido fechado com sucesso!", "info")
        return redirect(url_for("admin.pedidos"))

    # ------------------------------------------------------------
    # 2) PAGAMENTO
    # ------------------------------------------------------------
    if not forma:
        flash("Selecione a forma de pagamento.", "warning")
        return redirect(url_for("admin.pedidos"))

    pedido.forma_pagamento = forma
    pedido.forma_pagamento2 = forma2 if forma2 else None

    # ✅ USE ISSO (evita float escondido)
    total_com_desconto = money(pedido.total_com_desconto())

    valor1 = Decimal("0.00")
    valor2 = Decimal("0.00")

    # PRIMEIRA FORMA
    try:
        valor1 = money(valor_entregue) if valor_entregue else Decimal("0.00")
    except Exception:
        valor1 = Decimal("0.00")

    pedido.valor_entregue = float(valor1)

    # SEGUNDA FORMA
    if forma2:
        try:
            valor2 = money(valor_pagamento2) if valor_pagamento2 else Decimal("0.00")
        except Exception:
            valor2 = Decimal("0.00")

        pedido.valor_pagamento2 = float(valor2)
    else:
        pedido.valor_pagamento2 = 0

    # =========================================================
    # AJUSTE AUTOMÁTICO DE VALORES (quando não for dinheiro)
    # =========================================================

    # ----------------------------------
    # CASO TENHA SOMENTE 1 FORMA
    # ----------------------------------
    if not forma2:

        # DINHEIRO → precisa valor digitado
        if forma == "dinheiro":
            if valor1 < total_com_desconto:
                flash("Valor em dinheiro menor que total.", "warning")
                return redirect(url_for("admin.pedidos"))

        # PIX / CARTÃO / BONIF → assume total automático
        else:
            valor1 = total_com_desconto
            pedido.valor_entregue = float(valor1)

    # ----------------------------------
    # CASO TENHA 2 FORMAS
    # ----------------------------------
    else:

        # Se forma1 não é dinheiro e não digitou valor
        if forma != "dinheiro" and valor1 == Decimal("0.00"):
            valor1 = (total_com_desconto - valor2).quantize(Q, rounding=ROUND_HALF_UP)
            pedido.valor_entregue = float(valor1)

        # Se forma2 não é dinheiro e não digitou valor
        if forma2 != "dinheiro" and valor2 == Decimal("0.00"):
            valor2 = (total_com_desconto - valor1).quantize(Q, rounding=ROUND_HALF_UP)
            pedido.valor_pagamento2 = float(valor2)

        total_pago = (valor1 + valor2).quantize(Q, rounding=ROUND_HALF_UP)

        if total_pago < total_com_desconto:
            flash("Soma dos pagamentos menor que o total.", "warning")
            return redirect(url_for("admin.pedidos"))

    # =========================================================
    # TROCO
    # =========================================================
    total_pago = (valor1 + valor2).quantize(Q, rounding=ROUND_HALF_UP)

    if forma == "dinheiro" or forma2 == "dinheiro":
        pedido.troco = float((total_pago - total_com_desconto).quantize(Q, rounding=ROUND_HALF_UP))
    else:
        pedido.troco = 0

    db.session.commit()
    return redirect(url_for("admin.cupom", pedido_id=pedido.id))
# ================================
# ⭐ NOVO — SALVAR NFE VIA AJAX
# ================================
@admin_bp.route("/pedido/<int:pedido_id>/nfe", methods=["POST"])
@role_required("caixa", "admin")
def atualizar_nfe(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    data = request.get_json()

    marcado = data.get("nfe_emitida", False)
    pedido.nfe_emitida = bool(marcado)

    db.session.commit()

    return jsonify({"success": True, "nfe_emitida": pedido.nfe_emitida})

@admin_bp.route("/pedido/<int:pedido_id>/fechar", methods=["POST"])
@permissao_required("caixa")
def fechar_pedido(pedido_id):

    pedido = Pedido.query.get_or_404(pedido_id)
    
    # 🔴 valida forma de pagamento
    if not pedido.forma_pagamento or pedido.forma_pagamento.strip() == "":
        return jsonify({
            "success": False,
            "erro": "Defina a forma de pagamento antes de fechar o pedido."
        }), 400

    # Fecha o pedido atual
    pedido.pedido_fechado = True
    pedido.status = "finalizado"

    # Mesa só vira "livre" se não houver outros pedidos abertos nela.
    # Não fecha em cascata os outros pedidos — cada um é tratado isoladamente.
    if pedido.tipo == "mesa" and pedido.mesa_id and pedido.mesa:
        outros_abertos = (
            Pedido.query
            .filter_by(mesa_id=pedido.mesa_id)
            .filter(Pedido.pedido_fechado == False)
            .filter(Pedido.id != pedido.id)
            .count()
        )
        if outros_abertos == 0:
            pedido.mesa.status = "livre"

    db.session.commit()

    return jsonify({"success": True})

@admin_bp.route("/pedido/<int:pedido_id>/forcar-finalizacao", methods=["POST"])
@role_required("admin")
def forcar_finalizacao_pedido(pedido_id):
    """
    Admin força a finalização APENAS do pedido informado.
    Marca como 'cancelado' (não entra nos relatórios) e libera a mesa
    SOMENTE se não houver outros pedidos abertos legítimos na mesma mesa.
    Não toca em outros pedidos da mesma mesa — cada um precisa ser tratado
    individualmente, evitando cancelamento em cascata acidental.
    """
    pedido = Pedido.query.get_or_404(pedido_id)
    motivo = (request.form.get("motivo") or "").strip()

    pedido.pedido_fechado = True
    pedido.status = "finalizado"
    pedido.forma_pagamento = "cancelado"
    pedido.forma_pagamento2 = None
    pedido.valor_entregue = 0
    pedido.valor_pagamento2 = 0
    pedido.troco = 0
    pedido.desconto = 0

    # Mesa só é liberada se não houver mais nenhum pedido aberto nela.
    # Se houver outro aberto, ele continua e a mesa permanece ocupada.
    if pedido.tipo == "mesa" and pedido.mesa_id and pedido.mesa:
        outros_abertos = (
            Pedido.query
            .filter_by(mesa_id=pedido.mesa_id)
            .filter(Pedido.pedido_fechado == False)
            .filter(Pedido.id != pedido.id)
            .count()
        )
        if outros_abertos == 0:
            pedido.mesa.status = "livre"

    db.session.commit()

    extra = f" Motivo: {motivo}" if motivo else ""
    flash(f"Pedido #{pedido.id} finalizado pelo admin (não conta em relatório).{extra}", "success")
    return redirect(url_for("admin.pedidos"))


@admin_bp.route("/pedido/<int:pedido_id>/cancelar", methods=["POST"])
@permissao_required("caixa")
def cancelar_pedido(pedido_id):
    """
    Cancela um pedido de RETIRADA ou DELIVERY que não vai ser entregue
    (cliente desistiu, etc.). Pedidos de mesa não usam essa rota — usam
    a função "Liberar mesa" no menu de mesas.
    """
    pedido = Pedido.query.get_or_404(pedido_id)

    if pedido.tipo == "mesa":
        flash("Pedidos de mesa devem ser tratados via 'Liberar mesa'.", "warning")
        return redirect(url_for("admin.pedidos"))

    if pedido.pedido_fechado:
        flash("Pedido já está fechado.", "warning")
        return redirect(url_for("admin.pedidos"))

    motivo = (request.form.get("motivo") or "").strip()

    pedido.pedido_fechado = True
    pedido.status = "finalizado"
    pedido.forma_pagamento = "cancelado"
    pedido.forma_pagamento2 = None
    pedido.valor_entregue = 0
    pedido.valor_pagamento2 = 0
    pedido.troco = 0
    pedido.desconto = 0

    db.session.commit()

    extra = f" Motivo: {motivo}" if motivo else ""
    flash(f"Pedido #{pedido.id} cancelado (não conta em relatório).{extra}", "success")
    return redirect(url_for("admin.pedidos"))


@admin_bp.route("/mesa/<int:mesa_id>/liberar", methods=["POST"])
@role_required("admin")
def liberar_mesa(mesa_id):
    """
    Admin libera a mesa esquecida: marca o(s) pedido(s) aberto(s) como FINALIZADO
    (não cancelado) e libera a mesa. A forma de pagamento e demais valores são
    preservados — o pedido entra no relatório na data em que foi criado.
    """
    from ..models import Mesa
    mesa = Mesa.query.get_or_404(mesa_id)

    abertos = (
        Pedido.query
        .filter_by(mesa_id=mesa.id)
        .filter(Pedido.pedido_fechado == False)
        .all()
    )

    for p in abertos:
        p.pedido_fechado = True
        p.status = "finalizado"
        # Mantém forma_pagamento, valor_entregue, desconto etc. exatamente como estavam
        # — pedido entra normalmente no relatório do dia em que foi criado.

    mesa.status = "livre"
    db.session.commit()

    qtd = len(abertos)
    if qtd:
        flash(
            f"Mesa {mesa.numero} liberada — {qtd} pedido(s) finalizado(s) "
            f"(continua(m) no relatório do dia em que foi(ram) lançado(s)).",
            "success"
        )
    else:
        flash(f"Mesa {mesa.numero} liberada.", "success")

    next_url = request.form.get("next") or url_for("public.mesas")
    return redirect(next_url)


@admin_bp.route("/pedido/<int:pedido_id>/editar-caixa", methods=["GET", "POST"])
@permissao_required("caixa")
def editar_caixa(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    # 🔒 Bloqueia edição se pedido estiver fechado e NÃO for admin
    if pedido.pedido_fechado and current_user.role != "admin":
        flash("Pedido fechado não pode ser editado.", "warning")
        return redirect(url_for("admin.pedidos"))

    if request.method == "POST":
        if "remover_item" in request.form:
            item_id = int(request.form.get("remover_item"))
            item = PedidoItem.query.get(item_id)
            if item:
                db.session.delete(item)

        elif "salvar" in request.form:
            for item in pedido.itens:
                campo = f"qtd_{item.id}"
                if campo in request.form:
                    try:
                        item.quantidade = int(request.form[campo])
                    except ValueError:
                        pass

        db.session.commit()
        return redirect(url_for("admin.editar_caixa", pedido_id=pedido.id))

    # 🔽 BUSCA DIRETA NA TABELA PRODUTOS
    produtos = Produto.query.order_by(Produto.nome).all()

    return render_template(
        "admin/editar_caixa.html",
        pedido=pedido,
        produtos=produtos
    )

@admin_bp.route("/pedido/<int:pedido_id>/adicionar-produto", methods=["POST"])
@role_required("admin", "garcom")
def adicionar_produto_caixa(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    data = request.get_json()

    produto_id = data.get("produto_id")
    quantidade = data.get("quantidade", 1)

    try:
        quantidade = int(quantidade)
        if quantidade < 1:
            quantidade = 1
    except:
        quantidade = 1

    if not produto_id:
        return jsonify({"success": False, "error": "Produto inválido"})

    produto = Produto.query.get(produto_id)
    if not produto:
        return jsonify({"success": False, "error": "Produto não encontrado"})

    # Verifica se produto já existe no pedido
    item_existente = PedidoItem.query.filter_by(
        pedido_id=pedido.id,
        produto_id=produto.id
    ).first()

    if item_existente:
        # Soma quantidade
        item_existente.quantidade += quantidade
    else:
        # Cria novo item
        novo_item = PedidoItem(
            pedido_id=pedido.id,
            produto_id=produto.id,
            quantidade=quantidade
        )
        db.session.add(novo_item)

    db.session.commit()

    return jsonify({"success": True})


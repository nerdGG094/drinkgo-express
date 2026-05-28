from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from ..models import db, Mesa, Produto, Pedido, PedidoItem, Cliente, agora_brasil
from ..sockets import emit_novo_pedido
from ..utils.decorators import role_required
from . import public_bp
from collections import defaultdict
from ..models import Categoria
from datetime import datetime
from flask_login import login_required
from ..models import Produto

#---------------------------------------- BACKEND PEDIDOS ----------------------------------------------
@public_bp.route("/novo")
@role_required("garcom", "caixa", "admin")
def novo():
    return render_template("public/tipo_pedido.html")

@public_bp.route("/mesas")
@role_required("garcom", "caixa", "admin")
def mesas():
    # QUANTIDADE A EXIBIR (DEFAULT = 5 SE NÃO INFORMADO)
    qtd = request.args.get("qtd", default=5, type=int)
    # CARREGA TODAS AS MESAS ATIVAS
    mesas_raw = Mesa.query.filter_by(ativa=True).all()
    # ORDENA NUMERICAMENTE
    mesas_ordenadas = sorted(mesas_raw, key=lambda m: int(m.numero))
    # APLICA LIMITE SOLICITADO
    mesas_limitadas = mesas_ordenadas[:qtd]

    # ADICIONADO POR PRIMO SPINELLI 20032026 PARA EXIBIR GARÇOM QUE ESTA SEGURANDO A MESA
    for mesa in mesas_limitadas:
        mesa.pedido_aberto = Pedido.query.filter(
            Pedido.mesa_id == mesa.id,
            Pedido.status.in_(["aberto", "recebido"]),
            Pedido.pedido_fechado == False
        ).first()
    return render_template("public/mesas.html", mesas=mesas_limitadas)

#ROTA PARA CONTROLE DE ACESSO DE MESAS OCUPADAS
@public_bp.route("/mesa/<int:mesa_id>")
@role_required("garcom", "caixa", "admin")
def acessar_mesa(mesa_id):
    mesa = Mesa.query.get_or_404(mesa_id)

    # Busca TODOS os pedidos abertos da mesa (em ordem de criação).
    # Se houver mais de 1 = duplicata por toque-duplo / corrida no GET.
    # Mantém o mais antigo, migra itens dos demais e apaga os duplicados.
    pedidos_abertos = (
        Pedido.query
        .filter(
            Pedido.mesa_id == mesa.id,
            Pedido.status.in_(["aberto", "recebido"]),
            Pedido.pedido_fechado == False,
        )
        .order_by(Pedido.criado_em.asc(), Pedido.id.asc())
        .all()
    )

    if pedidos_abertos:
        pedido = pedidos_abertos[0]

        # Mescla duplicatas (caso tenham sido criadas em corrida)
        if len(pedidos_abertos) > 1:
            for dup in pedidos_abertos[1:]:
                for item in list(dup.itens):
                    item.pedido_id = pedido.id
                db.session.delete(dup)
            db.session.commit()

        # BLOQUEIA OUTRO GARÇOM
        if pedido.garcom_id != current_user.id:
            flash("⚠️ Essa mesa já está sendo atendida por outro garçom!", "danger")
            return redirect(url_for("public.mesas"))

        # MESMO GARÇOM → ACESSA NORMALMENTE
        return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

    # SE NÃO EXISTE → CRIA
    pedido = Pedido(
        mesa_id=mesa.id,
        tipo="mesa",
        status="aberto",
        garcom_id=current_user.id
    )

    mesa.status = "ocupada"
    db.session.add(pedido)
    db.session.commit()

    # Após o commit, re-checa: se outra requisição concorrente também criou
    # um pedido nesse intervalo, mescla agora para deixar só um.
    concorrentes = (
        Pedido.query
        .filter(
            Pedido.mesa_id == mesa.id,
            Pedido.status.in_(["aberto", "recebido"]),
            Pedido.pedido_fechado == False,
            Pedido.id != pedido.id,
        )
        .order_by(Pedido.criado_em.asc(), Pedido.id.asc())
        .all()
    )
    if concorrentes:
        # Mantém o mais antigo entre todos
        candidatos = sorted(
            [pedido] + concorrentes,
            key=lambda p: (p.criado_em, p.id),
        )
        principal = candidatos[0]
        for dup in candidatos[1:]:
            for item in list(dup.itens):
                item.pedido_id = principal.id
            db.session.delete(dup)
        db.session.commit()
        return redirect(url_for("public.cardapio_pedido", pedido_id=principal.id))

    return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

#ROTA PARA O FECHAMENTO DAS MESAS
@public_bp.route("/mesa/<int:mesa_id>/fechar", methods=["POST", "GET"])
@role_required("garcom", "caixa", "admin")
def fechar_mesa(mesa_id):
    mesa = Mesa.query.get_or_404(mesa_id)

    pedido = Pedido.query.filter(
        Pedido.mesa_id == mesa.id,
        Pedido.status.in_(["aberto", "recebido"]),
        Pedido.pedido_fechado == False
    ).first()

    if not pedido:
        flash("Nenhum pedido aberto nessa mesa.", "warning")
        return redirect(url_for("public.mesas"))

    #FINALIZA O PEDIDO
    pedido.status = "finalizado"
    pedido.pedido_fechado = True

    # FAZ A LIBERAÇÃO DA MESA
    mesa.status = "livre"
    db.session.commit()
    return redirect(url_for("public.mesas"))

# ROTA PARA TIPO DE PEDIDO RETIRADA NO LOCAL
@public_bp.route("/retirada", methods=["GET", "POST"])
@role_required("garcom", "caixa", "admin")
def retirada():

    if request.method == "POST":
        cod = request.form.get("codigo")
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        endereco = request.form.get("endereco")
        obs = request.form.get("obs")

        # ===============================
        # CLIENTE
        # ===============================
        cliente = None
        if cod:
            cliente = Cliente.query.filter_by(codigo=cod, ativo=True).first()

        if not cliente and nome:
            cliente = Cliente.query.filter(
                Cliente.nome.ilike(f"%{nome}%"),
                Cliente.ativo == True
            ).first()

        if not cliente:
            if not nome:
                flash("Informe o cliente.", "warning")
                return redirect(url_for("public.retirada"))

            cliente = Cliente(
                codigo=cod or None,
                nome=nome,
                telefone=telefone,
                endereco=endereco,
                obs=obs
            )
            db.session.add(cliente)
            db.session.flush()  # garante cliente.id
        else:
            if telefone:
                cliente.telefone = telefone
            if endereco:
                cliente.endereco = endereco
            if obs:
                cliente.obs = obs

        # ===============================
        # PEDIDO (CRIAÇÃO CORRETA)
        # ===============================
        novo_pedido = Pedido(
            tipo="retirada",
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            cliente_telefone=cliente.telefone,
            endereco=cliente.endereco,
            garcom_id=current_user.id if current_user.is_authenticated else None,
            criado_em=agora_brasil()
        )

        db.session.add(novo_pedido)
        db.session.commit()
        return redirect(
            url_for(
                "public.cardapio_pedido",
                pedido_id=novo_pedido.id
            )
        )
    return render_template("public/retirada.html")

# ROTA DE TIPO DE PEDIDO DELIVERY
@public_bp.route("/delivery", methods=["GET", "POST"])
@role_required("garcom", "caixa", "admin")
def delivery():
    if request.method == "POST":
        cod = request.form.get("codigo")
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        endereco = request.form.get("endereco")
        obs = request.form.get("obs")

        cliente = None
        if cod:
            cliente = Cliente.query.filter_by(codigo=cod, ativo=True).first()
        if not cliente and nome:
            cliente = Cliente.query.filter(Cliente.nome.ilike(f"%{nome}%"), Cliente.ativo == True).first()

        if not cliente:
            if not (nome and endereco):
                flash("Informe o endereço", "warning")
                return redirect(url_for("public.delivery"))
            cliente = Cliente(codigo=cod or None, nome=nome, telefone=telefone, endereco=endereco, obs=obs)
            db.session.add(cliente)
            db.session.flush()
        else:
            if telefone: cliente.telefone = telefone
            if endereco: cliente.endereco = endereco
            if obs: cliente.obs = obs

        pedido = Pedido(
            tipo="delivery",
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            cliente_telefone=cliente.telefone,
            endereco=cliente.endereco,
            garcom_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(pedido)
        db.session.commit()
        return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

    return render_template("public/delivery.html")

#ROTA PARA O CARDAPIO PÓS INFORMAR TIPO DE PEDIDO
@public_bp.route("/pedido/<int:pedido_id>/cardapio", methods=["GET", "POST"])
@role_required("garcom", "caixa", "admin")
def cardapio_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    mesa = pedido.mesa

    # ================= NOVO AGRUPAMENTO =================
    produtos_db = db.session.query(
        Produto,
        Categoria.nome
    ).join(
        Categoria, Categoria.id == Produto.categoria_id
    ).filter(
        Produto.ativo == True,
        Categoria.ativo == True
    ).order_by(
        Categoria.nome,
        Produto.nome
    ).all()

    categorias = defaultdict(list)

    for prod, nome_categoria in produtos_db:
        categorias[nome_categoria].append(prod)

    # ================= POST =================
    if request.method == "POST":
        itens = _coletar_itens_form(request.form)
        if not itens:
            flash("Informe ao menos 1 item.", "warning")
            return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

        for produto, qtd in itens:
            db.session.add(PedidoItem(pedido_id=pedido.id, produto_id=produto.id, quantidade=qtd))

        db.session.commit()
        emit_novo_pedido(pedido.id)
        return redirect(url_for("public.pedido_enviado", pedido_id=pedido.id))
    return render_template("public/cardapio.html", pedido=pedido, mesa=mesa, categorias=categorias)

#ROTA DE ENVIO DO PEDIDO
@public_bp.route("/pedido/<int:pedido_id>/enviado")
@role_required("garcom", "caixa", "admin")
def pedido_enviado(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("public/pedido_enviado.html", pedido=pedido)

def _coletar_itens_form(form):

    itens = []
    for key, value in form.items():
        if key.startswith("prod_") and value:
            try:
                qtd = int(value)
            except ValueError:
                continue
            if qtd <= 0:
                continue
            prod_id = int(key.split("_")[1])
            produto = Produto.query.get(prod_id)
            if produto:
                itens.append((produto, qtd))
    return itens

@public_bp.route("/pedido/<int:pedido_id>/editar", methods=["GET", "POST"])
@login_required
def editar_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if pedido.status != "aberto":
        flash("Pedido já fechado, não pode ser editado.", "error")
        return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

    if request.method == "POST":
        for item in pedido.itens:
            nova_qtd = int(request.form.get(f"item_{item.id}", item.quantidade))

            if nova_qtd <= 0:
                db.session.delete(item)
            else:
                item.quantidade = nova_qtd

        db.session.commit()
        flash("Pedido atualizado com sucesso!", "success")
        return redirect(url_for("public.cardapio_pedido", pedido_id=pedido.id))

    return render_template("public/editar_pedido.html", pedido=pedido)

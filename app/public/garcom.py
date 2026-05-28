from flask import render_template, request
from flask_login import current_user
from ..models import Pedido
from ..utils.decorators import role_required
from . import public_bp
from datetime import datetime, date, time

@public_bp.route("/pedidos")
@role_required("garcom", "caixa", "admin")
def pedidos_garcom():

    data_filtro = request.args.get("data")

    # SE NÃO OBTER O FILTRO DE DATA ELE MANTEM DA DATA  ATUAL A CONSULTA DOS PEDIDOS DO GARÇOM
    if data_filtro:
        try:
            data = datetime.strptime(data_filtro, "%Y-%m-%d").date()
        except:
            data = date.today()
    else:
        data = date.today()

    inicio = datetime.combine(data, time.min)
    fim = datetime.combine(data, time.max)

    # Admin: vê todos os pedidos do dia (de qualquer usuário que lançou).
    # Garçom / caixa: veem apenas os pedidos que eles mesmos lançaram.
    query = Pedido.query.filter(
        Pedido.criado_em >= inicio,
        Pedido.criado_em <= fim,
    )
    if current_user.role != "admin":
        query = query.filter(Pedido.garcom_id == current_user.id)

    pedidos = query.order_by(Pedido.criado_em.desc()).all()

    return render_template(
        "public/pedidos_garcom.html",
        pedidos=pedidos,
        data_filtro=data_filtro
    )
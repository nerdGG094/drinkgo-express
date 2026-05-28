from flask import render_template
from ..models import Pedido
from ..utils.decorators import role_required
from . import public_bp

@public_bp.route("/pedido/<int:pedido_id>/status")
@role_required("garcom", "caixa", "admin")
def status_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("public/status_pedido.html", pedido=pedido)

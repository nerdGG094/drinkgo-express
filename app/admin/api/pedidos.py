from flask import request, jsonify
from ...models import db, Pedido
from ...sockets import emit_status_pedido
from ...utils.decorators import role_required
from . import admin_api_bp

@admin_api_bp.route("/pedido/<int:pedido_id>/status", methods=["POST"])
@role_required("caixa", "admin")
def atualizar_status(pedido_id):
    novo_status = request.json.get("status")
    pedido = Pedido.query.get_or_404(pedido_id)
    pedido.status = novo_status
    db.session.commit()
    emit_status_pedido(pedido.id, novo_status)
    return jsonify({"ok": True})

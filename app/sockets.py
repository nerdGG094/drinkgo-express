from flask_socketio import SocketIO

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="threading"
)

def emit_novo_pedido(pedido_id):
    socketio.emit(
        "novo_pedido",
        {"pedido_id": pedido_id},
        namespace="/admin"
    )
    socketio.emit(
        "novo_pedido",
        {"pedido_id": pedido_id},
        namespace="/public"
    )

def emit_status_pedido(pedido_id, status):
    socketio.emit(
        "status_atualizado",
        {"pedido_id": pedido_id, "status": status},
        namespace="/admin"
    )
    socketio.emit(
        "status_atualizado",
        {"pedido_id": pedido_id, "status": status},
        namespace="/public"
    )

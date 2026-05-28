from app import create_app
from app.models import Pedido

app = create_app()

with app.app_context():
    p = Pedido.query.order_by(Pedido.id.desc()).first()
    print("ID:", p.id)
    print("DESCONTO NO BANCO =", p.desconto)

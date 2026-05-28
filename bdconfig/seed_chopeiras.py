from app import create_app, db
from app.models import Chopeira

app = create_app()

CHOPEIRAS_NUMEROS = [
    # Grupo 1
    142,143,144,145,146,147,148,149,150,155,156,157,158,153,160,161,162,
    171,172,173,174,175,176,177,178,179,180,181,182,191,192,

    # Grupo 2
    163,164,165,167,168,169,170,183,184,185,186,187,188,189,190,193,194,
    195,196,152,154,132,133,134,135,136,137,151
]

with app.app_context():

    existentes = {c.numero for c in Chopeira.query.all()}

    adicionadas = 0

    for numero in CHOPEIRAS_NUMEROS:
        if numero not in existentes:
            nova = Chopeira(numero=numero, status="disponivel")
            db.session.add(nova)
            adicionadas += 1

    db.session.commit()

    print(f"✅ {adicionadas} chopeiras adicionadas com sucesso!")

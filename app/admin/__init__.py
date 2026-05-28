from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates"
)

from . import dashboard, pedidos, relatorios, usuarios, clientes, produtos, entradas, chopeiras, bonif_relatorio, inventario, configuracao

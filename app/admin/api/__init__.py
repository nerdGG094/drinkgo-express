from flask import Blueprint

admin_api_bp = Blueprint("admin_api", __name__)

from . import pedidos

"""
Registro central de permissões controláveis pelo admin.

Cada permissão tem:
  - key: identificador estável usado no banco e nos templates
  - label: nome amigável
  - desc: descrição curta
  - icon: emoji p/ UI
  - endpoints: tuple de endpoints Flask que essa permissão libera

A permissão "admin" é especial: usuários com role "admin" sempre têm tudo,
independentemente do que está na coluna `permissoes`.
"""

from flask_login import current_user


PERMISSOES = [
    {
        "key": "dashboard",
        "label": "Dashboard",
        "desc": "Visão geral, KPIs e gráficos do dia",
        "icon": "📊",
        "endpoints": ("admin.dashboard",),
    },
    {
        "key": "caixa",
        "label": "Caixa",
        "desc": "Pedidos do dia, fechar, cobrar e imprimir cupom",
        "icon": "🧾",
        "endpoints": (
            "admin.pedidos",
            "admin.cupom",
            "admin.pagar_pedido",
            "admin.editar_caixa",
        ),
    },
    {
        "key": "relatorios",
        "label": "Relatórios",
        "desc": "Itens vendidos, bonificações e exportações",
        "icon": "📈",
        "endpoints": (
            "admin.relatorio_itens",
            "admin.bonif_relatorio_itens",
            "admin.exportar_relatorio_csv",
            "admin.exportar_relatorio_csv_bonif",
        ),
    },
    {
        "key": "produtos",
        "label": "Produtos & Categorias",
        "desc": "Cadastrar, editar e organizar o cardápio",
        "icon": "📦",
        "endpoints": (
            "admin.produtos",
            "admin.produtos_novo",
            "admin.produtos_editar",
            "admin.categoria_novo",
        ),
    },
    {
        "key": "chopeiras",
        "label": "Aluguel de Chopeiras",
        "desc": "Locação, devolução e relatório de chopeiras",
        "icon": "🍺",
        "endpoints": (
            "admin.chopeiras",
            "admin.alugar_chopeira",
            "admin.detalhes_chopeira",
            "admin.retornar_chopeira",
            "admin.relatorio_chopeiras_alugadas",
        ),
    },
    {
        "key": "entradas",
        "label": "Entrada de Produtos",
        "desc": "Registro manual de entradas no estoque",
        "icon": "📥",
        "endpoints": ("admin.entrada_produtos",),
    },
    {
        "key": "inventario",
        "label": "Inventário (contagem)",
        "desc": "Contagem geral diária — itens operacionais e produtos do cardápio",
        "icon": "🗃️",
        "endpoints": (
            "admin.inventario",
            "admin.inventario_item",
            "admin.inventario_produto",
            "admin.inventario_novo",
            "admin.inventario_editar",
            "admin.inventario_contar",
            "admin.inventario_item_contagem_rapida",
            "admin.inventario_produto_contagem_rapida",
            "admin.inventario_excluir_contagem",
            "admin.inventario_seed_padrao",
            "admin.inventario_relatorio",
            "admin.inventario_relatorio_excel",
        ),
    },
    {
        "key": "novo_pedido",
        "label": "Novo Pedido",
        "desc": "Abrir pedidos por mesa, retirada ou delivery",
        "icon": "➕",
        "endpoints": (
            "public.novo",
            "public.mesas",
            "public.retirada",
            "public.delivery",
            "public.cardapio",
            "public.acessar_mesa",
        ),
    },
]

PERMISSOES_BY_KEY = {p["key"]: p for p in PERMISSOES}


# Defaults por role quando o usuário ainda não tem permissões customizadas (NULL no banco)
DEFAULTS_POR_ROLE = {
    "admin":  [p["key"] for p in PERMISSOES],  # tudo
    "caixa":  ["dashboard", "caixa", "relatorios", "produtos", "chopeiras", "entradas", "novo_pedido", "inventario"],
    "garcom": ["caixa", "entradas", "novo_pedido"],
}


def permissoes_default_por_role(role: str) -> list[str]:
    return list(DEFAULTS_POR_ROLE.get((role or "").lower(), []))


def usuario_tem_permissao(user, key: str) -> bool:
    """Admin sempre passa; demais checam a lista do usuário."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = (getattr(user, "role", "") or "").lower()
    if role == "admin":
        return True
    perms = user.permissoes_efetivas() if hasattr(user, "permissoes_efetivas") else []
    return key in perms


def permissao_required(key: str):
    """
    Decorator de view: exige que o usuário tenha a permissão `key`.
    Admin sempre passa. Faz login_required implícito (via decorators existentes).
    """
    from functools import wraps
    from flask import abort
    from flask_login import login_required

    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if not usuario_tem_permissao(current_user, key):
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

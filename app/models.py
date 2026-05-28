from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash
import pytz
import json
from decimal import Decimal, ROUND_HALF_UP

def agora_brasil():
        return datetime.now(pytz.timezone("America/Sao_Paulo"))
    
db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="garcom")  # garcom, caixa, admin
    ativo = db.Column(db.Boolean, default=True)
    foto = db.Column(db.String(255))  # nome do arquivo em uploads/usuarios/

    # JSON com a lista de permissões customizadas. NULL = usa defaults do role.
    permissoes_json = db.Column(db.Text, nullable=True)

    # ---------------- helpers de permissão ----------------
    def get_permissoes(self):
        """Lista de chaves armazenadas. Retorna None se nunca foi customizado."""
        if self.permissoes_json is None:
            return None
        try:
            data = json.loads(self.permissoes_json)
            return list(data) if isinstance(data, (list, tuple)) else None
        except Exception:
            return None

    def set_permissoes(self, lista):
        """Salva a lista (sem validação — quem chama valida com o registry)."""
        if lista is None:
            self.permissoes_json = None
        else:
            self.permissoes_json = json.dumps(sorted(set(lista)))

    def permissoes_efetivas(self):
        """
        Retorna a lista de chaves que o usuário tem na prática.
        - admin: registro completo do registry (não bloqueável)
        - demais: a lista customizada se houver, senão default do role
        """
        from .utils.permissoes import (
            PERMISSOES_BY_KEY,
            permissoes_default_por_role,
        )
        role = (self.role or "").lower()
        if role == "admin":
            return list(PERMISSOES_BY_KEY.keys())
        custom = self.get_permissoes()
        if custom is None:
            return permissoes_default_por_role(role)
        return custom

    def tem_permissao(self, key):
        from .utils.permissoes import usuario_tem_permissao
        return usuario_tem_permissao(self, key)

class Mesa(db.Model):
    __tablename__ = "mesas"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), nullable=False, unique=True)
    ativa = db.Column(db.Boolean, default=True)

    status = db.Column(db.String(20), default="livre")  # livre / ocupada

    def __repr__(self):
        return f"<Mesa {self.numero}>"

class Cliente(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(255))
    obs = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    __tablename__ = "pedidos"
    id = db.Column(db.Integer, primary_key=True)
    mesa_id = db.Column(db.Integer, db.ForeignKey("mesas.id"), nullable=True)

    tipo = db.Column(db.String(20), nullable=False, default="mesa")  
    # mesa / retirada / delivery

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    garcom_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    cliente_nome = db.Column(db.String(120))
    cliente_telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(255))

    status = db.Column(db.String(20), default="recebido")

    criado_em = db.Column(db.DateTime, default=agora_brasil)
    
    forma_pagamento = db.Column(db.String(20), nullable=False)  # dinheiro, pix, cartao
    forma_pagamento2 = db.Column(db.String(20))  # segunda forma
    tipo_cartao = db.Column(db.String(10))  # tipo de cartão crédito ou débito
    valor_entregue = db.Column(db.Float)
    valor_pagamento2 = db.Column(db.Float, default=0)
    troco = db.Column(db.Float)

    desconto = db.Column(db.Float, default=0) 

    # NOVA COLUNA — NFE EMITIDA
    nfe_emitida = db.Column(db.Boolean, default=False)

    # NOVA COLUNA — PEDIDO FECHADO
    pedido_fechado = db.Column(db.Boolean, default=False)

    # Quando o cupom (recibo) foi visualizado/impresso pela primeira vez.
    # NULL = ainda não foi impresso. Permite identificar pedidos fechados sem
    # cupom impresso e bater com o conferimento físico no fim do dia.
    cupom_impresso_em = db.Column(db.DateTime)

    mesa = db.relationship("Mesa", backref="pedidos")
    cliente = db.relationship("Cliente", backref="pedidos")
    garcom = db.relationship("User")

    def total(self):
        total = Decimal("0.00")

        for item in self.itens:
            preco = Decimal(str(item.produto.preco)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            qtd = Decimal(str(item.quantidade))
            total += (preco * qtd)

        return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def total_com_desconto(self):
        total = Decimal(str(self.total()))
        desc = Decimal(str(self.desconto or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        final = (total - desc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if final < Decimal("0.00"):
            final = Decimal("0.00")
        return float(final)

class PedidoItem(db.Model):
    __tablename__ = "pedido_itens"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    observacao = db.Column(db.String(200))

    pedido = db.relationship("Pedido", backref="itens")
    produto = db.relationship("Produto")

    def subtotal(self):
        preco = Decimal(str(self.produto.preco)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qtd = Decimal(str(self.quantidade))
        return float((preco * qtd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def seed_if_empty():
    """Cria mesas, produtos, usuários e clientes de exemplo se o banco estiver vazio."""
    if Mesa.query.count() == 0:
        for i in range(1, 11):
            db.session.add(Mesa(numero=str(i)))
            
    # CHOPEIRAS
    if Chopeira.query.count() == 0:
        for i in range(1, 11):
            db.session.add(Chopeira(numero=i))


    #if User.query.count() == 0:
        #garcom = User(
            #nome="Garçom",
            #email="garcom@local",
            #senha_hash=generate_password_hash("123"),
            #role="garcom",
        #)
        #caixa = User(
            #nome="Caixa",
            #email="caixa@local",
            #senha_hash=generate_password_hash("123"),
            #role="caixa",
        #)
        #admin = User(
            #nome="Admin",
            #email="admin@local",
            #senha_hash=generate_password_hash("123"),
            #role="admin",
        #)
        #db.session.add_all([garcom, caixa, admin])

    #db.session.commit()


class EntradaProduto(db.Model):
    __tablename__ = "entrada_produtos"

    id = db.Column(db.Integer, primary_key=True)

    produto_nome = db.Column(db.String(150), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.Text)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario = db.relationship("User")

    criado_em = db.Column(db.DateTime, default=agora_brasil)

class Chopeira(db.Model):
    __tablename__ = "chopeiras"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False, unique=True)

    status = db.Column(
        db.String(20),
        default="disponivel"
    )  # disponivel | alugada

    def __repr__(self):
        return f"<Chopeira {self.numero}>"


class AluguelChopeira(db.Model):
    __tablename__ = "aluguel_chopeiras"

    id = db.Column(db.Integer, primary_key=True)

    # ===============================
    # RELAÇÃO COM CHOPEIRA
    # ===============================
    chopeira_id = db.Column(
        db.Integer,
        db.ForeignKey("chopeiras.id"),
        nullable=False
    )
    chopeira = db.relationship("Chopeira", backref="alugueis")

    # ===============================
    # DADOS DO CLIENTE
    # ===============================
    cliente_nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(255))

    # ===============================
    # DATAS
    # ===============================
    data_saida = db.Column(db.DateTime, default=agora_brasil)
    data_retorno = db.Column(db.DateTime)

    # ===============================
    # STATUS DA LOCAÇÃO
    # ===============================
    status = db.Column(db.String(20), default="alugado")
    # valores esperados: alugado | devolvido

    # ===============================
    # USUÁRIO DO SISTEMA
    # ===============================
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id")
    )
    usuario = db.relationship("User")

    # ===============================
    # EQUIPAMENTOS OPCIONAIS
    # ===============================
    alugou_co2 = db.Column(db.Boolean, default=False)
    keg_tipo = db.Column(db.String(10))
    alugou_manometro = db.Column(db.Boolean, default=False)
    alugou_pingadeira = db.Column(db.Boolean, default=False)

    # ===============================
    # MÉTODOS ÚTEIS
    # ===============================
    @property
    def ativo(self):
        """Retorna True se a locação estiver ativa"""
        return self.status == "alugado" and self.data_retorno is None

    def finalizar(self):
        """Finaliza a locação"""
        self.status = "devolvido"
        self.data_retorno = agora_brasil()

    def __repr__(self):
        return f"<AluguelChopeira chopeira={self.chopeira_id} cliente='{self.cliente_nome}' status={self.status}>"


class InventarioItem(db.Model):
    """
    Item observado nas contagens diárias do chão da empresa.
    Ex.: Barril vazio, Keg P (30L), Keg G (50L), CO₂, Manômetro, Pingadeira.

    Não é controle de estoque — só catálogo do que será contado.
    A "última quantidade contada" é cacheada para listagem rápida.
    """
    __tablename__ = "inventario_itens"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    categoria = db.Column(db.String(40), nullable=False, default="equipamento")
    unidade = db.Column(db.String(10), default="un")
    icone = db.Column(db.String(8))
    observacao = db.Column(db.Text)

    # Cache: última contagem (para listar sem JOIN). Pode ser NULL = nunca contado.
    ultima_quantidade = db.Column(db.Integer)
    ultima_contagem_data = db.Column(db.Date)

    # Alerta opcional: se a contagem ficar ≤ alerta_se_abaixo, lista sinaliza
    alerta_se_abaixo = db.Column(db.Integer)

    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime, default=agora_brasil)

    contagens = db.relationship(
        "ContagemInventario",
        backref="item",
        cascade="all, delete-orphan",
        order_by="ContagemInventario.data.desc(), ContagemInventario.id.desc()",
    )

    @property
    def status_contagem(self):
        """
        'pendente'    — ainda não foi contado hoje
        'contado'     — foi contado hoje
        'desatualizado' — última contagem é de mais de 1 dia atrás
        'nunca'       — nunca foi contado
        """
        from datetime import date, timedelta
        if not self.ultima_contagem_data:
            return "nunca"
        hoje = date.today()
        if self.ultima_contagem_data == hoje:
            return "contado"
        if self.ultima_contagem_data >= hoje - timedelta(days=1):
            return "pendente"
        return "desatualizado"

    @property
    def em_alerta(self):
        if self.alerta_se_abaixo is None or self.ultima_quantidade is None:
            return False
        return self.ultima_quantidade <= self.alerta_se_abaixo

    def __repr__(self):
        return f"<InventarioItem {self.slug} ult={self.ultima_quantidade}>"


class ContagemInventario(db.Model):
    """
    Registro de UMA contagem física em uma data específica.
    Pode referir-se a:
      - InventarioItem (item operacional: barril vazio, keg, CO₂, etc.)
      - Produto (item do cardápio: chopp, cerveja, etc.)
    Exatamente UM dos dois deve estar setado por linha.
    """
    __tablename__ = "inventario_contagens"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("inventario_itens.id"), nullable=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)

    data = db.Column(db.Date, nullable=False, default=lambda: agora_brasil().date(), index=True)
    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.String(200))

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario = db.relationship("User")
    produto = db.relationship("Produto", foreign_keys=[produto_id])

    criado_em = db.Column(db.DateTime, default=agora_brasil)


class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True)

    produtos = db.relationship("Produto", backref="categoria_rel")

class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey("categoria.id"),
        nullable=False
    )

    preco = db.Column(db.Numeric(10, 2), nullable=False)
    foto = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True)

    # Cache da última contagem física (inventário diário)
    ultima_quantidade = db.Column(db.Integer)
    ultima_contagem_data = db.Column(db.Date)
    alerta_se_abaixo = db.Column(db.Integer)

    @property
    def status_contagem(self):
        from datetime import date, timedelta
        if not self.ultima_contagem_data:
            return "nunca"
        hoje = date.today()
        if self.ultima_contagem_data == hoje:
            return "contado"
        if self.ultima_contagem_data >= hoje - timedelta(days=1):
            return "pendente"
        return "desatualizado"

    @property
    def em_alerta(self):
        if self.alerta_se_abaixo is None or self.ultima_quantidade is None:
            return False
        return self.ultima_quantidade <= self.alerta_se_abaixo

    def __repr__(self):
        return f"<Produto {self.nome}>"

import os
import sys
from datetime import timedelta


def base_dir():
    """
    Retorna o diretório base correto:
    - Em desenvolvimento: diretório atual
    - Em executável (.exe): diretório do executável
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    DB_PATH = os.path.join(base_dir(), "comanda.db")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{DB_PATH}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # =====================================================
    # SESSÃO — mantém usuário logado nos tablets / navegadores
    # =====================================================
    # Sobrevive a fechar/abrir o navegador
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    # Cookie "lembrar-me" (login_user(remember=True))
    REMEMBER_COOKIE_DURATION = timedelta(days=60)
    # Atributos compatíveis com HTTP em rede local
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False
    # Renova validade do cookie a cada request (rolling expiration)
    SESSION_REFRESH_EACH_REQUEST = True

    # =====================================================
    # PIX — chave da loja para gerar QR Code "Copia e Cola"
    # Sobrescreva via env: PIX_CHAVE, PIX_NOME, PIX_CIDADE
    # Tipos aceitos pela chave: CPF/CNPJ, e-mail, telefone (+55…), aleatória (UUID)
    # =====================================================
    PIX_CHAVE = os.environ.get("PIX_CHAVE", "adicionar aqui chave pix")  # ex.: "12345678000199" (CNPJ) ou "loja@email.com"
    PIX_NOME = os.environ.get("PIX_NOME", "CHOPP PALAZZO EXPRESS")
    PIX_CIDADE = os.environ.get("PIX_CIDADE", "SAO PAULO")

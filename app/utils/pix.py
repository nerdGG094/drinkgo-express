"""
Gerador de Pix "Copia e Cola" (BR Code / EMV) + QR Code base64.

Especificação resumida (Banco Central — Manual de Padrões):
  - Cada campo tem ID (2 dígitos) + tamanho (2 dígitos) + valor.
  - Campo 26: Merchant Account Information (Pix)
      - 00: GUI fixo "br.gov.bcb.pix"
      - 01: chave Pix (e-mail, CPF/CNPJ, telefone +5511..., aleatória UUID)
  - Campo 52: Merchant Category Code (4 dígitos, "0000" para genérico)
  - Campo 53: Currency = "986" (BRL)
  - Campo 54: Valor opcional (string com 2 casas, ex. "12.34")
  - Campo 58: País = "BR"
  - Campo 59: Nome do recebedor (até 25 chars, ASCII upper)
  - Campo 60: Cidade (até 15 chars, ASCII upper)
  - Campo 62: Additional Data (TXID em 05)
  - Campo 63: CRC16-CCITT (XModem) das demais infos

Não tem dependência externa. CRC16 implementado em puro Python.
"""

from __future__ import annotations

import base64
import io
import re
import unicodedata
from typing import Optional


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _ascii_upper(s: str, max_len: int) -> str:
    """Remove acentos, força ASCII maiúsculo e limita tamanho."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", "", only_ascii).upper().strip()
    return cleaned[:max_len]


def _emv(field_id: str, value: str) -> str:
    """Monta um TLV no padrão EMV: ID(2) + LEN(2) + VALUE."""
    length = f"{len(value):02d}"
    return f"{field_id}{length}{value}"


def _crc16_ccitt(payload: str) -> str:
    """CRC16-CCITT (XMODEM) em hex maiúsculo, 4 dígitos."""
    crc = 0xFFFF
    for ch in payload.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def gerar_brcode(
    chave: str,
    nome: str,
    cidade: str,
    valor: float,
    txid: str = "***",
    descricao: Optional[str] = None,
) -> str:
    """
    Retorna o payload "Pix Copia e Cola" pronto para QR Code.
    Lança ValueError se faltar chave.
    """
    if not chave:
        raise ValueError("Chave Pix não configurada.")

    nome_san = _ascii_upper(nome or "RECEBEDOR", 25) or "RECEBEDOR"
    cidade_san = _ascii_upper(cidade or "BRASIL", 15) or "BRASIL"
    txid_san = re.sub(r"[^A-Za-z0-9]", "", txid) or "***"
    if len(txid_san) > 25:
        txid_san = txid_san[:25]

    # Conta de Pix (26)
    mai_subfields = _emv("00", "br.gov.bcb.pix") + _emv("01", chave.strip())
    if descricao:
        desc = _ascii_upper(descricao, 50)
        if desc:
            mai_subfields += _emv("02", desc)

    # Additional Data (62) — TXID em sub-id 05
    add_data = _emv("05", txid_san)

    # Valor formatado com 2 casas decimais (ponto). Se zero, omite o campo.
    valor_str = f"{float(valor):.2f}" if valor and float(valor) > 0 else ""

    # Monta payload sem CRC
    parts = [
        _emv("00", "01"),                  # Payload Format Indicator
        _emv("01", "12"),                  # Point of Initiation = static (12)
        _emv("26", mai_subfields),         # Merchant Account Information
        _emv("52", "0000"),                # MCC genérico
        _emv("53", "986"),                 # Currency BRL
    ]
    if valor_str:
        parts.append(_emv("54", valor_str))
    parts += [
        _emv("58", "BR"),                  # País
        _emv("59", nome_san),              # Nome
        _emv("60", cidade_san),            # Cidade
        _emv("62", add_data),              # Additional Data (TXID)
    ]

    payload_sem_crc = "".join(parts) + "6304"  # placeholder CRC field id+len
    crc = _crc16_ccitt(payload_sem_crc)
    return payload_sem_crc + crc


def gerar_qrcode_base64(payload: str, box_size: int = 8, border: int = 2) -> str:
    """
    Gera o QR como PNG inline em base64 (data URI).
    Lazy import do `qrcode` para a página não quebrar caso a lib falte.
    """
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"

"""
Configurações administrativas do sistema.

Permite ao admin ajustar parâmetros sem editar código nem reiniciar o app:
  - Chave Pix da loja (chave + nome do recebedor + cidade)
"""

import os
import sys
import json

from flask import render_template, request, redirect, url_for, flash, current_app
from ..utils.decorators import role_required
from . import admin_bp


def _path_pix_settings():
    """Caminho do arquivo de persistência Pix (lado do .exe ou raiz do projeto)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
        )
    return os.path.join(base, "pix_settings.json")


@admin_bp.route("/config/pix", methods=["GET", "POST"])
@role_required("admin")
def config_pix():
    if request.method == "POST":
        chave  = (request.form.get("chave")  or "").strip()
        nome   = (request.form.get("nome")   or "").strip()
        cidade = (request.form.get("cidade") or "").strip()

        if not chave:
            flash("Informe a chave Pix.", "warning")
            return redirect(url_for("admin.config_pix"))

        # Sanitiza para o padrão exigido pelo Pix BR Code (ASCII upper, comprimentos)
        nome_s = nome.upper()[:25] or "RECEBEDOR"
        cidade_s = cidade.upper()[:15] or "BRASIL"

        path = _path_pix_settings()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"PIX_CHAVE": chave, "PIX_NOME": nome_s, "PIX_CIDADE": cidade_s},
                    f, ensure_ascii=False, indent=2,
                )
        except Exception as e:
            flash(f"Falha ao salvar arquivo: {e}", "danger")
            return redirect(url_for("admin.config_pix"))

        # Atualiza config em runtime — não precisa reiniciar o app
        current_app.config["PIX_CHAVE"]  = chave
        current_app.config["PIX_NOME"]   = nome_s
        current_app.config["PIX_CIDADE"] = cidade_s

        flash("Chave Pix atualizada com sucesso. Já vale para os próximos cupons.", "success")
        return redirect(url_for("admin.config_pix"))

    # ---------- GET ----------
    chave  = current_app.config.get("PIX_CHAVE", "")
    nome   = current_app.config.get("PIX_NOME", "")
    cidade = current_app.config.get("PIX_CIDADE", "")

    qr_preview = None
    payload_preview = None
    if chave:
        try:
            from ..utils.pix import gerar_brcode, gerar_qrcode_base64
            payload_preview = gerar_brcode(
                chave=chave,
                nome=nome or "RECEBEDOR",
                cidade=cidade or "BRASIL",
                valor=1.00,
                txid="PREVIEW",
            )
            qr_preview = gerar_qrcode_base64(payload_preview)
        except Exception as e:
            current_app.logger.warning(f"[PIX] preview falhou: {e}")

    path = _path_pix_settings()
    salvo_em_arquivo = os.path.exists(path)

    return render_template(
        "admin/config_pix.html",
        chave=chave,
        nome=nome,
        cidade=cidade,
        qr_preview=qr_preview,
        payload_preview=payload_preview,
        path_arquivo=path,
        salvo_em_arquivo=salvo_em_arquivo,
    )

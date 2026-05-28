from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from datetime import datetime
from app import db
from app.models import Chopeira, AluguelChopeira
from . import admin_bp
from app.utils.decorators import role_required
from app.utils.permissoes import permissao_required
from app.models import AluguelChopeira, Chopeira
from flask_login import login_required
from flask import send_file
import pandas as pd
from io import BytesIO

@admin_bp.route("/chopeiras")
@permissao_required("chopeiras")
def chopeiras():

	grupo1_numeros = [
		142,143,144,145,146,147,148,149,150,155,156,157,158,159,160,161,162,
		171,172,173,174,175,176,177,178,179,180,181,182,191,192
	]

	grupo2_numeros = [
		163,164,165,166,167,168,169,170,183,184,185,186,187,188,189,190,193,194,
		195,196,152,153,154,132,133,134,135,136,137,151,104
	]

	grupo3_numeros = [
		19,22,21,28
	]

	todas = Chopeira.query.all()

	grupo1 = []
	grupo2 = []
	grupo3 = []

	for c in todas:
		if c.numero in grupo1_numeros:
			grupo1.append(c)
		elif c.numero in grupo2_numeros:
			grupo2.append(c)
		elif c.numero in grupo3_numeros:
			grupo3.append(c)

	# ========= ANEXAR FLAGS DE EQUIPAMENTOS =========
	def anexar_flags(lista):
		for c in lista:
			aluguel = AluguelChopeira.query.filter_by(
				chopeira_id=c.id,
				status="alugado"
			).first()

			if aluguel:
				c.alugou_co2_atual = bool(aluguel.alugou_co2)
				c.keg_tipo_atual = aluguel.keg_tipo
				c.alugou_manometro_atual = bool(aluguel.alugou_manometro)
				c.alugou_pingadeira_atual = bool(aluguel.alugou_pingadeira)
			else:
				c.alugou_co2_atual = False
				c.keg_tipo_atual = None
				c.alugou_manometro_atual = False
				c.alugou_pingadeira_atual = False

	anexar_flags(grupo1)
	anexar_flags(grupo2)
	anexar_flags(grupo3)
	# ==============================================
	return render_template(
		"admin/chopeiras.html",
		grupo1=grupo1,
		grupo2=grupo2,
		grupo3=grupo3
	)

# ===============================
# ALUGAR CHOPEIRA (CLIQUE VERDE)
# ===============================
@admin_bp.route("/chopeiras/<int:chopeira_id>", methods=["GET", "POST"])
@permissao_required("chopeiras")
def alugar_chopeira(chopeira_id):

	chopeira = Chopeira.query.get_or_404(chopeira_id)

	if chopeira.status == "alugada":
		return redirect(url_for("admin.chopeiras"))

	if request.method == "POST":

		aluguel = AluguelChopeira(
			chopeira_id=chopeira.id,
			cliente_nome=request.form.get("cliente_nome"),
			telefone=request.form.get("telefone"),
			endereco=request.form.get("endereco"),
			usuario_id=current_user.id,
			data_saida=datetime.utcnow(),
			status="alugado",

			# NOVOS CAMPOS KEG, CO2, MANOMETRO E PINGADEIRA
			keg_tipo=request.form.get("keg_tipo"),
			alugou_co2=bool(request.form.get("alugou_co2")),
			alugou_manometro=bool(request.form.get("alugou_manometro")),
			alugou_pingadeira = bool(request.form.get("alugou_pingadeira"))
		)

		chopeira.status = "alugada"

		db.session.add(aluguel)
		db.session.commit()

		return redirect(url_for("admin.chopeiras"))

	return render_template(
		"admin/alugar_chopeira.html",
		chopeira=chopeira
	)

# ===============================
# RETORNAR CHOPEIRA (BOTÃO VERMELHO)
# ===============================
@admin_bp.route("/chopeiras/<int:chopeira_id>/retornar", methods=["POST"])
@permissao_required("chopeiras")
def retornar_chopeira(chopeira_id):

	chopeira = Chopeira.query.get_or_404(chopeira_id)

	aluguel = (
		AluguelChopeira.query
		.filter_by(
			chopeira_id=chopeira.id,
			status="alugado"
		)
		.first()
	)

	if aluguel:
		aluguel.status = "devolvido"
		aluguel.data_retorno = datetime.utcnow()

	chopeira.status = "disponivel"

	db.session.commit()

	return redirect(url_for("admin.chopeiras"))


@admin_bp.route("/chopeiras/<int:chopeira_id>/detalhes")
@login_required
def detalhes_chopeira(chopeira_id):

    # Chopeira
    chopeira = Chopeira.query.get_or_404(chopeira_id)

    # Locação ATIVA da chopeira
    aluguel = (
        AluguelChopeira.query
        .filter(
            AluguelChopeira.chopeira_id == chopeira_id,
            AluguelChopeira.data_retorno.is_(None)
        )
        .first()
    )

    return render_template(
        "admin/chopeira_detalhes.html",
        chopeira=chopeira,
        aluguel=aluguel
    )

@admin_bp.route("/chopeiras/relatorio")
@permissao_required("chopeiras")
def relatorio_chopeiras_alugadas():
    """
    Relatório completo de todas as chopeiras atualmente alugadas
    """

    alugueis = (
        AluguelChopeira.query
        .filter_by(status="alugado")
        .order_by(AluguelChopeira.data_saida.asc())
        .all()
    )

    return render_template(
        "admin/relatorio_chopeiras_alugadas.html",
        alugueis=alugueis,
        now=datetime.utcnow()
    )

@admin_bp.route("/chopeiras/relatorio/exportar-excel")
@permissao_required("chopeiras")
def exportar_relatorio_chopeiras_excel():

    alugueis = (
        AluguelChopeira.query
        .filter_by(status="alugado")
        .order_by(AluguelChopeira.data_saida.asc())
        .all()
    )

    dados = []

    for a in alugueis:
        dados.append({
            "Chopeira": a.chopeira.numero if a.chopeira else "",
            "Cliente": a.cliente_nome,
            "Telefone": a.telefone,
            "Endereço": a.endereco,
            "Data Saída": a.data_saida.strftime("%d/%m/%Y") if a.data_saida else "",
            "Dias Alugado": (datetime.utcnow() - a.data_saida).days if a.data_saida else "",
            "CO₂": "Sim" if a.alugou_co2 else "Não",
            "KEG": a.keg_tipo or "",
            "Manômetro": "Sim" if a.alugou_manometro else "Não",
            "Pingadeira": "Sim" if a.alugou_pingadeira else "Não",
            "Usuário": a.usuario.nome if a.usuario else ""
        })

    df = pd.DataFrame(dados)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Chopeiras Alugadas")

    output.seek(0)

    nome_arquivo = f"relatorio_chopeiras_alugadas_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

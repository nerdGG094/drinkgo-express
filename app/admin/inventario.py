"""
Inventário — contagem física diária de tudo que existe no chão da empresa.
Inclui:
  - InventarioItem  (operacionais: barril vazio, kegs, CO₂, manômetro, pingadeira, ...)
  - Produto         (cardápio: chopps, cervejas, etc.)
"""

import re
import unicodedata
from datetime import date, timedelta, datetime
from io import BytesIO

from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import current_user
from sqlalchemy import or_, func

from ..models import db, InventarioItem, ContagemInventario, Produto
from ..utils.permissoes import permissao_required
from . import admin_bp


# ----------------------------------------------------------------------
CATEGORIAS = [
    ("barril",      "Barril"),
    ("keg",         "Keg"),
    ("gas",         "Gás / Cilindro"),
    ("equipamento", "Equipamento"),
    ("acessorio",   "Acessório"),
    ("outros",      "Outros"),
]

ITENS_PADRAO = [
    {"slug": "barril_vazio", "nome": "Barril vazio",   "categoria": "barril",      "icone": "🛢️", "unidade": "un"},
    {"slug": "keg_p",        "nome": "Keg P (30L)",    "categoria": "keg",         "icone": "🍺", "unidade": "un"},
    {"slug": "keg_g",        "nome": "Keg G (50L)",    "categoria": "keg",         "icone": "🍺", "unidade": "un"},
    {"slug": "co2",          "nome": "CO₂ (cilindro)", "categoria": "gas",         "icone": "💨", "unidade": "un"},
    {"slug": "manometro",    "nome": "Manômetro",      "categoria": "equipamento", "icone": "🌡️", "unidade": "un"},
    {"slug": "pingadeira",   "nome": "Pingadeira",     "categoria": "acessorio",   "icone": "🧊", "unidade": "un"},
]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def slugify(s: str) -> str:
    if not s:
        return ""
    n = unicodedata.normalize("NFKD", s)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"[^a-zA-Z0-9]+", "_", n).strip("_").lower()
    return n[:60] or "item"


def slug_unico(base, exceto_id=None):
    slug = slugify(base)
    candidato = slug
    i = 2
    while True:
        q = InventarioItem.query.filter_by(slug=candidato)
        if exceto_id:
            q = q.filter(InventarioItem.id != exceto_id)
        if q.first() is None:
            return candidato
        candidato = f"{slug}_{i}"
        i += 1


def registrar_contagem_item(item, quantidade, data=None, observacao=None, usuario_id=None):
    if data is None:
        data = date.today()

    cont = ContagemInventario(
        item_id=item.id,
        produto_id=None,
        data=data,
        quantidade=int(quantidade),
        observacao=observacao,
        usuario_id=usuario_id,
    )
    db.session.add(cont)
    if (item.ultima_contagem_data is None) or (data >= item.ultima_contagem_data):
        item.ultima_quantidade = int(quantidade)
        item.ultima_contagem_data = data
    return cont


def registrar_contagem_produto(produto, quantidade, data=None, observacao=None, usuario_id=None):
    if data is None:
        data = date.today()

    cont = ContagemInventario(
        produto_id=produto.id,
        item_id=None,
        data=data,
        quantidade=int(quantidade),
        observacao=observacao,
        usuario_id=usuario_id,
    )
    db.session.add(cont)
    if (produto.ultima_contagem_data is None) or (data >= produto.ultima_contagem_data):
        produto.ultima_quantidade = int(quantidade)
        produto.ultima_contagem_data = data
    return cont


def _quantidade_anterior(*, item_id=None, produto_id=None, antes_de_data):
    q = ContagemInventario.query
    if item_id is not None:
        q = q.filter(ContagemInventario.item_id == item_id)
    if produto_id is not None:
        q = q.filter(ContagemInventario.produto_id == produto_id)
    cont = (
        q.filter(ContagemInventario.data < antes_de_data)
        .order_by(ContagemInventario.data.desc(), ContagemInventario.id.desc())
        .first()
    )
    return cont.quantidade if cont else None


# ======================================================================
# LISTA — itens operacionais + produtos do cardápio
# ======================================================================
@admin_bp.route("/inventario")
@permissao_required("inventario")
def inventario():
    busca = (request.args.get("q") or "").strip()
    cat = (request.args.get("categoria") or "todas").strip()
    tipo = (request.args.get("tipo") or "todos").strip()  # todos | item | produto

    itens = []
    if tipo in ("todos", "item"):
        q_item = InventarioItem.query
        if busca:
            like = f"%{busca}%"
            q_item = q_item.filter(or_(
                InventarioItem.nome.ilike(like),
                InventarioItem.slug.ilike(like),
            ))
        if cat and cat != "todas":
            q_item = q_item.filter(InventarioItem.categoria == cat)
        itens = q_item.order_by(InventarioItem.categoria, InventarioItem.nome).all()

    produtos = []
    if tipo in ("todos", "produto"):
        q_prod = Produto.query.filter_by(ativo=True)
        if busca:
            like = f"%{busca}%"
            q_prod = q_prod.filter(Produto.nome.ilike(like))
        # filtro por categoria do "tipo operacional" não se aplica a produtos;
        # se categoria != todas, só mostra produtos quando tipo=produto
        produtos = q_prod.order_by(Produto.nome).all() if (cat == "todas" or tipo == "produto") else []

    hoje = date.today()
    todos_itens = InventarioItem.query.filter_by(ativo=True).all()
    todos_produtos = Produto.query.filter_by(ativo=True).all()

    total = len(todos_itens) + len(todos_produtos)
    contados_hoje = (
        sum(1 for i in todos_itens if i.ultima_contagem_data == hoje) +
        sum(1 for p in todos_produtos if p.ultima_contagem_data == hoje)
    )
    pendentes = total - contados_hoje
    em_alerta = (
        sum(1 for i in todos_itens if i.em_alerta) +
        sum(1 for p in todos_produtos if p.em_alerta)
    )

    ultima_cont = (
        ContagemInventario.query
        .order_by(ContagemInventario.criado_em.desc())
        .first()
    )

    return render_template(
        "admin/inventario/lista.html",
        itens=itens,
        produtos=produtos,
        categorias=CATEGORIAS,
        categoria_filtro=cat,
        tipo_filtro=tipo,
        busca=busca,
        hoje=hoje,
        total_itens=total,
        contados_hoje=contados_hoje,
        pendentes=pendentes,
        em_alerta=em_alerta,
        ultima_cont=ultima_cont,
    )


# ======================================================================
# DETALHES — InventarioItem
# ======================================================================
@admin_bp.route("/inventario/item/<int:item_id>")
@permissao_required("inventario")
def inventario_item(item_id):
    item = InventarioItem.query.get_or_404(item_id)
    historico = (
        ContagemInventario.query
        .filter_by(item_id=item.id)
        .order_by(ContagemInventario.data.desc(), ContagemInventario.id.desc())
        .limit(60)
        .all()
    )
    historico_view = []
    for i, c in enumerate(historico):
        prev = historico[i + 1] if i + 1 < len(historico) else None
        delta = (c.quantidade - prev.quantidade) if prev else None
        historico_view.append({"c": c, "delta": delta})

    return render_template(
        "admin/inventario/item.html",
        kind="item",
        alvo=item,
        historico=historico_view,
        hoje=date.today(),
    )


# ======================================================================
# DETALHES — Produto (mesmo template)
# ======================================================================
@admin_bp.route("/inventario/produto/<int:produto_id>")
@permissao_required("inventario")
def inventario_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    historico = (
        ContagemInventario.query
        .filter_by(produto_id=produto.id)
        .order_by(ContagemInventario.data.desc(), ContagemInventario.id.desc())
        .limit(60)
        .all()
    )
    historico_view = []
    for i, c in enumerate(historico):
        prev = historico[i + 1] if i + 1 < len(historico) else None
        delta = (c.quantidade - prev.quantidade) if prev else None
        historico_view.append({"c": c, "delta": delta})

    return render_template(
        "admin/inventario/item.html",
        kind="produto",
        alvo=produto,
        historico=historico_view,
        hoje=date.today(),
    )


# ======================================================================
# REALIZAR CONTAGEM — formulário com TUDO (itens + produtos)
# ======================================================================
@admin_bp.route("/inventario/contar", methods=["GET", "POST"])
@permissao_required("inventario")
def inventario_contar():
    hoje = date.today()

    if request.method == "POST":
        data_str = (request.form.get("data") or "").strip()
        try:
            data_contagem = date.fromisoformat(data_str) if data_str else hoje
        except ValueError:
            data_contagem = hoje

        contadas = 0

        # InventarioItem
        for item in InventarioItem.query.filter_by(ativo=True).all():
            raw = (request.form.get(f"qtd_item_{item.id}") or "").strip()
            if raw == "":
                continue
            try:
                qtd = int(raw)
                if qtd < 0: raise ValueError
            except ValueError:
                continue
            obs = (request.form.get(f"obs_item_{item.id}") or "").strip() or None
            registrar_contagem_item(item, qtd, data=data_contagem, observacao=obs, usuario_id=current_user.id)
            contadas += 1

        # Produto
        for prod in Produto.query.filter_by(ativo=True).all():
            raw = (request.form.get(f"qtd_prod_{prod.id}") or "").strip()
            if raw == "":
                continue
            try:
                qtd = int(raw)
                if qtd < 0: raise ValueError
            except ValueError:
                continue
            obs = (request.form.get(f"obs_prod_{prod.id}") or "").strip() or None
            registrar_contagem_produto(prod, qtd, data=data_contagem, observacao=obs, usuario_id=current_user.id)
            contadas += 1

        if contadas == 0:
            flash("Nenhuma quantidade foi preenchida.", "warning")
            return redirect(url_for("admin.inventario_contar"))

        db.session.commit()
        flash(
            f"Contagem registrada: {contadas} entrada(s) lançada(s) em "
            f"{data_contagem.strftime('%d/%m/%Y')}.",
            "success"
        )
        return redirect(url_for("admin.inventario"))

    # GET — monta linhas para os dois tipos
    itens = (
        InventarioItem.query
        .filter_by(ativo=True)
        .order_by(InventarioItem.categoria, InventarioItem.nome)
        .all()
    )
    produtos = (
        Produto.query
        .filter_by(ativo=True)
        .order_by(Produto.nome)
        .all()
    )

    linhas_itens = []
    for it in itens:
        existente = (
            ContagemInventario.query
            .filter_by(item_id=it.id, data=hoje)
            .order_by(ContagemInventario.id.desc()).first()
        )
        anterior = _quantidade_anterior(item_id=it.id, antes_de_data=hoje)
        linhas_itens.append({
            "alvo": it, "kind": "item",
            "qtd_hoje_existente": existente.quantidade if existente else None,
            "qtd_anterior": anterior,
        })

    linhas_produtos = []
    for p in produtos:
        existente = (
            ContagemInventario.query
            .filter_by(produto_id=p.id, data=hoje)
            .order_by(ContagemInventario.id.desc()).first()
        )
        anterior = _quantidade_anterior(produto_id=p.id, antes_de_data=hoje)
        linhas_produtos.append({
            "alvo": p, "kind": "produto",
            "qtd_hoje_existente": existente.quantidade if existente else None,
            "qtd_anterior": anterior,
        })

    return render_template(
        "admin/inventario/contagem_form.html",
        linhas_itens=linhas_itens,
        linhas_produtos=linhas_produtos,
        hoje=hoje,
    )


# ======================================================================
# CONTAGEM RÁPIDA — InventarioItem
# ======================================================================
@admin_bp.route("/inventario/item/<int:item_id>/contagem-rapida", methods=["POST"])
@permissao_required("inventario")
def inventario_item_contagem_rapida(item_id):
    item = InventarioItem.query.get_or_404(item_id)
    raw = (request.form.get("quantidade") or "").strip()
    if raw == "":
        flash("Informe a quantidade.", "warning")
        return redirect(url_for("admin.inventario_item", item_id=item.id))
    try:
        qtd = int(raw)
        if qtd < 0: raise ValueError
    except ValueError:
        flash("Quantidade inválida.", "warning")
        return redirect(url_for("admin.inventario_item", item_id=item.id))
    obs = (request.form.get("observacao") or "").strip() or None
    registrar_contagem_item(item, qtd, observacao=obs, usuario_id=current_user.id)
    db.session.commit()
    flash(f"Contagem registrada: {item.nome} = {qtd} {item.unidade}.", "success")
    return redirect(url_for("admin.inventario_item", item_id=item.id))


# ======================================================================
# CONTAGEM RÁPIDA — Produto
# ======================================================================
@admin_bp.route("/inventario/produto/<int:produto_id>/contagem-rapida", methods=["POST"])
@permissao_required("inventario")
def inventario_produto_contagem_rapida(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    raw = (request.form.get("quantidade") or "").strip()
    if raw == "":
        flash("Informe a quantidade.", "warning")
        return redirect(url_for("admin.inventario_produto", produto_id=produto.id))
    try:
        qtd = int(raw)
        if qtd < 0: raise ValueError
    except ValueError:
        flash("Quantidade inválida.", "warning")
        return redirect(url_for("admin.inventario_produto", produto_id=produto.id))
    obs = (request.form.get("observacao") or "").strip() or None
    registrar_contagem_produto(produto, qtd, observacao=obs, usuario_id=current_user.id)
    db.session.commit()
    flash(f"Contagem registrada: {produto.nome} = {qtd} un.", "success")
    return redirect(url_for("admin.inventario_produto", produto_id=produto.id))


# ======================================================================
# EXCLUIR CONTAGEM (admin pode corrigir engano)
# ======================================================================
@admin_bp.route("/inventario/contagem/<int:contagem_id>/excluir", methods=["POST"])
@permissao_required("inventario")
def inventario_excluir_contagem(contagem_id):
    cont = ContagemInventario.query.get_or_404(contagem_id)
    item_id = cont.item_id
    produto_id = cont.produto_id

    db.session.delete(cont)
    db.session.flush()

    # Recalcula cache
    if item_id is not None:
        item = InventarioItem.query.get(item_id)
        nova = (
            ContagemInventario.query
            .filter_by(item_id=item_id)
            .order_by(ContagemInventario.data.desc(), ContagemInventario.id.desc())
            .first()
        )
        if nova:
            item.ultima_quantidade = nova.quantidade
            item.ultima_contagem_data = nova.data
        else:
            item.ultima_quantidade = None
            item.ultima_contagem_data = None
        db.session.commit()
        flash("Contagem removida.", "success")
        return redirect(url_for("admin.inventario_item", item_id=item_id))

    if produto_id is not None:
        produto = Produto.query.get(produto_id)
        nova = (
            ContagemInventario.query
            .filter_by(produto_id=produto_id)
            .order_by(ContagemInventario.data.desc(), ContagemInventario.id.desc())
            .first()
        )
        if nova:
            produto.ultima_quantidade = nova.quantidade
            produto.ultima_contagem_data = nova.data
        else:
            produto.ultima_quantidade = None
            produto.ultima_contagem_data = None
        db.session.commit()
        flash("Contagem removida.", "success")
        return redirect(url_for("admin.inventario_produto", produto_id=produto_id))

    db.session.commit()
    return redirect(url_for("admin.inventario"))


# ======================================================================
# ITEM operacional — novo / editar / seed
# ======================================================================
@admin_bp.route("/inventario/novo", methods=["GET", "POST"])
@permissao_required("inventario")
def inventario_novo():
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        categoria = (request.form.get("categoria") or "outros").strip()
        unidade = (request.form.get("unidade") or "un").strip()[:10]
        icone = (request.form.get("icone") or "").strip()[:8]
        observacao = (request.form.get("observacao") or "").strip()
        alerta_raw = (request.form.get("alerta_se_abaixo") or "").strip()

        if not nome:
            flash("Informe o nome do item.", "warning")
            return redirect(url_for("admin.inventario_novo"))
        try:
            alerta = int(alerta_raw) if alerta_raw else None
        except ValueError:
            alerta = None

        item = InventarioItem(
            nome=nome, slug=slug_unico(nome),
            categoria=categoria, unidade=unidade,
            icone=icone or None, observacao=observacao or None,
            alerta_se_abaixo=alerta, ativo=True,
        )
        db.session.add(item)
        db.session.commit()
        flash("Item criado. Agora você pode lançá-lo na próxima contagem.", "success")
        return redirect(url_for("admin.inventario_item", item_id=item.id))

    return render_template("admin/inventario/item_form.html", item=None, categorias=CATEGORIAS)


@admin_bp.route("/inventario/item/<int:item_id>/editar", methods=["GET", "POST"])
@permissao_required("inventario")
def inventario_editar(item_id):
    item = InventarioItem.query.get_or_404(item_id)
    if request.method == "POST":
        item.nome = (request.form.get("nome") or item.nome).strip()
        item.categoria = (request.form.get("categoria") or item.categoria).strip()
        item.unidade = (request.form.get("unidade") or item.unidade).strip()[:10]
        novo_icone = (request.form.get("icone") or "").strip()[:8]
        item.icone = novo_icone or None
        item.observacao = (request.form.get("observacao") or "").strip() or None
        item.ativo = bool(request.form.get("ativo"))
        alerta_raw = (request.form.get("alerta_se_abaixo") or "").strip()
        try:
            item.alerta_se_abaixo = int(alerta_raw) if alerta_raw else None
        except ValueError:
            item.alerta_se_abaixo = None
        db.session.commit()
        flash("Item atualizado.", "success")
        return redirect(url_for("admin.inventario_item", item_id=item.id))

    return render_template("admin/inventario/item_form.html", item=item, categorias=CATEGORIAS)


@admin_bp.route("/inventario/relatorio")
@permissao_required("inventario")
def inventario_relatorio():
    """Tela de relatório com filtros, preview agrupado por item e botão Excel."""
    hoje = date.today()
    data_ini_str = (request.args.get("data_ini") or "").strip()
    data_fim_str = (request.args.get("data_fim") or "").strip()

    try:
        data_ini = date.fromisoformat(data_ini_str) if data_ini_str else hoje
    except ValueError:
        data_ini = hoje
    try:
        data_fim = date.fromisoformat(data_fim_str) if data_fim_str else hoje
    except ValueError:
        data_fim = hoje
    if data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini

    contagens = (
        ContagemInventario.query
        .filter(ContagemInventario.data >= data_ini)
        .filter(ContagemInventario.data <= data_fim)
        .order_by(ContagemInventario.data.asc(), ContagemInventario.id.asc())
        .all()
    )

    # Agrupa por (kind, target_id) para o preview
    agrupado = {}
    for c in contagens:
        if c.item_id is not None and c.item is not None:
            key = ("item", c.item_id)
            nome = c.item.nome
            categoria = c.item.categoria
            unidade = c.item.unidade or "un"
            icone = c.item.icone or "📦"
        elif c.produto_id is not None and c.produto is not None:
            key = ("produto", c.produto_id)
            nome = c.produto.nome
            categoria = "Cardápio"
            unidade = "un"
            icone = "🍺"
        else:
            continue

        bucket = agrupado.setdefault(key, {
            "kind": key[0], "alvo_id": key[1],
            "nome": nome, "categoria": categoria,
            "unidade": unidade, "icone": icone,
            "registros": [], "primeira": None, "ultima": None,
        })
        bucket["registros"].append(c)

    # Calcula primeira/última quantidade e variação
    linhas = []
    for bucket in agrupado.values():
        regs = bucket["registros"]
        bucket["primeira_qtd"] = regs[0].quantidade
        bucket["ultima_qtd"] = regs[-1].quantidade
        bucket["primeira_data"] = regs[0].data
        bucket["ultima_data"] = regs[-1].data
        bucket["variacao"] = bucket["ultima_qtd"] - bucket["primeira_qtd"]
        bucket["count"] = len(regs)
        linhas.append(bucket)

    linhas.sort(key=lambda x: (x["kind"] != "item", x["categoria"], x["nome"]))

    total_registros = len(contagens)
    dias_com_contagem = len({c.data for c in contagens})
    itens_diferentes = len(agrupado)

    return render_template(
        "admin/inventario/relatorio.html",
        data_ini=data_ini,
        data_fim=data_fim,
        linhas=linhas,
        total_registros=total_registros,
        dias_com_contagem=dias_com_contagem,
        itens_diferentes=itens_diferentes,
        hoje=hoje,
    )


@admin_bp.route("/inventario/relatorio/excel")
@permissao_required("inventario")
def inventario_relatorio_excel():
    """Gera Excel com 3 abas: Resumo, Por Item (pivot), Detalhado."""
    import pandas as pd

    hoje = date.today()
    data_ini_str = (request.args.get("data_ini") or "").strip()
    data_fim_str = (request.args.get("data_fim") or "").strip()
    try:
        data_ini = date.fromisoformat(data_ini_str) if data_ini_str else hoje
    except ValueError:
        data_ini = hoje
    try:
        data_fim = date.fromisoformat(data_fim_str) if data_fim_str else hoje
    except ValueError:
        data_fim = hoje
    if data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini

    contagens = (
        ContagemInventario.query
        .filter(ContagemInventario.data >= data_ini)
        .filter(ContagemInventario.data <= data_fim)
        .order_by(ContagemInventario.data.asc(), ContagemInventario.id.asc())
        .all()
    )

    rows = []
    for c in contagens:
        if c.item_id is not None and c.item is not None:
            tipo = "Operacional"
            categoria = (c.item.categoria or "").capitalize()
            nome = c.item.nome
            unidade = c.item.unidade or "un"
        elif c.produto_id is not None and c.produto is not None:
            tipo = "Cardápio"
            categoria = "Cardápio"
            nome = c.produto.nome
            unidade = "un"
        else:
            continue

        rows.append({
            "Data":         c.data.strftime("%d/%m/%Y"),
            "Tipo":         tipo,
            "Categoria":    categoria,
            "Item":         nome,
            "Quantidade":   c.quantidade,
            "Unidade":      unidade,
            "Observação":   c.observacao or "",
            "Usuário":      c.usuario.nome if c.usuario else "",
            "Registrado em": c.criado_em.strftime("%d/%m/%Y %H:%M") if c.criado_em else "",
        })

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        # ----- Aba Resumo -----
        resumo_dados = [
            ["Período", f"{data_ini.strftime('%d/%m/%Y')} → {data_fim.strftime('%d/%m/%Y')}"],
            ["Total de contagens", len(rows)],
            ["Dias com contagem", len({r['Data'] for r in rows})],
            ["Itens distintos contados", len({(r['Tipo'], r['Item']) for r in rows})],
            ["Operacionais", sum(1 for r in rows if r['Tipo'] == 'Operacional')],
            ["Produtos do cardápio", sum(1 for r in rows if r['Tipo'] == 'Cardápio')],
            ["Soma das quantidades", int(sum(r['Quantidade'] for r in rows))],
            ["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")],
        ]
        df_resumo = pd.DataFrame(resumo_dados, columns=["Métrica", "Valor"])
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)

        if rows:
            df_det = pd.DataFrame(rows)

            # ----- Aba Por Item (matriz item × data) -----
            try:
                df_pivot = df_det.pivot_table(
                    index=["Tipo", "Categoria", "Item", "Unidade"],
                    columns="Data",
                    values="Quantidade",
                    aggfunc="last",
                    fill_value="",
                ).reset_index()
                df_pivot.to_excel(writer, sheet_name="Por Item", index=False)
            except Exception:
                pass

            # ----- Aba Detalhado -----
            df_det.to_excel(writer, sheet_name="Detalhado", index=False)
        else:
            pd.DataFrame([{"Info": "Nenhuma contagem registrada no período"}])\
                .to_excel(writer, sheet_name="Detalhado", index=False)

        # Auto-ajusta largura das colunas
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        v = str(cell.value) if cell.value is not None else ""
                        if len(v) > max_len:
                            max_len = len(v)
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 50)

    output.seek(0)
    nome = f"contagem_inventario_{data_ini.isoformat()}_a_{data_fim.isoformat()}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=nome,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/inventario/seed-padrao", methods=["POST"])
@permissao_required("inventario")
def inventario_seed_padrao():
    criados = 0
    for spec in ITENS_PADRAO:
        if InventarioItem.query.filter_by(slug=spec["slug"]).first():
            continue
        item = InventarioItem(
            slug=spec["slug"], nome=spec["nome"],
            categoria=spec["categoria"], unidade=spec.get("unidade", "un"),
            icone=spec.get("icone"), ativo=True,
        )
        db.session.add(item)
        criados += 1
    db.session.commit()
    if criados:
        flash(f"{criados} item(ns) padrão criados.", "success")
    else:
        flash("Os itens padrão já existem.", "info")
    return redirect(url_for("admin.inventario"))

import os
from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from ..models import db, Produto, Categoria
from ..utils.decorators import role_required
from ..utils.permissoes import permissao_required
from . import admin_bp
from collections import defaultdict
import sys
from flask import send_from_directory

ALLOWED_EXT = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

def get_base_dir():
    # quando roda em EXE
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # quando roda em dev normal
    return os.path.abspath(os.path.dirname(__file__))

BASE_DIR = get_base_dir()

# pasta externa definitiva
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "produtos")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def salvar_foto(file_storage, nome_atual=None, produto_id=None):
    if not file_storage or not file_storage.filename:
        return nome_atual

    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXT:
        flash("Formato de imagem inválido. Use PNG/JPG/GIF/WebP.", "warning")
        return nome_atual

    # nome padronizado
    if produto_id:
        filename = f"produto_{produto_id}{ext}"

    path = os.path.join(UPLOAD_DIR, filename)
    file_storage.save(path)

    return filename

@admin_bp.route("/produtos")
@permissao_required("produtos")
def produtos():

    categoria_filtro = request.args.get("categoria", "todas")

    # ===== QUERY COM JOIN =====
    query = db.session.query(
        Produto,
        Categoria.nome.label("categoria_nome")
    ).outerjoin(Categoria, Categoria.id == Produto.categoria_id)

    if categoria_filtro != "todas":
        query = query.filter(Categoria.nome == categoria_filtro)

    # ===== PAGINAÇÃO =====
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 150

    paginacao = query.order_by(Categoria.nome, Produto.nome)\
        .paginate(page=pagina, per_page=por_pagina, error_out=False)

    resultados = paginacao.items
    total_paginas = paginacao.pages

    # ===== AGRUPAR POR CATEGORIA =====
    produtos_por_categoria = defaultdict(list)

    for prod, cat_nome in resultados:
        prod.categoria_nome = cat_nome or "SEM CATEGORIA"
        produtos_por_categoria[prod.categoria_nome].append(prod)

    # ===== LISTA DE CATEGORIAS PARA FILTRO =====
    categorias = Categoria.query.filter_by(ativo=1).order_by(Categoria.nome).all()
    categorias = [c.nome for c in categorias]

    return render_template(
        "admin/produtos.html",
        produtos_por_categoria=produtos_por_categoria,
        pagina_atual=pagina,
        total_paginas=total_paginas,
        categoria_filtro=categoria_filtro,
        categorias=categorias
    )


@admin_bp.route("/produtos/novo", methods=["GET", "POST"])
@permissao_required("produtos")
def produtos_novo():
    if request.method == "POST":
        nome = request.form.get("nome")
        categoria_id = request.form.get("categoria_id")
        preco = request.form.get("preco")
        ativo = bool(request.form.get("ativo"))
        foto_arquivo = request.files.get("foto_arquivo")

        if not (nome and categoria_id and preco):
            flash("Preencha nome, categoria e preço.", "warning")
            return redirect(url_for("admin.produtos_novo"))

        try:
            preco_val = float(preco.replace(",", "."))
        except ValueError:
            flash("Preço inválido.", "warning")
            return redirect(url_for("admin.produtos_novo"))

        p = Produto(
            nome=nome,
            categoria_id=int(categoria_id),
            preco=preco_val,
            ativo=ativo
        )
        db.session.add(p)
        db.session.flush()  # para ter p.id

        foto_nome = salvar_foto(foto_arquivo, produto_id=p.id)
        p.foto = foto_nome

        db.session.commit()
        return redirect(url_for("admin.produtos"))

    categorias = Categoria.query.filter_by(ativo=1).order_by(Categoria.nome).all()
    return render_template(
        "admin/produtos_form.html",
        produto=None,
        categorias=categorias
    )

@admin_bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@permissao_required("produtos")
def produtos_editar(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    if request.method == "POST":
        nome = request.form.get("nome")
        categoria_id = request.form.get("categoria_id")
        preco = request.form.get("preco")
        ativo = bool(request.form.get("ativo"))
        foto_arquivo = request.files.get("foto_arquivo")

        if not (nome and categoria_id and preco):
            flash("Preencha nome, categoria e preço.", "warning")
            return redirect(url_for("admin.produtos_editar", produto_id=produto.id))

        try:
            preco_val = float(preco.replace(",", "."))
        except ValueError:
            flash("Preço inválido.", "warning")
            return redirect(url_for("admin.produtos_editar", produto_id=produto.id))

        produto.nome = nome
        produto.categoria_id = int(categoria_id)
        produto.preco = preco_val
        produto.ativo = ativo

        nova_foto = salvar_foto(foto_arquivo, nome_atual=produto.foto, produto_id=produto.id)
        produto.foto = nova_foto

        db.session.commit()
        return redirect(url_for("admin.produtos"))

    categorias = Categoria.query.filter_by(ativo=1).order_by(Categoria.nome).all()

    return render_template(
        "admin/produtos_form.html",
        produto=produto,
        categorias=categorias
    )


@admin_bp.route("/uploads/produtos/<filename>")
def imagem_produto(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@admin_bp.route("/categorias/nova", methods=["GET","POST"])
def categoria_novo():
    if request.method == "POST":
        nome = request.form.get("nome")
        ativo = True if request.form.get("ativo") else False

        nova = Categoria(nome=nome, ativo=ativo)
        db.session.add(nova)
        db.session.commit()

        flash("Categoria criada!", "success")
        return redirect(url_for("admin.produtos"))

    return render_template("admin/categoria_form.html", categoria=None)


@admin_bp.route("/categorias/editar/<int:id>", methods=["GET","POST"])
def categoria_editar(id):
    cat = Categoria.query.get_or_404(id)

    if request.method == "POST":
        cat.nome = request.form.get("nome")
        cat.ativo = True if request.form.get("ativo") else False

        db.session.commit()
        flash("Categoria atualizada!", "success")
        return redirect(url_for("admin.produtos"))

    return render_template("admin/categoria_form.html", categoria=cat)

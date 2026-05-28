# Comanda Digital V3 (Modular, com Upload de Fotos e Painel do Garçom)

## Requisitos
- Python 3.12 (recomendado)

## Instalação

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Login

- Garçom:
  - email: garcom@local
  - senha: 123

- Caixa:
  - email: caixa@local
  - senha: 123

- Admin:
  - email: admin@local
  - senha: 123

## Principais URLs

- Login: http://localhost:5000/auth/login
- Novo pedido (garçom): http://localhost:5000/public/novo
- Mesas: http://localhost:5000/public/mesas
- Painel do garçom (ver pedidos): http://localhost:5000/public/pedidos
- Status do pedido (garçom): /public/pedido/<id>/status

- Cozinha/Caixa: http://localhost:5000/admin/pedidos
- Cupom do pedido: /admin/pedido/<id>/cupom
- Relatório de itens vendidos: http://localhost:5000/admin/relatorio/itens

- Clientes: http://localhost:5000/admin/clientes
- Usuários (admin): http://localhost:5000/admin/usuarios
- Produtos (cadastro de cardápio, com upload de foto): http://localhost:5000/admin/produtos
```

As fotos enviadas pelo formulário de produto são salvas em `app/static/imagens_produtos/` e mostram automaticamente no cardápio e no painel da cozinha.

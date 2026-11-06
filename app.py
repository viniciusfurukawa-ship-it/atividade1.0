import os
from decimal import Decimal, InvalidOperation

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


load_dotenv()

app = Flask(__name__)
SUPABASE_URL = os.getenv().rstrip("/")
SUPABASE_SECRET_KEY = os.getenv()


def acessar_supabase(metodo, tabela, parametros=None, dados=None):
    resposta = requests.request(
        metodo,
        f"{SUPABASE_URL}/rest/v1/{tabela}",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            "content-type": "application/json",
            "prefer": "return=representation",
        },
        params=parametros,
        json=dados,
        timeout=10,
    )

    resposta.raise_for_status()
    return resposta.json()


def normalizar_texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def validar_cliente(dados):
    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON válido.")

    nome = normalizar_texto(dados.get("nome"))
    email = normalizar_texto(dados.get("email")).lower()
    telefone = normalizar_texto(dados.get("telefone"))

    if not nome:
        raise ValueError("O campo nome é obrigatório.")
    if len(nome) < 2 or len(nome) > 80:
        raise ValueError("O nome deve ter entre 2 e 80 caracteres.")
    if not email:
        raise ValueError("O campo e-mail é obrigatório.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Informe um e-mail válido.")
    if telefone and len(telefone) > 20:
        raise ValueError("O telefone deve ter no máximo 20 caracteres.")

    return {
        "nome": nome,
        "email": email,
        "telefone": telefone or None,
    }


@app.before_request
def conferir_configuracao():
    if request.path.startswith("/api/"):
        if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
            return jsonify(mensagem="configure a url e a chave do supabase"), 503


@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/clientes")
def listar_clientes():
    clientes = acessar_supabase(
        "GET",
        "clientes",
        {"select": "cliente_id,nome,email,telefone", "order": "nome.asc"},
    )
    return jsonify(clientes)


@app.post("/api/clientes")
def cadastrar_cliente():
    dados = request.get_json(silent=True)

    try:
        cliente = validar_cliente(dados)
    except ValueError as erro:
        return jsonify(mensagem=str(erro)), 400

    resultado = acessar_supabase("POST", "clientes", dados=cliente)
    item = resultado[0] if isinstance(resultado, list) and resultado else resultado
    return jsonify({"mensagem": "cliente cadastrado com sucesso", "cliente": item}), 201


@app.get("/api/categorias")
def listar_catgorias():
    categorias = acessar_supabase(
        "GET",
        "categorias",
        {"select": "categoria_id,nome", "order": "nome.asc"},
    )
    return jsonify(categorias)


@app.get("/api/produtos")
def listar_produto():
    produtos = acessar_supabase(
        "GET",
        "produtos",
        {"select": "produto_id, nome, preco, estoque, categorias(nome)", "order": "produto_id.desc"},
    )
    return jsonify(produtos)


@app.post("/api/produtos")
def cadastrar_produto():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(mensagem="Envie um objeto JSON válido."), 400

    campos = ["nome", "preco", "estoque", "categoria_id"]
    for campo in campos:
        if dados.get(campo) is None or not isinstance(dados.get(campo), str):
            return jsonify(mensagem=f"O campo {campo} deve ser preenchido com texto"), 400

    nome = dados["nome"].strip()
    texto_preco = dados["preco"].strip().replace(",", ".")
    texto_estoque = dados["estoque"].strip()
    texto_categoria = dados["categoria_id"].strip()

    if len(nome) < 3 or len(nome) > 80:
        return jsonify(mensagem="Nome deve ter de 3 a 80 caracteres"), 400

    try:
        preco = Decimal(texto_preco)
        estoque = int(texto_estoque)
        categoria_id = int(texto_categoria)
    except (InvalidOperation, ValueError):
        return jsonify(mensagem="Informe preço numérico, estoque inteiro e categoria válida!"), 400

    if not preco.is_finite() or preco <= 0 or preco > Decimal("999999.99"):
        return jsonify(mensagem="o preço deve estar entre R$ 0,01 e R$ 999999,99"), 400
    if preco != preco.quantize(Decimal("0.01")):
        return jsonify(mensagem="o preço deve ter no máximo duas casas decimais"), 400
    if estoque < 0 or estoque > 1000000:
        return jsonify(mensagem="o Estoque deve estar entre 0 e 1000000 unidades"), 400
    if categoria_id <= 0 or categoria_id > 2147483647:
        return jsonify(mensagem="selecione uma categoria valida"), 400

    categorias = acessar_supabase(
        "GET",
        "categorias",
        {"select": "categoria_id", "categoria_id": f"eq.{categoria_id}"},
    )
    if not categorias:
        return jsonify(mensagem="a categoria informada não existe "), 400

    acessar_supabase(
        "POST",
        "produtos",
        dados={
            "nome": nome,
            "preco": str(preco),
            "estoque": estoque,
            "categoria_id": categoria_id,
        },
    )

    return jsonify(mensagem="produto cadastrado com sucesso"), 201


@app.get("/api/carrinho")
def listar_carrinho():
    cliente_id = request.args.get("cliente_id", type=int)
    if cliente_id is None or cliente_id <= 0:
        return jsonify(mensagem="Informe um cliente válido para consultar o carrinho."), 400

    itens = acessar_supabase(
        "GET",
        "carrinho",
        {
            "select": "carrinho_id, cliente_id, produto_id, quantidade, produtos(produto_id, nome, preco)",
            "cliente_id": f"eq.{cliente_id}",
            "order": "carrinho_id.desc",
        },
    )

    itens_formatados = []
    total = Decimal("0.00")

    for item in itens:
        produto = item.get("produtos") or {}
        quantidade = int(item.get("quantidade") or 0)
        preco = Decimal(str(produto.get("preco") or "0"))
        subtotal = preco * quantidade
        total += subtotal

        itens_formatados.append(
            {
                "carrinho_id": item.get("carrinho_id"),
                "cliente_id": item.get("cliente_id"),
                "produto_id": item.get("produto_id") or produto.get("produto_id"),
                "nome": produto.get("nome") or "Produto",
                "quantidade": quantidade,
                "preco_unitario": float(preco),
                "subtotal": float(subtotal),
            }
        )

    return jsonify({
        "cliente_id": cliente_id,
        "itens": itens_formatados,
        "total": float(total.quantize(Decimal("0.01"))),
    })


@app.post("/api/carrinho")
def adicionar_item_carrinho():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(mensagem="Envie um objeto JSON válido."), 400

    try:
        cliente_id = int(dados.get("cliente_id"))
        produto_id = int(dados.get("produto_id"))
        quantidade = int(dados.get("quantidade"))
    except (TypeError, ValueError):
        return jsonify(mensagem="Informe cliente, produto e quantidade válidos."), 400

    if cliente_id <= 0:
        return jsonify(mensagem="Selecione um cliente válido."), 400
    if produto_id <= 0:
        return jsonify(mensagem="Selecione um produto válido."), 400
    if quantidade <= 0:
        return jsonify(mensagem="A quantidade deve ser maior que zero."), 400

    clientes = acessar_supabase(
        "GET",
        "clientes",
        {"select": "cliente_id", "cliente_id": f"eq.{cliente_id}"},
    )
    if not clientes:
        return jsonify(mensagem="Cliente não encontrado."), 404

    produtos = acessar_supabase(
        "GET",
        "produtos",
        {"select": "produto_id", "produto_id": f"eq.{produto_id}"},
    )
    if not produtos:
        return jsonify(mensagem="Produto não encontrado."), 404

    itens_existentes = acessar_supabase(
        "GET",
        "carrinho",
        {
            "select": "carrinho_id, produto_id",
            "cliente_id": f"eq.{cliente_id}",
            "produto_id": f"eq.{produto_id}",
        },
    )
    if itens_existentes:
        return jsonify(mensagem="Já existe este produto no carrinho deste cliente. Remova o item antes de adicionar novamente."), 400

    item = acessar_supabase(
        "POST",
        "carrinho",
        dados={
            "cliente_id": cliente_id,
            "produto_id": produto_id,
            "quantidade": quantidade,
        },
    )
    registro = item[0] if isinstance(item, list) and item else item
    return jsonify({"mensagem": "produto adicionado ao carrinho", "item": registro}), 201


@app.delete("/api/carrinho/<int:carrinho_id>")
def remover_item_carrinho(carrinho_id):
    itens = acessar_supabase(
        "GET",
        "carrinho",
        {"select": "carrinho_id", "carrinho_id": f"eq.{carrinho_id}"},
    )
    if not itens:
        return jsonify(mensagem="Item do carrinho não encontrado."), 404

    acessar_supabase(
        "DELETE",
        "carrinho",
        parametros={"carrinho_id": f"eq.{carrinho_id}"},
    )
    return jsonify(mensagem="item removido do carrinho")


@app.errorhandler(requests.exceptions.RequestException)
def tratar_erro_supabase(erro):
    app.logger.warning("falha ao acessar o supabase: %s", type(erro).__name__)

    if isinstance(erro, requests.exceptions.HTTPError):
        try:
            detalhe = erro.response.json()
        except ValueError:
            detalhe = {}

        if isinstance(detalhe, dict):
            codigo = detalhe.get("code")
            if codigo == "23505":
                return jsonify(mensagem="já existe um produto com este nome nesta categoria"), 409
            if codigo == "23503":
                return jsonify(mensagem="a categoria não está mais disponível. Atualize a página"), 405
            if codigo == "23514":
                return jsonify(mensagem="os dados não atendem às regras do banco"), 400

    return jsonify(mensagem="não foi possível acessar o banco, tente novamente"), 503


@app.errorhandler(500)
def tratar_erro_inesperado(erro):
    app.logger.exception("erro interno inesperado: %s", erro)
    return jsonify(mensagem="ocorreu uma falha interna"), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


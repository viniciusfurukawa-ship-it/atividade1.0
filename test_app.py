import app as app_module


def test_cliente_sem_nome_rejeitado():
    client = app_module.app.test_client()
    resposta = client.post("/api/clientes", json={"email": "joao@email.com"})

    assert resposta.status_code == 400
    dados = resposta.get_json()
    assert "nome" in dados["mensagem"].lower()


def test_carrinho_nao_permite_produto_duplicado(monkeypatch):
    client = app_module.app.test_client()

    def fake_acessar_supabase(metodo, tabela, parametros=None, dados=None):
        if metodo == "GET" and tabela == "clientes":
            return [{"cliente_id": 1, "nome": "João", "email": "joao@email.com"}]
        if metodo == "GET" and tabela == "produtos":
            return [{"produto_id": 3, "nome": "Caneta", "preco": "12.00"}]
        if metodo == "GET" and tabela == "carrinho":
            return [{
                "carrinho_id": 7,
                "cliente_id": 1,
                "produto_id": 3,
                "quantidade": 1,
                "produtos": {"produto_id": 3, "nome": "Caneta", "preco": "12.00"},
            }]
        if metodo == "POST" and tabela == "carrinho":
            return [{"carrinho_id": 8, "cliente_id": 1, "produto_id": 3, "quantidade": 2}]
        raise AssertionError(f"Chamada inesperada: {metodo} {tabela}")

    monkeypatch.setattr(app_module, "acessar_supabase", fake_acessar_supabase)

    resposta = client.post(
        "/api/carrinho",
        json={"cliente_id": 1, "produto_id": 3, "quantidade": 2},
    )

    assert resposta.status_code == 400
    dados = resposta.get_json()
    assert "já existe" in dados["mensagem"].lower()


def test_cliente_valido_cadastra_com_sucesso(monkeypatch):
    client = app_module.app.test_client()

    def fake_acessar_supabase(metodo, tabela, parametros=None, dados=None):
        if metodo == "POST" and tabela == "clientes":
            return [{"cliente_id": 12, "nome": "Maria", "email": "maria@email.com", "telefone": "11999999999"}]
        raise AssertionError(f"Chamada inesperada: {metodo} {tabela}")

    monkeypatch.setattr(app_module, "acessar_supabase", fake_acessar_supabase)

    resposta = client.post(
        "/api/clientes",
        json={"nome": "Maria", "email": "maria@email.com", "telefone": "11999999999"},
    )

    assert resposta.status_code == 201
    dados = resposta.get_json()
    assert dados["mensagem"] == "cliente cadastrado com sucesso"

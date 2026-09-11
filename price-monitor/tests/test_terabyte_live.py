from price_monitor.terabyte_live import (
    compute_live_score,
    extract_product_page,
    extract_products,
    is_category_url,
    is_product_url,
)


def test_extracts_listing_product():
    html = """
    <div class="card">
      <a href="/produto/12345/placa-de-video-teste">Placa de Vídeo GeForce RTX 5090 32GB</a>
      <div>De: R$ 14.999,90 por: R$ 8.999,90 à vista</div>
      <div>12x de R$ 882,34 sem juros</div>
    </div>
    """
    rows = extract_products(html, "https://www.terabyteshop.com.br/hardware/", "Hardware")
    assert len(rows) == 1
    assert rows[0]["price"] == 8999.90
    assert rows[0]["original_price"] == 14999.90


def test_sold_out_card_does_not_borrow_neighbor_price():
    html = """
    <section class="grid">
      <div class="card">
        <a href="/produto/40123/cadeira-yako-roxa">Cadeira Gamer Ninja Yako, Reclinável, Preta e Roxa</a>
        <div>Todos vendidos</div>
      </div>
      <div class="card">
        <a href="/produto/50000/almofada-kitty">Almofada Gamer Ninja Soft Kitty</a>
        <div>De: R$ 189,99 por: R$ 109,99 à vista</div>
      </div>
    </section>
    """
    rows = extract_products(html, "https://www.terabyteshop.com.br/cadeira/cadeira-gamer/gamer-ninja", "Categoria rotativa")
    urls = {x["url"] for x in rows}
    assert "https://www.terabyteshop.com.br/produto/40123/cadeira-yako-roxa" not in urls
    assert "https://www.terabyteshop.com.br/produto/50000/almofada-kitty" in urls


def test_product_page_uses_main_de_por_pair():
    html = """
    <html><head><title>Placa Mãe ASUS Teste | Terabyte</title></head><body>
      <h1>Placa Mãe ASUS Teste</h1>
      <div>De: R$ 1.097,90 por: R$ 699,99 à vista</div>
      <div>12x de R$ 68,63 sem juros</div>
      <section>Você também pode gostar <div>R$ 19,99</div></section>
    </body></html>
    """
    row = extract_product_page(html, "https://www.terabyteshop.com.br/produto/1/teste")
    assert row is not None
    assert row["price"] == 699.99
    assert row["original_price"] == 1097.90


def test_product_page_rejects_unavailable_sku():
    html = """
    <html><body><h1>Combo Logitech MK235</h1><div>Produto Indisponível</div>
    <section>Já que esgotou, veja este outro produto por R$ 19,99</section></body></html>
    """
    assert extract_product_page(html, "https://www.terabyteshop.com.br/produto/2/teste") is None


def test_sudden_drop_becomes_critical():
    row = {
        "title": "Placa de Vídeo GeForce RTX 5090 32GB",
        "price": 3999.90,
        "original_price": 9999.90,
        "url": "https://www.terabyteshop.com.br/produto/1/x",
    }
    state = {
        "last_price": 8999.90,
        "observations": [
            {"at": "a", "price": 8999.90},
            {"at": "b", "price": 8799.90},
            {"at": "c", "price": 8999.90},
        ],
    }
    scored = compute_live_score(row, state)
    assert scored["score"] >= 90
    assert scored["sudden_drop_pct"] >= 50


def test_strikethrough_alone_never_becomes_strong_alert():
    row = {
        "title": "Pendrive USB Tipo-C 64GB",
        "price": 79.90,
        "original_price": 199.99,
        "url": "https://www.terabyteshop.com.br/produto/3/x",
    }
    scored = compute_live_score(row, None)
    assert scored["advertised_drop_pct"] >= 60
    assert scored["score"] < 70


def test_stable_price_is_not_live_alert():
    row = {
        "title": "Mouse Gamer USB comum",
        "price": 99.90,
        "original_price": 129.90,
        "url": "https://www.terabyteshop.com.br/produto/2/x",
    }
    state = {
        "last_price": 99.90,
        "observations": [
            {"at": "a", "price": 99.90},
            {"at": "b", "price": 99.90},
            {"at": "c", "price": 99.90},
        ],
    }
    scored = compute_live_score(row, state)
    assert scored["score"] < 60
    assert scored["sudden_drop_pct"] == 0


def test_url_scope():
    assert is_product_url("https://www.terabyteshop.com.br/produto/123/teste")
    assert is_category_url("https://www.terabyteshop.com.br/hardware/placas-de-video")
    assert not is_category_url("https://example.com/hardware/")

from price_monitor.terabyte_live import compute_live_score, extract_products, is_category_url, is_product_url


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

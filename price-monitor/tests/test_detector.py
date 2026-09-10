from price_monitor.detector import detect_anomalies
from price_monitor.models import Offer
from price_monitor.normalize import product_key
from price_monitor.sources.mercadolivre import MercadoLivreSource
from price_monitor.sources.retailer import RetailerSource
from price_monitor.sources.shopee import ShopeeSource
from price_monitor.utils import extract_brl_prices, pick_current_and_original


def offer(price, original=None, source="Teste", key="apple|iphone-17-pro|max", url=None):
    x = Offer(source=source, title="Apple iPhone 17 Pro Max 256GB", price=price, original_price=original, url=url or f"https://example.com/{source}/{price}", store_name="Loja Oficial", official=True)
    x.product_key = key; return x


def test_extreme_price_de_can_flag_first_run():
    found = detect_anomalies([offer(1499, 6999)], {"products": {}})
    assert len(found) == 1 and found[0].baseline_kind == "preco_de"


def test_normal_advertised_discount_does_not_flag():
    assert detect_anomalies([offer(3999, 6999)], {"products": {}}) == []


def test_market_median_flags_outlier():
    rows = [offer(6999, source="A", url="https://a"), offer(6799, source="B", url="https://b"), offer(1499, source="C", url="https://c")]
    found = detect_anomalies(rows, {"products": {}})
    assert len(found) == 1 and found[0].offer.price == 1499 and found[0].baseline_kind == "mercado_atual"


def test_history_flags_outlier():
    history = {"products": {"apple|iphone-17-pro|max": [{"ts": "2026-09-01T00:00:00+00:00", "price": p} for p in [6500, 6600, 6400, 6550, 6700]]}}
    found = detect_anomalies([offer(1900, original=None)], history)
    assert len(found) == 1 and found[0].baseline_kind == "historico"


def test_price_parser_ignores_installment():
    prices = extract_brl_prices("De R$ 7.999,00 por R$ 2.999,00 ou 10x de R$ 299,90")
    assert 299.90 not in prices
    assert pick_current_and_original(prices) == (2999.0, 7999.0)


def test_price_parser_accepts_mercado_livre_without_cents():
    prices = extract_brl_prices("R$12.499 R$9.539 23% OFF ou 10x R$1.059 sem juros")
    assert 1059.0 not in prices
    assert pick_current_and_original(prices) == (9539.0, 12499.0)


def test_price_parser_ignores_savings_amount():
    text = "R$ 3.349,00 -12% R$ 2.943,08 no Pix Economize R$ 255,92 no Pix ou R$ 3.199,00 em 10x de R$ 319,90 sem juros"
    prices = extract_brl_prices(text)
    assert 255.92 not in prices
    assert 319.90 not in prices
    assert pick_current_and_original(prices) == (2943.08, 3349.0)


def test_price_parser_ignores_installment_when_site_glues_em10x():
    text = "R$ 4.299,00 -14% R$ 3.679,08 no Pix Economize R$ 319,92 no Pix ou R$ 3.999,00 em10x de R$ 399,90 sem juros"
    prices = extract_brl_prices(text)
    assert 319.92 not in prices
    assert 399.90 not in prices
    assert pick_current_and_original(prices) == (3679.08, 4299.0)


def test_price_parser_tcl_fridge_ignores_679_installment():
    text = "R$ 7.489,00 -16% R$ 6.255,08 no Pix Economize R$ 543,92 no Pix ou R$ 6.799,00 em10x de R$ 679,90 sem juros"
    prices = extract_brl_prices(text)
    assert 543.92 not in prices
    assert 679.90 not in prices
    assert pick_current_and_original(prices) == (6255.08, 7489.0)


def test_price_parser_ignores_money_discount_after_value():
    prices = extract_brl_prices("Preço R$ 2.999,00 + R$ 200,00 de desconto com cupom")
    assert prices == [2999.0]


def test_product_key_is_stable_enough():
    assert product_key("Apple iPhone 17 Pro Max 256GB Preto") == product_key("iPhone 17 Pro Max Apple 256 GB - Preto")


def test_ml_card_identifies_only_allowlisted_store_line():
    stores = [{"name": "Motorola", "marker": "Motorola", "verified_official": True}]
    assert MercadoLivreSource._card_store("Moto G86\nMotorola 4.9\nR$ 3.499", stores) == "Motorola"
    assert MercadoLivreSource._card_store("Moto G86 Motorola\nVikings 4.9\nR$ 2.999", stores) is None


def test_shopee_dominant_shop_id():
    hrefs = ["https://shopee.com.br/a-i.123.1", "https://shopee.com.br/b-i.123.2", "https://shopee.com.br/c-i.999.3"]
    assert ShopeeSource._dominant_shop_id(hrefs) == "123"


def test_retailer_accepts_only_product_links_on_own_domain():
    source = RetailerSource({
        "name": "Loja Teste",
        "base_url": "https://www.exemplo.com.br/",
        "direct_retailer": True,
        "catalog_urls": ["https://www.exemplo.com.br/categoria/notebooks"],
    })
    assert source._allowed_product_url("https://www.exemplo.com.br/produto/notebook-x") is True
    assert source._allowed_product_url("https://exemplo.com.br/categoria/notebooks") is False
    assert source._allowed_product_url("https://www.exemplo.com.br/") is False
    assert source._allowed_product_url("https://marketplace-outro.com/produto/notebook-x") is False

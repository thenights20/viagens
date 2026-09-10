from price_monitor.detector import detect_anomalies
from price_monitor.models import Offer
from price_monitor.normalize import product_key
from price_monitor.utils import extract_brl_prices, pick_current_and_original


def offer(price, original=None, source="Teste", key="apple|iphone-17-pro|max", url=None):
    x = Offer(
        source=source,
        title="Apple iPhone 17 Pro Max 256GB",
        price=price,
        original_price=original,
        url=url or f"https://example.com/{source}/{price}",
        store_name="Loja Oficial",
        official=True,
    )
    x.product_key = key
    return x


def test_extreme_price_de_can_flag_first_run():
    rows = [offer(1499, 6999)]
    found = detect_anomalies(rows, {"products": {}})
    assert len(found) == 1
    assert found[0].baseline_kind == "preco_de"


def test_normal_advertised_discount_does_not_flag():
    rows = [offer(3999, 6999)]
    found = detect_anomalies(rows, {"products": {}})
    assert found == []


def test_market_median_flags_outlier():
    rows = [
        offer(6999, source="A", url="https://a"),
        offer(6799, source="B", url="https://b"),
        offer(1499, source="C", url="https://c"),
    ]
    found = detect_anomalies(rows, {"products": {}})
    assert len(found) == 1
    assert found[0].offer.price == 1499
    assert found[0].baseline_kind == "mercado_atual"


def test_history_flags_outlier():
    history = {
        "products": {
            "apple|iphone-17-pro|max": [
                {"ts": "2026-09-01T00:00:00+00:00", "price": p}
                for p in [6500, 6600, 6400, 6550, 6700]
            ]
        }
    }
    found = detect_anomalies([offer(1900, original=None)], history)
    assert len(found) == 1
    assert found[0].baseline_kind == "historico"


def test_price_parser_ignores_installment():
    text = "De R$ 7.999,00 por R$ 2.999,00 ou 10x de R$ 299,90"
    prices = extract_brl_prices(text)
    assert 299.90 not in prices
    current, original = pick_current_and_original(prices)
    assert current == 2999.0
    assert original == 7999.0


def test_product_key_is_stable_enough():
    a = product_key("Apple iPhone 17 Pro Max 256GB Preto")
    b = product_key("iPhone 17 Pro Max Apple 256 GB - Preto")
    assert a == b

from price_monitor.bug_rules import score_product


def test_air_fryer_14_is_critical():
    row = score_product(title="Fritadeira Sem Óleo Air Fryer 5L Mondial", price=14)
    assert row["bug_score"] >= 80


def test_microwave_79_is_critical():
    row = score_product(title="Micro-ondas 21 Litros Mondial 1200W", price=79)
    assert row["bug_score"] >= 80


def test_ps5_449_is_critical():
    row = score_product(title="Console PlayStation 5 Slim Digital 825GB", price=449)
    assert row["bug_score"] >= 80


def test_rtx_5090_1899_is_critical():
    row = score_product(title="Placa de Video Zotac GeForce RTX 5090 Solid OC 32GB", price=1899)
    assert row["bug_score"] >= 80


def test_normal_price_does_not_trigger():
    row = score_product(title="Console PlayStation 5 Slim Digital 825GB", price=3600)
    assert row["bug_score"] < 60


def test_fake_strikethrough_alone_is_capped():
    row = score_product(title="Produto genérico", price=100, original_price=1000)
    assert row["bug_score"] < 70

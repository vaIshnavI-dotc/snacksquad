from backend.app.risk import risk_level


def test_fake_high():
    assert risk_level("fake", 0.95) == "high"


def test_fake_medium():
    assert risk_level("fake", 0.55) == "medium"


def test_real_low():
    assert risk_level("real", 0.05) == "low"


def test_real_borderline_medium():
    assert risk_level("real", 0.45) == "medium"

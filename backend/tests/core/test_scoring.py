"""Step 5 — confidence bucketing (TDD)."""

from core.services.scoring import bucket


class TestBucket:
    def test_high(self):
        assert bucket(0.9) == "high"
        assert bucket(0.66) == "high"

    def test_medium(self):
        assert bucket(0.5) == "medium"
        assert bucket(0.33) == "medium"

    def test_low(self):
        assert bucket(0.2) == "low"
        assert bucket(0.0) == "low"

    def test_custom_thresholds(self):
        assert bucket(0.4, high=0.8, medium=0.3) == "medium"
        assert bucket(0.85, high=0.8, medium=0.3) == "high"
        assert bucket(0.1, high=0.8, medium=0.3) == "low"

    def test_negative_is_low(self):
        assert bucket(-1.0) == "low"

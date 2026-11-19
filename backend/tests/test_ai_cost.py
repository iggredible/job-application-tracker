"""Estimated cost comes from a small price table keyed by model."""

from decimal import Decimal

from app.ai.cost import estimate_cost
from app.core.config import MODEL_PRICES, ModelPrice

PRICES = {"priced-model": ModelPrice(input_per_mtok=Decimal("2"), output_per_mtok=Decimal("10"))}


def test_cost_is_tokens_times_the_per_million_price() -> None:
    # 1,000 * $2 / 1M + 500 * $10 / 1M = $0.002 + $0.005
    assert estimate_cost("priced-model", 1000, 500, PRICES) == Decimal("0.007000")


def test_cost_is_rounded_to_the_six_places_of_the_column() -> None:
    assert estimate_cost("priced-model", 1, 1, PRICES) == Decimal("0.000012")


def test_cost_is_null_when_the_model_is_not_in_the_table() -> None:
    assert estimate_cost("unknown-model", 1000, 500, PRICES) is None


def test_cost_is_null_when_a_token_count_is_missing() -> None:
    assert estimate_cost("priced-model", None, 500, PRICES) is None
    assert estimate_cost("priced-model", 1000, None, PRICES) is None


def test_the_default_price_table_matches_the_published_prices() -> None:
    # https://platform.claude.com/docs/en/about-claude/pricing, dollars per million tokens.
    assert {model: (p.input_per_mtok, p.output_per_mtok) for model, p in MODEL_PRICES.items()} == {
        "claude-sonnet-5-5": (Decimal("2"), Decimal("10")),
        "claude-opus-5-5": (Decimal("4"), Decimal("20")),
        "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50")),
        "claude-fable-5-2": (Decimal("8"), Decimal("40")),
    }

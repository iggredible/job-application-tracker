from decimal import ROUND_HALF_UP, Decimal

from app.core.config import MODEL_PRICES, ModelPrice

_MILLION = Decimal(1_000_000)
_COLUMN_PLACES = Decimal("0.000001")  # ai_calls.estimated_cost is NUMERIC(10, 6)


def estimate_cost(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    prices: dict[str, ModelPrice] = MODEL_PRICES,
) -> Decimal | None:
    """Dollars for one call, or None when the model has no price or a token count is missing."""
    price = prices.get(model)
    if price is None or input_tokens is None or output_tokens is None:
        return None
    cost = (
        Decimal(input_tokens) * price.input_per_mtok
        + Decimal(output_tokens) * price.output_per_mtok
    ) / _MILLION
    return cost.quantize(_COLUMN_PLACES, rounding=ROUND_HALF_UP)

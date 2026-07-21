from decimal import Decimal, ROUND_HALF_UP


def finite(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError("Expected a finite nonnegative decimal")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -4 or value > Decimal("1000000000"):
        raise ValueError("At most four decimal places and one billion are supported")
    return value


def amount(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (finite(quantity) * finite(unit_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def comparable(left: str, right: str) -> bool:
    if left not in {"USD", "EUR", "GBP"} or left != right:
        raise ValueError("Currency mismatch or unsupported currency; no FX conversion")
    return True

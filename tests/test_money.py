from decimal import Decimal as D
import pytest
from reconciliation.money import amount, comparable


def test_rounds_only_extended_amount():
    assert amount(D("3"), D("0.335")) == D("1.01")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.00001"])
def test_invalid_money_rejected(value):
    with pytest.raises(ValueError):
        amount(D(value), D("1"))


def test_float_rejected():
    with pytest.raises(ValueError):
        amount(1.2, D("1"))


def test_currency_cannot_convert():
    assert comparable("USD", "USD")
    with pytest.raises(ValueError):
        comparable("USD", "EUR")
    with pytest.raises(ValueError):
        comparable("JPY", "JPY")

"""Fail-closed extraction of a candidate amount, never acceptance of a quote.

The caller must independently verify the source identifiers and every stay,
guest, meal, cancellation, eligibility, fee, freshness and request condition.
The fictional data-* contract used here is not a travel-site DOM adapter.
"""
from decimal import Decimal, InvalidOperation
import re


IDENTITY_ATTRIBUTES = {
    "supplier_id": "data-supplier-id",
    "hotel_id": "data-hotel-id",
    "room_id": "data-room-id",
    "rate_id": "data-rate-id",
}


def extract_candidate_amount(cards, expected, expected_name, expected_currency):
    """Require one source product, one name and one explicit monetary value.

    IDs stay strings, currency must match the caller's expected currency, and
    the returned amount stays an unrounded decimal string. This function does
    not validate request binding. No currency, tax, price-role or policy
    information is inferred from a display number.
    """
    if len(cards) != 1 or not isinstance(expected, dict):
        return None
    if not isinstance(expected_name, str) or not expected_name.strip():
        return None
    if not isinstance(expected_currency, str) or not re.fullmatch(r"[A-Z]{3}", expected_currency):
        return None
    card = cards[0]
    for field, attribute in IDENTITY_ATTRIBUTES.items():
        value = expected.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            return None
        if card.xpath(f"./@{attribute}").get() != value:
            return None
    if card.css("h3::text").getall() != [expected_name]:
        return None
    if card.xpath("./@data-currency").get() != expected_currency:
        return None
    price_nodes = card.css("span.price")
    if len(price_nodes) != 1 or len(price_nodes[0].xpath("./*")) != 0:
        return None
    texts = price_nodes[0].xpath("./text()").getall()
    if len(texts) != 1:
        return None
    amount = str(texts[0]).strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount):
        return None
    try:
        number = Decimal(amount)
    except InvalidOperation:
        return None
    if not number.is_finite() or number <= 0:
        return None
    return {
        **{field: expected[field] for field in IDENTITY_ATTRIBUTES},
        "name": expected_name,
        "candidate_amount": amount,
        "currency": expected_currency,
        "request_currency_binding_verified": False,
        "strict_quote_accepted": False,
        "remaining_verification": [
            "physical-room mapping and attributes",
            "request/response binding and stay/guests",
            "meal schedule and full cancellation intervals",
            "customer-price role, all mandatory charges and eligibility",
            "source authenticity, observation time and availability",
        ],
    }

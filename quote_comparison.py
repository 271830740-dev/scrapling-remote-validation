"""Compare source-normalized candidate quotes, never accept live evidence.

Adapters must independently establish every verification/evidence assertion.
This module cannot authenticate those assertions or interpret provider enums.
Platform IDs and price amounts may differ; normalized conditions must match.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
import re


class IncompleteQuote(ValueError):
    pass


def require(test, reason):
    if not test:
        raise IncompleteQuote(reason)


def text(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def instant(value):
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value),
        "absolute_time_missing_or_invalid")
    require(not value.endswith("-00:00"), "unknown_utc_offset")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def money(value):
    require(isinstance(value, str) and len(value) <= 128 and re.fullmatch(
        r"[0-9]+(?:\.[0-9]+)?", value), "decimal_amount_required")
    return Decimal(value)


def policy_key(policy, currency, nights):
    require(isinstance(policy, dict) and set(policy) == {"complete_verified", "intervals"}
            and policy["complete_verified"] is True, "full_cancellation_policy_unverified")
    rows = policy["intervals"]
    require(isinstance(rows, list) and bool(rows), "full_cancellation_policy_missing")
    result = []
    previous_end = None
    for index, row in enumerate(rows):
        require(isinstance(row, dict) and set(row) == {"start_at", "end_at", "penalty"},
                "cancellation_interval_shape")
        start = instant(row["start_at"]) if row["start_at"] is not None else None
        end = instant(row["end_at"]) if row["end_at"] is not None else None
        require((start is None) == (index == 0) and (end is None) == (index == len(rows)-1),
                "cancellation_coverage_incomplete")
        require(index == 0 or start == previous_end, "cancellation_gap_or_overlap")
        require(start is None or end is None or start < end, "cancellation_interval_order")
        penalty = row["penalty"]
        require(isinstance(penalty, dict), "cancellation_penalty_missing")
        kind = penalty.get("kind")
        if kind == "none":
            require(set(penalty) == {"kind"}, "cancellation_penalty_shape")
            pkey = (kind,)
        elif kind in {"fixed", "percent"}:
            keys = {"kind", "amount", "currency", "basis"} if kind == "fixed" else {"kind", "value", "basis"}
            require(set(penalty) == keys, "cancellation_penalty_shape")
            require(penalty.get("basis") == "stay_total", "unsupported_cancellation_basis")
            amount = money(penalty["amount"] if kind == "fixed" else penalty["value"])
            require(kind != "percent" or amount <= 100, "cancellation_percent_out_of_range")
            require(kind != "fixed" or penalty["currency"] == currency, "cancellation_currency_mismatch")
            pkey = (kind, amount, penalty["basis"], currency if kind == "fixed" else None)
        elif kind == "first_nights":
            require(set(penalty) == {"kind", "nights", "basis"} and
                    type(penalty["nights"]) is int and 1 <= penalty["nights"] <= nights and
                    penalty["basis"] == "nightly_customer_total_schedule", "cancellation_night_basis_invalid")
            pkey = (kind, penalty["nights"], penalty["basis"])
        else:
            raise IncompleteQuote("unsupported_cancellation_penalty")
        result.append((start, end, pkey))
        previous_end = end
    return tuple(result)


CONDITION_FIELDS = {
    "property_key", "physical_room_key", "check_in", "check_out", "rooms",
    "meal_state", "meal_schedule", "payment_timing", "audience_key", "market", "device",
    "other_terms", "cancellation_policy", "complete_verified", "evidence_ref",
}


def normalized(quote, now, max_age):
    require(isinstance(quote, dict), "quote_missing")
    source, c, price = quote.get("source"), quote.get("conditions"), quote.get("price")
    require(isinstance(source, dict), "source_missing")
    for key in ("platform", "hotel_id", "room_id", "rate_id", "request_id", "response_id", "evidence_ref"):
        require(text(source.get(key)), "source_identity_or_evidence_missing")
    require(source.get("request_binding_verified") is True and source.get("available") is True,
            "request_binding_or_availability_unverified")
    observed = instant(source.get("observed_at"))
    require(0 <= (now-observed).total_seconds() <= max_age, "quote_stale_or_future")
    require(isinstance(c, dict) and set(c) == CONDITION_FIELDS and c["complete_verified"] is True,
            "conditions_missing_or_unverified")
    for key in ("property_key", "physical_room_key", "audience_key", "market", "device", "evidence_ref"):
        require(text(c[key]), "condition_identity_missing")
    require(c["payment_timing"] in {"prepaid", "at_property", "split"}, "payment_timing_unknown")
    for key in ("check_in", "check_out"):
        require(isinstance(c[key], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", c[key]), "stay_date_invalid")
    checkin, checkout = date.fromisoformat(c["check_in"]), date.fromisoformat(c["check_out"])
    require(checkout > checkin, "stay_date_order")
    rooms = c["rooms"]
    require(isinstance(rooms, list) and bool(rooms), "requested_rooms_missing")
    room_key = []
    for room in rooms:
        require(isinstance(room, dict) and set(room) == {"adults", "children_ages"} and
                type(room["adults"]) is int and room["adults"] > 0 and
                isinstance(room["children_ages"], list) and
                all(type(age) is int and age >= 0 for age in room["children_ages"]), "requested_guests_invalid")
        room_key.append((room["adults"], tuple(sorted(room["children_ages"]))))
    require(isinstance(c["meal_schedule"], list), "meal_schedule_missing")
    require((c["meal_state"] == "verified_no_meals" and not c["meal_schedule"]) or
            (c["meal_state"] == "verified_schedule" and bool(c["meal_schedule"])),
            "meal_state_missing_or_inconsistent")
    meals = []
    for meal in c["meal_schedule"]:
        require(isinstance(meal, dict) and set(meal) == {"date", "room_index", "kind", "servings"}
                and text(meal["kind"]) and type(meal["room_index"]) is int and
                0 <= meal["room_index"] < len(rooms) and type(meal["servings"]) is int and
                meal["servings"] > 0, "meal_schedule_invalid")
        require(isinstance(meal["date"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", meal["date"]),
                "meal_date_invalid")
        # Actual service dates: checkout-day breakfast and checkin-day dinner are valid.
        # Completeness and guest applicability require original-source normalization.
        require(checkin <= date.fromisoformat(meal["date"]) <= checkout, "meal_date_outside_stay")
        meals.append((meal["date"], meal["room_index"], meal["kind"], meal["servings"]))
    require(len(meals) == len({row[:3] for row in meals}), "duplicate_or_conflicting_meal_records")
    require(isinstance(c["other_terms"], list) and all(text(term) for term in c["other_terms"]),
            "other_terms_unverified")
    price_fields = {"role", "basis", "currency", "stay_total", "coverage_verified", "evidence_ref"}
    require(isinstance(price, dict) and price_fields <= set(price) <= price_fields | {"components"},
            "price_fields_missing_or_unsupported")
    require(price.get("role") == "customer_payable" and
            price.get("basis") == "all_rooms_full_stay_all_mandatory_charges" and
            price.get("coverage_verified") is True and text(price.get("evidence_ref")),
            "final_payable_coverage_unverified")
    currency = price.get("currency")
    require(isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency), "currency_unknown")
    amount = money(price.get("stay_total"))
    require(amount > 0, "nonpositive_price")
    if "components" in price:
        components = price["components"]
        require(isinstance(components, list) and 0 < len(components) <= 4096,
                "price_components_missing_or_excessive")
        amounts = []
        for component in components:
            require(isinstance(component, dict) and set(component) == {"role", "amount", "currency"}
                    and component["role"] in {"room_subtotal", "mandatory_tax", "mandatory_fee"}
                    and component["currency"] == currency, "price_component_invalid")
            amounts.append(money(component["amount"]))
        with localcontext() as context:
            context.prec = 260
            require(sum(amounts, Decimal(0)) == amount, "price_component_total_mismatch")
    key = (c["property_key"], c["physical_room_key"], checkin, checkout, tuple(room_key),
           c["meal_state"], tuple(sorted(meals)), c["payment_timing"], c["audience_key"], c["market"], c["device"],
           tuple(sorted(c["other_terms"])), policy_key(c["cancellation_policy"], currency, (checkout-checkin).days))
    return key, currency, amount, observed


def compare_normalized_quotes(our, other, *, now_utc, max_age_seconds, max_skew_seconds):
    """Return candidate price differences only after normalized conditions match.

    Evidence refs/verification flags are caller assertions, not authenticated
    source proof. Independent original-source acceptance remains mandatory.
    No default freshness, implicit exchange rate or monetary rounding is used.
    """
    rejected = {"status": "not_comparable", "strict_quote_accepted": False}
    try:
        require(type(max_age_seconds) is int and max_age_seconds > 0 and
                type(max_skew_seconds) is int and max_skew_seconds >= 0, "freshness_window_invalid")
        now = instant(now_utc)
        a, b = normalized(our, now, max_age_seconds), normalized(other, now, max_age_seconds)
        require(a[0] == b[0], "normalized_conditions_differ")
        require(a[1] == b[1], "quote_currencies_differ")
        require(abs((a[3]-b[3]).total_seconds()) <= max_skew_seconds, "observation_skew_exceeded")
        with localcontext() as context:
            context.prec = 260  # Each accepted decimal string is at most128 chars.
            delta = a[2]-b[2]
        return {"status": "candidate_comparison", "currency": a[1],
                "our_stay_total": format(a[2], "f"), "other_stay_total": format(b[2], "f"),
                "difference_our_minus_other": format(delta, "f"),
                "lower_price_side": "our" if delta < 0 else "other" if delta > 0 else "equal",
                "strict_quote_accepted": False,
                "remaining_verification": "Independently authenticate both original sources and every adapter evidence assertion"}
    except IncompleteQuote as error:
        return {**rejected, "reason": str(error)}
    except (ValueError, TypeError, KeyError, OverflowError):
        return {**rejected, "reason": "invalid_normalized_input"}

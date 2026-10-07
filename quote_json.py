"""Decode raw quote JSON without silently losing conflicting source fields.

This is a transport guard, not a website adapter or quote acceptance check.
Keep the raw response separately. Business identifiers, currency, monetary
units, rounding, conditions and request identity still require source checks.
"""
import json
from decimal import Decimal, InvalidOperation


def decode_quote_json(raw, *, max_bytes=1_048_576):
    """Accept bounded UTF-8 JSON; reject duplicate decoded keys at any depth.

    Decimal number tokens retain decimal precision. Integer tokens stay exact
    integers; this does not make a numeric hotel ID a validated text ID.
    Repeated keys in separate objects are allowed. Duplicate keys in one
    object, including differently escaped spellings, are rejected.
    """
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("Invalid response byte limit")
    if not isinstance(raw, (str, bytes)):
        raise ValueError("Expected raw response text or bytes")
    try:
        if isinstance(raw, bytes):
            if len(raw) > max_bytes:
                raise ValueError("Response exceeds byte limit")
            text = raw.decode("utf-8", errors="strict")
        else:
            if len(raw) > max_bytes or len(raw.encode("utf-8")) > max_bytes:
                raise ValueError("Response exceeds byte limit")
            text = raw
        if text.startswith("\ufeff"):
            raise ValueError("Unexpected response BOM")

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    # Do not echo source key/value or response fragments.
                    raise ValueError("Duplicate JSON object member")
                result[key] = value
            return result

        def number(token, convert):
            if len(token) > 128:
                raise ValueError("Numeric token exceeds configured limit")
            return convert(token)

        def reject_constant(_):
            raise ValueError("Non-JSON numeric constant")

        return json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_float=lambda token: number(token, Decimal),
            parse_int=lambda token: number(token, int),
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, InvalidOperation):
        raise ValueError("Invalid or excessively nested UTF-8 JSON") from None
